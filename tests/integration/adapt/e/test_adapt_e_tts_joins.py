"""ADAPT-E-FIX2: sentence joins keep the model-generated tail through the default Kokoro factory; fake Kokoro subclass, no real weights, no network."""
from __future__ import annotations

import hashlib
import json
import socket
import wave
from io import BytesIO
from types import SimpleNamespace

import kokoro_onnx
import numpy as np
import pytest
from kokoro_onnx import Kokoro as LibraryKokoro
from kokoro_onnx.trim import trim as library_trim

from voice.adapters import real_kokoro_tts as tts_module
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts
from voice.domain.tts_invocation import ProviderRouteDecision
from voice.ports.script_text import ScriptText

FINGERPRINT = 'a' * 64
RATE = 24000
LEAD = 7200
TAIL = 10800
STYLE_SHAPE = (511, 1, 256)
MODEL_BYTES = b'fake-kokoro-model'
VOICES_BYTES = b'fake-kokoro-voices'
WEIGHT_FILES = {'kokoro-v1.0.onnx': MODEL_BYTES, 'voices-v1.0.bin': VOICES_BYTES}
SENTENCE_TEXT = ' '.join(c * 300 + '.' for c in 'abc')
COMMA_TEXT = 'd' * 300 + ', ' + 'e' * 300 + '.'
SINGLE_TEXT = 'Hello world.'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_lock(path, group, files, *, pinned=True):
    entries = [
        {'name': name, 'group': group, 'sha256': sha(data) if pinned else None, 'status': 'PINNED' if pinned else 'BLOCKED'}
        for name, data in files.items()
    ]
    path.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')


def decision() -> ProviderRouteDecision:
    return ProviderRouteDecision(
        provider_ref='kokoro-local',
        model_ref='kokoro-v1.0',
        account_ref='local',
        route_revision='r1',
        rationale_codes=('LOCAL',),
        fallback_order=(),
        capacity_reservation_ref='res-1',
        credential_acquisition_method='none',
        estimated_cost_class='free',
    )


def voice_request() -> dict[str, object]:
    return dict(
        script_version_id='sv-1',
        script_fingerprint=FINGERPRINT,
        voice_profile_ref='vp-1',
        provider_route_ref='pr-1',
        expected_language='en-US',
        operation_key='op-1',
        execution_grant_ref='g-1',
    )


