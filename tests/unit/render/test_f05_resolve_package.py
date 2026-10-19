"""F-05: resolve render package từ refs đã khóa (CT-RND-002).

coveredIds: CT-RND-002, acceptance §8 mục 6 (phía resolve)
"""
import ast
import copy
import dataclasses
import json
import pathlib
import uuid

import pytest

from render.domain.package_contract import CONSTRAINT_VIOLATION, MISSING_REQUIRED, RENDER_PACKAGE_FIELDS, WRONG_TYPE, RenderPackageRecord
from render.domain.package_fingerprint import HASHED_FIELDS, compute_package_fingerprint, verify_package_fingerprint
from render.domain.resolve_package import (
    ASSET_OUTSIDE_PLAN_OR_FALLBACK, DUPLICATE_ARTIFACT_VERSION, DUPLICATE_MATERIALIZATION_REF,
    INVALID_MATERIALIZATION_REF, RENDER_PACKAGE_NAMESPACE, URL_NOT_ALLOWED, ResolveError, resolve_render_package,
)
from render.ports.inputs import ArtifactInfoPort, LocalMaterialRef, PlanAssetPort, ResolveInputs, ResolvedAsset

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'resolve_package.py'
INPUTS_PATH = ROOT / 'src' / 'render' / 'ports' / 'inputs.py'
SHA_A = 'a' * 64
ASSET_ID = '00000000-0000-4000-8000-000000000053'
VISUAL_ID = '00000000-0000-4000-8000-000000000054'
AUDIO_ID = '00000000-0000-4000-8000-000000000055'
THUMB_ID = '00000000-0000-4000-8000-000000000056'
OTHER_ID = '00000000-0000-4000-8000-000000000099'
PLAN_REFS = (ASSET_ID, VISUAL_ID, AUDIO_ID, THUMB_ID)
BACKSLASH = chr(92)


class FakePlan:
    def __init__(self, refs) -> None:
        self.refs = refs
        self.calls: list[str] = []

    def asset_refs(self, production_plan_ref):
        self.calls.append(production_plan_ref)
        return self.refs


class FakeInfo:
    def get_asset(self, artifact_version_id):
        return None


def _valid() -> dict:
    return copy.deepcopy(json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['RenderPackage']['valid'][0])


def _asset(version: str = OTHER_ID, role: str = 'visual', **changes) -> ResolvedAsset:
    values = {'artifact_version_id': version, 'sha256': SHA_A, 'size_bytes': 5, 'media_type': 'image/png', 'role': role}
    return ResolvedAsset(**{**values, **changes})


def _inputs(**changes) -> ResolveInputs:
    valid = _valid()
    values = {name: valid[name] for name in HASHED_FIELDS}
    values['language_validation_refs'] = tuple(valid['language_validation_refs'])
    values['input_artifacts'] = tuple(ResolvedAsset(**item, role='voice') for item in valid['input_artifacts'])
    values['allowed_fallbacks'] = tuple(valid['allowed_fallbacks'])
    values['materialization_manifest'] = (LocalMaterialRef(artifact_version_id=ASSET_ID, local_ref='voice.wav'),)
    values.update(changes)
    return ResolveInputs(**values)


def _plan(refs=PLAN_REFS) -> FakePlan:
    return FakePlan(tuple(refs))


def _resolve(inputs=None, plan=None) -> RenderPackageRecord:
    record = resolve_render_package(_inputs() if inputs is None else inputs, _plan() if plan is None else plan)
    assert isinstance(record, RenderPackageRecord)
    return record


def _error(inputs, plan=None) -> ResolveError:
    with pytest.raises(ResolveError) as info:
        resolve_render_package(inputs, _plan() if plan is None else plan)
    return info.value

def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif hasattr(value, 'items'):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)
    elif dataclasses.is_dataclass(value):
        for item in dataclasses.fields(value):
            yield from _strings(getattr(value, item.name))


