"""E-09: WordTiming validator theo binding BINDING-D-E-F-VOICE-TIMING (CT-SUB-001).

coveredIds: CT-SUB-001 bất biến 1
"""
import ast
import copy
import dataclasses
import json
import pathlib

import pytest

from voice.domain.word_timing import (
    BINDING_VERSION, BOUNDARY_REQUIRED, CONSTRAINT_VIOLATION, MISSING_REQUIRED, WORD_OPTIONAL, WORD_REQUIRED,
    WORD_TIMING_CONSTRAINTS, WORD_TIMING_ITEMS, WORD_TIMING_OPTIONAL, WORD_TIMING_REQUIRED, WRONG_TYPE,
    WordTimingError, WordTimingRecord, validate_word_timing, word_timing_issues,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'd-e-f-voice-timing.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'voice' / 'domain' / 'word_timing.py'
ENTITY = 'WordTiming'
DELETE = object()


def _binding_entity() -> dict:
    entities = json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']
    return next(item for item in entities if item['name'] == ENTITY)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][ENTITY]


def _valid() -> dict:
    return copy.deepcopy(_fixture()['valid'][0])


def _derive(fields: list) -> tuple:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
        {f['name']: f['items'] for f in fields if 'items' in f},
    )


def _constants() -> tuple:
    return dict(WORD_TIMING_REQUIRED), dict(WORD_TIMING_OPTIONAL), dict(WORD_TIMING_ITEMS)


def _field(fields: list, name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


def _issues(payload: object) -> list:
    return [(issue.code, issue.field) for issue in word_timing_issues(payload)]


def _word(start: object, end: object, **extra: object) -> dict:
    return {'start_ms': start, 'end_ms': end, 'text': 'w', 'normalized_text': 'w', **extra}


def _seg(start: object, end: object, **extra: object) -> dict:
    return {'start_ms': start, 'end_ms': end, **extra}


def _payload(**changes: object) -> dict:
    payload = _valid()
    for name, value in changes.items():
        if value is DELETE:
            payload.pop(name, None)
        else:
            payload[name] = value
    return payload


def test_constants_match_binding() -> None:
    assert _constants() == _derive(_binding_entity()['fields'])


def test_binding_version_and_constraints_match_binding() -> None:
    assert BINDING_VERSION == json.loads(BINDING_PATH.read_text(encoding='utf-8'))['binding_version']
    assert list(WORD_TIMING_CONSTRAINTS) == _binding_entity()['constraints']


def test_drift_comparison_detects_mutated_binding() -> None:
    expected = _constants()
    assert expected[0] and expected[1] and expected[2]
    mutations = {
        'voice_hash_optional': lambda fs: _field(fs, 'voice_hash').update(required=False),
        'duration_as_string': lambda fs: _field(fs, 'voice_duration_ms').update(type='string'),
        'duration_required': lambda fs: _field(fs, 'voice_duration_ms').update(required=True),
        'fingerprint_as_string': lambda fs: _field(fs, 'script_fingerprint').update(type='string'),
        'words_items_dropped': lambda fs: _field(fs, 'words').pop('items'),
        'required_field_added': lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True}),
    }
    for name, mutate in mutations.items():
        fields = copy.deepcopy(_binding_entity()['fields'])
        mutate(fields)
        assert _derive(fields) != expected, name

INVALID = _fixture()['invalid']


def test_fixture_has_required_cases_and_pinned_codes() -> None:
    assert (MISSING_REQUIRED, WRONG_TYPE, CONSTRAINT_VIOLATION) == ('missing_required', 'wrong_type', 'constraint_violation')
    by_case = {c['case']: (c['expected_error']['code'], c['expected_error']['field']) for c in INVALID}
    assert by_case['words_out_of_order'] == ('constraint_violation', 'words')
    assert by_case['word_beyond_voice_duration'] == ('constraint_violation', 'words')
    assert by_case['missing_voice_hash'] == ('missing_required', 'voice_hash')
    assert _fixture()['valid']


