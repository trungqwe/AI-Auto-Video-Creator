"""PostgreSQL outbox writer for render (PERSIST-F)."""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from controlplane.domain.events import DomainEvent
from controlplane.domain.events.contracts import ensure_safe_event_payload
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from render.domain.events import EVENT_AGGREGATE_TYPES, PRODUCER, SENSITIVITY
from render.persistence._sql import ConnectionProvider, savepoint, uuid_text


@dataclass(frozen=True)
class OutboxContext:
    workspace_id: str | None = None
    correlation_id: str | None = None
    actor: str = 'render'


class PostgresRenderOutboxWriter(IOutboxWriter):
    def __init__(self, connection: ConnectionProvider, context: OutboxContext) -> None:
        self._connection = connection
        self._context = context

    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        deduplication_id: str,
    ) -> str:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError('event_type must be a non-empty string')
        if not isinstance(aggregate_id, str) or not aggregate_id.strip():
            raise ValueError('aggregate_id must be a non-empty string')
        if not isinstance(deduplication_id, str) or not deduplication_id.strip():
            raise ValueError('deduplication_id must be a non-empty string')
        if not isinstance(payload, Mapping):
            raise ValueError('payload must be a mapping')

        ensure_safe_event_payload(dict(payload))

        if self._context.workspace_id is None:
            raise ValueError('workspace_id is required for outbox events')
        workspace_id = uuid_text(self._context.workspace_id)

        conn = self._connection()
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, deduplication_id))

        row = conn.execute(
            'SELECT 1 FROM controlplane.cp_outbox_events WHERE event_id = %s',
            (event_id,),
        ).fetchone()
        if row is not None:
            return event_id

        correlation_id = self._context.correlation_id or deduplication_id
        occurred_at = datetime.datetime.now(datetime.UTC).isoformat()
        aggregate_type = EVENT_AGGREGATE_TYPES.get(event_type, 'Render')
        raw_rev = payload.get('revision')
        aggregate_revision = raw_rev if (isinstance(raw_rev, int) and not isinstance(raw_rev, bool) and raw_rev >= 1) else 1

        event = DomainEvent(
            contract_name=event_type,
            contract_version=1,
            message_id=event_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            causation_id=None,
            trace_context=None,
            occurred_at=occurred_at,
            actor=self._context.actor,
            recovery_epoch=None,
            payload=dict(payload),
            event_id=event_id,
            event_name=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_revision=aggregate_revision,
            producer=PRODUCER,
            schema_version=1,
            sensitivity=SENSITIVITY,
        )

        with savepoint(conn):
            PostgresOutboxRepository(conn).enqueue(event)

        return event_id