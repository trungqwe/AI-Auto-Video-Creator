"""ADAPT-E-FIX1: RealWhisperAligner.align recovers word coverage from model times and snaps sentence edges to speech runs; Whisper is faked behind model_factory and the VAD at the faster_whisper.vad boundary."""
from __future__ import annotations

import hashlib
import json
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig
from voice.domain.timing_coverage import TokenizationPolicy, check_coverage
from voice.domain.word_timing import validate_word_timing, word_timing_issues
from voice.ports.aligner import AlignerError, AlignmentRequest

POLICY = TokenizationPolicy(revision='adapt-e-edges-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
MODEL_FILES = {'config.json': b'{}', 'model.bin': b'fake-whisper-model'}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word(text, start, end, probability=0.9):
    return SimpleNamespace(word=text, start=start, end=end, probability=probability)


def steps(texts, step=0.4):
    return [word(' ' + text, index * step, (index + 1) * step) for index, text in enumerate(texts)]


class FakeModel:
    def __init__(self, words):
        self.words = words

    def transcribe(self, audio, **kwargs):
        segment = SimpleNamespace(start=0.0, end=self.words[-1].end, words=self.words)
        return iter([segment]), SimpleNamespace(language='en')


def vad_returning(runs):
    return lambda audio, vad_options=None, sampling_rate=16000, **kwargs: [{'start': on * 16, 'end': off * 16} for on, off in runs]


def run_align(tmp_path, monkeypatch, text, words, runs, *, duration_ms=12000, rate=16000, channels=1, **aligner_kwargs):
    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    for name, data in MODEL_FILES.items():
        (model_dir / name).write_bytes(data)
    lock = tmp_path / 'lock.json'
    entries = [{'name': name, 'group': 'faster-whisper-small.en', 'sha256': sha(data), 'status': 'PINNED'} for name, data in MODEL_FILES.items()]
    lock.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')
    voice = tmp_path / 'voice.wav'
    with wave.open(str(voice), 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(2 * channels * rate * duration_ms // 1000))
    if runs is not None:
        monkeypatch.setattr('faster_whisper.vad.get_speech_timestamps', runs if callable(runs) else vad_returning(runs))
    config = WhisperAlignerConfig(model_dir=model_dir, lock_path=lock, resolve_audio=lambda ref: voice, tokenization_policy=POLICY, max_unmatched_word_ratio=1.0)
    aligner = RealWhisperAligner(config, model_factory=lambda directory, device, compute_type: FakeModel(words), **aligner_kwargs)
    voice_hash = sha(voice.read_bytes())
    request = AlignmentRequest(voice_artifact_ref='voice-artifact-1', voice_hash=voice_hash, voice_duration_ms=duration_ms, script_version_id='sv-1', script_text=text, expected_language='en-US')
    result = aligner.align(request)
    payload = {
        'script_version_id': 'sv-1', 'script_fingerprint': 'a' * 64, 'voice_hash': voice_hash, 'timing_artifact_ref': 'timing-1',
        'words': [dict(w) for w in result.words], 'segment_boundaries': [dict(b) for b in result.segment_boundaries],
        'validation_report_ref': 'report-1', 'voice_duration_ms': duration_ms,
    }
    return result, aligner, payload


def spans(result):
    return [(w['normalized_text'], w['start_ms'], w['end_ms']) for w in result.words]


def assert_contract(text, payload, *, complete=True):
    assert word_timing_issues(payload) == ()
    if complete:
        assert check_coverage(text, validate_word_timing(payload).words, POLICY).complete


def test_zero_length_sentence_start_gets_vad_onset_and_model_end(tmp_path, monkeypatch):
    text = 'Station. Commuters recharged'
    words = [word(' Station.', 5.92, 6.48), word(' Commuters', 7.28, 7.28), word(' recharged', 7.28, 8.00)]
    result, aligner, payload = run_align(tmp_path, monkeypatch, text, words, [(0, 6620), (7140, 11180)])
    assert spans(result) == [('station', 0, 6620), ('commuters', 7140, 7280), ('recharged', 7280, 11180)]
    assert aligner.last_report.missing_script_indices == ()
    assert_contract(text, payload)


@pytest.mark.parametrize('words, runs', [
    ([word(' one', 1.0, 1.5), word(' two', 2.0, 2.0), word(' three', 2.5, 3.0)], [(1000, 1600)]),
], ids=['no-run-contains-t-minus-1'])
def test_zero_length_word_without_speech_evidence_stays_unmatched(tmp_path, monkeypatch, words, runs):
    result, aligner, payload = run_align(tmp_path, monkeypatch, 'one two three', words, runs)
    assert aligner.last_report.missing_script_indices == (1,)
    assert 'two' not in [w['normalized_text'] for w in result.words]
    assert_contract('one two three', payload, complete=False)  # the word is missing by design, so only boundary validity is asserted


def test_zero_length_word_ending_with_the_word_before_shares_its_span(tmp_path, monkeypatch):
    words = [word(' one', 1.0, 1.5), word(' two', 1.5, 1.5), word(' three', 1.5, 2.0)]
    result, aligner, payload = run_align(tmp_path, monkeypatch, 'one two three', words, [(800, 2200)])
    assert [w['normalized_text'] for w in result.words] == ['one', 'two', 'three']
    assert aligner.last_report.missing_script_indices == ()
    assert aligner.last_report.split_group_count == 1
    assert_contract('one two three', payload)


def test_spelling_variant_split_compound_and_numeral_take_model_times(tmp_path, monkeypatch):
    text = 'They counted thirty new multiyear grants for localized programs'
    heard = ['They', 'counted', '30', 'new', 'multi', '-year', 'grants', 'for', 'localised', 'programs']
    result, aligner, payload = run_align(tmp_path, monkeypatch, text, steps(heard), [])
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert (by_word.get('thirty'), by_word.get('multiyear'), by_word.get('localized')) == ((800, 1200), (1600, 2400), (3200, 3600))
    assert aligner.last_report.missing_script_indices == ()
    assert [w['text'] for w in result.words] == text.split()
    assert_contract(text, payload)


@pytest.mark.parametrize('runs, expected', [
    ([(400, 1300), (1900, 2600)], [('one', 400, 1300), ('two', 1900, 2600)]),
    ([(400, 2300)], [('one', 400, 2000), ('two', 2000, 2300)]),
], ids=['offset-before-next-word', 'offset-past-next-word'])
def test_sentence_end_extends_to_speech_offset_bounded_by_next_word(tmp_path, monkeypatch, runs, expected):
    words = [word(' one', 0.5, 1.0), word(' two', 2.0, 2.5)]
    result, _, payload = run_align(tmp_path, monkeypatch, 'one two', words, runs)
    assert spans(result) == expected
    assert_contract('one two', payload)


@pytest.mark.parametrize('words, runs, expected', [
    ([word(' one', 1.0, 1.5), word(' two', 2.5, 3.0)], [(900, 1600), (2100, 3200)], [('one', 900, 1600), ('two', 2100, 3200)]),
    ([word(' one', 1.0, 1.5), word(' two', 1.5, 2.0)], [(1200, 3000)], [('one', 1200, 1500), ('two', 1500, 3000)]),
], ids=['onset-after-previous-end', 'onset-bounded-by-previous-end'])
def test_sentence_start_pulls_back_to_speech_onset_bounded_by_previous_word(tmp_path, monkeypatch, words, runs, expected):
    result, _, payload = run_align(tmp_path, monkeypatch, 'one two', words, runs)
    assert spans(result) == expected
    assert_contract('one two', payload)


def test_word_straddling_a_pause_takes_the_larger_speech_run(tmp_path, monkeypatch):
    words = [word(' air.', 27.62, 28.00), word(' City', 28.00, 28.80)]
    result, _, payload = run_align(tmp_path, monkeypatch, 'air City', words, [(26336, 28032), (28704, 31104)], duration_ms=32000)
    # City overlaps run 1 by 32 ms and run 2 by 96 ms: both edges are clamped into run 2
    assert spans(result) == [('air', 26336, 28000), ('city', 28704, 28800)]
    assert_contract('air City', payload)


def test_last_word_end_is_capped_by_voice_duration(tmp_path, monkeypatch):
    words = [word(' one', 1.0, 1.5), word(' two', 2.0, 2.5)]
    result, _, payload = run_align(tmp_path, monkeypatch, 'one two', words, [(1900, 5000)], duration_ms=3000)
    assert spans(result) == [('one', 1000, 1500), ('two', 1900, 3000)]
    assert payload['words'][-1]['end_ms'] <= payload['voice_duration_ms']
    assert_contract('one two', payload)


def test_default_detector_resamples_to_16k_and_uses_the_raw_silero_options(tmp_path, monkeypatch):
    calls = []

    def fake(audio, vad_options=None, sampling_rate=16000, **kwargs):
        calls.append((audio, vad_options, sampling_rate, kwargs))
        return [{'start': 200 * 16, 'end': 600 * 16}]

    result, _, payload = run_align(tmp_path, monkeypatch, 'one', [word(' one', 0.2, 0.6)], fake, duration_ms=1500, rate=24000)
    assert len(calls) == 1
    audio, options, rate, extra = calls[0]
    assert audio.dtype == np.float32 and audio.shape == (24000,) and rate == 16000 and extra == {}
    assert (options.threshold, options.min_speech_duration_ms, options.min_silence_duration_ms, options.speech_pad_ms) == (0.5, 0, 100, 0)
    assert spans(result) == [('one', 200, 600)]
    assert_contract('one', payload)


def test_default_detector_rejects_non_mono_wav_as_aligner_error(tmp_path, monkeypatch):
    with pytest.raises(AlignerError) as caught:
        run_align(tmp_path, monkeypatch, 'one', [word(' one', 0.2, 0.6)], [], duration_ms=1500, channels=2)
    assert caught.value.code == 'aligner_runtime_error' and caught.value.retryable is False


def test_detector_failure_is_a_redacted_non_retryable_runtime_error(tmp_path, monkeypatch):
    def broken(audio, vad_options=None, sampling_rate=16000, **kwargs):
        raise RuntimeError('boom api_key=SECRETVALUE123')

    with pytest.raises(AlignerError) as caught:
        run_align(tmp_path, monkeypatch, 'one', [word(' one', 0.2, 0.6)], broken, duration_ms=1500)
    error = caught.value
    assert error.code == 'aligner_runtime_error' and error.retryable is False
    assert '[REDACTED]' in error.message and 'SECRETVALUE123' not in error.message


def test_injected_speech_detector_receives_the_verified_wav_path(tmp_path, monkeypatch):
    seen = []

    def detector(path):
        seen.append(path)
        return [(0, 500)]

    result, _, payload = run_align(tmp_path, monkeypatch, 'one', [word(' one', 0.2, 0.6)], None, duration_ms=1500, speech_detector=detector)
    assert seen == [tmp_path / 'voice.wav'] and spans(result) == [('one', 0, 500)]
    assert_contract('one', payload)
