"""B-1: CollectedDocumentPackage / CollectedDocumentResolution boundary checks and CHECK-B import boundary.

B-2..B-12 rerun this file as the shared module B boundary check.
"""
import copy
import json
import pathlib
import re

import pytest

from ingestion.domain.package_validation import (
    BINDING_VERSION,
    ENUM_VIOLATION,
    MISSING_REQUIRED,
    PACKAGE_ENUM,
    PACKAGE_ITEMS,
    PACKAGE_OPTIONAL,
    PACKAGE_REQUIRED,
    RESOLUTION_ENUM,
    RESOLUTION_ITEMS,
    RESOLUTION_OPTIONAL,
    RESOLUTION_REQUIRED,
    UNSUPPORTED_BINDING_VERSION,
    WRONG_TYPE,
    validate_collected_document_package,
    validate_collected_document_resolution,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'a-b-collected-document.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'a-b-collected-document' / 'payloads.json'
PACKAGE = 'CollectedDocumentPackage'
RESOLUTION = 'CollectedDocumentResolution'
ENTITIES = (PACKAGE, RESOLUTION)
VALIDATORS = {PACKAGE: validate_collected_document_package, RESOLUTION: validate_collected_document_resolution}
CONSTANTS = {
    PACKAGE: (PACKAGE_REQUIRED, PACKAGE_OPTIONAL, PACKAGE_ENUM, PACKAGE_ITEMS),
    RESOLUTION: (RESOLUTION_REQUIRED, RESOLUTION_OPTIONAL, RESOLUTION_ENUM, RESOLUTION_ITEMS),
}
BOUNDARY_RE = re.compile(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)')
MISSING = object()


def _binding() -> dict:
    return json.loads(BINDING_PATH.read_text(encoding='utf-8'))


def _binding_fields(entity: str) -> list[dict]:
    return next(item for item in _binding()['entities'] if item['name'] == entity)['fields']


def _fixture(entity: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]


def _valid(entity: str) -> dict:
    return copy.deepcopy(_fixture(entity)['valid'][0])


def _derive(fields: list[dict]) -> tuple[dict, ...]:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
        {f['name']: tuple(f['enum']) for f in fields if 'enum' in f},
        {f['name']: f['items'] for f in fields if 'items' in f},
    )


def _constants(entity: str) -> tuple[dict, ...]:
    return tuple(dict(table) for table in CONSTANTS[entity])


def _field(fields: list[dict], name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


def _issues(entity: str, payload: object) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in VALIDATORS[entity](payload)]


@pytest.mark.parametrize('entity', ENTITIES)
def test_constants_match_binding(entity: str) -> None:
    assert _constants(entity) == _derive(_binding_fields(entity))


def test_binding_version_constant_matches_binding() -> None:
    assert BINDING_VERSION == _binding()['binding_version']


def test_drift_comparison_detects_mutated_binding() -> None:
    expected = _constants(PACKAGE)
    assert expected[0], 'PACKAGE_REQUIRED must not be empty'
    mutations = {
        'provenance_chain_optional': lambda fs: _field(fs, 'provenance_chain').update(required=False),
        'source_revision_as_string': lambda fs: _field(fs, 'source_revision').update(type='string'),
        'eligibility_enum_extended': lambda fs: _field(fs, 'content_eligibility')['enum'].append('complete'),
        'media_items_dropped': lambda fs: _field(fs, 'media_discoveries').pop('items'),
        'required_field_added': lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True}),
    }
    for name, mutate in mutations.items():
        fields = _binding_fields(PACKAGE)
        mutate(fields)
        assert _derive(fields) != expected, name


def test_fixture_has_cases_for_both_entities() -> None:
    assert len(_fixture(PACKAGE)['invalid']) >= 4
    assert len(_fixture(RESOLUTION)['invalid']) >= 2


@pytest.mark.parametrize('entity', ENTITIES)
def test_fixture_valid_payloads_have_no_issues(entity: str) -> None:
    valid = _fixture(entity)['valid']
    assert valid
    for payload in valid:
        assert _issues(entity, payload) == []


@pytest.mark.parametrize(
    ('entity', 'case'),
    [pytest.param(entity, case, id=case['case']) for entity in ENTITIES for case in _fixture(entity)['invalid']],
)
def test_fixture_invalid_case_returns_expected_issue(entity: str, case: dict) -> None:
    expected = case['expected_error']
    assert _issues(entity, case['payload']) == [(expected['code'], expected['field'])]


