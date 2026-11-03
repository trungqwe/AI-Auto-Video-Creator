"""QC-HOOK-FIX: clip hook tối 16:9 (như clip Pixabay của lô f132d43a) đi qua render thật trên cảnh JPEG, nên output là full range
(yuvj420p); inspector thật phải đo hook và thumbnail như khi output là limited range, và vẫn bắt clip khác (FFmpeg ghim thật, không DB, không mạng).

coveredIds: CT-QC-001
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

from render.adapters.frame_probe import FrameProbe
from render.adapters.real_ffprobe_probe import DEFAULT_FFPROBE_PATH
from render.adapters.real_output_inspector import ssim_between
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateStatus

HERE = pathlib.Path(__file__).resolve().parent
D10_FIX1 = HERE / 'test_d10_fix1_hook_lead.py'


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


base = load_module('qc_hook_fix_d10_fix1', D10_FIX1)
render, judge, make_media = base.render, base.judge, base.make_media
require_ffmpeg, MIN_SIMILARITY, d10, f10 = base.require_ffmpeg, base.MIN_SIMILARITY, base.d10, base.f10

LINES = (
    ',drawbox=x=80:y=0:w=3:h=1080:color=0x5a1010:t=fill,drawbox=x=470:y=0:w=2:h=620:color=0x3a3a3a:t=fill'
    ',drawbox=x=50:y=380:w=650:h=650:color=0x2c2c2c:t=2,drawbox=x=940:y=20:w=880:h=1040:color=0x262626:t=2'
    ',drawbox=x=120:y=96:w=10:h=10:color=0xd8d8d8:t=fill,drawbox=x=170:y=96:w=10:h=10:color=0xd8d8d8:t=fill'
    ',drawbox=x=1620:y=960:w=10:h=10:color=0xd8d8d8:t=fill,drawbox=x=1200:y=400:w=12:h=12:color=0x801818:t=fill'
)
DARK_HOOK = f'color=c=black:s=1920x1080:r=30:d=3{LINES}'
OTHER_DARK = 'color=c=0x0a0a0a:s=1920x1080:r=30:d=3,drawbox=x=300:y=200:w=1300:h=700:color=0x3c3c3c:t=8,drawbox=x=900:y=0:w=4:h=1080:color=0x7a2020:t=fill'


def stage(tmp_path, scene):
    """Rig của F-10-FIX4 với cảnh là ảnh scene (bg.jpg hoặc bg.png), clip hook tối 1920x1080 và thumbnail lấy từ chính clip hook (như thumb:pxb-…)."""
    plan = d10._build(d10._hook((0, 3000), (500, 1500)))
    placement = dict(plan.to_render_package_inputs()['hook_placement'])
    rig = f10.Rig(tmp_path, base.VOICE_SECONDS)
    media = rig.root / 'media'
    make_media(media / scene, 'testsrc2=s=1080x1920:r=1:d=1', '-frames:v', '1')
    make_media(media / 'hook.mp4', DARK_HOOK, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an')
    make_media(media / 'other.mp4', OTHER_DARK, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an')
    hook_ref, audio_ref, thumb_ref = placement['visual_hook_ref'], placement['audio_hook_ref'], placement['thumbnail_ref']
    manifest = {'ref-bg': f'media/{scene}', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass', hook_ref: 'media/hook.mp4', audio_ref: 'media/hook.wav', thumb_ref: 'media/hook.mp4'}
    scene_type = 'image/jpeg' if scene.endswith('.jpg') else 'image/png'
    rig.record = validate_render_package_payload({
        'render_package_id': 'pkg-qc-hook-fix', 'package_fingerprint': 'b' * 64, 'production_snapshot_ref': 'snap-1',
        'script_version_ref': 'script-1', 'production_plan_ref': 'plan-1', 'preset_revision_ref': 'preset-1',
        'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing', 'output_metadata_revision': 'meta-1',
        'output_profile_revision': 'profile-1', 'language_validation_refs': ['lang-1'],
        'input_artifacts': [f10.artifact('ref-bg', scene_type), f10.artifact(hook_ref, 'video/mp4'), f10.artifact(thumb_ref, 'video/mp4')],
        'timeline': {'duration_ms': rig.voice_ms, 'segments': [{'start_ms': 0, 'end_ms': rig.voice_ms, 'visual_asset_refs': ['ref-bg']}]},
        'hook_placement': placement, 'subtitle_config': {'karaoke': True}, 'mix_plan': {}, 'allowed_fallbacks': [],
        'materialization_manifest': {ref: {'local_ref': local} for ref, local in manifest.items()},
        'output_path_ref': 'ref-output',
    })
    return rig, placement


def colour_range(path):
    done = subprocess.run(
        [str(DEFAULT_FFPROBE_PATH), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=color_range', '-of', 'json', str(path)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=120, check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)['streams'][0].get('color_range')


def hook_similarity(output, clip):
    canvas = FrameProbe(ffmpeg_path=f10.FFMPEG).frame_size(pathlib.Path(output))
    return ssim_between(f10.FFMPEG, pathlib.Path(output), 0, clip, None, width=90, height=160, timeout_seconds=120, canvas=canvas)


def test_dark_hook_over_jpeg_scenes_passes_hook_and_thumbnail_and_other_clip_fails(tmp_path):
    require_ffmpeg()
    rig, placement = stage(tmp_path, 'bg.jpg')
    output = render(rig)
    assert colour_range(output) == 'pc'
    evidence, hook_gate, thumb_gate = judge(rig, output)
    print(f'QCHOOKFIX full_range hook={evidence.visual_hook and evidence.visual_hook.similarity!r} thumb={thumb_gate.status} {thumb_gate.reason}')
    assert hook_gate.status is GateStatus.PASSED, hook_gate.reason
    assert evidence.visual_hook.similarity >= MIN_SIMILARITY
    assert thumb_gate.status is GateStatus.PASSED, thumb_gate.reason
    assert evidence.thumbnail.asset_ref == placement['thumbnail_ref']
    other = hook_similarity(output, rig.root / 'media' / 'other.mp4')
    assert other is not None and other < MIN_SIMILARITY


def test_full_range_output_measures_like_limited_range_output(tmp_path):
    require_ffmpeg()
    jpeg_rig, _ = stage(tmp_path / 'jpeg', 'bg.jpg')
    png_rig, _ = stage(tmp_path / 'png', 'bg.png')
    jpeg_out, png_out = render(jpeg_rig), render(png_rig)
    assert colour_range(jpeg_out) == 'pc' and colour_range(png_out) != 'pc'
    full = hook_similarity(jpeg_out, jpeg_rig.root / 'media' / 'hook.mp4')
    limited = hook_similarity(png_out, png_rig.root / 'media' / 'hook.mp4')
    print(f'QCHOOKFIX full={full!r} limited={limited!r}')
    assert full is not None and limited is not None
    assert limited >= MIN_SIMILARITY
    assert abs(full - limited) <= 0.02
