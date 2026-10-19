"""J-01: validator binding ProviderRouteRequest và ProviderRouteDecision (BINDING-J-PROVIDER-ROUTE 1.0.0).

coveredIds: CT-AI-ROUTE-001, TST-SEC-INV-012
"""
import ast
import copy
import dataclasses
import json
import pathlib
import re
import types
import typing

import pytest

from controlplane.domain.config_security.route_binding import (
    DECISION_ARRAY_ITEMS, DECISION_FIELDS, FORBIDDEN_DECISION_FIELDS, FORBIDDEN_FIELD, MISSING_REQUIRED, REQUEST_FIELDS,
    WRONG_TYPE, ProviderRouteDecision, ProviderRouteRequest, validate_route_decision, validate_route_request,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'j-provider-route.json'
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'config_security' / 'route_binding.py'
VALIDATORS = {'ProviderRouteRequest': validate_route_request, 'ProviderRouteDecision': validate_route_decision}
CLASSES = {'ProviderRouteRequest': ProviderRouteRequest, 'ProviderRouteDecision': ProviderRouteDecision}
TABLES = {'ProviderRouteRequest': REQUEST_FIELDS, 'ProviderRouteDecision': DECISION_FIELDS}
WRONG_VALUE = {'string': 5, 'array': 'x', 'object': 'x'}

_ENTITIES = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']
_BINDING = {e['name']: e for e in json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']}
VALID = [(entity, index) for entity, body in _ENTITIES.items() for index in range(len(body['valid']))]
INVALID = [(entity, case['case']) for entity, body in _ENTITIES.items() for case in body['invalid']]


def _valid(entity: str) -> dict:
    return copy.deepcopy(_ENTITIES[entity]['valid'][0])


def _case(entity: str, name: str) -> dict:
    return next(c for c in _ENTITIES[entity]['invalid'] if c['case'] == name)


def _binding_type(hint: object) -> str:
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        hint = next(arg for arg in typing.get_args(hint) if arg is not type(None))
    return {str: 'string', list: 'array', dict: 'object'}[typing.get_origin(hint) or hint]


def test_fixture_has_valid_and_invalid_cases_for_both_entities() -> None:
    assert set(_ENTITIES) == set(VALIDATORS)
    for body in _ENTITIES.values():
        assert body['valid'] and body['invalid']
    assert {name for _, name in INVALID} >= {
        'missing_data_sensitivity', 'api_key_leaked', 'missing_route_revision', 'fallback_order_as_string',
    }


@pytest.mark.parametrize(('entity', 'index'), VALID)
def test_fixture_valid_payloads_return_no_issues(entity: str, index: int) -> None:
    assert VALIDATORS[entity](_ENTITIES[entity]['valid'][index]) == []


@pytest.mark.parametrize(('entity', 'name'), INVALID)
def test_fixture_invalid_payloads_return_expected_error(entity: str, name: str) -> None:
    case = _case(entity, name)
    assert VALIDATORS[entity](case['payload']) == [case['expected_error']]


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_field_tables_match_binding(entity: str) -> None:
    binding_fields = _BINDING[entity]['fields']
    assert list(TABLES[entity].items()) == [(f['name'], (f['type'], f['required'])) for f in binding_fields]
    assert (len(REQUEST_FIELDS), len(DECISION_FIELDS)) == (8, 10)


def test_forbidden_and_item_tables_match_binding() -> None:
    assert list(FORBIDDEN_DECISION_FIELDS) == _BINDING['ProviderRouteDecision']['forbidden_fields']
    assert 'forbidden_fields' not in _BINDING['ProviderRouteRequest']
    items = {f['name']: f['items'] for f in _BINDING['ProviderRouteDecision']['fields'] if 'items' in f}
    assert dict(DECISION_ARRAY_ITEMS) == items


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_dataclass_fields_match_binding(entity: str) -> None:
    cls = CLASSES[entity]
    hints = typing.get_type_hints(cls)
    fields = dataclasses.fields(cls)
    binding_fields = _BINDING[entity]['fields']
    assert [f.name for f in fields] == [f['name'] for f in binding_fields]
    assert [_binding_type(hints[f.name]) for f in fields] == [f['type'] for f in binding_fields]
    optional = {f.name for f in fields if f.default is not dataclasses.MISSING}
    assert optional == {f['name'] for f in binding_fields if not f['required']}
    assert all(f.default is None for f in fields if f.name in optional)
    assert cls.__dataclass_params__.frozen


@pytest.mark.parametrize(('entity', 'index'), VALID)
def test_fixture_valid_payload_builds_frozen_dataclass(entity: str, index: int) -> None:
    payload = _ENTITIES[entity]['valid'][index]
    instance = CLASSES[entity](**payload)
    assert dataclasses.asdict(instance) == {name: payload.get(name) for name in TABLES[entity]}
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, next(iter(TABLES[entity])), 'x')


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
    request = _valid('ProviderRouteRequest')
    assert validate_route_request(request) == []
    request['health_quota_ref'] = 'quota-1'
    assert validate_route_request(request) == []
    decision = _valid('ProviderRouteDecision')
    assert validate_route_decision(decision) == []
    decision['project_ref'] = 'project-1'
    assert validate_route_decision(decision) == []


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_unknown_fields_are_ignored(entity: str) -> None:
    payload = _valid(entity)
    payload.update(future_field=1, another={'a': 1}, api_key_ref='ref-1')
    assert VALIDATORS[entity](payload) == []


@pytest.mark.parametrize('bad', [[1], ['a', 1], [None], [['a']], [{'a': 'b'}], [True]])
def test_rationale_codes_must_be_array_of_strings(bad: list) -> None:
    payload = _valid('ProviderRouteDecision')
    payload['rationale_codes'] = bad
    assert validate_route_decision(payload) == [{'code': WRONG_TYPE, 'field': 'rationale_codes'}]


@pytest.mark.parametrize('good', [[], ['QUOTA_AVAILABLE'], ['QUOTA_AVAILABLE', 'COST_WITHIN_BOUND']])
def test_rationale_codes_accepts_array_of_strings(good: list) -> None:
    payload = _valid('ProviderRouteDecision')
    payload['rationale_codes'] = good
    assert validate_route_decision(payload) == []


@pytest.mark.parametrize('bad', ['gemini', None, {'a': 1}, 5, ('a',)])
def test_fallback_order_must_be_array(bad: object) -> None:
    payload = _valid('ProviderRouteDecision')
    payload['fallback_order'] = bad
    assert validate_route_decision(payload) == [{'code': WRONG_TYPE, 'field': 'fallback_order'}]


@pytest.mark.parametrize('key', [
    'api_key', 'API_KEY', 'Api_Key', 'secret_value', 'SECRET_VALUE', 'access_token', 'Access_Token', 'refresh_token', 'REFRESH_TOKEN',
])
def test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value(key: str) -> None:
    for value in ('redacted-canary', None, 0, {}, ''):
        payload = _valid('ProviderRouteDecision')
        payload[key] = value
        assert validate_route_decision(payload) == [{'code': FORBIDDEN_FIELD, 'field': key.lower()}], value


def test_all_forbidden_fields_are_reported_once_in_binding_order() -> None:
    payload = _valid('ProviderRouteDecision')
    payload.update({'REFRESH_TOKEN': 'x', 'refresh_token': 'y', 'Api_Key': 'z', 'secret_value': 's', 'access_token': 'a'})
    assert validate_route_decision(payload) == [{'code': FORBIDDEN_FIELD, 'field': name} for name in FORBIDDEN_DECISION_FIELDS]


@pytest.mark.parametrize('entity', sorted(VALIDATORS))
def test_non_object_payload_is_wrong_type(entity: str) -> None:
    for bad in (None, [], 'x', 5, [_valid(entity)]):
        assert VALIDATORS[entity](bad) == [{'code': WRONG_TYPE, 'field': '$'}]


def test_issues_are_plain_dicts_in_stable_order_and_payload_is_not_mutated() -> None:
    payload = _valid('ProviderRouteDecision')
    del payload['route_revision']
    payload['fallback_order'] = 'x'
    payload['rationale_codes'] = [1]
    payload['API_KEY'] = 'x'
    before = copy.deepcopy(payload)
    issues = validate_route_decision(payload)
    assert payload == before
    assert issues == [
        {'code': MISSING_REQUIRED, 'field': 'route_revision'},
        {'code': WRONG_TYPE, 'field': 'rationale_codes'},
        {'code': WRONG_TYPE, 'field': 'fallback_order'},
        {'code': FORBIDDEN_FIELD, 'field': 'api_key'},
    ]
    assert all(type(issue) is dict and set(issue) == {'code', 'field'} for issue in issues)
    assert validate_route_decision(payload) == issues


def test_config_test_dir_has_no_init() -> None:
    assert not (pathlib.Path(__file__).parent / '__init__.py').exists()


def test_module_imports_only_allowed_modules_and_not_router_or_adapter() -> None:
    allowed = {'__future__', 'dataclasses', 'types', 'typing'}
    source = MODULE_PATH.read_text(encoding='utf-8')
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed
    assert re.search(r'config[.](router|adapter)', source) is None
