"""PW-F1: RealOutputInspector measures the visual gates with the pinned FFmpeg on lavfi samples; no mock, no database.

coveredIds: PW-F1-01, CT-QC-001
"""
import dataclasses
import json
import pathlib
import re
import subprocess
import pytest

from render.adapters.frame_probe import FrameProbe, subtitles_filter_path
from render.adapters.real_ffmpeg_renderer import FfmpegPinRejected, build_final_argv, sha256_file
from render.adapters.real_output_inspector import (
    AssDialogue,
    Band,
    InspectionInputs,
    InspectorSettings,
    RealOutputInspector,
    disclosure_band_from_ass,
    karaoke_sample_ms,
    parse_ass_dialogues,
    style_band_from_ass,
)
from render.domain.content_gates import (
    check_inference_disclosure_present,
    check_karaoke_timing_valid,
    check_subtitle_burned_in,
    check_thumbnail_present,
    check_visual_hook_present,
)
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateStatus, QualityPolicy
from render.adapters.ass_manifest import build_ass_text
from render.adapters.postgres_plan_assets import ScriptSegmentInfo
from render.domain.karaoke_plan import TimedWord
from render.domain.preset import build_preset_revision
from render.domain.render_command import MaterializedPaths, OutputProfile, ToolIdentity, build_render_command

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
PINNED_SHA = 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480'
WORDS = [{'start_ms': 1000}, {'start_ms': 1500}, {'start_ms': 3000}, {'start_ms': 3500}]
SEGMENTS_INFERENCE = [{'segment_id': 'seg-1', 'claim_mode': 'source_backed'}, {'segment_id': 'seg-2', 'claim_mode': 'inference'}]
SEGMENTS_SOURCED = [{'segment_id': 'seg-1', 'claim_mode': 'source_backed'}]

SETTINGS = InspectorSettings(
    compare_width=90,
    compare_height=160,
    thumbnail_min_ssim=0.8,
    subtitle_band=Band(top=0.70, bottom=0.80),
    disclosure_band=Band(top=0.10, bottom=0.25),
    overlay_max_missing_share=0.25,
    max_subtitle_samples=4,
    timeout_seconds=60,
)

POLICY = QualityPolicy(
    revision='pw-f1-test',
    thresholds={
        'VISUAL_HOOK_PRESENT': {'min_similarity': 0.85},
        'SUBTITLE_BURNED_IN': {'min_frames_with_text': 2},
        'KARAOKE_TIMING_VALID': {'tolerance_ms': 100},
    },
)


def require_ffmpeg() -> None:
    if not FFMPEG.is_file():
        pytest.fail(
            'BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.',
            pytrace=False,
        )


