"""P3 outbox adapters using only an active caller-owned connection."""
from __future__ import annotations

from typing import Any


class PostgresOutboxRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def enqueue(self, event: Any) -> str:
        self._connection.execute(
            """INSERT INTO controlplane.cp_outbox_events
            (event_id, workspace_id, contract_name, contract_version, message_id,
             correlation_id, causation_id, trace_context, occurred_at, actor,
             recovery_epoch, payload, event_name, aggregate_type, aggregate_id,
             aggregate_revision, producer, schema_version, sensitivity, recorded_at)
            VALUES (%(event_id)s, %(workspace_id)s, %(contract_name)s, %(contract_version)s,
             %(message_id)s, %(correlation_id)s, %(causation_id)s, %(trace_context)s,
             %(occurred_at)s, %(actor)s, %(recovery_epoch)s, %(payload)s::jsonb,
             %(event_name)s, %(aggregate_type)s, %(aggregate_id)s, %(aggregate_revision)s,
             %(producer)s, %(schema_version)s, %(sensitivity)s, CURRENT_TIMESTAMP)""",
            {
                "event_id": event.event_id, "workspace_id": event.workspace_id,
                "contract_name": event.contract_name, "contract_version": event.contract_version,
                "message_id": event.message_id, "correlation_id": event.correlation_id,
                "causation_id": event.causation_id, "trace_context": event.trace_context,
                "occurred_at": event.occurred_at, "actor": event.actor,
                "recovery_epoch": event.recovery_epoch, "payload": __import__("json").dumps(event.payload),
                "event_name": event.event_name, "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id, "aggregate_revision": event.aggregate_revision,
                "producer": event.producer, "schema_version": event.schema_version,
                "sensitivity": event.sensitivity,
            },
        )
        return event.event_id


class PostgresOutboxPublisher:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def dispatch(self, *, event_id: str, crash_before_ack: bool, delivery_observer: list[str]) -> str:
        row = self._connection.execute(
            "SELECT event_id::text FROM controlplane.cp_outbox_events WHERE event_id=%s AND published=false",
            (event_id,),
        ).fetchone()
        if row is None:
            return "already_published"
        delivery_observer.append(row[0])
        if crash_before_ack:
            return "delivered_unacknowledged"
        self._connection.execute(
            "UPDATE controlplane.cp_outbox_events SET published=true, published_at=CURRENT_TIMESTAMP WHERE event_id=%s",
            (event_id,),
        )
        return "published"
