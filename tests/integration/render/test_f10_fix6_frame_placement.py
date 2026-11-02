"""F-10-FIX6: ảnh bất kỳ tỉ lệ nào hiện trọn trong khung 1080x1920 qua FFmpeg ghim thật

Cảnh ảnh ngang đặt giữa khung dọc trên nền là chính ảnh làm mờ, làm tối; hook và thumbnail
dùng cùng bộ dựng frame_placement, cảnh ảnh tĩnh zoom chậm bằng loop, select và perspective.

coveredIds: CT-RND-004, CT-QC-001
"""
import json
import pathlib
import struct
import subprocess
import wave
import warnings
import zlib

import pytest
from types import SimpleNamespace

from render.domain import render_command
from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, build_final_argv, verify_ffmpeg_pin
from render.adapters.real_ffprobe_probe import DEFAULT_FFPROBE_PATH
from render.adapters.real_output_inspector import Band, InspectionInputs, InspectorSettings, RealOutputInspector
from render.domain.content_gates import check_thumbnail_present, check_visual_hook_present
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.quality_report import GateStatus, QualityPolicy
from render.domain.render_command import MaterializedPaths, OutputProfile, ToolIdentity, build_render_command

ROOT = pathlib.Path(__file__).resolve().parents[3]
MIN_SIMILARITY = json.loads((ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json').read_text(encoding='utf-8'))['qc']['hook_similarity_min']['value']
FFMPEG = DEFAULT_FFMPEG_PATH
W, H, FPS = 1080, 1920, 30
ROW = 960
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 200, 0)
PURPLE = (200, 0, 200)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ASS_TEXT = chr(10).join([
    '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    'Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1', '', '[Events]',
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    'Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,Sub',
]) + chr(10)


def write_png_raw(path, width, height, raw):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    path.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def write_wav(path, seconds):
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(bytes(2 * int(48000 * seconds)))


def run_process(command):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=600, check=False)


