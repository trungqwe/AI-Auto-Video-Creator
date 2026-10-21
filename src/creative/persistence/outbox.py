"""Transactional outbox of D: writes cp_outbox_events on the connection of the unit of work, so events commit or roll back with the records."""
from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from controlplane.domain.events.contracts import ensure_safe_event_payload
from controlplane.domain.interfaces.outbox import IOutboxWriter
from creative.ports import repositories as ports

SCHEMA_MAJOR = int(ports.SCHEMA_VERSION.split('.')[0])


class PostgresCreativeOutboxWriter(IOutboxWriter):
    def __init__(self, connection_source: Callable[[], Any], workspace_id: str, correlation_id: str, actor: str) -> None:
        self._connection = connection_source
        self._workspace_id = workspace_id
        self._correlation_id = correlation_id
        self._actor = actor

    def append_event(self, event_type: str, aggregate_id: str, payload: Mapping[str, Any], deduplication_id: str) -> str:
        for name, value in (('event_type', event_type), ('aggregate_id', aggregate_id), ('deduplication_id', deduplication_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')
        if not isinstance(payload, Mapping):
            raise ValueError('payload must be a mapping')
        aggregate_type = ports.EVENT_AGGREGATE_TYPES.get(event_type)
        if aggregate_type is None:
            raise ValueError(f'unknown event_type: {event_type}')
        try:
            revision = int(deduplication_id.rsplit(':', 1)[1])
        except (IndexError, ValueError):
            raise ValueError('deduplication_id must end with :<aggregate_revision>') from None
        if revision < 1:
            raise ValueError('aggregate_revision must be >= 1')
        ensure_safe_event_payload(dict(payload))
        connection = self._connection()
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, deduplication_id))
        existing = connection.execute(
            'SELECT workspace_id::text FROM controlplane.cp_outbox_events WHERE event_id = %s::uuid',
            (event_id,),
        ).fetchone()
        if existing is not None:
            if existing[0] != self._workspace_id:
                raise ValueError('deduplication_id belongs to another workspace')
            return event_id
        connection.execute(
            'INSERT INTO controlplane.cp_outbox_events (event_id, workspace_id, contract_name, contract_version, message_id, correlation_id, causation_id, trace_context, occurred_at, actor, recovery_epoch, payload, event_name, aggregate_type, aggregate_id, aggregate_revision, producer, schema_version, sensitivity) '
            'VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, NULL, NULL, %s, %s, NULL, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)',
            (
                event_id, self._workspace_id, ports.CONTRACT_NAME, ports.CONTRACT_VERSION, deduplication_id, self._correlation_id,
                datetime.datetime.now(datetime.timezone.utc), self._actor, json.dumps(dict(payload), ensure_ascii=False),
                event_type, aggregate_type, aggregate_id, revision, ports.PRODUCER, SCHEMA_MAJOR, ports.SENSITIVITY,
            ),
        )
        return event_id