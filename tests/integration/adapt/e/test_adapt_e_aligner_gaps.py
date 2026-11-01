"""ADAPT-E-FIX7: a short run of script words between two matched words takes the unused heard words between them, or joins the matched word next to it; Whisper is faked behind model_factory and the VAD behind speech_detector, nothing is patched.

coveredIds: CT-SUB-001
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from voice.ports.aligner import AlignerError

_path = Path(__file__).with_name('test_adapt_e_aligner_numbers.py')
_spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_fix7', _path)
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
word, steps, run_align, spans, assert_contract = numbers.word, numbers.steps, numbers.run_align, numbers.spans, numbers.assert_contract


def test_cp7_10_acronym_and_hyphen_take_model_times(tmp_path):
    text = 'back sharply. CARICOM Reparations Commission Vice-Chair Verene Shepherd rejected the proposal,'
    words = [
        word(' back', 24.36, 24.66), word(' sharply.', 24.66, 25.12), word(' Reparations', 25.12, 26.34, 0.76), word(' Commission', 26.34, 26.76),
        word(' Vice', 26.76, 27.22), word(' Chair', 27.22, 27.6), word(' Varen', 27.6, 27.94), word(' Shepherd', 27.94, 28.34),
        word(' rejected', 28.34, 29.1), word(' the', 29.1, 29.32), word(' proposal,', 29.32, 29.88),
    ]
    result, aligner, payload = run_align(tmp_path, text, words, duration_ms=31000)
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert len(by_word) == 11
    assert (by_word['caricom'], by_word['reparations'], by_word['vice-chair'], by_word['verene']) == ((25120, 25594), (25594, 26340), (26760, 27497), (27497, 27940))
    report = aligner.last_report
    assert report.missing_script_indices == () and report.split_group_count == 2 and report.split_word_count == 4
    assert_contract(text, payload)


def test_hyphen_word_heard_as_two_words(tmp_path):
    text = 'alpha beta vice-chair gamma'
    result, aligner, payload = run_align(tmp_path, text, steps(['alpha', 'beta', 'vice', 'chair', 'gamma'], step=0.3))
    assert spans(result)[2] == ('vice-chair', 600, 1200)
    assert aligner.last_report.missing_script_indices == () and aligner.last_report.split_group_count == 0
    assert_contract(text, payload)


def test_script_word_without_heard_word_shares_the_next_word_span(tmp_path):
    text = 'alpha caricom reparations beta'
    result, aligner, payload = run_align(tmp_path, text, steps(['alpha', 'reparations', 'beta'], step=0.3))
    assert spans(result)[1:3] == [('caricom', 300, 416), ('reparations', 416, 600)]
    assert aligner.last_report.split_group_count == 1 and aligner.last_report.missing_script_indices == ()
    assert_contract(text, payload)


def test_name_heard_as_three_pieces(tmp_path):
    text = 'alpha beta verene shepherd gamma'
    result, aligner, payload = run_align(tmp_path, text, steps(['alpha', 'beta', 'varen', 'shep', 'herd', 'gamma'], step=0.3))
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert by_word['verene'][0] == 600 and by_word['shepherd'][1] == 1500
    assert aligner.last_report.split_group_count == 1 and aligner.last_report.missing_script_indices == ()
    assert_contract(text, payload)


def test_trailing_acronym_joins_the_word_before(tmp_path):
    text = 'alpha beta today MP'
    result, aligner, payload = run_align(tmp_path, text, steps(['alpha', 'beta', 'today'], step=0.3))
    by_word = {name: (start, end) for name, start, end in spans(result)}
    assert by_word['today'][0] == 600 and by_word['mp'][1] == 900
    assert aligner.last_report.split_group_count == 1 and aligner.last_report.missing_script_indices == ()
    assert_contract(text, payload)


def test_number_run_keeps_the_fix3_rule(tmp_path):
    text = 'Leroy tracked one hundred fifty-six people.'
    result, aligner, payload = run_align(tmp_path, text, steps(['Leroy', 'tracked', '165', 'people.'], step=0.3))
    assert aligner.last_report.missing_script_indices == (2, 3, 4) and aligner.last_report.split_group_count == 0
    assert_contract(text, payload, complete=False)  # the number words stay missing by design


def test_run_longer_than_four_words_stays_missing(tmp_path):
    text = 'start red green blue pink gold end'
    result, aligner, payload = run_align(tmp_path, text, steps(['start', 'noise', 'sound', 'end'], step=0.3))
    assert aligner.last_report.missing_script_indices == (1, 2, 3, 4, 5) and aligner.last_report.split_group_count == 0
    assert_contract(text, payload, complete=False)


@pytest.mark.parametrize('max_ratio, passes', [(0.05, False), (0.2, True)])
def test_gap_groups_count_under_the_cap(tmp_path, max_ratio, passes):
    heard = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel', 'india', 'juliet']
    text = 'alpha bravo charlie delta echo kilo foxtrot golf hotel lima india juliet'
    if passes:
        result, aligner, payload = run_align(tmp_path, text, steps(heard, step=0.3), max_ratio=max_ratio)
        assert aligner.last_report.split_group_count == 2 and aligner.last_report.missing_script_indices == ()
        assert_contract(text, payload)
    else:
        with pytest.raises(AlignerError) as caught:
            run_align(tmp_path, text, steps(heard, step=0.3), max_ratio=max_ratio)
        assert caught.value.code == 'alignment_split_ratio_exceeded' and caught.value.retryable is False