def probe(path):
    done = run_process([DEFAULT_FFPROBE_PATH, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames,duration:format=duration', '-of', 'json', str(path)])
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def write_marked_png(path, width, height, cell, left=None, right=None):
    row = bytearray()
    for x in range(width):
        c = x // cell
        if left and c == 0:
            colour = left
        elif right and x >= width - cell:
            colour = right
        elif c % 2 == 0:
            colour = WHITE
        else:
            colour = BLACK
        row.extend(bytes(colour))
    raw = (bytes([0]) + bytes(row)) * height
    write_png_raw(path, width, height, raw)


def grab_frame(video, index):
    done = subprocess.run([FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-i', str(video), '-vf', f"select='eq(n,{index})'", '-frames:v', '1', '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, stdin=subprocess.DEVNULL, timeout=600, check=False)
    assert done.returncode == 0, done.stderr[-2000:].decode('utf-8', 'replace')
    assert len(done.stdout) == W * H * 3
    return done.stdout


def frame_of(world, index):
    if index not in world.frames:
        world.frames[index] = grab_frame(world.output, index)
    return world.frames[index]


def row_pixels(frame, y=ROW):
    return [tuple(frame[i:i + 3]) for i in range(y * W * 3, (y + 1) * W * 3, 3)]


def near(pixel, colour, limit=70):
    return all(abs(a - b) <= limit for a, b in zip(pixel, colour))


def run_start(pixels, colour, minimum=8):
    for x in range(len(pixels) - minimum + 1):
        if all(near(p, colour) for p in pixels[x:x + minimum]):
            return x
    return None


def luma(pixel):
    r, g, b = pixel
    return (299 * r + 587 * g + 114 * b) / 1000


def edge_x(pixels):
    values = [luma(p) for p in pixels]
    for i in range(len(values) - 1):
        if values[i] >= 127.5 > values[i + 1]:
            return i + (values[i] - 127.5) / (values[i] - values[i + 1])
    assert False, 'no bright to dark edge in the row'


def mean_diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def band_mean(frame, top, bottom):
    return sum(frame[top * W * 3:bottom * W * 3]) / ((bottom - top) * W * 3)


def max_step(frame, rows):
    return max(abs(frame[i + 3] - frame[i]) for y in rows for i in range(y * W * 3, (y + 1) * W * 3 - 3))


def value_after(argv, flag):
    assert flag in argv
    return argv[argv.index(flag) + 1]


def artifact(ref, media_type):
    return {'artifact_version_id': ref, 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': media_type}


def preset(revision=1, note='x'):
    section = {'note': note}
    return build_preset_revision({
        'preset_key': 'p1', 'revision': revision, 'visual_rhythm': section, 'layout_rules': section,
        'thumbnail_overlay_style': section, 'typography_karaoke_style': section, 'hook_treatment': section,
        'mix_rules': section, 'color_effect_rules': section, 'output_profile_ref': 'profile-1',
        'fallback_constraints': section, 'compatibility_requirements': section,
    })


def profile(**changes):
    values = {
        'width': 1080, 'height': 1920, 'fps': 30, 'video_codec': 'h264', 'audio_codec': 'aac',
        'container': 'mp4', 'pixel_format': 'yuv420p', 'encoder': 'libx264', 'bitrate': None,
    }
    values.update(changes)
    return OutputProfile(**values)


def tool(**changes):
    values = {'name': 'ffmpeg', 'version': '6.1', 'build': 'test-build', 'executable': FFMPEG}
    values.update(changes)
    return ToolIdentity(**values)


def materialized(root):
    return MaterializedPaths(staging_root=str(root), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg')


def render_package(root, *, locals_, still_refs, segments, hook, voice_ms):
    record = validate_render_package_payload({
        'render_package_id': 'pkg-1', 'package_fingerprint': 'a' * 64, 'production_snapshot_ref': 'snap-1',
        'script_version_ref': 'script-1', 'production_plan_ref': 'plan-1', 'preset_revision_ref': 'preset-1',
        'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing', 'output_metadata_revision': 'meta-1',
        'output_profile_revision': 'profile-1', 'language_validation_refs': ['lang-1'],
        'input_artifacts': [artifact(ref, 'image/png') for ref in still_refs],
        'timeline': {'duration_ms': voice_ms, 'segments': segments}, 'hook_placement': hook,
        'subtitle_config': {'karaoke': True}, 'mix_plan': {}, 'allowed_fallbacks': [],
        'materialization_manifest': {ref: {'local_ref': local} for ref, local in locals_.items()},
        'output_path_ref': 'ref-output',
    })
    spec = build_render_command(record, preset(), profile(), 'ref-ass', tool(), materialized(root), voice_duration_ms=voice_ms)
    output = root / 'out' / 'attempt.mp4'
    done = run_process(build_final_argv(spec.argv, FFMPEG, 'libx264', str(output)))
    assert done.returncode == 0, done.stderr[-2000:]
    return record, spec, output


def make_stage(base):
    root = base / 'stage'
    for name in ('media', 'subs', 'out'):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / 'subs' / 'karaoke.ass').write_text(ASS_TEXT, encoding='utf-8')
    write_wav(root / 'media' / 'voice.wav', 3.0)
    write_wav(root / 'media' / 'hook.wav', 1.0)
    return root


@pytest.fixture(scope='module')
def world(tmp_path_factory):
    verify_ffmpeg_pin(pathlib.Path(FFMPEG), DEFAULT_LOCK_PATH)
    root = make_stage(tmp_path_factory.mktemp('fix6'))
    media = root / 'media'
    write_marked_png(media / 'scene.png', 1600, 900, 40, RED, BLUE)
    write_marked_png(media / 'hook.png', 1200, 630, 40, GREEN, PURPLE)
    write_marked_png(media / 'thumb.png', 900, 1200, 40, YELLOW, CYAN)
    locals_ = {'ref-scene': 'media/scene.png', 'ref-hook': 'media/hook.png', 'ref-thumb': 'media/thumb.png', 'ref-hook-a': 'media/hook.wav', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass'}
    hook = {'visual_hook_ref': 'ref-hook', 'audio_hook_ref': 'ref-hook-a', 'thumbnail_ref': 'ref-thumb', 'hook_time_range': {'start_ms': 0, 'end_ms': 1000}, 'thumbnail_time_range': {'start_ms': 400, 'end_ms': 800}}
    segments = [{'start_ms': 0, 'end_ms': 3000, 'visual_asset_refs': ['ref-scene']}]
    record, spec, output = render_package(root, locals_=locals_, still_refs=['ref-scene', 'ref-hook', 'ref-thumb'], segments=segments, hook=hook, voice_ms=3000)
    return SimpleNamespace(root=root, record=record, spec=spec, output=output, frames={})


def test_landscape_markers_stay_in_frame(world):
    for index in (31, 89):
        pixels = row_pixels(frame_of(world, index))
        red = run_start(pixels, RED)
        blue = run_start(pixels, BLUE)
        assert red is not None and red < W // 2, index
        assert blue is not None and blue > W // 2, index


def test_backdrop_is_blurred_and_darker(world):
    frame = frame_of(world, 45)
    step = max_step(frame, range(100, 500, 20))
    backdrop = band_mean(frame, 100, 500)
    picture = band_mean(frame, 800, 1100)
    warnings.warn(f'F10FIX6 backdrop_step={step} backdrop_mean={backdrop:.1f} picture_mean={picture:.1f}')
    assert step <= 16
    assert backdrop <= 0.75 * picture


def test_only_the_scene_moves(world):
    f1, f10 = frame_of(world, 1), frame_of(world, 10)
    f13, f23 = frame_of(world, 13), frame_of(world, 23)
    f31, f89 = frame_of(world, 31), frame_of(world, 89)
    assert mean_diff(f1, f10) <= 2.0
    assert mean_diff(f13, f23) <= 2.0
    assert mean_diff(f31, f89) > 4.0
    a = run_start(row_pixels(f31), RED)
    b = run_start(row_pixels(f89), RED)
    assert a is not None and b is not None and 8 <= a - b <= 40
    warnings.warn(f'F10FIX6 red_start_31={a} red_start_89={b} shift={a - b}')


def test_hook_and_thumbnail_gates_pass(world):
    p5 = row_pixels(frame_of(world, 5))
    assert run_start(p5, GREEN) is not None and run_start(p5, PURPLE) is not None
    p18 = row_pixels(frame_of(world, 18))
    assert run_start(p18, YELLOW) is not None and run_start(p18, CYAN) is not None
    settings = InspectorSettings(compare_width=90, compare_height=160, thumbnail_min_ssim=MIN_SIMILARITY, subtitle_band=Band(top=0.70, bottom=0.80), disclosure_band=Band(top=0.10, bottom=0.25), overlay_max_missing_share=0.25, max_subtitle_samples=4, timeout_seconds=120)
    inspector = RealOutputInspector(inputs=InspectionInputs(staging_root=world.root, ass_ref='ref-ass', segments=[]), settings=settings)
    evidence = inspector.inspect(str(world.output), world.record)
    policy = QualityPolicy(revision='f10-fix6', thresholds={'VISUAL_HOOK_PRESENT': {'min_similarity': MIN_SIMILARITY}})
    hook_gate = check_visual_hook_present(evidence, world.record, policy)
    thumb_gate = check_thumbnail_present(evidence, world.record, policy)
    warnings.warn(f'F10FIX6 hook_gate={hook_gate.status.name} thumbnail_gate={thumb_gate.status.name}')
    assert hook_gate.status is GateStatus.PASSED, hook_gate.reason
    assert thumb_gate.status is GateStatus.PASSED, thumb_gate.reason


def test_final_argv_keeps_the_chain(world):
    spec_graph = value_after(world.spec.argv, '-filter_complex')
    final = build_final_argv(world.spec.argv, FFMPEG, 'libx264', str(world.root / 'out' / 'other.mp4'))
    final_graph = value_after(final, '-filter_complex')
    for prefix in ('s0', 'vhook', 'vthumb'):
        assert render_command.frame_placement(W, H, prefix) in final_graph
    assert 'subtitles=filename=' in final_graph and 'ass=filename=' not in final_graph
    assert spec_graph.split(',ass=filename=')[0] == final_graph.split(',subtitles=filename=')[0]
    assert final_graph.count('split=2') == 3 and final_graph.count('perspective=') == 1
    assert 'force_original_aspect_ratio' not in final_graph


def test_portrait_cover_zoom_and_frame_count(tmp_path):
    root = make_stage(tmp_path)
    write_marked_png(root / 'media' / 'scene.png', 1080, 1920, 120)
    write_marked_png(root / 'media' / 'hook.png', 1080, 1920, 120)
    locals_ = {'ref-scene': 'media/scene.png', 'ref-hook': 'media/hook.png', 'ref-hook-a': 'media/hook.wav', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass'}
    hook = {'visual_hook_ref': 'ref-hook', 'audio_hook_ref': 'ref-hook-a', 'thumbnail_ref': 'ref-hook', 'hook_time_range': {'start_ms': 2500, 'end_ms': 3000}, 'thumbnail_time_range': {'start_ms': 2600, 'end_ms': 2800}}
    segments = [
        {'start_ms': 0, 'end_ms': 1234, 'visual_asset_refs': ['ref-scene']},
        {'start_ms': 1234, 'end_ms': 3000, 'visual_asset_refs': ['ref-scene']},
    ]
    record, spec, output = render_package(root, locals_=locals_, still_refs=['ref-scene', 'ref-hook'], segments=segments, hook=hook, voice_ms=3000)
    stream = probe(output)['streams'][0]
    assert int(stream['nb_read_frames']) == 90
    assert (stream['width'], stream['height']) == (1080, 1920)
    f10, f36, f37 = grab_frame(output, 10), grab_frame(output, 36), grab_frame(output, 37)
    e37 = edge_x(row_pixels(f37))
    assert abs(e37 - 119.5) <= 0.5
    shift = abs(edge_x(row_pixels(f10)) - edge_x(row_pixels(f36)))
    assert 10 <= shift <= 30
    warnings.warn(f'F10FIX6 frames={stream["nb_read_frames"]} edge37={e37:.2f} zoom_shift_10_36={shift:.2f}')
