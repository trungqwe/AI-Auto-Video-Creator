"""PRS-LAYOUT-RENDER: video dựng theo bố cục của preset qua FFmpeg ghim thật, khung giữa mỗi cảnh trùng khung QC của compose_layout.

Preset có layout_rules.presentation thì mỗi cảnh hiện ảnh của cảnh ở ô chính và ảnh kế tiếp ở các ô phụ; preset không có thì giữ cảnh
một ảnh (argv và đồ thị như cũ); ít ảnh hơn bố cục cần, đồ thị quá dài hay cảnh không phải ảnh tĩnh thì giữ cảnh một ảnh và ghi lý do.
Không mạng, không CSDL.

coveredIds: FR-PRS-002, FR-PRS-003
"""
import pathlib
import subprocess
from types import SimpleNamespace

import pytest

from render.adapters.real_ffmpeg_renderer import DEFAULT_LOCK_PATH, build_final_argv, verify_ffmpeg_pin
from render.domain import layout, render_command
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.render_command import RenderCommandRejected, build_render_command
from tests.integration.render.test_f10_fix6_frame_placement import FFMPEG, H, W, grab_frame, make_stage, materialized, profile, tool, write_png_raw

COLOURS = {'ref-a': (220, 30, 30), 'ref-b': (30, 200, 60), 'ref-c': (40, 60, 230), 'ref-d': (230, 200, 20)}
HOOK = {'visual_hook_ref': 'ref-hook', 'audio_hook_ref': 'ref-hook-a', 'thumbnail_ref': 'ref-hook', 'hook_time_range': {'start_ms': 0, 'end_ms': 400}, 'thumbnail_time_range': {'start_ms': 100, 'end_ms': 300}}


def preset(presentation=None):
    section = {'note': 'x'}
    rules = {'note': 'x'} if presentation is None else {'note': 'x', 'presentation': presentation}
    return build_preset_revision({
        'preset_key': 'p1', 'revision': 1, 'visual_rhythm': section, 'layout_rules': rules,
        'thumbnail_overlay_style': section, 'typography_karaoke_style': section, 'hook_treatment': section,
        'mix_rules': section, 'color_effect_rules': section, 'output_profile_ref': 'profile-1',
        'fallback_constraints': section, 'compatibility_requirements': section,
    })


