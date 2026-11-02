"""ADAPT-E-FIX9: align hears again the audio around a clause the first pass skipped; Whisper is faked behind model_factory.

coveredIds: CT-SUB-001
"""
from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path
from types import SimpleNamespace

from voice.adapters.real_whisper_aligner import RealWhisperAligner, WhisperAlignerConfig
from voice.ports.aligner import AlignmentRequest

_path = Path(__file__).with_name('test_adapt_e_aligner_numbers.py')
_spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_fix9', _path)
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
word, spans, assert_contract = numbers.word, numbers.spans, numbers.assert_contract

CLIP = [[5.8, 9.8]]
DURATION_MS = 16000


def heard(text, start_ms, end_ms):
    return word(' ' + text, start_ms / 1000, end_ms / 1000)


def frame(clause_size):
    step = 3200 // clause_size
    words = [heard(f'w{i}', i * 200, i * 200 + 200) for i in range(31)]
    words += [heard(f'c{k}', 6200 + k * step, 6200 + (k + 1) * step) for k in range(clause_size)]
    words += [heard(f'w{i}', 9400 + (i - 31) * 200, 9600 + (i - 31) * 200) for i in range(31, 59)]
    text = ' '.join(w.word.strip() for w in words)
    return text, words, [w for w in words if not w.word.startswith(' c')]


class SkippingModel:
    def __init__(self, first, second, fails=False):
        self.first, self.second, self.fails = first, second, fails
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        clip = kwargs.get('clip_timestamps')
        words = self.first
        if clip is not None:
            if self.fails:
                raise RuntimeError('second pass failed')
            words = [w for w in self.second if clip[0] <= w.start and w.end <= clip[1]]
        segment = SimpleNamespace(start=0.0, end=max((w.end for w in words), default=0.0), words=words)
        return iter([segment]), SimpleNamespace(language='en')

    @property
    def clips(self):
        return [call['clip_timestamps'] for call in self.calls if 'clip_timestamps' in call]


def run(tmp_path, text, model, max_ratio):
    model_dir = tmp_path / 'whisper'
    model_dir.mkdir()
    entries = []
    for name, data in numbers.MODEL_FILES.items():
        (model_dir / name).write_bytes(data)
        entries.append({'name': name, 'group': 'faster-whisper-small.en', 'sha256': numbers.sha(data), 'status': 'PINNED'})
    lock = tmp_path / 'lock.json'
    lock.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')
    voice = tmp_path / 'voice.wav'
    with wave.open(str(voice), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(2 * 16 * DURATION_MS))
    config = WhisperAlignerConfig(model_dir=model_dir, lock_path=lock, resolve_audio=lambda ref: voice, tokenization_policy=numbers.POLICY, max_unmatched_word_ratio=max_ratio)
    aligner = RealWhisperAligner(config, model_factory=lambda directory, device, compute_type: model, speech_detector=lambda path: [])
    voice_hash = numbers.sha(voice.read_bytes())
    request = AlignmentRequest(voice_artifact_ref='voice-artifact-1', voice_hash=voice_hash, voice_duration_ms=DURATION_MS, script_version_id='sv-1', script_text=text, expected_language='en-US')
    result = aligner.align(request)
    payload = {'script_version_id': 'sv-1', 'script_fingerprint': 'a' * 64, 'voice_hash': voice_hash, 'timing_artifact_ref': 'timing-1', 'words': [dict(w) for w in result.words], 'segment_boundaries': [dict(b) for b in result.segment_boundaries], 'validation_report_ref': 'report-1', 'voice_duration_ms': DURATION_MS}
    return result, aligner, payload


def test_skipped_clause_is_heard_again_in_its_window(tmp_path):
    text, words, first = frame(10)
    model = SkippingModel(first, words)
    result, aligner, payload = run(tmp_path, text, model, 0.05)
    assert model.clips == CLIP
    call = model.calls[1]
    assert call['language'] == 'en' and call['word_timestamps'] is True and call['vad_filter'] is False and call['condition_on_previous_text'] is False
    assert 'initial_prompt' not in call and 'hotwords' not in call
    clause = [(n, s, e) for n, s, e in spans(result) if n.startswith('c')]
    assert clause == [(f'c{k}', 6200 + k * 320, 6520 + k * 320) for k in range(10)]
    assert len(result.words) == 69
    assert spans(result)[:31] == [(f'w{i}', i * 200, i * 200 + 200) for i in range(31)]
    report = aligner.last_report
    assert report.relisten_count == 1 and report.missing_script_indices == () and report.split_group_count == 0
    assert report.unmatched_ratio == 0.0
    assert_contract(text, payload)


def test_second_pass_that_hears_nothing_new_keeps_the_first_pass(tmp_path):
    text, words, first = frame(10)
    model = SkippingModel(first, first)
    result, aligner, payload = run(tmp_path, text, model, 1.0)
    assert model.clips == CLIP
    report = aligner.last_report
    assert report.relisten_count == 0 and report.missing_script_indices == tuple(range(31, 41))
    assert [n for n, s, e in spans(result) if n.startswith('c')] == []
    assert len(result.words) == 59
    assert_contract(text, payload, complete=False)


def test_failed_second_pass_keeps_the_first_pass(tmp_path):
    text, words, first = frame(10)
    model = SkippingModel(first, words, fails=True)
    result, aligner, payload = run(tmp_path, text, model, 1.0)
    assert model.clips == CLIP
    report = aligner.last_report
    assert report.relisten_count == 0 and report.missing_script_indices == tuple(range(31, 41))
    assert len(result.words) == 59
    assert_contract(text, payload, complete=False)


def test_runs_of_four_words_or_less_are_not_heard_again(tmp_path):
    text, words, first = frame(4)
    model = SkippingModel(first, words)
    result, aligner, payload = run(tmp_path, text, model, 0.05)
    assert model.clips == []
    report = aligner.last_report
    assert report.relisten_count == 0 and report.missing_script_indices == ()
    assert len(result.words) == 63
