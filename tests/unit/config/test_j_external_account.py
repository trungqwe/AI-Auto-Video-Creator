"""J-06: aggregate ExternalAccount và ExternalAccountView (CT-ACC-001, QR-SEC-009, CT-STATE-013).

coveredIds: CT-ACC-001, QR-SEC-009, CT-STATE-013
"""
import dataclasses

import pytest

from controlplane.domain.config_security import external_account
from controlplane.domain.config_security.external_account import (
    ExternalAccount, account_allows_role, reactivate_with_new_credential, rotate_credential, to_view,
)
from controlplane.domain.config_security.status_graph import ExternalAccountStatus, can_transition_account

A = ExternalAccountStatus
NOW = '2026-10-20T08:00:00+00:00'
EXPECTED_FIELDS = [
    'external_account_id', 'workspace_id', 'provider', 'account_label', 'status', 'project_ref', 'capabilities', 'credential_version',
    'credential_updated_at', 'credential_expires_at', 'quota_observation_ref', 'health', 'revision',
]
EXPECTED_VIEW_KEYS = {
    'external_account_id', 'provider', 'account_label', 'status', 'project_ref', 'capabilities', 'quota_observation_ref',
    'credential_metadata', 'health',
}
FORBIDDEN_KEY_PARTS = ('secret', 'handle', 'token', 'api_key', 'password', 'private_key')


def _account(**overrides) -> ExternalAccount:
    values = {
        'external_account_id': 'acc-1', 'workspace_id': 'ws-1', 'provider': 'prov-a', 'account_label': 'primary', 'status': A.ENABLED,
        'project_ref': 'proj-1', 'capabilities': frozenset({'script_writer', 'planner'}), 'credential_version': 3,
        'credential_updated_at': '2026-10-01T00:00:00+00:00', 'credential_expires_at': '2027-10-01T00:00:00+00:00',
        'quota_observation_ref': 'quota-1', 'health': 'ok', 'revision': 5,
    }
    values.update(overrides)
    return ExternalAccount(**values)


def _all_keys(value) -> list:
    keys = []
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(key)
            keys.extend(_all_keys(item))
    return keys


def test_external_account_is_frozen_dataclass_with_declared_fields():
    assert dataclasses.is_dataclass(ExternalAccount)
    assert [f.name for f in dataclasses.fields(ExternalAccount)] == EXPECTED_FIELDS
    assert external_account.ExternalAccountStatus is A
    account = _account()
    assert isinstance(account.capabilities, frozenset)
    with pytest.raises(dataclasses.FrozenInstanceError):
        account.revision = 99


def test_to_view_returns_exactly_the_nine_ct_acc_001_keys():
    view = to_view(_account())
    assert type(view) is dict
    assert set(view) == EXPECTED_VIEW_KEYS and len(view) == 9
    assert view == {
        'external_account_id': 'acc-1', 'provider': 'prov-a', 'account_label': 'primary', 'status': 'enabled', 'project_ref': 'proj-1',
        'capabilities': ['planner', 'script_writer'], 'quota_observation_ref': 'quota-1', 'health': 'ok',
        'credential_metadata': {'present': True, 'updated_at': '2026-10-01T00:00:00+00:00', 'expires_at': '2027-10-01T00:00:00+00:00'},
    }


@pytest.mark.parametrize('status', list(A), ids=lambda status: status.name)
def test_to_view_status_is_lowercase(status):
    view = to_view(_account(status=status))
    assert view['status'] == status.value.lower()
    assert view['status'] == view['status'].lower()


def test_to_view_capabilities_is_sorted_list():
    view = to_view(_account(capabilities=frozenset({'zeta', 'alpha', 'mid'})))
    assert type(view['capabilities']) is list
    assert view['capabilities'] == ['alpha', 'mid', 'zeta']


def test_to_view_credential_metadata_has_only_present_updated_at_expires_at():
    meta = to_view(_account())['credential_metadata']
    assert set(meta) == {'present', 'updated_at', 'expires_at'}
    assert meta['present'] is True
    empty = to_view(_account(credential_version=0, credential_updated_at=None, credential_expires_at=None))['credential_metadata']
    assert empty == {'present': False, 'updated_at': None, 'expires_at': None}


def test_to_view_keeps_optional_keys_when_values_are_none():
    view = to_view(_account(project_ref=None, quota_observation_ref=None, health=None))
    assert set(view) == EXPECTED_VIEW_KEYS
    assert view['project_ref'] is None and view['quota_observation_ref'] is None and view['health'] is None


def test_to_view_and_account_leak_no_secret_or_handle():
    keys = _all_keys(to_view(_account()))
    assert keys
    assert not [key for key in keys if any(part in key for part in FORBIDDEN_KEY_PARTS)]
    field_names = [f.name for f in dataclasses.fields(ExternalAccount)]
    assert not [name for name in field_names if any(part in name for part in FORBIDDEN_KEY_PARTS)]


