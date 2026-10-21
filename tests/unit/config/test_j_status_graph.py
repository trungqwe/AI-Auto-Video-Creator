"""J-04: đồ thị trạng thái ConfigRevision và ExternalAccount (CT-STATE-013, CT-ACC-001).

coveredIds: CT-STATE-013, CT-ACC-001
"""
import itertools

import pytest

from controlplane.application.config_security import _allowed_transition
from controlplane.application.projections.config_account_views import ACCOUNT_STATUSES
from controlplane.domain.config_security import ConfigRevisionStatus, status_graph
from controlplane.domain.config_security.status_graph import (
    ACCOUNT_EDGES, CONFIG_REVISION_EDGES, ExternalAccountStatus, account_status_view, can_transition_account,
    can_transition_config, require_account_transition, require_config_transition,
)
from dataclasses import replace

from controlplane.application.config_security.account_recovery import AccountRecoveryService
from controlplane.application.config_security.account_test import AccountTestReceipt
from controlplane.application.storage_meta import ArtifactLocationStore
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security.external_account import ExternalAccount, recover_after_passing_test
from controlplane.domain.statemachine import ArtifactLocationState, ForbiddenTransitionError
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion, CleanupAuthorization

C = ConfigRevisionStatus
A = ExternalAccountStatus

DECLARED_CONFIG = {'DRAFT', 'PUBLISHED', 'SUPERSEDED', 'INVALIDATED'}
DECLARED_ACCOUNT = {'ENABLED', 'DISABLED', 'DEGRADED', 'INVALID', 'REVOKED'}
EXPECTED_CONFIG_EDGES = frozenset({
    (C.DRAFT, C.PUBLISHED), (C.PUBLISHED, C.SUPERSEDED), (C.DRAFT, C.INVALIDATED),
    (C.PUBLISHED, C.INVALIDATED), (C.SUPERSEDED, C.INVALIDATED),
})
EXPECTED_ACCOUNT_EDGES = frozenset({
    (A.DISABLED, A.ENABLED), (A.ENABLED, A.DISABLED), (A.ENABLED, A.DEGRADED), (A.ENABLED, A.INVALID), (A.ENABLED, A.REVOKED),
    (A.DEGRADED, A.ENABLED), (A.INVALID, A.ENABLED),
})
EXPECTED_VIEW = {'ENABLED': 'enabled', 'DISABLED': 'disabled', 'DEGRADED': 'degraded', 'REVOKED': 'revoked', 'INVALID': 'invalid'}
CONFIG_PAIRS = list(itertools.product(C, C))
ACCOUNT_PAIRS = list(itertools.product(A, A))


def _pair_id(pair) -> str:
    return f'{pair[0].name}-{pair[1].name}'


def test_every_enum_member_is_declared():
    assert {m.name for m in C} == DECLARED_CONFIG
    assert {m.name for m in A} == DECLARED_ACCOUNT
    assert all(m.value == m.name for m in A)
    assert set(EXPECTED_VIEW) == DECLARED_ACCOUNT
    assert status_graph.ConfigRevisionStatus is C


def test_edge_sets_are_exact_frozensets():
    assert isinstance(CONFIG_REVISION_EDGES, frozenset) and len(CONFIG_REVISION_EDGES) == 5
    assert CONFIG_REVISION_EDGES == EXPECTED_CONFIG_EDGES
    assert isinstance(ACCOUNT_EDGES, frozenset) and len(ACCOUNT_EDGES) == 7
    assert ACCOUNT_EDGES == EXPECTED_ACCOUNT_EDGES


@pytest.mark.parametrize('pair', CONFIG_PAIRS, ids=_pair_id)
def test_config_pair_is_allowed_only_on_declared_edges(pair):
    current, requested = pair
    allowed = pair in EXPECTED_CONFIG_EDGES
    assert can_transition_config(current, requested) is allowed
    if allowed:
        assert require_config_transition(current, requested, 7) is None
        return
    with pytest.raises(ForbiddenTransitionError) as info:
        require_config_transition(current, requested, 7)
    error = info.value
    assert (error.aggregate_type, error.current_state, error.requested_next_state, error.current_revision) == ('config_revision', current, requested, 7)


@pytest.mark.parametrize('pair', ACCOUNT_PAIRS, ids=_pair_id)
def test_account_pair_is_allowed_only_on_declared_edges(pair):
    current, requested = pair
    allowed = pair in EXPECTED_ACCOUNT_EDGES
    assert can_transition_account(current, requested) is allowed
    if allowed:
        assert require_account_transition(current, requested, 3) is None
        return
    with pytest.raises(ForbiddenTransitionError) as info:
        require_account_transition(current, requested, 3)
    error = info.value
    assert (error.aggregate_type, error.current_state, error.requested_next_state, error.current_revision) == ('external_account', current, requested, 3)


@pytest.mark.parametrize('pair', CONFIG_PAIRS, ids=_pair_id)
def test_config_graph_matches_application_allowed_transition(pair):
    assert can_transition_config(*pair) is _allowed_transition(*pair)


def test_config_counterexamples_are_rejected():
    assert not can_transition_config(C.DRAFT, C.SUPERSEDED)
    assert not can_transition_config(C.SUPERSEDED, C.PUBLISHED)
    assert not any(can_transition_config(C.INVALIDATED, status) for status in C)
    assert not any(can_transition_config(status, status) for status in C)


def test_account_counterexamples_are_rejected():
    assert not can_transition_account(A.REVOKED, A.ENABLED)
    assert not can_transition_account(A.DISABLED, A.REVOKED)
    assert not any(can_transition_account(A.REVOKED, status) for status in A)
    for recoverable in (A.DEGRADED, A.INVALID):
        assert {status for status in A if can_transition_account(recoverable, status)} == {A.ENABLED}
    assert not can_transition_account(A.DISABLED, A.DEGRADED)
    assert not any(can_transition_account(status, status) for status in A)


@pytest.mark.parametrize('status', list(A), ids=lambda status: status.name)
def test_account_status_view_is_lowercase_value(status):
    view = account_status_view(status)
    assert type(view) is str
    assert view == EXPECTED_VIEW[status.name]


def test_account_status_view_matches_projection_statuses():
    assert {account_status_view(status) for status in A} == set(ACCOUNT_STATUSES)


def test_account_status_view_rejects_unknown_status():
    with pytest.raises(ValueError):
        account_status_view('UNKNOWN')

def _account(status, revision=5):
    return ExternalAccount(
        external_account_id='acc-1',
        workspace_id='ws-1',
        provider='prov-a',
        account_label='primary',
        status=status,
        project_ref='proj-1',
        capabilities=frozenset({'planner'}),
        credential_version=3,
        credential_updated_at='2026-10-01T00:00:00+00:00',
        credential_expires_at=None,
        quota_observation_ref=None,
        health='ok',
        revision=revision,
    )


def _receipt(ok=True, external_account_id='acc-1'):
    return AccountTestReceipt(
        receipt_id='r-1',
        operation_key='op-1',
        external_account_id=external_account_id,
        ok=ok,
        latency_ms=5,
        error_class=None,
        redacted_detail=None,
        tested_at='2026-10-20T08:00:00+00:00',
    )


@pytest.mark.parametrize('status', [A.DEGRADED, A.INVALID], ids=lambda s: s.name)
def test_recover_after_passing_test_restores_degraded_and_invalid(status):
    old = _account(status, revision=5)
    result = recover_after_passing_test(old)
    assert result.status is A.ENABLED
    assert result.revision == 6
    assert replace(result, status=old.status, revision=old.revision) == old
    assert old.status is status and old.revision == 5


@pytest.mark.parametrize('status', [A.ENABLED, A.DISABLED, A.REVOKED], ids=lambda s: s.name)
def test_recover_after_passing_test_rejects_other_statuses(status):
    with pytest.raises(ValueError):
        recover_after_passing_test(_account(status))


@pytest.mark.parametrize('status', [A.DEGRADED, A.INVALID], ids=lambda s: s.name)
def test_service_recovers_degraded_and_invalid_with_passing_receipt(status):
    acc = _account(status, revision=5)
    result = AccountRecoveryService().recover(acc, _receipt(), 5)
    assert result.status is A.ENABLED
    assert result.revision == 6


@pytest.mark.parametrize('status,receipt', [
    (A.DEGRADED, _receipt(ok=False)),
    (A.INVALID, _receipt(ok=False)),
    (A.DEGRADED, _receipt(ok=1)),
    (A.DEGRADED, _receipt(external_account_id='acc-2')),
    (A.REVOKED, _receipt(ok=True)),
    (A.DISABLED, _receipt(ok=True)),
    (A.ENABLED, _receipt(ok=True)),
], ids=[
    'degraded-failed-receipt',
    'invalid-failed-receipt',
    'degraded-truthy-int-ok',
    'degraded-mismatched-account-id',
    'revoked-passing-receipt',
    'disabled-passing-receipt',
    'enabled-passing-receipt',
])
def test_service_returns_same_account_without_recovery(status, receipt):
    account = _account(status)
    result = AccountRecoveryService().recover(account, receipt, account.revision)
    assert result is account


@pytest.mark.parametrize('expected_revision', [4, 6])
def test_service_rejects_stale_expected_revision(expected_revision):
    acc = _account(A.DEGRADED, revision=5)
    with pytest.raises(RevisionConflictError) as info:
        AccountRecoveryService().recover(acc, _receipt(), expected_revision)
    assert info.value.current_revision == 5


def test_service_takes_no_ports():
    service = AccountRecoveryService()
    assert service is not None


HASH = 'a' * 64


def _location(state=ArtifactLocationState.CLEANUP_AUTHORIZED, revision=4):
    return ArtifactLocation(
        workspace_id='ws-1',
        location_id='loc-1',
        artifact_version_id='ver-1',
        backend_ref='backend-1',
        provider_namespace_ref='ns-1',
        provider_object_ref='obj-1',
        logical_locator='loc/1',
        observed_hash=HASH,
        observed_size_bytes=10,
        provider_metadata_revision=None,
        verification_evidence_ref='verif-1',
        state=state,
        revision=revision,
        created_at='2026-10-20T00:00:00+00:00',
        updated_at='2026-10-20T00:00:00+00:00',
    )


def _version(**overrides):
    base = {
        'workspace_id': 'ws-1',
        'artifact_id': 'art-1',
        'artifact_version_id': 'ver-1',
        'sha256_hash': HASH,
        'size_bytes': 10,
        'mime_type': 'video/mp4',
        'artifact_kind': 'render',
        'owner_ref': 'owner-1',
        'lineage_ref': None,
        'retention_ref': 'ret-1',
        'sensitivity_ref': 'sens-1',
        'created_at': '2026-10-20T00:00:00+00:00',
    }
    base.update(overrides)
    return ArtifactVersion(**base)


def _authorization(**overrides):
    base = {
        'workspace_id': 'ws-1',
        'cleanup_authorization_id': 'auth-1',
        'location_id': 'loc-1',
        'artifact_version_id': 'ver-1',
        'artifact_hash': HASH,
        'reason': 'retention',
        'policy_revision': 'p-1',
        'completion_evidence_ref': 'comp-1',
        'verification_evidence_ref': 'verif-1',
        'issued_at': '2026-10-20T00:00:00+00:00',
        'expires_at': '2026-10-21T00:00:00+00:00',
        'recovery_epoch': 1,
        'authorizing_owner_ref': 'owner-1',
        'actor_ref': 'actor-1',
        'audit_ref': 'audit-1',
        'correlation_ref': 'corr-1',
    }
    base.update(overrides)
    return CleanupAuthorization(**base)


class _FakeRepository:
    def __init__(self, location: ArtifactLocation | None, version: ArtifactVersion | None):
        self._location = location
        self._version = version
        self.updates: list[tuple[int, ArtifactLocationState, str | None]] = []

    def get_location(self, workspace_id: str, location_id: str) -> ArtifactLocation | None:
        if self._location and self._location.workspace_id == workspace_id and self._location.location_id == location_id:
            return self._location
        return None

    def get_version(self, workspace_id: str, artifact_version_id: str) -> ArtifactVersion | None:
        if self._version and self._version.workspace_id == workspace_id and self._version.artifact_version_id == artifact_version_id:
            return self._version
        return None

    def update_location(self, location: ArtifactLocation, expected_revision: int, requested_state: ArtifactLocationState, evidence: str | None) -> ArtifactLocation | None:
        self.updates.append((expected_revision, requested_state, evidence))
        self._location = replace(location, state=requested_state, revision=location.revision + 1)
        return self._location


def _call(repo, **overrides):
    params = {
        'connection': object(),
        'workspace_id': 'ws-1',
        'location_id': 'loc-1',
        'expected_revision': 4,
        'authorization': _authorization(),
        'artifact_version_id': 'ver-1',
        'artifact_hash': HASH,
        'cleanup_deleted': True,
        'cleanup_receipt_ref': 'cleanup-receipt-1',
    }
    params.update(overrides)
    return ArtifactLocationStore(lambda connection: repo).record_cleanup_deleted(**params)


def test_record_cleanup_deleted_happy_path():
    repo = _FakeRepository(_location(), _version())
    result = _call(repo)
    assert result.state is ArtifactLocationState.DELETED
    assert result.revision == 5
    assert repo.updates == [(4, ArtifactLocationState.DELETED, None)]
    assert result.verification_evidence_ref == 'verif-1'


@pytest.mark.parametrize('bad_flag', [False, None, 1, 'true'])
def test_record_cleanup_deleted_rejects_invalid_flag(bad_flag):
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, cleanup_deleted=bad_flag)
    assert repo.updates == []


@pytest.mark.parametrize('bad_ref', ['', '   ', None, '/etc/x', 'C:\\x', '../x', 'token=abc'])
def test_record_cleanup_deleted_rejects_unsafe_or_empty_receipt_ref(bad_ref):
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, cleanup_receipt_ref=bad_ref)
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_mismatched_authorization_hash():
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, authorization=_authorization(artifact_hash='b' * 64))
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_mismatched_kwarg_hash():
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, artifact_hash='b' * 64)
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_mismatched_version_hash():
    repo = _FakeRepository(_location(), _version(sha256_hash='b' * 64))
    with pytest.raises(ValueError):
        _call(repo)
    assert repo.updates == []


@pytest.mark.parametrize('auth_override', [
    {'location_id': 'loc-2'},
    {'artifact_version_id': 'ver-2'},
    {'workspace_id': 'ws-2'},
])
def test_record_cleanup_deleted_rejects_mismatched_authorization(auth_override):
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, authorization=_authorization(**auth_override))
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_none_authorization():
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(ValueError):
        _call(repo, authorization=None)
    assert repo.updates == []


@pytest.mark.parametrize('state', [s for s in ArtifactLocationState if s is not ArtifactLocationState.CLEANUP_AUTHORIZED], ids=lambda s: s.name)
def test_record_cleanup_deleted_rejects_non_cleanup_authorized_state(state):
    repo = _FakeRepository(_location(state=state), _version())
    with pytest.raises(ValueError):
        _call(repo)
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_stale_expected_revision():
    repo = _FakeRepository(_location(revision=4), _version())
    with pytest.raises(RevisionConflictError) as info:
        _call(repo, expected_revision=3)
    assert info.value.current_revision == 4
    assert repo.updates == []


def test_record_cleanup_deleted_rejects_missing_location():
    repo = _FakeRepository(_location(), _version())
    with pytest.raises(PermissionError):
        _call(repo, location_id='loc-x')
    assert repo.updates == []


def test_transition_and_validate_transition_reject_deleted():
    repo = _FakeRepository(_location(), _version())
    store = ArtifactLocationStore(lambda connection: repo)
    with pytest.raises(ForbiddenTransitionError):
        store.transition(connection=object(), workspace_id='ws-1', location_id='loc-1', expected_revision=4, requested_state=ArtifactLocationState.DELETED)
    assert repo.updates == []
    with pytest.raises(ForbiddenTransitionError):
        store.validate_transition(current_state=ArtifactLocationState.CLEANUP_AUTHORIZED, current_revision=4, expected_revision=4, requested_state=ArtifactLocationState.DELETED)
    assert repo.updates == []


def test_artifact_location_store_has_no_delete_method():
    assert not hasattr(ArtifactLocationStore, 'delete')
