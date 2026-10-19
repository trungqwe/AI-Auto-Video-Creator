"""E-10: phủ từ, confidence và báo cáo gap theo CT-SUB-001.

coveredIds: CT-SUB-001 (phủ từ, gap, confidence)
"""
import ast
import dataclasses
import inspect
import json
import pathlib

import pytest

from voice.domain.timing_coverage import (
    INPUT_NOT_READY, AlignmentGap, CoverageReport, GapReport, LowConfidenceWord, TimingPolicyRejected,
    TokenizationPolicy, build_gap_report, check_coverage, tokenize_script,
)
from voice.domain.word_timing import WordTimingWord, validate_word_timing

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'voice' / 'domain' / 'timing_coverage.py'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
APOS = chr(0x2019)
RULE_FIELDS = ('revision', 'unicode_form', 'casefold', 'edge_strip_categories')

# test-only policy fixture (GIẢ ĐỊNH, IMPL-PLAN-E §7): giá trị policy không là hằng trong src/
POLICY = TokenizationPolicy(
    revision='test-only-en-1', unicode_form='NFC', casefold=True, edge_strip_categories=('P',),
    gap_tolerance_ms=50, min_confidence=0.6,
)


def _w(start: int, end: int, token: str | None, confidence: object = None) -> WordTimingWord:
    return WordTimingWord(start_ms=start, end_ms=end, text=token, normalized_text=token, confidence=confidence)


def _words(*tokens: str) -> list:
    return [_w(i * 10, i * 10 + 10, token) for i, token in enumerate(tokens)]


def _with(**changes: object) -> TokenizationPolicy:
    return dataclasses.replace(POLICY, **changes)


def _not_ready(call) -> str:
    with pytest.raises(TimingPolicyRejected) as info:
        call()
    assert info.value.code == INPUT_NOT_READY
    return info.value.reason


def test_policy_is_frozen_and_has_no_hidden_defaults() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        POLICY.revision = 'x'
    assert all(getattr(TokenizationPolicy(), f.name) is None for f in dataclasses.fields(TokenizationPolicy))


def test_tokenize_folds_case_and_strips_edge_punctuation() -> None:
    text = '  Breaking NEWS, (tonight): [well-known] don' + APOS + 't stop!  '
    assert tokenize_script(text, POLICY) == ('breaking', 'news', 'tonight', 'well-known', 'don' + APOS + 't', 'stop')


def test_tokenize_splits_on_any_whitespace_and_drops_punctuation_only_tokens() -> None:
    assert tokenize_script('a' + chr(9) + 'b' + chr(10) + 'c - ... d', POLICY) == ('a', 'b', 'c', 'd')
    assert tokenize_script('', POLICY) == () and tokenize_script('...', POLICY) == ()


def test_tokenize_applies_unicode_form_from_policy() -> None:
    composed, decomposed = 'caf' + chr(0xE9), 'cafe' + chr(0x301)
    assert tokenize_script(decomposed + '.', POLICY) == (composed,)
    assert tokenize_script(composed, _with(unicode_form='NFD')) == (decomposed,)


def test_tokenize_follows_casefold_and_edge_rules_of_policy() -> None:
    assert tokenize_script('News, ok', _with(casefold=False)) == ('News', 'ok')
    assert tokenize_script('News, ok', _with(edge_strip_categories=())) == ('news,', 'ok')


def test_missing_policy_is_input_not_ready() -> None:
    assert _not_ready(lambda: tokenize_script('a', None)) == 'missing_policy'
    assert _not_ready(lambda: check_coverage('a', _words('a'), None)) == 'missing_policy'


@pytest.mark.parametrize('field', RULE_FIELDS)
def test_missing_rule_field_is_input_not_ready(field: str) -> None:
    policy = _with(**{field: None})
    assert _not_ready(lambda: tokenize_script('a', policy)) == 'missing_' + field
    assert _not_ready(lambda: check_coverage('a', _words('a'), policy)) == 'missing_' + field


@pytest.mark.parametrize(
    'changes',
    [{'unicode_form': 'NFX'}, {'casefold': 1}, {'revision': ''}, {'edge_strip_categories': 'P'}, {'edge_strip_categories': ('',)}],
)
def test_malformed_rule_is_value_error(changes: dict) -> None:
    with pytest.raises(ValueError):
        tokenize_script('a', _with(**changes))


def test_wrong_argument_types_are_type_errors() -> None:
    for call in (lambda: tokenize_script(5, POLICY), lambda: tokenize_script('a', {}), lambda: check_coverage('a', 'a', POLICY)):
        with pytest.raises(TypeError):
            call()


