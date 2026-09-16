"""P7A composition of accepted PostgreSQL adapters on one caller connection."""

from __future__ import annotations

from typing import Any, Callable

from psycopg.types.json import Jsonb

from controlplane.application.config_security import ConfigRevisionRepository, ConfigRevisionService
from controlplane.application.control_api.commands import ControlApiCommandService
from controlplane.application.orchestration.start_batch import StartBatchService
from controlplane.infrastructure.db.config_security import (
    PostgresConfigEventSink, PostgresConfigSecurityRepository,
)
from controlplane.infrastructure.db.idempotency.postgres_repository import PostgresIdempotencyRepository
from controlplane.infrastructure.db.orchestration.start_batch import PostgresStartBatchRepository
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository


class PostgresReceiptFields:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def bind(self, *, workspace_id: str, receipt_id: object,
             operation_id: str | None, resource_ref: dict[str, object],
             current_revision: int | None) -> dict[str, object]:
        row = self._connection.execute(
            "UPDATE controlplane.cp_command_receipts SET operation_id=%s,resource_ref=%s,"
            "current_revision=%s WHERE workspace_id=%s AND receipt_id=%s "
            "RETURNING receipt_id,command_id,disposition,operation_id,resource_ref,accepted_at,current_revision",
            (operation_id, Jsonb(resource_ref), current_revision, workspace_id, receipt_id),
        ).fetchone()
        if row is None:
            raise LookupError("receipt not found in workspace")
        return PostgresIdempotencyRepository._receipt(row)


class PostgresConfigScope:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def current(self, *, workspace_id: str, scope_kind: str, scope_key: str) -> Any | None:
        row = self._connection.execute(
            "SELECT config_revision_id::text FROM controlplane.cp_config_revisions "
            "WHERE workspace_id=%s AND scope_kind=%s AND scope_key=%s "
            "ORDER BY config_revision_number DESC LIMIT 1",
            (workspace_id, scope_kind, scope_key),
        ).fetchone()
        if row is None:
            return None
        return PostgresConfigSecurityRepository(self._connection).get_scoped(
            workspace_id=workspace_id, config_revision_id=row[0],
        )


def compose_command_service(uow_factory: Callable[[], Any]) -> ControlApiCommandService:
    return ControlApiCommandService(
        uow_factory=uow_factory,
        idempotency_factory=PostgresIdempotencyRepository,
        receipt_fields_factory=PostgresReceiptFields,
        outbox_factory=PostgresOutboxRepository,
        start_batch_service=StartBatchService(PostgresStartBatchRepository),
        config_scope_factory=PostgresConfigScope,
        config_service=ConfigRevisionService(
            PostgresConfigSecurityRepository, PostgresConfigEventSink,
        ),
        config_repository=ConfigRevisionRepository(
            PostgresConfigSecurityRepository, PostgresConfigEventSink,
        ),
    )