def test_fixture_valid_payloads_are_accepted() -> None:
    for payload in _fixture()['valid']:
        assert _issues(payload) == []
        assert isinstance(validate_word_timing(payload), WordTimingRecord)


@pytest.mark.parametrize('case', INVALID, ids=[case['case'] for case in INVALID])
def test_fixture_invalid_payloads_report_expected_error(case: dict) -> None:
    expected = (case['expected_error']['code'], case['expected_error']['field'])
    assert _issues(case['payload']) == [expected]
    with pytest.raises(WordTimingError) as caught:
        validate_word_timing(case['payload'])
    assert (caught.value.code, caught.value.field) == expected


def test_valid_payload_returns_record_with_fixture_values() -> None:
    payload = _valid()
    record = validate_word_timing(payload)
    assert isinstance(record, WordTimingRecord)
    for name in ('script_version_id', 'script_fingerprint', 'voice_hash', 'timing_artifact_ref', 'validation_report_ref'):
        assert getattr(record, name) == payload[name]
    assert record.voice_duration_ms == 65000
    assert [(w.start_ms, w.end_ms, w.text, w.normalized_text, w.confidence) for w in record.words] == [
        (0, 420, 'Breaking', 'breaking', 0.98),
        (420, 900, 'news', 'news', 0.97),
    ]
    assert [(b.start_ms, b.end_ms) for b in record.segment_boundaries] == [(0, 900)]
    assert record.alignment_gaps == ()


def test_record_is_frozen_and_does_not_alias_payload() -> None:
    payload = _payload(alignment_gaps=[{'start_ms': 900, 'end_ms': 950}])
    record = validate_word_timing(payload)
    assert isinstance(record, WordTimingRecord)
    assert isinstance(record.words, tuple) and isinstance(record.segment_boundaries, tuple)
    assert isinstance(record.alignment_gaps, tuple)
    for target, name in ((record, 'voice_hash'), (record.words[0], 'end_ms'), (record.segment_boundaries[0], 'end_ms')):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(target, name, 'x')
    payload['alignment_gaps'][0]['end_ms'] = 1
    payload['words'][0]['end_ms'] = 1
    assert record.alignment_gaps == ({'start_ms': 900, 'end_ms': 950},)
    assert record.words[0].end_ms == 420

V = (CONSTRAINT_VIOLATION, 'words')
T = (WRONG_TYPE, 'words')
M = (MISSING_REQUIRED, 'words')
WORD_CASES = [
    pytest.param([_word(100, 100)], [V], id='end_equals_start'),
    pytest.param([_word(200, 100)], [V], id='end_before_start'),
    pytest.param([_word(-1, 100)], [V], id='negative_start'),
    pytest.param([_word(0, 500), _word(400, 900)], [V], id='overlap'),
    pytest.param([_word(0, 500), _word(0, 500)], [V], id='duplicate_span'),
    pytest.param([_word(0, 500), _word(500, 400)], [V], id='second_word_end_before_start'),
    pytest.param([_word(0, 65001)], [V], id='end_beyond_duration'),
    pytest.param([_word(0, 420, confidence=-0.01)], [V], id='confidence_below_zero'),
    pytest.param([_word(0, 420, confidence=1.01)], [V], id='confidence_above_one'),
    pytest.param([_word(0, 420, confidence=float('nan'))], [V], id='confidence_nan'),
    pytest.param([], [V], id='empty_words'),
    pytest.param([_word(True, 420)], [T], id='start_bool'),
    pytest.param([_word(0, True)], [T], id='end_bool'),
    pytest.param([_word(0.0, 420)], [T], id='start_float'),
    pytest.param([_word(0, '420')], [T], id='end_text'),
    pytest.param([_word(0, 420, confidence=True)], [T], id='confidence_bool'),
    pytest.param([_word(0, 420, confidence='0.5')], [T], id='confidence_text'),
    pytest.param([_word(0, 420, text=5)], [T], id='text_not_string'),
    pytest.param([{'end_ms': 420}], [M], id='missing_start'),
    pytest.param([{'start_ms': 0}], [M], id='missing_end'),
    pytest.param(['news'], [T], id='item_not_object'),
    pytest.param('news', [T], id='words_text'),
    pytest.param(None, [T], id='words_null'),
]
VALID_WORD_CASES = [
    pytest.param([_word(0, 420), _word(420, 900)], id='touching_words'),
    pytest.param([_word(0, 420), _word(500, 900)], id='gap_between_words'),
    pytest.param([_word(0, 65000)], id='ends_exactly_at_duration'),
    pytest.param([_word(0, 1)], id='shortest_word'),
    pytest.param([_word(0, 420, confidence=0), _word(420, 900, confidence=1)], id='confidence_bounds'),
    pytest.param([{'start_ms': 0, 'end_ms': 420}], id='text_fields_optional'),
]