def record_for(refs, scene_ms=1000, scenes=None):
    order = scenes if scenes is not None else refs
    segments = [{'start_ms': i * scene_ms, 'end_ms': (i + 1) * scene_ms, 'visual_asset_refs': [ref]} for i, ref in enumerate(order)]
    locals_ = {ref: f'media/{ref}.png' for ref in refs}
    locals_.update({'ref-hook': 'media/ref-hook.png', 'ref-hook-a': 'media/hook.wav', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass'})
    return validate_render_package_payload({
        'render_package_id': 'pkg-1', 'package_fingerprint': 'a' * 64, 'production_snapshot_ref': 'snap-1',
        'script_version_ref': 'script-1', 'production_plan_ref': 'plan-1', 'preset_revision_ref': 'preset-1',
        'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing', 'output_metadata_revision': 'meta-1',
        'output_profile_revision': 'profile-1', 'language_validation_refs': ['lang-1'],
        'input_artifacts': [{'artifact_version_id': ref, 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': 'image/png'} for ref in [*refs, 'ref-hook']],
        'timeline': {'duration_ms': scene_ms * len(order), 'segments': segments}, 'hook_placement': HOOK,
        'subtitle_config': {'karaoke': True}, 'mix_plan': {}, 'allowed_fallbacks': [],
        'materialization_manifest': {ref: {'local_ref': local} for ref, local in locals_.items()},
        'output_path_ref': 'ref-output',
    })


@pytest.fixture(scope='module')
def stage(tmp_path_factory):
    verify_ffmpeg_pin(pathlib.Path(FFMPEG), DEFAULT_LOCK_PATH)
    root = make_stage(tmp_path_factory.mktemp('prs_render'))
    for ref, colour in {**COLOURS, 'ref-hook': (255, 255, 255)}.items():
        width, height = (160, 90) if ref != 'ref-c' else (90, 160)
        write_png_raw(root / 'media' / f'{ref}.png', width, height, b''.join(b'\x00' + bytes(colour) * width for _ in range(height)))
    return root


def pixel(frame, x, y):
    at = (y * W + x) * 3
    return tuple(frame[at:at + 3])


def near(found, wanted, limit=40):
    return all(abs(a - b) <= limit for a, b in zip(found, wanted))


def inside(box, fx=0.25, fy=0.3):
    return round(box.x + box.w * fx), round(box.y + box.h * fy)


def test_hero_strip_video_shows_the_scene_image_in_the_main_cell_and_the_next_ones_in_the_strip(stage):
    refs = ['ref-a', 'ref-b', 'ref-c', 'ref-d']
    record = record_for(refs[:3])
    spec = build_render_command(record, preset({'layout_key': 'HERO_STRIP', 'accent_colour': '#FFD400'}), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=3000)
    graph = spec.argv[spec.argv.index('-filter_complex') + 1]
    assert len(graph) < render_command.LAYOUT_GRAPH_MAX_CHARS
    assert '{image:2}' in spec.redacted_argv and '{asset:0}' not in spec.redacted_argv
    output = stage / 'out' / 'hero.mp4'
    done = subprocess.run(build_final_argv(spec.argv, FFMPEG, 'libx264', str(output)), capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=600, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    geometry = layout.layout_geometry('HERO_STRIP')
    main = layout.Box(40, 510, 1000, 620)
    strip = [cell.box for cell in geometry.cells[1:]]
    for scene, frame_index in ((1, 45), (2, 75)):
        frame = grab_frame(output, frame_index)
        cells, _ = layout.slot_sources('HERO_STRIP', refs[:3], scene)
        assert near(pixel(frame, *inside(main)), COLOURS[cells[0]]), (scene, pixel(frame, *inside(main)))
        for box, ref in zip(strip, cells[1:]):
            assert near(pixel(frame, *inside(box, 0.5, 0.5)), COLOURS[ref]), (scene, ref)
        assert near(pixel(frame, 540, 395), (255, 212, 0)), scene


def test_preset_without_presentation_keeps_the_single_image_scene(stage):
    record = record_for(['ref-a', 'ref-b', 'ref-c'])
    plain = build_render_command(record, preset(), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=3000)
    graph = plain.argv[plain.argv.index('-filter_complex') + 1]
    assert render_command.frame_placement(1080, 1920, 's0') in graph and '[ku0]' not in graph
    assert '{asset:0}' in plain.redacted_argv


@pytest.mark.parametrize('key, refs, reason', [
    ('HERO_STRIP', ['ref-a'], 'too_few_images'),
    ('MOSAIC_GRID', ['ref-a', 'ref-b'], 'too_few_images'),
])
def test_too_few_images_keep_the_single_image_scene_and_say_why(stage, key, refs, reason):
    record = record_for(refs, scenes=refs * 2)
    spec = build_render_command(record, preset({'layout_key': key, 'accent_colour': '#FF3B30'}), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=2000 * len(refs))
    plain = build_render_command(record, preset(), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=2000 * len(refs))
    assert spec.argv == plain.argv
    assert spec.spec_fingerprint != plain.spec_fingerprint


def test_a_graph_longer_than_the_cap_keeps_the_single_image_scene(stage):
    # PRS-LAYOUT-POLISH: the cap is LAYOUT_SCRIPT_MAX_CHARS (the graph reaches ffmpeg through a file); 240 scenes exceed it.
    refs = ['ref-a', 'ref-b', 'ref-c', 'ref-d']
    record = record_for(refs, scene_ms=100, scenes=refs * 60)
    spec = build_render_command(record, preset({'layout_key': 'MOSAIC_GRID', 'accent_colour': '#FF3B30'}), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=24000)
    assert '{asset:239}' in spec.redacted_argv and '{image:0}' not in spec.redacted_argv


@pytest.mark.parametrize('presentation', [{'layout_key': 'GRID', 'accent_colour': '#FFD400'}, {'layout_key': 'HERO_STRIP', 'accent_colour': 'yellow'}, 'HERO_STRIP'])
def test_a_malformed_presentation_is_refused(stage, presentation):
    record = record_for(['ref-a', 'ref-b'])
    with pytest.raises(RenderCommandRejected) as caught:
        build_render_command(record, preset(presentation), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=2000)
    assert caught.value.reason == 'invalid_preset.layout_rules.presentation'


def test_twelve_scene_layout_videos_stay_under_the_cap(stage):
    refs = ['ref-a', 'ref-b', 'ref-c', 'ref-d']
    for key in layout.LAYOUT_KEYS:
        record = record_for(refs, scene_ms=1000, scenes=(refs * 3)[:12])
        spec = build_render_command(record, preset({'layout_key': key, 'accent_colour': '#00F0FF'}), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=12000)
        assert '{image:0}' in spec.redacted_argv, key
        assert len(spec.argv[spec.argv.index('-filter_complex') + 1]) <= render_command.LAYOUT_SCRIPT_MAX_CHARS, key
