"""PostgreSQL outbox writer for source ingestion."""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from controlplane.domain.events import DomainEvent
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from source_ingestion.persistence._sql import ConnectionProvider, savepoint, uuid_text


@dataclass(frozen=True)
class OutboxContext:
    workspace_id: str | None = None
    correlation_id: str | None = None
    actor: str = 'source_ingestion'


class PostgresSourceOutboxWriter(IOutboxWriter):
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

        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, deduplication_id))

        raw_ws = payload.get('workspace_id')
        if isinstance(raw_ws, str) and raw_ws.strip():
            ws_candidate = raw_ws
        elif isinstance(self._context.workspace_id, str) and self._context.workspace_id.strip():
            ws_candidate = self._context.workspace_id
        else:
            raise ValueError('workspace_id is required for outbox events')

        workspace_id = uuid_text(ws_candidate, field='workspace_id')

        conn = self._connection()
        row = conn.execute(
            'SELECT 1 FROM controlplane.cp_outbox_events WHERE event_id = %s',
            (event_id,),
        ).fetchone()
        if row is not None:
            return event_id

        payload_corr = payload.get('correlation_id')
        if isinstance(payload_corr, str) and payload_corr.strip():
            correlation_id = payload_corr
        elif isinstance(self._context.correlation_id, str) and self._context.correlation_id.strip():
            correlation_id = self._context.correlation_id
        else:
            correlation_id = deduplication_id

        raw_occ = payload.get('occurred_at')
        occurred_at = None
        if isinstance(raw_occ, str):
            try:
                parsed = datetime.datetime.fromisoformat(raw_occ)
                if parsed.tzinfo is not None:
                    occurred_at = raw_occ
            except (ValueError, TypeError):
                pass
        if occurred_at is None:
            occurred_at = datetime.datetime.now(datetime.UTC).isoformat()

        payload_actor = payload.get('actor')
        if isinstance(payload_actor, str) and payload_actor.strip():
            actor = payload_actor
        else:
            actor = self._context.actor

        raw_epoch = payload.get('recovery_epoch')
        recovery_epoch: int | None = None
        if isinstance(raw_epoch, int) and raw_epoch >= 0:
            recovery_epoch = raw_epoch
        elif isinstance(raw_epoch, str) and raw_epoch.isdigit() and len(raw_epoch) <= 18:
            recovery_epoch = int(raw_epoch)

        payload_agg_type = payload.get('aggregate_type')
        if isinstance(payload_agg_type, str) and payload_agg_type.strip():
            aggregate_type = payload_agg_type
        else:
            aggregate_type = 'SourceIngestion'

        payload_agg_rev = payload.get('aggregate_revision')
        if type(payload_agg_rev) is int and payload_agg_rev >= 1:
            aggregate_revision = payload_agg_rev
        else:
            aggregate_revision = 1

        event = DomainEvent(
            contract_name=event_type,
            contract_version=1,
            message_id=event_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            causation_id=None,
            trace_context=None,
            occurred_at=occurred_at,
            actor=actor,
            recovery_epoch=recovery_epoch,
            payload=dict(payload),
            event_id=event_id,
            event_name=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_revision=aggregate_revision,
            producer='A',
            schema_version=1,
            sensitivity='internal',
        )

        with savepoint(conn):
            PostgresOutboxRepository(conn).enqueue(event)

        return event_id
