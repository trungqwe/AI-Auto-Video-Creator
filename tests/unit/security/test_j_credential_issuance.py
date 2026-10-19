"""J-11: credential ngắn hạn và revocation (CT-SEC-002, CT-SEC-003 điều 7, INV-012, QR-SEC-009).

coveredIds: CT-SEC-002, CT-SEC-003, TST-SEC-INV-012, QR-SEC-009
"""
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.application.config_security.credential_issuance import (
    CredentialGrant, CredentialIssuer, GrantBindingError, GrantExpiredError, GrantRevokedError, GrantValidationError,
    IssuanceDeniedError, IssuedCredential, RefreshTokenNotAllowedError, validate_grant,
)
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import SecretValue, find_canaries

CANARY = 'CANARY-J11-TOKEN-4e8a1c'
NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
MAX_TTL = 600
ACCOUNT_REF = 'acc-1'
GRANT_FIELDS = (
    'grant_id', 'audience', 'capability', 'workspace_id', 'account_ref', 'issued_at', 'expires_at', 'operation_ref', 'job_ref',
    'credential_version', 'revocation_version', 'permissions',
)


class FakeMinter:
    def __init__(self):
        self.grants = []

    def mint(self, grant):
        self.grants.append(grant)
        return SecretValue(CANARY)


class FakeRevocations:
    def __init__(self, versions=None):
        self.versions = dict(versions or {})
        self.calls = []

    def revocation_version(self, account_ref):
        self.calls.append(account_ref)
        return self.versions.get(account_ref, 0)

    def revoke(self, account_ref):
        self.versions[account_ref] = self.versions.get(account_ref, 0) + 1


def make_account(**overrides):
    values = dict(
        external_account_id=ACCOUNT_REF, workspace_id='ws-1', provider='google-drive', account_label='Drive chính',
        status=ExternalAccountStatus.ENABLED, project_ref='proj-1', capabilities=frozenset({'drive.upload', 'drive.read'}),
        credential_version=3, credential_updated_at=None, credential_expires_at=None, quota_observation_ref=None,
        health=None, revision=1,
    )
    values.update(overrides)
    return ExternalAccount(**values)


def make_issuer(minter=None, revocations=None, max_ttl=MAX_TTL):
    return CredentialIssuer(minter or FakeMinter(), revocations or FakeRevocations(), max_ttl)


def issue(issuer=None, **overrides):
    params = dict(
        account=make_account(), audience='worker', capability='drive.upload', permissions=frozenset({'drive.upload'}),
        ttl_seconds=300, now=NOW,
    )
    params.update(overrides)
    return (issuer or make_issuer()).issue(**params)


def test_grant_has_exactly_the_contract_fields_and_no_token_or_secret():
    names = tuple(field.name for field in dataclasses.fields(CredentialGrant))
    assert names == GRANT_FIELDS
    assert not [name for name in names if 'token' in name or 'secret' in name]
    assert CredentialGrant.__dataclass_params__.frozen


def test_grant_is_frozen():
    grant = issue().grant
    with pytest.raises(dataclasses.FrozenInstanceError):
        grant.audience = 'desktop'


def test_issued_credential_has_grant_and_token_only():
    assert tuple(field.name for field in dataclasses.fields(IssuedCredential)) == ('grant', 'token')
    assert IssuedCredential.__dataclass_params__.frozen


def test_canary_token_is_absent_from_every_rendering():
    issued = issue()
    assert issued.token.reveal() == CANARY
    assert find_canaries([CANARY], issued, issued.grant, issued.token) == []
    assert CANARY not in repr(issued) and CANARY not in str(issued) and CANARY not in repr(issued.grant)


def test_issue_sets_expiry_and_bindings():
    minter, revocations = FakeMinter(), FakeRevocations({ACCOUNT_REF: 2})
    grant = issue(make_issuer(minter, revocations), operation_ref='op-1', job_ref='job-1').grant
    assert grant.issued_at == NOW
    assert grant.expires_at == NOW + timedelta(seconds=300)
    assert (grant.audience, grant.capability, grant.workspace_id, grant.account_ref) == ('worker', 'drive.upload', 'ws-1', ACCOUNT_REF)
    assert (grant.operation_ref, grant.job_ref) == ('op-1', 'job-1')
    assert (grant.credential_version, grant.revocation_version) == (3, 2)
    assert grant.permissions == frozenset({'drive.upload'})
    assert grant.grant_id
    assert minter.grants == [grant]


def test_issue_without_bindings_leaves_refs_none():
    grant = issue().grant
    assert grant.operation_ref is None and grant.job_ref is None


def test_grant_ids_are_unique():
    issuer = make_issuer()
    assert issue(issuer).grant.grant_id != issue(issuer).grant.grant_id


def test_ttl_at_ceiling_is_allowed():
    assert issue(ttl_seconds=MAX_TTL).grant.expires_at == NOW + timedelta(seconds=MAX_TTL)


@pytest.mark.parametrize('ttl', [0, -1, MAX_TTL + 1, 10**9, True, 1.5, '60', None])
def test_ttl_outside_ceiling_is_denied_without_minting(ttl):
    minter = FakeMinter()
    with pytest.raises(IssuanceDeniedError):
        issue(make_issuer(minter), ttl_seconds=ttl)
    assert minter.grants == []


@pytest.mark.parametrize('now', [datetime(2026, 10, 20, 12, 0, 0), '2026-10-20T12:00:00Z', None])
def test_now_without_timezone_is_denied(now):
    minter = FakeMinter()
    with pytest.raises(IssuanceDeniedError):
        issue(make_issuer(minter), now=now)
    assert minter.grants == []