@pytest.mark.parametrize('words, expected', WORD_CASES)
def test_invalid_words_are_rejected(words: object, expected: list) -> None:
    payload = _payload(words=words)
    assert _issues(payload) == expected
    with pytest.raises(WordTimingError):
        validate_word_timing(payload)


@pytest.mark.parametrize('words', VALID_WORD_CASES)
def test_valid_words_are_accepted(words: list) -> None:
    record = validate_word_timing(_payload(words=words))
    assert isinstance(record, WordTimingRecord)
    assert len(record.words) == len(words)


@pytest.mark.parametrize('duration', [DELETE, None])
def test_word_end_is_unbounded_without_voice_duration(duration: object) -> None:
    payload = _payload(words=[_word(0, 10**9)], segment_boundaries=[_seg(0, 10**9)], voice_duration_ms=duration)
    record = validate_word_timing(payload)
    assert isinstance(record, WordTimingRecord)
    assert record.voice_duration_ms is None

def test_word_and_boundary_constants_match_fixture_keys() -> None:
    valid = _valid()
    assert set(WORD_REQUIRED) | set(WORD_OPTIONAL) == set(valid['words'][0])
    assert dict(WORD_REQUIRED) == {'start_ms': 'integer', 'end_ms': 'integer'}
    assert WORD_OPTIONAL['confidence'] == 'number'
    assert dict(BOUNDARY_REQUIRED) == dict(WORD_REQUIRED)
    assert set(BOUNDARY_REQUIRED) == set(valid['segment_boundaries'][0])


@pytest.mark.parametrize('name', sorted(WORD_TIMING_REQUIRED))
def test_missing_required_field_is_reported(name: str) -> None:
    assert _issues(_payload(**{name: DELETE})) == [(MISSING_REQUIRED, name)]


@pytest.mark.parametrize('name', sorted(WORD_TIMING_REQUIRED))
def test_null_required_field_is_wrong_type(name: str) -> None:
    assert _issues(_payload(**{name: None})) == [(WRONG_TYPE, name)]


@pytest.mark.parametrize('name', ['script_fingerprint', 'voice_hash'])
@pytest.mark.parametrize(
    'value', ['A' * 64, 'a' * 63, 'a' * 65, 'g' * 64, 'a' * 64 + chr(10), ' ' + 'a' * 63, 5, True, ['a' * 64]]
)
def test_sha256_must_be_lowercase_hex(name: str, value: object) -> None:
    assert _issues(_payload(**{name: value})) == [(WRONG_TYPE, name)]


@pytest.mark.parametrize('name', ['script_version_id', 'timing_artifact_ref', 'validation_report_ref'])
@pytest.mark.parametrize('value', [5, True, ['x'], {'x': 1}])
def test_string_fields_reject_non_strings(name: str, value: object) -> None:
    assert _issues(_payload(**{name: value})) == [(WRONG_TYPE, name)]


@pytest.mark.parametrize(
    'value, expected',
    [
        pytest.param('65s', [(WRONG_TYPE, 'voice_duration_ms')], id='text'),
        pytest.param(True, [(WRONG_TYPE, 'voice_duration_ms')], id='bool'),
        pytest.param(65000.0, [(WRONG_TYPE, 'voice_duration_ms')], id='float'),
        pytest.param(0, [(CONSTRAINT_VIOLATION, 'voice_duration_ms')], id='zero'),
        pytest.param(-1, [(CONSTRAINT_VIOLATION, 'voice_duration_ms')], id='negative'),
    ],
)
def test_voice_duration_ms_is_validated(value: object, expected: list) -> None:
    assert _issues(_payload(voice_duration_ms=value)) == expected


