"""G-01: validator binding ActivityRequest và ActivityResult (BINDING-G-ACTIVITY-EXECUTION 1.0.0).

coveredIds: không
"""
import ast
import copy
import json
import pathlib

import pytest

from controlplane.domain.orchestration.activity_binding import (
    ACTIVITY_REQUEST_FIELDS, ACTIVITY_REQUEST_FORBIDDEN, ACTIVITY_REQUEST_REQUIRED,
    ACTIVITY_RESULT_FIELDS, ACTIVITY_RESULT_REQUIRED, DISPOSITIONS,
    ENUM_VIOLATION, FORBIDDEN_FIELD, MISSING_REQUIRED, WRONG_TYPE,
    validate_activity_request, validate_activity_result,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-activity-execution.json'
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'activity_binding.py'
VALIDATORS = {'ActivityRequest': validate_activity_request, 'ActivityResult': validate_activity_result}
WRONG_VALUE = {'string': 5, 'array': 'x', 'object': 'x', 'integer': '3', 'datetime': 5}

_ENTITIES = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']
_BINDING = {e['name']: e for e in json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']}
VALID = [(entity, index) for entity, body in _ENTITIES.items() for index in range(len(body['valid']))]
INVALID = [(entity, case['case']) for entity, body in _ENTITIES.items() for case in body['invalid']]


def _valid(entity: str) -> dict:
    return copy.deepcopy(_ENTITIES[entity]['valid'][0])


def _case(entity: str, name: str) -> dict:
    return next(c for c in _ENTITIES[entity]['invalid'] if c['case'] == name)


def test_fixture_has_valid_and_invalid_cases_for_both_entities() -> None:
    assert set(_ENTITIES) == set(VALIDATORS)
    for body in _ENTITIES.values():
        assert body['valid'] and body['invalid']


@pytest.mark.parametrize(('entity', 'index'), VALID)
def test_fixture_valid_payloads_return_no_issues(entity: str, index: int) -> None:
    assert VALIDATORS[entity](_ENTITIES[entity]['valid'][index]) == []


@pytest.mark.parametrize(('entity', 'name'), INVALID)
def test_fixture_invalid_payloads_return_expected_error(entity: str, name: str) -> None:
    case = _case(entity, name)
    assert VALIDATORS[entity](case['payload']) == [case['expected_error']]


def test_module_tables_match_binding() -> None:
    for entity, fields, required in (
        ('ActivityRequest', ACTIVITY_REQUEST_FIELDS, ACTIVITY_REQUEST_REQUIRED),
        ('ActivityResult', ACTIVITY_RESULT_FIELDS, ACTIVITY_RESULT_REQUIRED),
    ):
        binding_fields = _BINDING[entity]['fields']
        assert list(fields.items()) == [(f['name'], f['type']) for f in binding_fields]
        assert set(required) == {f['name'] for f in binding_fields if f['required']}
    assert list(ACTIVITY_REQUEST_FORBIDDEN) == _BINDING['ActivityRequest']['forbidden_fields']
    disposition = next(f for f in _BINDING['ActivityResult']['fields'] if f['name'] == 'disposition')
    assert list(DISPOSITIONS) == disposition['enum']


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_missing_required_and_wrong_type_follow_binding(entity: str) -> None:
    validate = VALIDATORS[entity]
    for field in _BINDING[entity]['fields']:
        name = field['name']
        if field['required']:
            payload = _valid(entity)
            del payload[name]
            assert validate(payload) == [{'code': MISSING_REQUIRED, 'field': name}], name
            payload = _valid(entity)
            payload[name] = None
            assert validate(payload) == [{'code': WRONG_TYPE, 'field': name}], name
        payload = _valid(entity)
        payload[name] = WRONG_VALUE[field['type']]
        assert validate(payload) == [{'code': WRONG_TYPE, 'field': name}], name


def test_optional_fields_may_be_absent_and_valid_when_typed() -> None:
    request = _valid('ActivityRequest')
    request.update(execution_grant={'grant_id': 'g'}, deadline_at='2026-10-18T08:00:00.123+07:00')
    assert validate_activity_request(request) == []
    del request['video_job_id']
    assert validate_activity_request(request) == []
    result = _valid('ActivityResult')
    result.update(metrics={}, warnings=[], problem={}, operation_receipt_ref='r')
    assert validate_activity_result(result) == []


def test_unknown_fields_are_ignored() -> None:
    request = _valid('ActivityRequest')
    request.update(future_field=1, another={'a': 1})
    result = _valid('ActivityResult')
    result.update(future_field=[1], secret_value='x', raw_blob='y')
    assert validate_activity_request(request) == []
    assert validate_activity_result(result) == []


@pytest.mark.parametrize('present', [('secret_value',), ('raw_blob',), ('secret_value', 'raw_blob')])
def test_forbidden_fields_are_rejected_with_any_value(present: tuple) -> None:
    for value in ('redacted-canary', None, 0, {}):
        payload = _valid('ActivityRequest')
        payload.update({name: value for name in present})
        assert validate_activity_request(payload) == [{'code': FORBIDDEN_FIELD, 'field': name} for name in present]


def test_integer_rejects_bool_float_and_string() -> None:
    for bad in (True, False, 3.0, '3'):
        payload = _valid('ActivityResult')
        payload['execution_generation'] = bad
        assert validate_activity_result(payload) == [{'code': WRONG_TYPE, 'field': 'execution_generation'}], bad
    for good in (0, 3):
        payload = _valid('ActivityResult')
        payload['execution_generation'] = good
        assert validate_activity_result(payload) == []


def test_recovery_epoch_must_be_string() -> None:
    for bad in (1, 1.5, None, ['epoch-0001']):
        payload = _valid('ActivityResult')
        payload['recovery_epoch'] = bad
        assert validate_activity_result(payload) == [{'code': WRONG_TYPE, 'field': 'recovery_epoch'}], bad
    payload = _valid('ActivityResult')
    payload['recovery_epoch'] = '1'
    assert validate_activity_result(payload) == []


def test_disposition_accepts_only_contract_values() -> None:
    for value in ('succeeded', 'failed', 'waiting', 'outcome_unknown', 'stale'):
        payload = _valid('ActivityResult')
        payload['disposition'] = value
        assert validate_activity_result(payload) == [], value
    for bad in ('done', 'SUCCEEDED', '', ' succeeded', 'completed'):
        payload = _valid('ActivityResult')
        payload['disposition'] = bad
        assert validate_activity_result(payload) == [{'code': ENUM_VIOLATION, 'field': 'disposition'}], bad
    for bad in (5, None, ['succeeded'], {'a': 1}):
        payload = _valid('ActivityResult')
        payload['disposition'] = bad
        assert validate_activity_result(payload) == [{'code': WRONG_TYPE, 'field': 'disposition'}], bad


@pytest.mark.parametrize('value', ['2026-10-18T08:00:00Z', '2026-10-18T08:00:00.123456+07:00', '2026-10-18T08:00:00-05:00'])
def test_datetime_accepts_rfc3339(value: str) -> None:
    result = _valid('ActivityResult')
    result['completed_at'] = value
    assert validate_activity_result(result) == []
    request = _valid('ActivityRequest')
    request['deadline_at'] = value
    assert validate_activity_request(request) == []


@pytest.mark.parametrize('value', [
    '2026-10-18T08:00:00', '2026-10-18', '2026-10-18 08:00:00Z', '2026-10-18T08:00:00+0700',
    '2026-13-18T08:00:00Z', '2026-10-18T25:00:00Z', '2026-02-30T08:00:00Z', '', 1760774400, None,
])
def test_datetime_rejects_non_rfc3339(value: object) -> None:
    result = _valid('ActivityResult')
    result['completed_at'] = value
    assert validate_activity_result(result) == [{'code': WRONG_TYPE, 'field': 'completed_at'}]
    request = _valid('ActivityRequest')
    request['deadline_at'] = value
    assert validate_activity_request(request) == [{'code': WRONG_TYPE, 'field': 'deadline_at'}]


def test_side_effect_requires_execution_grant() -> None:
    payload = _valid('ActivityRequest')
    assert validate_activity_request(payload, side_effect=True) == [{'code': MISSING_REQUIRED, 'field': 'execution_grant'}]
    assert validate_activity_request(payload) == []
    assert validate_activity_request(payload, side_effect=False) == []
    payload['execution_grant'] = {'grant_id': 'g'}
    assert validate_activity_request(payload, side_effect=True) == []
    payload['execution_grant'] = 'g'
    assert validate_activity_request(payload, side_effect=True) == [{'code': WRONG_TYPE, 'field': 'execution_grant'}]
    payload['execution_grant'] = {'grant_id': 'g'}
    payload['secret_value'] = 'x'
    assert validate_activity_request(payload, side_effect=True) == [{'code': FORBIDDEN_FIELD, 'field': 'secret_value'}]


@pytest.mark.parametrize('bad', [None, 1, 0, 'False', 'true'])
def test_side_effect_flag_must_be_bool(bad: object) -> None:
    with pytest.raises(TypeError):
        validate_activity_request(_valid('ActivityRequest'), side_effect=bad)


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_non_object_payload_is_wrong_type(entity: str) -> None:
    for bad in (None, [], 'x', 5, [_valid(entity)]):
        assert VALIDATORS[entity](bad) == [{'code': WRONG_TYPE, 'field': '$'}]


def test_issues_are_plain_dicts_in_stable_order_and_payload_is_not_mutated() -> None:
    payload = _valid('ActivityRequest')
    del payload['operation_key']
    payload['raw_blob'] = 'x'
    before = copy.deepcopy(payload)
    issues = validate_activity_request(payload, side_effect=True)
    assert payload == before
    assert issues == [
        {'code': MISSING_REQUIRED, 'field': 'operation_key'},
        {'code': MISSING_REQUIRED, 'field': 'execution_grant'},
        {'code': FORBIDDEN_FIELD, 'field': 'raw_blob'},
    ]
    assert all(type(issue) is dict and set(issue) == {'code', 'field'} for issue in issues)
    assert validate_activity_request(payload, side_effect=True) == issues


def test_orchestration_test_dir_has_no_init() -> None:
    assert not (pathlib.Path(__file__).parent / '__init__.py').exists()


def test_module_imports_only_allowed_modules() -> None:
    allowed = {'__future__', 'datetime', 're', 'types'}
    imported = set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed
