"""F-03: RenderPackage validator theo binding BINDING-F-RENDER-PACKAGE (CT-RND-002).

coveredIds: CT-RND-002 (schema), TST-SEC-INV-020 (phía F)
"""
import ast
import copy
import dataclasses
import json
import pathlib

import pytest

from render.domain.package_contract import (
    BINDING_VERSION,
    CONSTRAINT_VIOLATION,
    FORBIDDEN_FIELD,
    INPUT_ARTIFACT_FIELDS,
    MISSING_REQUIRED,
    RENDER_PACKAGE_FIELDS,
    RENDER_PACKAGE_FORBIDDEN_FIELDS,
    WRONG_TYPE,
    ContractViolation,
    InputArtifactRecord,
    RenderPackageRecord,
    validate_render_package_payload,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'f-render-package.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'package_contract.py'
ENTITY = 'RenderPackage'
DELETE = object()


def _binding() -> dict:
    return json.loads(BINDING_PATH.read_text(encoding='utf-8'))


def _binding_entity() -> dict:
    for entity in _binding()['entities']:
        if entity['name'] == ENTITY:
            return entity
    raise KeyError(f'Entity {ENTITY} not found in binding')


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][ENTITY]


def _valid() -> dict:
    return copy.deepcopy(_fixture()['valid'][0])


def _payload(**changes: object) -> dict:
    payload = _valid()
    for key, val in changes.items():
        if val is DELETE:
            payload.pop(key, None)
        else:
            payload[key] = val
    return payload


def _error(payload: object) -> tuple[str, str]:
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(payload)
    return (info.value.code, info.value.field)


def _constants_view() -> tuple[tuple[tuple[str, str, bool, str | None], ...], tuple[str, ...]]:
    return (
        tuple((f.name, f.type, f.required, f.items) for f in RENDER_PACKAGE_FIELDS),
        tuple(RENDER_PACKAGE_FORBIDDEN_FIELDS),
    )


def _binding_view(entity: dict) -> tuple[tuple[tuple[str, str, bool, str | None], ...], tuple[str, ...]]:
    return (
        tuple((f['name'], f['type'], f['required'], f.get('items')) for f in entity['fields']),
        tuple(entity['forbidden_fields']),
    )


def test_constants_match_binding() -> None:
    entity = _binding_entity()
    assert _constants_view() == _binding_view(entity)
    assert len(RENDER_PACKAGE_FIELDS) == 19
    assert RENDER_PACKAGE_FORBIDDEN_FIELDS == ('shell_command', 'arbitrary_url')
    assert BINDING_VERSION == _binding()['binding_version']


def test_binding_comparison_detects_drift() -> None:
    e1 = copy.deepcopy(_binding_entity())
    e1['fields'][0]['type'] = 'sha256'
    assert _binding_view(e1) != _constants_view()

    e2 = copy.deepcopy(_binding_entity())
    e2['fields'][1]['required'] = False
    assert _binding_view(e2) != _constants_view()

    e3 = copy.deepcopy(_binding_entity())
    del e3['fields'][2]
    assert _binding_view(e3) != _constants_view()

    e4 = copy.deepcopy(_binding_entity())
    e4['forbidden_fields'].pop()
    assert _binding_view(e4) != _constants_view()

    e5 = copy.deepcopy(_binding_entity())
    del e5['fields'][10]['items']
    assert _binding_view(e5) != _constants_view()


def test_record_fields_follow_binding() -> None:
    assert [f.name for f in dataclasses.fields(RenderPackageRecord)] == [f['name'] for f in _binding_entity()['fields']]
    assert [f.name for f in dataclasses.fields(InputArtifactRecord)] == list(INPUT_ARTIFACT_FIELDS)
    assert dict(INPUT_ARTIFACT_FIELDS) == {
        'artifact_version_id': 'string',
        'sha256': 'sha256',
        'size_bytes': 'integer',
        'media_type': 'string',
    }


def test_fixture_invalid_cases_are_the_known_three() -> None:
    assert {c['case'] for c in _fixture()['invalid']} == {
        'missing_hook_placement',
        'input_artifacts_as_string',
        'ai_supplied_shell_command',
    }


@pytest.mark.parametrize('payload', _fixture()['valid'])
def test_valid_fixture_returns_frozen_record(payload: dict) -> None:
    record = validate_render_package_payload(payload)
    assert isinstance(record, RenderPackageRecord)
    assert record.render_package_id == payload['render_package_id']
    assert record.package_fingerprint == payload['package_fingerprint']
    assert record.language_validation_refs == ('lang-val-0001',)
    assert record.input_artifacts == (
        InputArtifactRecord(
            '00000000-0000-4000-8000-000000000053',
            '0123456789abcdef' * 4,
            1024,
            'audio/wav',
        ),
    )
    assert record.timeline['segments'] == ()
    assert record.hook_placement['hook_time_range']['end_ms'] == 3000
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.output_path_ref = 'x'
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.input_artifacts[0].size_bytes = 1
    with pytest.raises(TypeError):
        record.timeline['x'] = 1


@pytest.mark.parametrize('case_data', _fixture()['invalid'], ids=lambda c: c['case'])
def test_fixture_invalid_cases(case_data: dict) -> None:
    expected_error = case_data['expected_error']
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(case_data['payload'])
    assert (info.value.code, info.value.field) == (expected_error['code'], expected_error['field'])
    assert isinstance(info.value, ValueError)


@pytest.mark.parametrize('name', [f.name for f in RENDER_PACKAGE_FIELDS])
def test_missing_each_required_field(name: str) -> None:
    assert _error(_payload(**{name: DELETE})) == (MISSING_REQUIRED, name)


@pytest.mark.parametrize('name', [f.name for f in RENDER_PACKAGE_FIELDS])
def test_none_each_required_field(name: str) -> None:
    assert _error(_payload(**{name: None})) == (WRONG_TYPE, name)


_FIELD_TYPES = {f.name: f.type for f in RENDER_PACKAGE_FIELDS}
_BAD_TYPE_VALUES = {'string': 5, 'sha256': 5, 'array': {}, 'object': []}


@pytest.mark.parametrize('name', [f.name for f in RENDER_PACKAGE_FIELDS])
def test_wrong_type_each_field(name: str) -> None:
    bad_val = _BAD_TYPE_VALUES[_FIELD_TYPES[name]]
    assert _error(_payload(**{name: bad_val})) == (WRONG_TYPE, name)


@pytest.mark.parametrize(
    'value',
    [
        'A' * 64,
        '0123456789ABCDEF' * 4,
        'a' * 63,
        'a' * 65,
        'g' * 64,
        'a' * 64 + '\n',
        ' ' + 'a' * 64,
        '',
    ],
)
def test_package_fingerprint_must_be_lowercase_sha256(value: str) -> None:
    assert _error(_payload(package_fingerprint=value)) == (WRONG_TYPE, 'package_fingerprint')


@pytest.mark.parametrize('value', ['a' * 64, '0123456789abcdef' * 4])
def test_package_fingerprint_valid_cases(value: str) -> None:
    record = validate_render_package_payload(_payload(package_fingerprint=value))
    assert record.package_fingerprint == value


@pytest.mark.parametrize(
    'value',
    [
        'lang-val-0001',
        [1],
        ['ok', None],
        [['x']],
        {'a': 'b'},
    ],
)
def test_language_validation_refs_must_be_array_of_strings(value: object) -> None:
    assert _error(_payload(language_validation_refs=value)) == (WRONG_TYPE, 'language_validation_refs')


def test_language_validation_refs_valid_case() -> None:
    record = validate_render_package_payload(_payload(language_validation_refs=['a', 'b']))
    assert record.language_validation_refs == ('a', 'b')


def test_empty_arrays_are_valid() -> None:
    record = validate_render_package_payload(
        _payload(input_artifacts=[], language_validation_refs=[], allowed_fallbacks=[])
    )
    assert record.input_artifacts == ()
    assert record.language_validation_refs == ()
    assert record.allowed_fallbacks == ()


@pytest.mark.parametrize('value', [None, [], 'x', 5, ()])
def test_non_mapping_payload_is_wrong_type(value: object) -> None:
    assert _error(value) == (WRONG_TYPE, '$')


def test_unknown_fields_are_ignored() -> None:
    payload = _valid()
    payload['extra_field'] = 1
    payload['input_artifacts'][0]['extra'] = 'x'
    payload['timeline']['extra'] = 1
    record = validate_render_package_payload(payload)
    assert not hasattr(record, 'extra_field')
    assert not hasattr(record.input_artifacts[0], 'extra')
    assert len(dataclasses.fields(record)) == 19
    assert len(dataclasses.fields(record.input_artifacts[0])) == 4


def test_payload_is_not_mutated() -> None:
    payload = _valid()
    before = copy.deepcopy(payload)
    validate_render_package_payload(payload)
    assert payload == before
    bad = _payload(materialization_manifest={'a': {'shell_command': 'x'}})
    before_bad = copy.deepcopy(bad)
    _error(bad)
    assert bad == before_bad


def test_record_does_not_alias_payload() -> None:
    payload = _valid()
    record = validate_render_package_payload(payload)
    payload['timeline']['segments'].append({'a': 1})
    payload['hook_placement']['hook_time_range']['end_ms'] = 1
    payload['input_artifacts'][0]['size_bytes'] = 7
    assert record.timeline['segments'] == ()
    assert record.hook_placement['hook_time_range']['end_ms'] == 3000
    assert record.input_artifacts[0].size_bytes == 1024


PATHS = [
    (),
    ('timeline',),
    ('timeline', 'segments', 0),
    ('hook_placement', 'hook_time_range'),
    ('subtitle_config',),
    ('mix_plan',),
    ('allowed_fallbacks', 0),
    ('input_artifacts', 0),
    ('materialization_manifest',),
    ('materialization_manifest', 'a', 'b', 0),
]


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('key', RENDER_PACKAGE_FORBIDDEN_FIELDS)
@pytest.mark.parametrize('value', ['ffmpeg -i x', None])
def test_forbidden_field_is_rejected_at_every_level(path: tuple, key: str, value: object) -> None:
    payload = _payload(
        timeline={'segments': [{}]},
        allowed_fallbacks=[{}],
        materialization_manifest={'a': {'b': [{}]}},
    )
    target = payload
    for step in path:
        target = target[step]
    target[key] = value
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(payload)
    assert info.value.code == FORBIDDEN_FIELD
    assert info.value.field == key
    assert info.value.path.endswith(key)


def test_forbidden_field_paths() -> None:
    p1 = _payload(materialization_manifest={'a': {'b': [{'arbitrary_url': 'http://x'}]}})
    with pytest.raises(ContractViolation) as info1:
        validate_render_package_payload(p1)
    assert info1.value.path == 'materialization_manifest.a.b[0].arbitrary_url'

    p2 = _payload(timeline={'segments': [{'shell_command': 'x'}]})
    with pytest.raises(ContractViolation) as info2:
        validate_render_package_payload(p2)
    assert info2.value.path == 'timeline.segments[0].shell_command'


def test_forbidden_field_wins_over_other_errors() -> None:
    assert _error(_payload(hook_placement=DELETE, shell_command='x')) == (FORBIDDEN_FIELD, 'shell_command')


def test_forbidden_names_in_string_values_are_not_keys() -> None:
    record = validate_render_package_payload(_payload(subtitle_config={'text': 'shell_command arbitrary_url'}))
    assert record.subtitle_config['text'] == 'shell_command arbitrary_url'


def _with_artifact(**changes: object) -> dict:
    payload = _valid()
    part = payload['input_artifacts'][0]
    for key, val in changes.items():
        if val is DELETE:
            part.pop(key, None)
        else:
            part[key] = val
    return payload


