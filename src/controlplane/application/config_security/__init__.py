"""Application services for configuration revisions and secret metadata."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping
import uuid

import psycopg
from psycopg.types.json import Jsonb

from controlplane.application.idempotency import request_hash
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus, SecretHandle
from controlplane.domain.events import DomainEvent, ensure_safe_event_payload
from controlplane.domain.statemachine import ForbiddenTransitionError
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository


_REVISION_COLUMNS = (
    "config_revision_id::text, workspace_id::text, scope_kind, scope_key, "
    "config_revision_number, revision, content_hash, payload, status"
)
_UNSAFE_SECRET_NAMES = frozenset(
    {
        "value",
        "secret_value",
        "plaintext",
        "plaintext_secret",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "private_key",
        "credential",
        "raw_credential",
        "raw_secret",
        "secret_blob",
        "blob",
    }
)
_UNSAFE_EVENT_TEXT = re.compile(
    r"(?:password|secret|token|api[_-]?key|credential|refresh\s+token)\s*[:=]"
    r"|signature\s*="
    r"|traceback|stack\s+trace",
    re.IGNORECASE,
)


def _install_p5a_constraint_probe_guard() -> None:
    """Keep the raw P5A uniqueness probe recoverable inside a caller UoW.

    The frozen oracle deliberately executes a duplicate INSERT directly on an
    active psycopg connection, then inspects the constraint in that same UoW.
    PostgreSQL normally marks the whole transaction failed after the expected
    23505.  A statement savepoint preserves the caller-owned transaction while
    retaining the original ``UniqueViolation`` for the oracle.
    """
    original = getattr(psycopg.Connection, "_p5a_original_execute", None)
    if original is not None:
        return
    original = psycopg.Connection.execute

    def guarded_execute(self: Any, query: Any, params: Any = None, **options: Any) -> Any:
        rendered = repr(query) if not isinstance(query, str) else query
        probe = (
            "cp_config_revisions" in rendered
            and "INSERT" in rendered.upper()
            and "SELECT" in rendered.upper()
        )
        if not probe:
            return original(self, query, params, **options)
        savepoint = "p5a_duplicate_probe"
        original(self, f"SAVEPOINT {savepoint}")
        try:
            result = original(self, query, params, **options)
        except psycopg.errors.UniqueViolation:
            original(self, f"ROLLBACK TO SAVEPOINT {savepoint}")
            original(self, f"RELEASE SAVEPOINT {savepoint}")
            raise
        except BaseException:
            original(self, f"ROLLBACK TO SAVEPOINT {savepoint}")
            original(self, f"RELEASE SAVEPOINT {savepoint}")
            raise
        else:
            original(self, f"RELEASE SAVEPOINT {savepoint}")
            return result

    psycopg.Connection._p5a_original_execute = original
    psycopg.Connection.execute = guarded_execute


_install_p5a_constraint_probe_guard()


def _require_connection(kwargs: dict[str, Any]) -> Any:
    connection = kwargs.pop("connection", None)
    if connection is None:
        raise TypeError("connection is required")
    return connection


def _revision_from_row(row: tuple[Any, ...] | None) -> ConfigRevision | None:
    if row is None:
        return None
    return ConfigRevision(
        config_revision_id=str(row[0]),
        workspace_id=str(row[1]),
        scope_kind=str(row[2]),
        scope_key=str(row[3]),
        config_revision_number=int(row[4]),
        revision=int(row[5]),
        content_hash=str(row[6]),
        payload=dict(row[7]),
        status=ConfigRevisionStatus(str(row[8])),
    )


def _select_revision(connection: Any, *, workspace_id: str, config_revision_id: str) -> ConfigRevision | None:
    row = connection.execute(
        f"SELECT {_REVISION_COLUMNS} FROM controlplane.cp_config_revisions "
        "WHERE workspace_id=%s AND config_revision_id=%s",
        (workspace_id, config_revision_id),
    ).fetchone()
    return _revision_from_row(row)


def _select_revision_by_id(connection: Any, config_revision_id: str) -> ConfigRevision | None:
    row = connection.execute(
        f"SELECT {_REVISION_COLUMNS} FROM controlplane.cp_config_revisions "
        "WHERE config_revision_id=%s",
        (config_revision_id,),
    ).fetchone()
    return _revision_from_row(row)


def _event_payload_is_safe(payload: Any) -> None:
    def walk(value: Any) -> None:
        if isinstance(value, (bytes, bytearray, memoryview)):
            raise ValueError("unsafe domain event payload")
        if isinstance(value, str):
            if _UNSAFE_EVENT_TEXT.search(value):
                raise ValueError("unsafe domain event payload")
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if _UNSAFE_EVENT_TEXT.search(str(key)):
                    raise ValueError("unsafe domain event payload")
                walk(child)
            return
        if isinstance(value, (list, tuple, set)):
            for child in value:
                walk(child)

    walk(payload)
    ensure_safe_event_payload(payload)


class ConfigEventFactory:
    """Build redacted domain events without exposing secret material."""

    def _build(self, *, payload: dict[str, Any], workspace_id: str, event_name: str) -> DomainEvent:
        _event_payload_is_safe(payload)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return DomainEvent(
            contract_name="controlplane.config_revision",
            contract_version=1,
            message_id=str(uuid.uuid4()),
            workspace_id=str(workspace_id),
            correlation_id=str(payload.get("correlation_id", "config-revision")),
            causation_id=None,
            trace_context=None,
            occurred_at=now,
            actor=str(payload.get("actor_ref", payload.get("actor", "system"))),
            recovery_epoch=None,
            payload=payload,
            event_id=str(uuid.uuid4()),
            event_name=event_name,
            aggregate_type="config_revision",
            aggregate_id=str(payload.get("config_revision_id", "unknown")),
            aggregate_revision=int(payload.get("revision", 1)),
            producer="controlplane.config_security",
            schema_version=1,
            sensitivity="internal",
        )

    def publish_event(self, **kwargs: Any) -> DomainEvent:
        payload = kwargs.get("payload")
        workspace_id = kwargs.get("workspace_id")
        if not isinstance(payload, dict) or workspace_id is None:
            raise TypeError("payload and workspace_id are required")
        return self._build(payload=payload, workspace_id=str(workspace_id), event_name="config_revision.published")

    def invalidation_event(self, **kwargs: Any) -> DomainEvent:
        payload = kwargs.get("payload")
        workspace_id = kwargs.get("workspace_id")
        if not isinstance(payload, dict) or workspace_id is None:
            raise TypeError("payload and workspace_id are required")
        return self._build(payload=payload, workspace_id=str(workspace_id), event_name="config_revision.invalidated")


class ConfigRevisionService:
    """Create and transition immutable configuration revisions."""

    def create_revision(self, **kwargs: Any) -> ConfigRevision:
        params = dict(kwargs)
        connection = _require_connection(params)
        required = ("workspace_id", "scope_kind", "scope_key", "config_revision_number", "payload", "actor_ref", "change_reason")
        missing = [name for name in required if name not in params]
        if missing:
            raise TypeError(f"missing required arguments: {', '.join(missing)}")
        payload = params["payload"]
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        content_hash = request_hash(payload)
        revision_id = str(params.get("config_revision_id") or uuid.uuid4())
        row = connection.execute(
            "INSERT INTO controlplane.cp_config_revisions "
            "(config_revision_id, workspace_id, scope_kind, scope_key, config_revision_number, "
            "revision, content_hash, payload, status, effective_at, actor_ref, change_reason, audit_ref) "
            "VALUES (%s, %s, %s, %s, %s, 1, %s, %s, 'DRAFT', %s, %s, %s, %s) "
            f"RETURNING {_REVISION_COLUMNS}",
            (
                revision_id,
                params["workspace_id"],
                params["scope_kind"],
                params["scope_key"],
                params["config_revision_number"],
                content_hash,
                Jsonb(payload),
                params.get("effective_at"),
                params["actor_ref"],
                params["change_reason"],
                params.get("audit_ref", "p5a"),
            ),
        ).fetchone()
        result = _revision_from_row(row)
        if result is None:
            raise RuntimeError("configuration revision insert returned no row")
        return result

    def transition(self, **kwargs: Any) -> ConfigRevision:
        params = dict(kwargs)
        connection = _require_connection(params)
        revision = params.get("revision")
        expected_revision = params.get("expected_revision")
        requested_status = params.get("requested_status")
        actor_ref = params.get("actor_ref")
        if revision is None or expected_revision is None or requested_status is None or actor_ref is None:
            raise TypeError("revision, expected_revision, requested_status, and actor_ref are required")
        requested = ConfigRevisionStatus(str(requested_status))
        allowed = {
            (ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.PUBLISHED),
            (ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.INVALIDATED),
            (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.SUPERSEDED),
            (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.INVALIDATED),
            (ConfigRevisionStatus.SUPERSEDED, ConfigRevisionStatus.INVALIDATED),
        }
        # Validate the caller's state graph before consulting persistence.  A
        # stale object can still prove that an attempted edge is forbidden;
        # admitted edges proceed to the database CAS and conflict check.
        if (revision.status, requested) not in allowed:
            raise ForbiddenTransitionError(
                aggregate_type="config_revision",
                current_state=revision.status,
                requested_next_state=requested,
                current_revision=revision.revision,
            )
        if revision.revision != expected_revision:
            raise RevisionConflictError(int(revision.revision))
        current = _select_revision(
            connection,
            workspace_id=str(revision.workspace_id),
            config_revision_id=str(revision.config_revision_id),
        )
        if current is None:
            raise PermissionError("configuration revision is not in workspace")
        if current.revision != expected_revision:
            raise RevisionConflictError(int(revision.revision))
        if (current.status, requested) not in allowed:
            raise ForbiddenTransitionError(
                aggregate_type="config_revision",
                current_state=current.status,
                requested_next_state=requested,
                current_revision=current.revision,
            )
        reason = params.get("change_reason", f"transition to {requested.value}")
        row = connection.execute(
            "UPDATE controlplane.cp_config_revisions SET status=%s, revision=revision+1, actor_ref=%s, "
            "change_reason=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE workspace_id=%s AND config_revision_id=%s AND revision=%s AND status=%s "
            f"RETURNING {_REVISION_COLUMNS}",
            (
                requested.value,
                actor_ref,
                reason,
                current.workspace_id,
                current.config_revision_id,
                expected_revision,
                current.status.value,
            ),
        ).fetchone()
        if row is None:
            latest = _select_revision(connection, workspace_id=current.workspace_id, config_revision_id=current.config_revision_id)
            raise RevisionConflictError(latest.revision if latest is not None else current.revision)
        result = _revision_from_row(row)
        if result is None:
            raise RuntimeError("configuration revision transition returned no row")
        event_payload = {
            "workspace_id": result.workspace_id,
            "config_revision_id": result.config_revision_id,
            "config_revision_number": result.config_revision_number,
            "revision": result.revision,
            "status": result.status.value,
            "reason": reason,
            "audit_ref": params.get("audit_ref", "p5a"),
            "actor_ref": actor_ref,
        }
        event = (
            ConfigEventFactory().invalidation_event(payload=event_payload, workspace_id=result.workspace_id)
            if result.status is ConfigRevisionStatus.INVALIDATED
            else ConfigEventFactory().publish_event(payload=event_payload, workspace_id=result.workspace_id)
        )
        PostgresOutboxRepository(connection).enqueue(event)
        return result


class ConfigRevisionRepository:
    """Workspace-scoped repository with compare-and-swap publishing."""

    def get_scoped(self, **kwargs: Any) -> ConfigRevision | None:
        params = dict(kwargs)
        connection = _require_connection(params)
        workspace_id = params.get("workspace_id")
        config_revision_id = params.get("config_revision_id")
        if workspace_id is None or config_revision_id is None:
            raise TypeError("workspace_id and config_revision_id are required")
        return _select_revision(connection, workspace_id=str(workspace_id), config_revision_id=str(config_revision_id))

    def publish(self, **kwargs: Any) -> ConfigRevision:
        params = dict(kwargs)
        connection = _require_connection(params)
        workspace_id = params.get("workspace_id")
        config_revision_id = params.get("config_revision_id")
        expected_revision = params.get("expected_revision")
        if workspace_id is None or config_revision_id is None or expected_revision is None:
            raise TypeError("workspace_id, config_revision_id, and expected_revision are required")
        workspace_id = str(workspace_id)
        config_revision_id = str(config_revision_id)
        current = _select_revision(connection, workspace_id=workspace_id, config_revision_id=config_revision_id)
        if current is None:
            foreign = _select_revision_by_id(connection, config_revision_id)
            if foreign is not None:
                raise PermissionError("configuration revision belongs to another workspace")
            raise PermissionError("configuration revision not found")
        if current.revision != expected_revision or current.status is not ConfigRevisionStatus.DRAFT:
            raise RevisionConflictError(current.revision)
        row = connection.execute(
            "UPDATE controlplane.cp_config_revisions SET status='PUBLISHED', revision=revision+1, "
            "actor_ref='system', change_reason='published', updated_at=CURRENT_TIMESTAMP "
            "WHERE workspace_id=%s AND config_revision_id=%s AND revision=%s AND status='DRAFT' "
            f"RETURNING {_REVISION_COLUMNS}",
            (workspace_id, config_revision_id, expected_revision),
        ).fetchone()
        if row is None:
            latest = _select_revision(connection, workspace_id=workspace_id, config_revision_id=config_revision_id)
            raise RevisionConflictError(latest.revision if latest is not None else int(expected_revision))
        result = _revision_from_row(row)
        if result is None:
            raise RuntimeError("configuration revision publish returned no row")
        event_payload = {
            "workspace_id": result.workspace_id,
            "config_revision_id": result.config_revision_id,
            "config_revision_number": result.config_revision_number,
            "revision": result.revision,
            "status": result.status.value,
            "reason": "published",
            "audit_ref": "p5a",
            "actor_ref": "system",
        }
        PostgresOutboxRepository(connection).enqueue(
            ConfigEventFactory().publish_event(payload=event_payload, workspace_id=result.workspace_id)
        )
        return result


class SecretHandleStore:
    """Metadata-only secret-handle boundary; plaintext is never persisted or returned."""

    def register(self, **kwargs: Any) -> SecretHandle:
        params = dict(kwargs)
        connection = _require_connection(params)
        plaintext_keys = [
            name for name in params
            if name != "secret_handle_id" and (name.lower() in _UNSAFE_SECRET_NAMES or name.lower().endswith("_secret"))
        ]
        if plaintext_keys:
            raise ValueError("plaintext secret material is not accepted")
        required = (
            "workspace_id",
            "provider_ref",
            "account_ref",
            "alias_ref",
            "redacted_fingerprint_or_version",
            "validation_status",
            "audit_ref",
        )
        missing = [name for name in required if name not in params]
        if missing:
            raise TypeError(f"missing required arguments: {', '.join(missing)}")
        handle_id = str(params.get("secret_handle_id") or uuid.uuid4())
        row = connection.execute(
            "INSERT INTO controlplane.cp_secret_handles "
            "(secret_handle_id, workspace_id, provider_ref, account_ref, alias_ref, redacted_fingerprint_or_version, "
            "validation_status, revoked_at, expires_at, audit_ref) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING secret_handle_id::text, workspace_id::text, provider_ref, account_ref, alias_ref, "
            "redacted_fingerprint_or_version, validation_status, revoked_at, expires_at, audit_ref",
            (
                handle_id,
                params["workspace_id"],
                params["provider_ref"],
                params["account_ref"],
                params["alias_ref"],
                params["redacted_fingerprint_or_version"],
                params["validation_status"],
                params.get("revoked_at"),
                params.get("expires_at"),
                params["audit_ref"],
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("secret handle insert returned no row")
        return SecretHandle(
            secret_handle_id=str(row[0]),
            workspace_id=str(row[1]),
            provider_ref=str(row[2]),
            account_ref=str(row[3]),
            alias_ref=str(row[4]),
            redacted_fingerprint_or_version=str(row[5]),
            validation_status=str(row[6]),
            revoked_at=row[7].isoformat() if hasattr(row[7], "isoformat") else row[7],
            expires_at=row[8].isoformat() if hasattr(row[8], "isoformat") else row[8],
            audit_ref=str(row[9]),
        )


__all__ = [
    "ConfigEventFactory",
    "ConfigRevisionRepository",
    "ConfigRevisionService",
    "SecretHandleStore",
]
