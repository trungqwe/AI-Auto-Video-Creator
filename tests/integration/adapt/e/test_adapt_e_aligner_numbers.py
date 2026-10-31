"""ADAPT-E-FIX3: RealWhisperAligner.align shares one heard span between a script number group and a heard number group of the same value; Whisper is faked behind model_factory and the VAD behind speech_detector, nothing is patched."""
from __future__ import annotations

import hashlib
import json
import wave
from types import SimpleNamespace

import pytest

from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig
from voice.domain.timing_coverage import TokenizationPolicy, check_coverage
from voice.domain.word_timing import validate_word_timing, word_timing_issues
from voice.ports.aligner import AlignerError, AlignmentRequest

POLICY = TokenizationPolicy(revision='adapt-e-numbers-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',), gap_tolerance_ms=500, min_confidence=0.5)
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


def run_align(tmp_path, text, words, runs=(), *, max_ratio=1.0, duration_ms=12000):
    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    for name, data in MODEL_FILES.items():
        (model_dir / name).write_bytes(data)
    lock = tmp_path / 'lock.json'
    entries = [{'name': name, 'group': 'faster-whisper-small.en', 'sha256': sha(data), 'status': 'PINNED'} for name, data in MODEL_FILES.items()]
    lock.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')
    voice = tmp_path / 'voice.wav'
    with wave.open(str(voice), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(2 * 16000 * duration_ms // 1000))
    config = WhisperAlignerConfig(model_dir=model_dir, lock_path=lock, resolve_audio=lambda ref: voice, tokenization_policy=POLICY, max_unmatched_word_ratio=max_ratio)
    aligner = RealWhisperAligner(config, model_factory=lambda directory, device, compute_type: FakeModel(words), speech_detector=lambda path: list(runs))
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


LEROY = 'Leroy tracked one hundred fifty-six people.'
LEROY_COMMA = 'Leroy tracked one hundred fifty-six, people.'
HEARD_156 = [word(' Leroy', 0.0, 0.5), word(' tracked', 0.5, 1.0), word(' 156', 1.0, 2.9, 0.8), word(' people.', 2.9, 3.4)]
SHARED = [('one', 1000, 1300), ('hundred', 1300, 2000), ('fifty-six', 2000, 2900)]


@pytest.mark.parametrize('runs', [[], [(0, 3400)]], ids=['no-runs', 'one-run'])
def test_number_words_share_heard_numeral(tmp_path, runs):
    result, aligner, payload = run_align(tmp_path, LEROY, HEARD_156, runs)
    assert spans(result) == [('leroy', 0, 500), ('tracked', 500, 1000), *SHARED, ('people', 2900, 3400)]
    assert [w['confidence'] for w in result.words[2:5]] == [0.8, 0.8, 0.8]
    report = aligner.last_report
    assert report.missing_script_indices == () and report.extra_transcript_indices == () and report.unmatched_ratio == 0.0
    assert report.split_word_count == 3
    assert_contract(LEROY, payload)


def test_number_words_share_heard_numeral_with_trailing_comma(tmp_path):
    result, aligner, payload = run_align(tmp_path, LEROY_COMMA, HEARD_156, [])
    assert spans(result)[2:5] == SHARED
    report = aligner.last_report
    assert report.missing_script_indices == () and report.extra_transcript_indices == ()
    assert report.split_word_count == 3
    assert_contract(LEROY_COMMA, payload)


def test_numeral_without_room_not_split(tmp_path):
    heard = [word(' Leroy', 0.0, 0.5), word(' tracked', 0.5, 0.8), word(' 156', 1.0, 1.0, 0.8), word(' people.', 1.0, 3.4)]
    result, aligner, payload = run_align(tmp_path, LEROY, heard, [(0, 3400)])
    report = aligner.last_report
    assert report.missing_script_indices == (2, 3, 4) and report.extra_transcript_indices == (2,)
    assert report.split_word_count == 0
    assert_contract(LEROY, payload, complete=False)  # three number words are missing by design, only boundary validity is asserted


def test_numeral_takes_heard_number_words(tmp_path):
    text = 'Leroy tracked 156 people.'
    heard = [word(' Leroy', 0.0, 0.5), word(' tracked', 0.5, 1.0), word(' one', 1.0, 1.3), word(' hundred', 1.3, 2.0), word(' fifty', 2.0, 2.4, 0.7), word('-six', 2.4, 2.9), word(' people.', 2.9, 3.4)]
    result, aligner, payload = run_align(tmp_path, text, heard, [(0, 3400)])
    numeral = [w for w in result.words if w['normalized_text'] == '156']
    assert [(w['start_ms'], w['end_ms'], w['confidence']) for w in numeral] == [(1000, 2900, 0.7)]
    report = aligner.last_report
    assert report.missing_script_indices == () and report.extra_transcript_indices == ()
    assert report.split_word_count == 0
    assert_contract(text, payload)


@pytest.mark.parametrize('x, y, matched', [
    ('one hundred and fifty-six', '156', True),
    ('two thousand twenty-six', '2026', True),
    ('twenty twenty-six', '2026', True),
    ('a hundred', '100', True),
    ('1,500', 'one thousand five hundred', True),
    ('2026', 'two thousand and twenty six', True),
    ('one hundred fifty-six', '165', False),
    ('fifty percent', '50', False),
    ('about one hundred', 'around 100', False),
    ('five five', '10', False),
])
def test_number_forms(tmp_path, x, y, matched):
    text = f'they saw {x} birds.'
    result, aligner, payload = run_align(tmp_path, text, steps(['they', 'saw', *y.split(), 'birds.'], step=0.5))
    report = aligner.last_report
    if matched:
        assert report.missing_script_indices == () and report.extra_transcript_indices == ()
        assert_contract(text, payload)
    else:
        assert set(range(2, 2 + len(x.split()))) <= set(report.missing_script_indices)
        assert report.split_word_count == 0


@pytest.mark.parametrize('n, a, b', [(57, 5.7, 7.6), (56, 5.6, 7.5)])
def test_split_capped(tmp_path, n, a, b):
    names = [f'w{k}' for k in range(n)]
    text = ' '.join(names) + ' one hundred fifty-six'
    heard = steps(names, step=0.1) + [word(' 156', a, b)]
    if n == 57:
        result, aligner, payload = run_align(tmp_path, text, heard, max_ratio=0.05)
        assert aligner.last_report.split_word_count == 3
    else:
        with pytest.raises(AlignerError) as caught:
            run_align(tmp_path, text, heard, max_ratio=0.05)
        assert caught.value.code == 'alignment_split_ratio_exceeded' and caught.value.retryable is False
