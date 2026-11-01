"""F-10-FIX5: nền nhạc của PrepareAudioBed được trộn vào mp4 dưới giọng đúng audio.bed_gain_db so với giọng, trước loudnorm hai lượt.

Postgres thật, FFmpeg ghim, không vá hàm nào; chỉ tiêm transport nhạc và cổng grant. Giọng có khoảng nghỉ do FFmpeg sinh, MP3 nhạc sinh tại chỗ bằng libmp3lame.

coveredIds: CT-RND-002, CT-AUD-001, FR-AUD-006
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re
import subprocess
import warnings
from types import SimpleNamespace

import pytest

FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300, check=False)


def run_ffmpeg(args: list[str]) -> None:
    done = _run([str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', *args])
    assert done.returncode == 0, done.stderr


def make_mp3(path: pathlib.Path, lavfi: str, seconds: int = 40, volume: float = 0.3) -> bytes:
    run_ffmpeg(['-f', 'lavfi', '-i', lavfi, '-t', str(seconds), '-af', f'volume={volume}', '-c:a', 'libmp3lame', '-b:a', '128k', str(path)])
    return path.read_bytes()


def make_wav(path: pathlib.Path, lavfi: str, seconds: float, af: str = 'anull') -> bytes:
    run_ffmpeg(['-f', 'lavfi', '-i', lavfi, '-t', str(seconds), '-af', af, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', str(path)])
    return path.read_bytes()


def make_voice(path: pathlib.Path, seconds: float) -> bytes:
    """Lời 2,5 s rồi nghỉ 1,5 s im lặng tuyệt đối, chu kỳ 4 s."""
    return make_wav(path, 'sine=frequency=220:sample_rate=48000', seconds, af="volume='if(lt(mod(t,4),2.5),0.3,0)':eval=frame")


def make_clip(path: pathlib.Path, seconds: float) -> None:
    run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=size=540x960:rate=30', '-t', str(seconds), '-pix_fmt', 'yuv420p', '-c:v', 'libx264', str(path)])


def _ebur128(path: pathlib.Path, prefix: str) -> str:
    done = _run([str(FFMPEG), '-hide_banner', '-nostdin', '-nostats', '-i', str(path), '-map', '0:a:0', '-vn', '-af', f'{prefix}ebur128=peak=true:framelog=quiet', '-f', 'null', '-'])
    assert done.returncode == 0, done.stderr
    return done.stderr.rsplit('Summary:', 1)[1]


def _level(match: re.Match | None) -> float:
    assert match is not None
    return -70.0 if match.group(1) == '-inf' else float(match.group(1))


def window_lufs(path: pathlib.Path, start_s: float, end_s: float) -> float:
    summary = _ebur128(path, f'atrim=start={start_s}:end={end_s},asetpts=N/SR/TB,')
    return _level(re.search(r'I:\s+(-?[0-9.]+|-inf) LUFS', summary))


def file_lufs_tp(path: pathlib.Path) -> tuple[float, float]:
    summary = _ebur128(path, '')
    return _level(re.search(r'I:\s+(-?[0-9.]+|-inf) LUFS', summary)), _level(re.search(r'Peak:\s+(-?[0-9.]+|-inf) dBFS', summary))


def video_md5(path: pathlib.Path) -> str:
    done = _run([str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:v:0', '-f', 'md5', '-'])
    assert done.returncode == 0, done.stderr
    return done.stdout.strip().split('MD5=', 1)[1]


from catalog.domain.hooks import HookKind
from controlplane.api.wiring.production_profile import WiringConfig, load_production_profile
from controlplane.api.wiring.render import ProductionRenderSources
from controlplane.api.wiring.voice import build_voice_services, voice_activity_handlers
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.infrastructure.db.uow import TransactionManager
from render.adapters.activity_inputs import ActivityInputError
from render.adapters.config_render_sources import PRESET_SCOPE_KIND
from render.adapters.postgres_plan_assets import PostgresPlanAssets
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe
from render.domain.package_contract import MISSING_REQUIRED
from render.domain.render_command import MaterializedPaths, RenderCommandRejected, ToolIdentity, build_render_command
from render.domain.resolve_package import ResolveError, resolve_render_package
from render.domain.validate_package import validate_render_package
from render.ports.lease import GpuLease
from render.ports.renderer import RendererStatus
from tests.integration.prod_wiring.test_pw_f3_render_inputs import (  # noqa: F401
    AUDIO_HOOK_ID,
    NOW,
    PLAN_ID,
    SCRIPT_ID,
    TIMING_REF,
    VISUAL_HOOK_ID,
    creative_plan,
    edit,
    insert_plan,
    insert_script,
    manager,
    pinned,
    render_runtime,
    script_segments_payload,
    seed_hook,
    service,
    stage_and_register,
    timing_payload,
)
from voice.adapters.audio_bed_source import HttpsResponse, MusicSource
from voice.domain.voice_track import VoiceTrack
from voice.persistence import PostgresVoiceUnitOfWork

VOICE_MS = 14000
BED_JOB = 'job-f5'
BED_STAGE_RUN = 'job-f5:process:r1'
BED_PLAN = 'plan-f5-bed'
BED_KEY = 'f5:bed'
URL_A = 'https://music-a.test/a.mp3'
URL_B = 'https://music-b.test/b.mp3'


@pytest.fixture
def bed_world(pw_database, manager, pinned, service, tmp_path):
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)
    db = pw_database
    runtime = dataclasses.replace(render_runtime(tmp_path), ffmpeg_path=FFMPEG, ffprobe_path=FFMPEG.with_name('ffprobe.exe'), runtime_lock_path=LOCK_PATH)
    work = tmp_path / 'work'
    work.mkdir()
    make_clip(work / 'v1.mp4', 2)
    make_clip(work / 'v2.mp4', 2)
    hook_video = work / 'hook.mp4'
    make_clip(hook_video, 2)
    hook_video_bytes = hook_video.read_bytes()
    hook_audio_bytes = make_wav(work / 'hook.wav', 'sine=frequency=880:sample_rate=48000', 2, af='volume=0.05')
    voice_bytes = make_voice(work / 'voice.wav', 14)
    voice_ref = 'voice-artifact-' + sha(voice_bytes)
    v1 = stage_and_register(manager, db, runtime, 'media/f5-visual-1.mp4', (work / 'v1.mp4').read_bytes())
    v2 = stage_and_register(manager, db, runtime, 'media/f5-visual-2.mp4', (work / 'v2.mp4').read_bytes())
    voice_version = stage_and_register(manager, db, runtime, 'voice/' + voice_ref, voice_bytes)
    stage_and_register(manager, db, runtime, f'media/{sha(hook_video_bytes)}.mp4', hook_video_bytes)
    stage_and_register(manager, db, runtime, f'media/{sha(hook_audio_bytes)}.wav', hook_audio_bytes)
    seed_hook(manager, db, VISUAL_HOOK_ID, HookKind.VISUAL_HOOK, sha(hook_video_bytes))
    seed_hook(manager, db, AUDIO_HOOK_ID, HookKind.AUDIO_HOOK, sha(hook_audio_bytes))
    insert_script(db, script_segments_payload(['source_backed', 'source_backed'], [4, 4]))
    plan_payload = creative_plan(db, pinned, v1.artifact_version_id, v2.artifact_version_id).to_payload()
    insert_plan(db, plan_payload)
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_word_timings (workspace_id, record_key, revision, payload, timing_artifact_ref) VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (db.workspace_id, TIMING_REF, json.dumps({**timing_payload(), 'voice_duration_ms': VOICE_MS}), TIMING_REF),
        )
    profile = load_production_profile(PROFILE_PATH)
    sources = ProductionRenderSources(manager=manager, workspace_id=db.workspace_id, profile=profile, runtime=runtime, clock=lambda: NOW)
    plan_port = PostgresPlanAssets(manager, workspace_id=db.workspace_id)
    refs = [
        {'ref_type': 'production_plan', 'ref_id': PLAN_ID},
        {'ref_type': 'script_version', 'ref_id': SCRIPT_ID},
        {'ref_type': 'word_timing', 'ref_id': TIMING_REF},
        {'ref_type': 'voice_artifact', 'ref_id': voice_ref},
        {'ref_type': 'artifact_version', 'ref_id': voice_version.artifact_version_id, 'source_ref_id': 'voice/' + voice_ref},
        {'ref_type': 'artifact_version', 'ref_id': v1.artifact_version_id, 'source_ref_id': 'media/f5-visual-1.mp4'},
        {'ref_type': 'artifact_version', 'ref_id': v2.artifact_version_id, 'source_ref_id': 'media/f5-visual-2.mp4'},
        {'ref_type': 'output_path', 'ref_id': 'out-f5'},
        {'ref_type': 'production_snapshot', 'ref_id': 'snap-f5'},
        {'ref_type': 'output_metadata', 'ref_id': 'meta-f5'},
    ]
    hook_end_ms = plan_payload['hook_placement']['hook_time_range']['end_ms']
    if hook_end_ms > 3700:
        pytest.fail(f'BLOCKED: hook_end_ms={hook_end_ms} exceeds 3700; measurement windows assume the hook ends before 3.7 s', pytrace=False)
    return SimpleNamespace(
        db=db, manager=manager, service=service, runtime=runtime, profile=profile, sources=sources, plan_port=plan_port, refs=refs,
        voice_bytes=voice_bytes, voice_ms=VOICE_MS, voice_version=voice_version, voice_ref=voice_ref, hook_end_ms=hook_end_ms, work=work,
    )


class RecordingTransport:
    def __init__(self, bodies: dict) -> None:
        self.bodies = bodies
        self.calls: list[str] = []

    def fetch(self, url, *, max_bytes, timeout_seconds):
        self.calls.append(url)
        if url not in self.bodies:
            raise OSError('unreachable')
        return HttpsResponse(200, self.bodies[url], url)


def make_source(role: str, url: str, data: bytes, moods) -> MusicSource:
    return MusicSource(source_id=f'{role}-test', role=role, url=url, license='CC BY 4.0', attribution='Test Track by Tester', author='Tester', sha256=sha(data), moods=tuple(moods))


@pytest.fixture
def bed_result(bed_world):
    world = bed_world
    db, ws = world.db, world.db.workspace_id
    mp3_a = make_mp3(world.work / 'a.mp3', 'sine=frequency=523:sample_rate=44100', volume=0.5)
    mp3_b = make_mp3(world.work / 'b.mp3', 'sine=frequency=659:sample_rate=44100', volume=0.05)
    sources = (make_source('primary', URL_A, mp3_a, ('calm',)), make_source('fallback', URL_B, mp3_b, ('tense',)))
    transport = RecordingTransport({URL_A: mp3_a, URL_B: mp3_b})
    voice = VoiceTrack(
        voice_artifact_ref=world.voice_ref, script_version_id='sv-f5', script_fingerprint='c' * 64, voice_hash=sha(world.voice_bytes),
        actual_duration_ms=VOICE_MS, provider_model_voice_revision='kokoro-v1.0', usage_metrics={}, warnings=(), receipt_ref='receipt-f5',
    )
    with PostgresVoiceUnitOfWork(world.manager, workspace_id=ws) as uow:
        uow.outputs.append('voice', f'track:{BED_JOB}', 1, voice)
        uow.commit()
    payload = {
        'music_cues': [
            {'start_ms': 0, 'end_ms': 8000, 'mood': 'calm', 'artifact_ref': 'music-calm'},
            {'start_ms': 8000, 'end_ms': 14000, 'mood': 'tense', 'artifact_ref': 'music-tense'},
        ],
        'sfx_cues': [{'start_ms': 8000, 'end_ms': 14000, 'artifact_ref': 'sfx-1'}],
    }
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_plans (workspace_id, record_key, revision, payload, production_plan_id) VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (ws, BED_PLAN, json.dumps(payload), BED_PLAN),
        )
    services = build_voice_services(world.manager, WiringConfig(mode='production', workspace_id=ws, profile=world.profile, runtime=world.runtime))
    handlers = voice_activity_handlers(
        services, manager=world.manager, workspace_id=ws, profile=world.profile, runtime=world.runtime,
        grants=SimpleNamespace(is_grant_current=lambda grant: True), clock=lambda: NOW, music_sources=sources, music_transport=transport,
    )
    request = {
        'workflow_id': 'wf-f5', 'workflow_run_id': 'run-f5', 'stage_run_id': BED_STAGE_RUN, 'activity_name': 'PrepareAudioBed',
        'activity_version': '1', 'input_refs': [{'ref_type': 'production_plan', 'ref_id': BED_PLAN}], 'operation_key': BED_KEY,
        'capability_requirements': {'task_queue': 'desktop_cpu'}, 'retry_policy_ref': 'retry-1', 'video_job_id': BED_JOB,
    }
    claims = GrantClaims('op-f5', BED_STAGE_RUN, 1, '0', 'lease-f5', '2026-11-01T00:00:00Z', '2026-11-01T02:00:00Z', 'PrepareAudioBed', 'fp-f5')
    return SimpleNamespace(
        result=handlers['PrepareAudioBed'](request, claims), key=BED_KEY, services=services, handlers=handlers, request=request, claims=claims,
        sources=sources, transport=transport,
    )


def test_prepare_audio_bed_handler_adds_one_cue_ref_per_cue(bed_world, bed_result):
    result = bed_result.result
    assert result['disposition'] == 'succeeded', result
    refs = result['output_refs']
    assert any(ref['ref_type'] == 'media_artifact' for ref in refs)
    cues = [ref for ref in refs if ref['ref_type'] == 'audio_bed_cue']
    assert len(cues) == 3
    spans = [(0, 8000), (8000, 14000), (8000, 14000)]
    for index, (cue, (start, end)) in enumerate(zip(cues, spans)):
        assert cue['ref_id'] == f'{BED_KEY}#{index}'
        assert cue['start_ms'] == str(start) and cue['end_ms'] == str(end)
    assert all(cue['rendition_ref'].startswith('music-') for cue in cues[:2])
    assert cues[2]['rendition_ref'].startswith('bed-none-')
    for cue in cues[:2]:
        assert cue['staged_ref'] == f"audio_library/{cue['rendition_ref']}.audio"
        assert (bed_world.runtime.staging_root / cue['staged_ref']).is_file()


def cue_refs(bed_result) -> list[dict]:
    return [ref for ref in bed_result.result['output_refs'] if ref['ref_type'] == 'audio_bed_cue']


def bed_input_refs(bed_world, bed_result) -> list[dict]:
    return [*bed_world.refs, *bed_result.result['output_refs']]


def render_mp4(world, refs, name):
    inputs = world.sources.resolve_inputs(refs)
    record = resolve_render_package(inputs, world.plan_port)
    report = validate_render_package(record, world.sources.validation_context(record))
    assert report.passed is True, report.findings
    plan = world.sources.render_plan(record, f'render:{name}:1')
    (world.runtime.staging_root / 'out').mkdir(exist_ok=True)
    outcome = RealFfmpegRenderer(ffmpeg_path=str(FFMPEG), lock_path=LOCK_PATH, timeout_seconds=600).run(plan.command_spec, lease=GpuLease(lease_id='lease-f5', owner_ref='f10-fix5'))
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    return record, pathlib.Path(outcome.output_ref)


def test_audio_bed_is_mixed_under_the_voice_at_the_approved_gain(bed_world, bed_result):
    world = bed_world
    record_bed, bed_mp4 = render_mp4(world, bed_input_refs(world, bed_result), 'bed')
    record_old, old_mp4 = render_mp4(world, world.refs, 'old')
    bed_gain = world.profile.parameters['audio.bed_gain_db']
    assert not record_old.mix_plan
    plan = record_bed.mix_plan
    assert [(bed['start_ms'], bed['end_ms']) for bed in plan['beds']] == [(0, 8000), (8000, 14000)]
    assert plan['bed_gain_db'] == bed_gain
    voice_lufs = file_lufs_tp(world.runtime.staging_root / world.voice_version.artifact_version_id)[0]
    for bed in plan['beds']:
        rendition = file_lufs_tp(world.runtime.staging_root / f"{bed['rendition_ref']}.wav")[0]
        assert abs(bed['gain_db'] - (bed_gain + voice_lufs - rendition)) <= 0.15
    loud, peak = file_lufs_tp(bed_mp4)
    assert abs(loud - world.profile.parameters['audio.loudness']['integrated_lufs']) <= 1.5
    assert peak <= -1.5
    duration = RealFfprobeProbe(ffprobe_path=str(FFMPEG.with_name('ffprobe.exe'))).probe(str(bed_mp4)).duration_ms
    assert abs(duration - world.voice_ms) <= 50
    assert video_md5(bed_mp4) == video_md5(old_mp4)
    speech, gap, delta = [], [], []
    for (s0, s1), (g0, g1) in (((4.3, 6.2), (6.8, 7.7)), ((8.3, 10.2), (10.8, 11.7))):
        speech.append(window_lufs(bed_mp4, s0, s1))
        gap.append(window_lufs(bed_mp4, g0, g1))
        delta.append(speech[-1] - gap[-1])
        assert abs(delta[-1] + bed_gain) <= 1.0, (speech, gap)
    old_gaps = [window_lufs(old_mp4, 6.8, 7.7), window_lufs(old_mp4, 10.8, 11.7)]
    assert all(level <= -70.0 for level in old_gaps), old_gaps
    warnings.warn(f'f10-fix5 measurements: mp4 I={loud} TP={peak} speech={speech} gap={gap} delta={delta} old_gap={old_gaps} duration_ms={duration} beds={plan["beds"]} voice_lufs={plan["voice_integrated_lufs"]} old_I_TP={file_lufs_tp(old_mp4)}')


def test_cue_refs_survive_the_flow_dedup_by_ref_type_and_ref_id(bed_result):
    refs = bed_result.result['output_refs']
    assert len({(ref['ref_type'], ref['ref_id']) for ref in refs}) == len(refs)


# --- ca lỗi của resolve_inputs ---


def resolve_with(world, cues):
    return world.sources.resolve_inputs([*world.refs, *cues])


def first_music_cue(bed_result) -> dict:
    return next(cue for cue in cue_refs(bed_result) if cue['rendition_ref'].startswith('music-'))


@pytest.mark.parametrize('change', [
    {'start_ms': 'abc'},
    {'start_ms': '5', 'end_ms': '5'},
    {'start_ms': '9', 'end_ms': '4'},
    {'start_ms': 5},
    {'rendition_ref': 'music-xyz'},
    {'rendition_ref': 'bed-none-short'},
])
def test_malformed_cue_ref_is_invalid_input(bed_world, bed_result, change):
    cue = {**first_music_cue(bed_result), **change}
    with pytest.raises(ActivityInputError) as info:
        resolve_with(bed_world, [cue])
    assert info.value.code == 'INVALID_INPUT'


def _drop_staged(cue, world):
    return {key: value for key, value in cue.items() if key != 'staged_ref'}


def _escape_staged(cue, world):
    return {**cue, 'staged_ref': '../x'}


def _tamper_staged(cue, world):
    root = world.runtime.staging_root
    (root / f"{cue['rendition_ref']}.wav").unlink(missing_ok=True)
    with (root / cue['staged_ref']).open('ab') as stream:
        stream.write(b'\0')
    return cue


def _silent_rendition(cue, world):
    data = make_wav(world.work / 'silent.wav', 'anullsrc=r=48000:cl=mono', 3)
    ref = f'music-{sha(data)}'
    library = world.runtime.staging_root / 'audio_library'
    library.mkdir(parents=True, exist_ok=True)
    (library / f'{ref}.audio').write_bytes(data)
    return {**cue, 'rendition_ref': ref, 'staged_ref': f'audio_library/{ref}.audio'}


@pytest.mark.parametrize('mutate', [_drop_staged, _escape_staged, _tamper_staged, _silent_rendition])
def test_unusable_rendition_is_input_not_ready(bed_world, bed_result, mutate):
    cue = mutate(dict(first_music_cue(bed_result)), bed_world)
    with pytest.raises(ActivityInputError) as info:
        resolve_with(bed_world, [cue])
    assert info.value.code == 'INPUT_NOT_READY'
    assert 'audio_bed_not_ready:' + cue['rendition_ref'] in str(info.value)


def test_bed_gain_missing_is_input_not_ready(bed_world, bed_result):
    def change(payload):
        payload['mix_rules']['bed_gain_db'] = 'x'
        return payload

    edit(bed_world.service, bed_world.db, PRESET_SCOPE_KIND, 'bold-yellow', change)
    with pytest.raises(ActivityInputError) as info:
        resolve_with(bed_world, cue_refs(bed_result))
    assert info.value.code == 'INPUT_NOT_READY'
    assert 'bed_gain_db' in str(info.value)


def test_no_cue_refs_and_bed_none_only_keep_the_old_mix_plan(bed_world):
    plain = bed_world.sources.resolve_inputs(bed_world.refs)
    assert not plain.mix_plan
    silent = {'ref_type': 'audio_bed_cue', 'ref_id': 'f5:none#0', 'rendition_ref': 'bed-none-' + '0' * 64, 'start_ms': '0', 'end_ms': '4000'}
    quiet = resolve_with(bed_world, [silent])
    assert not quiet.mix_plan
    assert tuple(quiet.input_artifacts) == tuple(plain.input_artifacts)


def test_flat_copy_is_reused_when_intact_and_replaced_when_wrong(bed_world, bed_result):
    cue = first_music_cue(bed_result)
    flat = bed_world.runtime.staging_root / f"{cue['rendition_ref']}.wav"
    resolve_with(bed_world, [cue])
    first = flat.stat().st_mtime_ns
    resolve_with(bed_world, [cue])
    assert flat.stat().st_mtime_ns == first
    flat.write_bytes(b'not the rendition')
    resolve_with(bed_world, [cue])
    assert sha(flat.read_bytes()) == cue['rendition_ref'][len('music-'):]


def test_render_does_not_touch_the_audio_library(bed_world, bed_result):
    library = bed_world.runtime.staging_root / 'audio_library'

    def snapshot():
        return sorted((item.name, item.stat().st_size, item.stat().st_mtime_ns) for item in library.iterdir())

    before = snapshot()
    resolve_with(bed_world, cue_refs(bed_result))
    assert snapshot() == before


# --- quy tắc cửa sổ, asset, lệnh ---


def stage_rendition(world, seconds, frequency):
    data = make_wav(world.work / f'r-{frequency}.wav', f'sine=frequency={frequency}:sample_rate=48000', seconds, af='volume=0.2')
    digest = sha(data)
    target = world.runtime.staging_root / 'audio_library' / f'music-{digest}.audio'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return f'music-{digest}', f'audio_library/music-{digest}.audio'


def cue(ref, staged, start, end, index):
    return {'ref_type': 'audio_bed_cue', 'ref_id': f'f5:win#{index}', 'rendition_ref': ref, 'start_ms': str(start), 'end_ms': str(end), 'staged_ref': staged}


def beds_of(world, cues):
    return [(bed['rendition_ref'], bed['start_ms'], bed['end_ms']) for bed in resolve_with(world, cues).mix_plan['beds']]


def test_bed_windows_follow_the_join_and_overlap_rules(bed_world):
    r1, s1 = stage_rendition(bed_world, 8, 220)
    r2, s2 = stage_rendition(bed_world, 5, 330)
    assert beds_of(bed_world, [cue(r1, s1, 0, 3000, 0), cue(r1, s1, 3000, 6000, 1)]) == [(r1, 0, 6000)]
    assert beds_of(bed_world, [cue(r1, s1, 0, 4000, 0), cue(r1, s1, 3000, 7000, 1)]) == [(r1, 0, 7000)]
    assert beds_of(bed_world, [cue(r2, s2, 0, 3000, 0), cue(r2, s2, 3000, 6000, 1)]) == [(r2, 0, 3000), (r2, 3000, 6000)]
    overlap = [cue(r1, s1, 0, 5000, 0), cue(r2, s2, 3000, 8000, 1)]
    assert beds_of(bed_world, overlap) == [(r1, 0, 3000), (r2, 3000, 8000)]
    assert beds_of(bed_world, list(reversed(overlap))) == [(r1, 0, 3000), (r2, 3000, 8000)]


def overlap_inputs(world):
    r1, s1 = stage_rendition(world, 8, 220)
    r2, s2 = stage_rendition(world, 5, 330)
    return (r1, r2), world.sources.resolve_inputs([*world.refs, cue(r1, s1, 0, 5000, 0), cue(r2, s2, 3000, 8000, 1)])


def test_each_rendition_becomes_one_asset_and_one_flat_manifest_entry(bed_world):
    refs, inputs = overlap_inputs(bed_world)
    manifest = {entry.artifact_version_id: entry for entry in inputs.materialization_manifest}
    for ref in refs:
        (asset,) = [item for item in inputs.input_artifacts if item.artifact_version_id == ref]
        flat = bed_world.runtime.staging_root / f'{ref}.wav'
        assert asset.sha256 == ref[len('music-'):]
        assert asset.size_bytes == flat.stat().st_size
        assert asset.media_type == 'audio/wav' and asset.role == 'music_bed'
        assert manifest[ref].local_ref == f'{ref}.wav'
        assert flat.parent == bed_world.runtime.staging_root
    for bed in inputs.mix_plan['beds']:
        assert isinstance(bed['integrated_lufs'], float) and isinstance(bed['gain_db'], float)


def test_resolve_rejects_a_bed_missing_from_the_inputs(bed_world):
    refs, inputs = overlap_inputs(bed_world)
    kept = tuple(item for item in inputs.input_artifacts if item.artifact_version_id != refs[1])
    with pytest.raises(ResolveError) as info:
        resolve_render_package(dataclasses.replace(inputs, input_artifacts=kept), bed_world.plan_port)
    assert info.value.code == MISSING_REQUIRED
    assert info.value.field == 'mix_plan.beds[1].rendition_ref'


def command_args(world, pinned, record):
    return (
        record, pinned[0].preset, pinned[1].profile, world.sources.ass_ref_for(record),
        ToolIdentity(name='ffmpeg', version='test', build='test-build', executable='C:/tools/ffmpeg.exe'),
        MaterializedPaths(staging_root=str(world.runtime.staging_root), output_path='out/render_cmd.mp4', thumbnail_path='out/render_cmd.jpg'),
    )


def test_render_command_adds_one_input_and_one_chain_per_bed(bed_world, pinned):
    refs, inputs = overlap_inputs(bed_world)
    record = resolve_render_package(inputs, bed_world.plan_port)
    plan = bed_world.sources.render_plan(record, 'render:cmd:1')
    argv = plan.command_spec.redacted_argv
    for index, bed in enumerate(record.mix_plan['beds']):
        at = argv.index('{bed:%d}' % index)
        seconds = f"{(bed['end_ms'] - bed['start_ms']) // 1000}.{(bed['end_ms'] - bed['start_ms']) % 1000:03d}"
        assert argv[at - 3:at] == ('-t', seconds, '-i')
    graph = argv[argv.index('-filter_complex') + 1]
    for index, bed in enumerate(record.mix_plan['beds']):
        assert f"volume={bed['gain_db']:.2f}dB,adelay={bed['start_ms']}:all=1[abed{index}]" in graph
    assert 'amix=inputs=4:duration=first:normalize=0' in graph
    assert graph.index('amix=inputs=4') < graph.index('loudnorm')
    plain_record = dataclasses.replace(record, mix_plan={})
    plain = build_render_command(*command_args(bed_world, pinned, plain_record), voice_duration_ms=bed_world.voice_ms)
    with_beds = build_render_command(*command_args(bed_world, pinned, record), voice_duration_ms=bed_world.voice_ms)
    assert with_beds.spec_fingerprint != plain.spec_fingerprint
    plain_graph = plain.redacted_argv[plain.redacted_argv.index('-filter_complex') + 1]
    voice_index = sum(1 for item in plain.redacted_argv[:plain.redacted_argv.index('{voice}')] if item == '-i') - 1
    assert f'[{voice_index}:a:0][ahook]amix=inputs=2:duration=first:normalize=0' in plain_graph
    assert '{bed:' not in ' '.join(plain.redacted_argv)


@pytest.mark.parametrize('change,code', [
    ({'start_ms': 1000, 'end_ms': 1000}, 'INVALID_INPUT'),
    ({'start_ms': -1}, 'INVALID_INPUT'),
    ({'gain_db': 'x'}, 'INVALID_INPUT'),
    ({'gain_db': float('nan')}, 'INVALID_INPUT'),
    ({'gain_db': True}, 'INVALID_INPUT'),
    ({'rendition_ref': 'music-' + '1' * 64}, 'asset_not_materialized'),
])
def test_render_command_rejects_bad_beds(bed_world, pinned, change, code):
    refs, inputs = overlap_inputs(bed_world)
    record = resolve_render_package(inputs, bed_world.plan_port)
    bed = {'rendition_ref': refs[0], 'start_ms': 0, 'end_ms': 3000, 'gain_db': -30.0, **change}
    broken = dataclasses.replace(record, mix_plan={'beds': [bed]})
    with pytest.raises(RenderCommandRejected) as info:
        build_render_command(*command_args(bed_world, pinned, broken), voice_duration_ms=bed_world.voice_ms)
    assert info.value.code == code