def test_exact_words_are_complete() -> None:
    report = check_coverage('Breaking NEWS, tonight!', _words('breaking', 'news', 'tonight'), POLICY)
    assert report == CoverageReport('test-only-en-1', 3, 3, (), (), True)


def test_any_missing_word_is_not_complete() -> None:
    for gone in range(3):
        tokens = ['breaking', 'news', 'tonight']
        del tokens[gone]
        report = check_coverage('Breaking news tonight', _words(*tokens), POLICY)
        assert (report.complete, report.expected_count, report.matched_count) == (False, 3, 2)
        assert (report.missing_indices, report.extra_indices) == ((gone,), ())


def test_any_extra_word_is_detected() -> None:
    for pos in range(4):
        tokens = ['breaking', 'news', 'tonight']
        tokens.insert(pos, 'uh')
        report = check_coverage('Breaking news tonight', _words(*tokens), POLICY)
        assert (report.complete, report.matched_count) == (False, 3)
        assert (report.missing_indices, report.extra_indices) == ((), (pos,))


def test_wrong_order_is_not_complete() -> None:
    report = check_coverage('a b c', _words('a', 'c', 'b'), POLICY)
    assert (report.complete, report.matched_count) == (False, 2)
    assert (len(report.missing_indices), len(report.extra_indices)) == (1, 1)


def test_case_and_punctuation_do_not_shift_coverage() -> None:
    quoted = chr(34) + 'Hello' + chr(34) + ' -- (world)'
    for script in ('Hello, WORLD!', 'hello world', quoted, '  HELLO' + chr(10) + 'World...'):
        assert check_coverage(script, _words('hello', 'world'), POLICY).complete is True


def test_normalized_text_must_equal_token() -> None:
    cased = [_w(0, 10, 'breaking'), _w(10, 20, 'NEWS')]
    absent = [_w(0, 10, 'breaking'), _w(10, 20, None)]
    for words in (cased, absent):
        report = check_coverage('breaking news', words, POLICY)
        assert (report.complete, report.missing_indices, report.extra_indices) == (False, (1,), (1,))


def test_empty_inputs_are_never_complete() -> None:
    assert check_coverage('', [], POLICY).complete is False
    assert check_coverage('...', [], POLICY).expected_count == 0
    report = check_coverage('a b', [], POLICY)
    assert (report.complete, report.missing_indices, report.extra_indices) == (False, (0, 1), ())
    assert check_coverage('', _words('a'), POLICY).extra_indices == (0,)


def test_coverage_accepts_words_of_validated_word_timing_record() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['WordTiming']['valid'][0]
    record = validate_word_timing(payload)
    assert check_coverage('Breaking news', record.words, POLICY).complete is True
    assert check_coverage('Breaking news today', record.words, POLICY).missing_indices == (2,)


