"""F-16: events of F (RenderCompleted, OutputQualityChecked) and the DomainEvent envelope check (CT-EVT-002, CT-EVT-003, CONV-F-10); pure, no I/O, no clock.

Both builders return controlplane DomainEvent after ensure_safe_event_payload. A payload holds only refs, hashes, revisions and a gate summary: never video bytes, argv, absolute paths, error text, warnings or secrets. RenderCompleted needs a SUCCEEDED attempt (a technical fact, not a finished video); OutputQualityChecked is emitted for a passed and for a failed QualityReport.

coveredIds: CT-EVT-002, CT-EVT-003, TST-SEC-INV-012
"""
from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from controlplane.domain.events.contracts import DomainEvent, ensure_safe_event_payload
from controlplane.domain.statemachine import OperationState
from render.domain.quality_report import QualityReport
from render.domain.render_attempt import RenderAttempt

PRODUCER = 'F'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
CONTRACT_NAME = 'render.events'
CONTRACT_VERSION = 1
ATTEMPT_NOT_SUCCEEDED = 'ATTEMPT_NOT_SUCCEEDED'
MODULE_IDS = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J')

ENVELOPE_FIELDS = MappingProxyType({
    'event_id': 'string',
    'event_name': 'string',
    'aggregate_type': 'string',
    'aggregate_id': 'string',
    'aggregate_revision': 'integer',
    'producer': 'string',
    'schema_version': 'string',
    'recovery_epoch': 'string',
    'payload': 'object',
    'sensitivity': 'string',
})

FORBIDDEN_ENVELOPE_FIELDS = frozenset({'secret_value', 'raw_oauth_response', 'stack_trace', 'blob'})

EVENT_AGGREGATE_TYPES = MappingProxyType({
    'RenderCompleted': 'RenderAttempt',
    'OutputQualityChecked': 'QualityReport',
})

_REF_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}')
_DRIVE_RE = re.compile(r'[A-Za-z]:')


class EventEnvelopeError(ValueError):
    def __init__(self, issues: Any) -> None:
        self.issues = tuple(issues)
        super().__init__(', '.join(f'{code}:{field}' for code, field in self.issues))


class AttemptNotSucceededError(ValueError):
    def __init__(self, event_name: str, state: str) -> None:
        self.code = ATTEMPT_NOT_SUCCEEDED
        self.event_name = event_name
        self.state = state
        super().__init__(f'{ATTEMPT_NOT_SUCCEEDED}: {event_name} needs a SUCCEEDED attempt, got {state}')


def _text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


@dataclasses.dataclass(frozen=True, kw_only=True)
class EventContext:
    workspace_id: str
    correlation_id: str
    actor: str
    occurred_at: str
    recovery_epoch: str
    event_id: str
    message_id: str
    causation_id: str | None = None

    def __post_init__(self) -> None:
        _text('workspace_id', self.workspace_id)
        _text('correlation_id', self.correlation_id)
        _text('actor', self.actor)
        _text('message_id', self.message_id)
        if not isinstance(self.occurred_at, str):
            raise ValueError('occurred_at must be an ISO-8601 timestamp')
        try:
            datetime.datetime.fromisoformat(self.occurred_at)
        except ValueError:
            raise ValueError('occurred_at must be an ISO-8601 timestamp') from None
        if self.causation_id is not None:
            _text('causation_id', self.causation_id)


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, Mapping)
    return False


def _find_forbidden_keys(obj: Any, found: list[tuple[str, str]]) -> None:
    if isinstance(obj, Mapping):
        for key, child in obj.items():
            if isinstance(key, str) and key in FORBIDDEN_ENVELOPE_FIELDS:
                found.append(('forbidden_field', key))
            _find_forbidden_keys(child, found)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _find_forbidden_keys(item, found)


def envelope_issues(envelope: object) -> tuple[tuple[str, str], ...]:
    """Check an envelope against the domain-event-envelope binding; returns (code, field) pairs, () when valid."""
    if not isinstance(envelope, Mapping):
        return (('wrong_type', '$'),)
    issues: list[tuple[str, str]] = []
    for name, type_name in ENVELOPE_FIELDS.items():
        if name not in envelope:
            issues.append(('missing_required', name))
            continue
        value = envelope[name]
        if not _matches_type(value, type_name):
            issues.append(('wrong_type', name))
        elif type_name == 'string' and value.strip() == '':
            issues.append(('constraint_violation', name))
        elif name == 'aggregate_revision' and value < 1:
            issues.append(('constraint_violation', name))
        elif name == 'producer' and value not in MODULE_IDS:
            issues.append(('enum_violation', 'producer'))
    for key in envelope:
        if isinstance(key, str) and key in FORBIDDEN_ENVELOPE_FIELDS:
            issues.append(('forbidden_field', key))
    payload = envelope.get('payload')
    if isinstance(payload, Mapping):
        _find_forbidden_keys(payload, issues)
        try:
            ensure_safe_event_payload(dict(payload))
        except ValueError:
            issues.append(('forbidden_field', 'payload'))
    return tuple(dict.fromkeys(issues))


