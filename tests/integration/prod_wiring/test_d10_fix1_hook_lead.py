"""D-10-FIX1: plan thật của D (thumbnail dời sang sau lead-in) đi qua build_render_command, RealFfmpegRenderer và RealOutputInspector thật; VISUAL_HOOK_PRESENT và THUMBNAIL_PRESENT cùng đạt (FFmpeg ghim thật, không DB).

coveredIds: CT-RND-003, CT-QC-001
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

from render.adapters.real_output_inspector import Band, InspectionInputs, InspectorSettings, RealOutputInspector
from render.domain.content_gates import check_thumbnail_present, check_visual_hook_present
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateStatus, QualityPolicy
from render.ports.renderer import RendererStatus

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
D10_TESTS = ROOT / 'tests' / 'unit' / 'creative' / 'test_d10_production_plan.py'
F10_RIG = ROOT / 'tests' / 'integration' / 'render' / 'test_f10_fix4_render_loudness.py'
MIN_SIMILARITY = json.loads(PROFILE.read_text(encoding='utf-8'))['qc']['hook_similarity_min']['value']
VOICE_SECONDS = 4.0


def load_module(name, path):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


d10 = load_module('d10_fix1_plan_tests', D10_TESTS)
f10 = load_module('d10_fix1_render_rig', F10_RIG)


def require_ffmpeg():
    if not pathlib.Path(f10.FFMPEG).is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)


def make_media(path, source, *extra):
    done = f10.run([f10.FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', source, *extra, str(path)])
    assert done.returncode == 0, done.stderr


def stage(tmp_path, placement):
    """Rig của F-10-FIX4 (giọng, âm hook, nền, ASS, preset production) cộng clip hook gradient, ảnh bài 1200x630 và hook_placement cho trước."""
    rig = f10.Rig(tmp_path, VOICE_SECONDS)
    media = rig.root / 'media'
    make_media(media / 'hook.mp4', 'gradients=s=1080x1920:r=30:d=3:seed=7', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an')
    make_media(media / 'thumb.png', 'testsrc2=s=1200x630:r=1:d=1', '-frames:v', '1')
    hook_ref, audio_ref, thumb_ref = placement['visual_hook_ref'], placement['audio_hook_ref'], placement['thumbnail_ref']
    manifest = {'ref-bg': 'media/bg.png', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass', hook_ref: 'media/hook.mp4', audio_ref: 'media/hook.wav', thumb_ref: 'media/thumb.png'}
    rig.record = validate_render_package_payload({
        'render_package_id': 'pkg-d10-fix1', 'package_fingerprint': 'a' * 64, 'production_snapshot_ref': 'snap-1',
        'script_version_ref': 'script-1', 'production_plan_ref': 'plan-1', 'preset_revision_ref': 'preset-1',
        'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing', 'output_metadata_revision': 'meta-1',
        'output_profile_revision': 'profile-1', 'language_validation_refs': ['lang-1'],
        'input_artifacts': [f10.artifact('ref-bg', 'image/png'), f10.artifact(hook_ref, 'video/mp4'), f10.artifact(thumb_ref, 'image/png')],
        'timeline': {'duration_ms': rig.voice_ms, 'segments': [{'start_ms': 0, 'end_ms': rig.voice_ms, 'visual_asset_refs': ['ref-bg']}]},
        'hook_placement': placement, 'subtitle_config': {'karaoke': True}, 'mix_plan': {}, 'allowed_fallbacks': [],
        'materialization_manifest': {ref: {'local_ref': local} for ref, local in manifest.items()},
        'output_path_ref': 'ref-output',
    })
    return rig


def render(rig):
    outcome = rig.run(rig.spec('final'))
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    return outcome.output_ref


def judge(rig, output_ref):
    settings = InspectorSettings(compare_width=90, compare_height=160, thumbnail_min_ssim=MIN_SIMILARITY, subtitle_band=Band(top=0.70, bottom=0.80), disclosure_band=Band(top=0.10, bottom=0.25), overlay_max_missing_share=0.25, max_subtitle_samples=4, timeout_seconds=120)
    inspector = RealOutputInspector(inputs=InspectionInputs(staging_root=rig.root, ass_ref='ref-ass', segments=[]), settings=settings)
    evidence = inspector.inspect(output_ref, rig.record)
    policy = QualityPolicy(revision='d10-fix1', thresholds={'VISUAL_HOOK_PRESENT': {'min_similarity': MIN_SIMILARITY}})
    return evidence, check_visual_hook_present(evidence, rig.record, policy), check_thumbnail_present(evidence, rig.record, policy)


AI_CASES = [
    ((0, 3000), (0, 3000), (500, 3000)),
    ((0, 3000), (0, 600), (500, 1100)),
    ((0, 1000), (0, 1000), (500, 1000)),
    ((0, 3000), (500, 1500), (500, 1500)),
]


@pytest.mark.parametrize('hook, thumb, expected', AI_CASES)
def test_plan_from_d_passes_visual_hook_and_thumbnail_gates(tmp_path, hook, thumb, expected):
    require_ffmpeg()
    plan = d10._build(d10._hook(hook, thumb))
    placement = plan.to_render_package_inputs()['hook_placement']
    assert placement['hook_time_range'] == {'start_ms': hook[0], 'end_ms': hook[1]}
    assert placement['thumbnail_time_range'] == {'start_ms': expected[0], 'end_ms': expected[1]}
    rig = stage(tmp_path, placement)
    evidence, hook_gate, thumb_gate = judge(rig, render(rig))
    assert hook_gate.status is GateStatus.PASSED, hook_gate.reason
    assert evidence.visual_hook.similarity >= MIN_SIMILARITY
    assert thumb_gate.status is GateStatus.PASSED, thumb_gate.reason


def test_package_whose_thumbnail_covers_the_whole_hook_fails_visual_hook(tmp_path):
    require_ffmpeg()
    plan = d10._build(d10._hook((0, 3000), (500, 1500)))
    placement = dict(plan.to_render_package_inputs()['hook_placement'], thumbnail_time_range={'start_ms': 0, 'end_ms': 3000})
    rig = stage(tmp_path, placement)
    evidence, hook_gate, thumb_gate = judge(rig, render(rig))
    assert hook_gate.status is GateStatus.FAILED
    assert hook_gate.reason == 'visual_hook_similarity_below_threshold'
    assert evidence.visual_hook.similarity < MIN_SIMILARITY
