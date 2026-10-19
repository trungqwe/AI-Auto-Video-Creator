"""Storage ports of D: append-only repositories, receipt store, D event builders and DomainEvent envelope check (CT-EVT-002, CT-EVT-003); pure, no I/O, no clock."""

from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from controlplane.domain.events.contracts import DomainEvent, ensure_safe_event_payload
from creative.domain.analysis import ContentAnalysis
from creative.domain.angles import StoryAngleSet
from creative.domain.invocation import AIInvocationRecord
from creative.domain.output_metadata import OutputMetadata
from creative.domain.production_plan import ProductionPlan
from creative.domain.script import ScriptVersion
from creative.domain.snapshot import ProductionSnapshot, matches_type
from creative.domain.variant import VariantValidationResult

KIND_ANALYSIS = 'analysis'
KIND_ANGLE_SET = 'angle_set'
KIND_SCRIPT = 'script'
KIND_PLAN = 'plan'
KIND_VARIANT_VALIDATION = 'variant_validation'
KIND_OUTPUT_METADATA = 'output_metadata'
KIND_INVOCATION = 'invocation_record'

RECORD_TYPES = MappingProxyType({
    KIND_ANALYSIS: ContentAnalysis,
    KIND_ANGLE_SET: StoryAngleSet,
    KIND_SCRIPT: ScriptVersion,
    KIND_PLAN: ProductionPlan,
    KIND_VARIANT_VALIDATION: VariantValidationResult,
    KIND_OUTPUT_METADATA: OutputMetadata,
    KIND_INVOCATION: AIInvocationRecord,
})

UNIQUE_ID_ATTRS = MappingProxyType({
    KIND_ANGLE_SET: 'set_id',
    KIND_SCRIPT: 'script_version_id',
    KIND_PLAN: 'production_plan_id',
})

PRODUCER = 'D'
SCHEMA_VERSION = '1.0.0'
SENSITIVITY = 'internal'
CONTRACT_NAME = 'creative.events'
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
    'ProductionSnapshotCommitted': 'ProductionSnapshot',
    'StoryAnglesGenerated': 'StoryAngleSet',
    'ScriptVersionCreated': 'ScriptVersion',
    'ProductionPlanCreated': 'ProductionPlan',
    'VariantValidated': 'VariantValidation',
    'OutputMetadataCreated': 'OutputMetadata',
})


class DuplicateRecordError(ValueError):
    pass


class DuplicateSnapshotError(DuplicateRecordError):
    pass


class DuplicateReceiptError(DuplicateRecordError):
    pass


class EventEnvelopeError(ValueError):
    def __init__(self, issues: Any) -> None:
        self.issues = tuple(issues)
        super().__init__(', '.join(f'{code}:{field}' for code, field in self.issues))


@dataclasses.dataclass(frozen=True)
class StoredRecord:
    kind: str
    key: str
    revision: int
    record: object


@dataclasses.dataclass(frozen=True)
class CommandReceipt:
    workspace_id: str
    idempotency_key: str
    request_hash: str
    aggregate_ref: str
    aggregate_revision: int

    def __post_init__(self) -> None:
        for name, value in (
            ('workspace_id', self.workspace_id),
            ('idempotency_key', self.idempotency_key),
            ('request_hash', self.request_hash),
            ('aggregate_ref', self.aggregate_ref),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')
        if type(self.aggregate_revision) is not int or self.aggregate_revision < 1:
            raise ValueError('aggregate_revision must be an integer >= 1')


@runtime_checkable
class SnapshotRepository(Protocol):
    def add(self, snapshot: ProductionSnapshot) -> None:
        """Add a production snapshot."""
        ...

    def get(self, snapshot_id: str) -> ProductionSnapshot | None:
        """Get snapshot by ID."""
        ...

    def list_snapshots(self) -> tuple[ProductionSnapshot, ...]:
        """List all snapshots."""
        ...


@runtime_checkable
class AppendOnlyRepository(Protocol):
    def append(self, key: str, revision: int, record: object) -> StoredRecord:
        """Append a new revision (append-only, new revision must be latest + 1)."""
        ...

    def latest(self, key: str) -> StoredRecord | None:
        """Return latest stored record or None."""
        ...

    def revisions(self, key: str) -> tuple[StoredRecord, ...]:
        """Return all stored revisions in ascending order."""
        ...


@runtime_checkable
class AnalysisRepository(AppendOnlyRepository, Protocol):
    """Repository for content analysis."""


@runtime_checkable
class AngleSetRepository(AppendOnlyRepository, Protocol):
    """Repository for story angle sets."""


@runtime_checkable
class ScriptRepository(AppendOnlyRepository, Protocol):
    """Repository for script versions."""


@runtime_checkable
class PlanRepository(AppendOnlyRepository, Protocol):
    """Repository for production plans."""


@runtime_checkable
class VariantValidationRepository(AppendOnlyRepository, Protocol):
    """Repository for variant validation results."""


@runtime_checkable
class OutputMetadataRepository(AppendOnlyRepository, Protocol):
    """Repository for output metadata."""


@runtime_checkable
class InvocationRecordRepository(AppendOnlyRepository, Protocol):
    """Repository for AI invocation records."""


@runtime_checkable
class ReceiptStore(Protocol):
    def get(self, workspace_id: str, idempotency_key: str) -> CommandReceipt | None:
        """Get command receipt by workspace_id and idempotency_key."""
        ...

    def put(self, receipt: CommandReceipt) -> None:
        """Store command receipt."""
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


_REF_RE = re.compile(rf'\S{{1,{MAX_VALUE_LENGTH}}}')


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


def build_production_snapshot_committed(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    snapshot: ProductionSnapshot,
) -> DomainEvent:
    if not isinstance(snapshot, ProductionSnapshot):
        raise TypeError('snapshot must be a ProductionSnapshot')
    payload = {
        'snapshot_id': _ref('snapshot_id', snapshot.snapshot_id),
        'source_set_fingerprint': _sha('source_set_fingerprint', snapshot.source_set_fingerprint),
        'configuration_bundle_fingerprint': _sha('configuration_bundle_fingerprint', snapshot.configuration_bundle_fingerprint),
    }
    return _build('ProductionSnapshotCommitted', context, aggregate_id, aggregate_revision, payload)


def build_story_angles_generated(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    angle_set: StoryAngleSet,
) -> DomainEvent:
    if not isinstance(angle_set, StoryAngleSet):
        raise TypeError('angle_set must be a StoryAngleSet')
    payload = {
        'set_id': _ref('set_id', angle_set.set_id),
        'analysis_id': _ref('analysis_id', angle_set.analysis_id),
        'analysis_revision': angle_set.analysis_revision,
        'angle_ids': _ref_list('angle_ids', [a.angle_id for a in angle_set.angles]),
        'variation_policy_revision': _ref('variation_policy_revision', angle_set.variation_policy_revision),
    }
    return _build('StoryAnglesGenerated', context, aggregate_id, aggregate_revision, payload)


def build_script_version_created(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    script: ScriptVersion,
) -> DomainEvent:
    if not isinstance(script, ScriptVersion):
        raise TypeError('script must be a ScriptVersion')
    payload = {
        'script_version_id': _ref('script_version_id', script.script_version_id),
        'script_fingerprint': _sha('script_fingerprint', script.script_fingerprint),
    }
    return _build('ScriptVersionCreated', context, aggregate_id, aggregate_revision, payload)


def build_production_plan_created(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    plan: ProductionPlan,
) -> DomainEvent:
    if not isinstance(plan, ProductionPlan):
        raise TypeError('plan must be a ProductionPlan')
    payload = {
        'production_plan_id': _ref('production_plan_id', plan.production_plan_id),
        'script_version_id': _ref('script_version_id', plan.script_version_id),
        'plan_fingerprint': _sha('plan_fingerprint', plan.plan_fingerprint),
        'selection_fingerprint': _sha('selection_fingerprint', plan.selection_fingerprint),
    }
    return _build('ProductionPlanCreated', context, aggregate_id, aggregate_revision, payload)


def build_variant_validated(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    result: VariantValidationResult,
) -> DomainEvent:
    if not isinstance(result, VariantValidationResult):
        raise TypeError('result must be a VariantValidationResult')
    if result.valid is not True:
        raise ValueError('variant_not_valid')
    payload = {
        'validation_hash': _sha('validation_hash', result.validation_hash),
        'registry_revision': result.registry_revision,
        'phase': _ref('phase', result.phase),
        'variation_policy_revision': _ref('variation_policy_revision', result.variation_policy_revision),
    }
    return _build('VariantValidated', context, aggregate_id, aggregate_revision, payload)


def build_output_metadata_created(
    context: EventContext,
    *,
    aggregate_id: str,
    aggregate_revision: int,
    metadata: OutputMetadata,
) -> DomainEvent:
    if not isinstance(metadata, OutputMetadata):
        raise TypeError('metadata must be an OutputMetadata')
    payload = {
        'source_job_ref': _ref('source_job_ref', metadata.source_job_ref),
        'metadata_revision': metadata.metadata_revision,
        'source_output_refs': _ref_list('source_output_refs', list(metadata.source_output_refs)),
    }
    return _build('OutputMetadataCreated', context, aggregate_id, aggregate_revision, payload)


__all__ = [
    'AnalysisRepository',
    'AngleSetRepository',
    'AppendOnlyRepository',
    'CONTRACT_NAME',
    'CONTRACT_VERSION',
    'CommandReceipt',
    'DomainEvent',
    'DuplicateReceiptError',
    'DuplicateRecordError',
    'DuplicateSnapshotError',
    'ENVELOPE_FIELDS',
    'EVENT_AGGREGATE_TYPES',
    'EventContext',
    'EventEnvelopeError',
    'FORBIDDEN_ENVELOPE_FIELDS',
    'InvocationRecordRepository',
    'KIND_ANALYSIS',
    'KIND_ANGLE_SET',
    'KIND_INVOCATION',
    'KIND_OUTPUT_METADATA',
    'KIND_PLAN',
    'KIND_SCRIPT',
    'KIND_VARIANT_VALIDATION',
    'MAX_VALUE_LENGTH',
    'MODULE_IDS',
    'OutputMetadataRepository',
    'PRODUCER',
    'PlanRepository',
    'RECORD_TYPES',
    'ReceiptStore',
    'SCHEMA_VERSION',
    'SENSITIVITY',
    'ScriptRepository',
    'SnapshotRepository',
    'StoredRecord',
    'UNIQUE_ID_ATTRS',
    'VariantValidationRepository',
    'build_output_metadata_created',
    'build_production_plan_created',
    'build_production_snapshot_committed',
    'build_script_version_created',
    'build_story_angles_generated',
    'build_variant_validated',
    'deduplication_id_for',
    'ensure_safe_event_payload',
    'envelope_issues',
]