def deduplication_id_for(event: DomainEvent) -> str:
    """Stable outbox deduplication id: workspace, event name, aggregate id and aggregate revision."""
    if not isinstance(event, DomainEvent):
        raise TypeError('event must be a DomainEvent')
    return f'{event.workspace_id}:{event.event_name}:{event.aggregate_id}:{event.aggregate_revision}'


def _ref(name: str, value: Any) -> str:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None or '..' in value or '//' in value or _DRIVE_RE.match(value):
        raise ValueError(f'invalid {name}')
    return value


def _require_succeeded(event_name: str, attempt: object) -> RenderAttempt:
    if not isinstance(attempt, RenderAttempt):
        raise TypeError('attempt must be a RenderAttempt')
    if attempt.receipt_state is not OperationState.SUCCEEDED:
        raise AttemptNotSucceededError(event_name, attempt.receipt_state.value)
    return attempt


def _build(event_name: str, context: EventContext, aggregate_id: str, aggregate_revision: int, payload: dict[str, Any]) -> DomainEvent:
    if not isinstance(context, EventContext):
        raise TypeError('context must be an EventContext')
    ensure_safe_event_payload(payload)
    aggregate_type = EVENT_AGGREGATE_TYPES[event_name]
    envelope = {
        'event_id': context.event_id,
        'event_name': event_name,
        'aggregate_type': aggregate_type,
        'aggregate_id': aggregate_id,
        'aggregate_revision': aggregate_revision,
        'producer': PRODUCER,
        'schema_version': SCHEMA_VERSION,
        'recovery_epoch': context.recovery_epoch,
        'payload': payload,
        'sensitivity': SENSITIVITY,
    }
    issues = envelope_issues(envelope)
    if issues:
        raise EventEnvelopeError(issues)
    return DomainEvent(
        contract_name=CONTRACT_NAME,
        contract_version=CONTRACT_VERSION,
        message_id=context.message_id,
        workspace_id=context.workspace_id,
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        trace_context=None,
        occurred_at=context.occurred_at,
        actor=context.actor,
        recovery_epoch=context.recovery_epoch,
        payload=payload,
        event_id=context.event_id,
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_revision=aggregate_revision,
        producer=PRODUCER,
        schema_version=SCHEMA_VERSION,
        sensitivity=SENSITIVITY,
    )


def build_render_completed(context: EventContext, *, attempt: RenderAttempt) -> DomainEvent:
    """RenderCompleted for a SUCCEEDED attempt only; aggregate_revision is the attempt revision."""
    done = _require_succeeded('RenderCompleted', attempt)
    payload = {
        'render_attempt_id': _ref('render_attempt_id', done.render_attempt_id),
        'package_fingerprint': _ref('package_fingerprint', done.package_fingerprint),
        'output_artifact_ref': _ref('output_artifact_ref', done.output_artifact_ref),
        'receipt_ref': _ref('receipt_ref', done.receipt_ref),
        'revision': done.revision,
    }
    return _build('RenderCompleted', context, done.render_attempt_id, done.revision, payload)


def build_output_quality_checked(context: EventContext, *, attempt: RenderAttempt, report: QualityReport, aggregate_revision: int) -> DomainEvent:
    """OutputQualityChecked for a SUCCEEDED attempt; emitted whether the report passed or failed."""
    done = _require_succeeded('OutputQualityChecked', attempt)
    if not isinstance(report, QualityReport):
        raise TypeError('report must be a QualityReport')
    payload: dict[str, Any] = {
        'quality_report_ref': _ref('quality_report_ref', report.report_id),
        'render_attempt_id': _ref('render_attempt_id', done.render_attempt_id),
        'output_artifact_ref': _ref('output_artifact_ref', done.output_artifact_ref),
        'passed': report.passed,
        'blocking_gates': [gate.value for gate in report.blocking_gates],
        'gate_statuses': {item.gate.value: item.status.value for item in report.gates},
    }
    if report.policy_revision is not None:
        payload['policy_revision'] = _ref('policy_revision', report.policy_revision)
    return _build('OutputQualityChecked', context, report.report_id, aggregate_revision, payload)


__all__ = [
    'ATTEMPT_NOT_SUCCEEDED',
    'AttemptNotSucceededError',
    'CONTRACT_NAME',
    'CONTRACT_VERSION',
    'DomainEvent',
    'ENVELOPE_FIELDS',
    'EVENT_AGGREGATE_TYPES',
    'EventContext',
    'EventEnvelopeError',
    'FORBIDDEN_ENVELOPE_FIELDS',
    'MODULE_IDS',
    'PRODUCER',
    'SCHEMA_VERSION',
    'SENSITIVITY',
    'build_output_quality_checked',
    'build_render_completed',
    'deduplication_id_for',
    'ensure_safe_event_payload',
    'envelope_issues',
]
