from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ J (config & security).
Đấu nối DpapiSecretStore, DriveAccessTokenBroker, DriveOAuthConfig,
PooledReservationStore, PooledCostLedger và PostgresAccountStatusPort.
Không mở Credentials/, không đọc hay in bí mật, không chạy OAuth lúc dựng."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from controlplane.api.wiring._shared import (
    PooledCostLedger,
    PooledReservationStore,
)
from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from controlplane.application.config_security.capacity_reservation import (
    InMemoryReservationStore,
)
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.dpapi_secret_store import (
    DpapiSecretStore,
)
from controlplane.infrastructure.security.oauth_drive_token import (
    DpapiRefreshTokenReader,
    DriveAccessTokenBroker,
)
from controlplane.infrastructure.security.oauth_google_loopback import (
    DriveOAuthConfig,
)


class InMemorySecretStore:
    def __init__(self) -> None:
        self._versions: dict[str, int] = {}
        self._revoked: set[tuple[str, int]] = set()

    def put(self, secret_ref: str, value: Any) -> int:
        cur = self._versions.get(secret_ref, 0) + 1
        self._versions[secret_ref] = cur
        return cur

    def revoke(self, secret_ref: str, version: int) -> None:
        self._revoked.add((secret_ref, version))

    def current_version(self, secret_ref: str) -> int | None:
        cur = self._versions.get(secret_ref)
        if cur is None or (secret_ref, cur) in self._revoked:
            return None
        return cur


class InMemoryCostLedger:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], Any] = {}

    def records(
        self,
        workspace_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[Any, ...]:
        matched = []
        for (w_id, _), rec in self._records.items():
            if w_id == workspace_id:
                occ = datetime.fromisoformat(rec.occurred_at)
                if window_start <= occ < window_end:
                    matched.append(rec)
        return tuple(matched)

    def append(self, workspace_id: str, record: Any) -> None:
        key = (workspace_id, record.record_id)
        if key not in self._records:
            self._records[key] = record


class PostgresAccountStatusPort:
    def __init__(self, manager: Any, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = workspace_id

    def account_status(self, account_ref: str) -> ExternalAccountStatus:
        with self._manager.borrow_connection() as connection:
            row = connection.execute(
                'SELECT status FROM controlplane.cp_external_accounts WHERE workspace_id=%s AND external_account_id=%s',
                (self._workspace_id, account_ref),
            ).fetchone()
            if not row:
                return ExternalAccountStatus.REVOKED
            return ExternalAccountStatus(str(row[0]))


@dataclass(frozen=True)
class ConfigSecurityServices:
    mode: str
    secret_store: Any
    token_broker: Any
    oauth_config: Any
    reservation_store: Any
    cost_ledger: Any
    account_status: Any


def build_config_security_services(manager: Any, config: WiringConfig) -> ConfigSecurityServices:
    if config.mode != PROFILE_PRODUCTION:
        return ConfigSecurityServices(
            config.mode,
            InMemorySecretStore(),
            None,
            None,
            InMemoryReservationStore(),
            InMemoryCostLedger(),
            None,
        )

    profile, runtime = config.production_parts()
    store = DpapiSecretStore(runtime.secret_store_root)
    reader = DpapiRefreshTokenReader(store)
    statuses = PostgresAccountStatusPort(manager, config.workspace_id)
    broker = DriveAccessTokenBroker(
        runtime.oauth_client_secrets_path,
        profile.credential_max_ttl_seconds,
        store,
        reader,
        statuses,
        lambda: datetime.now(timezone.utc),
    )
    oauth = DriveOAuthConfig(
        runtime.oauth_client_secrets_path,
        runtime.oauth_consent_timeout_seconds,
    )
    return ConfigSecurityServices(
        'production',
        store,
        broker,
        oauth,
        PooledReservationStore(manager, config.workspace_id),
        PooledCostLedger(manager),
        statuses,
    )


__all__ = [
    'ConfigSecurityServices',
    'InMemoryCostLedger',
    'InMemorySecretStore',
    'PostgresAccountStatusPort',
    'build_config_security_services',
]
