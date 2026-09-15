"""Application orchestration for P5A configuration and secret metadata."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable, Protocol
import uuid

from controlplane.application.idempotency import request_hash
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus, SecretHandle
from controlplane.domain.events import DomainEvent, ensure_safe_event_payload
from controlplane.domain.statemachine import ForbiddenTransitionError


class ConfigSecurityRepositoryPort(Protocol):
    def create_revision(self, **kwargs: Any) -> ConfigRevision: ...
    def get_scoped(self, **kwargs: Any) -> ConfigRevision | None: ...
    def get_by_id(self, **kwargs: Any) -> ConfigRevision | None: ...
    def transition(self, **kwargs: Any) -> ConfigRevision | None: ...
    def register_secret_handle(self, **kwargs: Any) -> SecretHandle: ...


class ConfigEventSinkPort(Protocol):
    def enqueue(self, event: DomainEvent) -> str: ...


RepositoryFactory = Callable[[Any], ConfigSecurityRepositoryPort]
EventSinkFactory = Callable[[Any], ConfigEventSinkPort]
_UNSAFE_SECRET_NAMES = frozenset({"value", "secret_value", "plaintext", "plaintext_secret", "token", "access_token", "refresh_token", "password", "private_key", "credential", "raw_credential", "raw_secret", "secret_blob", "blob"})
_UNSAFE_EVENT_TEXT = re.compile(r"(?:password|secret|token|api[_-]?key|credential|refresh\s+token)\s*[:=]|signature\s*=|traceback|stack\s+trace", re.IGNORECASE)


def _event_payload_is_safe(payload: Any) -> None:
    def walk(value: Any) -> None:
        if isinstance(value, (bytes, bytearray, memoryview)):
            raise ValueError("unsafe domain event payload")
        if isinstance(value, str):
            if _UNSAFE_EVENT_TEXT.search(value): raise ValueError("unsafe domain event payload")
        elif isinstance(value, dict):
            for key, child in value.items():
                if _UNSAFE_EVENT_TEXT.search(str(key)): raise ValueError("unsafe domain event payload")
                walk(child)
        elif isinstance(value, (list, tuple, set)):
            for child in value: walk(child)
    walk(payload)
    ensure_safe_event_payload(payload)


class ConfigEventFactory:
    def _build(self, *, payload: dict[str, Any], workspace_id: str, event_name: str) -> DomainEvent:
        _event_payload_is_safe(payload)
        return DomainEvent(contract_name="controlplane.config_revision", contract_version=1, message_id=str(uuid.uuid4()), workspace_id=str(workspace_id), correlation_id=str(payload.get("correlation_id", "config-revision")), causation_id=None, trace_context=None, occurred_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), actor=str(payload.get("actor_ref", payload.get("actor", "system"))), recovery_epoch=None, payload=payload, event_id=str(uuid.uuid4()), event_name=event_name, aggregate_type="config_revision", aggregate_id=str(payload.get("config_revision_id", "unknown")), aggregate_revision=int(payload.get("revision", 1)), producer="controlplane.config_security", schema_version=1, sensitivity="internal")

    def publish_event(self, **kwargs: Any) -> DomainEvent:
        payload, workspace_id = kwargs.get("payload"), kwargs.get("workspace_id")
        if not isinstance(payload, dict) or workspace_id is None: raise TypeError("payload and workspace_id are required")
        return self._build(payload=payload, workspace_id=str(workspace_id), event_name="config_revision.published")

    def invalidation_event(self, **kwargs: Any) -> DomainEvent:
        payload, workspace_id = kwargs.get("payload"), kwargs.get("workspace_id")
        if not isinstance(payload, dict) or workspace_id is None: raise TypeError("payload and workspace_id are required")
        return self._build(payload=payload, workspace_id=str(workspace_id), event_name="config_revision.invalidated")


def _allowed_transition(current: ConfigRevisionStatus, requested: ConfigRevisionStatus) -> bool:
    return (current, requested) in {(ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.PUBLISHED), (ConfigRevisionStatus.DRAFT, ConfigRevisionStatus.INVALIDATED), (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.SUPERSEDED), (ConfigRevisionStatus.PUBLISHED, ConfigRevisionStatus.INVALIDATED), (ConfigRevisionStatus.SUPERSEDED, ConfigRevisionStatus.INVALIDATED)}


class _ConfigRevisionOrchestrator:
    def __init__(self, repository_factory: RepositoryFactory, event_sink_factory: EventSinkFactory) -> None:
        self._repository_factory, self._event_sink_factory = repository_factory, event_sink_factory

    @staticmethod
    def _event(revision: ConfigRevision, *, reason: str, actor_ref: str, audit_ref: str) -> DomainEvent:
        payload = {"workspace_id": revision.workspace_id, "config_revision_id": revision.config_revision_id, "config_revision_number": revision.config_revision_number, "revision": revision.revision, "status": revision.status.value, "reason": reason, "audit_ref": audit_ref, "actor_ref": actor_ref}
        factory = ConfigEventFactory()
        return factory.invalidation_event(payload=payload, workspace_id=revision.workspace_id) if revision.status is ConfigRevisionStatus.INVALIDATED else factory.publish_event(payload=payload, workspace_id=revision.workspace_id)


class ConfigRevisionService(_ConfigRevisionOrchestrator):
    """Create and transition immutable revisions through injected persistence ports."""
    def create_revision(self, **kwargs: Any) -> ConfigRevision:
        params = dict(kwargs); connection = params.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        required = ("workspace_id", "scope_kind", "scope_key", "config_revision_number", "payload", "actor_ref", "change_reason")
        missing = [name for name in required if name not in params]
        if missing: raise TypeError(f"missing required arguments: {', '.join(missing)}")
        if not isinstance(params["payload"], dict): raise ValueError("payload must be a JSON object")
        return self._repository_factory(connection).create_revision(**params, config_revision_id=str(params.get("config_revision_id") or uuid.uuid4()), content_hash=request_hash(params["payload"]))

    def transition(self, **kwargs: Any) -> ConfigRevision:
        params = dict(kwargs); connection = params.pop("connection", None)
        revision, expected_revision, requested_status, actor_ref = params.get("revision"), params.get("expected_revision"), params.get("requested_status"), params.get("actor_ref")
        if connection is None: raise TypeError("connection is required")
        if revision is None or expected_revision is None or requested_status is None or actor_ref is None: raise TypeError("revision, expected_revision, requested_status, and actor_ref are required")
        requested = ConfigRevisionStatus(str(requested_status))
        if not _allowed_transition(revision.status, requested): raise ForbiddenTransitionError(aggregate_type="config_revision", current_state=revision.status, requested_next_state=requested, current_revision=revision.revision)
        if revision.revision != expected_revision: raise RevisionConflictError(int(revision.revision))
        repository = self._repository_factory(connection)
        current = repository.get_scoped(workspace_id=revision.workspace_id, config_revision_id=revision.config_revision_id)
        if current is None: raise PermissionError("configuration revision is not in workspace")
        if current.revision != expected_revision: raise RevisionConflictError(current.revision)
        if not _allowed_transition(current.status, requested): raise ForbiddenTransitionError(aggregate_type="config_revision", current_state=current.status, requested_next_state=requested, current_revision=current.revision)
        reason = params.get("change_reason", f"transition to {requested.value}")
        result = repository.transition(workspace_id=current.workspace_id, config_revision_id=current.config_revision_id, expected_revision=expected_revision, current_status=current.status, requested_status=requested, actor_ref=actor_ref, change_reason=reason)
        if result is None:
            latest = repository.get_scoped(workspace_id=current.workspace_id, config_revision_id=current.config_revision_id)
            raise RevisionConflictError(latest.revision if latest is not None else current.revision)
        self._event_sink_factory(connection).enqueue(self._event(result, reason=reason, actor_ref=str(actor_ref), audit_ref=str(params.get("audit_ref", "p5a"))))
        return result


class ConfigRevisionRepository(_ConfigRevisionOrchestrator):
    """Workspace-scoped publishing facade over injected persistence ports."""
    def get_scoped(self, **kwargs: Any) -> ConfigRevision | None:
        connection, workspace_id, config_revision_id = kwargs.get("connection"), kwargs.get("workspace_id"), kwargs.get("config_revision_id")
        if connection is None or workspace_id is None or config_revision_id is None: raise TypeError("connection, workspace_id and config_revision_id are required")
        return self._repository_factory(connection).get_scoped(workspace_id=str(workspace_id), config_revision_id=str(config_revision_id))

    def publish(self, **kwargs: Any) -> ConfigRevision:
        connection, workspace_id, config_revision_id, expected_revision = kwargs.get("connection"), kwargs.get("workspace_id"), kwargs.get("config_revision_id"), kwargs.get("expected_revision")
        if connection is None or workspace_id is None or config_revision_id is None or expected_revision is None: raise TypeError("connection, workspace_id, config_revision_id and expected_revision are required")
        repository = self._repository_factory(connection)
        current = repository.get_scoped(workspace_id=str(workspace_id), config_revision_id=str(config_revision_id))
        if current is None:
            if repository.get_by_id(config_revision_id=str(config_revision_id)) is not None: raise PermissionError("configuration revision belongs to another workspace")
            raise PermissionError("configuration revision not found")
        if current.revision != expected_revision or current.status is not ConfigRevisionStatus.DRAFT: raise RevisionConflictError(current.revision)
        result = repository.transition(workspace_id=current.workspace_id, config_revision_id=current.config_revision_id, expected_revision=expected_revision, current_status=ConfigRevisionStatus.DRAFT, requested_status=ConfigRevisionStatus.PUBLISHED, actor_ref="system", change_reason="published")
        if result is None:
            latest = repository.get_scoped(workspace_id=current.workspace_id, config_revision_id=current.config_revision_id)
            raise RevisionConflictError(latest.revision if latest is not None else current.revision)
        self._event_sink_factory(connection).enqueue(self._event(result, reason="published", actor_ref="system", audit_ref="p5a"))
        return result


class SecretHandleStore:
    """Metadata-only secret boundary backed by an injected persistence port."""
    def __init__(self, repository_factory: RepositoryFactory) -> None: self._repository_factory = repository_factory
    def register(self, **kwargs: Any) -> SecretHandle:
        params = dict(kwargs); connection = params.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        plaintext_keys = [name for name in params if name != "secret_handle_id" and (name.lower() in _UNSAFE_SECRET_NAMES or name.lower().endswith("_secret"))]
        if plaintext_keys: raise ValueError("plaintext secret material is not accepted")
        required = ("workspace_id", "provider_ref", "account_ref", "alias_ref", "redacted_fingerprint_or_version", "validation_status", "audit_ref")
        missing = [name for name in required if name not in params]
        if missing: raise TypeError(f"missing required arguments: {', '.join(missing)}")
        return self._repository_factory(connection).register_secret_handle(**params, secret_handle_id=str(params.get("secret_handle_id") or uuid.uuid4()))


__all__ = ["ConfigEventFactory", "ConfigRevisionRepository", "ConfigRevisionService", "SecretHandleStore"]