def test_desktop_with_oauth_refresh_is_denied():
    minter = FakeMinter()
    with pytest.raises(RefreshTokenNotAllowedError) as caught:
        issue(make_issuer(minter), audience='desktop', permissions=frozenset({'drive.upload', 'oauth.refresh'}))
    assert isinstance(caught.value, IssuanceDeniedError)
    assert minter.grants == []


def test_desktop_without_refresh_is_issued():
    assert issue(audience='desktop').grant.audience == 'desktop'


def test_permissions_given_as_plain_string_are_denied():
    with pytest.raises(IssuanceDeniedError):
        issue(permissions='oauth.refresh')


@pytest.mark.parametrize('status', [status for status in ExternalAccountStatus if status is not ExternalAccountStatus.ENABLED])
def test_account_not_enabled_is_denied(status):
    minter = FakeMinter()
    with pytest.raises(IssuanceDeniedError):
        issue(make_issuer(minter), account=make_account(status=status))
    assert minter.grants == []


def test_account_of_another_workspace_is_denied():
    with pytest.raises(IssuanceDeniedError):
        issue(workspace_id='ws-other')
    assert issue(workspace_id='ws-1').grant.workspace_id == 'ws-1'


@pytest.mark.parametrize('capability', ['ai.generate', '*', 'drive', ''])
def test_capability_outside_account_is_denied(capability):
    with pytest.raises(IssuanceDeniedError):
        issue(capability=capability)


def test_minter_must_return_secret_value():
    class RawMinter:
        def mint(self, grant):
            return CANARY

    with pytest.raises(IssuanceDeniedError) as caught:
        issue(make_issuer(RawMinter()))
    assert find_canaries([CANARY], str(caught.value), repr(caught.value)) == []


@pytest.mark.parametrize('max_ttl', [0, -5, True, 1.5, None])
def test_issuer_requires_positive_int_ceiling(max_ttl):
    with pytest.raises(ValueError):
        CredentialIssuer(FakeMinter(), FakeRevocations(), max_ttl)


def test_valid_grant_passes_and_reads_live_revocation():
    revocations = FakeRevocations({ACCOUNT_REF: 1})
    grant = issue(make_issuer(revocations=revocations)).grant
    assert validate_grant(grant, make_account(), NOW + timedelta(seconds=299), revocations) is None
    assert revocations.calls[-1] == ACCOUNT_REF


@pytest.mark.parametrize('offset', [300, 301, 86400])
def test_expired_grant_raises(offset):
    grant = issue().grant
    with pytest.raises(GrantExpiredError):
        validate_grant(grant, make_account(), NOW + timedelta(seconds=offset), FakeRevocations())


def test_revoke_after_issue_wins_over_stale_snapshot_before_expiry():
    revocations, account = FakeRevocations(), make_account()
    grant = issue(make_issuer(revocations=revocations), account=account).grant
    later = NOW + timedelta(seconds=1)
    assert later < grant.expires_at
    assert validate_grant(grant, account, later, revocations) is None
    revocations.revoke(ACCOUNT_REF)
    with pytest.raises(GrantRevokedError):
        validate_grant(grant, account, later, revocations)


@pytest.mark.parametrize('status', [ExternalAccountStatus.REVOKED, ExternalAccountStatus.INVALID, ExternalAccountStatus.DISABLED])
def test_account_in_dead_status_raises_revoked(status):
    grant = issue().grant
    with pytest.raises(GrantRevokedError):
        validate_grant(grant, make_account(status=status), NOW, FakeRevocations())


def test_degraded_account_still_validates():
    grant = issue().grant
    assert validate_grant(grant, make_account(status=ExternalAccountStatus.DEGRADED), NOW, FakeRevocations()) is None


def test_operation_mismatch_raises_binding_error():
    grant = issue(operation_ref='op-1').grant
    assert validate_grant(grant, make_account(), NOW, FakeRevocations(), operation_ref='op-1') is None
    with pytest.raises(GrantBindingError):
        validate_grant(grant, make_account(), NOW, FakeRevocations(), operation_ref='op-2')
    with pytest.raises(GrantBindingError):
        validate_grant(grant, make_account(), NOW, FakeRevocations())


def test_unbound_grant_accepts_any_operation():
    grant = issue().grant
    assert validate_grant(grant, make_account(), NOW, FakeRevocations(), operation_ref='op-9') is None


def test_grant_for_other_account_or_workspace_raises_binding_error():
    grant = issue().grant
    with pytest.raises(GrantBindingError):
        validate_grant(grant, make_account(external_account_id='acc-2'), NOW, FakeRevocations())
    with pytest.raises(GrantBindingError):
        validate_grant(grant, make_account(workspace_id='ws-2'), NOW, FakeRevocations())


def test_naive_now_in_validate_raises_validation_error():
    grant = issue().grant
    with pytest.raises(GrantValidationError):
        validate_grant(grant, make_account(), datetime(2026, 10, 20, 12, 0, 0), FakeRevocations())


def test_errors_carry_no_credential_material():
    revocations = FakeRevocations()
    grant = issue(make_issuer(revocations=revocations), operation_ref='op-1').grant
    errors = []
    for call in (
        lambda: issue(audience='desktop', permissions=frozenset({'oauth.refresh'})),
        lambda: validate_grant(grant, make_account(), NOW + timedelta(seconds=999), revocations, operation_ref='op-1'),
        lambda: validate_grant(grant, make_account(), NOW, revocations, operation_ref='op-2'),
        lambda: validate_grant(grant, make_account(status=ExternalAccountStatus.REVOKED), NOW, revocations, operation_ref='op-1'),
    ):
        with pytest.raises(Exception) as caught:
            call()
        errors.append(caught.value)
    assert len(errors) == 4
    assert find_canaries([CANARY], *[str(error) for error in errors], *[repr(error) for error in errors]) == []
