"""PostgreSQL outbox writer of E: events go to controlplane.cp_outbox_events on the connection of the unit of work."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping
from typing import Any

from controlplane.domain.events.contracts import DomainEvent, ensure_safe_event_payload
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.infrastructure.db.outbox import PostgresOutboxRepository
from voice.ports.repositories import CONTRACT_NAME, CONTRACT_VERSION, EVENT_AGGREGATE_TYPES, PRODUCER, SCHEMA_VERSION, SENSITIVITY

_SCHEMA_MAJOR = int(SCHEMA_VERSION.split('.')[0])


def _revision_of(deduplication_id: str) -> int:
    tail = deduplication_id.rsplit(':', 1)[-1]
    return int(tail) if tail.isascii() and tail.isdigit() and len(tail) <= 18 and int(tail) >= 1 else 1


def _epoch_of(value: Any) -> int | None:
    return int(value) if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 18 else None


class PostgresVoiceOutboxWriter(IOutboxWriter):
    def __init__(self, session: Any) -> None:
        self._session = session

    def append_event(self, event_type: str, aggregate_id: str, payload: Mapping[str, Any], deduplication_id: str) -> str:
        for name, value in (('event_type', event_type), ('aggregate_id', aggregate_id), ('deduplication_id', deduplication_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')
        if not isinstance(payload, Mapping):
            raise ValueError('payload must be a mapping')
        ensure_safe_event_payload(dict(payload))
        if event_type not in EVENT_AGGREGATE_TYPES:
            raise ValueError(f'unknown event_type: {event_type}')
        connection = self._session.connection
        workspace_id = self._session.require_workspace()
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, deduplication_id))
        if connection.execute('SELECT 1 FROM controlplane.cp_outbox_events WHERE event_id = %s::uuid', (event_id,)).fetchone() is not None:
            return event_id
        event = DomainEvent(
            contract_name=CONTRACT_NAME, contract_version=CONTRACT_VERSION, message_id=event_id,
            workspace_id=workspace_id, correlation_id=self._session.correlation_id, causation_id=None, trace_context=None,
            occurred_at=self._session.now().isoformat(), actor=self._session.actor,
            recovery_epoch=_epoch_of(self._session.recovery_epoch), payload=copy.deepcopy(dict(payload)),
            event_id=event_id, event_name=event_type, aggregate_type=EVENT_AGGREGATE_TYPES[event_type],
            aggregate_id=aggregate_id, aggregate_revision=_revision_of(deduplication_id), producer=PRODUCER,
            schema_version=_SCHEMA_MAJOR, sensitivity=SENSITIVITY,
        )
        PostgresOutboxRepository(connection).enqueue(event)
        return event_id
