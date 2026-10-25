"""PP-2: provider_credentials for 9Router, a CredentialSourcePort over the DPAPI vault (CT-SEC-001, INV-012).

The key is read only from the vault alias given by the caller (ports.json router.secret_ref) and is yielded to the caller of acquire; it is never cached, logged or put into an exception message.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import (
    DpapiRefreshTokenReader,
    DriveTokenDeniedError,
    DriveTokenError,
)
from controlplane.infrastructure.security.secret_redaction import REDACTED


class ProviderCredentialError(Exception):
    pass


def _require_ref(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


class RouterKeyCredentials:
    def __init__(self, store: DpapiSecretStore, router_account_ref: str, router_secret_ref: str) -> None:
        self._router_account_ref = _require_ref(router_account_ref, 'router_account_ref')
        self._router_secret_ref = _require_ref(router_secret_ref, 'router_secret_ref')
        self._reader = DpapiRefreshTokenReader(store)

    @contextmanager
    def acquire(self, credential_method: str, account_ref: str) -> Iterator[str]:
        if credential_method != CREDENTIAL_METHOD:
            raise ValueError('unsupported credential_method')
        if account_ref != self._router_account_ref:
            raise ValueError('unsupported account_ref')
        try:
            secret = self._reader.read(self._router_secret_ref)
        except DriveTokenDeniedError:
            raise ProviderCredentialError('router key is revoked or missing') from None
        except DriveTokenError:
            raise ProviderCredentialError('router key could not be decrypted') from None
        key = secret.reveal()
        if not isinstance(key, str) or not key:
            raise ProviderCredentialError('router key is empty')
        yield key

    def __repr__(self) -> str:
        return f'RouterKeyCredentials(account_ref={self._router_account_ref!r}, secret_ref={self._router_secret_ref!r}, key={REDACTED})'


__all__ = ['ProviderCredentialError', 'RouterKeyCredentials']
