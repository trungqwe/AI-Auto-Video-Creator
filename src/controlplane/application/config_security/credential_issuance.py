"""J-11: credential ngắn hạn và revocation (CT-SEC-002, CT-SEC-003 điều 7, QR-SEC-009, INV-012).

Application use case: không I/O, không đọc đồng hồ (caller truyền `now` có múi giờ), không lưu token.
CredentialGrant chỉ là metadata; token chỉ nằm trong IssuedCredential dưới dạng SecretValue.
Trần TTL là bắt buộc (D8-J-08); revoke thắng snapshot cũ vì RevocationPort được đọc trực tiếp khi validate.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
import uuid

from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import SecretValue

DESKTOP_AUDIENCE = 'desktop'
REFRESH_PERMISSION = 'oauth.refresh'
_DEAD_STATUSES = frozenset({ExternalAccountStatus.REVOKED, ExternalAccountStatus.INVALID, ExternalAccountStatus.DISABLED})


class CredentialError(Exception):
    """Gốc của mọi từ chối J-11; thông điệp không bao giờ chứa credential."""


class IssuanceDeniedError(CredentialError):
    pass


class RefreshTokenNotAllowedError(IssuanceDeniedError):
    pass


class GrantValidationError(CredentialError):
    pass


class GrantExpiredError(GrantValidationError):
    pass


class GrantRevokedError(GrantValidationError):
    pass


class GrantBindingError(GrantValidationError):
    pass


@dataclass(frozen=True)
class CredentialGrant:
    grant_id: str
    audience: str
    capability: str
    workspace_id: str
    account_ref: str
    issued_at: datetime
    expires_at: datetime
    operation_ref: str | None
    job_ref: str | None
    credential_version: int
    revocation_version: int
    permissions: frozenset[str]


@dataclass(frozen=True)
class IssuedCredential:
    grant: CredentialGrant
    token: SecretValue = field(repr=False)


class TokenMinterPort(Protocol):
    def mint(self, grant: CredentialGrant) -> SecretValue: ...


class RevocationPort(Protocol):
    def revocation_version(self, account_ref: str) -> int: ...


def _require_aware(now: datetime, error: type[CredentialError]) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise error('now must be a timezone-aware datetime')


def _require_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IssuanceDeniedError('revocation version must be a non-negative int')
    return value


class CredentialIssuer:
    """Cấp grant ngắn hạn; trần TTL bắt buộc (D8-J-08), desktop không bao giờ nhận quyền refresh."""

    def __init__(self, minter: TokenMinterPort, revocations: RevocationPort, max_ttl_seconds: int) -> None:
        if isinstance(max_ttl_seconds, bool) or not isinstance(max_ttl_seconds, int) or max_ttl_seconds <= 0:
            raise ValueError('max_ttl_seconds must be a positive int')
        self._minter, self._revocations, self._max_ttl_seconds = minter, revocations, max_ttl_seconds

    def issue(
        self, account: ExternalAccount, audience: str, capability: str, permissions: Iterable[str], ttl_seconds: int,
        now: datetime, operation_ref: str | None = None, job_ref: str | None = None, *, workspace_id: str | None = None,
    ) -> IssuedCredential:
        _require_aware(now, IssuanceDeniedError)
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0 or ttl_seconds > self._max_ttl_seconds:
            raise IssuanceDeniedError('ttl_seconds must be a positive int not above max_ttl_seconds')
        if not isinstance(audience, str) or not audience or not isinstance(capability, str) or not capability:
            raise IssuanceDeniedError('audience and capability must be non-empty strings')
        if isinstance(permissions, (str, bytes)):
            raise IssuanceDeniedError('permissions must be a collection of permission names')
        granted = frozenset(permissions)
        if not all(isinstance(name, str) and name for name in granted):
            raise IssuanceDeniedError('permission names must be non-empty strings')
        if account.status is not ExternalAccountStatus.ENABLED:
            raise IssuanceDeniedError('account is not ENABLED')
        if workspace_id is not None and workspace_id != account.workspace_id:
            raise IssuanceDeniedError('account belongs to another workspace')
        if capability not in account.capabilities:
            raise IssuanceDeniedError('capability is not granted to the account')
        if audience == DESKTOP_AUDIENCE and REFRESH_PERMISSION in granted:
            raise RefreshTokenNotAllowedError('desktop must not receive a refresh token')
        grant = CredentialGrant(
            grant_id=str(uuid.uuid4()), audience=audience, capability=capability, workspace_id=account.workspace_id,
            account_ref=account.external_account_id, issued_at=now, expires_at=now + timedelta(seconds=ttl_seconds),
            operation_ref=operation_ref, job_ref=job_ref, credential_version=account.credential_version,
            revocation_version=_require_version(self._revocations.revocation_version(account.external_account_id)),
            permissions=granted,
        )
        token = self._minter.mint(grant)
        if not isinstance(token, SecretValue):
            raise IssuanceDeniedError('minter must return a SecretValue')
        return IssuedCredential(grant=grant, token=token)


def validate_grant(
    grant: CredentialGrant, account: ExternalAccount, now: datetime, revocations: RevocationPort, operation_ref: str | None = None,
) -> None:
    """Fail-closed: trạng thái account và RevocationPort đọc trực tiếp thắng mọi snapshot cũ của grant (CT-SEC-003 điều 7).

    Grant có operation_ref thì operation_ref của caller phải bằng đúng; grant không ràng buộc operation thì chấp nhận mọi operation.
    """
    _require_aware(now, GrantValidationError)
    if grant.account_ref != account.external_account_id or grant.workspace_id != account.workspace_id:
        raise GrantBindingError('grant is not bound to this account or workspace')
    if account.status in _DEAD_STATUSES:
        raise GrantRevokedError('account is not usable: ' + account.status.value)
    if revocations.revocation_version(grant.account_ref) > grant.revocation_version:
        raise GrantRevokedError('grant was revoked after it was issued')
    if now >= grant.expires_at:
        raise GrantExpiredError('grant has expired')
    if grant.operation_ref is not None and grant.operation_ref != operation_ref:
        raise GrantBindingError('grant is bound to another operation')


__all__ = [
    'CredentialError', 'CredentialGrant', 'CredentialIssuer', 'GrantBindingError', 'GrantExpiredError', 'GrantRevokedError',
    'GrantValidationError', 'IssuanceDeniedError', 'IssuedCredential', 'RefreshTokenNotAllowedError', 'RevocationPort',
    'TokenMinterPort', 'validate_grant',
]
