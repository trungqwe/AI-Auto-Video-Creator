"""OPSTREAM-WIRE: P3 consumer that projects outbox events into controlplane.cp_operation_stream in the worker process.

Every event of the workspace in cp_outbox_events goes through the accepted P3 PostgresEventProcessor under the consumer
CONSUMER_ID, one event per transaction: dedupe by (consumer_id, event_id) checkpoint, revision order per aggregate,
quarantine of unsupported schema, and the operation stream append of PostgresOperationStreamRepository (ordering fence,
monotonic cursor, _ensure_safe). The APPLIED checkpoints of the consumer are the projection state, so a rerun or a
restart never appends an event twice. The consumer only reads cp_outbox_events and never touches its published flag,
which belongs to OutboxRelay. An event whose stored payload fails the payload safety check is quarantined by reference
(no payload is copied). The connection factory must return a connection with autocommit off.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.projections.postgres import PostgresEventProcessor

CONSUMER_ID = 'controlplane.operation_stream'
BATCH_LIMIT = 100
APPLIED = 'APPLIED'
UNSAFE_PAYLOAD = 'QUARANTINED_UNSAFE_PAYLOAD'
_LOG = logging.getLogger(__name__)
COLUMNS = (
    'event_id', 'workspace_id', 'contract_name', 'contract_version', 'message_id', 'correlation_id', 'causation_id',
    'trace_context', 'occurred_at', 'actor', 'recovery_epoch', 'payload', 'event_name', 'aggregate_type', 'aggregate_id',
    'aggregate_revision', 'producer', 'schema_version', 'sensitivity',
)
PENDING_SQL = (
    'SELECT e.event_id::text, e.workspace_id::text, e.contract_name, e.contract_version, e.message_id, e.correlation_id, '
    'e.causation_id, e.trace_context, e.occurred_at, e.actor, e.recovery_epoch, e.payload, e.event_name, e.aggregate_type, '
    'e.aggregate_id, e.aggregate_revision, e.producer, e.schema_version, e.sensitivity '
    'FROM controlplane.cp_outbox_events e '
    'WHERE e.workspace_id = %s '
    'AND NOT EXISTS (SELECT 1 FROM controlplane.cp_event_checkpoints c WHERE c.consumer_id = %s AND c.event_id = e.event_id) '
    'AND NOT EXISTS (SELECT 1 FROM controlplane.cp_event_quarantine q WHERE q.consumer_id = %s AND q.event_id = e.event_id) '
    'ORDER BY e.recorded_at, e.aggregate_revision, e.event_id LIMIT %s'
)
REVISION_SQL = (
    'SELECT MAX(e.aggregate_revision) FROM controlplane.cp_outbox_events e '
    'JOIN controlplane.cp_event_checkpoints c ON c.consumer_id = %s AND c.event_id = e.event_id AND c.status = %s '
    'WHERE e.workspace_id = %s AND e.aggregate_type = %s AND e.aggregate_id = %s'
)
QUARANTINE_SQL = (
    'INSERT INTO controlplane.cp_event_quarantine '
    '(consumer_id, event_id, workspace_id, reason_code, event_envelope, quarantine_status) '
    "VALUES (%s, %s, %s, %s, %s::jsonb, 'OPEN') ON CONFLICT (consumer_id, event_id) DO NOTHING"
)


class AppliedRevisions:
    """Projection seam of PostgresEventProcessor for one aggregate type of one workspace.

    The current revision of an aggregate is the highest revision this consumer has checkpointed as APPLIED; the
    processor writes that checkpoint in the same transaction as the stream row, so apply() records nothing itself.
    """

    def __init__(self, connection: Any, workspace_id: str, aggregate_type: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id
        self._aggregate_type = aggregate_type

    def current_revision(self, consumer_id: str, aggregate_id: str) -> int | None:
        row = self._connection.execute(
            REVISION_SQL, (consumer_id, APPLIED, self._workspace_id, self._aggregate_type, aggregate_id),
        ).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def apply(self, consumer_id: str, aggregate_id: str, revision: int) -> None:
        return None


def _event(row: tuple[Any, ...]) -> DomainEvent:
    values = dict(zip(COLUMNS, row))
    occurred_at = values['occurred_at']
    values['occurred_at'] = occurred_at.isoformat() if hasattr(occurred_at, 'isoformat') else str(occurred_at)
    return DomainEvent(**values)


def _reference(row: tuple[Any, ...]) -> str:
    values = dict(zip(COLUMNS, row))
    return json.dumps({
        'source': 'controlplane.cp_outbox_events',
        'event_id': values['event_id'],
        'event_name': values['event_name'],
        'aggregate_type': values['aggregate_type'],
        'aggregate_id': values['aggregate_id'],
        'aggregate_revision': values['aggregate_revision'],
    })


class OperationStreamRelay:
    def __init__(
        self,
        connection_factory: Callable[[], Any],
        workspace_id: str,
        *,
        consumer_id: str = CONSUMER_ID,
        batch_limit: int = BATCH_LIMIT,
    ) -> None:
        if batch_limit < 1:
            raise ValueError('batch_limit must be positive')
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id
        self._consumer_id = consumer_id
        self._batch_limit = batch_limit

    def run_once(self) -> int:
        """Project up to batch_limit pending events, one transaction each; return how many were appended to the stream."""
        connection = self._connection_factory()
        try:
            if connection.autocommit:
                raise ValueError('connection_factory must return a connection with autocommit off')
            rows = connection.execute(
                PENDING_SQL, (self._workspace_id, self._consumer_id, self._consumer_id, self._batch_limit),
            ).fetchall()
            connection.commit()
            appended = 0
            for row in rows:
                try:
                    appended += self._project(connection, row)
                except BaseException:
                    connection.rollback()
                    raise
                connection.commit()
            return appended
        finally:
            connection.close()

    def _project(self, connection: Any, row: tuple[Any, ...]) -> int:
        try:
            event = _event(row)
        except ValueError:
            _LOG.warning('outbox event %s has an unsafe payload; quarantined for %s', row[0], self._consumer_id)
            connection.execute(QUARANTINE_SQL, (self._consumer_id, row[0], row[1], UNSAFE_PAYLOAD, _reference(row)))
            return 0
        processor = PostgresEventProcessor(connection, AppliedRevisions(connection, self._workspace_id, event.aggregate_type))
        return 1 if processor.process(event=event, consumer_id=self._consumer_id) == 'applied' else 0

    async def run_forever(self, stop_event: asyncio.Event, interval_seconds: float) -> None:
        """Wait one interval, then project; repeat until stop_event is set."""
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive')
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                _LOG.exception('operation stream relay cycle failed')


__all__ = ['APPLIED', 'CONSUMER_ID', 'UNSAFE_PAYLOAD', 'AppliedRevisions', 'OperationStreamRelay']
