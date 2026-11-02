"""ADAPT-E-FIX10: a spoken number run in the script takes the heard span of the digits Whisper wrote for the same values; Whisper is faked behind model_factory, nothing is patched.

coveredIds: CT-SUB-001
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).with_name('test_adapt_e_aligner_numbers.py')
_spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_fix10', _path)
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
word, steps, spans, run_align, assert_contract = numbers.word, numbers.steps, numbers.spans, numbers.run_align, numbers.assert_contract


def align_case(tmp_path, k, lead, spoken, pieces, **kwargs):
    names = [f'w{n}' for n in range(lead)]
    text = ' '.join([*names, spoken, 'end.'])
    heard = steps(names, step=0.1)
    cursor = lead / 10
    for piece, length in pieces:
        heard.append(word(' ' + piece, cursor, cursor + length))
        cursor += length
    heard.append(word(' end.', cursor, cursor + 0.1))
    (tmp_path / f'case{k}').mkdir()
    return (text, *run_align(tmp_path / f'case{k}', text, heard, **kwargs))


def test_score_words_share_the_span_of_the_heard_digits(tmp_path):
    text, result, aligner, payload = align_case(tmp_path, 0, 40, 'sixty-six to forty-five', [('66-45', 1.4)], max_ratio=0.05)
    assert spans(result)[40:43] == [('sixty-six', 4000, 4600), ('to', 4600, 4733), ('forty-five', 4733, 5400)]
    assert [w['confidence'] for w in result.words[40:43]] == [0.9, 0.9, 0.9]
    report = aligner.last_report
    assert report.spoken_group_count == 1 and report.split_word_count == 3 and report.split_group_count == 1
    assert report.missing_script_indices == () and report.extra_transcript_indices == () and report.unmatched_ratio == 0.0
    assert_contract(text, payload)


def test_clock_times_in_words_match_whisper_digits(tmp_path):
    cases = [('eight thirty', '8.30'), ('nine forty-five', '9.45'), ('five and oh', '5-0'), ('one hundred twenty-four to one hundred three', '124-103')]
    for k, (spoken, digits) in enumerate(cases):
        text, result, aligner, payload = align_case(tmp_path, k, 20, spoken, [(digits, 1.2)])
        group = result.words[20:20 + len(spoken.split())]
        assert [w['normalized_text'] for w in group] == spoken.split(), spoken
        assert group[0]['start_ms'] == 2000 and group[-1]['end_ms'] == 3200, spoken
        assert all(a['start_ms'] < a['end_ms'] == b['start_ms'] for a, b in zip(group, group[1:])) and group[-1]['start_ms'] < group[-1]['end_ms'], spoken
        report = aligner.last_report
        assert report.spoken_group_count == 1 and report.split_group_count == 1 and report.split_word_count == len(group), spoken
        assert report.missing_script_indices == () and report.extra_transcript_indices == (), spoken
        assert_contract(text, payload)


def test_other_values_are_not_grouped(tmp_path):
    cases = [('about one hundred', ['around', '100']), ('one hundred twenty-four to one hundred three', ['124-104']), ('five and oh', ['5-1'])]
    for k, (spoken, pieces) in enumerate(cases):
        text, result, aligner, payload = align_case(tmp_path, k, 20, spoken, [(piece, 0.5) for piece in pieces])
        report = aligner.last_report
        assert report.spoken_group_count == 0 and report.split_word_count == 0 and report.split_group_count == 0, spoken
        assert report.missing_script_indices == tuple(range(20, 20 + len(spoken.split()))), spoken
        assert report.extra_transcript_indices == tuple(range(20, 20 + len(pieces))), spoken
        assert len(result.words) == 21, spoken


def test_first_pass_within_the_gates_is_not_regrouped(tmp_path):
    text, result, aligner, payload = align_case(tmp_path, 0, 60, 'sixty-six to forty-five', [('66-45', 1.4)], max_ratio=0.05)
    report = aligner.last_report
    assert report.spoken_group_count == 0 and report.relisten_count == 0
    assert report.split_word_count == 3 and report.split_group_count == 1
    assert [w['confidence'] for w in result.words[60:63]] == [0.0, 0.0, 0.0]
    assert report.unmatched_ratio == pytest.approx(4 / 126)
