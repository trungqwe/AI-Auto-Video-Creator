"""Module B domain events (CT-EVT-002, CT-EVT-003) built as BINDING-DOMAIN-EVENT-ENVELOPE dicts.

Payloads carry only IDs, revisions and refs; article text never enters an event.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from controlplane.domain.events.contracts import ensure_safe_event_payload

EVENT_NAMES = frozenset({
    'ArticleRevisionAccepted',
    'DuplicateDocumentResolved',
    'EventLinkResolved',
    'EventUpdateAccepted',
})
AGGREGATE_TYPES = frozenset({'Article', 'ArticleRevision', 'CollectedDocumentResolution', 'Event', 'EventUpdate'})
PRODUCER = 'B'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
MAX_VALUE_LENGTH = 256

_TOKEN_RE = re.compile(r'\S{1,%d}' % MAX_VALUE_LENGTH)
_PAYLOAD_KEY_RE = re.compile(r'(?:[a-z][a-z0-9]*_)*(?:id|ids|revision|revisions|ref|refs)')


def _require_token(name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f'invalid {name}')
    return value


def _payload_scalar(value: object) -> str | int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and _TOKEN_RE.fullmatch(value):
        return value
    raise ValueError('payload value must be an id, revision or ref')


def _payload_value(value: object) -> str | int | list[str | int]:
    if isinstance(value, (list, tuple)):
        return [_payload_scalar(item) for item in value]
    return _payload_scalar(value)


def build_event(
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_revision: int,
    payload: Mapping[str, Any],
    recovery_epoch: str,
    event_id: str,
) -> dict[str, Any]:
    """Return a module B DomainEvent dict holding exactly the binding fields; raise ValueError on any violation."""
    if not isinstance(event_name, str) or event_name not in EVENT_NAMES:
        raise ValueError('unsupported module B event_name')
    if not isinstance(aggregate_type, str) or aggregate_type not in AGGREGATE_TYPES:
        raise ValueError('unsupported module B aggregate_type')
    _require_token('aggregate_id', aggregate_id)
    if isinstance(aggregate_revision, bool) or not isinstance(aggregate_revision, int) or aggregate_revision < 1:
        raise ValueError('invalid aggregate_revision')
    _require_token('recovery_epoch', recovery_epoch)
    _require_token('event_id', event_id)
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError('payload must be a non-empty mapping')
    ensure_safe_event_payload(dict(payload))
    safe_payload: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not _PAYLOAD_KEY_RE.fullmatch(key):
            raise ValueError('payload key must name an id, revision or ref')
        safe_payload[key] = _payload_value(value)
    return {
        'event_id': event_id,
        'event_name': event_name,
        'aggregate_type': aggregate_type,
        'aggregate_id': aggregate_id,
        'aggregate_revision': aggregate_revision,
        'producer': PRODUCER,
        'schema_version': SCHEMA_VERSION,
        'recovery_epoch': recovery_epoch,
        'payload': safe_payload,
        'sensitivity': SENSITIVITY,
    }