def test_allows_role_true_for_enabled_matching_workspace_and_granted_role():
    account = _account()
    assert account_allows_role(account, 'ws-1', 'script_writer') is True
    assert account_allows_role(account, 'ws-1', 'planner') is True


@pytest.mark.parametrize('status', [A.DISABLED, A.DEGRADED, A.INVALID, A.REVOKED], ids=lambda status: status.name)
def test_allows_role_false_unless_status_is_enabled(status):
    assert account_allows_role(_account(status=status), 'ws-1', 'script_writer') is False


def test_allows_role_false_for_ungranted_role():
    account = _account()
    assert account_allows_role(account, 'ws-1', 'voice_director') is False
    assert account_allows_role(account, 'ws-1', '') is False
    assert account_allows_role(account, 'ws-1', None) is False
    assert account_allows_role(_account(capabilities=frozenset()), 'ws-1', 'script_writer') is False


def test_allows_role_false_for_other_workspace():
    assert account_allows_role(_account(), 'ws-2', 'script_writer') is False


def test_allows_role_matches_exactly_without_wildcard():
    account = _account()
    for role in ('*', 'script_*', 'script', 'SCRIPT_WRITER', ' script_writer'):
        assert account_allows_role(account, 'ws-1', role) is False
    wildcard_account = _account(capabilities=frozenset({'*', 'script_*'}))
    for role in ('script_writer', 'planner', 'script_other'):
        assert account_allows_role(wildcard_account, 'ws-1', role) is False


def test_rotate_credential_returns_new_account_with_higher_version():
    account = _account()
    rotated = rotate_credential(account, 4, NOW)
    assert rotated is not account
    assert (rotated.credential_version, rotated.credential_updated_at, rotated.revision) == (4, NOW, 6)
    assert rotated == dataclasses.replace(account, credential_version=4, credential_updated_at=NOW, revision=6)
    assert account == _account()


@pytest.mark.parametrize('status', list(A), ids=lambda status: status.name)
def test_rotate_credential_keeps_status_and_never_reactivates(status):
    assert rotate_credential(_account(status=status), 4, NOW).status is status


@pytest.mark.parametrize('bad_version', [3, 2, 0, -1])
def test_rotate_credential_rejects_equal_or_lower_version(bad_version):
    account = _account()
    with pytest.raises(ValueError):
        rotate_credential(account, bad_version, NOW)
    assert account == _account()


def test_rotate_and_reactivate_reject_non_int_version():
    for bad_version in (True, 1.5, '1', None):
        with pytest.raises(ValueError):
            rotate_credential(_account(credential_version=0), bad_version, NOW)
        with pytest.raises(ValueError):
            reactivate_with_new_credential(_account(status=A.REVOKED, credential_version=0), bad_version, NOW)


def test_rotate_and_reactivate_reject_blank_timestamp():
    for bad_now in ('', None, 5):
        with pytest.raises(ValueError):
            rotate_credential(_account(), 4, bad_now)
        with pytest.raises(ValueError):
            reactivate_with_new_credential(_account(status=A.REVOKED), 4, bad_now)


def test_reactivate_from_revoked_with_newer_version_returns_new_enabled_account():
    revoked = _account(status=A.REVOKED)
    reactivated = reactivate_with_new_credential(revoked, 4, NOW)
    assert reactivated is not revoked
    assert reactivated.status is A.ENABLED
    assert (reactivated.credential_version, reactivated.credential_updated_at, reactivated.revision) == (4, NOW, 6)
    assert reactivated == dataclasses.replace(revoked, status=A.ENABLED, credential_version=4, credential_updated_at=NOW, revision=6)
    assert revoked == _account(status=A.REVOKED)
    assert revoked.status is A.REVOKED


@pytest.mark.parametrize('old_version', [3, 2, 0])
def test_reactivate_rejects_equal_or_older_credential_version(old_version):
    revoked = _account(status=A.REVOKED)
    with pytest.raises(ValueError):
        reactivate_with_new_credential(revoked, old_version, NOW)
    assert revoked == _account(status=A.REVOKED)


@pytest.mark.parametrize('status', [A.ENABLED, A.DISABLED, A.DEGRADED, A.INVALID], ids=lambda status: status.name)
def test_reactivate_rejects_non_revoked_account(status):
    account = _account(status=status)
    with pytest.raises(ValueError):
        reactivate_with_new_credential(account, 4, NOW)
    assert account == _account(status=status)


def test_reactivation_is_not_a_status_graph_edge_and_restores_routing():
    assert not can_transition_account(A.REVOKED, A.ENABLED)
    revoked = _account(status=A.REVOKED)
    assert account_allows_role(revoked, 'ws-1', 'script_writer') is False
    reactivated = reactivate_with_new_credential(revoked, 4, NOW)
    assert account_allows_role(reactivated, 'ws-1', 'script_writer') is True
    with pytest.raises(ValueError):
        reactivate_with_new_credential(reactivated, 5, NOW)