def test_report_is_frozen_and_accepts_any_iterable() -> None:
    report = check_coverage('a b', (word for word in _words('a')), POLICY)
    assert (report.missing_indices, report.extra_indices) == ((1,), ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.complete = True


def test_gaps_cover_leading_between_and_trailing_above_tolerance() -> None:
    words = [_w(200, 300, 'a'), _w(400, 500, 'b'), _w(510, 900, 'c')]
    assert build_gap_report(words, 1000, POLICY) == GapReport(
        (AlignmentGap(0, 200), AlignmentGap(300, 400), AlignmentGap(900, 1000)), ()
    )


def test_gap_threshold_comes_only_from_policy() -> None:
    words = [_w(200, 300, 'a'), _w(400, 500, 'b'), _w(510, 900, 'c')]
    assert build_gap_report(words, 1000, _with(gap_tolerance_ms=150)).alignment_gaps == (AlignmentGap(0, 200),)
    assert build_gap_report(words, 1000, _with(gap_tolerance_ms=99)).alignment_gaps[1] == AlignmentGap(300, 400)
    assert build_gap_report(words, 1000, _with(gap_tolerance_ms=100)).alignment_gaps == (AlignmentGap(0, 200),)


def test_gap_equal_to_tolerance_is_not_reported() -> None:
    assert build_gap_report([_w(50, 100, 'a')], 150, POLICY).alignment_gaps == ()
    assert build_gap_report([_w(51, 100, 'a')], 151, POLICY).alignment_gaps == (AlignmentGap(0, 51), AlignmentGap(100, 151))
    zero = _with(gap_tolerance_ms=0)
    assert build_gap_report([_w(0, 10, 'a'), _w(10, 20, 'b')], 20, zero).alignment_gaps == ()
    assert build_gap_report([_w(0, 10, 'a'), _w(11, 20, 'b')], 20, zero).alignment_gaps == (AlignmentGap(10, 11),)


def test_no_words_is_one_gap_when_voice_is_longer_than_tolerance() -> None:
    assert build_gap_report([], 1000, POLICY).alignment_gaps == (AlignmentGap(0, 1000),)
    assert build_gap_report([], 50, POLICY).alignment_gaps == ()


def test_gap_report_accepts_any_iterable_and_is_frozen() -> None:
    report = build_gap_report((word for word in [_w(0, 900, 'a')]), 1000, POLICY)
    assert report.alignment_gaps == (AlignmentGap(900, 1000),)
    assert report.alignment_gaps[0].duration_ms == 100
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.alignment_gaps = ()


def test_gap_payload_is_accepted_by_word_timing_validator() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['WordTiming']['valid'][0]
    record = validate_word_timing(payload)
    report = build_gap_report(record.words, record.voice_duration_ms, POLICY)
    assert report.alignment_gaps == (AlignmentGap(900, 65000),)
    payload['alignment_gaps'] = [gap.to_payload() for gap in report.alignment_gaps]
    assert validate_word_timing(payload).alignment_gaps == ({'start_ms': 900, 'end_ms': 65000},)


def test_low_confidence_words_use_policy_threshold() -> None:
    words = [_w(0, 10, 'a', 0.59), _w(10, 20, 'b', 0.6), _w(20, 30, 'c', None), _w(30, 40, 'd', 0), _w(40, 50, 'e', 1)]
    assert build_gap_report(words, 50, POLICY).low_confidence_words == (LowConfidenceWord(0, 0.59), LowConfidenceWord(3, 0))
    strict = build_gap_report(words, 50, _with(min_confidence=0.95)).low_confidence_words
    assert strict == (LowConfidenceWord(0, 0.59), LowConfidenceWord(1, 0.6), LowConfidenceWord(3, 0))
    assert build_gap_report(words, 50, _with(min_confidence=0)).low_confidence_words == ()


def test_gap_report_without_policy_input_is_input_not_ready() -> None:
    words = _words('a')
    assert _not_ready(lambda: build_gap_report(words, 1000, None)) == 'missing_policy'
    assert _not_ready(lambda: build_gap_report(words, 1000, TokenizationPolicy())) == 'missing_gap_tolerance_ms'
    assert _not_ready(lambda: build_gap_report(words, 1000, _with(gap_tolerance_ms=None))) == 'missing_gap_tolerance_ms'
    assert _not_ready(lambda: build_gap_report(words, 1000, _with(min_confidence=None))) == 'missing_min_confidence'
    assert _not_ready(lambda: build_gap_report(words, None, POLICY)) == 'missing_voice_duration_ms'


def test_gap_report_needs_only_gap_fields_of_policy() -> None:
    policy = TokenizationPolicy(gap_tolerance_ms=50, min_confidence=0.6)
    assert build_gap_report([_w(0, 900, 'a')], 1000, policy).alignment_gaps == (AlignmentGap(900, 1000),)


@pytest.mark.parametrize(
    'changes',
    [{'gap_tolerance_ms': -1}, {'gap_tolerance_ms': True}, {'gap_tolerance_ms': 50.0}, {'gap_tolerance_ms': '50'},
     {'min_confidence': -0.1}, {'min_confidence': 1.1}, {'min_confidence': True}, {'min_confidence': '0.5'},
     {'min_confidence': float('nan')}],
)
def test_malformed_gap_policy_is_value_error(changes: dict) -> None:
    with pytest.raises(ValueError):
        build_gap_report(_words('a'), 1000, _with(**changes))


@pytest.mark.parametrize('duration', [0, -1, True, 1.5, '1000'])
def test_malformed_voice_duration_is_value_error(duration: object) -> None:
    with pytest.raises(ValueError):
        build_gap_report(_words('a'), duration, POLICY)


def _tree() -> ast.AST:
    return ast.parse(MODULE_PATH.read_text(encoding='utf-8'))


def test_module_has_no_numeric_policy_constants() -> None:
    numbers = {
        node.value for node in ast.walk(_tree())
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    }
    assert numbers <= {0, 1}


def test_policy_parameter_has_no_default() -> None:
    for function in (tokenize_script, check_coverage, build_gap_report):
        assert inspect.signature(function).parameters['policy'].default is inspect.Parameter.empty


def test_module_imports_only_allowed_stdlib() -> None:
    allowed = {'__future__', 'difflib', 'unicodedata', 'collections.abc', 'dataclasses', 'voice.domain.word_timing'}
    imported = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed
