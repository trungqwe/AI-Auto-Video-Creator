"""Storage ports of E: append-only OutputRepository, E event builders and DomainEvent envelope check (CT-EVT-002, CT-EVT-003); pure, no I/O, no clock."""

from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from controlplane.domain.events.contracts import DomainEvent, ensure_safe_event_payload
from voice.domain.voice_track import matches_type

KIND_VOICE = 'voice'
KIND_WORD_TIMING = 'word_timing'
PRODUCER = 'E'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
CONTRACT_NAME = 'voice.events'
CONTRACT_VERSION = 1
MAX_VALUE_LENGTH = 256
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
    'ImageSafetyAssessed': 'ImageSafetyAssessment',
    'MediaProcessingCompleted': 'ProcessingOperation',
    'VoiceReady': 'VoiceTrack',
    'WordTimingReady': 'WordTiming',
})

_REF_RE = re.compile(rf'\S{{1,{MAX_VALUE_LENGTH}}}')


class DuplicateOutputError(ValueError):
    pass


class EventEnvelopeError(ValueError):
    def __init__(self, issues: Any) -> None:
        self.issues = tuple(issues)
        super().__init__(', '.join(f'{code}:{field}' for code, field in self.issues))


class ArtifactNotVerifiedError(ValueError):
    def __init__(self, event_name: str) -> None:
        self.code = 'ARTIFACT_NOT_VERIFIED'
        self.event_name = event_name
        super().__init__(f'ARTIFACT_NOT_VERIFIED: {event_name}')


@dataclasses.dataclass(frozen=True)
class StoredOutput:
    kind: str
    key: str
    revision: int
    record: object


@runtime_checkable
class OutputRepository(Protocol):
    def append(self, kind: str, key: str, revision: int, record: object) -> StoredOutput:
        """Append a new revision (append-only, new revision must be latest + 1)."""
        ...

    def latest(self, kind: str, key: str) -> StoredOutput | None:
        """Return latest stored output or None."""
        ...

    def revisions(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        """Return all stored revisions in ascending order."""
        ...


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
        except Exception:
            raise ValueError('occurred_at must be an ISO-8601 timestamp')
        if self.causation_id is not None:
            _text('causation_id', self.causation_id)


def _find_forbidden_keys(obj: Any, forbidden: frozenset[str], found: list[tuple[str, str]]) -> None:
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if isinstance(k, str) and k in forbidden:
                found.append(('forbidden_field', k))
            _find_forbidden_keys(v, forbidden, found)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _find_forbidden_keys(item, forbidden, found)


def envelope_issues(envelope: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(envelope, Mapping):
        return (('wrong_type', '$'),)

    issues: list[tuple[str, str]] = []

    for name, type_name in ENVELOPE_FIELDS.items():
        if name not in envelope:
            issues.append(('missing_required', name))
        else:
            value = envelope[name]
            if not matches_type(value, type_name):
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

    if 'payload' in envelope and isinstance(envelope['payload'], Mapping):
        payload_map = envelope['payload']
        _find_forbidden_keys(payload_map, FORBIDDEN_ENVELOPE_FIELDS, issues)
        try:
            ensure_safe_event_payload(dict(payload_map))
        except ValueError:
            issues.append(('forbidden_field', 'payload'))

    return tuple(dict.fromkeys(issues))


def deduplication_id_for(event: DomainEvent) -> str:
    if not isinstance(event, DomainEvent):
        raise TypeError('event must be a DomainEvent')
    return f'{event.workspace_id}:{event.event_name}:{event.aggregate_id}:{event.aggregate_revision}'


def _ref(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _REF_RE.fullmatch(value):
        raise ValueError(f'invalid {name}')
    return value


def _sha(name: str, value: Any) -> str:
    if not matches_type(value, 'sha256'):
        raise ValueError(f'invalid {name}')
    return value


def _ref_list(name: str, values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)) or len(values) == 0:
        raise ValueError(f'{name} must be a non-empty list or tuple')
    return [_ref(f'{name}[{i}]', v) for i, v in enumerate(values)]


def _sha_list(name: str, values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)) or len(values) == 0:
        raise ValueError(f'{name} must be a non-empty list or tuple')
    return [_sha(f'{name}[{i}]', v) for i, v in enumerate(values)]


def _require_verified(event_name: str, artifact_verified: bool) -> None:
    if artifact_verified is not True:
        raise ArtifactNotVerifiedError(event_name)


def _build(
    event_name: str,
    context: EventContext,
    aggregate_id: str,
    aggregate_revision: int,
    payload: dict[str, Any],
) -> DomainEvent:
    if not isinstance(context, EventContext):
        raise TypeError('context must be an EventContext')
    ensure_safe_event_payload(payload)

    envelope = {
        'event_id': context.event_id,
        'event_name': event_name,
        'aggregate_type': EVENT_AGGREGATE_TYPES[event_name],
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
        aggregate_type=EVENT_AGGREGATE_TYPES[event_name],
        aggregate_id=aggregate_id,
        aggregate_revision=aggregate_revision,
        producer=PRODUCER,
        schema_version=SCHEMA_VERSION,
        sensitivity=SENSITIVITY,
    )


def build_image_safety_assessed(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    assessment_ref: str,
    artifact_ref: str,
    content_sha256: str,
    policy_revision: str,
) -> DomainEvent:
    payload = {
        'assessment_ref': _ref('assessment_ref', assessment_ref),
        'artifact_ref': _ref('artifact_ref', artifact_ref),
        'content_sha256': _sha('content_sha256', content_sha256),
        'policy_revision': _ref('policy_revision', policy_revision),
    }
    return _build('ImageSafetyAssessed', context, aggregate_id, aggregate_revision, payload)


def build_media_processing_completed(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    artifact_verified: bool,
    processing_operation_id: str,
    output_artifact_refs: list[str] | tuple[str, ...],
    output_hashes: list[str] | tuple[str, ...],
    operation_receipt_ref: str,
) -> DomainEvent:
    _require_verified('MediaProcessingCompleted', artifact_verified)
    refs = _ref_list('output_artifact_refs', output_artifact_refs)
    hashes = _sha_list('output_hashes', output_hashes)
    if len(hashes) != len(refs):
        raise ValueError('output_hashes must match output_artifact_refs')
    payload = {
        'processing_operation_id': _ref('processing_operation_id', processing_operation_id),
        'output_artifact_refs': refs,
        'output_hashes': hashes,
        'operation_receipt_ref': _ref('operation_receipt_ref', operation_receipt_ref),
    }
    return _build('MediaProcessingCompleted', context, aggregate_id, aggregate_revision, payload)


def build_voice_ready(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    artifact_verified: bool,
    voice_artifact_ref: str,
    voice_hash: str,
    script_version_id: str,
    receipt_ref: str,
) -> DomainEvent:
    _require_verified('VoiceReady', artifact_verified)
    payload = {
        'voice_artifact_ref': _ref('voice_artifact_ref', voice_artifact_ref),
        'voice_hash': _sha('voice_hash', voice_hash),
        'script_version_id': _ref('script_version_id', script_version_id),
        'receipt_ref': _ref('receipt_ref', receipt_ref),
    }
    return _build('VoiceReady', context, aggregate_id, aggregate_revision, payload)


def build_word_timing_ready(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    artifact_verified: bool,
    timing_artifact_ref: str,
    voice_hash: str,
    script_version_id: str,
    validation_report_ref: str,
) -> DomainEvent:
    _require_verified('WordTimingReady', artifact_verified)
    payload = {
        'timing_artifact_ref': _ref('timing_artifact_ref', timing_artifact_ref),
        'voice_hash': _sha('voice_hash', voice_hash),
        'script_version_id': _ref('script_version_id', script_version_id),
        'validation_report_ref': _ref('validation_report_ref', validation_report_ref),
    }
    return _build('WordTimingReady', context, aggregate_id, aggregate_revision, payload)


__all__ = [
    'ArtifactNotVerifiedError',
    'CONTRACT_NAME',
    'CONTRACT_VERSION',
    'DomainEvent',
    'DuplicateOutputError',
    'ENVELOPE_FIELDS',
    'EVENT_AGGREGATE_TYPES',
    'EventContext',
    'EventEnvelopeError',
    'FORBIDDEN_ENVELOPE_FIELDS',
    'KIND_VOICE',
    'KIND_WORD_TIMING',
    'MAX_VALUE_LENGTH',
    'MODULE_IDS',
    'OutputRepository',
    'PRODUCER',
    'SCHEMA_VERSION',
    'SENSITIVITY',
    'StoredOutput',
    'build_image_safety_assessed',
    'build_media_processing_completed',
    'build_voice_ready',
    'build_word_timing_ready',
    'deduplication_id_for',
    'ensure_safe_event_payload',
    'envelope_issues',
]
