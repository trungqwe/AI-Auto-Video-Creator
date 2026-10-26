"""PW-E2: single WAV file name rule (DQ-13), LocalVoiceRoute, PostgresScriptText and WAV duration measured from samples, on real PostgreSQL 18.6.

coveredIds: PW-E2-01, CT-MED-007
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import io
import json
import pathlib
import uuid
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from controlplane.infrastructure.db.uow import TransactionManager
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.persistence.repositories import PostgresScriptRepository
from voice.adapters.local_voice_route import LocalVoiceRoute
from voice.adapters.postgres_script_text import PostgresScriptText, ScriptVersionNotFound
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts, VoiceArtifactPlacer
from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig
from voice.adapters.wav_duration import InvalidWavError, measure_wav_duration_ms, read_wav_info
from voice.application import voice_pipeline as vp
from voice.domain.timing_coverage import TokenizationPolicy
from voice.domain.tts_invocation import RouteContractViolation, plan_provider_path
from voice.persistence import PostgresVoiceUnitOfWork
from voice.ports.aligner import AlignerError, AlignmentRequest
from voice.ports.repositories import EventContext
from voice.ports.script_text import ScriptText, ScriptTextPort
from voice.ports.tts import VoiceRoutePort

ROOT = pathlib.Path(__file__).resolve().parents[3]
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
ROUTE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
VOICE_SRC = ROOT / 'src' / 'voice'
TRACK = 'track-e2'
TOKENIZATION = TokenizationPolicy(revision='tok-test-v1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
NETWORK_ROOTS = {'socket', 'urllib', 'http', 'requests', 'httpx', 'aiohttp', 'ftplib', 'google', 'openai', 'huggingface_hub', 'subprocess'}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_wav_bytes(frames: int, rate: int = 24000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(2 * channels * frames))
    return buffer.getvalue()


def imported_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    roots = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    return roots | {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}


def route_request() -> dict:
    data = json.loads(ROUTE_FIXTURE.read_text(encoding='utf-8'))
    return {**copy.deepcopy(data['entities']['ProviderRouteRequest']['valid'][0]), 'ai_role': 'voice_synthesis', 'allowed_fallbacks': []}


def test_pw_e2_wav_duration_is_measured_from_samples_rate_and_channels() -> None:
    for frames, rate, channels, expected_ms in [(2400, 24000, 1, 100), (8000, 16000, 2, 500), (22050, 22050, 1, 1000), (24001, 24000, 1, 1000)]:
        wav_bytes = make_wav_bytes(frames, rate, channels)
        info = read_wav_info(wav_bytes)
        assert (info.frames, info.sample_rate, info.channels) == (frames, rate, channels)
        assert measure_wav_duration_ms(wav_bytes) == expected_ms
    slow, fast = make_wav_bytes(16000, 8000), make_wav_bytes(16000, 16000)
    assert len(slow) == len(fast)
    assert (measure_wav_duration_ms(slow), measure_wav_duration_ms(fast)) == (2000, 1000)


def test_pw_e2_wav_duration_rejects_broken_wav() -> None:
    good = make_wav_bytes(2400)
    for bad in (good[:-100], good[:30], b'', b'not a wav at all', make_wav_bytes(0)):
        with pytest.raises(InvalidWavError) as caught:
            measure_wav_duration_ms(bad)
        assert caught.value.code == 'wav_invalid'
    with pytest.raises(TypeError):
        measure_wav_duration_ms('text')


def test_pw_e2_local_voice_route_resolves_only_local_kokoro() -> None:
    route = LocalVoiceRoute()
    assert isinstance(route, VoiceRoutePort)
    assert list(inspect.signature(LocalVoiceRoute.__init__).parameters) == ['self', 'route_revision']
    request = {**route_request(), 'allowed_fallbacks': ['gemini-tts', 'openai-tts']}
    decision = route.resolve(request)
    assert (decision.provider_ref, decision.model_ref, decision.account_ref) == ('kokoro-local', 'kokoro-v1.0', 'local')
    assert decision.fallback_order == () and decision.credential_acquisition_method == 'none' and decision.estimated_cost_class == 'free'
    assert plan_provider_path(decision, request) == ('kokoro-local',)
    with pytest.raises(RouteContractViolation):
        route.resolve({key: value for key, value in route_request().items() if key != 'job_ref'})
    with pytest.raises(RouteContractViolation):
        route.resolve({**route_request(), 'api_key': 'x'})
    assert not imported_roots(VOICE_SRC / 'adapters' / 'local_voice_route.py') & NETWORK_ROOTS


def make_script(workspace_id: str, script_id: str, narration: list[str]) -> ScriptVersion:
    ref = ResourceRef(workspace_id, 'article', 'ref-e2', 'rev-1')
    segments = tuple(
        ScriptSegment(segment_id=f'{script_id}-{index}', order=index, text=text, claim_mode='inference', scene_intent='scene', source_refs=(ref,), disclosure=None, word_count=len(text.split()), estimated_seconds=1.0)
        for index, text in enumerate(narration)
    )
    return ScriptVersion(script_version_id=script_id, language='en', hook_intent='hook', thumbnail_transition='cut', segments=segments, pronunciation_hints=(), speech_rate=2.5, estimated_duration_seconds=3.0)


def seed_scripts(manager, workspace_id: str, scripts: list) -> None:
    with manager.borrow_connection() as connection:
        repository = PostgresScriptRepository(lambda: connection, workspace_id)
        for script in scripts:
            repository.append(script.script_version_id, 1, script)


def test_pw_e2_script_text_is_read_from_cp_script_versions_by_script_ref(pw_database) -> None:
    other_workspace = str(uuid.uuid4())
    with pw_database.connect() as admin:
        admin.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (other_workspace, 'pw-other', 'ACTIVE'))
    manager = TransactionManager(pw_database.dsn)
    try:
        first = make_script(pw_database.workspace_id, 'sv-e2-a', ['Breaking news', 'today in town'])
        second = make_script(pw_database.workspace_id, 'sv-e2-b', ['Second script'])
        seed_scripts(manager, pw_database.workspace_id, [first, second])
        seed_scripts(manager, other_workspace, [make_script(other_workspace, 'sv-e2-a', ['Foreign workspace text'])])
        port = PostgresScriptText(manager, workspace_id=pw_database.workspace_id)
        assert isinstance(port, ScriptTextPort)
        assert list(inspect.signature(PostgresScriptText.get_text).parameters) == ['self', 'script_version_id']
        assert port.get_text('sv-e2-a') == ScriptText('sv-e2-a', 'Breaking news today in town', first.script_fingerprint)
        assert port.get_text('sv-e2-b') == ScriptText('sv-e2-b', 'Second script', second.script_fingerprint)
        assert PostgresScriptText(manager, workspace_id=other_workspace).get_text('sv-e2-a').text == 'Foreign workspace text'
        with pytest.raises(ScriptVersionNotFound):
            port.get_text('sv-e2-missing')
    finally:
        manager.close()
    assert 'cp_script_versions' in (VOICE_SRC / 'adapters' / 'postgres_script_text.py').read_text(encoding='utf-8')


WEIGHTS_FILES = {'kokoro-v1.0.onnx': b'fake-kokoro-model', 'voices-v1.0.bin': b'fake-kokoro-voices'}
WHISPER_FILES = {'config.json': b'{}', 'model.bin': b'fake-whisper-model', 'tokenizer.json': b'{}', 'vocabulary.txt': b'a'}


def write_lock(path: pathlib.Path, group: str, files: dict) -> None:
    entries = [{'name': name, 'group': group, 'sha256': sha(data), 'status': 'PINNED'} for name, data in files.items()]
    path.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')


class FakeKokoroModel:
    def create(self, text, voice, speed, lang):
        return np.linspace(-0.5, 0.5, 24000, dtype=np.float32), 24000


class FakeWhisperModel:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def transcribe(self, audio, **kwargs):
        self.opened.append(audio)
        words = [SimpleNamespace(word=' ' + text, start=0.3 * index, end=0.3 * (index + 1), probability=0.9) for index, text in enumerate(['Breaking', 'news', 'today'])]
        return iter([SimpleNamespace(start=0.0, end=0.9, words=words)]), SimpleNamespace(language='en')


def make_aligner(tmp_path: pathlib.Path, voice_root: pathlib.Path):
    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    for name, data in WHISPER_FILES.items():
        (model_dir / name).write_bytes(data)
    write_lock(tmp_path / 'whisper-lock.json', 'faster-whisper-small.en', WHISPER_FILES)
    whisper = FakeWhisperModel()
    config = WhisperAlignerConfig(model_dir=model_dir, lock_path=tmp_path / 'whisper-lock.json', voice_root=voice_root, tokenization_policy=TOKENIZATION, max_unmatched_word_ratio=0.2)
    return RealWhisperAligner(config, model_factory=lambda directory, device, compute_type: whisper), whisper


def voice_base() -> dict:
    return dict(json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))['entities']['VoiceTrackRequest']['valid'][0])


def ctx(name: str) -> EventContext:
    return EventContext(workspace_id='ws-1', correlation_id='corr-1', actor='worker-e', occurred_at='2026-10-27T00:00:00+00:00', recovery_epoch='epoch-1', event_id=f'evt-{name}', message_id=f'msg-{name}')


def voice_command(request: dict) -> vp.CreateVoiceTrackCommand:
    return vp.CreateVoiceTrackCommand(track_key=TRACK, voice_request=request, route_request=route_request(), attempt_policy={'max_attempts': 2, 'max_attempts_per_provider': 2}, duration_policy=(500, 70000), context=ctx('voice'))


def build_rig(tmp_path: pathlib.Path, database):
    voice_root = tmp_path / 'voice'
    voice_root.mkdir()
    weights = tmp_path / 'weights'
    weights.mkdir()
    for name, data in WEIGHTS_FILES.items():
        (weights / name).write_bytes(data)
    write_lock(tmp_path / 'kokoro-lock.json', 'kokoro-onnx', WEIGHTS_FILES)
    config = KokoroConfig(weights_dir=weights, lock_path=tmp_path / 'kokoro-lock.json', staging_dir=voice_root, voice='af_heart', speed=1.0, language='en-us', sample_rate=24000)
    tts = RealKokoroTts(config, model_factory=lambda model_path, voices_path: FakeKokoroModel())
    aligner, whisper = make_aligner(tmp_path, voice_root)
    manager = TransactionManager(database.dsn)
    base = voice_base()
    script = make_script(database.workspace_id, base['script_version_id'], ['Breaking news today'])
    seed_scripts(manager, database.workspace_id, [script])
    pipeline = vp.VoicePipeline(uow=PostgresVoiceUnitOfWork(manager, workspace_id=database.workspace_id), script_port=PostgresScriptText(manager, workspace_id=database.workspace_id), route_port=LocalVoiceRoute(), tts_engine=tts, aligner=aligner, measure_duration_ms=measure_wav_duration_ms, place_artifact=VoiceArtifactPlacer(voice_root))
    return SimpleNamespace(voice_root=voice_root, whisper=whisper, manager=manager, pipeline=pipeline, request={**base, 'script_fingerprint': script.script_fingerprint})


@pytest.fixture
def rig(tmp_path, pw_database):
    built = build_rig(tmp_path, pw_database)
    yield built
    built.manager.close()


def test_pw_e2_pipeline_places_the_wav_as_voice_artifact_and_aligner_opens_that_name(rig, pw_database) -> None:
    voice = rig.pipeline.create_voice_track(voice_command(rig.request)).voice_track
    artifact = rig.voice_root / voice.voice_artifact_ref
    assert voice.voice_artifact_ref == 'voice-artifact-' + voice.voice_hash and artifact.is_file()
    assert sha(artifact.read_bytes()) == voice.voice_hash and voice.actual_duration_ms == 1000
    assert sorted(path.name for path in rig.voice_root.iterdir()) == sorted(['tmp', voice.voice_artifact_ref])
    assert list((rig.voice_root / 'tmp').iterdir()) == [] and list(rig.voice_root.rglob('tts-*')) == []
    timing = rig.pipeline.create_word_timing(vp.CreateWordTimingCommand(track_key=TRACK, voice_request=rig.request, tokenization_policy=TOKENIZATION, context=ctx('timing')))
    assert rig.whisper.opened == [str(artifact)] and len(timing.timing.words) == 3
    with pw_database.connect() as connection:
        assert connection.execute('SELECT voice_hash FROM controlplane.cp_voice_tracks').fetchall() == [(voice.voice_hash,)]


def test_pw_e2_replayed_command_keeps_the_single_artifact(rig) -> None:
    first = rig.pipeline.create_voice_track(voice_command(rig.request))
    second = rig.pipeline.create_voice_track(voice_command(rig.request))
    assert second.replayed is True and second.voice_track.voice_artifact_ref == first.voice_track.voice_artifact_ref
    assert sorted(path.name for path in rig.voice_root.iterdir()) == sorted(['tmp', first.voice_track.voice_artifact_ref])


def align_request(ref: str, wav_bytes: bytes) -> AlignmentRequest:
    return AlignmentRequest(voice_artifact_ref=ref, voice_hash=sha(wav_bytes), voice_duration_ms=1000, script_version_id='sv-1', script_text='Breaking news today', expected_language='en')


def test_pw_e2_aligner_opens_only_the_voice_artifact_name(tmp_path) -> None:
    voice_root = tmp_path / 'voice'
    voice_root.mkdir()
    wav_bytes = make_wav_bytes(24000)
    digest = sha(wav_bytes)
    (voice_root / f'tts-{digest}.wav').write_bytes(wav_bytes)
    aligner, whisper = make_aligner(tmp_path, voice_root)
    for ref in (f'tts-{digest}.wav', f'voice-artifact-{digest}', f'../voice-artifact-{digest}', 'voice-artifact-1'):
        with pytest.raises(AlignerError) as caught:
            aligner.align(align_request(ref, wav_bytes))
        assert caught.value.code == 'voice_unavailable'
    assert whisper.opened == []
    (voice_root / f'voice-artifact-{digest}').write_bytes(wav_bytes)
    result = aligner.align(align_request(f'voice-artifact-{digest}', wav_bytes))
    assert whisper.opened == [str(voice_root / f'voice-artifact-{digest}')] and len(result.words) == 3


def test_pw_e2_aligner_config_requires_exactly_one_audio_source(tmp_path) -> None:
    base = dict(model_dir=tmp_path, lock_path=tmp_path / 'lock.json', tokenization_policy=TOKENIZATION, max_unmatched_word_ratio=0.2)
    for extra in ({}, {'voice_root': tmp_path, 'resolve_audio': lambda ref: tmp_path}, {'voice_root': pathlib.Path('relative')}):
        with pytest.raises(ValueError):
            WhisperAlignerConfig(**base, **extra)


def test_pw_e2_placer_moves_the_temp_wav_to_the_artifact_name_and_refuses_other_names(tmp_path) -> None:
    voice_root = tmp_path / 'voice'
    (voice_root / 'tmp').mkdir(parents=True)
    wav_bytes = make_wav_bytes(2400)
    digest = sha(wav_bytes)
    temp = voice_root / 'tmp' / f'{digest}.wav'
    temp.write_bytes(wav_bytes)
    placer = VoiceArtifactPlacer(voice_root)
    final = placer(f'voice-artifact-{digest}', wav_bytes)
    assert final == voice_root / f'voice-artifact-{digest}' and final.read_bytes() == wav_bytes and not temp.exists()
    assert placer(f'voice-artifact-{digest}', wav_bytes) == final
    for bad in (f'tts-{digest}.wav', 'voice-artifact-' + '0' * 64, f'voice-artifact-{digest[:-1]}'):
        with pytest.raises(ValueError):
            placer(bad, wav_bytes)
    other = make_wav_bytes(1200)
    other_ref = f'voice-artifact-{sha(other)}'
    assert placer(other_ref, other).read_bytes() == other
    assert sorted(path.name for path in voice_root.iterdir()) == sorted(['tmp', f'voice-artifact-{digest}', other_ref])
    assert list((voice_root / 'tmp').iterdir()) == []


def test_pw_e2_voice_pipeline_names_the_artifact_and_stays_free_of_io() -> None:
    path = VOICE_SRC / 'application' / 'voice_pipeline.py'
    text = path.read_text(encoding='utf-8')
    assert 'voice-artifact-' in text and 'from src.' not in text
    assert not imported_roots(path) & {'os', 'pathlib', 'shutil', 'tempfile', 'io', 'socket'}
    assert 'open' not in {node.func.id for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert 'tts-' not in (VOICE_SRC / 'adapters' / 'real_whisper_aligner.py').read_text(encoding='utf-8')
