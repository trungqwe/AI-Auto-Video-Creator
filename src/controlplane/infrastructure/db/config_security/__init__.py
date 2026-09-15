"""PostgreSQL adapters for P5A configuration and secret metadata ports."""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus, SecretHandle
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository


_REVISION_COLUMNS = "config_revision_id::text, workspace_id::text, scope_kind, scope_key, config_revision_number, revision, content_hash, payload, status"


def _revision(row: tuple[Any, ...] | None) -> ConfigRevision | None:
    if row is None: return None
    return ConfigRevision(str(row[0]), str(row[1]), str(row[2]), str(row[3]), int(row[4]), int(row[5]), str(row[6]), dict(row[7]), ConfigRevisionStatus(str(row[8])))


class PostgresConfigSecurityRepository:
    """P5A persistence adapter bound to the caller-owned UoW connection."""
    def __init__(self, connection: Any) -> None: self._connection = connection

    def create_revision(self, **kwargs: Any) -> ConfigRevision:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_config_revisions (config_revision_id, workspace_id, scope_kind, scope_key, config_revision_number, revision, content_hash, payload, status, effective_at, actor_ref, change_reason, audit_ref) VALUES (%s, %s, %s, %s, %s, 1, %s, %s, 'DRAFT', %s, %s, %s, %s) " + f"RETURNING {_REVISION_COLUMNS}",
            (kwargs["config_revision_id"], kwargs["workspace_id"], kwargs["scope_kind"], kwargs["scope_key"], kwargs["config_revision_number"], kwargs["content_hash"], Jsonb(kwargs["payload"]), kwargs.get("effective_at"), kwargs["actor_ref"], kwargs["change_reason"], kwargs.get("audit_ref", "p5a")),
        ).fetchone()
        result = _revision(row)
        if result is None: raise RuntimeError("configuration revision insert returned no row")
        return result

    def get_scoped(self, **kwargs: Any) -> ConfigRevision | None:
        return _revision(self._connection.execute(f"SELECT {_REVISION_COLUMNS} FROM controlplane.cp_config_revisions WHERE workspace_id=%s AND config_revision_id=%s", (kwargs["workspace_id"], kwargs["config_revision_id"])).fetchone())

    def get_by_id(self, **kwargs: Any) -> ConfigRevision | None:
        return _revision(self._connection.execute(f"SELECT {_REVISION_COLUMNS} FROM controlplane.cp_config_revisions WHERE config_revision_id=%s", (kwargs["config_revision_id"],)).fetchone())

    def transition(self, **kwargs: Any) -> ConfigRevision | None:
        return _revision(self._connection.execute(
            "UPDATE controlplane.cp_config_revisions SET status=%s, revision=revision+1, actor_ref=%s, change_reason=%s, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND config_revision_id=%s AND revision=%s AND status=%s " + f"RETURNING {_REVISION_COLUMNS}",
            (kwargs["requested_status"].value, kwargs["actor_ref"], kwargs["change_reason"], kwargs["workspace_id"], kwargs["config_revision_id"], kwargs["expected_revision"], kwargs["current_status"].value),
        ).fetchone())

    def register_secret_handle(self, **kwargs: Any) -> SecretHandle:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_secret_handles (secret_handle_id, workspace_id, provider_ref, account_ref, alias_ref, redacted_fingerprint_or_version, validation_status, revoked_at, expires_at, audit_ref) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING secret_handle_id::text, workspace_id::text, provider_ref, account_ref, alias_ref, redacted_fingerprint_or_version, validation_status, revoked_at, expires_at, audit_ref",
            (kwargs["secret_handle_id"], kwargs["workspace_id"], kwargs["provider_ref"], kwargs["account_ref"], kwargs["alias_ref"], kwargs["redacted_fingerprint_or_version"], kwargs["validation_status"], kwargs.get("revoked_at"), kwargs.get("expires_at"), kwargs["audit_ref"]),
        ).fetchone()
        if row is None: raise RuntimeError("secret handle insert returned no row")
        return SecretHandle(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), row[7].isoformat() if hasattr(row[7], "isoformat") else row[7], row[8].isoformat() if hasattr(row[8], "isoformat") else row[8], str(row[9]))


class PostgresConfigEventSink:
    """P5A event sink delegated to the existing P3 PostgreSQL outbox adapter."""
    def __init__(self, connection: Any) -> None: self._outbox = PostgresOutboxRepository(connection)
    def enqueue(self, event: Any) -> str: return self._outbox.enqueue(event)


__all__ = ["PostgresConfigEventSink", "PostgresConfigSecurityRepository"]
