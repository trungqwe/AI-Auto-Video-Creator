"""PW-E4-FIX1: nhạc nền thật (MP3 ghim chuẩn hoá bằng FFmpeg ghim, transport HTTPS ghim địa chỉ) trên PostgreSQL và FFmpeg ghim thật.

coveredIds: FR-AUD-007, FR-AUD-004, CT-AUD-001
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import hashlib
import json
import pathlib
import socket
import subprocess
from decimal import Decimal
from types import SimpleNamespace

import pytest

import controlplane.api.wiring.production_profile as profile_wiring
from controlplane.api.wiring.production_profile import ProductionProfileError
from controlplane.api.wiring.voice import ProductionHttpsTransport, build_voice_services, locate_media_file, verify_media_output, voice_activity_deps
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from voice.adapters.audio_bed_source import HttpsResponse, MusicSource, MusicSourceError, silent_wav
from voice.adapters.profile_media_policy import build_loudness_constraints
from voice.domain.processing import Disposition
from voice.domain.voice_track import VoiceTrack
from voice.persistence import PostgresVoiceUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NOW = datetime.datetime(2026, 11, 1, 1, 0, tzinfo=datetime.timezone.utc)
PRIMARY_URL = 'https://music-primary.test/bed.mp3'
FALLBACK_URL = 'https://music-fallback.test/bed.mp3'
JOB = 'job-fix1'
STAGE_RUN = 'job-fix1:process:r1'
PLAN = 'plan-fix1'


def make_runtime(tmp_path: pathlib.Path) -> profile_wiring.ProductionRuntime:
    return profile_wiring.ProductionRuntime(
        ffmpeg_path=FFMPEG,
        ffprobe_path=FFMPEG.with_name('ffprobe.exe'),
        runtime_lock_path=LOCK_PATH,
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'model-weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={'revision': 'pw-w2', 'unicode_form': 'NFC', 'casefold': True, 'edge_strip_categories': ('P',), 'gap_tolerance_ms': 500, 'min_confidence': 0.5},
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=LocalGpuLease(2, 60.0),
    )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RecordingTransport:
    def __init__(self, bodies: dict, statuses: dict | None = None) -> None:
        self.bodies = bodies
        self.statuses = statuses or {}
        self.calls: list[str] = []

    def fetch(self, url, *, max_bytes, timeout_seconds):
        self.calls.append(url)
        if url not in self.bodies:
            raise OSError('unreachable')
        return HttpsResponse(self.statuses.get(url, 200), self.bodies[url], url)


def run_ffmpeg(args) -> None:
    completed = subprocess.run([str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', *args], capture_output=True, text=True, check=False, timeout=120)
    assert completed.returncode == 0, completed.stderr


def make_mp3(path: pathlib.Path, lavfi: str, af: str | None = None, seconds: int = 40) -> bytes:
    run_ffmpeg(['-f', 'lavfi', '-i', lavfi, '-t', str(seconds)] + (['-af', af] if af else []) + ['-c:a', 'libmp3lame', '-b:a', '128k', str(path)])
    return path.read_bytes()


def measure(path: pathlib.Path) -> dict[str, float]:
    completed = subprocess.run(
        [str(FFMPEG), '-hide_banner', '-nostdin', '-nostats', '-i', str(path), '-af', 'loudnorm=I=-23:TP=-2:LRA=7:print_format=json', '-f', 'null', '-'],
        capture_output=True, text=True, check=False, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    text = completed.stderr
    raw = json.loads(text[text.rindex('{'):text.rindex('}') + 1])
    return {name: float(raw[name]) for name in ('input_i', 'input_tp', 'input_lra')}


def make_source(role: str, url: str, data: bytes, moods) -> MusicSource:
    return MusicSource(source_id=f'{role}-test', role=role, url=url, license='CC BY 4.0', attribution='Test Track by Tester', author='Tester', sha256=sha(data), moods=tuple(moods))


@pytest.fixture
def rig(pw_database, tmp_path):
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)
    profile = profile_wiring.load_production_profile(PROFILE_PATH)
    runtime = make_runtime(tmp_path)
    runtime.staging_root.mkdir(parents=True)
    work = tmp_path / 'work'
    work.mkdir()
    ws = pw_database.workspace_id
    config = profile_wiring.WiringConfig(mode='production', workspace_id=ws, profile=profile, runtime=runtime)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        services = build_voice_services(manager, config)
        yield SimpleNamespace(
            database=pw_database, manager=manager, ws=ws, profile=profile, runtime=runtime, services=services, work=work,
            library=runtime.staging_root / 'audio_library', grant=ExecutionGrant(ws, 'op-fix1', JOB, STAGE_RUN, 1, 0),
        )
    finally:
        manager.close()


def make_deps(rig, sources, transport, profile=None):
    return voice_activity_deps(
        rig.services, manager=rig.manager, workspace_id=rig.ws, profile=profile or rig.profile, runtime=rig.runtime,
        grants=None, clock=lambda: NOW, music_sources=sources, music_transport=transport,
    )


def seed_plan(rig, music, sfx) -> None:
    voice = VoiceTrack(
        voice_artifact_ref='voice-artifact-' + 'a' * 64, script_version_id='sv-fix1', script_fingerprint='c' * 64, voice_hash='a' * 64,
        actual_duration_ms=65000, provider_model_voice_revision='kokoro-v1.0', usage_metrics={}, warnings=(), receipt_ref='receipt-fix1',
    )
    with PostgresVoiceUnitOfWork(rig.manager, workspace_id=rig.ws) as uow:
        uow.outputs.append('voice', f'track:{JOB}', 1, voice)
        uow.commit()
    payload = {'music_cues': music, 'sfx_cues': sfx}
    with rig.database.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_plans (workspace_id, record_key, revision, payload, production_plan_id) VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (rig.ws, PLAN, json.dumps(payload), PLAN),
        )


def run_bed(rig, deps, inputs, key):
    request = {
        'workflow_id': 'wf-fix1', 'workflow_run_id': 'run-fix1', 'stage_run_id': STAGE_RUN, 'activity_name': 'PrepareAudioBed',
        'activity_version': '1', 'input_refs': [{'ref_type': 'production_plan', 'ref_id': PLAN}], 'operation_key': key,
        'capability_requirements': {'task_queue': 'desktop_cpu'}, 'retry_policy_ref': 'retry-1', 'video_job_id': JOB,
    }
    kwargs = inputs.resolve('PrepareAudioBed', request, rig.grant)
    return deps.media.prepare_audio_bed(operation_key=key, **kwargs)


def test_pw_e4_fix1_sfx_cues_do_not_pull_music_cues_to_none(rig) -> None:
    mp3 = make_mp3(rig.work / 'a.mp3', 'sine=frequency=220:sample_rate=44100', af='volume=0.3')
    fallback_mp3 = make_mp3(rig.work / 'b.mp3', 'sine=frequency=330:sample_rate=44100', af='volume=0.3', seconds=36)
    sources = (make_source('primary', PRIMARY_URL, mp3, ('calm',)), make_source('fallback', FALLBACK_URL, fallback_mp3, ('carefree',)))
    transport = RecordingTransport({PRIMARY_URL: mp3, FALLBACK_URL: fallback_mp3})
    deps, inputs = make_deps(rig, sources, transport)
    seed_plan(
        rig,
        music=[{'start_ms': 0, 'end_ms': 31765, 'mood': 'calm', 'artifact_ref': 'music-1'}, {'start_ms': 31765, 'end_ms': 64853, 'artifact_ref': 'music-2'}],
        sfx=[{'start_ms': 1000, 'end_ms': 2100, 'artifact_ref': 'sfx-1'}, {'start_ms': 30000, 'end_ms': 31500, 'artifact_ref': 'sfx-2'}],
    )
    result = run_bed(rig, deps, inputs, 'fix1:bed-1')
    assert result.receipt.disposition is Disposition.SUCCEEDED, result.receipt.error
    assert 'AUDIO_MIX_QUALITY' not in result.receipt.warnings
    record = result.record
    assert record.provenance['bed_kind'] == 'external_music'
    track = record.provenance['tracks'][0]
    assert track['sha256'] == sha(mp3)
    rendition = track['rendition_sha256']
    assert rendition != sha(mp3)
    assert rendition == sha((rig.library / f'music-{rendition}.audio').read_bytes())
    assert record.renditions[0].rendition_ref == record.renditions[1].rendition_ref == f'music-{rendition}'
    for index, span in ((2, 1100), (3, 1500)):
        ref = record.renditions[index].rendition_ref
        assert ref.startswith('bed-none-')
        assert (rig.library / f'{ref}.wav').read_bytes() == silent_wav(span)
    assert [(item['cue_index'], item['bed_kind'], item['reason']) for item in record.provenance['sfx']] == [(2, 'none', 'no_sfx_source'), (3, 'none', 'no_sfx_source')]
    verify = verify_media_output(locate_media_file(rig.manager, rig.ws, rig.runtime.staging_root))
    for ref in result.receipt.output_refs:
        found = verify(ref)
        assert found is not None
        if ref.startswith('music-'):
            assert found.content_sha256 == rendition
    assert transport.calls == [PRIMARY_URL]
    again = run_bed(rig, deps, inputs, 'fix1:bed-2')
    assert again.receipt.disposition is Disposition.SUCCEEDED, again.receipt.error
    assert transport.calls == [PRIMARY_URL]
    assert again.record.renditions[0].rendition_ref == record.renditions[0].rendition_ref


NOISE = 'anoisesrc=color=pink:amplitude=0.4:seed=7:sample_rate=44100'
MP3_KINDS = {
    'loud': ('sine=frequency=55:sample_rate=44100', 'volume=7.6'),
    'wide_lra': (NOISE, "volume='if(lt(t,20),1,0.15)':eval=frame"),
}


@pytest.mark.parametrize('kind', ('loud', 'wide_lra'))
def test_pw_e4_fix1_prepared_music_lands_inside_the_profile_window(rig, kind) -> None:
    lavfi, af = MP3_KINDS[kind]
    mp3 = make_mp3(rig.work / f'{kind}.mp3', lavfi, af=af)
    before = measure(rig.work / f'{kind}.mp3')
    if kind == 'loud':
        assert -9 <= before['input_i'] <= -7 and -1.2 <= before['input_tp'] <= -0.6, before
    else:
        assert before['input_lra'] > 11, before
    sources = (make_source('primary', PRIMARY_URL, mp3, ('calm',)), make_source('fallback', FALLBACK_URL, mp3, ('carefree',)))
    transport = RecordingTransport({PRIMARY_URL: mp3, FALLBACK_URL: mp3})
    deps, inputs = make_deps(rig, sources, transport)
    seed_plan(rig, music=[{'start_ms': 0, 'end_ms': 20000, 'artifact_ref': 'music-1'}], sfx=[])
    result = run_bed(rig, deps, inputs, f'fix1:{kind}')
    assert result.receipt.disposition is Disposition.SUCCEEDED, result.receipt.error
    assert result.record.provenance['bed_kind'] == 'external_music'
    assert 'AUDIO_MIX_QUALITY' not in result.receipt.warnings
    track = result.record.provenance['tracks'][0]
    stored = rig.library / f"music-{track['rendition_sha256']}.audio"
    limits = build_loudness_constraints(rig.profile.parameters)
    got = measure(stored)
    assert limits.min_lufs <= got['input_i'] <= limits.max_lufs
    assert got['input_tp'] <= limits.max_true_peak_dbtp
    assert abs(result.record.loudness_report.integrated_lufs - got['input_i']) <= 0.05
    assert abs(result.record.loudness_report.true_peak_dbtp - got['input_tp']) <= 0.05
    assert track['duration_ms'] >= 20000
    assert list(rig.library.glob('prep-*')) == []


def test_pw_e4_fix1_primary_500_uses_the_fallback_for_a_cue_without_mood(rig) -> None:
    mp3 = make_mp3(rig.work / 'f.mp3', 'sine=frequency=262:sample_rate=44100', af='volume=0.3')
    sources = (make_source('primary', PRIMARY_URL, mp3, ('calm', 'ambient')), make_source('fallback', FALLBACK_URL, mp3, ('carefree', 'upbeat')))
    transport = RecordingTransport({PRIMARY_URL: b'x', FALLBACK_URL: mp3}, statuses={PRIMARY_URL: 500})
    deps, inputs = make_deps(rig, sources, transport)
    seed_plan(rig, music=[{'start_ms': 0, 'end_ms': 20000, 'artifact_ref': 'music-1'}], sfx=[])
    result = run_bed(rig, deps, inputs, 'fix1:fallback')
    assert result.receipt.disposition is Disposition.SUCCEEDED, result.receipt.error
    assert result.record.provenance['bed_kind'] == 'external_music'
    assert transport.calls == [PRIMARY_URL, FALLBACK_URL]
    assert result.record.provenance['tracks'][0]['source_id'] == 'fallback-test'


def test_pw_e4_fix1_silent_mp3_gives_bed_none_music_unreadable_and_no_leftovers(rig) -> None:
    mp3 = make_mp3(rig.work / 's.mp3', 'anullsrc=r=44100:cl=mono', seconds=40)
    sources = (make_source('primary', PRIMARY_URL, mp3, ('calm',)), make_source('fallback', FALLBACK_URL, mp3, ('carefree',)))
    transport = RecordingTransport({PRIMARY_URL: mp3, FALLBACK_URL: mp3})
    deps, inputs = make_deps(rig, sources, transport)
    seed_plan(rig, music=[{'start_ms': 0, 'end_ms': 20000, 'artifact_ref': 'music-1'}], sfx=[])
    result = run_bed(rig, deps, inputs, 'fix1:silent')
    assert result.receipt.disposition is Disposition.SUCCEEDED, result.receipt.error
    assert 'AUDIO_MIX_QUALITY' in result.receipt.warnings
    record = result.record
    assert record.provenance['bed_kind'] == 'none'
    assert 'music_unreadable' in record.provenance['errors']
    assert list(rig.library.glob('music-*')) == []
    assert list(rig.library.glob('*.part*')) == []
    assert list(rig.library.glob('prep-*')) == []
    assert record.renditions[0].rendition_ref.startswith('bed-none-')


GLOBAL = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]


def _v4(address: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]


@pytest.mark.parametrize(
    'url, infos',
    [
        ('http://music-primary.test/bed.mp3', GLOBAL),
        ('https://music-primary.test:8443/bed.mp3', GLOBAL),
        ('https://user:pw@music-primary.test/bed.mp3', GLOBAL),
        (PRIMARY_URL, []),
        (PRIMARY_URL, _v4('127.0.0.1')),
        (PRIMARY_URL, _v4('10.1.2.3')),
        (PRIMARY_URL, _v4('169.254.1.1')),
        (PRIMARY_URL, [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 443, 0, 0))]),
        (PRIMARY_URL, GLOBAL + _v4('10.0.0.1')),
    ],
)
def test_pw_e4_fix1_transport_refuses_before_any_network(url, infos) -> None:
    assert ProductionHttpsTransport() is not None
    calls: list[str] = []

    def resolve(host, port, type=0):
        calls.append(host)
        return infos

    transport = ProductionHttpsTransport(resolve=resolve)
    with pytest.raises(MusicSourceError) as caught:
        transport.fetch(url, max_bytes=1024, timeout_seconds=1.0)
    assert caught.value.code == 'music_url_not_allowed'


def test_pw_e4_fix1_missing_profile_lra_is_a_build_error(rig) -> None:
    value = dict(rig.profile.parameters['audio.loudness'])
    del value['lra']
    profile = dataclasses.replace(rig.profile, parameters={**rig.profile.parameters, 'audio.loudness': value})
    with pytest.raises(ProductionProfileError) as caught:
        make_deps(rig, (), RecordingTransport({}), profile=profile)
    assert 'audio.loudness.lra' in str(caught.value)


def test_pw_e4_fix1_module_docstring_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    line = [item for item in doc.splitlines() if item.startswith('coveredIds:')][0]
    ids = {item.strip() for item in line[len('coveredIds:'):].split(',')}
    assert {'FR-AUD-007', 'FR-AUD-004', 'CT-AUD-001'} <= ids
