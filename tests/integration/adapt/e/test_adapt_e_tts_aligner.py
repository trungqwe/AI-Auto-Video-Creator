"""ADAPT-E integration tests: local Kokoro TTS adapter and faster-whisper aligner with test-only fake models.

Real weights, real audio and alignment accuracy belong to CP7; nothing is downloaded and the network is blocked.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import socket
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from voice.adapters import real_kokoro_tts as tts_module
from voice.adapters import real_whisper_aligner as aligner_module
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts
from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig
from voice.domain.timing_coverage import TimingPolicyRejected, TokenizationPolicy, check_coverage
from voice.domain.tts_invocation import ProviderRouteDecision, TtsProviderError, TtsSynthesis
from voice.domain.voice_track import ScriptBindingError
from voice.domain.word_timing import validate_word_timing, word_timing_issues
from voice.ports.aligner import AlignerError, AlignerPort, AlignmentRequest
from voice.ports.script_text import ScriptText
from voice.ports.tts import TtsEnginePort

REPO_ROOT = Path(__file__).resolve().parents[4]
FINGERPRINT = 'a' * 64
POLICY = TokenizationPolicy(revision='adapt-e-test-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('network access attempted')

    for name in ('connect', 'connect_ex'):
        monkeypatch.setattr(socket.socket, name, refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


@pytest.fixture(autouse=True)
def no_speech_detected(monkeypatch):
    # Edge snapping is covered in test_adapt_e_aligner_edges.py; here the VAD sees no speech, so model times stay untouched.
    monkeypatch.setattr('faster_whisper.vad.get_speech_timestamps', lambda audio, vad_options=None, sampling_rate=16000, **kwargs: [])


def write_lock(path, group, files, *, pinned=True):
    entries = [
        {'name': name, 'group': group, 'sha256': sha(data) if pinned else None, 'status': 'PINNED' if pinned else 'BLOCKED'}
        for name, data in files.items()
    ]
    path.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')


def make_wav(path, duration_ms=5000, rate=16000):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(2 * (rate * duration_ms // 1000)))
    return path


MODEL_BYTES = b'fake-kokoro-model'
VOICES_BYTES = b'fake-kokoro-voices'
WEIGHT_FILES = {'kokoro-v1.0.onnx': MODEL_BYTES, 'voices-v1.0.bin': VOICES_BYTES}


class FakeKokoroModel:
    def __init__(self, *, rate=24000, samples=None, error=None):
        self.rate = rate
        self.samples = np.linspace(-1.0, 1.0, 2400, dtype=np.float32) if samples is None else samples
        self.error = error
        self.calls = []

    def create(self, text, voice, speed, lang):
        self.calls.append({'text': text, 'voice': voice, 'speed': speed, 'lang': lang})
        if self.error is not None:
            raise self.error
        return self.samples, self.rate


class ModelFactory:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def __call__(self, model_path, voices_path):
        self.calls.append((model_path, voices_path))
        return self.model


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
    config = KokoroConfig(weights_dir=weights, lock_path=lock, staging_dir=staging, voice='af_heart', speed=1.1, language='en-us', sample_rate=24000)
    return SimpleNamespace(weights=weights, staging=staging, lock=lock, config=config)


def make_tts(env, model=None, **kwargs):
    factory = ModelFactory(model if model is not None else FakeKokoroModel())
    return RealKokoroTts(env.config, model_factory=factory, **kwargs), factory


def decision():
    return ProviderRouteDecision(
        provider_ref='kokoro-local', model_ref='kokoro-v1.0', account_ref='local', route_revision='r1',
        rationale_codes=('LOCAL',), fallback_order=(), capacity_reservation_ref='res-1',
        credential_acquisition_method='none', estimated_cost_class='free',
    )


def voice_request():
    return {
        'script_version_id': 'sv-1', 'script_fingerprint': FINGERPRINT, 'voice_profile_ref': 'vp-1',
        'provider_route_ref': 'pr-1', 'expected_language': 'en-US', 'operation_key': 'op-1', 'execution_grant_ref': 'g-1',
    }


def script(text='Hello world.'):
    return ScriptText('sv-1', text, FINGERPRINT)


def test_synthesize_writes_mono_pcm_wav_with_configured_parameters(tts_env):
    engine, factory = make_tts(tts_env)
    result = engine.synthesize(decision(), script(), voice_request())
    assert isinstance(engine, TtsEnginePort)
    assert isinstance(result, TtsSynthesis)
    with wave.open(BytesIO(result.audio_bytes), 'rb') as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 24000, 2400)
        pcm = np.frombuffer(wav.readframes(2400), dtype='<i2')
    assert int(pcm[0]) == -32767 and int(pcm[-1]) == 32767
    staged = list((tts_env.staging / 'tmp').glob('*.wav'))
    assert len(staged) == 1 and staged[0].read_bytes() == result.audio_bytes and staged[0].name == sha(result.audio_bytes) + '.wav'
    assert list((tts_env.staging / 'tmp').glob('*.part')) == [] and list(tts_env.staging.glob('*.wav')) == []
    weights = tts_env.weights
    assert factory.calls == [(str(weights / 'kokoro-v1.0.onnx'), str(weights / 'voices-v1.0.bin'))]
    assert factory.model.calls == [{'text': 'Hello world.', 'voice': 'af_heart', 'speed': 1.1, 'lang': 'en-us'}]
    for fragment in (sha(MODEL_BYTES), sha(VOICES_BYTES), 'af_heart'):
        assert fragment in result.voice_revision
    assert result.usage_metrics['characters'] == len('Hello world.')
    assert result.usage_metrics['audio_ms'] == 100


def test_model_is_verified_and_loaded_once(tts_env):
    engine, factory = make_tts(tts_env)
    engine.synthesize(decision(), script(), voice_request())
    engine.synthesize(decision(), script(), voice_request())
    assert len(factory.calls) == 1
    assert len(factory.model.calls) == 2


def expect_tts_error(engine, code):
    with pytest.raises(TtsProviderError) as caught:
        engine.synthesize(decision(), script(), voice_request())
    assert caught.value.code == code
    assert caught.value.retryable is False
    return caught.value


@pytest.mark.parametrize('name', sorted(WEIGHT_FILES))
def test_sha256_mismatch_is_rejected_before_loading(tts_env, name):
    (tts_env.weights / name).write_bytes(b'tampered')
    engine, factory = make_tts(tts_env)
    expect_tts_error(engine, 'weights_sha256_mismatch')
    assert factory.calls == []
    assert list(tts_env.staging.iterdir()) == [tts_env.staging / 'tmp'] and list((tts_env.staging / 'tmp').iterdir()) == []


@pytest.mark.parametrize('name', sorted(WEIGHT_FILES))
def test_missing_weights_are_rejected_without_download(tts_env, name):
    (tts_env.weights / name).unlink()
    engine, factory = make_tts(tts_env)
    expect_tts_error(engine, 'weights_missing')
    assert factory.calls == []


def test_unpinned_or_unreadable_lock_is_rejected(tts_env):
    write_lock(tts_env.lock, 'kokoro-onnx', WEIGHT_FILES, pinned=False)
    engine, factory = make_tts(tts_env)
    expect_tts_error(engine, 'weights_unpinned')
    tts_env.lock.unlink()
    expect_tts_error(make_tts(tts_env)[0], 'weights_unpinned')
    assert factory.calls == []


def test_weights_inside_git_tree_are_rejected(tts_env):
    config = KokoroConfig(weights_dir=REPO_ROOT / 'models-test-only', lock_path=tts_env.lock, staging_dir=tts_env.staging, voice='af_heart', speed=1.0, language='en-us', sample_rate=24000)
    factory = ModelFactory(FakeKokoroModel())
    expect_tts_error(RealKokoroTts(config, model_factory=factory), 'weights_in_git_tree')
    assert factory.calls == []


def test_runtime_error_is_redacted_and_not_retryable(tts_env):
    model = FakeKokoroModel(error=RuntimeError('boom api_key=SECRETVALUE123 hunter2 at ' + str(tts_env.weights)))
    engine, _ = make_tts(tts_env, model, known_secrets=('hunter2',))
    error = expect_tts_error(engine, 'tts_runtime_error')
    assert '[REDACTED]' in error.message
    for leaked in ('SECRETVALUE123', 'hunter2', str(tts_env.weights)):
        assert leaked not in error.message


def test_model_factory_failure_is_runtime_error(tts_env):
    def broken(model_path, voices_path):
        raise OSError('cannot load')

    expect_tts_error(RealKokoroTts(tts_env.config, model_factory=broken), 'tts_runtime_error')


def test_sample_rate_mismatch_and_empty_audio_are_rejected(tts_env):
    expect_tts_error(make_tts(tts_env, FakeKokoroModel(rate=22050))[0], 'sample_rate_mismatch')
    expect_tts_error(make_tts(tts_env, FakeKokoroModel(samples=np.zeros(0, dtype=np.float32)))[0], 'empty_audio')
    assert list(tts_env.staging.iterdir()) == [tts_env.staging / 'tmp'] and list((tts_env.staging / 'tmp').iterdir()) == []


def test_missing_staging_directory_is_rejected(tts_env):
    tts_env.staging.rmdir()
    engine, factory = make_tts(tts_env)
    expect_tts_error(engine, 'staging_missing')
    assert factory.calls == []


def test_script_binding_is_enforced_before_loading(tts_env):
    engine, factory = make_tts(tts_env)
    request = dict(voice_request(), script_fingerprint='b' * 64)
    with pytest.raises(ScriptBindingError):
        engine.synthesize(decision(), script(), request)
    assert factory.calls == []


def test_kokoro_config_rejects_invalid_values(tts_env):
    base = dict(weights_dir=tts_env.weights, lock_path=tts_env.lock, staging_dir=tts_env.staging, voice='af_heart', speed=1.0, language='en-us', sample_rate=24000)
    for override in ({'speed': 3.0}, {'sample_rate': 0}, {'voice': ''}, {'weights_dir': Path('relative')}):
        with pytest.raises(ValueError):
            KokoroConfig(**{**base, **override})


MODEL_FILES = {'config.json': b'{}', 'model.bin': b'fake-whisper-model', 'tokenizer.json': b'{}', 'vocabulary.txt': b'a'}


def word(text, start, end, probability=0.9):
    return SimpleNamespace(word=text, start=start, end=end, probability=probability)


def segment(start, end, words):
    return SimpleNamespace(start=start, end=end, words=words)


class FakeWhisperModel:
    def __init__(self, segments, *, language='en', error=None):
        self.segments = segments
        self.language = language
        self.error = error
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        if self.error is not None:
            raise self.error
        return iter(self.segments), SimpleNamespace(language=self.language)


class WhisperFactory:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def __call__(self, model_dir, device, compute_type):
        self.calls.append((model_dir, device, compute_type))
        return self.model


@pytest.fixture
def align_env(tmp_path):
    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    for name, data in MODEL_FILES.items():
        (model_dir / name).write_bytes(data)
    lock = tmp_path / 'lock.json'
    write_lock(lock, 'faster-whisper-small.en', MODEL_FILES)
    voice = make_wav(tmp_path / 'voice.wav')
    return SimpleNamespace(model_dir=model_dir, lock=lock, voice=voice, voice_hash=sha(voice.read_bytes()))


def make_aligner(env, segments, *, max_ratio=0.2, model=None, **kwargs):
    factory = WhisperFactory(model if model is not None else FakeWhisperModel(segments))
    config = WhisperAlignerConfig(
        model_dir=env.model_dir, lock_path=env.lock, resolve_audio=lambda ref: env.voice,
        tokenization_policy=POLICY, max_unmatched_word_ratio=max_ratio,
    )
    return RealWhisperAligner(config, model_factory=factory, **kwargs), factory


def make_request(env, text, duration_ms=5000, voice_hash=None):
    return AlignmentRequest(
        voice_artifact_ref='voice-artifact-1', voice_hash=voice_hash or env.voice_hash, voice_duration_ms=duration_ms,
        script_version_id='sv-1', script_text=text, expected_language='en-US',
    )


def spoken(texts, step=0.4):
    words = [word(' ' + text, index * step, (index + 1) * step) for index, text in enumerate(texts)]
    return [segment(0.0, step * len(texts), words)]


HELLO_TEXT = 'Hello, world! This is a test.'
HELLO_SEGMENTS = [segment(0.1, 2.6, [
    word(' Hello,', 0.10, 0.52, 0.91), word(' world!', 0.52, 1.20, 0.88), word(' This', 1.45, 1.70, 0.95),
    word(' is', 1.70, 1.82, 0.97), word(' a', 1.90, 1.97, 0.70), word(' test.', 1.97, 2.60, 0.93),
])]


def test_word_times_come_from_the_model_and_are_valid(align_env):
    aligner, factory = make_aligner(align_env, HELLO_SEGMENTS)
    result = aligner.align(make_request(align_env, HELLO_TEXT))
    assert isinstance(aligner, AlignerPort)
    spans = [(w['start_ms'], w['end_ms']) for w in result.words]
    assert spans == [(100, 520), (520, 1200), (1450, 1700), (1700, 1820), (1900, 1970), (1970, 2600)]
    assert len({end - start for start, end in spans}) > 1
    assert [w['text'] for w in result.words] == ['Hello,', 'world!', 'This', 'is', 'a', 'test.']
    assert [w['normalized_text'] for w in result.words] == ['hello', 'world', 'this', 'is', 'a', 'test']
    assert [w['confidence'] for w in result.words] == [0.91, 0.88, 0.95, 0.97, 0.70, 0.93]
    assert result.segment_boundaries == ({'start_ms': 100, 'end_ms': 2600},)
    assert result.voice_locale_reported == 'en'
    model_sha = sha(MODEL_FILES['model.bin'])
    assert result.aligner_revision == 'faster-whisper==' + importlib.metadata.version('faster-whisper') + ';model-sha256=' + model_sha
    audio, kwargs = factory.model.calls[0]
    assert audio == str(align_env.voice)
    assert kwargs['word_timestamps'] is True and kwargs['language'] == 'en'
    assert factory.calls == [(str(align_env.model_dir), 'cpu', 'int8')]
    assert aligner.last_report.matched_count == 6 and aligner.last_report.unmatched_ratio == 0.0
    payload = {
        'script_version_id': 'sv-1', 'script_fingerprint': FINGERPRINT, 'voice_hash': align_env.voice_hash,
        'timing_artifact_ref': 'timing-1', 'words': [dict(w) for w in result.words],
        'segment_boundaries': [dict(b) for b in result.segment_boundaries],
        'validation_report_ref': 'report-1', 'voice_duration_ms': 5000,
    }
    assert word_timing_issues(payload) == ()
    assert check_coverage(HELLO_TEXT, validate_word_timing(payload).words, POLICY).complete


TEN = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
TEN_TEXT = ' '.join(TEN)


def test_unmatched_script_word_is_counted_and_gets_no_time(align_env):
    heard = [text for text in TEN if text != 'five']
    aligner, _ = make_aligner(align_env, spoken(heard), max_ratio=0.1)
    result = aligner.align(make_request(align_env, TEN_TEXT))
    report = aligner.last_report
    assert report.missing_script_indices == (4,) and report.extra_transcript_indices == ()
    assert report.matched_count == 9 and report.unmatched_ratio == pytest.approx(1 / 19)
    assert 'five' not in [w['normalized_text'] for w in result.words]
    six = result.words[4]
    assert (six['normalized_text'], six['start_ms'], six['end_ms']) == ('six', 1600, 2000)


def test_ratio_above_threshold_raises_aligner_error(align_env):
    heard = [text for text in TEN if text != 'five']
    aligner, _ = make_aligner(align_env, spoken(heard), max_ratio=0.05)
    with pytest.raises(AlignerError) as caught:
        aligner.align(make_request(align_env, TEN_TEXT))
    assert caught.value.code == 'alignment_unmatched_ratio_exceeded' and caught.value.retryable is False
    assert aligner.last_report.missing_script_indices == (4,)


def test_extra_transcribed_word_is_counted(align_env):
    heard = TEN[:2] + ['uh'] + TEN[2:]
    aligner, _ = make_aligner(align_env, spoken(heard), max_ratio=0.1)
    result = aligner.align(make_request(align_env, TEN_TEXT))
    assert len(result.words) == 10
    assert aligner.last_report.extra_transcript_indices == (2,)
    assert aligner.last_report.unmatched_ratio == pytest.approx(1 / 21)


def test_punctuation_only_model_words_are_ignored(align_env):
    segments = [segment(0.0, 1.0, [word(' -', 0.0, 0.1), word(' alpha', 0.1, 0.5), word(' ...', 0.5, 0.6), word(' beta', 0.6, 1.0)])]
    aligner, _ = make_aligner(align_env, segments)
    result = aligner.align(make_request(align_env, 'alpha beta'))
    assert len(result.words) == 2
    assert aligner.last_report.transcript_word_count == 2 and aligner.last_report.unmatched_ratio == 0.0


def test_overlap_zero_length_and_overrun_are_bounded_not_invented(align_env):
    segments = [segment(0.0, 9.0, [word(' alpha', 0.0, 1.0), word(' beta', 0.9, 1.5), word(' gamma', 1.5, 1.5), word(' delta', 1.6, 9.0)])]
    aligner, _ = make_aligner(align_env, segments, max_ratio=0.3)
    result = aligner.align(make_request(align_env, 'alpha beta gamma delta', duration_ms=3000))
    assert [(w['normalized_text'], w['start_ms'], w['end_ms']) for w in result.words] == [('alpha', 0, 1000), ('beta', 1000, 1500), ('delta', 1600, 3000)]
    assert aligner.last_report.missing_script_indices == (2,) and aligner.last_report.extra_transcript_indices == (2,)
    assert result.segment_boundaries == ({'start_ms': 0, 'end_ms': 3000},)


def test_nothing_matched_raises_without_inventing_times(align_env):
    aligner, _ = make_aligner(align_env, spoken(['zzz']), max_ratio=1.0)
    with pytest.raises(AlignerError) as caught:
        aligner.align(make_request(align_env, 'alpha beta'))
    assert caught.value.code == 'no_aligned_words'


def test_confidence_is_clamped_to_unit_interval(align_env):
    segments = [segment(0.0, 1.0, [word(' alpha', 0.0, 0.5, 1.4), word(' beta', 0.5, 1.0, -0.2)])]
    result = make_aligner(align_env, segments)[0].align(make_request(align_env, 'alpha beta'))
    assert [w['confidence'] for w in result.words] == [1.0, 0.0]


def expect_aligner_error(aligner, request, code):
    with pytest.raises(AlignerError) as caught:
        aligner.align(request)
    assert caught.value.code == code and caught.value.retryable is False
    return caught.value


@pytest.mark.parametrize('name', sorted(MODEL_FILES))
def test_model_sha256_mismatch_and_missing_file_are_rejected(align_env, name):
    (align_env.model_dir / name).write_bytes(b'tampered')
    aligner, factory = make_aligner(align_env, HELLO_SEGMENTS)
    expect_aligner_error(aligner, make_request(align_env, HELLO_TEXT), 'weights_sha256_mismatch')
    (align_env.model_dir / name).unlink()
    expect_aligner_error(make_aligner(align_env, HELLO_SEGMENTS)[0], make_request(align_env, HELLO_TEXT), 'weights_missing')
    assert factory.calls == []


def test_unpinned_lock_is_rejected(align_env):
    write_lock(align_env.lock, 'faster-whisper-small.en', MODEL_FILES, pinned=False)
    aligner, factory = make_aligner(align_env, HELLO_SEGMENTS)
    expect_aligner_error(aligner, make_request(align_env, HELLO_TEXT), 'weights_unpinned')
    assert factory.calls == []


def test_model_inside_git_tree_is_rejected(align_env):
    config = WhisperAlignerConfig(
        model_dir=REPO_ROOT / 'models-test-only', lock_path=align_env.lock, resolve_audio=lambda ref: align_env.voice,
        tokenization_policy=POLICY, max_unmatched_word_ratio=0.2,
    )
    factory = WhisperFactory(FakeWhisperModel(HELLO_SEGMENTS))
    expect_aligner_error(RealWhisperAligner(config, model_factory=factory), make_request(align_env, HELLO_TEXT), 'weights_in_git_tree')
    assert factory.calls == []


def test_voice_hash_mismatch_and_missing_voice_are_rejected(align_env):
    aligner, factory = make_aligner(align_env, HELLO_SEGMENTS)
    expect_aligner_error(aligner, make_request(align_env, HELLO_TEXT, voice_hash='0' * 64), 'voice_hash_mismatch')
    config = WhisperAlignerConfig(
        model_dir=align_env.model_dir, lock_path=align_env.lock, resolve_audio=lambda ref: align_env.model_dir / 'nope.wav',
        tokenization_policy=POLICY, max_unmatched_word_ratio=0.2,
    )
    expect_aligner_error(RealWhisperAligner(config, model_factory=factory), make_request(align_env, HELLO_TEXT), 'voice_unavailable')
    assert factory.calls == []


def test_runtime_error_is_redacted(align_env):
    model = FakeWhisperModel([], error=RuntimeError('oops access_token=abc123secret hunter2 ' + str(align_env.model_dir)))
    aligner, _ = make_aligner(align_env, [], model=model, known_secrets=('hunter2',))
    error = expect_aligner_error(aligner, make_request(align_env, HELLO_TEXT), 'aligner_runtime_error')
    assert '[REDACTED]' in error.message
    for leaked in ('abc123secret', 'hunter2', str(align_env.model_dir)):
        assert leaked not in error.message


def test_aligner_config_rejects_invalid_values(align_env):
    base = dict(model_dir=align_env.model_dir, lock_path=align_env.lock, resolve_audio=lambda ref: align_env.voice, tokenization_policy=POLICY, max_unmatched_word_ratio=0.2)
    with pytest.raises(ValueError):
        WhisperAlignerConfig(**{**base, 'max_unmatched_word_ratio': 1.5})
    with pytest.raises(ValueError):
        WhisperAlignerConfig(**{**base, 'model_dir': Path('relative')})
    with pytest.raises(TimingPolicyRejected):
        WhisperAlignerConfig(**{**base, 'tokenization_policy': TokenizationPolicy()})


FORBIDDEN_ROOTS = {'socket', 'urllib', 'http', 'requests', 'httpx', 'aiohttp', 'ftplib', 'google', 'openai', 'huggingface_hub', 'subprocess'}
SOURCES = [Path(tts_module.__file__), Path(aligner_module.__file__)]


@pytest.mark.parametrize('path', SOURCES, ids=lambda path: path.name)
def test_adapter_source_has_no_network_gemini_or_src_prefix(path):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    roots = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    roots |= {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not roots & FORBIDDEN_ROOTS
    assert 'gemini' not in text.casefold()
    assert 'from src.' not in text and 'import src.' not in text
    assert 'sha256' in text


def test_adapters_use_the_chosen_libraries_locally():
    tts_text = SOURCES[0].read_text(encoding='utf-8')
    aligner_text = SOURCES[1].read_text(encoding='utf-8')
    assert 'kokoro_onnx' in tts_text
    assert 'faster_whisper' in aligner_text and 'word_timestamps=True' in aligner_text and 'local_files_only=True' in aligner_text
    assert 'faster_whisper.vad' in aligner_text and 'get_speech_timestamps' in aligner_text and 'vad_filter=False' in aligner_text and 'condition_on_previous_text=False' in aligner_text
