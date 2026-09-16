"""Atomic HTTP command coordination using accepted P1/P2/P3/P5A ports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol
import uuid

from controlplane.application.idempotency import request_hash
from controlplane.application.orchestration.start_batch import StartBatchService
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events import DomainEvent


class IdempotencyPort(Protocol):
    def lock_key(self, **kwargs: Any) -> None: ...
    def get_record(self, **kwargs: Any) -> Any: ...
    def replay_receipt(self, receipt_id: object) -> dict[str, object]: ...
    def create_receipt(self, **kwargs: Any) -> dict[str, object]: ...
    def create_record(self, **kwargs: Any) -> None: ...


class ReceiptFieldsPort(Protocol):
    def bind(self, *, workspace_id: str, receipt_id: object,
             operation_id: str | None, resource_ref: dict[str, object],
             current_revision: int | None) -> dict[str, object]: ...


class OutboxPort(Protocol):
    def enqueue(self, event: DomainEvent) -> str: ...


class ConfigScopePort(Protocol):
    def current(self, *, workspace_id: str, scope_kind: str,
                scope_key: str) -> Any | None: ...


class ControlApiCommandService:
    def __init__(self, *, uow_factory: Callable[[], Any],
                 idempotency_factory: Callable[[Any], IdempotencyPort],
                 receipt_fields_factory: Callable[[Any], ReceiptFieldsPort],
                 outbox_factory: Callable[[Any], OutboxPort],
                 start_batch_service: StartBatchService,
                 config_scope_factory: Callable[[Any], ConfigScopePort],
                 config_service: Any, config_repository: Any) -> None:
        self._uow_factory = uow_factory
        self._idempotency_factory = idempotency_factory
        self._receipt_fields_factory = receipt_fields_factory
        self._outbox_factory = outbox_factory
        self._start_batch_service = start_batch_service
        self._config_scope_factory = config_scope_factory
        self._config_service = config_service
        self._config_repository = config_repository

    @staticmethod
    def _idempotency_check(repo: IdempotencyPort, *, workspace_id: str,
                           command_name: str, idempotency_key: str,
                           logical: dict[str, object]) -> tuple[str, dict[str, object] | None]:
        digest = request_hash(logical)
        key = {"workspace_id": workspace_id, "command_name": command_name,
               "idempotency_key": idempotency_key}
        repo.lock_key(**key)
        record = repo.get_record(**key)
        if record is not None:
            if record[0] != digest:
                raise ValueError("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD")
            return digest, repo.replay_receipt(record[1])
        return digest, None

    def start_batch(self, *, workspace_id: str, actor_id: str,
                    correlation_id: str, idempotency_key: str,
                    payload: dict[str, object],
                    inject_before_commit: BaseException | None = None) -> dict[str, object]:
        target = payload.get("target_completed_videos")
        if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
            raise ValueError("target_completed_videos must be a positive integer")
        logical = {"workspace_id": workspace_id, "command_name": "StartProductionBatch",
                   "payload": payload}
        with self._uow_factory() as uow:
            connection = uow.connection
            idempotency = self._idempotency_factory(connection)
            digest, duplicate = self._idempotency_check(
                idempotency, workspace_id=workspace_id,
                command_name="StartProductionBatch", idempotency_key=idempotency_key,
                logical=logical,
            )
            if duplicate is not None:
                return duplicate
            batch_id = self._start_batch_service.start(
                connection=connection, workspace_id=workspace_id, target_count=target,
            )
            operation_id = str(uuid.uuid4())
            receipt = idempotency.create_receipt(workspace_id=workspace_id)
            receipt = self._receipt_fields_factory(connection).bind(
                workspace_id=workspace_id, receipt_id=receipt["receipt_id"],
                operation_id=operation_id,
                resource_ref={"kind": "production_batch", "batch_id": batch_id},
                current_revision=None,
            )
            idempotency.create_record(
                workspace_id=workspace_id, command_name="StartProductionBatch",
                idempotency_key=idempotency_key, request_hash=digest,
                receipt_id=receipt["receipt_id"],
            )
            event = DomainEvent(
                contract_name="controlplane.production_batch", contract_version=1,
                message_id=str(uuid.uuid4()), workspace_id=workspace_id,
                correlation_id=correlation_id, causation_id=None, trace_context=None,
                occurred_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                actor=actor_id, recovery_epoch=None,
                payload={"batch_id": batch_id, "operation_id": operation_id,
                         "receipt_id": str(receipt["receipt_id"]),
                         "target_count": target, "status": "CREATED"},
                event_id=str(uuid.uuid4()), event_name="production_batch.start_accepted",
                aggregate_type="production_batch", aggregate_id=batch_id,
                aggregate_revision=1, producer="controlplane.control_api",
                schema_version=1, sensitivity="internal",
            )
            self._outbox_factory(connection).enqueue(event)
            if inject_before_commit is not None:
                raise inject_before_commit
            return receipt

    def put_config(self, *, workspace_id: str, actor_id: str,
                   idempotency_key: str, scope_kind: str, scope_key: str,
                   expected_revision: int, payload: dict[str, object],
                   inject_before_commit: BaseException | None = None) -> dict[str, object]:
        logical = {"workspace_id": workspace_id, "command_name": "PublishConfigurationRevision",
                   "payload": {"scope_kind": scope_kind, "scope_key": scope_key,
                               "configuration": payload},
                   "expected_revision": expected_revision}
        with self._uow_factory() as uow:
            connection = uow.connection
            idempotency = self._idempotency_factory(connection)
            digest, duplicate = self._idempotency_check(
                idempotency, workspace_id=workspace_id,
                command_name="PublishConfigurationRevision",
                idempotency_key=idempotency_key, logical=logical,
            )
            if duplicate is not None:
                return duplicate
            current = self._config_scope_factory(connection).current(
                workspace_id=workspace_id, scope_kind=scope_kind, scope_key=scope_key,
            )
            current_revision = current.revision if current is not None else 0
            if current_revision != expected_revision:
                raise RevisionConflictError(current_revision)
            created = self._config_service.create_revision(
                connection=connection, workspace_id=workspace_id,
                scope_kind=scope_kind, scope_key=scope_key,
                config_revision_number=(current.config_revision_number + 1 if current else 1),
                payload=payload, actor_ref=actor_id, change_reason="HTTP configuration update",
            )
            published = self._config_repository.publish(
                connection=connection, workspace_id=workspace_id,
                config_revision_id=created.config_revision_id, expected_revision=1,
            )
            receipt = idempotency.create_receipt(workspace_id=workspace_id)
            receipt = self._receipt_fields_factory(connection).bind(
                workspace_id=workspace_id, receipt_id=receipt["receipt_id"],
                operation_id=None,
                resource_ref={"kind": "config_revision",
                              "config_revision_id": published.config_revision_id},
                current_revision=published.revision,
            )
            idempotency.create_record(
                workspace_id=workspace_id, command_name="PublishConfigurationRevision",
                idempotency_key=idempotency_key, request_hash=digest,
                receipt_id=receipt["receipt_id"],
            )
            if inject_before_commit is not None:
                raise inject_before_commit
            return receipt