@pytest.mark.parametrize('entity', ENTITIES)
def test_each_missing_required_field_is_reported(entity: str) -> None:
    required = CONSTANTS[entity][0]
    assert required, f'{entity} REQUIRED must not be empty'
    for name in required:
        payload = _valid(entity)
        del payload[name]
        assert _issues(entity, payload) == [(MISSING_REQUIRED, name)], name


@pytest.mark.parametrize(
    ('field', 'value', 'code'),
    [
        ('provenance_chain', MISSING, MISSING_REQUIRED),
        ('provenance_chain', None, WRONG_TYPE),
        ('provenance_chain', ['final_fetch'], WRONG_TYPE),
        ('content_eligibility', 'complete', ENUM_VIOLATION),
        ('source_revision', '3', WRONG_TYPE),
        ('source_revision', True, WRONG_TYPE),
        ('fetched_at', 'yesterday', WRONG_TYPE),
        ('fetched_at', '2026-10-18T08:00:00', WRONG_TYPE),
        ('fetched_at', '2026-13-01T08:00:00Z', WRONG_TYPE),
        ('published_at_candidate', '2026-10-18', WRONG_TYPE),
        ('media_discoveries', [1], WRONG_TYPE),
    ],
)
def test_package_counterexamples_are_rejected(field: str, value: object, code: str) -> None:
    payload = _valid(PACKAGE)
    if value is MISSING:
        del payload[field]
    else:
        payload[field] = value
    assert _issues(PACKAGE, payload) == [(code, field)]


def test_rfc3339_datetimes_with_offset_are_accepted() -> None:
    for value in ('2026-10-18T08:00:00Z', '2026-10-18T08:00:00.123456+07:00', '2026-10-18T08:00:00-05:30'):
        for field in ('fetched_at', 'published_at_candidate'):
            payload = _valid(PACKAGE)
            payload[field] = value
            assert _issues(PACKAGE, payload) == [], (field, value)


@pytest.mark.parametrize('entity', ENTITIES)
def test_unknown_field_is_ignored(entity: str) -> None:
    payload = _valid(entity)
    payload['x_future_optional_field'] = {'additive': True}
    assert _issues(entity, payload) == []


@pytest.mark.parametrize('entity', ENTITIES)
def test_binding_version_major_other_than_one_is_unsupported(entity: str) -> None:
    for version in ('1.0.0', '1.4.2'):
        payload = _valid(entity)
        payload['binding_version'] = version
        assert _issues(entity, payload) == [], version
    for version in ('2.0.0', '0.9.0', '10.0.0', 'v1', '1', 1, None):
        payload = _valid(entity)
        payload['binding_version'] = version
        assert _issues(entity, payload) == [(UNSUPPORTED_BINDING_VERSION, 'binding_version')], version


@pytest.mark.parametrize('entity', ENTITIES)
def test_non_mapping_payload_is_wrong_type(entity: str) -> None:
    for value in (None, [], 'payload'):
        assert _issues(entity, value) == [(WRONG_TYPE, '$')], value


def test_boundary_regex_detects_forbidden_imports() -> None:
    for line in ('from src.controlplane import x', 'import requests', '    import socket', 'from urllib.parse import urlparse', 'import psycopg'):
        assert BOUNDARY_RE.search(line), line
    for line in ('import re', 'from datetime import datetime', 'from ingestion.domain import package_validation'):
        assert not BOUNDARY_RE.search(line), line


def test_ingestion_import_boundary() -> None:
    root = pathlib.Path(__file__).resolve().parents[3]
    files = sorted((root / 'src' / 'ingestion').rglob('*.py'))
    scanned = {path.relative_to(root).as_posix() for path in files}
    assert {'src/ingestion/__init__.py', 'src/ingestion/domain/package_validation.py'} <= scanned, scanned
    offenders = [path.relative_to(root).as_posix() for path in files if BOUNDARY_RE.search(path.read_text(encoding='utf-8'))]
    assert not offenders, offenders
    for relative in ('tests/unit/ingestion/__init__.py', 'tests/integration/ingestion/__init__.py'):
        assert not (root / relative).exists(), relative
