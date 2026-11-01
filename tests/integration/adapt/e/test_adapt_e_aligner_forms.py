"""ADAPT-E-FIX4: RealWhisperAligner.align rejoins Whisper pieces into one script token and shares one heard span across an amount cluster of the same value and unit; Whisper is faked behind model_factory and the VAD behind speech_detector, nothing is patched."""
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


def case(x, P):
    text = f'they saw {x} birds.'
    items = [' they', ' saw', *P, ' birds.']
    return text, [word(*t) if isinstance(t, tuple) else word(t, k / 2, (k + 1) / 2) for k, t in enumerate(items)]


def assert_matched(tmp_path, x, P, split):
    text, heard = case(x, P)
    result, aligner, payload = run_align(tmp_path, text, heard)
    report = aligner.last_report
    assert report.missing_script_indices == () and report.extra_transcript_indices == ()
    assert report.split_word_count == split
    assert_contract(text, payload)


@pytest.mark.parametrize('x, P', [
    ('long-term', [' long', '-term']),
    ('well-known state-run', [' well', '-known', ' state', '-run']),
    ('COVID-19', [' COVID', '-19']),
    ('nine-year-old', [' 9', '-year', '-old']),
    ('200,000', [' 200', ',000']),
    ('$3.5', [' $3', '.5']),
])
def test_pieces_rejoin(tmp_path, x, P):
    assert_matched(tmp_path, x, P, 0)


@pytest.mark.parametrize('x, P, split', [
    ('two hundred thousand', [' 200', ',000'], 3),
    ('three point five million dollars', [' $3', '.5', (' million', 1.75, 2.125)], 5),
    ('five dollars', [' $5'], 2),
    ('twenty-five percent', [' 25', '%'], 2),
    ('one point two trillion dollars', [' $1', '.2', ' trillion'], 5),
    ('$0.50', [' fifty', ' cents'], 0),
])
def test_amount_cluster(tmp_path, x, P, split):
    assert_matched(tmp_path, x, P, split)


@pytest.mark.parametrize('x, P, missing', [
    ('fifty percent', [' 50'], (2, 3)),
    ('five dollars', [' 5%'], (2, 3)),
    ('two hundred thousand', [' 200', ',500'], (2, 3, 4)),
    ('$1,500', [' $1', '.00,', ' $500'], (2,)),
])
def test_amounts_differ(tmp_path, x, P, missing):
    text, heard = case(x, P)
    result, aligner, payload = run_align(tmp_path, text, heard)
    report = aligner.last_report
    assert report.missing_script_indices == missing
    assert report.split_word_count == 0
    assert_contract(text, payload, complete=False)


def test_amount_without_room(tmp_path):
    text = 'they saw five dollars birds.'
    heard = [word(' they', 0.0, 0.5), word(' saw', 0.5, 1.0), word(' $5', 1.0, 1.0), word(' birds.', 1.0, 1.5)]
    result, aligner, payload = run_align(tmp_path, text, heard)
    report = aligner.last_report
    assert report.missing_script_indices == (2, 3) and report.extra_transcript_indices == (2,)
    assert report.split_word_count == 0
    assert_contract(text, payload, complete=False)


@pytest.mark.parametrize('n', [38, 37])
def test_forms_split_counts_one_group(tmp_path, n):
    names = [f'w{k}' for k in range(n)]
    text = ' '.join(names) + ' five dollars'
    heard = steps(names, step=0.1) + [word(' $5', n / 10, n / 10 + 0.5)]
    result, aligner, payload = run_align(tmp_path, text, heard, max_ratio=0.05)
    assert aligner.last_report.split_word_count == 2 and aligner.last_report.split_group_count == 1


@pytest.mark.parametrize('n', [34, 33])
def test_forms_split_groups_capped(tmp_path, n):
    names = [f'w{k}' for k in range(n)]
    text = ' '.join(names) + ' five dollars s0 five dollars s1'
    cursor = n / 10
    heard = steps(names, step=0.1) + [
        word(' $5', cursor, cursor + 0.5), word(' s0', cursor + 0.5, cursor + 0.6),
        word(' $5', cursor + 0.6, cursor + 1.1), word(' s1', cursor + 1.1, cursor + 1.2),
    ]
    if n == 34:
        result, aligner, payload = run_align(tmp_path, text, heard, max_ratio=0.05)
        assert aligner.last_report.split_word_count == 4 and aligner.last_report.split_group_count == 2
    else:
        with pytest.raises(AlignerError) as caught:
            run_align(tmp_path, text, heard, max_ratio=0.05)
        assert caught.value.code == 'alignment_split_ratio_exceeded' and caught.value.retryable is False