@pytest.mark.parametrize('item', ['voice.wav', 5, None, [], ['a']])
def test_input_artifact_must_be_object(item: object) -> None:
    assert _error(_payload(input_artifacts=[item])) == (WRONG_TYPE, 'input_artifacts')


@pytest.mark.parametrize('name', list(INPUT_ARTIFACT_FIELDS))
def test_input_artifact_missing_subfield(name: str) -> None:
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(_with_artifact(**{name: DELETE}))
    assert info.value.code == MISSING_REQUIRED
    assert info.value.field == 'input_artifacts'
    assert info.value.path == f'input_artifacts[0].{name}'


BAD_ARTIFACT = {'artifact_version_id': 5, 'sha256': 5, 'size_bytes': '1', 'media_type': 5}


@pytest.mark.parametrize('name', list(BAD_ARTIFACT))
@pytest.mark.parametrize('kind', ['none', 'wrong'])
def test_input_artifact_subfield_none_or_wrong_type(name: str, kind: str) -> None:
    val = None if kind == 'none' else BAD_ARTIFACT[name]
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(_with_artifact(**{name: val}))
    assert info.value.code == WRONG_TYPE
    assert info.value.field == 'input_artifacts'
    assert info.value.path == f'input_artifacts[0].{name}'


@pytest.mark.parametrize(
    'value',
    [
        'A' * 64,
        '0123456789ABCDEF' * 4,
        'a' * 63,
        'a' * 65,
        'g' * 64,
        'a' * 64 + '\n',
    ],
)
def test_input_artifact_sha256_format(value: str) -> None:
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(_with_artifact(sha256=value))
    assert info.value.code == WRONG_TYPE
    assert info.value.field == 'input_artifacts'
    assert info.value.path == 'input_artifacts[0].sha256'


@pytest.mark.parametrize('value', [True, False, 1.0, 1.5, '1'])
def test_input_artifact_size_bytes_wrong_type(value: object) -> None:
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(_with_artifact(size_bytes=value))
    assert info.value.code == WRONG_TYPE
    assert info.value.field == 'input_artifacts'
    assert info.value.path == 'input_artifacts[0].size_bytes'


@pytest.mark.parametrize('value', [-1, -1024])
def test_input_artifact_size_bytes_constraint_violation(value: int) -> None:
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(_with_artifact(size_bytes=value))
    assert info.value.code == CONSTRAINT_VIOLATION
    assert info.value.field == 'input_artifacts'
    assert info.value.path == 'input_artifacts[0].size_bytes'


@pytest.mark.parametrize('value', [0, 2**40])
def test_input_artifact_size_bytes_valid(value: int) -> None:
    record = validate_render_package_payload(_with_artifact(size_bytes=value))
    assert record.input_artifacts[0].size_bytes == value
    assert type(record.input_artifacts[0].size_bytes) is int


def test_second_artifact_error_reports_its_index() -> None:
    payload = _valid()
    second = copy.deepcopy(payload['input_artifacts'][0])
    second['sha256'] = 'A' * 64
    payload['input_artifacts'].append(second)
    with pytest.raises(ContractViolation) as info:
        validate_render_package_payload(payload)
    assert info.value.path == 'input_artifacts[1].sha256'


def test_valid_artifacts_are_records_in_order() -> None:
    payload = _valid()
    a1 = copy.deepcopy(payload['input_artifacts'][0])
    a1['artifact_version_id'] = 'a1'
    a2 = copy.deepcopy(payload['input_artifacts'][0])
    a2['artifact_version_id'] = 'a2'
    payload['input_artifacts'] = [a1, a2]
    record = validate_render_package_payload(payload)
    assert [a.artifact_version_id for a in record.input_artifacts] == ['a1', 'a2']
    assert all(isinstance(a, InputArtifactRecord) for a in record.input_artifacts)


def test_module_imports_only_pure_stdlib() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert names <= {'__future__', 're', 'collections.abc', 'dataclasses', 'types'}


def test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