def script(text: str) -> ScriptText:
    return ScriptText('sv-1', text, FINGERPRINT)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('network access attempted')

    for name in ('connect', 'connect_ex'):
        monkeypatch.setattr(socket.socket, name, refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


def fake_audio(n_chars: int) -> np.ndarray:
    return np.concatenate([
        np.zeros(LEAD),
        0.5 * np.sin(2 * np.pi * 220 * np.arange(24 * n_chars) / RATE),
        np.zeros(TAIL),
    ]).astype(np.float32)


class FakeKokoro(LibraryKokoro):
    instances = []

    def __init__(self, model_path: str, voices_path: str) -> None:
        self.voices = {'af_heart': np.zeros(STYLE_SHAPE, dtype=np.float32)}
        self.phonemize_calls = []
        self.audio_calls = []
        self.tokenizer = SimpleNamespace(phonemize=self._phonemize)
        FakeKokoro.instances.append(self)

    def _phonemize(self, text: str, lang: str) -> str:
        self.phonemize_calls.append((text, lang))
        return text

    def _create_audio(self, phonemes: str, voice: object, speed: float) -> tuple[np.ndarray, int]:
        self.audio_calls.append((phonemes, voice.shape, speed))
        return fake_audio(len(phonemes)), RATE


@pytest.fixture(autouse=True)
def fake_kokoro(monkeypatch):
    FakeKokoro.instances = []
    monkeypatch.setattr(kokoro_onnx, 'Kokoro', FakeKokoro)


@pytest.fixture
def tts_env(tmp_path):
    weights = tmp_path / 'weights'
    staging = tmp_path / 'staging'
    weights.mkdir()
    staging.mkdir()
    for name, data in WEIGHT_FILES.items():
        (weights / name).write_bytes(data)
    lock = tmp_path / 'lock.json'
    write_lock(lock, 'kokoro-onnx', WEIGHT_FILES)
    config = KokoroConfig(
        weights_dir=weights,
        lock_path=lock,
        staging_dir=staging,
        voice='af_heart',
        speed=1.1,
        language='en-us',
        sample_rate=24000,
    )
    return SimpleNamespace(config=config, weights=weights, staging=staging)


def synth(env, text: str):
    engine = RealKokoroTts(env.config)
    return engine.synthesize(decision(), script(text), voice_request())


def wav_pcm(result) -> np.ndarray:
    with wave.open(BytesIO(result.audio_bytes), 'rb') as wav:
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')


def reference_pcm(text: str) -> np.ndarray:
    return np.frombuffer(
        tts_module._to_pcm16(
            FakeKokoro.instances[-1].create(text, voice='af_heart', speed=1.1, lang='en-us')[0]
        ),
        dtype='<i2',
    )


def shape_of(pcm: np.ndarray) -> tuple[np.ndarray, int, int]:
    nz = np.flatnonzero(pcm)
    return np.diff(nz) - 1, int(nz[0]), len(pcm) - 1 - int(nz[-1])


def test_sentence_joins_keep_model_tail_through_default_factory(tts_env):
    result = synth(tts_env, SENTENCE_TEXT)
    pcm = wav_pcm(result)
    ref = reference_pcm(SENTENCE_TEXT)
    gaps, lead, trail = shape_of(pcm)
    _, ref_lead, ref_trail = shape_of(ref)
    batches = LibraryKokoro._split_phonemes(FakeKokoro.instances[-1], SENTENCE_TEXT)
    assert len(batches) == 3

    assert len([int(g) for g in gaps if g >= TAIL]) == 2
    assert np.array_equal(pcm[pcm != 0], ref[ref != 0])
    assert lead == ref_lead and trail == ref_trail
    assert len(pcm) == len(ref) + sum(
        len(a) - int(library_trim(a)[1][1])
        for a in (fake_audio(len(b)) for b in batches[:-1])
    )


@pytest.mark.parametrize('text', [COMMA_TEXT, SINGLE_TEXT])
def test_comma_join_and_single_batch_unchanged(tts_env, text):
    result = synth(tts_env, text)
    batches = LibraryKokoro._split_phonemes(FakeKokoro.instances[-1], text)
    if text == COMMA_TEXT:
        assert len(batches) == 2 and batches[0].endswith(',')
    elif text == SINGLE_TEXT:
        assert len(batches) == 1
    assert wav_pcm(result).tobytes() == reference_pcm(text).tobytes()


def test_wrapper_keeps_voice_speed_lang_and_batching(tts_env):
    result = synth(tts_env, SENTENCE_TEXT)
    assert len(result.audio_bytes) > 0
    assert len(FakeKokoro.instances) == 1
    fake = FakeKokoro.instances[0]
    assert fake.phonemize_calls == [(SENTENCE_TEXT, tts_env.config.language)]
    expected = LibraryKokoro._split_phonemes(fake, SENTENCE_TEXT)
    assert len(expected) == 3
    assert [c[0] for c in fake.audio_calls] == expected
    assert all(c[1] == fake.voices[tts_env.config.voice].shape for c in fake.audio_calls)
    assert all(c[2] == tts_env.config.speed for c in fake.audio_calls)


class FourArgModel:
    def __init__(self) -> None:
        self.calls = []
        self.samples = np.linspace(-1.0, 1.0, 2400, dtype=np.float32)

    def create(self, text: str, voice: str, speed: float, lang: str) -> tuple[np.ndarray, int]:
        self.calls.append({'text': text, 'voice': voice, 'speed': speed, 'lang': lang})
        return self.samples, RATE


def test_revision_marks_join_policy_and_injected_model_path_unchanged(tts_env):
    result = synth(tts_env, SINGLE_TEXT)
    assert result.voice_revision.endswith(';sentence_joins=model-tail')
    for fragment in (sha(MODEL_BYTES), sha(VOICES_BYTES), 'af_heart'):
        assert fragment in result.voice_revision

    model = FourArgModel()
    factory_calls = []

    def factory(model_path: str, voices_path: str):
        factory_calls.append((model_path, voices_path))
        return model

    engine = RealKokoroTts(tts_env.config, model_factory=factory)
    injected = engine.synthesize(decision(), script(SENTENCE_TEXT), voice_request())

    assert model.calls == [{'text': SENTENCE_TEXT, 'voice': 'af_heart', 'speed': 1.1, 'lang': 'en-us'}]
    assert wav_pcm(injected).tobytes() == tts_module._to_pcm16(model.samples)
    assert 'sentence_joins' not in injected.voice_revision
    assert len(factory_calls) == 1
    assert len(FakeKokoro.instances) == 1
