"""PW-F2: audio, English output and output profile gates measured on the pinned FFmpeg; PostgreSQL stores the report.

coveredIds: PW-F2-01, CT-QC-001
"""
import dataclasses
import json
import pathlib
import subprocess
import pytest

from controlplane.infrastructure.db.uow import TransactionManager
from render.adapters.ffmpeg_capability import parse_encoders, parse_filters, read_tool_capability
from render.adapters.real_ffmpeg_renderer import FfmpegPinRejected, sha256_file
from render.adapters.real_ffprobe_probe import RealFfprobeProbe, measure_audio, measure_loudness
from render.adapters.real_output_inspector import (
    Band,
    InspectionInputs,
    InspectorSettings,
    LanguageSource,
    RealOutputInspector,
    audio_mix_result,
)
from render.domain.content_gates import (
    ExpectedLanguageRevisions,
    check_audio_hook_present,
    check_english_output_valid,
)
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import (
    GateName,
    GateResult as ReportGate,
    QualityPolicy,
    build_quality_report,
)
from render.domain.technical_gates import evaluate_technical_gates
from render.persistence import PostgresRenderUnitOfWork
from render.ports.repositories import KIND_QUALITY_REPORT

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
PINNED_SHA = 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480'
MIN_VOICE_LEVEL = -31.0

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
    revision='pw-f2-test',
    thresholds={
        'AUDIO_HOOK_PRESENT': {'min_level_db': -32.0},
        'VOICE_AUDIBLE': {'min_voice_level': MIN_VOICE_LEVEL},
        'DURATION_RANGE': {'duration_range_ms': [5000, 7000]},
        'ENGLISH_OUTPUT_VALID': {'required_language': 'en'},
        'AUDIO_MIX_QUALITY': {'target_lufs': -14.0},
    },
)

FLAT_POLICY = {
    'duration_range_ms': (5000, 7000),
    'min_voice_level': MIN_VOICE_LEVEL,
}

PROFILE = {
    'container': 'mp4',
    'video_codec': 'h264',
    'audio_codec': 'aac',
    'width': 1080,
    'height': 1920,
    'fps': 30,
}

EXPECTED = ExpectedLanguageRevisions(
    script_fingerprint='fp-script',
    voice_hash='h-voice',
    subtitle_text_hash='h-sub',
)

