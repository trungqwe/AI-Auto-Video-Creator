"""J-05: resolve bundle cấu hình có provenance (CT-CFG-002).

coveredIds: CT-CFG-002, TST-INT-INV-004, TST-SEC-INV-020
"""
import ast
import copy
import dataclasses
import hashlib
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.application.config_security.bundle_resolution import (
    BundleRequest, BundleSecretError, ConfigBundle, EffectiveConfigRevision, MissingPinError, MissingScopeError, PinnedRevisionInvalidatedError,
    resolve_bundle,
)
from controlplane.application.idempotency import request_hash
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'config_security' / 'bundle_resolution.py'
WS = 'ws-1'
T0 = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
PUBLISHED = ConfigRevisionStatus.PUBLISHED
SUPERSEDED = ConfigRevisionStatus.SUPERSEDED
INVALIDATED = ConfigRevisionStatus.INVALIDATED
DRAFT = ConfigRevisionStatus.DRAFT
WORKSPACE_SCOPE = ('workspace', 'default')
KINDS = ('workspace', 'module', 'provider', 'preset', 'policy')
P5A_FIELDS = [
    'config_revision_id', 'workspace_id', 'scope_kind', 'scope_key', 'config_revision_number', 'revision', 'content_hash', 'payload', 'status',
]


def _rid(kind: str, key: str, number: int, workspace_id: str = WS) -> str:
    return f'{workspace_id}-{kind}-{key}-{number}'


def _rev(kind: str, key: str, number: int, status: ConfigRevisionStatus = PUBLISHED, *, workspace_id: str = WS, payload: dict | None = None, effective_at: datetime | None = None) -> EffectiveConfigRevision:
    payload = {'from': _rid(kind, key, number)} if payload is None else payload
    revision = ConfigRevision(
        config_revision_id=_rid(kind, key, number, workspace_id), workspace_id=workspace_id, scope_kind=kind, scope_key=key,
        config_revision_number=number, revision=number + 10, content_hash=request_hash(payload), payload=payload, status=status,
    )
    return EffectiveConfigRevision(revision, effective_at)


def _ws(number: int, status: ConfigRevisionStatus = PUBLISHED, **kwargs: object) -> EffectiveConfigRevision:
    return _rev('workspace', 'default', number, status, **kwargs)


def _request(**overrides: object) -> BundleRequest:
    fields = dict(
        workspace_id=WS, job_ref='job-1', stage_ref='script', evaluation_time=T0, required_scopes=(WORKSPACE_SCOPE,), snapshot_state='NOT_COMMITTED',
    )
    fields.update(overrides)
    return BundleRequest(**fields)


def _committed(revisions: list, pins: dict) -> ConfigBundle:
    return resolve_bundle(revisions, _request(snapshot_state='COMMITTED', pinned_revision_ids=pins))


def _layers() -> list[EffectiveConfigRevision]:
    return [_rev(kind, 'default', 1, payload={'x': kind, f'own_{kind}': 1}) for kind in KINDS]


def _all_scopes() -> tuple:
    return tuple((kind, 'default') for kind in KINDS)


def test_p5a_config_revision_keeps_nine_fields_without_effective_at() -> None:
    assert [f.name for f in dataclasses.fields(ConfigRevision)] == P5A_FIELDS
    assert 'effective_at' not in P5A_FIELDS


def test_effective_config_revision_is_frozen_wrapper_of_p5a_revision() -> None:
    wrapper = _ws(1)
    assert [f.name for f in dataclasses.fields(EffectiveConfigRevision)] == ['revision', 'effective_at']
    assert EffectiveConfigRevision.__dataclass_params__.frozen
    assert isinstance(wrapper.revision, ConfigRevision)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(wrapper, 'effective_at', None)


def test_naive_effective_at_raises_value_error_with_code() -> None:
    with pytest.raises(ValueError) as caught:
        _ws(1, effective_at=datetime(2026, 10, 20, 12, 0))
    assert type(caught.value) is ValueError
    assert str(caught.value) == 'naive_effective_at'


@pytest.mark.parametrize('effective_at', [None, T0, T0 - timedelta(days=1), datetime(2026, 10, 20, 19, 0, tzinfo=timezone(timedelta(hours=7)))])
def test_none_or_aware_effective_at_is_accepted(effective_at: datetime | None) -> None:
    assert _ws(1, effective_at=effective_at).effective_at == effective_at


def test_future_effective_at_is_ignored_and_not_applied_early() -> None:
    bundle = resolve_bundle([_ws(1), _ws(2, effective_at=T0 + timedelta(seconds=1))], _request())
    assert bundle.revision_refs == (_rid('workspace', 'default', 1),)
    assert bundle.values == {'from': _rid('workspace', 'default', 1)}


@pytest.mark.parametrize('effective_at', [None, T0, T0 - timedelta(hours=1)])
def test_none_equal_or_past_effective_at_is_applied(effective_at: datetime | None) -> None:
    bundle = resolve_bundle([_ws(1), _ws(2, effective_at=effective_at)], _request())
    assert bundle.revision_refs == (_rid('workspace', 'default', 2),)


def test_latest_effective_number_wins_per_scope() -> None:
    revisions = [_ws(3, effective_at=T0 + timedelta(hours=1)), _ws(1), _ws(2, effective_at=T0 - timedelta(hours=1))]
    assert resolve_bundle(revisions, _request()).revision_refs == (_rid('workspace', 'default', 2),)


@pytest.mark.parametrize('status', [SUPERSEDED, INVALIDATED, DRAFT])
def test_only_published_revisions_are_selected_when_not_committed(status: ConfigRevisionStatus) -> None:
    assert resolve_bundle([_ws(1), _ws(2, status)], _request()).revision_refs == (_rid('workspace', 'default', 1),)
    with pytest.raises(MissingScopeError):
        resolve_bundle([_ws(2, status)], _request())


def test_missing_required_scope_raises_missing_scope() -> None:
    with pytest.raises(MissingScopeError) as caught:
        resolve_bundle([_ws(1), _rev('provider', 'gemini', 1)], _request(required_scopes=(WORKSPACE_SCOPE, ('provider', 'openai'))))
    assert str(caught.value) == 'missing_scope'
    with pytest.raises(MissingScopeError):
        resolve_bundle([], _request())


def test_revision_of_another_workspace_is_skipped_without_revealing_it() -> None:
    foreign = _ws(9, workspace_id='ws-2')
    bundle = resolve_bundle([_ws(1), foreign], _request())
    assert bundle.revision_refs == (_rid('workspace', 'default', 1),)
    assert 'ws-2' not in repr(bundle)
    with pytest.raises(MissingScopeError) as caught:
        resolve_bundle([foreign], _request())
    assert str(caught.value) == 'missing_scope'
    assert 'ws-2' not in str(caught.value)


def test_invalid_request_is_rejected_with_codes() -> None:
    cases = [
        ({'snapshot_state': 'committed'}, 'invalid_snapshot_state'),
        ({'evaluation_time': datetime(2026, 10, 20)}, 'naive_evaluation_time'),
        ({'required_scopes': (('account', 'x'),)}, 'invalid_scope_kind'),
    ]
    for overrides, code in cases:
        with pytest.raises(ValueError) as caught:
            resolve_bundle([_ws(1)], _request(**overrides))
        assert type(caught.value) is ValueError
        assert str(caught.value) == code


def test_job_snapshot_keeps_old_revision_and_fingerprint_after_new_publish() -> None:
    before = [_ws(1, payload={'model': 'old'})]
    snapshot = resolve_bundle(before, _request())
    pins = {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)}
    after = before + [_ws(2, payload={'model': 'new'})]
    committed = _committed(after, pins)
    fresh = resolve_bundle(after, _request(job_ref='job-2'))
    assert committed.revision_refs == snapshot.revision_refs
    assert committed.values == {'model': 'old'}
    assert committed.bundle_fingerprint == snapshot.bundle_fingerprint
    assert fresh.revision_refs == (_rid('workspace', 'default', 2),)
    assert fresh.values == {'model': 'new'}
    assert fresh.bundle_fingerprint != snapshot.bundle_fingerprint


def test_committed_without_pin_raises_missing_pin() -> None:
    for pins in ({}, {('provider', 'gemini'): 'x'}):
        with pytest.raises(MissingPinError) as caught:
            _committed([_ws(1)], pins)
        assert str(caught.value) == 'missing_pin'


def test_committed_pin_to_invalidated_revision_raises() -> None:
    with pytest.raises(PinnedRevisionInvalidatedError) as caught:
        _committed([_ws(1, INVALIDATED), _ws(2)], {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)})
    assert str(caught.value) == 'pinned_revision_invalidated'


def test_committed_pin_to_superseded_revision_is_used() -> None:
    bundle = _committed([_ws(1, SUPERSEDED), _ws(2)], {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)})
    assert bundle.revision_refs == (_rid('workspace', 'default', 1),)


def test_committed_pin_to_draft_raises_missing_pin() -> None:
    with pytest.raises(MissingPinError) as caught:
        _committed([_ws(1, DRAFT)], {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)})
    assert str(caught.value) == 'pinned_revision_not_published'


def test_committed_pin_to_foreign_or_other_scope_revision_is_missing_pin() -> None:
    foreign, other_scope = _ws(1, workspace_id='ws-2'), _rev('provider', 'gemini', 1)
    for pin in (foreign.revision.config_revision_id, other_scope.revision.config_revision_id, 'unknown'):
        with pytest.raises(MissingPinError) as caught:
            _committed([foreign, other_scope, _ws(2)], {WORKSPACE_SCOPE: pin})
        assert str(caught.value) == 'missing_pin'
        assert 'ws-2' not in str(caught.value)


def test_committed_ignores_effective_at_of_pinned_revision() -> None:
    pinned = _ws(1, effective_at=T0 + timedelta(days=1))
    bundle = _committed([pinned], {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)})
    assert bundle.revision_refs == (_rid('workspace', 'default', 1),)


def test_merge_order_is_workspace_module_provider_preset_policy() -> None:
    layers = _layers()
    for count in range(1, 6):
        scopes = tuple(reversed(_all_scopes()[:count]))
        bundle = resolve_bundle(list(reversed(layers[:count])), _request(required_scopes=scopes))
        assert bundle.values['x'] == KINDS[count - 1]
        assert bundle.provenance['x'] == _rid(KINDS[count - 1], 'default', 1)
    full = resolve_bundle(layers, _request(required_scopes=_all_scopes()))
    assert full.values == {'x': 'policy', **{f'own_{kind}': 1 for kind in KINDS}}
    assert full.provenance['own_module'] == _rid('module', 'default', 1)


def test_deep_merge_overrides_leaf_and_keeps_siblings_with_provenance() -> None:
    base = _rev('workspace', 'default', 1, payload={'llm': {'model': 'a', 'limits': {'rpm': 1, 'tpm': 2}}, 'keep': 1})
    provider = _rev('provider', 'gemini', 1, payload={'llm': {'limits': {'rpm': 9}}})
    bundle = resolve_bundle([provider, base], _request(required_scopes=(WORKSPACE_SCOPE, ('provider', 'gemini'))))
    assert bundle.values == {'llm': {'model': 'a', 'limits': {'rpm': 9, 'tpm': 2}}, 'keep': 1}
    ws_id, provider_id = _rid('workspace', 'default', 1), _rid('provider', 'gemini', 1)
    assert bundle.provenance == {'llm.model': ws_id, 'llm.limits.rpm': provider_id, 'llm.limits.tpm': ws_id, 'keep': ws_id}


def test_type_change_replaces_value_and_provenance_prefix() -> None:
    policy_id = _rid('policy', 'default', 1)
    scopes = (WORKSPACE_SCOPE, ('policy', 'default'))

    def merged(base_payload: dict, policy_payload: dict) -> ConfigBundle:
        return resolve_bundle([_ws(1, payload=base_payload), _rev('policy', 'default', 1, payload=policy_payload)], _request(required_scopes=scopes))

    down = merged({'a': {'b': 1}}, {'a': 5})
    assert (down.values, down.provenance) == ({'a': 5}, {'a': policy_id})
    up = merged({'a': 5}, {'a': {'b': 1}})
    assert (up.values, up.provenance) == ({'a': {'b': 1}}, {'a.b': policy_id})
    lists = merged({'l': [1, 2]}, {'l': [3]})
    assert (lists.values, lists.provenance) == ({'l': [3]}, {'l': policy_id})


def test_same_kind_scopes_merge_in_scope_key_order_regardless_of_input_order() -> None:
    first = _rev('provider', 'a', 1, payload={'x': 'a'})
    second = _rev('provider', 'b', 1, payload={'x': 'b'})
    scopes = (('provider', 'a'), ('provider', 'b'))
    for revisions, required in (([first, second], scopes), ([second, first], scopes[::-1])):
        assert resolve_bundle(revisions, _request(required_scopes=required)).values == {'x': 'b'}


def test_prompt_scope_is_only_in_revision_refs() -> None:
    prompt = _rev('prompt', 'script', 1, payload={'template': 'hello', 'x': 'prompt'})
    bundle = resolve_bundle([_ws(1, payload={'x': 'ws'}), prompt], _request(required_scopes=(('prompt', 'script'), WORKSPACE_SCOPE)))
    assert bundle.values == {'x': 'ws'}
    assert bundle.revision_refs == tuple(sorted((_rid('prompt', 'script', 1), _rid('workspace', 'default', 1))))
    assert bundle.provenance == {'x': _rid('workspace', 'default', 1)}


SECRET_PAYLOADS = [
    {'password': 'canary-value'},
    {'apiKey': 'canary-value'},
    {'a': {'client_secret': 'canary-value'}},
    {'items': [{'token': 'canary-value'}]},
]


@pytest.mark.parametrize('payload', SECRET_PAYLOADS)
@pytest.mark.parametrize('kind,key', [('workspace', 'default'), ('prompt', 'script')])
def test_sensitive_key_in_selected_revision_raises_without_leaking(payload: dict, kind: str, key: str) -> None:
    with pytest.raises(BundleSecretError) as caught:
        resolve_bundle([_rev(kind, key, 1, payload=payload)], _request(required_scopes=((kind, key),)))
    assert str(caught.value) == 'secret_in_bundle'
    assert 'canary-value' not in str(caught.value)


def test_sensitive_key_in_pinned_revision_raises() -> None:
    with pytest.raises(BundleSecretError):
        _committed([_ws(1, payload={'token': 'canary-value'})], {WORKSPACE_SCOPE: _rid('workspace', 'default', 1)})


def test_non_sensitive_keys_and_unselected_revisions_do_not_raise() -> None:
    clean = {'max_tokens': 10, 'secret_handle_ref': 'handle-1'}
    bundle = resolve_bundle([_ws(1, SUPERSEDED, payload={'password': 'canary-value'}), _ws(2, payload=clean)], _request())
    assert bundle.values == clean


def _expected_fingerprint(refs: tuple, values: dict) -> str:
    canonical = json.dumps({'revision_refs': sorted(refs), 'values': values}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def test_fingerprint_is_sha256_of_canonical_refs_and_values() -> None:
    scopes = _all_scopes() + (('prompt', 'script'),)
    bundle = resolve_bundle(_layers() + [_rev('prompt', 'script', 1)], _request(required_scopes=scopes))
    assert bundle.bundle_fingerprint == _expected_fingerprint(bundle.revision_refs, bundle.values)
    assert len(bundle.bundle_fingerprint) == 64
    assert len(bundle.revision_refs) == 6
    assert bundle.revision_refs == tuple(sorted(bundle.revision_refs))


def test_result_is_independent_of_input_order_and_repeatable() -> None:
    layers, scopes = _layers(), _all_scopes()
    first = resolve_bundle(layers, _request(required_scopes=scopes))
    assert resolve_bundle(layers, _request(required_scopes=scopes)) == first
    assert resolve_bundle(layers[::-1], _request(required_scopes=scopes[::-1])) == first


def test_fingerprint_changes_with_values_or_selected_revision() -> None:
    base = resolve_bundle([_ws(1, payload={'a': 1})], _request())
    changed = resolve_bundle([_ws(1, payload={'a': 2})], _request())
    renumbered = resolve_bundle([_ws(1, payload={'a': 1}), _ws(2, payload={'a': 1})], _request())
    assert len({base.bundle_fingerprint, changed.bundle_fingerprint, renumbered.bundle_fingerprint}) == 3


def test_fingerprint_ignores_key_order_of_payload() -> None:
    one = resolve_bundle([_ws(1, payload={'a': 1, 'b': 2})], _request())
    two = resolve_bundle([_ws(1, payload={'b': 2, 'a': 1})], _request())
    assert one.bundle_fingerprint == two.bundle_fingerprint


def test_inputs_are_not_mutated_and_result_does_not_alias_payloads() -> None:
    revisions = [_ws(1, payload={'a': {'b': [1, 2]}}), _rev('policy', 'default', 1, payload={'c': {'d': 1}})]
    request = _request(required_scopes=(WORKSPACE_SCOPE, ('policy', 'default')))
    revisions_before, request_before = copy.deepcopy(revisions), copy.deepcopy(request)
    bundle = resolve_bundle(revisions, request)
    assert revisions == revisions_before
    assert request == request_before
    bundle.values['a']['b'].append(99)
    bundle.values['c']['d'] = 2
    assert revisions == revisions_before


def test_contract_types_are_frozen_with_contract_fields() -> None:
    assert [f.name for f in dataclasses.fields(BundleRequest)] == [
        'workspace_id', 'job_ref', 'stage_ref', 'evaluation_time', 'required_scopes', 'snapshot_state', 'pinned_revision_ids',
    ]
    assert [f.name for f in dataclasses.fields(ConfigBundle)] == ['revision_refs', 'values', 'provenance', 'bundle_fingerprint', 'warnings']
    assert BundleRequest.__dataclass_params__.frozen and ConfigBundle.__dataclass_params__.frozen
    first, second = _request(), _request()
    assert first.pinned_revision_ids == {}
    assert first.pinned_revision_ids is not second.pinned_revision_ids
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(first, 'job_ref', 'x')
    bundle = resolve_bundle([_ws(1)], _request())
    assert type(bundle.revision_refs) is tuple
    assert type(bundle.warnings) is tuple and bundle.warnings == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(bundle, 'values', {})


def test_business_errors_are_plain_exceptions_not_value_errors() -> None:
    for cls in (MissingPinError, PinnedRevisionInvalidatedError, MissingScopeError, BundleSecretError):
        assert issubclass(cls, Exception) and not issubclass(cls, ValueError)


def test_module_is_pure_and_imports_only_allowed_modules() -> None:
    allowed = {
        '__future__', 'collections.abc', 'copy', 'dataclasses', 'datetime', 'hashlib', 'json', 'typing',
        'controlplane.application.config_security.publish_plan', 'controlplane.domain.config_security',
    }
    imported, clock_calls = set(), set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
        elif isinstance(node, ast.Attribute) and node.attr in {'now', 'utcnow', 'today'}:
            clock_calls.add(node.attr)
    assert imported <= allowed
    assert not clock_calls


def test_module_docstring_declares_covered_ids() -> None:
    assert 'coveredIds: CT-CFG-002, TST-INT-INV-004, TST-SEC-INV-020' in (__doc__ or '')