def _imports(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
    return roots


def test_dtos_are_frozen_with_the_specified_fields() -> None:
    assert [f.name for f in dataclasses.fields(ResolvedAsset)] == ['artifact_version_id', 'sha256', 'size_bytes', 'media_type', 'role']
    assert {f.name for f in dataclasses.fields(ResolveInputs)} == set(HASHED_FIELDS)
    for item in (_asset(), _inputs(), LocalMaterialRef(artifact_version_id='a', local_ref='b.wav')):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(item, dataclasses.fields(item)[0].name, 'x')


def test_ports_are_runtime_protocols() -> None:
    assert isinstance(_plan(), PlanAssetPort) and isinstance(FakeInfo(), ArtifactInfoPort)
    assert not isinstance(object(), PlanAssetPort) and not isinstance(object(), ArtifactInfoPort)


def test_ports_module_is_stdlib_only() -> None:
    assert _imports(INPUTS_PATH) <= {'__future__', 'collections', 'dataclasses', 'typing'}

def test_resolve_builds_valid_record_with_f04_fingerprint_and_uuid5_id() -> None:
    inputs, plan = _inputs(), _plan()
    record = _resolve(inputs, plan)
    assert {f.name for f in dataclasses.fields(record)} == {spec.name for spec in RENDER_PACKAGE_FIELDS}
    assert record.package_fingerprint == compute_package_fingerprint(record)
    verify_package_fingerprint(record)
    assert record.render_package_id == str(uuid.uuid5(RENDER_PACKAGE_NAMESPACE, record.package_fingerprint))
    assert plan.calls == [inputs.production_plan_ref]
    for name in HASHED_FIELDS:
        if isinstance(getattr(inputs, name), str):
            assert getattr(record, name) == getattr(inputs, name)
    assert dataclasses.asdict(record.input_artifacts[0]) == _valid()['input_artifacts'][0]
    assert record.materialization_manifest == {ASSET_ID: {'local_ref': 'voice.wav'}}


def test_repeated_resolve_returns_same_package_and_id() -> None:
    first, second = _resolve(), _resolve()
    assert first == second and first.render_package_id == second.render_package_id


def test_different_content_gives_different_fingerprint_and_id() -> None:
    base, changed = _resolve(), _resolve(_inputs(output_profile_revision='out-prof-v2'))
    assert base.package_fingerprint != changed.package_fingerprint
    assert base.render_package_id != changed.render_package_id


def test_input_order_does_not_change_package() -> None:
    extra = _asset()
    plan = _plan((*PLAN_REFS, OTHER_ID))
    one = _inputs(input_artifacts=(*_inputs().input_artifacts, extra), language_validation_refs=('lang-a', 'lang-b'))
    two = _inputs(input_artifacts=(extra, *_inputs().input_artifacts), language_validation_refs=('lang-b', 'lang-a'))
    assert _resolve(one, plan) == _resolve(two, plan)


def test_later_mutation_of_inputs_does_not_change_record() -> None:
    timeline = {'segments': [{'start_ms': 0, 'end_ms': 10, 'visual_asset_refs': [ASSET_ID]}]}
    record = _resolve(_inputs(timeline=timeline))
    before = record.package_fingerprint
    timeline['segments'][0]['visual_asset_refs'].append(OTHER_ID)
    assert compute_package_fingerprint(record) == before
    assert record.timeline['segments'][0]['visual_asset_refs'] == (ASSET_ID,)


def test_caption_text_passes_through_verbatim_and_f_adds_nothing() -> None:
    config = {'karaoke': True, 'caption_text': 'Xin chào'}
    record = _resolve(_inputs(subtitle_config=config))
    assert dict(record.subtitle_config) == config
    assert not any('://' in text for text in _strings(record))
    assert record.mix_plan == {} and record.allowed_fallbacks == ()

def test_asset_outside_plan_and_fallbacks_is_rejected() -> None:
    error = _error(_inputs(input_artifacts=(*_inputs().input_artifacts, _asset())))
    assert (error.code, error.field) == (ASSET_OUTSIDE_PLAN_OR_FALLBACK, 'input_artifacts[1]')


def test_fallback_with_artifact_id_allows_that_asset_but_plain_fallback_does_not() -> None:
    assets = (*_inputs().input_artifacts, _asset())
    record = _resolve(_inputs(input_artifacts=assets, allowed_fallbacks=({'kind': 'technical', 'artifact_version_id': OTHER_ID},)))
    assert OTHER_ID in {item.artifact_version_id for item in record.input_artifacts}
    error = _error(_inputs(input_artifacts=assets, allowed_fallbacks=({'kind': 'technical'},)))
    assert error.code == ASSET_OUTSIDE_PLAN_OR_FALLBACK


def test_voice_and_word_timing_assets_are_exempt_from_plan_membership() -> None:
    inputs = _inputs()
    voice = _asset(inputs.voice_artifact_ref, 'voice')
    timing = _asset(inputs.word_timing_ref, 'word_timing')
    assert _resolve(_inputs(input_artifacts=(*inputs.input_artifacts, voice, timing)))


def test_timeline_and_hook_refs_outside_plan_are_rejected() -> None:
    segment = {'start_ms': 0, 'end_ms': 10, 'visual_asset_refs': [OTHER_ID]}
    error = _error(_inputs(timeline={'segments': [segment]}))
    assert (error.code, error.field) == (ASSET_OUTSIDE_PLAN_OR_FALLBACK, 'timeline.segments[0].visual_asset_refs[0]')
    hook = {**_valid()['hook_placement'], 'visual_hook_ref': OTHER_ID}
    error = _error(_inputs(hook_placement=hook))
    assert (error.code, error.field) == (ASSET_OUTSIDE_PLAN_OR_FALLBACK, 'hook_placement.visual_hook_ref')


def test_plan_port_and_inputs_type_are_checked() -> None:
    error = _error(_inputs(), FakePlan(None))
    assert (error.code, error.field) == (MISSING_REQUIRED, 'plan_assets')
    with pytest.raises(ResolveError) as info:
        resolve_render_package(_inputs(), object())
    assert (info.value.code, info.value.field) == (WRONG_TYPE, 'plan_assets')
    with pytest.raises(ResolveError) as info:
        resolve_render_package({}, _plan())
    assert (info.value.code, info.value.field) == (WRONG_TYPE, 'inputs')


def test_duplicate_artifact_version_is_rejected() -> None:
    error = _error(_inputs(input_artifacts=(*_inputs().input_artifacts, _asset(ASSET_ID))))
    assert (error.code, error.field) == (DUPLICATE_ARTIFACT_VERSION, 'input_artifacts[1].artifact_version_id')


@pytest.mark.parametrize('name, value, field', [
    ('subtitle_config', {'karaoke': True, 'caption': 'see https://x.test/a'}, 'subtitle_config.caption'),
    ('mix_plan', {'tracks': ['http://x.test/a']}, 'mix_plan.tracks[0]'),
    ('allowed_fallbacks', ({'kind': 'a', 'source': 'https://x.test'},), 'allowed_fallbacks[0].source'),
    ('timeline', {'segments': [{'note': 'ftp://h/x'}]}, 'timeline.segments[0].note'),
    ('output_path_ref', 'file:///c:/x', 'output_path_ref'),
    ('script_version_ref', 'https://x.test/s', 'script_version_ref'),
])
def test_url_anywhere_in_inputs_is_rejected(name, value, field) -> None:
    error = _error(_inputs(**{name: value}))
    assert (error.code, error.field) == (URL_NOT_ALLOWED, field)


@pytest.mark.parametrize('name, value, field', [
    ('mix_plan', {'shell_command': 'x'}, 'shell_command'),
    ('subtitle_config', {'a': {'arbitrary_url': 'x'}}, 'arbitrary_url'),
])
def test_forbidden_fields_are_rejected_with_field(name, value, field) -> None:
    error = _error(_inputs(**{name: value}))
    assert (error.code, error.field) == ('forbidden_field', field)

@pytest.mark.parametrize('name', HASHED_FIELDS)
def test_missing_input_reports_field(name) -> None:
    error = _error(_inputs(**{name: None}))
    assert (error.code, error.field) == (MISSING_REQUIRED, name)


def test_blank_text_input_is_missing() -> None:
    error = _error(_inputs(production_snapshot_ref='  '))
    assert (error.code, error.field) == (MISSING_REQUIRED, 'production_snapshot_ref')


@pytest.mark.parametrize('name, value', [
    ('timeline', 'x'), ('hook_placement', []), ('subtitle_config', 1), ('mix_plan', 'x'),
    ('language_validation_refs', 'abc'), ('allowed_fallbacks', 'abc'), ('input_artifacts', 'abc'),
    ('materialization_manifest', 'abc'), ('production_snapshot_ref', 5), ('output_path_ref', 5),
])
def test_wrong_type_input_reports_field(name, value) -> None:
    error = _error(_inputs(**{name: value}))
    assert (error.code, error.field) == (WRONG_TYPE, name)


def test_element_level_errors_carry_field() -> None:
    cases = [
        (_inputs(input_artifacts=({'artifact_version_id': ASSET_ID},)), WRONG_TYPE, 'input_artifacts[0]'),
        (_inputs(input_artifacts=(_asset(ASSET_ID, role=None),)), MISSING_REQUIRED, 'input_artifacts[0].role'),
        (_inputs(input_artifacts=(_asset(ASSET_ID, sha256='A' * 64),)), WRONG_TYPE, 'input_artifacts'),
        (_inputs(input_artifacts=(_asset(ASSET_ID, size_bytes=True),)), WRONG_TYPE, 'input_artifacts'),
        (_inputs(input_artifacts=(_asset(ASSET_ID, size_bytes=-1),)), CONSTRAINT_VIOLATION, 'input_artifacts'),
        (_inputs(language_validation_refs=(7,)), WRONG_TYPE, 'language_validation_refs[0]'),
        (_inputs(allowed_fallbacks=('x',)), WRONG_TYPE, 'allowed_fallbacks[0]'),
    ]
    for inputs, code, field in cases:
        error = _error(inputs)
        assert (error.code, error.field) == (code, field)


@pytest.mark.parametrize('local', [
    'C:' + BACKSLASH + 'x' + BACKSLASH + 'a.mp4', '/etc/a.mp4', '../a.mp4', 'a/b.mp4', 'a' + BACKSLASH + 'b.mp4',
    'https://x.test/a.mp4', 'a:b', '.hidden',
])
def test_free_path_strings_are_not_accepted_as_local_refs(local) -> None:
    error = _error(_inputs(materialization_manifest=(LocalMaterialRef(artifact_version_id=ASSET_ID, local_ref=local),)))
    assert (error.code, error.field) == (INVALID_MATERIALIZATION_REF, 'materialization_manifest[0].local_ref')


def test_materialization_only_accepts_local_material_ref_objects() -> None:
    for item in ('voice.wav', {'artifact_version_id': ASSET_ID, 'local_ref': 'voice.wav'}):
        error = _error(_inputs(materialization_manifest=(item,)))
        assert (error.code, error.field) == (WRONG_TYPE, 'materialization_manifest[0]')
    ref = LocalMaterialRef(artifact_version_id=ASSET_ID, local_ref='voice.wav')
    error = _error(_inputs(materialization_manifest=(ref, ref)))
    assert (error.code, error.field) == (DUPLICATE_MATERIALIZATION_REF, 'materialization_manifest[1].artifact_version_id')
    two = (ref, LocalMaterialRef(artifact_version_id=OTHER_ID, local_ref='clip_01.mp4'))
    assert set(_resolve(_inputs(materialization_manifest=two)).materialization_manifest) == {ASSET_ID, OTHER_ID}


def test_module_is_pure_and_declares_covered_ids() -> None:
    source = MODULE_PATH.read_text(encoding='utf-8')
    assert _imports(MODULE_PATH) <= {'__future__', 'collections', 'dataclasses', 're', 'uuid', 'render'}
    assert 'uuid4' not in source and 'uuid1' not in source and 'src.' not in source
    assert not any(isinstance(node, ast.Constant) and isinstance(node.value, str) and '://' in node.value for node in ast.walk(ast.parse(source)))
    assert 'coveredIds: CT-RND-002' in source
