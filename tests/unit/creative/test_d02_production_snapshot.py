"""D-02: ProductionSnapshot bất biến, validator theo binding và BuildProductionSnapshot (CT-AI-001).

coveredIds: CT-AI-001, TST-INT-INV-004, TST-INT-INV-005
"""
import ast
import copy
import dataclasses
import hashlib
import itertools
import json
import pathlib

import pytest

from controlplane.application.idempotency import canonicalization
from creative.domain import snapshot as snapshot_module
from creative.domain.snapshot import (
    BINDING_VERSION,
    ENUM_VIOLATION,
    INPUT_NOT_READY,
    MISSING_REQUIRED,
    NOT_ELIGIBLE,
    SNAPSHOT_ENUM,
    SNAPSHOT_ITEMS,
    SNAPSHOT_OPTIONAL,
    SNAPSHOT_REQUIRED,
    WRONG_TYPE,
    ProductionSnapshot,
    SnapshotRejected,
    build_production_snapshot,
    fingerprint_refs,
    matches_type,
    validate_production_snapshot,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'b-d-production-snapshot.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'b-d-production-snapshot' / 'payloads.json'
SNAPSHOT_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'snapshot.py'
ENTITY = 'ProductionSnapshot'
MISSING = object()
SHA = '0123456789abcdef' * 4


def _binding() -> dict:
    return json.loads(BINDING_PATH.read_text(encoding='utf-8'))


def _binding_fields() -> list[dict]:
    return next(item for item in _binding()['entities'] if item['name'] == ENTITY)['fields']


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][ENTITY]


def _valid() -> dict:
    return copy.deepcopy(_fixture()['valid'][0])


def _derive(fields: list[dict]) -> tuple[dict, ...]:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
        {f['name']: tuple(f['enum']) for f in fields if 'enum' in f},
        {f['name']: f['items'] for f in fields if 'items' in f},
    )


def _constants() -> tuple[dict, ...]:
    return tuple(dict(table) for table in (SNAPSHOT_REQUIRED, SNAPSHOT_OPTIONAL, SNAPSHOT_ENUM, SNAPSHOT_ITEMS))


def _field(fields: list[dict], name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


def _issues(payload: object) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in validate_production_snapshot(payload)]


def test_constants_match_binding() -> None:
    assert _constants() == _derive(_binding_fields())


def test_binding_version_constant_matches_binding() -> None:
    assert BINDING_VERSION == _binding()['binding_version']


def test_drift_comparison_detects_mutated_binding() -> None:
    expected = _constants()
    assert expected[0], 'SNAPSHOT_REQUIRED must not be empty'
    mutations = {
        'fingerprint_optional': lambda fs: _field(fs, 'source_set_fingerprint').update(required=False),
        'mode_enum_extended': lambda fs: _field(fs, 'production_mode')['enum'].append('timeline'),
        'source_refs_items_dropped': lambda fs: _field(fs, 'source_refs').pop('items'),
        'timestamp_as_string': lambda fs: _field(fs, 'snapshot_timestamp').update(type='string'),
        'required_field_added': lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True}),
    }
    for name, mutate in mutations.items():
        fields = _binding_fields()
        mutate(fields)
        assert _derive(fields) != expected, name


def test_fixture_has_valid_and_invalid_cases() -> None:
    assert _fixture()['valid']
    assert len(_fixture()['invalid']) >= 4


def test_fixture_valid_payloads_have_no_issues() -> None:
    for payload in _fixture()['valid']:
        assert _issues(payload) == []


@pytest.mark.parametrize('case', _fixture()['invalid'], ids=lambda case: case['case'])
def test_fixture_invalid_case_returns_expected_issue(case: dict) -> None:
    expected = case['expected_error']
    assert _issues(case['payload']) == [(expected['code'], expected['field'])]


def test_test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-AI-001, TST-INT-INV-004, TST-INT-INV-005' in (doc or '').splitlines()


def test_each_missing_required_field_is_reported() -> None:
    assert SNAPSHOT_REQUIRED, 'SNAPSHOT_REQUIRED must not be empty'
    for name in SNAPSHOT_REQUIRED:
        payload = _valid()
        del payload[name]
        assert _issues(payload) == [(MISSING_REQUIRED, name)], name


@pytest.mark.parametrize(
    ('field', 'value', 'code'),
    [
        ('production_mode', 'timeline', ENUM_VIOLATION),
        ('production_mode', 'Single_Article', ENUM_VIOLATION),
        ('production_mode', 1, WRONG_TYPE),
        ('snapshot_id', 5, WRONG_TYPE),
        ('snapshot_id', None, WRONG_TYPE),
        ('eligibility_reason', MISSING, MISSING_REQUIRED),
        ('source_set_fingerprint', SHA.upper(), WRONG_TYPE),
        ('source_set_fingerprint', SHA[:63], WRONG_TYPE),
        ('source_set_fingerprint', SHA + '0', WRONG_TYPE),
        ('source_set_fingerprint', 'g' * 64, WRONG_TYPE),
        ('configuration_bundle_fingerprint', None, WRONG_TYPE),
        ('configuration_bundle_fingerprint', 'abc', WRONG_TYPE),
        ('snapshot_timestamp', 'yesterday', WRONG_TYPE),
        ('snapshot_timestamp', '2026-10-18T08:00:00', WRONG_TYPE),
        ('snapshot_timestamp', '2026-13-01T08:00:00Z', WRONG_TYPE),
        ('source_refs', [1], WRONG_TYPE),
        ('source_refs', 'x', WRONG_TYPE),
        ('index_revision_refs', ['idx'], WRONG_TYPE),
        ('configuration_revision_refs', {'a': 1}, WRONG_TYPE),
        ('batch_ref', 5, WRONG_TYPE),
        ('video_job_ref', ['job'], WRONG_TYPE),
        ('recent_variant_exclusions', 'x', WRONG_TYPE),
    ],
)
def test_field_counterexamples_are_rejected(field: str, value: object, code: str) -> None:
    payload = _valid()
    if value is MISSING:
        del payload[field]
    else:
        payload[field] = value
    assert _issues(payload) == [(code, field)]


def test_each_binding_production_mode_is_valid() -> None:
    for mode in ('single_article', 'multi_article_event', 'from_then_to_now'):
        payload = _valid()
        payload['production_mode'] = mode
        assert _issues(payload) == [], mode


def test_datetime_accepts_rfc3339_with_offset() -> None:
    for value in ('2026-10-18T08:00:00Z', '2026-10-18T08:00:00.123456+07:00', '2026-10-18T08:00:00-05:30'):
        payload = _valid()
        payload['snapshot_timestamp'] = value
        assert _issues(payload) == [], value


def test_unknown_field_is_ignored() -> None:
    payload = _valid()
    payload['x_future_optional_field'] = {'additive': True}
    assert _issues(payload) == []


def test_non_mapping_payload_is_wrong_type() -> None:
    for value in (None, [], 'payload'):
        assert _issues(value) == [(WRONG_TYPE, '$')], value


def test_integer_type_rejects_bool() -> None:
    assert matches_type(1, 'integer') is True
    for value in (True, False, '1', 1.5, None):
        assert matches_type(value, 'integer') is False, value


def test_sha256_type_requires_64_lowercase_hex() -> None:
    assert matches_type(SHA, 'sha256') is True
    for value in (SHA.upper(), SHA[:63], SHA + '0', 'g' * 64, 5, None):
        assert matches_type(value, 'sha256') is False, value


CONTENT_TYPES = ('article_revision', 'event_update_accepted')
TIMESTAMP = '2026-10-18T08:00:00Z'


