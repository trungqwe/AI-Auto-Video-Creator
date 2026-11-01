"""ADAPT-E-FIX6: a model word that ends where the word before it ends (zero-length) shares the span of that word; Whisper is faked behind model_factory and the VAD behind speech_detector, nothing is patched.

coveredIds: CT-SUB-001
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from voice.ports.aligner import AlignerError

_path = Path(__file__).with_name('test_adapt_e_aligner_numbers.py')
_spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_fix6', _path)
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
word, run_align, spans, assert_contract = numbers.word, numbers.run_align, numbers.spans, numbers.assert_contract


def test_cp7_10_zero_length_word_shares_the_word_before(tmp_path):
    text = 'national address, declaring there can be no compromise'
    words = [
        word(' national', 23.5, 24.1), word(' address,', 24.12, 24.68), word(' declaring', 24.84, 25.2),
        word(' there', 25.2, 25.6, 0.84), word(' can', 25.6, 25.6, 0.41), word(' be', 25.6, 25.74),
        word(' no', 25.74, 25.94), word(' compromise', 25.94, 26.48),
    ]
    result, aligner, payload = run_align(tmp_path, text, words, duration_ms=27000)
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert len(by_word) == 8
    assert (by_word['there'], by_word['can'], by_word['be']) == ((25200, 25450), (25450, 25600), (25600, 25740))
    assert aligner.last_report.missing_script_indices == ()
    assert aligner.last_report.split_group_count == 1
    assert aligner.last_report.split_word_count == 2
    assert_contract(text, payload)


def test_two_zero_length_words_in_a_row(tmp_path):
    words = [word(' alpha', 1.0, 1.6), word(' be', 1.6, 1.6), word(' ce', 1.6, 1.6), word(' delta', 1.6, 2.2)]
    result, aligner, payload = run_align(tmp_path, 'alpha be ce delta', words)
    assert spans(result) == [('alpha', 1000, 1428), ('be', 1428, 1514), ('ce', 1514, 1600), ('delta', 1600, 2200)]
    assert aligner.last_report.split_group_count == 2
    assert_contract('alpha be ce delta', payload)


def test_zero_length_first_word_without_speech_run_stays_unmatched(tmp_path):
    words = [word(' omega', 0.0, 0.0), word(' alpha', 0.5, 1.0)]
    result, aligner, payload = run_align(tmp_path, 'omega alpha', words)
    assert aligner.last_report.missing_script_indices == (0,)
    assert aligner.last_report.split_group_count == 0
    assert_contract('omega alpha', payload, complete=False)


@pytest.mark.parametrize('max_ratio, passes', [(0.05, False), (0.1, True)])
def test_zero_length_groups_count_under_the_cap(tmp_path, max_ratio, passes):
    words = []
    for n in range(18):
        words.append(word(f' w{n}', n * 0.1, (n + 1) * 0.1))
        if n in (5, 12):
            words.append(word(f' z{n}', (n + 1) * 0.1, (n + 1) * 0.1))
    text = ' '.join(w.word.strip() for w in words)
    if passes:
        result, aligner, payload = run_align(tmp_path, text, words, max_ratio=max_ratio)
        assert aligner.last_report.split_group_count == 2
        assert aligner.last_report.missing_script_indices == ()
    else:
        with pytest.raises(AlignerError) as caught:
            run_align(tmp_path, text, words, max_ratio=max_ratio)
        assert caught.value.code == 'alignment_split_ratio_exceeded' and caught.value.retryable is False