def test_alignment_gaps_is_optional_array() -> None:
    assert _issues(_payload(alignment_gaps='gap')) == [(WRONG_TYPE, 'alignment_gaps')]
    for value in (DELETE, None, []):
        record = validate_word_timing(_payload(alignment_gaps=value))
        assert isinstance(record, WordTimingRecord)
        assert record.alignment_gaps == ()

S = (CONSTRAINT_VIOLATION, 'segment_boundaries')
ST = (WRONG_TYPE, 'segment_boundaries')
SEGMENT_CASES = [
    pytest.param([_seg(100, 100)], [S], id='end_equals_start'),
    pytest.param([_seg(200, 100)], [S], id='end_before_start'),
    pytest.param([_seg(-1, 100)], [S], id='negative_start'),
    pytest.param([_seg(0, 65001)], [S], id='end_beyond_duration'),
    pytest.param([_seg(500, 900), _seg(0, 400)], [S], id='out_of_order'),
    pytest.param([_seg(0, 500), _seg(400, 900)], [S], id='overlap'),
    pytest.param([_seg(True, 900)], [ST], id='start_bool'),
    pytest.param([_seg(0, '900')], [ST], id='end_text'),
    pytest.param([{'start_ms': 0}], [(MISSING_REQUIRED, 'segment_boundaries')], id='missing_end'),
    pytest.param(['0-900'], [ST], id='item_not_object'),
    pytest.param('0-900', [ST], id='not_list'),
]


@pytest.mark.parametrize('segments, expected', SEGMENT_CASES)
def test_invalid_segment_boundaries_are_rejected(segments: object, expected: list) -> None:
    assert _issues(_payload(segment_boundaries=segments)) == expected


@pytest.mark.parametrize('segments', [[], [_seg(0, 400), _seg(400, 900)], [_seg(0, 65000)]])
def test_valid_segment_boundaries_are_accepted(segments: list) -> None:
    record = validate_word_timing(_payload(segment_boundaries=segments))
    assert isinstance(record, WordTimingRecord)
    assert len(record.segment_boundaries) == len(segments)


def test_unknown_fields_are_ignored() -> None:
    payload = _payload(extra_top='x', binding_version='9.9.9')
    payload['words'][0]['extra_word'] = {'any': 1}
    payload['segment_boundaries'][0]['extra_segment'] = 1
    assert _issues(payload) == []
    record = validate_word_timing(payload)
    assert isinstance(record, WordTimingRecord)
    for obj in (record, record.words[0], record.segment_boundaries[0]):
        assert not any(name.startswith('extra') or name == 'binding_version' for name in vars(obj))


@pytest.mark.parametrize('payload', [None, [], 'text', 5, ()])
def test_non_object_payload_is_wrong_type(payload: object) -> None:
    assert _issues(payload) == [(WRONG_TYPE, '$')]
    with pytest.raises(WordTimingError):
        validate_word_timing(payload)


def test_all_issues_are_reported_once_and_payload_is_not_mutated() -> None:
    payload = _payload(voice_hash=DELETE, words=[_word(420, 900), _word(0, 420), _word(0, 420)])
    snapshot = copy.deepcopy(payload)
    expected = [(MISSING_REQUIRED, 'voice_hash'), (CONSTRAINT_VIOLATION, 'words')]
    assert _issues(payload) == expected
    with pytest.raises(WordTimingError) as caught:
        validate_word_timing(payload)
    assert [(i.code, i.field) for i in caught.value.issues] == expected
    assert (caught.value.code, caught.value.field) == expected[0]
    assert payload == snapshot


def test_module_imports_only_allowed_stdlib() -> None:
    allowed = {'__future__', 'copy', 're', 'collections.abc', 'dataclasses', 'types'}
    imported = set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed
