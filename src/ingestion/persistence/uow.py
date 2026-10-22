"""PostgreSQL Unit of Work and Outbox writer for module B (PERSIST-B, REQ-B-CONV-02)."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from types import TracebackType
from typing import Any

from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from ingestion.application.ports import OutboxWriter, UnitOfWork
from ingestion.persistence.repositories import (
    PostgresArticleRepository,
    PostgresEventRepository,
    PostgresRecordRepository,
    PostgresResolutionRepository,
)


class PostgresOutboxWriter(OutboxWriter):
    def __init__(
        self,
        connection_getter: Callable[[], Any],
        workspace_id: str,
        correlation_id: str = "ingestion",
        actor: str = "system:ingestion",
    ) -> None:
        self._connection_getter = connection_getter
        self._workspace_id = workspace_id
        self._correlation_id = correlation_id
        self._actor = actor

    @property
    def _conn(self) -> Any:
        return self._connection_getter()

    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        deduplication_id: str,
    ) -> str:
        if not isinstance(deduplication_id, str) or not deduplication_id:
            raise ValueError("deduplication_id must be a non-empty string")

        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, deduplication_id))
        conn = self._conn
        row = conn.execute(
            "SELECT 1 FROM controlplane.cp_outbox_events WHERE event_id = %s",
            (event_id,),
        ).fetchone()
        if row is not None:
            return event_id

        raw_epoch = payload.get("recovery_epoch")
        recovery_epoch: int | None = None
        if isinstance(raw_epoch, int) and raw_epoch < 2**63:
            recovery_epoch = raw_epoch
        elif isinstance(raw_epoch, str) and raw_epoch.isdigit() and int(raw_epoch) < 2**63:
            recovery_epoch = int(raw_epoch)

        plain_payload = json.loads(json.dumps(dict(payload), default=str))

        event = DomainEvent(
            contract_name=event_type,
            contract_version=1,
            message_id=deduplication_id,
            workspace_id=self._workspace_id,
            correlation_id=self._correlation_id,
            causation_id=None,
            trace_context=None,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            actor=self._actor,
            recovery_epoch=recovery_epoch,
            payload=plain_payload,
            event_id=event_id,
            event_name=event_type,
            aggregate_type="ingestion",
            aggregate_id=aggregate_id,
            aggregate_revision=1,
            producer="ingestion",
            schema_version=1,
            sensitivity="internal",
        )

        PostgresOutboxRepository(conn).enqueue(event)
        return event_id


class PostgresIngestionUnitOfWork(UnitOfWork):
    def __init__(
        self,
        manager: Any,
        *,
        workspace_id: str,
        correlation_id: str = "ingestion",
        actor: str = "system:ingestion",
    ) -> None:
        self._manager = manager
        self._workspace_id = workspace_id
        self._correlation_id = correlation_id
        self._actor = actor
        self._active = False
        self._context: Any = None
        self._connection: Any = None

        self.articles = PostgresArticleRepository(self._get_connection, workspace_id)
        self.resolutions = PostgresResolutionRepository(self._get_connection, workspace_id)
        self.events = PostgresEventRepository(self._get_connection, workspace_id)
        self.records = PostgresRecordRepository(self._get_connection, workspace_id)
        self.outbox = PostgresOutboxWriter(
            self._get_connection,
            workspace_id,
            correlation_id=correlation_id,
            actor=actor,
        )

    def _get_connection(self) -> Any:
        if not self._active or self._connection is None:
            raise RuntimeError("unit of work is not active; use `with uow:`")
        return self._connection

    def __enter__(self) -> PostgresIngestionUnitOfWork:
        if self._active:
            raise RuntimeError("unit of work is already active")
        self._active = True
        self._context = self._manager.borrow_connection()
        self._connection = self._context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if self._connection is not None:
                try:
                    self._connection.rollback()
                except Exception:
                    pass
        finally:
            context = self._context
            self._connection = None
            self._context = None
            self._active = False
            if context is not None:
                context.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        if not self._active or self._connection is None:
            raise RuntimeError("unit of work is not active; use `with uow:`")
        self._connection.commit()

    def rollback(self) -> None:
        if not self._active or self._connection is None:
            raise RuntimeError("unit of work is not active; use `with uow:`")
        self._connection.rollback()

    def begin(self) -> None:
        if not self._active or self._connection is None:
            raise RuntimeError("unit of work is not active; use `with uow:`")
