"""ADAPT-J: short-lived Drive access token for the broker credential_method; the refresh token never leaves the broker (CT-SEC-001, INV-012)."""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.application.config_security.secret_update import SecretStorePort
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_google_loopback import (
    ACCOUNT_REF,
    SCOPE,
    SECRET_REF,
    load_client_config,
    quiet_oauth_loggers,
)
from controlplane.infrastructure.security.secret_redaction import SecretValue
from controlplane.security.dpapi import dpapi_decrypt


class DriveTokenError(Exception):
    pass


class DriveTokenDeniedError(DriveTokenError):
    pass


class DriveTokenRefreshError(DriveTokenError):
    pass


class AccountStatusPort(Protocol):
    def account_status(self, account_ref: str) -> ExternalAccountStatus:
        ...


class RefreshTokenReaderPort(Protocol):
    def read(self, secret_ref: str) -> SecretValue:
        ...


class DpapiRefreshTokenReader:
    def __init__(self, store: DpapiSecretStore, entropy: bytes | None = None) -> None:
        if entropy is not None and not isinstance(entropy, (bytes, bytearray)):
            raise TypeError('entropy must be bytes or None')
        self._store = store
        self._entropy = bytes(entropy) if entropy is not None else None

    def read(self, secret_ref: str) -> SecretValue:
        vault = self._store.export_vault([secret_ref])
        cipher = vault.get(secret_ref)
        if cipher is None:
            raise DriveTokenDeniedError('secret handle is revoked or missing')
        try:
            decrypted = dpapi_decrypt(cipher, self._entropy).decode('utf-8')
            return SecretValue(decrypted)
        except Exception:
            raise DriveTokenError('refresh token could not be decrypted') from None


class DriveAccessTokenBroker:
    def __init__(
        self,
        client_secrets_path: Path,
        max_ttl_seconds: int,
        store: SecretStorePort,
        reader: RefreshTokenReaderPort,
        statuses: AccountStatusPort,
        clock: Callable[[], datetime],
    ) -> None:
        if isinstance(max_ttl_seconds, bool) or not isinstance(max_ttl_seconds, int) or max_ttl_seconds <= 0:
            raise ValueError('max_ttl_seconds must be a positive int')
        self._client_secrets_path = client_secrets_path
        self._max_ttl_seconds = max_ttl_seconds
        self._store = store
        self._reader = reader
        self._statuses = statuses
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: tuple[str, datetime, int] | None = None

    @contextmanager
    def acquire(self, credential_method: str, account_ref: str) -> Iterator[str]:
        yield self._token(credential_method, account_ref)

    def _token(self, credential_method: str, account_ref: str) -> str:
        if credential_method != CREDENTIAL_METHOD:
            raise ValueError('unsupported credential_method')
        if account_ref != ACCOUNT_REF:
            raise ValueError('unsupported account_ref')

        status = self._statuses.account_status(account_ref)
        if status in {
            ExternalAccountStatus.REVOKED,
            ExternalAccountStatus.INVALID,
            ExternalAccountStatus.DISABLED,
        }:
            self._cached = None
            raise DriveTokenDeniedError('account is not usable: ' + status.value)

        version = self._store.current_version(SECRET_REF)
        if version is None:
            self._cached = None
            raise DriveTokenDeniedError('secret handle is revoked or missing')

        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError('clock must return a timezone-aware datetime')

        with self._lock:
            if self._cached is not None and self._cached[2] == version and now < self._cached[1]:
                return self._cached[0]
            return self._refresh(now, version)

    def _refresh(self, now: datetime, version: int) -> str:
        cfg = load_client_config(self._client_secrets_path)['installed']
        raw = self._reader.read(SECRET_REF).reveal()
        creds = Credentials(
            token=None,
            refresh_token=raw,
            token_uri=cfg['token_uri'],
            client_id=cfg['client_id'],
            client_secret=cfg['client_secret'],
            scopes=[SCOPE],
        )

        with quiet_oauth_loggers():
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise DriveTokenRefreshError('access token refresh failed: ' + type(exc).__name__) from None

        if not creds.token:
            raise DriveTokenRefreshError('access token refresh returned empty token')

        expires_at = now + timedelta(seconds=self._max_ttl_seconds)
        if creds.expiry:
            expiry_utc = (
                creds.expiry.replace(tzinfo=timezone.utc)
                if creds.expiry.tzinfo is None
                else creds.expiry
            )
            expires_at = min(expires_at, expiry_utc)

        self._cached = (creds.token, expires_at, version)
        return creds.token


__all__ = [
    'AccountStatusPort',
    'DpapiRefreshTokenReader',
    'DriveAccessTokenBroker',
    'DriveTokenDeniedError',
    'DriveTokenError',
    'DriveTokenRefreshError',
    'RefreshTokenReaderPort',
]
