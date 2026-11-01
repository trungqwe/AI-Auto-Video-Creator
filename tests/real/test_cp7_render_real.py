"""CP7-8 / RG-07: render thật qua RealFfmpegRenderer (5 preset x 2 video NVENC + 1 libx264), QC ffprobe/loudnorm/signalstats, lỗi thật, chốt chặn đĩa; không renderer giả cho các video QC."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import wave
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402
import cp7_common as c  # noqa: E402
import cp7_media_probe as mp  # noqa: E402
from controlplane.api.wiring.production_profile import load_production_profile  # noqa: E402
from controlplane.domain.orchestration import ExecutionGrant  # noqa: E402
from controlplane.domain.orchestration.resource_admission import (  # noqa: E402
    AdmissionLimits,
    Admitted,
    ResourceNeed,
    ResourceSnapshot,
    Wait,
    WaitReason,
    decide_admission,
)
from controlplane.domain.statemachine import OperationState  # noqa: E402
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease  # noqa: E402
from render.adapters.ass_manifest import build_ass_material  # noqa: E402
from render.adapters.config_render_sources import ass_inputs, render_config_payloads  # noqa: E402
from render.adapters.postgres_plan_assets import ScriptSegmentInfo  # noqa: E402
from render.adapters.real_ffmpeg_renderer import (  # noqa: E402
    FfmpegPinRejected,
    RealFfmpegRenderer,
    build_final_argv,
    verify_ffmpeg_pin,
    sha256_file as renderer_sha256,
)
from render.adapters.real_ffprobe_probe import RealFfprobeProbe  # noqa: E402
from render.adapters.real_output_inspector import (  # noqa: E402
    Band,
    InspectionInputs,
    InspectorSettings,
    RealOutputInspector,
    evenly_sampled,
    karaoke_observations,
    parse_ass_dialogues,
)
from render.application.package_pipeline import CommandContext  # noqa: E402
from render.application.render_video import (  # noqa: E402
    InMemoryRenderUnitOfWork,
    ReconcileRenderCommand,
    ReconcileRequired,
    RenderPipeline,
    RenderVideoCommand,
)
from render.domain.karaoke_plan import TimedWord  # noqa: E402
from render.domain.package_contract import validate_render_package_payload  # noqa: E402
from render.domain.preset import build_preset_revision  # noqa: E402
from render.domain.render_command import (  # noqa: E402
    MaterializedPaths,
    OutputProfile,
    ToolIdentity,
    build_render_command,
)
from render.domain.validate_package import PackageValidationReport, _compute_report_id  # noqa: E402
from render.ports.lease import GpuLeaseUnavailable  # noqa: E402
from render.ports.renderer import RendererStatus, RendererTimeout  # noqa: E402
from render.ports.repositories import KIND_PACKAGE  # noqa: E402
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts  # noqa: E402
from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig  # noqa: E402
from voice.domain.timing_coverage import TokenizationPolicy  # noqa: E402
from voice.domain.tts_invocation import ProviderRouteDecision  # noqa: E402
from voice.ports.aligner import AlignerError, AlignmentRequest  # noqa: E402
from voice.ports.script_text import ScriptText  # noqa: E402

LOCK = REPO / 'tools' / 'launcher' / 'prod' / 'model-weights.lock.json'
PROFILE = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
RUNTIME_LOCK = REPO / 'tools' / 'runtime' / 'runtime.lock.json'
PYPROJECT = REPO / 'pyproject.toml'
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-8' / 'report.md'
FFMPEG_EXE = mp.DEFAULT_FFMPEG
FFPROBE_EXE = mp.DEFAULT_FFPROBE
DEADLINE = c.Deadline(4 * 3600)
RENDER_TIMEOUT_S = 900
MAX_BYTES = 157286400
DUR_MIN_S = 61.0
DUR_MAX_S = 70.0
HOOK_SIM_MIN = 0.85
HOOK_AUDIO_MIN_DB = -40.0
CONTINUITY_MIN = 0.6
SUBTITLE_MIN_SHARE = 0.9
KARAOKE_TOL_MS = 150
KARAOKE_MIN_SHARE = 0.95
LOUD_TARGET = -16.0
LOUD_TOL = 1.5
TP_MAX = -1.5
TMP_MAX_BYTES = 5 * 1024 ** 3
HOOK_RANGE = (0, 2500)
THUMB_RANGE = (500, 1500)
PRESET_COUNT = 5


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _profile_value(*keys):
    node = _json(PROFILE)
    for key in keys:
        node = node[key]
    return node['value']


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _in_git_tree(path):
    resolved = path.resolve()
    return any((p / '.git').exists() for p in (resolved, *resolved.parents))


def _find_dir(root, names):
    for directory in [root, *sorted(p for p in root.iterdir() if p.is_dir())]:
        if all((directory / name).is_file() for name in names):
            return directory
    pytest.fail(f'no directory under {root} holds {names}')


POLICY = TokenizationPolicy(revision='cp7-8-real-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
DECISION = ProviderRouteDecision(provider_ref='kokoro-local', model_ref='kokoro-v1.0', account_ref='local', route_revision='cp7-8', rationale_codes=('LOCAL',), fallback_order=(), capacity_reservation_ref='cp7-8-res', credential_acquisition_method='none', estimated_cost_class='free')


def _locked_av():
    for requirement in tomllib.loads(PYPROJECT.read_text(encoding='utf-8'))['tool']['uv']['constraint-dependencies']:
        found = re.fullmatch(r'av==([0-9][0-9.]*)', requirement)
        if found:
            return found.group(1)
    pytest.fail('pyproject.toml has no av== constraint')


@pytest.fixture(scope='module')
def weights():
    lock = _json(LOCK)
    entries = lock['files']
    assert lock['storage']['in_git'] is False and len(entries) >= 6
    for entry in entries:
        name = entry['name']
        assert entry['status'] == 'PINNED', f'{name} not PINNED'
        assert re.fullmatch(r'[0-9a-f]{64}', str(entry['sha256'])), f'{name} sha256 invalid'
        assert '<commit>' not in entry['url'], f'{name} url has no pinned commit'
    root = _data_root() / lock['storage']['subdir']
    assert root.is_dir(), 'models directory missing'
    resolved = root.resolve()
    assert not _in_git_tree(resolved) and resolved != REPO and REPO not in resolved.parents, 'weights inside Git tree'
    groups = {}
    for entry in entries:
        groups.setdefault(entry['group'], []).append(entry['name'])
    directories = {group: _find_dir(root, names) for group, names in groups.items()}
    details = []
    for entry in entries:
        name = entry['name']
        actual = _sha256(directories[entry['group']] / name)
        assert actual == entry['sha256'], f'sha256 mismatch for {name}'
        details.append(f'{name} sha256={actual} group={entry["group"]}')
    return SimpleNamespace(kokoro_dir=directories['kokoro-onnx'], whisper_dir=directories['faster-whisper-small.en'], details=details)


SCRIPTS = {
    'A': 'Cities around the world are discovering the value of small neighborhood gardens. Residents transform empty lots into green spaces where families grow fresh vegetables and herbs. Local schools join these projects and teach children how plants grow from tiny seeds. Volunteers collect rainwater in large barrels and use it during the dry summer months. Bees and butterflies visit the flowers and help every crop produce a larger harvest. Neighbors share tools and recipes and swap stories about their favorite meals. Experts say that shared gardens reduce street heat and improve the quality of local air. City officials now offer free soil and training to every group that wants to start one. Small green spaces make crowded streets calmer and bring people closer together. Community organizers arrange weekly workshops where experienced gardeners explain seasonal composting techniques. Children paint colorful wooden signs to label each raised planting bed with care. Friendly weekend markets showcase handmade preserves and crisp freshly harvested lettuce for everyone. Start growing today.',
    'B': 'Along the northern coast engineers have finished a new offshore wind farm. Forty large turbines now rise above the water and turn steadily in the strong sea breeze. Cables laid along the seabed carry clean electricity to the nearest power station. The project supplies enough energy for nearly two hundred thousand homes every year. Fishing crews worked with the builders to keep shipping lanes open and safe. Marine scientists monitor the area and report that fish and seabirds have adapted well. Local workshops now train young technicians to maintain the machines and inspect the blades. Energy prices in the region have become more stable since the turbines started working. Environmental agencies praise the reduced dependence on fossil fuel generation facilities. Coastal communities welcome the steady technical employment created across nearby service harbors. Automated maintenance vessels conduct regular underwater foundation inspections using smart acoustic sensors. Planners already study a second site farther out at sea. The wind keeps blowing and the power keeps flowing.',
}

assert set(SCRIPTS) == {'A', 'B'}
for _key, _text in SCRIPTS.items():
    assert 120 <= len(_text.split()) <= 180
    assert re.fullmatch(r'[A-Za-z .]+', _text)


def _ffmpeg(*args):
    proc = mp.run_ffmpeg(['-y', *args], timeout=DEADLINE.timeout(300))
    assert proc.returncode == 0, 'ffmpeg helper failed'


SEED_SPECS = {
    'A': (
        'testsrc2=s=1080x1920',
        'rgbtestsrc=s=1080x1920',
        'smptehdbars=s=1080x1920',
        'yuvtestsrc=s=1080x1920',
        'gradients=s=1080x1920:seed=7',
    ),
    'B': (
        'gradients=s=1080x1920:seed=9',
        'yuvtestsrc=s=1080x1920',
        'smptehdbars=s=1080x1920',
        'rgbtestsrc=s=1080x1920',
        'testsrc2=s=1080x1920',
    ),
}
HOOK_SPECS = {
    'A': 'gradients=s=1080x1920:seed=21',
    'B': 'gradients=s=1080x1920:seed=33',
}


def make_png(path, lavfi_spec):
    # băng đen phủ vùng phụ đề (0,70 đến 0,86 chiều cao) để mọi ảnh có cùng nền ở vùng đo phụ đề, nhờ đó chênh lệch đo được là do chữ
    _ffmpeg('-f', 'lavfi', '-i', lavfi_spec, '-vf', 'drawbox=x=0:y=1340:w=1080:h=320:color=black:t=fill', '-frames:v', '1', str(path))


def make_hook_wav(path):
    _ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=660:sample_rate=48000:duration=2.5', '-ac', '1', str(path))


def synth_voice(tts, aligner, resolve, key, text, work):
    ref = f'cp7-8-voice-{key}'
    fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()
    request = {
        'script_version_id': ref,
        'script_fingerprint': fingerprint,
        'voice_profile_ref': 'cp7-8-' + ref,
        'provider_route_ref': 'cp7-8-route',
        'expected_language': 'en-US',
        'operation_key': 'cp7-8-' + ref,
        'execution_grant_ref': 'cp7-8-grant',
    }
    data = tts.synthesize(DECISION, ScriptText(ref, text, fingerprint), request).audio_bytes
    wav_path = work / f'voice-{key}.wav'
    wav_path.write_bytes(data)
    with wave.open(str(wav_path), 'rb') as wav:
        rate = wav.getframerate()
        frames = wav.getnframes()
    duration_ms = frames * 1000 // rate
    resolve[ref] = wav_path
    result = aligner.align(AlignmentRequest(
        voice_artifact_ref=ref,
        voice_hash=hashlib.sha256(data).hexdigest(),
        voice_duration_ms=duration_ms,
        script_version_id=ref,
        script_text=text,
        expected_language='en-US',
    ))
    words = []
    raw_starts = []
    prev_end = 0
    for w in result.words:
        w_text = w.get('text', '') if isinstance(w, dict) else getattr(w, 'text', '')
        if not w_text:
            continue
        start_val = int(w['start_ms'] if isinstance(w, dict) else w.start_ms)
        end_val = int(w['end_ms'] if isinstance(w, dict) else w.end_ms)
        start = max(start_val, prev_end)
        end = max(end_val, start + 10)
        prev_end = end
        words.append(TimedWord(text=w_text, start_ms=start, end_ms=end))
        raw_starts.append(start)
    assert 62000 <= duration_ms <= 69000, f'BLOCKED kich ban: thoi luong ngoai 62-69 s, sua do dai kich ban (duration_ms={duration_ms})'
    assert len(words) >= 0.9 * len(text.split()), f'too few aligned words: {len(words)} / {len(text.split())}'
    return SimpleNamespace(
        key=key,
        ref=ref,
        wav=wav_path,
        data=data,
        duration_ms=duration_ms,
        words=words,
        raw_starts=raw_starts,
        sha256=hashlib.sha256(data).hexdigest(),
    )

SUPPLEMENTS = {
    'ass_style': {
        'secondary_colour': '&H00FFFFFF',
        'back_colour': '&H80000000',
        'italic': 0,
        'underline': 0,
        'strike_out': 0,
        'scale_x': 100,
        'scale_y': 100,
        'spacing': 0,
        'angle': 0,
        'border_style': 1,
        'shadow': 0,
        'alignment': 2,
        'encoding': 1,
    },
    'layout': {
        'margin_left': 60,
        'margin_right': 60,
        'max_words_per_line': 4,
        'max_chars_per_line': 28,
        'disclosure_font_size': 40,
        'disclosure_alignment': 8,
        'disclosure_margin_v': 240,
    },
    'sections': {
        'visual_rhythm': {'note': 'cp7-8'},
        'thumbnail_overlay_style': {'note': 'cp7-8'},
        'hook_treatment': {'note': 'cp7-8'},
        'color_effect_rules': {'note': 'cp7-8'},
    },
    'quality_thresholds': {
        'SUBTITLE_BURNED_IN': {'min_frames_with_text': 2},
        'VOICE_AUDIBLE': {'min_voice_level': -40.0},
    },
    'output_profile': {
        'video_codec': 'h264',
        'pixel_format': 'yuv420p',
    },
}


def load_presets():
    params = dict(load_production_profile(PROFILE).parameters)
    items = render_config_payloads(params, SUPPLEMENTS)
    output = [payload for kind, key, payload in items if key == 'output-profile'][0]
    presets = {key: build_preset_revision({**payload, 'revision': 1}) for kind, key, payload in items if kind == 'preset' and key != 'output-profile'}
    thresholds = [payload['thresholds'] for kind, key, payload in items if kind == 'policy'][0]
    assert len(presets) == PRESET_COUNT
    return (output, presets, thresholds)


TOOL = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=str(FFMPEG_EXE).replace(chr(92), '/'))


def output_profile(output, encoder):
    return OutputProfile(
        width=output['width'],
        height=output['height'],
        fps=output['fps'],
        video_codec=output['video_codec'],
        audio_codec=output['audio_codec'],
        container=output['container'],
        pixel_format=output['pixel_format'],
        encoder=encoder,
        bitrate=None,
    )


def make_spec(ctx, package, preset, ass_ref, encoder, output_name):
    return build_render_command(
        package,
        preset,
        output_profile(ctx.output, encoder),
        ass_ref,
        TOOL,
        MaterializedPaths(
            staging_root=str(ctx.staging),
            output_path=f'out/{output_name}.mp4',
            thumbnail_path=f'out/{output_name}.jpg',
        ),
    )


def build_video(ctx, video_key, preset, encoder, name):
    voice = ctx.voices[video_key]
    seed_files = ctx.seed_files[video_key]
    hook_png = ctx.hook_png[video_key]
    hook_wav = ctx.hook_wav[video_key]

    inputs = ass_inputs(preset, output_profile(ctx.output, encoder))
    segs = [ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='source_backed', disclosure=None, word_count=len(voice.words))]
    material = build_ass_material(
        staging_root=str(ctx.staging),
        words=voice.words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=segs,
    )

    visual_hook_ref = f'ref-hook-visual-{video_key}'
    audio_hook_ref = f'ref-hook-audio-{video_key}'
    voice_ref = f'ref-voice-{video_key}'
    seed_refs = [f'ref-seed-{video_key}-{i}' for i in range(len(seed_files))]

    manifest = {
        voice_ref: {'local_ref': f'media/voice-{video_key}.wav'},
        visual_hook_ref: {'local_ref': f'media/hook-{video_key}.png'},
        audio_hook_ref: {'local_ref': f'media/hook-{video_key}.wav'},
        material.ass_ref: {'local_ref': material.entry.local_ref},
    }
    for i, ref in enumerate(seed_refs):
        manifest[ref] = {'local_ref': f'media/seed-{video_key}-{i}.png'}

    input_artifacts = []
    for ref, p in zip(seed_refs, seed_files):
        input_artifacts.append({
            'artifact_version_id': ref,
            'sha256': renderer_sha256(p),
            'size_bytes': p.stat().st_size,
            'media_type': 'image/png',
        })
    input_artifacts.append({
        'artifact_version_id': visual_hook_ref,
        'sha256': renderer_sha256(hook_png),
        'size_bytes': hook_png.stat().st_size,
        'media_type': 'image/png',
    })
    input_artifacts.append({
        'artifact_version_id': voice_ref,
        'sha256': renderer_sha256(voice.wav),
        'size_bytes': voice.wav.stat().st_size,
        'media_type': 'audio/wav',
    })
    input_artifacts.append({
        'artifact_version_id': audio_hook_ref,
        'sha256': renderer_sha256(hook_wav),
        'size_bytes': hook_wav.stat().st_size,
        'media_type': 'audio/wav',
    })

    seg_count = len(seed_files)
    segments = []
    for i in range(seg_count):
        s_start = voice.duration_ms * i // seg_count
        s_end = voice.duration_ms * (i + 1) // seg_count
        segments.append({
            'start_ms': s_start,
            'end_ms': s_end,
            'visual_asset_refs': [seed_refs[i]],
        })
    timeline = {
        'duration_ms': voice.duration_ms,
        'segments': segments,
    }
    hook_placement = {
        'visual_hook_ref': visual_hook_ref,
        'audio_hook_ref': audio_hook_ref,
        'thumbnail_ref': visual_hook_ref,
        'hook_time_range': {'start_ms': 0, 'end_ms': 2500},
        'thumbnail_time_range': {'start_ms': 500, 'end_ms': 1500},
    }

    payload = {
        'render_package_id': f'pkg-{name}',
        'package_fingerprint': '',
        'production_snapshot_ref': f'cp7-8-snap-{name}',
        'script_version_ref': f'cp7-8-script-{name}',
        'production_plan_ref': f'cp7-8-plan-{name}',
        'preset_revision_ref': f'cp7-8-preset-{name}',
        'voice_artifact_ref': voice_ref,
        'word_timing_ref': f'cp7-8-timing-{name}',
        'output_metadata_revision': f'cp7-8-meta-{name}',
        'output_profile_revision': f'cp7-8-prof-{name}',
        'language_validation_refs': [f'cp7-8-lang-{name}'],
        'input_artifacts': input_artifacts,
        'timeline': timeline,
        'hook_placement': hook_placement,
        'subtitle_config': {'karaoke': True},
        'mix_plan': {},
        'allowed_fallbacks': [],
        'materialization_manifest': manifest,
        'output_path_ref': f'ref-output-{name}',
    }
    payload_copy = {k: v for k, v in payload.items() if k != 'package_fingerprint'}
    payload['package_fingerprint'] = hashlib.sha256(json.dumps(payload_copy, sort_keys=True).encode('utf-8')).hexdigest()

    package = validate_render_package_payload(payload)
    spec = make_spec(ctx, package, preset, material.ass_ref, encoder, name)
    return SimpleNamespace(
        name=name,
        key=video_key,
        preset=preset,
        preset_key=preset.preset_key,
        encoder=encoder,
        package=package,
        spec=spec,
        ass_ref=material.ass_ref,
        ass_text=material.text,
        output_ref=f'out/{name}.mp4',
        output_path=ctx.staging / 'out' / f'{name}.mp4',
        words=voice.words,
        raw_starts=voice.raw_starts,
    )


SETTINGS = InspectorSettings(
    compare_width=90,
    compare_height=160,
    thumbnail_min_ssim=0.8,
    subtitle_band=Band(top=0.72, bottom=0.84),
    disclosure_band=Band(top=0.10, bottom=0.25),
    overlay_max_missing_share=0.25,
    max_subtitle_samples=20,
    timeout_seconds=120,
)


def qc_verdict(path):
    code, data = mp.ffprobe_json(path)
    facts = mp.media_facts(data)
    decode = mp.decode_check(path)
    reasons = []
    if code != 0 or data is None:
        reasons.append('ffprobe_rejected')
    if not decode.get('playable'):
        reasons.append('decode_errors')
    if (facts.get('width'), facts.get('height')) != (1080, 1920):
        reasons.append('size')
    fps = facts.get('fps')
    if fps is None or abs(fps - 30.0) > 0.01:
        reasons.append('fps')
    if facts.get('video_codec') != 'h264':
        reasons.append('video_codec')
    if facts.get('audio_codec') != 'aac':
        reasons.append('audio_codec')
    fmt = facts.get('format_names') or []
    if 'mp4' not in fmt:
        reasons.append('container')
    dur = facts.get('duration_s')
    if dur is None or dur < DUR_MIN_S or dur > DUR_MAX_S:
        reasons.append('duration')
    sz = facts.get('size_bytes')
    if sz is None or sz > MAX_BYTES:
        reasons.append('bytes')
    return SimpleNamespace(ok=not reasons, reasons=reasons, facts=facts, decode=decode)


@pytest.fixture(scope='module')
def suite(weights, tmp_path_factory):
    if not (FFMPEG_EXE.is_file() and FFPROBE_EXE.is_file()):
        pytest.fail('BLOCKED: ffmpeg or ffprobe missing')
    try:
        mp.verify_pin()
    except Exception as exc:
        pytest.fail(f'BLOCKED: ffmpeg pin verify failed: {exc}')
    rc, _, _ = mp.run_bounded(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], timeout=10)
    if rc != 0:
        pytest.fail(f'BLOCKED: nvidia-smi failed with rc {rc}')
    locked_av, installed_av = _locked_av(), importlib.metadata.version('av')
    if installed_av != locked_av:
        pytest.fail(f'BLOCKED: installed av=={installed_av} differs from locked av=={locked_av}')

    work = tmp_path_factory.mktemp('cp7_render')
    if shutil.disk_usage(work).free < 10 * 1024 ** 3:
        pytest.fail('BLOCKED: free disk space less than 10 GiB')

    staging = work / 'staging'
    (staging / 'media').mkdir(parents=True, exist_ok=True)
    (staging / 'out').mkdir(parents=True, exist_ok=True)
    assert re.fullmatch(r'[A-Za-z0-9_./:\\-]+', str(staging)), f'BLOCKED: staging path unsafe for ASS filter: {staging}'

    voice_conf = _profile_value('voice', 'engine')
    engine_conf = _profile_value('aligner', 'engine')
    tts_staging = work / 'tts_staging'
    tts_staging.mkdir(parents=True, exist_ok=True)
    rate_hz = voice_conf['output']['sample_rate_hz']
    tts = RealKokoroTts(KokoroConfig(
        weights_dir=weights.kokoro_dir,
        lock_path=LOCK,
        staging_dir=tts_staging,
        voice=voice_conf['voice'],
        speed=voice_conf['speed'],
        language=voice_conf['lang'],
        sample_rate=rate_hz,
    ))
    resolve = {}
    aligner = RealWhisperAligner(WhisperAlignerConfig(
        model_dir=weights.whisper_dir,
        lock_path=LOCK,
        resolve_audio=lambda ref: resolve[ref],
        tokenization_policy=POLICY,
        max_unmatched_word_ratio=1.0,
        language=engine_conf['language'],
        device=engine_conf['device'],
        compute_type=engine_conf['compute_type'],
    ))

    voices = {k: synth_voice(tts, aligner, resolve, k, SCRIPTS[k], staging / 'media') for k in ('A', 'B')}

    seed_files = {}
    hook_png = {}
    hook_wav = {}
    for k in ('A', 'B'):
        seed_list = []
        for i, spec in enumerate(SEED_SPECS[k]):
            p = staging / 'media' / f'seed-{k}-{i}.png'
            make_png(p, spec)
            seed_list.append(p)
        seed_files[k] = seed_list

        h_png = staging / 'media' / f'hook-{k}.png'
        make_png(h_png, HOOK_SPECS[k])
        hook_png[k] = h_png

        h_wav = staging / 'media' / f'hook-{k}.wav'
        make_hook_wav(h_wav)
        hook_wav[k] = h_wav

    output, presets, thresholds = load_presets()
    assert thresholds['VISUAL_HOOK_PRESENT']['min_similarity'] == HOOK_SIM_MIN
    assert thresholds['AUDIO_HOOK_PRESENT']['min_level_db'] == HOOK_AUDIO_MIN_DB
    assert thresholds['VISUAL_CONTINUITY']['min_continuity'] == CONTINUITY_MIN

    ctx = SimpleNamespace(
        staging=staging,
        output=output,
        voices=voices,
        seed_files=seed_files,
        hook_png=hook_png,
        hook_wav=hook_wav,
        work=work,
    )

    planned = []
    for pkey in sorted(presets.keys()):
        pr = presets[pkey]
        for vkey in ('A', 'B'):
            name = f'{pkey}-{vkey}-nvenc'
            planned.append(build_video(ctx, vkey, pr, 'h264_nvenc', name))
    first_pkey = sorted(presets.keys())[0]
    first_pr = presets[first_pkey]
    planned.append(build_video(ctx, 'A', first_pr, 'libx264', f'{first_pkey}-A-libx264'))

    lease = LocalGpuLease(2, RENDER_TIMEOUT_S + 600)
    renderer = RealFfmpegRenderer(lease=lease, ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=RENDER_TIMEOUT_S)

    runs = []
    for vid in planned:
        DEADLINE.check()
        held = lease.acquire(vid.name)
        try:
            outcome = renderer.run(vid.spec, lease=held)
        finally:
            lease.release(held)
        assert outcome.status is RendererStatus.SUCCEEDED, f'render failed for {vid.name}: {outcome.error}'
        assert renderer.last_encoder == vid.encoder

        path = vid.output_path
        qc = qc_verdict(path)
        inspector = RealOutputInspector(
            inputs=InspectionInputs(staging_root=staging, ass_ref=vid.ass_ref, segments=()),
            settings=SETTINGS,
            ffmpeg_path=FFMPEG_EXE,
            lock_path=RUNTIME_LOCK,
        )
        evidence = inspector.inspect(str(path), vid.package)
        continuity = mp.visual_continuity(path)
        loud = mp.loudnorm(path)
        dialogues = parse_ass_dialogues(vid.ass_text)
        obs = karaoke_observations(dialogues)
        dialogue_mids = [(d.start_ms + d.end_ms) // 2 for d in dialogues if dialogues and d.style == dialogues[0].style]
        samples = len(evenly_sampled(dialogue_mids, 20))
        sha = renderer_sha256(path)

        style_lines = [line for line in vid.ass_text.splitlines() if line.startswith('Style:')]
        primary_colour = style_lines[0].split('Style:')[1].split(',')[3].strip() if style_lines else ''

        runs.append(SimpleNamespace(
            video=vid,
            outcome=outcome,
            wall_ms=outcome.metrics.wall_time_ms,
            qc=qc,
            evidence=evidence,
            continuity=continuity,
            loud=loud,
            obs=obs,
            samples=samples,
            sha256=sha,
            primary_colour=primary_colour,
        ))

    return SimpleNamespace(ctx=ctx, runs=runs, renderer=renderer, lease=lease, thresholds=thresholds)

def test_rg07_ffmpeg_pin_used(suite, tmp_path, emit):
    actual_pin = mp.verify_pin()
    assert actual_pin == mp.FFMPEG_PIN_SHA256
    lock_data = _json(RUNTIME_LOCK)
    assert actual_pin == lock_data['pins']['ffmpeg']['sha256']
    verify_ffmpeg_pin(FFMPEG_EXE, RUNTIME_LOCK)

    for run in suite.runs:
        norm_spec = os.path.normcase(os.path.normpath(run.video.spec.argv[0]))
        norm_exe = os.path.normcase(os.path.normpath(str(FFMPEG_EXE)))
        assert norm_spec == norm_exe

    fake = tmp_path / 'fake_ffmpeg.exe'
    fake.write_bytes(b'not_real_ffmpeg')
    with pytest.raises(mp.PinMismatch):
        mp.verify_pin(fake)
    with pytest.raises(FfmpegPinRejected):
        verify_ffmpeg_pin(fake, RUNTIME_LOCK)

    probe_src = REPO / 'tools' / 'real' / 'cp7_media_probe.py'
    tree = ast.parse(probe_src.read_text(encoding='utf-8'))
    imports = [node.names[0].name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)] + [
        node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module != '__future__'
    ]
    non_std = [i for i in imports if i not in sys.stdlib_module_names]
    assert not non_std, f'probe imports non-stdlib modules: {non_std}'

    emit(c.report_line('RG-07', 'ffmpeg_pin_used', 'PASS'))
    emit(f'- ffmpeg_pin_used: sha256={actual_pin} verified=true stdlib_only=true')


def test_rg07_nvenc_presets(suite, emit):
    nvenc_runs = [r for r in suite.runs if r.video.encoder == 'h264_nvenc']
    assert len(nvenc_runs) == 10
    by_preset = {}
    for r in nvenc_runs:
        by_preset.setdefault(r.video.preset_key, []).append(r.video.key)
        assert dict(r.outcome.metrics.gpu_metrics) == {'encoder_h264_nvenc': 1}
        final_argv = build_final_argv(r.video.spec.argv, str(FFMPEG_EXE), 'h264_nvenc', 'x.part')
        argv_str = list(final_argv)
        idx = argv_str.index('-preset')
        assert argv_str[idx + 1] == 'p5'
    assert len(by_preset) == 5
    for pkey, vkeys in by_preset.items():
        assert sorted(vkeys) == ['A', 'B']

    colours = {r.primary_colour for r in nvenc_runs}
    assert len(colours) == 5

    emit(c.report_line('RG-07', 'nvenc_presets', 'PASS'))
    emit(f'- nvenc_presets: runs=10 presets=5 (2 videos each) distinct_colours={len(colours)} nvenc_preset=p5')


def test_rg07_libx264_fallback(suite, emit):
    cpu_runs = [r for r in suite.runs if r.video.encoder == 'libx264']
    assert len(cpu_runs) == 1
    run = cpu_runs[0]
    assert dict(run.outcome.metrics.cpu_metrics) == {'encoder_libx264': 1}
    assert run.qc.ok

    emit(c.report_line('RG-07', 'libx264_fallback', 'PASS'))
    emit(f'- libx264_fallback: runs=1 name={run.video.name} wall_ms={run.wall_ms} qc_ok={run.qc.ok}')


def test_rg07_container_spec(suite, emit):
    assert len(suite.runs) == 11
    for r in suite.runs:
        assert r.qc.ok, f'qc failed for {r.video.name}: {r.qc.reasons}'
        f = r.qc.facts
        assert f['width'] == 1080
        assert f['height'] == 1920
        assert abs(f['fps'] - 30.0) <= 0.01
        assert f['video_codec'] == 'h264'
        assert f['audio_codec'] == 'aac'
        assert f['audio_rate'] == 48000
        assert 'mp4' in f['format_names']

    emit(c.report_line('RG-07', 'container_spec', 'PASS'))
    emit(f'- container_spec: count=11 width=1080 height=1920 fps=30.0 video=h264 audio=aac@48000 format=mp4')


def test_rg07_duration_61_70(suite, emit):
    durs = [r.qc.facts['duration_s'] for r in suite.runs]
    for d in durs:
        assert DUR_MIN_S <= d <= DUR_MAX_S

    emit(c.report_line('RG-07', 'duration_61_70', 'PASS'))
    emit(f'- duration_61_70: min_s={min(durs):.3f} max_s={max(durs):.3f} count={len(durs)} in_range=[61, 70]')


def test_rg07_size_cap(suite, emit):
    sizes = [r.qc.facts['size_bytes'] for r in suite.runs]
    for sz in sizes:
        assert sz <= MAX_BYTES

    total_staging = sum(p.stat().st_size for p in suite.ctx.staging.rglob('*') if p.is_file())
    assert total_staging < TMP_MAX_BYTES

    emit(c.report_line('RG-07', 'size_cap', 'PASS'))
    emit(f'- size_cap: max_bytes={max(sizes)} cap={MAX_BYTES} staging_bytes={total_staging} staging_cap={TMP_MAX_BYTES}')


def test_rg07_playable(suite, emit):
    for r in suite.runs:
        assert r.qc.decode['playable'] is True
        assert r.qc.decode['returncode'] == 0
        assert r.sha256 == r.outcome.sha256

    emit(c.report_line('RG-07', 'playable', 'PASS'))
    emit(f'- playable: count={len(suite.runs)} decode_check_playable=true sha256_matched=true')


def test_rg07_subtitle_visible(suite, emit):
    min_share = 1.0
    details = []
    for r in suite.runs:
        assert r.samples >= 10
        share = r.evidence.subtitle.frames_with_text / r.samples
        assert share >= SUBTITLE_MIN_SHARE
        if share < min_share:
            min_share = share
        details.append(f'{r.video.name}: {r.evidence.subtitle.frames_with_text}/{r.samples}')

    emit(c.report_line('RG-07', 'subtitle_visible', 'PASS'))
    emit(f'- subtitle_visible: min_share={min_share:.3f} threshold={SUBTITLE_MIN_SHARE} details={json.dumps(details)}')


def test_rg07_karaoke_timing(suite, emit):
    min_share = 1.0
    max_delta = 0
    profile_tol = _profile_value('qc', 'karaoke_tolerance_ms')
    for r in suite.runs:
        assert len(r.obs) == len(r.video.words)
        ok_count = 0
        for i in range(len(r.obs)):
            delta = abs(r.obs[i].highlight_ms - r.video.raw_starts[i])
            if delta > max_delta:
                max_delta = delta
            if delta <= KARAOKE_TOL_MS:
                ok_count += 1
        share = ok_count / len(r.obs)
        assert share >= KARAOKE_MIN_SHARE
        if share < min_share:
            min_share = share

    emit(c.report_line('RG-07', 'karaoke_timing', 'PASS'))
    emit(f'- karaoke_timing: min_share={min_share:.4f} threshold={KARAOKE_MIN_SHARE} max_delta_ms={max_delta} tolerance_ms={KARAOKE_TOL_MS} profile_tolerance_ms={profile_tol} note=ass_aligned_against_aligner_markers')


def test_rg07_hook_checks(suite, emit):
    sims = []
    levels = []
    conts = []
    for r in suite.runs:
        assert r.evidence.visual_hook is not None
        assert r.evidence.audio_hook is not None
        assert r.evidence.visual_hook.similarity >= HOOK_SIM_MIN
        assert r.evidence.audio_hook.level_db >= HOOK_AUDIO_MIN_DB
        assert r.continuity['continuity'] >= CONTINUITY_MIN
        sims.append(r.evidence.visual_hook.similarity)
        levels.append(r.evidence.audio_hook.level_db)
        conts.append(r.continuity['continuity'])

    emit(c.report_line('RG-07', 'hook_checks', 'PASS'))
    emit(f'- hook_checks: min_sim={min(sims):.4f} (>= {HOOK_SIM_MIN}) min_audio_db={min(levels):.2f} (>= {HOOK_AUDIO_MIN_DB}) min_continuity={min(conts):.4f} (>= {CONTINUITY_MIN})')


def test_rg07_loudness_recorded(suite, emit):
    rows = []
    warn_count = 0
    for r in suite.runs:
        i = r.loud['input_i']
        tp = r.loud['input_tp']
        lra = r.loud['input_lra']
        assert not math.isnan(i) and not math.isnan(tp) and not math.isnan(lra)
        warn = abs(i - LOUD_TARGET) > LOUD_TOL or tp > TP_MAX
        if warn:
            warn_count += 1
        rows.append(f'{r.video.name}: I={i:.1f}LUFS TP={tp:.1f}dBTP LRA={lra:.1f} warn={warn}')

    emit(c.report_line('RG-07', 'loudness_recorded', 'PASS'))
    emit(f'- loudness_recorded: total={len(suite.runs)} warn_count={warn_count} target={LOUD_TARGET}LUFS tol={LOUD_TOL}LU max_tp={TP_MAX}dBTP')
    for row in rows:
        emit(f'- loudness_recorded: {row}')


def test_rg07_render_p95(suite, emit):
    walls = [r.wall_ms for r in suite.runs if r.video.encoder == 'h264_nvenc']
    assert len(walls) == 10
    assert all(w > 0 for w in walls)
    p95 = mp.percentile_nearest_rank(walls, 0.95)
    assert p95 <= RENDER_TIMEOUT_S * 1000
    sorted_walls = sorted(walls)
    median = (sorted_walls[4] + sorted_walls[5]) / 2.0
    cpu_run = [r for r in suite.runs if r.video.encoder == 'libx264'][0]

    emit(c.report_line('RG-07', 'render_p95', 'PASS'))
    emit(f'- render_p95: p95_ms={p95} median_ms={median:.1f} max_ms={max(walls)} libx264_ms={cpu_run.wall_ms} cap_ms={RENDER_TIMEOUT_S * 1000} note=G02_metric_reference_7min_video_for_comparison_only')

GRANT = ExecutionGrant(
    workspace_id='ws-cp7-8',
    operation_id='op-grant-cp7-8',
    job_id='job-cp7-8',
    stage_run_id='stage-cp7-8',
    execution_generation=1,
    recovery_epoch=1,
)
CONTEXT = CommandContext(
    workspace_id='ws-cp7-8',
    correlation_id='corr-cp7-8',
    actor='cp7-8',
    occurred_at='2026-10-30T00:00:00+00:00',
)


class AlwaysCurrent:
    def is_grant_current(self, grant):
        return True


class StagedPaths:
    def __init__(self, staging):
        self.staging = Path(staging)

    def _abs(self, ref):
        return ref if Path(ref).is_absolute() else str(self.staging / ref)


class StagedProbe(StagedPaths):
    def probe(self, ref):
        return RealFfprobeProbe(
            ffprobe_path=str(FFPROBE_EXE),
            ffmpeg_path=FFMPEG_EXE,
            lock_path=RUNTIME_LOCK,
        ).probe(self._abs(ref))


class StagedObserver(StagedPaths):
    def observe(self, ref):
        return RealFfmpegRenderer(
            ffmpeg_path=str(FFMPEG_EXE),
            lock_path=RUNTIME_LOCK,
        ).observe(self._abs(ref))


class LateTimeoutRenderer:
    takes_held_lease = True

    def __init__(self, inner):
        self.inner = inner

    def run(self, spec, *, lease):
        outcome = self.inner.run(spec, lease=lease)
        assert outcome.status is RendererStatus.SUCCEEDED
        raise RendererTimeout('answer lost after the side effect')


class CorruptingRenderer:
    takes_held_lease = True

    def __init__(self, inner):
        self.inner = inner

    def run(self, spec, *, lease):
        outcome = self.inner.run(spec, lease=lease)
        assert outcome.status is RendererStatus.SUCCEEDED
        p = Path(outcome.output_ref)
        with p.open('r+b') as handle:
            handle.write(b'\x00' * 4096)
        return dataclasses.replace(outcome, sha256=renderer_sha256(p))


KILL_WRAPPER = """import os, pathlib, subprocess, sys, time

