"""F-09-FIX1: every ASS text line stays inside the safe area thanks to WrapStyle 0; rendered with the pinned FFmpeg, no mock, no database.

coveredIds: CT-SUB-001, CT-QC-001, CT-AI-004
"""
import pathlib
import subprocess

import pytest

from render.adapters.ass_manifest import build_ass_text
from render.adapters.postgres_plan_assets import ScriptSegmentInfo
from render.adapters.real_ffmpeg_renderer import build_final_argv, sha256_file
from render.domain.karaoke_plan import TimedWord
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.render_command import MaterializedPaths, OutputProfile, ToolIdentity, build_render_command

FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
PINNED_SHA = 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480'
SAFE_X_MIN = 55
SAFE_X_MAX = 1024
DEVIATION = 24
KARAOKE_SIZE = 72
DISCLOSURE_SIZE = 40
WIDTH = 1080
HEIGHT = 1920

TYPOGRAPHY = {
    'font_name': 'Arial', 'font_size': 72, 'primary_colour': '&H0000D4FF', 'secondary_colour': '&H00FFFFFF',
    'outline_colour': '&H00000000', 'back_colour': '&H80000000', 'bold': -1, 'italic': 0, 'underline': 0,
    'strike_out': 0, 'scale_x': 100, 'scale_y': 100, 'spacing': 0, 'angle': 0, 'border_style': 1,
    'outline': 4, 'shadow': 0, 'alignment': 2, 'encoding': 1,
}
SAFE_AREA = {'margin_left': 60, 'margin_right': 60, 'margin_vertical': 360}
LIMITS = {'max_words_per_line': 4, 'max_chars_per_line': 28, 'play_res_x': 1080, 'play_res_y': 1920}
DISCLOSURE_STYLE = {'font_size': 40, 'alignment': 8, 'margin_v': 240}

LINES = (
    'James Webb Space Telescope,',
    'Dense gas pockets resist',
    'Vatican aides deny rumors',
    'Pope Leo urges calm',
    'MOSCOW WARNS NATO MEMBERS',
    'Experts see slower growth',
)
WORDS = [TimedWord(w, i * 500, i * 500 + 500) for i, w in enumerate(' '.join(LINES).split())]
DISCLOSURES = {
    'seg-1': 'Astrophysical inference explaining how dense gas pockets temporarily withstand stellar erosion.',
    'seg-3': "Analytical assessment based on traditional Vatican neutrality standards and Pope Leo's vocal opposition to administration policies.",
    'seg-5': 'Analysis evaluating the shift in traditional papal neutrality based on Vatican statements.',
}
SEGMENTS = tuple(
    ScriptSegmentInfo(
        segment_id=f'seg-{i}',
        order=i,
        claim_mode='inference' if f'seg-{i}' in DISCLOSURES else 'source_backed',
        disclosure=DISCLOSURES.get(f'seg-{i}'),
        word_count=4,
    )
    for i in range(6)
)


def ass_text() -> str:
    return build_ass_text(WORDS, TYPOGRAPHY, SAFE_AREA, LIMITS, DISCLOSURE_STYLE, SEGMENTS)


def require_ffmpeg() -> None:
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)
    assert sha256_file(FFMPEG) == PINNED_SHA


def run_ffmpeg(*args):
    done = subprocess.run(
        [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
        capture_output=True, stdin=subprocess.DEVNULL, check=False, timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return done


def package():
    bg = {'artifact_version_id': 'ref-bg', 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': 'image/png'}
    segments = [
        {'start_ms': 0, 'end_ms': 6000, 'visual_asset_refs': ['ref-bg']},
        {'start_ms': 6000, 'end_ms': 12000, 'visual_asset_refs': ['ref-bg']},
    ]
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
        'timeline': {'duration_ms': 12000, 'segments': segments},
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
            'ref-ass': {'local_ref': 'subs/captions.ass'},
        },
        'output_path_ref': 'ref-output',
    })


