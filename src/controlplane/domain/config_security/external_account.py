"""J-06: aggregate ExternalAccount và ExternalAccountView (CT-ACC-001, QR-SEC-009, CT-STATE-013).

Pure domain: no I/O, no clock, no mutation; every function returns a new ExternalAccount and the caller passes `now_iso`.
The account holds credential metadata only (version, timestamps), never a secret value or handle.
REVOKED -> ENABLED is not an ACCOUNT_EDGES edge (J-04, D8-J-09); it exists only in reactivate_with_new_credential.
DEGRADED/INVALID -> ENABLED (PUC-J-03) is an ACCOUNT_EDGES edge used only by recover_after_passing_test.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from controlplane.domain.config_security.status_graph import ExternalAccountStatus, account_status_view, require_account_transition


@dataclass(frozen=True)
class ExternalAccount:
    external_account_id: str
    workspace_id: str
    provider: str
    account_label: str
    status: ExternalAccountStatus
    project_ref: str | None
    capabilities: frozenset[str]
    credential_version: int
    credential_updated_at: str | None
    credential_expires_at: str | None
    quota_observation_ref: str | None
    health: str | None
    revision: int


def _require_newer_version(current: int, new_version: int) -> None:
    if isinstance(new_version, bool) or not isinstance(new_version, int):
        raise ValueError('new_version must be an int')
    if new_version <= current:
        raise ValueError('new_version must be greater than the current credential_version')


def _require_timestamp(now_iso: str) -> None:
    if not isinstance(now_iso, str) or not now_iso:
        raise ValueError('now_iso must be a non-empty string')


def to_view(account: ExternalAccount) -> dict:
    """Return the CT-ACC-001 view: 9 keys, lowercase status, sorted capabilities, credential metadata only."""
    return {
        'external_account_id': account.external_account_id,
        'provider': account.provider,
        'account_label': account.account_label,
        'status': account_status_view(account.status),
        'project_ref': account.project_ref,
        'capabilities': sorted(account.capabilities),
        'quota_observation_ref': account.quota_observation_ref,
        'credential_metadata': {
            'present': account.credential_version > 0,
            'updated_at': account.credential_updated_at,
            'expires_at': account.credential_expires_at,
        },
        'health': account.health,
    }


def account_allows_role(account: ExternalAccount, workspace_id: str, ai_role: str) -> bool:
    """True only for an ENABLED account of the same workspace with ai_role exactly in capabilities (QR-SEC-009, no wildcard)."""
    return (
        account.status is ExternalAccountStatus.ENABLED
        and account.workspace_id == workspace_id
        and isinstance(ai_role, str)
        and ai_role in account.capabilities
    )


def rotate_credential(account: ExternalAccount, new_version: int, now_iso: str) -> ExternalAccount:
    """New account with a greater credential_version, credential_updated_at=now_iso, revision+1; status is kept."""
    _require_newer_version(account.credential_version, new_version)
    _require_timestamp(now_iso)
    return replace(account, credential_version=new_version, credential_updated_at=now_iso, revision=account.revision + 1)


def reactivate_with_new_credential(account: ExternalAccount, new_version: int, now_iso: str) -> ExternalAccount:
    """New ENABLED account from a REVOKED one with a greater credential_version; any other status raises ValueError."""
    if account.status is not ExternalAccountStatus.REVOKED:
        raise ValueError('only a REVOKED account can be reactivated with a new credential')
    _require_newer_version(account.credential_version, new_version)
    _require_timestamp(now_iso)
    return replace(
        account, status=ExternalAccountStatus.ENABLED, credential_version=new_version, credential_updated_at=now_iso,
        revision=account.revision + 1,
    )


_RECOVERABLE = frozenset({ExternalAccountStatus.DEGRADED, ExternalAccountStatus.INVALID})


def recover_after_passing_test(account: ExternalAccount) -> ExternalAccount:
    """New ENABLED account from a DEGRADED or INVALID one, revision+1 (PUC-J-03); any other status raises ValueError.

    The caller proves the passing CT-ACC-002 test of this same account; this pure function never probes or reads a secret.
    """
    if account.status not in _RECOVERABLE:
        raise ValueError('only a DEGRADED or INVALID account can recover after a passing test')
    require_account_transition(account.status, ExternalAccountStatus.ENABLED, account.revision)
    return replace(account, status=ExternalAccountStatus.ENABLED, revision=account.revision + 1)
