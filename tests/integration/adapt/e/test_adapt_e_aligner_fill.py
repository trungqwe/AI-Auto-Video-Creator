"""ADAPT-E-FIX8: script words still without a time after every rule take the span between the two timed words around them; Whisper is faked behind model_factory and the VAD behind speech_detector, nothing is patched.

coveredIds: CT-SUB-001
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from voice.ports.aligner import AlignerError

_path = Path(__file__).with_name('test_adapt_e_aligner_numbers.py')
_spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_fix8', _path)
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
word, run_align, spans, assert_contract = numbers.word, numbers.run_align, numbers.spans, numbers.assert_contract

RUN = 'sociedad espanola de biologia del desarrollo'


def heard(text, start_ms, end_ms, probability=0.9):
    return word(' ' + text, start_ms / 1000, end_ms / 1000, probability)


def frame(run):
    words = [heard(f'w{i}', i * 100, i * 100 + 100) for i in range(60)]
    words += [heard('so', 6000, 6300, 0.4), heard('see', 6300, 6600, 0.4), heard('dad', 6600, 6900, 0.4)]
    words += [heard(f'w{i}', 6900 + (i - 60) * 100, 7000 + (i - 60) * 100) for i in range(60, 114)]
    text = ' '.join([*(f'w{i}' for i in range(60)), run, *(f'w{i}' for i in range(60, 114))])
    return text, words


def test_six_word_run_takes_the_time_between_its_neighbours(tmp_path):
    text, words = frame(RUN)
    result, aligner, payload = run_align(tmp_path, text, words, max_ratio=0.05, duration_ms=13000)
    filled = [w for w in result.words if w['confidence'] == 0.0]
    assert [w['normalized_text'] for w in filled] == RUN.split()
    assert filled[0]['start_ms'] == 6000 and filled[-1]['end_ms'] == 6900
    assert len(result.words) == 120
    report = aligner.last_report
    assert report.missing_script_indices == ()
    assert report.split_group_count == 1 and report.split_word_count == 6
    assert report.unmatched_ratio == pytest.approx(9 / 237)
    assert_contract(text, payload)


def test_filled_words_still_count_as_unmatched(tmp_path):
    text, words = frame(RUN)
    with pytest.raises(AlignerError) as caught:
        run_align(tmp_path, text, words, max_ratio=0.03, duration_ms=13000)
    assert caught.value.code == 'alignment_unmatched_ratio_exceeded'
    assert caught.value.retryable is False


def test_more_missing_words_than_the_cap_stay_missing(tmp_path):
    text, words = frame(RUN + ' sevilla')
    result, aligner, payload = run_align(tmp_path, text, words, max_ratio=0.05, duration_ms=13000)
    report = aligner.last_report
    assert report.missing_script_indices == tuple(range(60, 67))
    assert report.split_group_count == 0
    assert all(w['confidence'] != 0.0 for w in result.words)
    assert_contract(text, payload, complete=False)


def test_number_run_without_room_shares_the_word_before(tmp_path):
    words = []
    clock = 0
    for i in range(60):
        length = 300 if i == 39 else 100
        words.append(heard(f'w{i}', clock, clock + length))
        clock += length
    text = ' '.join([*(f'w{i}' for i in range(40)), 'nineteen eighty-four', *(f'w{i}' for i in range(40, 60))])
    result, aligner, payload = run_align(tmp_path, text, words)
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert by_word['w39'][0] == 3900 and by_word['eighty-four'][1] == 4200
    report = aligner.last_report
    assert report.missing_script_indices == () and report.split_group_count == 1
    assert_contract(text, payload)