@pytest.fixture(scope='module')
def world(tmp_path_factory):
    require_ffmpeg()
    staging = tmp_path_factory.mktemp('f09_fix1') / 'staging'
    for folder in ('media', 'subs', 'out'):
        (staging / folder).mkdir(parents=True)
    run_ffmpeg('-f', 'lavfi', '-i', 'color=c=gray:s=1080x1920:r=1', '-frames:v', '1', str(staging / 'media' / 'bg.png'))
    run_ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=1000:duration=12', '-c:a', 'pcm_s16le', str(staging / 'media' / 'voice.wav'))
    (staging / 'subs' / 'captions.ass').write_text(ass_text(), encoding='utf-8')
    section = {'note': 'x'}
    preset = build_preset_revision({
        'preset_key': 'p1', 'revision': 1, 'visual_rhythm': section, 'layout_rules': section,
        'thumbnail_overlay_style': section, 'typography_karaoke_style': section, 'hook_treatment': section,
        'mix_rules': section, 'color_effect_rules': section, 'output_profile_ref': 'profile-1',
        'fallback_constraints': section, 'compatibility_requirements': section,
    })
    tool = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=str(FFMPEG))
    paths = MaterializedPaths(staging_root=str(staging), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg')
    profile = OutputProfile(
        width=1080, height=1920, fps=30, video_codec='h264', audio_codec='aac', container='mp4',
        pixel_format='yuv420p', encoder='libx264', bitrate=None,
    )
    spec = build_render_command(package(), preset, profile, 'ref-ass', tool, paths)
    out = staging / 'out' / 'wrap.mp4'
    done = subprocess.run(
        build_final_argv(spec.argv, str(FFMPEG), 'libx264', str(out)),
        capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', timeout=120, check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return {'video': out, 'ass': ass_text()}


def frame(video, ms):
    done = run_ffmpeg('-ss', f'{ms / 1000}', '-i', str(video), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-')
    data = done.stdout
    assert len(data) == WIDTH * HEIGHT
    return data


def box(data, y_from, y_to):
    x_min = x_max = y_min = y_max = None
    for y in range(y_from, y_to):
        row = data[y * WIDTH:(y + 1) * WIDTH]
        xs = [x for x, v in enumerate(row) if abs(v - 128) > DEVIATION]
        if not xs:
            continue
        x_min = xs[0] if x_min is None else min(x_min, xs[0])
        x_max = xs[-1] if x_max is None else max(x_max, xs[-1])
        y_min = y if y_min is None else y_min
        y_max = y
    if x_min is None:
        return None
    return (x_min, x_max, y_min, y_max)


def rows(height, size):
    return max(1, round(height / (1.12 * size)))


def measure(world, name, ms, y_from, y_to, size):
    b = box(frame(world['video'], ms), y_from, y_to)
    assert b is not None
    print('F09FIX1 MEASURE', name, 'x', b[0], b[1], 'y', b[2], b[3], 'rows', rows(b[3] - b[2] + 1, size))
    return b


def test_header_has_wrap_style_0(world) -> None:
    lines = world['ass'].splitlines()
    assert 'WrapStyle: 0' in lines
    assert 'WrapStyle: 2' not in lines


def test_disclosure_dialogue_text_is_verbatim(world) -> None:
    lines = world['ass'].splitlines()
    disclosure_lines = [line for line in lines if line.startswith('Dialogue:') and ',Disclosure,' in line]
    assert [line.split(',,', 1)[1] for line in disclosure_lines] == [DISCLOSURES['seg-1'], DISCLOSURES['seg-3'], DISCLOSURES['seg-5']]


@pytest.mark.parametrize(('segment_id', 'ms'), [('seg-1', 3000), ('seg-3', 7000), ('seg-5', 11000)])
def test_disclosure_inside_safe_area(world, segment_id, ms) -> None:
    b = measure(world, segment_id, ms, 0, 960, DISCLOSURE_SIZE)
    assert SAFE_X_MIN <= b[0] and b[1] <= SAFE_X_MAX
    assert b[3] - b[2] + 1 > 1.5 * DISCLOSURE_SIZE


def test_wide_karaoke_line_wraps_inside_safe_area(world) -> None:
    assert len([line for line in world['ass'].splitlines() if line.startswith('Dialogue:') and ',Karaoke,' in line]) == 6
    b = measure(world, 'karaoke-wide', 9000, 960, 1920, KARAOKE_SIZE)
    assert SAFE_X_MIN <= b[0] and b[1] <= SAFE_X_MAX
    assert b[3] - b[2] + 1 > 1.5 * KARAOKE_SIZE


def test_fitting_karaoke_line_stays_on_one_row(world) -> None:
    b = measure(world, 'karaoke-fit', 1000, 960, 1920, KARAOKE_SIZE)
    assert SAFE_X_MIN <= b[0] and b[1] <= SAFE_X_MAX
    assert b[3] - b[2] + 1 <= 1.5 * KARAOKE_SIZE