args = sys.argv[1:]
out = pathlib.Path(args[-1])
target_bytes = int(os.environ.get('CP7_KILL_AT_BYTES', '262144'))
marker_path = os.environ.get('CP7_KILL_MARKER')

proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.monotonic() + 300.0
killed = False

while time.monotonic() < deadline:
    if proc.poll() is not None:
        break
    try:
        if out.exists() and out.stat().st_size >= target_bytes:
            proc.kill()
            proc.wait()
            killed = True
            if marker_path:
                pathlib.Path(marker_path).write_text(str(out.stat().st_size), encoding='utf-8')
            sys.exit(1)
    except Exception:
        pass
    time.sleep(0.05)

if not killed and proc.poll() is None:
    proc.kill()
    proc.wait()
    sys.exit(1)

sys.exit(proc.returncode if proc.returncode is not None else 0)
"""


def make_rig(suite, video, renderer):
    uow = InMemoryRenderUnitOfWork()
    with uow as u:
        u.renders.append(KIND_PACKAGE, video.package.render_package_id, 1, video.package)
        fp = video.package.package_fingerprint
        u.reports.append(PackageValidationReport(package_fingerprint=fp, findings=(), passed=True, report_id=_compute_report_id(fp, ())))
        u.commit()
    lease = LocalGpuLease(2, RENDER_TIMEOUT_S + 600)
    pipeline = RenderPipeline(
        uow=uow,
        renderer=renderer,
        lease=lease,
        probe=StagedProbe(suite.ctx.staging),
        observer=StagedObserver(suite.ctx.staging),
        grants=AlwaysCurrent(),
    )
    return SimpleNamespace(uow=uow, pipeline=pipeline, lease=lease, video=video)


def render_command(video, spec, attempt_id, output_name=None):
    output_ref = f'out/{output_name}.mp4' if output_name else video.output_ref
    return RenderVideoCommand(
        grant=GRANT,
        render_package_id=video.package.render_package_id,
        render_attempt_id=attempt_id,
        output_artifact_ref=output_ref,
        receipt_ref='rcpt-' + attempt_id,
        command_spec=spec,
        context=CONTEXT,
    )


@pytest.fixture(scope='module')
def killed(suite, tmp_path_factory):
    home = tmp_path_factory.mktemp('cp7_kill')
    wrapper_path = home / 'kill_wrapper.py'
    wrapper_path.write_text(KILL_WRAPPER, encoding='utf-8')
    marker_path = home / 'marker.txt'

    old_bytes = os.environ.get('CP7_KILL_AT_BYTES')
    old_marker = os.environ.get('CP7_KILL_MARKER')
    os.environ['CP7_KILL_AT_BYTES'] = '262144'
    os.environ['CP7_KILL_MARKER'] = str(marker_path)

    try:
        video = build_video(suite.ctx, 'A', suite.runs[0].video.preset, 'h264_nvenc', 'kill-a')
        renderer = RealFfmpegRenderer(
            ffmpeg_path=str(FFMPEG_EXE),
            lock_path=RUNTIME_LOCK,
            timeout_seconds=RENDER_TIMEOUT_S,
            command_prefix=(sys.executable, str(wrapper_path)),
        )
        rig = make_rig(suite, video, renderer)
        result = rig.pipeline.render_video(render_command(video, video.spec, 'attempt-kill-1', 'kill-a'))

        retry_spec = make_spec(suite.ctx, video.package, video.preset, video.ass_ref, 'h264_nvenc', 'kill-a-retry')
        pipeline2 = RenderPipeline(
            uow=rig.uow,
            renderer=RealFfmpegRenderer(ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=RENDER_TIMEOUT_S),
            lease=rig.lease,
            probe=StagedProbe(suite.ctx.staging),
            observer=StagedObserver(suite.ctx.staging),
            grants=AlwaysCurrent(),
        )
        retry = pipeline2.render_video(render_command(video, retry_spec, 'attempt-kill-2', 'kill-a-retry'))

        marker_val = int(marker_path.read_text(encoding='utf-8')) if marker_path.is_file() else -1
        return SimpleNamespace(
            result=result,
            retry=retry,
            rig=rig,
            marker=marker_val,
            out_dir=suite.ctx.staging / 'out',
            video=video,
            retry_path=suite.ctx.staging / 'out' / 'kill-a-retry.mp4',
        )
    finally:
        if old_bytes is None:
            os.environ.pop('CP7_KILL_AT_BYTES', None)
        else:
            os.environ['CP7_KILL_AT_BYTES'] = old_bytes
        if old_marker is None:
            os.environ.pop('CP7_KILL_MARKER', None)
        else:
            os.environ['CP7_KILL_MARKER'] = old_marker


def test_rg07_crash_recovery(killed, emit):
    assert killed.result.attempt.receipt_state is OperationState.FAILED
    assert killed.result.problem.code == 'render_attempt_failed'

    h1 = killed.rig.lease.acquire('check-1')
    h2 = killed.rig.lease.acquire('check-2')
    killed.rig.lease.release(h1)
    killed.rig.lease.release(h2)

    assert killed.retry.attempt.receipt_state is OperationState.SUCCEEDED
    assert qc_verdict(killed.retry_path).ok

    emit(c.report_line('RG-07', 'crash_recovery', 'PASS'))
    emit(f'- crash_recovery: attempt_state={killed.result.attempt.receipt_state.value} problem={killed.result.problem.code} retry_state={killed.retry.attempt.receipt_state.value} retry_qc_ok=true lease_released=true')


def test_rg07_partial_output(killed, emit):
    assert killed.marker >= 262144
    part_files = list(killed.out_dir.glob('*.part'))
    assert not part_files, f'residual part files found: {part_files}'
    assert not (killed.out_dir / 'kill-a.mp4').exists(), 'partial output kill-a.mp4 was not cleaned up'

    remaining = [p.name for p in killed.out_dir.iterdir() if p.is_file()]
    emit(c.report_line('RG-07', 'partial_output', 'PASS'))
    emit(f'- partial_output: marker_bytes={killed.marker} no_part_files=true kill_a_absent=true remaining_count={len(remaining)}')


def test_rg07_timeout_outcome_unknown(suite, emit):
    video_a = build_video(suite.ctx, 'B', suite.runs[0].video.preset, 'h264_nvenc', 'late-b')
    renderer_a = LateTimeoutRenderer(RealFfmpegRenderer(ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=RENDER_TIMEOUT_S))
    rig_a = make_rig(suite, video_a, renderer_a)
    result_a = rig_a.pipeline.render_video(render_command(video_a, video_a.spec, 'attempt-late-1', 'late-b'))
    assert result_a.attempt.receipt_state is OperationState.OUTCOME_UNKNOWN
    assert result_a.problem.code == 'render_outcome_unknown'

    spec_a2 = make_spec(suite.ctx, video_a.package, video_a.preset, video_a.ass_ref, 'h264_nvenc', 'late-b-2')
    with pytest.raises(ReconcileRequired):
        rig_a.pipeline.render_video(render_command(video_a, spec_a2, 'attempt-late-2', 'late-b-2'))

    expected_sha = renderer_sha256(video_a.output_path)
    reconciled_a = rig_a.pipeline.reconcile_render(ReconcileRenderCommand(
        grant=GRANT,
        render_attempt_id='attempt-late-1',
        context=CONTEXT,
        expected_sha256=expected_sha,
    ))
    assert reconciled_a.attempt.receipt_state is OperationState.SUCCEEDED
    assert qc_verdict(video_a.output_path).ok

    video_b = build_video(suite.ctx, 'A', suite.runs[0].video.preset, 'h264_nvenc', 'tmo-a')
    renderer_b = RealFfmpegRenderer(ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=2)
    rig_b = make_rig(suite, video_b, renderer_b)
    result_b = rig_b.pipeline.render_video(render_command(video_b, video_b.spec, 'attempt-tmo-1', 'tmo-a'))
    assert result_b.attempt.receipt_state is OperationState.OUTCOME_UNKNOWN

    reconciled_b = rig_b.pipeline.reconcile_render(ReconcileRenderCommand(
        grant=GRANT,
        render_attempt_id='attempt-tmo-1',
        context=CONTEXT,
        expected_sha256=None,
    ))
    assert reconciled_b.attempt.receipt_state is OperationState.FAILED
    assert 'reconcile_output_missing' in (reconciled_b.attempt.error or '')
    out_dir = suite.ctx.staging / 'out'
    assert not list(out_dir.glob('*.part'))
    assert not (out_dir / 'tmo-a.mp4').exists()

    emit(c.report_line('RG-07', 'timeout_outcome_unknown', 'PASS'))
    emit(f'- timeout_outcome_unknown: scenario_a_reconciled_succeeded=true qc_ok=true scenario_b_reconciled_failed=true error={reconciled_b.attempt.error}')


def test_rg07_corrupt_qc_fail(suite, tmp_path, emit):
    video = build_video(suite.ctx, 'B', suite.runs[1].video.preset, 'h264_nvenc', 'corrupt-b')
    renderer = CorruptingRenderer(RealFfmpegRenderer(ffmpeg_path=str(FFMPEG_EXE), lock_path=RUNTIME_LOCK, timeout_seconds=RENDER_TIMEOUT_S))
    rig = make_rig(suite, video, renderer)
    result = rig.pipeline.render_video(render_command(video, video.spec, 'attempt-corrupt-1', 'corrupt-b'))
    assert result.attempt.receipt_state is OperationState.FAILED
    assert 'output_not_decodable' in (result.attempt.error or '')
    qc_corrupt = qc_verdict(video.output_path)
    assert qc_corrupt.ok is False
    assert any(r in qc_corrupt.reasons for r in ('ffprobe_rejected', 'decode_errors'))

    run0 = suite.runs[0]
    raw = run0.video.output_path.read_bytes()
    trunc_path = tmp_path / 'truncated.mp4'
    trunc_path.write_bytes(raw[: int(len(raw) * 0.4)])
    qc_trunc = qc_verdict(trunc_path)
    assert qc_trunc.ok is False

    assert run0.qc.ok

    emit(c.report_line('RG-07', 'corrupt_qc_fail', 'PASS'))
    emit(f'- corrupt_qc_fail: pipeline_corrupt_reasons={qc_corrupt.reasons} truncated_reasons={qc_trunc.reasons} baseline_ok=true')


class CountingRenderer:
    takes_held_lease = True

    def __init__(self):
        self.calls = 0

    def run(self, spec, *, lease):
        self.calls += 1
        return SimpleNamespace(status=RendererStatus.SUCCEEDED)


def test_rg07_disk_guard(suite, emit):
    reserve = _profile_value('working_set', 'disk_reserve_bytes')
    free = shutil.disk_usage(suite.ctx.staging).free
    mib = 1024 * 1024
    if free // mib - 1 < reserve // mib + 1:
        pytest.fail('BLOCKED: o dia con it hon disk_reserve_bytes')

    limits = AdmissionLimits(cpu_max_percent=100, ram_reserve_mb=0, disk_reserve_mb=reserve // mib)
    snapshot = ResourceSnapshot(cpu=0.0, gpu_slots_free=2, ram_free_mb=1000000, disk_free_mb=free // mib, network_ok=True)

    max_size_mib = max(r.qc.facts['size_bytes'] for r in suite.runs) // mib
    need_ok = ResourceNeed(gpu_slots=1, ram_mb=0, disk_mb=max_size_mib + 1, needs_network=False)
    decision_ok = decide_admission(limits, snapshot, need_ok)
    assert isinstance(decision_ok, Admitted)

    need_block_mib = free // mib - reserve // mib + 1
    need_block = ResourceNeed(gpu_slots=1, ram_mb=0, disk_mb=need_block_mib, needs_network=False)
    decision_block = decide_admission(limits, snapshot, need_block)
    assert decision_block == Wait(WaitReason.INSUFFICIENT_DISK)

    def guarded(decision, rend, spec):
        if isinstance(decision, Admitted):
            return rend.run(spec, lease=None)
        return None

    counter = CountingRenderer()
    guard_video = build_video(suite.ctx, 'A', suite.runs[0].video.preset, 'h264_nvenc', 'guard-a')
    guarded(decision_block, counter, guard_video.spec)
    assert counter.calls == 0
    assert not guard_video.output_path.exists()

    guarded(decision_ok, counter, guard_video.spec)
    assert counter.calls == 1

    bytes_written = sum(p.stat().st_size for p in suite.ctx.work.rglob('*') if p.is_file())
    assert bytes_written < TMP_MAX_BYTES

    emit(c.report_line('RG-07', 'disk_guard', 'PASS'))
    emit(f'- disk_guard: free_bytes={free} reserve_bytes={reserve} margin_bytes={free - reserve} need_ok_mib={max_size_mib + 1} need_block_mib={need_block_mib} bytes_written_by_test={bytes_written} note=khong lap day dia')
