"""PP-3: drive_token_broker over the DPAPI vault (CT-SEC-001, INV-012).

The existing DriveAccessTokenBroker does the token exchange; this module only wires it to the vault. No token is written to disk, logged or put into an error message.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from controlplane.application.config_security.secret_update import SecretStorePort
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import DpapiRefreshTokenReader, DriveAccessTokenBroker
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF, SECRET_REF


class VaultAccountStatusPort:
    def __init__(self, store: SecretStorePort) -> None:
        self._store = store

    def account_status(self, account_ref: str) -> ExternalAccountStatus:
        if account_ref == ACCOUNT_REF and self._store.current_version(SECRET_REF) is not None:
            return ExternalAccountStatus.ENABLED
        return ExternalAccountStatus.REVOKED


def build_drive_token_broker(
    client_secrets_path: Path,
    max_ttl_seconds: int,
    store: DpapiSecretStore,
    clock: Callable[[], datetime],
) -> DriveAccessTokenBroker:
    return DriveAccessTokenBroker(
        client_secrets_path,
        max_ttl_seconds,
        store,
        DpapiRefreshTokenReader(store),
        VaultAccountStatusPort(store),
        clock,
    )


__all__ = ['VaultAccountStatusPort', 'build_drive_token_broker']