def _ref(ref_type: str, ref_id: str, revision_id: str) -> dict:
    return {'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def _inputs(**overrides: object) -> dict:
    inputs = {
        'snapshot_id': 'snap-1',
        'production_mode': 'multi_article_event',
        'source_refs': [
            _ref('article_revision', 'a-2', 'rev-1'),
            _ref('article_revision', 'a-1', 'rev-3'),
            _ref('event_update_accepted', 'u-1', 'rev-1'),
        ],
        'index_revision_refs': [_ref('media_index', 'm-1', 'idx-1')],
        'configuration_revision_refs': [_ref('prompt', 'p-1', 'cfg-2'), _ref('preset', 's-1', 'cfg-1')],
        'content_ref_types': CONTENT_TYPES,
        'eligibility_reason': 'multi_article_event_eligible',
        'snapshot_timestamp': TIMESTAMP,
        'batch_ref': 'batch-1',
        'video_job_ref': 'job-1',
        'recent_variant_exclusions': ['variant-b', 'variant-a'],
    }
    inputs.update(overrides)
    return inputs


def _expected_fingerprint(refs: list[dict]) -> str:
    ordered = sorted(refs, key=lambda ref: (ref['ref_type'], ref['ref_id'], ref['revision_id']))
    text = json.dumps(ordered, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def test_build_returns_frozen_snapshot_that_passes_validator() -> None:
    snapshot = build_production_snapshot(**_inputs())
    assert isinstance(snapshot, ProductionSnapshot)
    assert ProductionSnapshot.__dataclass_params__.frozen
    payload = snapshot.to_payload()
    assert validate_production_snapshot(payload) == []
    sources = [
        _ref('article_revision', 'a-1', 'rev-3'),
        _ref('article_revision', 'a-2', 'rev-1'),
        _ref('event_update_accepted', 'u-1', 'rev-1'),
    ]
    configs = [_ref('preset', 's-1', 'cfg-1'), _ref('prompt', 'p-1', 'cfg-2')]
    assert payload['source_refs'] == sources
    assert payload['index_revision_refs'] == [_ref('media_index', 'm-1', 'idx-1')]
    assert payload['configuration_revision_refs'] == configs
    assert payload['source_set_fingerprint'] == _expected_fingerprint(sources)
    assert payload['configuration_bundle_fingerprint'] == _expected_fingerprint(configs)
    assert payload['recent_variant_exclusions'] == ['variant-a', 'variant-b']
    assert (payload['batch_ref'], payload['video_job_ref']) == ('batch-1', 'job-1')
    assert (snapshot.snapshot_id, snapshot.production_mode) == ('snap-1', 'multi_article_event')
    assert (snapshot.eligibility_reason, snapshot.snapshot_timestamp) == ('multi_article_event_eligible', TIMESTAMP)


def test_optional_fields_are_omitted_when_absent() -> None:
    snapshot = build_production_snapshot(**_inputs(batch_ref=None, video_job_ref=None, recent_variant_exclusions=()))
    payload = snapshot.to_payload()
    assert 'batch_ref' not in payload and 'video_job_ref' not in payload
    assert payload['recent_variant_exclusions'] == []
    assert validate_production_snapshot(payload) == []


@pytest.mark.parametrize('mode', ['single_article', 'multi_article_event', 'from_then_to_now'])
def test_each_binding_production_mode_builds(mode: str) -> None:
    snapshot = build_production_snapshot(**_inputs(production_mode=mode))
    assert snapshot.production_mode == mode
    assert validate_production_snapshot(snapshot.to_payload()) == []


def test_build_from_fixture_inputs_matches_fixture_payload() -> None:
    valid = _valid()
    snapshot = build_production_snapshot(
        snapshot_id=valid['snapshot_id'],
        production_mode=valid['production_mode'],
        source_refs=valid['source_refs'],
        index_revision_refs=valid['index_revision_refs'],
        configuration_revision_refs=valid['configuration_revision_refs'],
        content_ref_types=('article_revision',),
        eligibility_reason=valid['eligibility_reason'],
        snapshot_timestamp=valid['snapshot_timestamp'],
        batch_ref=valid['batch_ref'],
    )
    payload = snapshot.to_payload()
    valid['source_set_fingerprint'] = payload['source_set_fingerprint']
    valid['configuration_bundle_fingerprint'] = payload['configuration_bundle_fingerprint']
    valid['recent_variant_exclusions'] = []
    assert payload == valid
    assert payload['source_set_fingerprint'] == _expected_fingerprint(valid['source_refs'])


def test_fingerprint_does_not_depend_on_ref_order() -> None:
    base = _inputs()
    expected = build_production_snapshot(**base)
    for name in ('source_refs', 'configuration_revision_refs'):
        for ordering in itertools.permutations(base[name]):
            rebuilt = build_production_snapshot(**_inputs(**{name: list(ordering)}))
            assert rebuilt.source_set_fingerprint == expected.source_set_fingerprint
            assert rebuilt.configuration_bundle_fingerprint == expected.configuration_bundle_fingerprint
            assert rebuilt == expected


def test_fingerprint_changes_with_revision_or_ref_set() -> None:
    base = build_production_snapshot(**_inputs())
    sources = _inputs()['source_refs']
    bumped = [_ref('article_revision', 'a-1', 'rev-4'), *sources[2:], sources[0]]
    assert build_production_snapshot(**_inputs(source_refs=bumped)).source_set_fingerprint != base.source_set_fingerprint
    added = [*sources, _ref('article_revision', 'a-3', 'rev-1')]
    assert build_production_snapshot(**_inputs(source_refs=added)).source_set_fingerprint != base.source_set_fingerprint
    configs = [_ref('prompt', 'p-1', 'cfg-9'), _ref('preset', 's-1', 'cfg-1')]
    changed = build_production_snapshot(**_inputs(configuration_revision_refs=configs))
    assert changed.configuration_bundle_fingerprint != base.configuration_bundle_fingerprint
    assert changed.source_set_fingerprint == base.source_set_fingerprint


def test_duplicate_and_extra_ref_keys_are_normalized() -> None:
    sources = _inputs()['source_refs']
    noisy = [{**sources[0], 'title': 'x'}, sources[0], *sources[1:]]
    assert build_production_snapshot(**_inputs(source_refs=noisy)) == build_production_snapshot(**_inputs())


def test_fingerprint_is_computed_by_request_hash_on_sorted_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(snapshot_module, 'request_hash', lambda value: calls.append(value) or 'f' * 64)
    refs = [_ref('b', 'x', '2'), _ref('a', 'y', '1'), _ref('a', 'x', '3')]
    assert fingerprint_refs(refs) == 'f' * 64
    assert calls == [[_ref('a', 'x', '3'), _ref('a', 'y', '1'), _ref('b', 'x', '2')]]


def test_snapshot_cannot_be_mutated_after_creation() -> None:
    snapshot = build_production_snapshot(**_inputs())
    for name in ('snapshot_id', 'eligibility_reason', 'source_set_fingerprint', 'source_refs', 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(snapshot, name, 'changed')
    with pytest.raises(TypeError):
        snapshot.source_refs[0]['revision_id'] = 'changed'
    with pytest.raises(TypeError):
        snapshot.configuration_revision_refs[0]['revision_id'] = 'changed'
    assert isinstance(snapshot.source_refs, tuple)


def test_later_changes_to_inputs_do_not_reach_snapshot() -> None:
    inputs = _inputs()
    reference = build_production_snapshot(**copy.deepcopy(inputs))
    snapshot = build_production_snapshot(**inputs)
    inputs['source_refs'][0]['revision_id'] = 'rev-99'
    inputs['source_refs'].append(_ref('article_revision', 'a-9', 'rev-1'))
    inputs['configuration_revision_refs'][0]['revision_id'] = 'cfg-99'
    inputs['recent_variant_exclusions'].append('variant-z')
    assert snapshot == reference
    assert snapshot.to_payload() == reference.to_payload()


def _without_revision(ref: dict, variant: object) -> dict:
    broken = dict(ref)
    if variant is MISSING:
        del broken['revision_id']
    else:
        broken['revision_id'] = variant
    return broken


def _rejection(**overrides: object) -> SnapshotRejected:
    with pytest.raises(SnapshotRejected) as excinfo:
        build_production_snapshot(**_inputs(**overrides))
    return excinfo.value


@pytest.mark.parametrize('name', ['source_refs', 'index_revision_refs', 'configuration_revision_refs'])
@pytest.mark.parametrize('variant', [MISSING, None, ''], ids=['absent', 'none', 'empty'])
def test_missing_revision_id_is_input_not_ready(name: str, variant: object) -> None:
    refs = _inputs()[name]
    rejected = _rejection(**{name: [_without_revision(refs[0], variant), *refs[1:]]})
    assert (rejected.code, rejected.reason) == (INPUT_NOT_READY, 'missing_revision_id')


@pytest.mark.parametrize('ref_type', ['dedup_observation', 'collected_document'])
def test_ref_outside_content_set_is_not_eligible(ref_type: str) -> None:
    mixed = [*_inputs()['source_refs'], _ref(ref_type, 'obs-1', 'rev-1')]
    for sources in (mixed, [_ref(ref_type, 'obs-1', 'rev-1')], [_without_revision(_ref(ref_type, 'obs-1', 'x'), MISSING)]):
        rejected = _rejection(source_refs=sources)
        assert (rejected.code, rejected.reason) == (NOT_ELIGIBLE, 'ref_type_not_content')


def test_duplicate_observation_does_not_create_snapshot() -> None:
    created: list[object] = []
    try:
        created.append(build_production_snapshot(**_inputs(production_mode='single_article', source_refs=[_ref('dedup_observation', 'article-1', 'rev-1')])))
    except SnapshotRejected as rejected:
        assert rejected.code == NOT_ELIGIBLE
    assert created == []


def test_content_ref_types_come_from_policy_without_hidden_default() -> None:
    snapshot = build_production_snapshot(**_inputs(content_ref_types=('dedup_observation',), source_refs=[_ref('dedup_observation', 'o-1', 'rev-1')]))
    assert snapshot.source_refs[0]['ref_type'] == 'dedup_observation'
    assert _rejection(content_ref_types=('dedup_observation',)).code == NOT_ELIGIBLE


def _snapshot_tree() -> ast.Module:
    return ast.parse(SNAPSHOT_SOURCE.read_text(encoding='utf-8'))


def test_missing_policy_inputs_are_input_not_ready() -> None:
    cases = {
        'missing_content_ref_types': {'content_ref_types': ()},
        'missing_eligibility_reason': {'eligibility_reason': None},
        'missing_source_refs': {'source_refs': []},
        'missing_configuration_refs': {'configuration_revision_refs': []},
    }
    for reason, overrides in cases.items():
        rejected = _rejection(**overrides)
        assert (rejected.code, rejected.reason) == (INPUT_NOT_READY, reason), reason
    assert _rejection(eligibility_reason='').reason == 'missing_eligibility_reason'
    assert build_production_snapshot(**_inputs(index_revision_refs=[])).index_revision_refs == ()


def test_invalid_arguments_raise_value_error() -> None:
    bad = [
        {'production_mode': 'timeline'},
        {'production_mode': 'single'},
        {'production_mode': None},
        {'snapshot_id': ''},
        {'snapshot_timestamp': 'yesterday'},
        {'snapshot_timestamp': '2026-10-18T08:00:00'},
        {'source_refs': 'abc'},
        {'source_refs': [1]},
        {'source_refs': [{'ref_type': 'article_revision', 'revision_id': 'rev-1'}]},
        {'batch_ref': ''},
        {'video_job_ref': 5},
        {'recent_variant_exclusions': ['']},
    ]
    for overrides in bad:
        with pytest.raises(ValueError):
            build_production_snapshot(**_inputs(**overrides))


def test_no_article_snapshot_entity() -> None:
    names: set[str] = set()
    for node in ast.walk(_snapshot_tree()):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name)
    assert 'ArticleSnapshot' not in names
    assert not hasattr(snapshot_module, 'ArticleSnapshot')


ALLOWED_IMPORTS = frozenset(
    {'__future__', 're', 'collections.abc', 'dataclasses', 'datetime', 'types', 'controlplane.application.idempotency.canonicalization'}
)


def test_snapshot_imports_stay_inside_allowlist_and_use_request_hash() -> None:
    found: set[str] = set()
    for node in ast.walk(_snapshot_tree()):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add('.' * node.level + (node.module or ''))
    assert found <= ALLOWED_IMPORTS, found
    assert snapshot_module.request_hash is canonicalization.request_hash