def ffmpeg(*args: str) -> None:
    result = subprocess.run(
        [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


ASS_TEMPLATE = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 180
PlayResY: 320

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,40,1
Style: Disclosure,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.50,Karaoke,,0,0,0,,{\k@@FIRST@@}Hello {\k100}world
Dialogue: 0,0:00:03.00,0:00:04.00,Karaoke,,0,0,0,,{\k50}good {\k50}day
Dialogue: 0,0:00:04.50,0:00:05.50,Disclosure,seg-2,0,0,0,,AI inference
"""

BACKSLASH = chr(92)
BURN_PATH_CHARS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./:' + BACKSLASH)


def burn_filter(ass_path: pathlib.Path) -> str:
    text = str(ass_path)
    assert all(ch in BURN_PATH_CHARS for ch in text), text
    return 'subtitles=filename=' + text.replace(BACKSLASH, '/').replace(':', BACKSLASH * 2 + ':')


def shift_clock(match: re.Match, delta_ms: int) -> str:
    h, m, s, cs = (int(x) for x in match.groups())
    total = ((h * 60 + m) * 60 + s) * 100 + cs + delta_ms // 10
    seconds, centis = divmod(total, 100)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}'


def burn_ass_text(kind: str, first_k: str = '50') -> str | None:
    """ASS text drawn into the video: 'same' as the staged one, 'karaoke_only' without the Disclosure dialogue, 'other' with different words, 'shifted' two seconds later, 'none' for no text at all."""
    if kind == 'none':
        return None
    text = ASS_TEMPLATE.replace('@@FIRST@@', first_k)
    lines = text.splitlines(keepends=True)
    if kind == 'same':
        return text
    if kind == 'karaoke_only':
        return ''.join(x for x in lines if not (x.startswith('Dialogue:') and ',Disclosure,' in x))
    if kind == 'other':
        swaps = (('Hello', 'Qxz'), ('world', 'jvk'), ('good', 'wqy'), ('day', 'kzx'), ('AI inference', 'ZQJ XVK'))
        out = []
        for x in lines:
            if x.startswith('Dialogue:'):
                for old, new in swaps:
                    x = x.replace(old, new)
            out.append(x)
        return ''.join(out)
    if kind == 'shifted':
        pattern = r'(\d+):(\d{2}):(\d{2})\.(\d{2})'
        return ''.join(re.sub(pattern, lambda m: shift_clock(m, 2000), x, count=2) if x.startswith('Dialogue:') else x for x in lines)
    raise ValueError(kind)


def sample_package():
    return validate_render_package_payload({
        'render_package_id': 'pkg-f1',
        'package_fingerprint': 'a' * 64,
        'production_snapshot_ref': 'snap',
        'script_version_ref': 'script',
        'production_plan_ref': 'plan',
        'preset_revision_ref': 'preset',
        'voice_artifact_ref': 'ref-voice',
        'word_timing_ref': 'ref-timing',
        'output_metadata_revision': 'meta',
        'output_profile_revision': 'profile',
        'language_validation_refs': ['lang'],
        'input_artifacts': [],
        'timeline': {'segments': []},
        'hook_placement': {
            'visual_hook_ref': 'ref-hook',
            'audio_hook_ref': 'ref-voice',
            'thumbnail_ref': 'ref-thumb',
            'hook_time_range': {'start_ms': 0, 'end_ms': 1000},
            'thumbnail_time_range': {'start_ms': 200, 'end_ms': 800},
        },
        'subtitle_config': {'karaoke': True},
        'mix_plan': {},
        'allowed_fallbacks': [],
        'materialization_manifest': {
            'ref-hook': {'local_ref': 'media/hook.png'},
            'ref-thumb': {'local_ref': 'media/thumb.png'},
            'ref-ass': {'local_ref': 'subs/captions.ass'},
        },
        'output_path_ref': 'ref-output',
    })


def build_sample(
    root: pathlib.Path,
    *,
    background: str = 'testsrc',
    burn: str = 'same',
    thumb: str = 'ok',
    ass: str = 'full',
    first_k: str = '50',
) -> dict:
    staging_media = root / 'staging' / 'media'
    staging_subs = root / 'staging' / 'subs'
    out_dir = root / 'out'
    staging_media.mkdir(parents=True, exist_ok=True)
    staging_subs.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    hook_path = staging_media / 'hook.png'
    ffmpeg('-f', 'lavfi', '-i', 'testsrc=s=180x320:r=1:d=1', '-frames:v', '1', str(hook_path))

    bg_path = root / 'bg.png'
    if background == 'testsrc':
        bg_path.write_bytes(hook_path.read_bytes())
    elif background == 'smptebars':
        ffmpeg('-f', 'lavfi', '-i', 'smptebars=s=180x320:r=1:d=1', '-frames:v', '1', str(bg_path))

    thumb_path = staging_media / 'thumb.png'
    if thumb == 'ok':
        thumb_path.write_bytes(hook_path.read_bytes())
    elif thumb == 'corrupt':
        thumb_path.write_bytes(b'not a png')

    vf = 'format=yuv420p'
    burn_text = burn_ass_text(burn, first_k)
    if burn_text is not None:
        burn_path = root / 'burn.ass'
        burn_path.write_text(burn_text, encoding='utf-8')
        vf += ',' + burn_filter(burn_path)

    out_path = out_dir / 'final.mp4'
    ffmpeg(
        '-loop',
        '1',
        '-framerate',
        '30',
        '-i',
        str(bg_path),
        '-t',
        '6',
        '-vf',
        vf,
        '-c:v',
        'libx264',
        '-preset',
        'ultrafast',
        '-crf',
        '18',
        '-pix_fmt',
        'yuv420p',
        '-an',
        str(out_path),
    )

    if ass != 'none':
        ass_content = ASS_TEMPLATE.replace('@@FIRST@@', first_k)
        (staging_subs / 'captions.ass').write_text(ass_content, encoding='utf-8')

    package = sample_package()

    return {
        'root': root,
        'output_ref': str(out_path),
        'package': package,
    }


def inspect_sample(
    sample: dict,
    segments: list[dict],
    settings: InspectorSettings = SETTINGS,
    lock_path: pathlib.Path = LOCK_PATH,
) -> RealOutputInspector:
    inspector = RealOutputInspector(
        inputs=InspectionInputs(
            staging_root=sample['root'] / 'staging',
            ass_ref='ref-ass',
            segments=segments,
        ),
        settings=settings,
        lock_path=lock_path,
    )
    return inspector.inspect(sample['output_ref'], sample['package'])


def gates(evidence, package, segments) -> dict:
    return {
        'visual_hook': check_visual_hook_present(evidence, package, POLICY),
        'thumbnail': check_thumbnail_present(evidence, package, POLICY),
        'subtitle': check_subtitle_burned_in(evidence, POLICY),
        'karaoke': check_karaoke_timing_valid(evidence, WORDS, POLICY),
        'disclosure': check_inference_disclosure_present(evidence, segments),
    }


def test_pw_f1_ffmpeg_is_the_pinned_binary() -> None:
    require_ffmpeg()
    lock_data = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    assert lock_data['pins']['ffmpeg']['sha256'] == PINNED_SHA
    assert sha256_file(FFMPEG) == PINNED_SHA


def test_pw_f1_correct_sample_passes_every_measured_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path)
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    for k in results:
        assert results[k].status is GateStatus.PASSED
    assert evidence.subtitle.frames_with_text == 2
    assert 0.85 <= evidence.visual_hook.similarity <= 1.0
    assert [o.highlight_ms for o in evidence.karaoke.observations] == [1000, 1500, 3000, 3500]
    assert [(o.segment_id, o.visible) for o in evidence.disclosure.observations] == [('seg-2', True)]


def test_pw_f1_replaced_hook_fails_visual_hook_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, background='smptebars')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert results['visual_hook'].status is GateStatus.FAILED
    assert results['visual_hook'].reason == 'visual_hook_similarity_below_threshold'
    assert results['subtitle'].status is GateStatus.PASSED
    assert results['karaoke'].status is GateStatus.PASSED
    assert results['disclosure'].status is GateStatus.PASSED


def test_pw_f1_missing_burned_in_subtitles_fails_subtitle_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, burn='none')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert evidence.subtitle.frames_with_text == 0
    assert results['subtitle'].status is GateStatus.FAILED
    assert results['subtitle'].reason == 'subtitle_frames_below_threshold'


def test_pw_f1_corrupt_thumbnail_fails_thumbnail_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, thumb='corrupt')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert evidence.thumbnail is None
    assert results['thumbnail'].status is GateStatus.FAILED
    assert results['thumbnail'].reason == 'thumbnail_not_observed'


def test_pw_f1_karaoke_offset_beyond_tolerance_fails_karaoke_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, first_k='80')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert results['karaoke'].status is GateStatus.FAILED
    assert results['karaoke'].reason == 'karaoke_timing_out_of_tolerance'
    assert results['karaoke'].measured_value == 300
    assert results['subtitle'].status is GateStatus.PASSED


def test_pw_f1_missing_disclosure_band_fails_with_segment_id(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, burn='karaoke_only')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert results['disclosure'].status is GateStatus.FAILED
    assert results['disclosure'].reason == 'disclosure_missing:seg-2'
    assert evidence.disclosure.observations[0].visible is False


def test_pw_f1_without_inference_segments_disclosure_is_not_applicable(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path)
    evidence = inspect_sample(sample, SEGMENTS_SOURCED)
    results = gates(evidence, sample['package'], SEGMENTS_SOURCED)
    assert evidence.disclosure is None
    assert results['disclosure'].status is GateStatus.NOT_APPLICABLE


def test_pw_f1_missing_ass_measures_nothing_and_never_passes(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, ass='none')
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    results = gates(evidence, sample['package'], SEGMENTS_INFERENCE)
    assert evidence.karaoke is None
    assert evidence.subtitle is None
    assert results['karaoke'].status is GateStatus.NOT_EVALUATED
    assert results['subtitle'].status is GateStatus.FAILED
    assert results['subtitle'].reason == 'subtitle_not_observed'
    assert results['disclosure'].status is GateStatus.FAILED
    assert results['disclosure'].reason == 'disclosure_missing:seg-2'


SCENE_SOURCES = ('testsrc2', 'smptebars', 'rgbtestsrc')
SCENE_DIALOGUES = (
    r'Dialogue: 0,0:00:00.20,0:00:01.80,Karaoke,,0,0,0,,{\k60}Alpha {\k60}beta',
    r'Dialogue: 0,0:00:02.20,0:00:03.80,Karaoke,,0,0,0,,{\k60}Gamma {\k60}delta',
    r'Dialogue: 0,0:00:04.20,0:00:05.80,Karaoke,,0,0,0,,{\k60}Omega {\k60}sigma',
    'Dialogue: 0,0:00:02.20,0:00:03.80,Disclosure,seg-2,0,0,0,,AI inference',
)
SCENE_ASS = ASS_TEMPLATE.split('Dialogue:', 1)[0] + chr(10).join(SCENE_DIALOGUES) + chr(10)


def build_scene_sample(root: pathlib.Path, *, burn: bool) -> dict:
    subs = root / 'staging' / 'subs'
    subs.mkdir(parents=True, exist_ok=True)
    (root / 'out').mkdir(parents=True, exist_ok=True)
    (subs / 'captions.ass').write_text(SCENE_ASS, encoding='utf-8')
    graph = '[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p'
    if burn:
        burn_path = root / 'burn.ass'
        burn_path.write_text(SCENE_ASS, encoding='utf-8')
        graph += ',' + burn_filter(burn_path)
    inputs: list[str] = []
    for source in SCENE_SOURCES:
        inputs += ['-f', 'lavfi', '-i', f'{source}=s=180x320:r=30:d=2']
    out_path = root / 'out' / 'final.mp4'
    ffmpeg(*inputs, '-filter_complex', graph + '[v]', '-map', '[v]', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-pix_fmt', 'yuv420p', '-an', str(out_path))
    return {'root': root, 'output_ref': str(out_path), 'package': sample_package()}


def test_pw_f1_fix3_scene_sample_without_text_fails_both_gates(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    evidence = inspect_sample(build_scene_sample(tmp_path, burn=False), SEGMENTS_INFERENCE)
    subtitle = check_subtitle_burned_in(evidence, POLICY)
    disclosure = check_inference_disclosure_present(evidence, SEGMENTS_INFERENCE)
    assert evidence.subtitle.frames_with_text == 0
    assert (subtitle.status, subtitle.reason) == (GateStatus.FAILED, 'subtitle_frames_below_threshold')
    assert (disclosure.status, disclosure.reason) == (GateStatus.FAILED, 'disclosure_missing:seg-2')


def test_pw_f1_fix3_scene_sample_with_text_passes_three_of_three(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    evidence = inspect_sample(build_scene_sample(tmp_path, burn=True), SEGMENTS_INFERENCE)
    assert evidence.subtitle.frames_with_text == 3
    assert check_subtitle_burned_in(evidence, POLICY).status is GateStatus.PASSED
    assert check_inference_disclosure_present(evidence, SEGMENTS_INFERENCE).status is GateStatus.PASSED


@pytest.mark.parametrize('burn', ['none', 'other', 'shifted'])
def test_pw_f1_fix3_no_text_other_text_or_shifted_text_fails_both_gates(tmp_path: pathlib.Path, burn: str) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, burn=burn)
    evidence = inspect_sample(sample, SEGMENTS_INFERENCE)
    assert evidence.subtitle.frames_with_text == 0
    assert check_subtitle_burned_in(evidence, POLICY).status is GateStatus.FAILED
    assert [(o.segment_id, o.visible) for o in evidence.disclosure.observations] == [('seg-2', False)]
    assert check_inference_disclosure_present(evidence, SEGMENTS_INFERENCE).status is GateStatus.FAILED


def test_pw_f1_thresholds_come_from_settings_not_code(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    settings = dataclasses.replace(SETTINGS, overlay_max_missing_share=1e-6)
    evidence = inspect_sample(build_sample(tmp_path), SEGMENTS_INFERENCE, settings=settings)
    assert evidence.subtitle.frames_with_text == 0
    assert evidence.disclosure.observations[0].visible is False
    with pytest.raises(TypeError):
        InspectorSettings()


def test_pw_f1_unpinned_ffmpeg_is_refused_before_any_run(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    bad_lock = tmp_path / 'bad.lock.json'
    bad_lock.write_text(
        json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': '0' * 64}}}),
        encoding='utf-8',
    )
    sample = build_sample(tmp_path)
    with pytest.raises(FfmpegPinRejected):
        inspect_sample(sample, SEGMENTS_INFERENCE, lock_path=bad_lock)


def test_pw_f1_frame_probe_reads_duration_and_overlay_difference(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    shown = build_sample(tmp_path / 'shown')
    hidden = build_sample(tmp_path / 'hidden', burn='none')
    ass = shown['root'] / 'staging' / 'subs' / 'captions.ass'
    probe = FrameProbe(ffmpeg_path=FFMPEG)
    media = pathlib.Path(shown['output_ref'])
    duration = probe.duration_ms(media)
    assert duration is not None and 5900 <= duration <= 6100
    band = style_band_from_ass(ass.read_text(encoding='utf-8'), 'Karaoke')
    assert band is not None
    at = dict(subtitles_path=ass, top=band.top, bottom=band.bottom)
    with_text = probe.overlay_difference(media, sample_ms=1750, **at)
    without = probe.overlay_difference(pathlib.Path(hidden['output_ref']), sample_ms=1750, **at)
    idle = probe.overlay_difference(media, sample_ms=500, **at)
    assert with_text is not None and without is not None and idle is not None
    assert with_text.ink > 0 and without.ink == pytest.approx(with_text.ink)
    assert with_text.residual <= 0.1 * with_text.ink
    assert without.residual >= 0.75 * without.ink
    assert idle.ink == 0
    assert probe.overlay_difference(media, sample_ms=60000, **at) is None
    assert probe.overlay_difference(media, sample_ms=1750, subtitles_path=tmp_path / 'a b' / 'x.ass', top=band.top, bottom=band.bottom) is None
    assert probe.overlay_difference(media, sample_ms=1750, subtitles_path=ass, top=0.5, bottom=0.5) is None


MOTION_CLIP = "color=c=gray:s=180x320:r=30:d={d},format=yuv420p,geq=lum='128+100*sin(2*PI*(X/45+T+{phase}))':cb=128:cr=128"


def make_motion_clip(path: pathlib.Path, *, seconds: float, phase: float = 0.0) -> None:
    ffmpeg(
        '-f',
        'lavfi',
        '-i',
        MOTION_CLIP.format(d=seconds, phase=phase),
        '-c:v',
        'libx264',
        '-video_track_timescale',
        '30',
        '-preset',
        'ultrafast',
        '-crf',
        '18',
        '-pix_fmt',
        'yuv420p',
        '-an',
        str(path),
    )


def clip_package(*, hook_range: tuple[int, int], thumb_range: tuple[int, int], hook_local: str, thumb_local: str):
    return validate_render_package_payload({
        'render_package_id': 'pkg-f1',
        'package_fingerprint': 'a' * 64,
        'production_snapshot_ref': 'snap',
        'script_version_ref': 'script',
        'production_plan_ref': 'plan',
        'preset_revision_ref': 'preset',
        'voice_artifact_ref': 'ref-voice',
        'word_timing_ref': 'ref-timing',
        'output_metadata_revision': 'meta',
        'output_profile_revision': 'profile',
        'language_validation_refs': ['lang'],
        'input_artifacts': [],
        'timeline': {'segments': []},
        'hook_placement': {
            'visual_hook_ref': 'ref-hook',
            'audio_hook_ref': 'ref-voice',
            'thumbnail_ref': 'ref-thumb',
            'hook_time_range': {'start_ms': hook_range[0], 'end_ms': hook_range[1]},
            'thumbnail_time_range': {'start_ms': thumb_range[0], 'end_ms': thumb_range[1]},
        },
        'subtitle_config': {'karaoke': True},
        'mix_plan': {},
        'allowed_fallbacks': [],
        'materialization_manifest': {
            'ref-hook': {'local_ref': hook_local},
            'ref-thumb': {'local_ref': thumb_local},
            'ref-ass': {'local_ref': 'subs/captions.ass'},
        },
        'output_path_ref': 'ref-output',
    })


def build_clip_sample(
    root: pathlib.Path,
    *,
    clip_seconds: float,
    hook_range: tuple[int, int] = (0, 1000),
    thumb_range: tuple[int, int] = (200, 800),
    thumb_clip: str = 'hook',
) -> dict:
    media = root / 'staging' / 'media'
    out_dir = root / 'out'
    media.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    make_motion_clip(media / 'hook.mp4', seconds=clip_seconds)
    make_motion_clip(media / 'other.mp4', seconds=3, phase=0.35)
    thumb_local = 'media/hook.mp4' if thumb_clip == 'hook' else 'media/other.mp4'
    out_path = out_dir / 'final.mp4'
    ffmpeg(
        '-i',
        str(media / 'hook.mp4'),
        '-vf',
        f'tpad=start_duration={hook_range[0] / 1000}:start_mode=add:color=black:stop_mode=clone:stop_duration=5',
        '-t',
        '4',
        '-c:v',
        'libx264',
        '-preset',
        'ultrafast',
        '-crf',
        '18',
        '-pix_fmt',
        'yuv420p',
        '-an',
        str(out_path),
    )
    return {
        'root': root,
        'output_ref': str(out_path),
        'package': clip_package(
            hook_range=hook_range,
            thumb_range=thumb_range,
            hook_local='media/hook.mp4',
            thumb_local=thumb_local,
        ),
    }


def thumbnail_result(sample: dict):
    evidence = inspect_sample(sample, SEGMENTS_SOURCED)
    return (evidence, check_thumbnail_present(evidence, sample['package'], POLICY))


def test_pw_f1_thumbnail_hook_clip_same_asset_passes(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_clip_sample(tmp_path, clip_seconds=3)
    evidence, result = thumbnail_result(sample)
    assert result.status is GateStatus.PASSED
    assert evidence.thumbnail.time_ms == 500


def test_pw_f1_thumbnail_hook_clip_offset_uses_hook_start(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_clip_sample(tmp_path, clip_seconds=3, hook_range=(1000, 2000), thumb_range=(1200, 1800))
    evidence, result = thumbnail_result(sample)
    assert result.status is GateStatus.PASSED
    assert evidence.thumbnail.time_ms == 1500


def test_pw_f1_thumbnail_short_clip_holds_last_frame_passes(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_clip_sample(tmp_path, clip_seconds=0.4)
    evidence, result = thumbnail_result(sample)
    assert result.status is GateStatus.PASSED
    assert evidence.thumbnail.time_ms == 500


def test_pw_f1_thumbnail_other_clip_is_asset_mismatch(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_clip_sample(tmp_path, clip_seconds=3, thumb_clip='other')
    evidence, result = thumbnail_result(sample)
    assert result.status is GateStatus.FAILED
    assert result.reason == 'thumbnail_asset_mismatch'


def test_pw_f1_thumbnail_same_still_image_keeps_first_frame(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path)
    sample['package'] = clip_package(hook_range=(0, 1000), thumb_range=(200, 800), hook_local='media/hook.png', thumb_local='media/hook.png')
    evidence, result = thumbnail_result(sample)
    assert result.status is GateStatus.PASSED
    assert evidence.thumbnail is not None


FIX2_WORDS = ['Prices', 'rose', 'sharply', 'today', 'Analysts', 'suspect', 'supply', 'shortage']
FIX2_DISCLOSURE = 'AI analysis, not confirmed fact'
FIX2_TYPOGRAPHY = {
    'font_name': 'Arial', 'font_size': 72, 'primary_colour': '&H0000D4FF', 'secondary_colour': '&H00FFFFFF',
    'outline_colour': '&H00000000', 'back_colour': '&H80000000', 'bold': -1, 'italic': 0, 'underline': 0,
    'strike_out': 0, 'scale_x': 100, 'scale_y': 100, 'spacing': 0, 'angle': 0, 'border_style': 1,
    'outline': 4, 'shadow': 0, 'alignment': 2, 'encoding': 1,
}
FIX2_SEGMENTS = (
    ScriptSegmentInfo(segment_id='seg-1', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
    ScriptSegmentInfo(segment_id='seg-2', order=1, claim_mode='inference', disclosure=FIX2_DISCLOSURE, word_count=4),
)
FIX2_PROFILE = OutputProfile(width=1080, height=1920, fps=30, video_codec='h264', audio_codec='aac', container='mp4', pixel_format='yuv420p', encoder='libx264', bitrate=None)


def fix2_ass_text(max_words: int = 4) -> str:
    words = [TimedWord(text, i * 500, i * 500 + 500) for i, text in enumerate(FIX2_WORDS)]
    safe_area = {'margin_left': 60, 'margin_right': 60, 'margin_vertical': 360}
    limits = {'max_words_per_line': max_words, 'max_chars_per_line': 28, 'play_res_x': 1080, 'play_res_y': 1920}
    disclosure_style = {'font_size': 40, 'alignment': 8, 'margin_v': 240}
    return build_ass_text(words, FIX2_TYPOGRAPHY, safe_area, limits, disclosure_style, FIX2_SEGMENTS)


def fix2_package(ass_local: str):
    bg = {'artifact_version_id': 'ref-bg', 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': 'image/png'}
    segments = [{'start_ms': 0, 'end_ms': 2000, 'visual_asset_refs': ['ref-bg']}, {'start_ms': 2000, 'end_ms': 4000, 'visual_asset_refs': ['ref-bg']}]
    return validate_render_package_payload({
        'render_package_id': 'pkg-f1',
        'package_fingerprint': 'a' * 64,
        'production_snapshot_ref': 'snap',
        'script_version_ref': 'script',
        'production_plan_ref': 'plan',
        'preset_revision_ref': 'preset',
        'voice_artifact_ref': 'ref-voice',
        'word_timing_ref': 'ref-timing',
        'output_metadata_revision': 'meta',
        'output_profile_revision': 'profile',
        'language_validation_refs': ['lang'],
        'input_artifacts': [bg],
        'timeline': {'duration_ms': 4000, 'segments': segments},
        'hook_placement': {
            'visual_hook_ref': 'ref-bg',
            'audio_hook_ref': 'ref-voice',
            'thumbnail_ref': 'ref-bg',
            'hook_time_range': {'start_ms': 0, 'end_ms': 1000},
            'thumbnail_time_range': {'start_ms': 200, 'end_ms': 800},
        },
        'subtitle_config': {'karaoke': True},
        'mix_plan': {},
        'allowed_fallbacks': [],
        'materialization_manifest': {
            'ref-bg': {'local_ref': 'media/bg.png'},
            'ref-voice': {'local_ref': 'media/voice.wav'},
            'ref-ass': {'local_ref': ass_local},
        },
        'output_path_ref': 'ref-output',
    })


def fix2_render(staging, ass_local, name):
    section = {'note': 'x'}
    preset = build_preset_revision({'preset_key': 'p1', 'revision': 1, 'visual_rhythm': section, 'layout_rules': section, 'thumbnail_overlay_style': section, 'typography_karaoke_style': section, 'hook_treatment': section, 'mix_rules': section, 'color_effect_rules': section, 'output_profile_ref': 'profile-1', 'fallback_constraints': section, 'compatibility_requirements': section})
    tool = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=str(FFMPEG))
    paths = MaterializedPaths(staging_root=str(staging), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg')
    spec = build_render_command(fix2_package(ass_local), preset, FIX2_PROFILE, 'ref-ass', tool, paths)
    out = staging / 'out' / name
    done = subprocess.run(build_final_argv(spec.argv, str(FFMPEG), 'libx264', str(out)), capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', timeout=120, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return out


def with_alignment_5(line: str) -> str:
    parts = line.rstrip(chr(10)).split(',')
    assert parts[0] == 'Style: Disclosure'
    parts[18] = '5'
    return ','.join(parts) + chr(10)


@pytest.fixture(scope='module')
def fix2_world(tmp_path_factory):
    require_ffmpeg()
    staging = tmp_path_factory.mktemp('pw_f1_fix2') / 'staging'
    for folder in ('media', 'subs', 'out'):
        (staging / folder).mkdir(parents=True)
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=1', '-frames:v', '1', str(staging / 'media' / 'bg.png'))
    ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=1000:duration=4', '-c:a', 'pcm_s16le', str(staging / 'media' / 'voice.wav'))
    lines = fix2_ass_text().splitlines(keepends=True)
    variants = {'with.ass': lines, 'without_dialogue.ass': [x for x in lines if not (x.startswith('Dialogue:') and ',Disclosure,' in x)], 'without_style.ass': [x for x in lines if not x.startswith('Style: Disclosure,')]}
    assert len(variants['without_dialogue.ass']) == len(lines) - 1 and len(variants['without_style.ass']) == len(lines) - 1
    for name, kept in variants.items():
        (staging / 'subs' / name).write_text(''.join(kept), encoding='utf-8')
    (staging / 'subs' / 'continuous.ass').write_text(fix2_ass_text(max_words=3), encoding='utf-8')
    (staging / 'subs' / 'center.ass').write_text(''.join(with_alignment_5(x) if x.startswith('Style: Disclosure,') else x for x in lines), encoding='utf-8')
    return {
        'staging': staging,
        'video_with': fix2_render(staging, 'subs/with.ass', 'with.mp4'),
        'video_without': fix2_render(staging, 'subs/without_dialogue.ass', 'without.mp4'),
        'video_continuous': fix2_render(staging, 'subs/continuous.ass', 'continuous.mp4'),
        'video_center': fix2_render(staging, 'subs/center.ass', 'center.mp4'),
    }


def fix2_inspect(world, video, ass_local, settings=SETTINGS):
    inspector = RealOutputInspector(inputs=InspectionInputs(staging_root=world['staging'], ass_ref='ref-ass', segments=SEGMENTS_INFERENCE), settings=settings, lock_path=LOCK_PATH)
    evidence = inspector.inspect(str(video), fix2_package(ass_local))
    return evidence, check_inference_disclosure_present(evidence, SEGMENTS_INFERENCE)


def test_pw_f1_fix2_static_background_disclosure_passes_with_production_band(fix2_world) -> None:
    evidence, result = fix2_inspect(fix2_world, fix2_world['video_with'], 'subs/with.ass')
    assert [(o.segment_id, o.visible) for o in evidence.disclosure.observations] == [('seg-2', True)]
    assert result.status is GateStatus.PASSED


def test_pw_f1_fix3_continuous_speech_render_passes_both_gates(fix2_world) -> None:
    text = (fix2_world['staging'] / 'subs' / 'continuous.ass').read_text(encoding='utf-8')
    spans = sorted((d.start_ms, d.end_ms) for d in parse_ass_dialogues(text) if d.style == 'Karaoke')
    assert len(spans) == 3
    assert all(nxt[0] - prev[1] < 400 for prev, nxt in zip(spans, spans[1:])) and spans[0][0] < 400 and 4000 - spans[-1][1] < 400
    evidence, disclosure = fix2_inspect(fix2_world, fix2_world['video_continuous'], 'subs/continuous.ass')
    assert evidence.subtitle is not None, 'subtitle_not_observed'
    assert evidence.subtitle.frames_with_text == 3
    assert check_subtitle_burned_in(evidence, POLICY).status is GateStatus.PASSED
    assert disclosure.status is GateStatus.PASSED


def test_pw_f1_fix3_premise_same_frame_ratio_holds_for_narrow_and_wide_band(fix2_world) -> None:
    probe = FrameProbe(ffmpeg_path=FFMPEG, timeout_seconds=60)
    ass = fix2_world['staging'] / 'subs' / 'with.ass'
    for top, bottom in ((0.125, 0.175), (0.10, 0.25)):
        shown = probe.overlay_difference(fix2_world['video_with'], sample_ms=3000, subtitles_path=ass, top=top, bottom=bottom)
        hidden = probe.overlay_difference(fix2_world['video_without'], sample_ms=3000, subtitles_path=ass, top=top, bottom=bottom)
        assert shown is not None and hidden is not None
        assert shown.ink > 0 and shown.residual <= 0.1 * shown.ink
        assert hidden.residual >= 0.75 * hidden.ink


def test_pw_f1_fix2_render_without_disclosure_dialogue_fails(fix2_world) -> None:
    evidence, result = fix2_inspect(fix2_world, fix2_world['video_without'], 'subs/with.ass')
    assert [(o.segment_id, o.visible) for o in evidence.disclosure.observations] == [('seg-2', False)]
    assert result.status is GateStatus.FAILED
    assert result.reason == 'disclosure_missing:seg-2'


@pytest.mark.parametrize(
    ('video', 'ass_local', 'band', 'visible'),
    [
        ('video_with', 'subs/without_style.ass', Band(top=0.12, bottom=0.18), False),
        ('video_with', 'subs/with.ass', Band(top=0.50, bottom=0.60), True),
        ('video_center', 'subs/center.ass', Band(top=0.45, bottom=0.55), True),
        ('video_center', 'subs/center.ass', Band(top=0.10, bottom=0.25), False),
    ],
    ids=['missing_style_row_not_visible', 'style_band_beats_settings_band', 'alignment_5_uses_settings_band', 'alignment_5_other_settings_band_not_visible'],
)
def test_pw_f1_fix2_disclosure_band_source(fix2_world, video: str, ass_local: str, band: Band, visible: bool) -> None:
    settings = dataclasses.replace(SETTINGS, disclosure_band=band)
    evidence, _ = fix2_inspect(fix2_world, fix2_world[video], ass_local, settings=settings)
    assert evidence.disclosure.observations[0].visible is visible

STYLE_FORMAT = 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'


def style_ass(*, play_res_y='1920', size='40', outline='4', alignment='8', margin_v='240', with_style=True) -> str:
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080']
    if play_res_y is not None:
        lines.append(f'PlayResY: {play_res_y}')
    lines += ['', '[V4+ Styles]', STYLE_FORMAT, 'Style: Karaoke,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,2,60,60,360,1']
    if with_style:
        lines.append(f'Style: Disclosure,Arial,{size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{outline},0,{alignment},60,60,{margin_v},1')
    lines += ['', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    return chr(10).join(lines) + chr(10)


@pytest.mark.parametrize(
    ('kwargs', 'top', 'bottom'),
    [
        ({}, 0.125, 0.175),
        ({'alignment': '7'}, 0.125, 0.175),
        ({'alignment': '9'}, 0.125, 0.175),
        ({'alignment': '2'}, 0.825, 0.875),
        ({'alignment': '1'}, 0.825, 0.875),
        ({'alignment': '3'}, 0.825, 0.875),
        ({'margin_v': '1900'}, 1900 / 1920, 1.0),
        ({'alignment': '2', 'margin_v': '1900'}, 0.0, 1 - 1900 / 1920),
    ],
)
def test_pw_f1_fix2_band_from_style_geometry(kwargs: dict, top: float, bottom: float) -> None:
    band = disclosure_band_from_ass(style_ass(**kwargs))
    assert band is not None
    assert (band.top, band.bottom) == pytest.approx((top, bottom))


@pytest.mark.parametrize(
    'kwargs',
    [
        {'with_style': False},
        {'play_res_y': None},
        {'play_res_y': 'abc'},
        {'play_res_y': '0'},
        {'alignment': '4'},
        {'alignment': '5'},
        {'alignment': '6'},
        {'alignment': 'x'},
        {'size': 'abc'},
        {'outline': ''},
        {'margin_v': 'abc'},
        {'margin_v': '2000'},
    ],
)
def test_pw_f1_fix2_band_none_falls_back(kwargs: dict) -> None:
    assert disclosure_band_from_ass(style_ass(**kwargs)) is None


def test_pw_f1_fix2_band_follows_the_section_format_order() -> None:
    text = chr(10).join([
        '[Script Info]',
        'PlayResY: 1920',
        '[V4+ Styles]',
        'Format: Name, MarginV, Alignment, Fontsize, Outline',
        'Style: Disclosure,240,8,40,4',
    ]) + chr(10)
    band = disclosure_band_from_ass(text)
    assert band is not None
    assert (band.top, band.bottom) == pytest.approx((0.125, 0.175))


def karaoke_line(text: str, start_ms: int = 1000, end_ms: int = 2500) -> AssDialogue:
    return AssDialogue(style='Karaoke', name='', start_ms=start_ms, end_ms=end_ms, text=text)


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        (r'{\k50}Hello {\k100}world', 2000),
        (r'{\k50}good {\k50}day', 1250),
        (r'{\k20}{\k30}hi {\k90}there', 1950),
        ('plain text without tags', 1750),
        (r'{\k0}zero', 1750),
    ],
    ids=['longest_word', 'tie_takes_first', 'gap_tag_is_skipped', 'no_tag_uses_line_middle', 'zero_length_uses_line_middle'],
)
def test_pw_f1_fix3_karaoke_sample_ms(text: str, expected: int) -> None:
    assert karaoke_sample_ms(karaoke_line(text)) == expected


def test_pw_f1_fix3_style_band_from_ass_reads_the_karaoke_row() -> None:
    band = style_band_from_ass(style_ass(), 'Karaoke')
    assert band is not None
    assert (band.top, band.bottom) == pytest.approx((1 - 360 / 1920 - 2 * (72 + 8) / 1920, 1 - 360 / 1920))
    assert style_band_from_ass(style_ass(), 'Missing') is None


@pytest.mark.parametrize('value', [0, 0.0, 1, 1.0, -0.25, 1.5, True, False, float('nan'), float('inf'), '0.25', None])
def test_pw_f1_fix3_overlay_max_missing_share_is_validated(value) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(SETTINGS, overlay_max_missing_share=value)


def test_pw_f1_fix3_overlay_max_missing_share_has_no_default() -> None:
    field = {f.name: f for f in dataclasses.fields(InspectorSettings)}['overlay_max_missing_share']
    assert field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING


def test_pw_f1_fix3_subtitles_filter_path_escapes_like_the_renderer() -> None:
    assert subtitles_filter_path('C:' + BACKSLASH + 'a' + BACKSLASH + 'b.ass') == 'C' + BACKSLASH * 2 + ':/a/b.ass'
    assert subtitles_filter_path('C:/a b/x.ass') is None
    assert subtitles_filter_path('C:/a,b/x.ass') is None
    assert subtitles_filter_path('') is None
