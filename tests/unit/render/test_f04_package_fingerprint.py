"""F-04: fingerprint bất biến của RenderPackage (CT-RND-002).

coveredIds: CT-RND-002, acceptance §8 mục 1
"""
import ast
import copy
import dataclasses
import json
import pathlib
import re
from unittest import mock

import pytest

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain import package_fingerprint
from render.domain.package_contract import RenderPackageRecord, validate_render_package_payload
from render.domain.package_fingerprint import (
    EXCLUDED_FIELDS,
    INVALID_VALUE,
    PACKAGE_FINGERPRINT_MISMATCH,
    WRONG_TYPE,
    PackageFingerprintError,
    compute_package_fingerprint,
    verify_package_fingerprint,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'package_fingerprint.py'
SHA_A = 'a' * 64
SHA_B = 'b' * 64
SHA_C = 'c' * 64
CANONICALIZER = 'controlplane.application.idempotency.canonicalization'
HASHED = [f.name for f in dataclasses.fields(RenderPackageRecord) if f.name not in EXCLUDED_FIELDS]


def _valid() -> dict:
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return copy.deepcopy(data['entities']['RenderPackage']['valid'][0])


def _artifact(version: str, sha: str = SHA_A, size: int = 10, media: str = 'audio/wav') -> dict:
    return {'artifact_version_id': version, 'sha256': sha, 'size_bytes': size, 'media_type': media}


def _rich_payload() -> dict:
    payload = _valid()
    payload['language_validation_refs'] = ['lang-b', 'lang-a', 'lang-c']
    payload['input_artifacts'] = [_artifact('art-2', SHA_B, 20, 'image/png'), _artifact('art-1')]
    payload['timeline'] = {
        'segments': [{'id': 's1', 'start_ms': 0, 'end_ms': 10}, {'id': 's2', 'start_ms': 10, 'end_ms': 20}],
        'fps': 30,
    }
    payload['mix_plan'] = {'voice_gain': 1, 'music': {'duck': True, 'curve': [1, 2]}}
    payload['subtitle_config'] = {'karaoke': True, 'style': {'font': 'x', 'size': 12}}
    payload['allowed_fallbacks'] = [{'kind': 'a', 'order': 1}]
    payload['materialization_manifest'] = {'items': [{'ref': 'r1', 'kind': 'k'}]}
    return payload


def _record(payload: dict | None = None) -> RenderPackageRecord:
    return validate_render_package_payload(_rich_payload() if payload is None else payload)


def _sealed(record: RenderPackageRecord) -> RenderPackageRecord:
    return dataclasses.replace(record, package_fingerprint=compute_package_fingerprint(record))


def _reverse_keys(value: object) -> object:
    if isinstance(value, dict):
        return {key: _reverse_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_keys(item) for item in value]
    return value


def _changed(record: RenderPackageRecord, name: str) -> object:
    value = getattr(record, name)
    if name == 'input_artifacts':
        return ()
    if name == 'language_validation_refs':
        return (*value, 'lang-extra')
    if name == 'allowed_fallbacks':
        return (*value, {'kind': 'extra'})
    if isinstance(value, str):
        return value + '-changed'
    return {**value, 'changed_marker': 1}


def test_fingerprint_is_request_hash_of_every_field_except_the_two_excluded() -> None:
    payload = _rich_payload()
    basis = {key: value for key, value in payload.items() if key not in EXCLUDED_FIELDS}
    basis['language_validation_refs'] = ['lang-a', 'lang-b', 'lang-c']
    basis['input_artifacts'] = [_artifact('art-1'), _artifact('art-2', SHA_B, 20, 'image/png')]
    fingerprint = compute_package_fingerprint(validate_render_package_payload(payload))
    assert fingerprint == request_hash(basis)
    assert re.fullmatch(r'[0-9a-f]{64}', fingerprint)


def test_hashed_basis_covers_all_record_fields_but_two() -> None:
    record = _record()
    with mock.patch.object(package_fingerprint, 'request_hash', wraps=request_hash) as spy:
        compute_package_fingerprint(record)
    basis = spy.call_args.args[0]
    assert EXCLUDED_FIELDS == ('package_fingerprint', 'render_package_id')
    assert set(basis) == {f.name for f in dataclasses.fields(RenderPackageRecord)} - set(EXCLUDED_FIELDS)
    assert len(basis) == 17
    for name in ('preset_revision_ref', 'output_profile_revision', 'word_timing_ref'):
        assert name in basis


def test_fingerprint_is_deterministic_and_ignores_identity_fields() -> None:
    record = _record()
    assert compute_package_fingerprint(record) == compute_package_fingerprint(_record())
    other = dataclasses.replace(record, render_package_id='other-id', package_fingerprint='f' * 64)
    assert compute_package_fingerprint(other) == compute_package_fingerprint(record)


@pytest.mark.parametrize('name', HASHED)
def test_changing_any_hashed_field_changes_fingerprint(name: str) -> None:
    record = _record()
    changed = dataclasses.replace(record, **{name: _changed(record, name)})
    assert compute_package_fingerprint(changed) != compute_package_fingerprint(record)


@pytest.mark.parametrize(
    ('attr', 'value'),
    [('sha256', SHA_C), ('size_bytes', 11), ('media_type', 'video/mp4'), ('artifact_version_id', 'art-9')],
)
def test_changing_input_artifact_field_changes_fingerprint(attr: str, value: object) -> None:
    record = _record()
    first = dataclasses.replace(record.input_artifacts[0], **{attr: value})
    changed = dataclasses.replace(record, input_artifacts=(first, *record.input_artifacts[1:]))
    assert compute_package_fingerprint(changed) != compute_package_fingerprint(record)


def test_dict_key_order_does_not_change_fingerprint() -> None:
    payload = _rich_payload()
    reordered = _reverse_keys(payload)
    assert list(reordered) != list(payload)
    assert list(reordered['mix_plan']) != list(payload['mix_plan'])
    assert list(reordered['timeline']['segments'][0]) != list(payload['timeline']['segments'][0])
    assert compute_package_fingerprint(_record(reordered)) == compute_package_fingerprint(_record(payload))


def test_input_artifacts_order_does_not_change_fingerprint() -> None:
    payload = _rich_payload()
    swapped = copy.deepcopy(payload)
    swapped['input_artifacts'].reverse()
    assert swapped['input_artifacts'] != payload['input_artifacts']
    assert compute_package_fingerprint(_record(swapped)) == compute_package_fingerprint(_record(payload))


def test_input_artifacts_with_same_version_id_are_ordered_deterministically() -> None:
    payload = _rich_payload()
    payload['input_artifacts'] = [_artifact('same', SHA_A), _artifact('same', SHA_B)]
    swapped = copy.deepcopy(payload)
    swapped['input_artifacts'].reverse()
    assert compute_package_fingerprint(_record(swapped)) == compute_package_fingerprint(_record(payload))


def test_language_validation_refs_order_does_not_change_fingerprint() -> None:
    payload = _rich_payload()
    swapped = copy.deepcopy(payload)
    swapped['language_validation_refs'].reverse()
    assert swapped['language_validation_refs'] != payload['language_validation_refs']
    assert compute_package_fingerprint(_record(swapped)) == compute_package_fingerprint(_record(payload))


def test_timeline_segment_order_changes_fingerprint() -> None:
    payload = _rich_payload()
    swapped = copy.deepcopy(payload)
    swapped['timeline']['segments'].reverse()
    assert swapped['timeline']['segments'] != payload['timeline']['segments']
    assert compute_package_fingerprint(_record(swapped)) != compute_package_fingerprint(_record(payload))


def test_source_payload_mutation_after_resolve_does_not_change_fingerprint() -> None:
    payload = _rich_payload()
    record = _record(payload)
    before = compute_package_fingerprint(record)
    payload['timeline']['segments'].append({'id': 's3'})
    payload['input_artifacts'][0]['sha256'] = SHA_A
    payload['mix_plan']['voice_gain'] = 2
    assert compute_package_fingerprint(record) == before


def test_verify_accepts_matching_fingerprint() -> None:
    assert verify_package_fingerprint(_sealed(_record())) is None


def test_verify_rejects_wrong_stored_fingerprint() -> None:
    record = dataclasses.replace(_record(), package_fingerprint='f' * 64)
    with pytest.raises(PackageFingerprintError) as info:
        verify_package_fingerprint(record)
    assert (info.value.code, info.value.field) == (PACKAGE_FINGERPRINT_MISMATCH, 'package_fingerprint')
    assert isinstance(info.value, ValueError)


@pytest.mark.parametrize('name', HASHED)
def test_verify_rejects_package_edited_after_sealing(name: str) -> None:
    sealed = _sealed(_record())
    edited = dataclasses.replace(sealed, **{name: _changed(sealed, name)})
    with pytest.raises(PackageFingerprintError) as info:
        verify_package_fingerprint(edited)
    assert (info.value.code, info.value.field) == (PACKAGE_FINGERPRINT_MISMATCH, 'package_fingerprint')


def test_sealed_record_cannot_be_edited_in_place() -> None:
    sealed = _sealed(_record())
    for name in ('package_fingerprint', 'preset_revision_ref', 'input_artifacts'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(sealed, name, sealed.package_fingerprint)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sealed.input_artifacts[0].sha256 = SHA_A
    with pytest.raises(TypeError):
        sealed.timeline['fps'] = 1
    with pytest.raises(TypeError):
        sealed.timeline['segments'][0]['id'] = 'x'


@pytest.mark.parametrize('value', [None, {}, 'x', 5])
def test_compute_and_verify_reject_non_record(value: object) -> None:
    for func in (compute_package_fingerprint, verify_package_fingerprint):
        with pytest.raises(PackageFingerprintError) as info:
            func(value)
        assert (info.value.code, info.value.field) == (WRONG_TYPE, 'record')


def test_compute_rejects_malformed_collections() -> None:
    record = _record()
    for name, value in (('input_artifacts', ({'artifact_version_id': 'x'},)), ('language_validation_refs', ('ok', 5))):
        bad = dataclasses.replace(record, **{name: value})
        with pytest.raises(PackageFingerprintError) as info:
            compute_package_fingerprint(bad)
        assert (info.value.code, info.value.field) == (WRONG_TYPE, name)


def test_compute_rejects_values_the_canonicalizer_refuses() -> None:
    bad = dataclasses.replace(_record(), timeline={'segments': (), 'bad': float('nan')})
    with pytest.raises(PackageFingerprintError) as info:
        compute_package_fingerprint(bad)
    assert (info.value.code, info.value.field) == (INVALID_VALUE, 'package_fingerprint')


def test_module_uses_shared_canonicalizer_and_pure_imports() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert names <= {'__future__', 'collections.abc', 'dataclasses', CANONICALIZER, 'render.domain.package_contract'}
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == CANONICALIZER
        for alias in node.names
    }
    assert imported == {'request_hash'}


def test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
