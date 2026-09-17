"""P3 projection adapters using an active caller-owned PostgreSQL connection."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from controlplane.domain.events import ensure_safe_event_payload


class PostgresOperationStreamRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append(self, *, event: Any, safe_summary: str = "projection", operation_id: str | None = None) -> int:
        _ensure_safe(event.payload, safe_summary)
        return self._connection.execute(
            """WITH ordering_fence AS MATERIALIZED (
                SELECT pg_advisory_xact_lock(
                    hashtextextended('cp_operation_stream:' || %s::text, 0)
                ) AS acquired
            ), allocated_cursor AS MATERIALIZED (
                SELECT nextval(
                    pg_get_serial_sequence('controlplane.cp_operation_stream', 'stream_event_id')::regclass
                ) AS stream_event_id
                FROM ordering_fence
            )
            INSERT INTO controlplane.cp_operation_stream
            (stream_event_id, workspace_id, operation_id, resource_type, resource_id,
             resource_revision, event_kind, occurred_at, recorded_at, summary, correlation_id)
            SELECT allocated_cursor.stream_event_id, %s, %s, %s, %s, %s, %s, %s,
                   CURRENT_TIMESTAMP, %s, %s
            FROM allocated_cursor
            RETURNING stream_event_id""",
            (event.workspace_id, event.workspace_id, operation_id, event.aggregate_type, event.aggregate_id,
             event.aggregate_revision, event.event_name, event.occurred_at, safe_summary,
             event.correlation_id),
        ).fetchone()[0]


class PostgresEventProcessor:
    def __init__(self, connection: Any, projection: Any) -> None:
        self._connection = connection
        self._projection = projection
        self._stream = PostgresOperationStreamRepository(connection)

    def process(self, *, event: Any, consumer_id: str, current_recovery_epoch: int | None = None,
                inject_before_commit: BaseException | None = None) -> str:
        if event.schema_version != 1:
            return self._quarantine(event, consumer_id, "QUARANTINED_UNSUPPORTED_SCHEMA")
        if current_recovery_epoch is not None and event.recovery_epoch is not None and event.recovery_epoch < current_recovery_epoch:
            return self._quarantine(event, consumer_id, "STALE_RECOVERY_EPOCH")
        existing = self._connection.execute(
            "SELECT status FROM controlplane.cp_event_checkpoints WHERE consumer_id=%s AND event_id=%s",
            (consumer_id, event.event_id),
        ).fetchone()
        if existing is not None:
            return "deduplicated"
        self._connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{consumer_id}:{event.workspace_id}:{event.aggregate_type}:{event.aggregate_id}",))
        existing = self._connection.execute(
            "SELECT status FROM controlplane.cp_event_checkpoints WHERE consumer_id=%s AND event_id=%s",
            (consumer_id, event.event_id),
        ).fetchone()
        if existing is not None:
            return "deduplicated"
        current = self._projection.current_revision(consumer_id, event.aggregate_id)
        if current is not None and event.aggregate_revision <= current:
            return self._checkpoint(event, consumer_id, "OUT_OF_ORDER", current)
        if current is not None and event.aggregate_revision > current + 1:
            return self._checkpoint(event, consumer_id, "GAP_BLOCKED", current)
        self._projection.apply(consumer_id, event.aggregate_id, event.aggregate_revision)
        self._stream.append(event=event)
        self._checkpoint(event, consumer_id, "APPLIED", event.aggregate_revision)
        if inject_before_commit is not None:
            raise inject_before_commit
        return "applied"

    def _checkpoint(self, event: Any, consumer_id: str, status: str, current: int | None) -> str:
        self._connection.execute(
            """INSERT INTO controlplane.cp_event_checkpoints
            (consumer_id,event_id,workspace_id,aggregate_type,aggregate_id,aggregate_revision,current_applied_revision,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (consumer_id,event_id) DO NOTHING""",
            (consumer_id, event.event_id, event.workspace_id, event.aggregate_type, event.aggregate_id,
             event.aggregate_revision, current, status),
        )
        return status.lower()

    def _quarantine(self, event: Any, consumer_id: str, reason: str) -> str:
        self._connection.execute(
            """INSERT INTO controlplane.cp_event_quarantine
            (consumer_id,event_id,workspace_id,reason_code,event_envelope,quarantine_status)
            VALUES (%s,%s,%s,%s,%s::jsonb,'OPEN') ON CONFLICT (consumer_id,event_id) DO NOTHING""",
            (consumer_id, event.event_id, event.workspace_id, reason, json.dumps(_event_envelope(event))),
        )
        return "quarantined"


def _ensure_safe(payload: Any, summary: str) -> None:
    if re.search(r"traceback|stack trace", summary, re.IGNORECASE):
        raise ValueError("unsafe operation stream projection")
    ensure_safe_event_payload(payload)


def _event_envelope(event: Any) -> dict[str, Any]:
    """Return the complete, already validated immutable event representation."""
    if hasattr(event, "__dataclass_fields__"):
        return asdict(event)
    return {
        name: getattr(event, name)
        for name in (
            "contract_name", "contract_version", "message_id", "workspace_id", "correlation_id",
            "causation_id", "trace_context", "occurred_at", "actor", "recovery_epoch", "payload",
            "event_id", "event_name", "aggregate_type", "aggregate_id", "aggregate_revision",
            "producer", "schema_version", "sensitivity",
        )
    }
