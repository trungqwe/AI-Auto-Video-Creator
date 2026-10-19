"""G-13: dựng event envelope của G (CT-EVT-002/003, BINDING-DOMAIN-EVENT-ENVELOPE).

Pure application: không I/O, không đồng hồ, không sinh ngẫu nhiên. Payload chỉ mang ID và revision.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from controlplane.domain.events.contracts import ensure_safe_event_payload

PRODUCER = 'G'
SCHEMA_VERSION = '1'
SENSITIVITY = 'internal'
MAX_VALUE_LENGTH = 256
AGGREGATE_TYPES = {
    'BatchStarted': 'Batch',
    'JobAllocated': 'VideoJob',
    'StageStateChanged': 'StageRun',
    'JobWaiting': 'VideoJob',
    'JobFailed': 'VideoJob',
    'VideoCompleted': 'VideoJob',
    'BatchTargetReached': 'Batch',
    'BatchExhausted': 'Batch',
}
EVENT_NAMES = frozenset(AGGREGATE_TYPES)
FORBIDDEN_FIELDS = frozenset({'secret_value', 'raw_oauth_response', 'stack_trace', 'blob'})
REQUIRED_PAYLOAD_FIELDS = {'VideoCompleted': ('completion_id',)}

_PAYLOAD_KEY_RE = re.compile(r'(?:[a-z][a-z0-9]*_)*(?:id|ids|revision|revisions)')


def _is_token(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= MAX_VALUE_LENGTH and not any(ch.isspace() for ch in value)


def _require_token(name: str, value: object) -> str:
    if not _is_token(value):
        raise ValueError(f'invalid {name}')
    return value


def _payload_scalar(value: object) -> str | int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if _is_token(value):
        return value
    raise ValueError('payload value must be an id or revision')


def _payload_value(value: object) -> str | int | list[str | int]:
    if isinstance(value, (list, tuple)):
        return [_payload_scalar(item) for item in value]
    return _payload_scalar(value)


def build_g_event(event_name: str, aggregate_id: str, aggregate_revision: int, recovery_epoch: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a module G DomainEvent dict holding exactly the binding fields; raise ValueError on any violation."""
    if not isinstance(event_name, str) or event_name not in EVENT_NAMES:
        raise ValueError('unsupported module G event_name')
    _require_token('aggregate_id', aggregate_id)
    if isinstance(aggregate_revision, bool) or not isinstance(aggregate_revision, int) or aggregate_revision < 0:
        raise ValueError('invalid aggregate_revision')
    _require_token('recovery_epoch', recovery_epoch)
    if not isinstance(payload, Mapping):
        raise ValueError('payload must be a mapping')
    if any(key in FORBIDDEN_FIELDS for key in payload):
        raise ValueError('forbidden payload field')
    ensure_safe_event_payload(dict(payload))
    safe_payload: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not _PAYLOAD_KEY_RE.fullmatch(key):
            raise ValueError('payload key must name an id or revision')
        safe_payload[key] = _payload_value(value)
    for field in REQUIRED_PAYLOAD_FIELDS.get(event_name, ()):
        if not isinstance(safe_payload.get(field), str):
            raise ValueError(f'payload requires {field}')
    return {
        'event_id': f'{event_name}:{aggregate_id}:{aggregate_revision}',
        'event_name': event_name,
        'aggregate_type': AGGREGATE_TYPES[event_name],
        'aggregate_id': aggregate_id,
        'aggregate_revision': aggregate_revision,
        'producer': PRODUCER,
        'schema_version': SCHEMA_VERSION,
        'recovery_epoch': recovery_epoch,
        'payload': safe_payload,
        'sensitivity': SENSITIVITY,
    }


__all__ = ['AGGREGATE_TYPES', 'EVENT_NAMES', 'FORBIDDEN_FIELDS', 'MAX_VALUE_LENGTH', 'PRODUCER', 'REQUIRED_PAYLOAD_FIELDS', 'SCHEMA_VERSION', 'SENSITIVITY', 'build_g_event']
