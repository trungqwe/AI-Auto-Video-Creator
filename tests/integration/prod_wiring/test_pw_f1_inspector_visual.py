"""PW-F1: RealOutputInspector measures the visual gates with the pinned FFmpeg on lavfi samples; no mock, no database.

coveredIds: PW-F1-01, CT-QC-001
"""
import dataclasses
import json
import pathlib
import subprocess
import pytest

from render.adapters.frame_probe import FrameProbe
from render.adapters.real_ffmpeg_renderer import FfmpegPinRejected, sha256_file
from render.adapters.real_output_inspector import Band, InspectionInputs, InspectorSettings, RealOutputInspector
from render.domain.content_gates import (
    check_inference_disclosure_present,
    check_karaoke_timing_valid,
    check_subtitle_burned_in,
    check_thumbnail_present,
    check_visual_hook_present,
)
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateStatus, QualityPolicy

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
    subtitle_min_difference=5.0,
    disclosure_band=Band(top=0.10, bottom=0.25),
    disclosure_min_difference=5.0,
    baseline_min_gap_ms=400,
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


def build_sample(
    root: pathlib.Path,
    *,
    background: str = 'testsrc',
    karaoke_boxes: bool = True,
    disclosure_box: bool = True,
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

    vf_filters = ['format=yuv420p']
    if karaoke_boxes:
        vf_filters.append("drawbox=x=10:y=230:w=160:h=20:color=white:t=fill:enable='between(t,1,2.5)'")
        vf_filters.append("drawbox=x=10:y=230:w=160:h=20:color=white:t=fill:enable='between(t,3,4)'")
    if disclosure_box:
        vf_filters.append("drawbox=x=10:y=45:w=160:h=20:color=white:t=fill:enable='between(t,4.5,5.5)'")
    vf = ','.join(vf_filters)

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

    package = validate_render_package_payload({
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
    sample = build_sample(tmp_path, karaoke_boxes=False)
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
    sample = build_sample(tmp_path, disclosure_box=False)
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


def test_pw_f1_thresholds_come_from_settings_not_code(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    settings = dataclasses.replace(SETTINGS, subtitle_min_difference=1000.0)
    evidence = inspect_sample(build_sample(tmp_path), SEGMENTS_INFERENCE, settings=settings)
    assert evidence.subtitle.frames_with_text == 0
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


def test_pw_f1_frame_probe_reads_duration_and_band_difference(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path)
    probe = FrameProbe(ffmpeg_path=FFMPEG)
    media = pathlib.Path(sample['output_ref'])
    duration = probe.duration_ms(media)
    assert duration is not None
    assert 5900 <= duration <= 6100
    diff_box = probe.band_difference(
        media,
        sample_ms=1750,
        baseline_ms=500,
        width=90,
        height=160,
        top=0.70,
        bottom=0.80,
    )
    assert diff_box is not None
    assert diff_box >= 5.0
    diff_base = probe.band_difference(
        media,
        sample_ms=500,
        baseline_ms=500,
        width=90,
        height=160,
        top=0.70,
        bottom=0.80,
    )
    assert diff_base is not None
    assert diff_base < 5.0


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