GOOD_LANGUAGE = LanguageSource(
    evidence_ref='lang-1',
    script_fingerprint='fp-script',
    voice_hash='h-voice',
    subtitle_text_hash='h-sub',
    voice_locale='en-US',
    subtitle_locale='en',
    script_locale='en',
    title_locale='en',
    hashtag_locale='en',
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


AUDIO_FILTERS = {
    'voice': "sine=frequency=440:sample_rate=48000,volume=0.5,volume=0:enable='not(between(t,0.2,2.5)+between(t,3,4))'",
    'quiet': "sine=frequency=440:sample_rate=48000,volume=0.001,volume=0:enable='not(between(t,0.2,2.5)+between(t,3,4))'",
    'silent': 'anullsrc=r=48000:cl=stereo',
}

ASS_TEXT = r"""[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.20,0:00:02.50,Karaoke,,0,0,0,,{\k100}@@A@@ {\k130}@@B@@
Dialogue: 0,0:00:03.00,0:00:04.00,Karaoke,,0,0,0,,{\k50}good {\k50}day
"""


def build_sample(
    root: pathlib.Path,
    *,
    audio: str = 'voice',
    size: str = '1080x1920',
    vcodec: str = 'libx264',
    words: tuple[str, str] = ('Hello', 'world'),
) -> dict:
    staging_root = root / 'staging'
    staging_subs = staging_root / 'subs'
    staging_media = staging_root / 'media'
    out_dir = root / 'out'
    staging_subs.mkdir(parents=True, exist_ok=True)
    staging_media.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    hook_path = staging_media / 'hook.png'
    ffmpeg('-f', 'lavfi', '-i', 'testsrc=s=180x320:r=1:d=1', '-frames:v', '1', str(hook_path))
    thumb_path = staging_media / 'thumb.png'
    thumb_path.write_bytes(hook_path.read_bytes())

    out_path = out_dir / 'final.mp4'
    cmd = ['-f', 'lavfi', '-i', f'testsrc=s={size}:r=30:d=6']
    if audio != 'none':
        cmd.extend(['-f', 'lavfi', '-i', AUDIO_FILTERS[audio]])
    cmd.extend(['-c:v', vcodec, '-pix_fmt', 'yuv420p', '-r', '30'])
    if vcodec == 'libx264':
        cmd.extend(['-preset', 'ultrafast'])
    if audio == 'none':
        cmd.append('-an')
    else:
        cmd.extend(['-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k', '-shortest'])
    cmd.extend(['-movflags', '+faststart', str(out_path)])
    ffmpeg(*cmd)

    ass_content = ASS_TEXT.replace('@@A@@', words[0]).replace('@@B@@', words[1])
    (staging_subs / 'captions.ass').write_text(ass_content, encoding='utf-8')

    package = validate_render_package_payload({
        'render_package_id': 'pkg-f2',
        'package_fingerprint': 'b' * 64,
        'production_snapshot_ref': 'snap',
        'script_version_ref': 'script',
        'production_plan_ref': 'plan',
        'preset_revision_ref': 'preset',
        'voice_artifact_ref': 'ref-voice',
        'word_timing_ref': 'ref-timing',
        'output_metadata_revision': 'meta-f2',
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


def run_gates(
    sample: dict,
    *,
    language: LanguageSource | None = GOOD_LANGUAGE,
    expected: ExpectedLanguageRevisions = EXPECTED,
    use_windows: bool = True,
) -> dict:
    inspector = RealOutputInspector(
        inputs=InspectionInputs(
            staging_root=sample['root'] / 'staging',
            ass_ref='ref-ass',
            segments=[],
            language=language,
        ),
        settings=SETTINGS,
        lock_path=LOCK_PATH,
    )
    windows = inspector.speech_windows(sample['package']) if use_windows else ()
    probe = RealFfprobeProbe(ffmpeg_path=FFMPEG, lock_path=LOCK_PATH, voice_windows=windows)
    technical = evaluate_technical_gates(
        probe,
        sample['output_ref'],
        policy=FLAT_POLICY,
        expected_profile=PROFILE,
        threshold_revision=POLICY.revision,
    )
    evidence = inspector.inspect(sample['output_ref'], sample['package'])
    return {
        'tech': {g.gate.value: g for g in technical},
        'audio_hook': check_audio_hook_present(evidence, sample['package'], POLICY),
        'english': check_english_output_valid(evidence, sample['package'], expected, POLICY),
        'evidence': evidence,
        'probe': probe,
        'inspector': inspector,
    }


def test_pw_f2_ffmpeg_is_the_pinned_binary() -> None:
    require_ffmpeg()
    assert sha256_file(FFMPEG) == PINNED_SHA
    with open(LOCK_PATH, encoding='utf-8') as f:
        lock_data = json.load(f)
    assert lock_data['pins']['ffmpeg']['sha256'] == PINNED_SHA


def test_pw_f2_probe_measures_audio_for_silent_quiet_and_voice(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    s_silent = build_sample(tmp_path / 'silent', audio='silent')
    s_quiet = build_sample(tmp_path / 'quiet', audio='quiet')
    s_voice = build_sample(tmp_path / 'voice', audio='voice')

    probe = RealFfprobeProbe(ffmpeg_path=FFMPEG, lock_path=LOCK_PATH)
    m_silent = probe.probe(s_silent['output_ref'])
    m_quiet = probe.probe(s_quiet['output_ref'])
    m_voice = probe.probe(s_voice['output_ref'])

    assert m_silent.audio_level is not None
    assert m_silent.severe_audio_errors == ()
    assert m_silent.has_audio_stream is True

    assert m_quiet.audio_level is not None
    assert m_quiet.severe_audio_errors == ()
    assert m_quiet.has_audio_stream is True

    assert m_voice.audio_level is not None
    assert m_voice.severe_audio_errors == ()
    assert m_voice.has_audio_stream is True

    assert m_silent.audio_level < m_quiet.audio_level < m_voice.audio_level
    assert m_silent.audio_level <= -60
    assert m_quiet.audio_level <= -40


def test_pw_f2_correct_sample_passes_audio_language_and_profile_gates(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    gates = run_gates(sample)
    tech = gates['tech']

    assert tech['FILE_PLAYABLE'].status.value == 'passed'
    assert tech['DURATION_RANGE'].status.value == 'passed'
    assert tech['VOICE_AUDIBLE'].status.value == 'passed'
    assert tech['OUTPUT_PROFILE_VALID'].status.value == 'passed'
    assert gates['audio_hook'].status.value == 'passed'
    assert gates['english'].status.value == 'passed'

    evidence = gates['evidence']
    assert evidence.audio_hook.start_ms == 0
    assert evidence.audio_hook.end_ms == 1000
    assert evidence.language.output_metadata_revision == 'meta-f2'
    assert evidence.language.subtitle_locale == 'en'


def test_pw_f2_silent_sample_fails_voice_and_audio_hook(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='silent')
    gates = run_gates(sample)
    tech = gates['tech']

    assert tech['VOICE_AUDIBLE'].status.value == 'failed'
    assert tech['VOICE_AUDIBLE'].reason == 'voice_below_min_level'
    assert tech['VOICE_AUDIBLE'].measured_value is not None

    assert gates['audio_hook'].status.value == 'failed'
    assert gates['audio_hook'].reason == 'audio_hook_level_below_threshold'


def test_pw_f2_quiet_voice_fails_voice_audible(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='quiet')
    gates = run_gates(sample)
    tech = gates['tech']

    assert tech['VOICE_AUDIBLE'].status.value == 'failed'
    assert tech['VOICE_AUDIBLE'].reason == 'voice_below_min_level'

    assert gates['audio_hook'].status.value == 'failed'
    assert gates['audio_hook'].reason == 'audio_hook_level_below_threshold'


def test_pw_f2_no_audio_stream_fails_with_named_reasons(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='none')
    gates = run_gates(sample)
    tech = gates['tech']

    assert tech['VOICE_AUDIBLE'].status.value == 'failed'
    assert tech['VOICE_AUDIBLE'].reason == 'no_audio_stream'

    assert gates['audio_hook'].status.value == 'failed'
    assert gates['audio_hook'].reason == 'audio_hook_not_observed'
    assert gates['evidence'].audio_hook is None


def test_pw_f2_voice_level_is_measured_over_spoken_windows_only(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    gates_windows = run_gates(sample, use_windows=True)
    gates_whole = run_gates(sample, use_windows=False)

    assert gates_windows['tech']['VOICE_AUDIBLE'].status.value == 'passed'
    assert gates_whole['tech']['VOICE_AUDIBLE'].status.value == 'failed'
    assert gates_whole['tech']['VOICE_AUDIBLE'].reason == 'voice_below_min_level'

    level_windows = gates_windows['tech']['VOICE_AUDIBLE'].measured_value
    level_whole = gates_whole['tech']['VOICE_AUDIBLE'].measured_value
    assert level_windows - level_whole >= 1.0


def test_pw_f2_audio_level_none_never_passes(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    probe = RealFfprobeProbe()
    m = probe.probe(sample['output_ref'])
    assert m.audio_level is None
    assert m.severe_audio_errors is None

    technical = evaluate_technical_gates(
        probe,
        sample['output_ref'],
        policy=FLAT_POLICY,
        expected_profile=PROFILE,
        threshold_revision=POLICY.revision,
    )
    tech = {g.gate.value: g for g in technical}
    assert tech['VOICE_AUDIBLE'].status.value == 'failed'
    assert tech['VOICE_AUDIBLE'].reason == 'missing_measurement'


def test_pw_f2_unpinned_ffmpeg_is_refused(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    bad = tmp_path / 'bad.lock.json'
    bad.write_text(
        json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': '0' * 64}}}),
        encoding='utf-8',
    )
    with pytest.raises(FfmpegPinRejected):
        RealFfprobeProbe(ffmpeg_path=FFMPEG, lock_path=bad).probe(sample['output_ref'])
    with pytest.raises(FfmpegPinRejected):
        read_tool_capability(ffmpeg_path=FFMPEG, lock_path=bad)


def test_pw_f2_wrong_voice_language_fails_english_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    lang = dataclasses.replace(GOOD_LANGUAGE, voice_locale='vi')
    gates = run_gates(sample, language=lang)
    assert gates['english'].status.value == 'failed'
    assert gates['english'].reason == 'language_mismatch:voice_locale'
    assert gates['tech']['VOICE_AUDIBLE'].status.value == 'passed'
    assert gates['audio_hook'].status.value == 'passed'


def test_pw_f2_non_latin_subtitle_fails_english_gate(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice', words=('Привет', 'мир'))
    gates = run_gates(sample)
    assert gates['evidence'].language.subtitle_locale == 'und'
    assert gates['english'].status.value == 'failed'
    assert gates['english'].reason == 'language_mismatch:subtitle_locale'


def test_pw_f2_title_locale_from_d_is_checked(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    lang = dataclasses.replace(GOOD_LANGUAGE, title_locale='es')
    gates = run_gates(sample, language=lang)
    assert gates['english'].status.value == 'failed'
    assert gates['english'].reason == 'language_mismatch:title_locale'


def test_pw_f2_missing_language_source_or_stale_hash_fails(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    gates_none = run_gates(sample, language=None)
    assert gates_none['evidence'].language is None
    assert gates_none['english'].status.value == 'failed'
    assert gates_none['english'].reason == 'language_evidence_missing'

    bad_expected = ExpectedLanguageRevisions(
        script_fingerprint='fp-script',
        voice_hash='h-voice',
        subtitle_text_hash='h-other',
    )
    gates_mismatch = run_gates(sample, language=GOOD_LANGUAGE, expected=bad_expected)
    assert gates_mismatch['english'].status.value == 'failed'
    assert gates_mismatch['english'].reason == 'language_evidence_revision_mismatch:subtitle_text_hash'


def test_pw_f2_wrong_resolution_fails_output_profile(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice', size='720x1280')
    gates = run_gates(sample)
    tech = gates['tech']
    assert tech['OUTPUT_PROFILE_VALID'].status.value == 'failed'
    assert tech['OUTPUT_PROFILE_VALID'].reason == 'profile_mismatch:width,height'
    assert tech['FILE_PLAYABLE'].status.value == 'passed'


def test_pw_f2_wrong_codec_fails_output_profile(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice', vcodec='mpeg4')
    gates = run_gates(sample)
    tech = gates['tech']
    assert tech['OUTPUT_PROFILE_VALID'].status.value == 'failed'
    assert tech['OUTPUT_PROFILE_VALID'].reason == 'profile_mismatch:video_codec'


def test_pw_f2_loudness_off_target_is_only_a_warning(tmp_path: pathlib.Path) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    stats = measure_loudness(FFMPEG, pathlib.Path(sample['output_ref']))
    assert stats.integrated_lufs is not None
    assert stats.true_peak_dbtp is not None

    result = audio_mix_result(
        stats,
        target_lufs=-14.0,
        tolerance_lu=0.5,
        max_true_peak_dbtp=-1.0,
        threshold_revision='pw-f2-test',
        evidence_ref='AUDIO_MIX:final.mp4',
    )
    assert result.gate is GateName.AUDIO_MIX_QUALITY
    assert result.status.value == 'failed'
    assert result.reason is not None and 'loudness_out_of_target' in result.reason

    report = build_quality_report([result], policy=POLICY)
    assert GateName.AUDIO_MIX_QUALITY not in report.blocking_gates

    pass_result = audio_mix_result(
        stats,
        target_lufs=stats.integrated_lufs,
        tolerance_lu=0.5,
        max_true_peak_dbtp=stats.true_peak_dbtp + 1.0,
        threshold_revision='pw-f2-test',
        evidence_ref='AUDIO_MIX:final.mp4',
    )
    assert pass_result.status.value == 'passed'


def test_pw_f2_tool_capability_comes_from_the_pinned_ffmpeg() -> None:
    require_ffmpeg()
    capability = read_tool_capability(ffmpeg_path=FFMPEG, lock_path=LOCK_PATH)
    assert capability is not None
    assert {'subtitles', 'loudnorm', 'libass'} <= capability.filters
    assert {'libx264', 'h264_nvenc', 'aac'} <= capability.encoders
    assert 'zz_not_an_encoder' not in capability.encoders
    assert 'libx264' not in capability.filters

    assert parse_encoders(' V....D mpeg4                MPEG-4 part 2\n A....D aac                  AAC\n') == frozenset({'mpeg4', 'aac'})
    assert parse_filters(' T. loudnorm         A->A       EBU R128\n .. testsrc          |->V       Generate test pattern.\n') == frozenset({'loudnorm', 'testsrc'})
    assert parse_filters('Filters:\n  T. = Timeline support\n  .S = Slice threading\n  A = Audio input/output\n  | = Source or sink filter\n TS aap               AA->A      Apply Affine Projection algorithm to first audio stream.\n') == frozenset({'aap'})


def test_pw_f2_report_is_stored_in_postgres(tmp_path: pathlib.Path, pw_database) -> None:
    require_ffmpeg()
    sample = build_sample(tmp_path, audio='voice')
    gates = run_gates(sample)
    tech = gates['tech']
    results = [
        ReportGate(
            gate=item.gate.value,
            status=item.status.value,
            evidence_ref=item.evidence_ref,
            measured_value=item.measured_value,
            threshold_revision=item.threshold_revision,
            reason=item.reason,
        )
        for item in tech.values()
    ]
    results.extend([gates['audio_hook'], gates['english']])
    report = build_quality_report(results, policy=POLICY)

    assert all(
        g.status.value == 'passed'
        for g in report.gates
        if g.gate.value in {
            'AUDIO_HOOK_PRESENT',
            'VOICE_AUDIBLE',
            'ENGLISH_OUTPUT_VALID',
            'OUTPUT_PROFILE_VALID',
            'FILE_PLAYABLE',
            'DURATION_RANGE',
        }
    )
    assert report.passed is False

    manager = TransactionManager(pw_database.dsn, pool_max_size=2)
    try:
        with PostgresRenderUnitOfWork(manager, workspace_id=pw_database.workspace_id, correlation_id='corr-pw-f2', actor='pw-f2') as uow:
            uow.renders.append(KIND_QUALITY_REPORT, 'qr-pw-f2', 1, report)
            uow.commit()

        with PostgresRenderUnitOfWork(manager, workspace_id=pw_database.workspace_id, correlation_id='corr-pw-f2', actor='pw-f2') as uow:
            latest = uow.renders.latest(KIND_QUALITY_REPORT, 'qr-pw-f2')
            assert latest is not None
            assert latest.record == report
            assert latest.record.passed is False
    finally:
        manager.close()
