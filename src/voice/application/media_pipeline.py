"""E-17: media processing commands (CT-PROC-003..CT-PROC-007, CT-AUD-001, CT-STATE-011) over injected ports; no I/O, no clock, no subprocess.
Each command is one UnitOfWork with the new output, the receipt and the outbox event; receipts are terminal, so a replay returns the stored receipt and never calls a tool again.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.events.contracts import DomainEvent
from controlplane.domain.interfaces.outbox import IOutboxWriter
from voice.domain.audio_bed import (
    AudioBedError,
    AudioBedRejected,
    AudioBedRequest,
    LoudnessReport,
    PreparedRendition,
    build_audio_bed_result,
)
from voice.domain.image_safety import (
    IMAGE_KIND,
    INPUT_NOT_READY,
    ImageSafetyAssessment,
    ImageSafetyError,
    ImageSafetyPolicy,
    SafetyOutcome,
    original_usable_for,
)
from voice.domain.image_safety import assess_image_safety as domain_assess_image_safety
from voice.domain.image_transform import (
    TransformOutput,
    TransformPolicy,
    TransformPort,
    TransformRegion,
    TransformRequest,
    TransformSkipped,
    TransformStatus,
)
from voice.domain.image_transform import transform_sensitive_image as domain_transform_sensitive_image
from voice.domain.normalize import (
    SAFETY_TRANSFORM_NOT_APPLICABLE,
    FocusRegion,
    NormalizeSpec,
    plan_rendition,
    verify_tool_outcome,
)
from voice.domain.probe import Readability, parse_probe_output
from voice.domain.processing import (
    CONSTRAINT_VIOLATION,
    MISSING_REQUIRED,
    WRONG_TYPE,
    ArtifactRef,
    Disposition,
    ProcessingContractError,
)
from voice.ports.media_tool import MediaToolPort, ToolOutcome
from voice.ports.probe import ProbePort
from voice.ports.repositories import (
    EventContext,
    OutputRepository,
    build_image_safety_assessed,
    build_media_processing_completed,
    deduplication_id_for,
)

OP_PROBE_MEDIA = 'ProbeMedia'
OP_ASSESS_IMAGE_SAFETY = 'AssessImageSafety'
OP_TRANSFORM_SENSITIVE_IMAGE = 'TransformSensitiveImage'
OP_NORMALIZE_MEDIA = 'NormalizeMedia'
OP_PREPARE_AUDIO_BED = 'PrepareAudioBed'

KIND_PROBE_REPORT = 'probe_report'
KIND_IMAGE_SAFETY = 'image_safety_assessment'
KIND_PROCESSED_MEDIA = 'processed_media'
KIND_AUDIO_BED = 'audio_bed_result'
KIND_RECEIPT = 'receipt'
KIND_RECEIPT_BY_REQUEST = 'receipt_by_request'
RECORD_KINDS = (KIND_PROBE_REPORT, KIND_IMAGE_SAFETY, KIND_PROCESSED_MEDIA, KIND_AUDIO_BED)

ERR_OUTPUT_NOT_VERIFIED = 'output_not_verified'
ERR_OUTPUT_HASH_MISMATCH = 'output_hash_mismatch'
ERR_OUTPUT_NOT_READABLE = 'output_not_readable'
ERR_OUTPUT_REF_MISMATCH = 'output_ref_mismatch'
ERR_OUTPUT_REPLACES_ORIGINAL = 'output_replaces_original'
ERR_OUTPUT_HASHES_MISMATCH = 'output_hashes_mismatch'
ERR_TOOL_BAD_RESULT = 'tool_bad_result'
ERR_RECEIPT_COMMIT_FAILED = 'receipt_commit_failed'

_SHA256_RE = re.compile(r'[0-9a-f]{64}')


class IdempotencyConflictError(ValueError):
    """Same operation_key reused with a different request."""

    def __init__(self, operation_key: str) -> None:
        self.code = 'IDEMPOTENCY_CONFLICT'
        self.operation_key = operation_key
        super().__init__(f'{self.code}: {operation_key}')


class RetryNotAllowedError(RuntimeError):
    """The same request already has an outcome_unknown receipt; a direct retry could repeat the side effect."""

    def __init__(self, operation_key: str) -> None:
        self.code = 'OUTCOME_UNKNOWN_RETRY_NOT_ALLOWED'
        self.operation_key = operation_key
        super().__init__(f'{self.code}: {operation_key}')


@dataclasses.dataclass(frozen=True)
class OperationReceipt:
    operation_key: str
    operation: str
    request_fingerprint: str
    disposition: Disposition
    outcome: str | None = None
    output_refs: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def receipt_ref(self) -> str:
        return f'receipt:{self.operation_key}'


@dataclasses.dataclass(frozen=True)
class VerifiedOutput:
    content_sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.content_sha256, str) or not _SHA256_RE.fullmatch(self.content_sha256):
            raise ProcessingContractError(WRONG_TYPE, 'content_sha256')
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise ProcessingContractError(WRONG_TYPE, 'size_bytes')
        if self.size_bytes < 0:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'size_bytes')


@dataclasses.dataclass(frozen=True)
class ProcessedRendition:
    output_ref: str
    output_sha256: str
    size_bytes: int
    input_ref: ArtifactRef
    lineage_refs: tuple[str, ...]
    media_kind: str
    spec_fingerprint: str
    plan_fingerprint: str


@dataclasses.dataclass(frozen=True)
class CommandResult:
    receipt: OperationReceipt
    record: object | None = None
    replayed: bool = False


@dataclasses.dataclass(frozen=True)
class AudioBedOutcome:
    status: Disposition
    renditions: tuple[PreparedRendition, ...] = ()
    output_hashes: tuple[str, ...] = ()
    loudness_report: LoudnessReport | None = None
    provenance: Mapping = dataclasses.field(default_factory=dict)
    risk_metadata: Mapping = dataclasses.field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error: str | None = None


@runtime_checkable
class AudioBedPort(Protocol):
    """E-local port; the real binding opens in CONV-E-07."""

    def prepare(self, request: AudioBedRequest) -> AudioBedOutcome:
        ...


class MediaUnitOfWork(Protocol):
    """Structural type of the in-memory UnitOfWork of E-15; the application layer never imports adapters."""

    outputs: OutputRepository
    outbox: IOutboxWriter

    def commit(self) -> None:
        ...

    def __enter__(self) -> MediaUnitOfWork:
        ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> object:
        ...


@dataclasses.dataclass(frozen=True)
class ImageBatchItem:
    item_id: str
    artifact_ref: ArtifactRef
    detector: object
    regions: tuple = ()
    user_visual_hook: bool = False


@dataclasses.dataclass(frozen=True)
class ImageBatchResult:
    item_id: str
    outcome: SafetyOutcome
    original_ref: ArtifactRef
    processed_ref: ArtifactRef | None
    usable_ref: ArtifactRef | None
    warnings: tuple[str, ...]
    receipt_refs: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class _Decision:
    disposition: Disposition
    outcome: str | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()
    outputs: tuple[tuple[str, object], ...] = ()
    output_refs: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    event_factory: Callable[[], DomainEvent] | None = None
    side_effect_done: bool = False


class _TrackedTransformPort:
    """Notes that the port returned, i.e. the side effect happened."""

    def __init__(self, port: TransformPort) -> None:
        self._port = port
        self.completed = False

    def transform(self, request: TransformRequest) -> TransformOutput:
        output = self._port.transform(request)
        self.completed = True
        return output


def _check_key(operation_key: object) -> str:
    if not isinstance(operation_key, str) or not 1 <= len(operation_key) <= 200:
        raise ValueError('invalid operation_key')
    if any(ch.isspace() for ch in operation_key):
        raise ValueError('invalid operation_key')
    return operation_key


def _check_context(context: object) -> EventContext:
    if not isinstance(context, EventContext):
        raise TypeError('context must be an EventContext')
    return context


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _ref_dict(ref: ArtifactRef) -> dict[str, str]:
    return {'ref': ref.ref, 'content_sha256': ref.content_sha256}


def _verify(outputs: Sequence[tuple[str, str]], verified: Mapping[str, VerifiedOutput] | None) -> str | None:
    """Returns an error code unless I verified every (ref, sha256) pair; no evidence means not ready."""
    for ref, sha in outputs:
        item = None if verified is None else verified.get(ref)
        if not isinstance(item, VerifiedOutput):
            return ERR_OUTPUT_NOT_VERIFIED
        if item.content_sha256 != sha:
            return ERR_OUTPUT_HASH_MISMATCH
    return None


def _completed_event(context: EventContext, operation_key: str, refs: list[str], hashes: list[str]) -> DomainEvent:
    return build_media_processing_completed(
        context,
        aggregate_id=operation_key,
        aggregate_revision=1,
        artifact_verified=True,
        processing_operation_id=operation_key,
        output_artifact_refs=refs,
        output_hashes=hashes,
        operation_receipt_ref=f'receipt:{operation_key}',
    )


def _append_receipt(uow: MediaUnitOfWork, receipt: OperationReceipt) -> None:
    uow.outputs.append(KIND_RECEIPT, receipt.operation_key, 1, receipt)
    latest = uow.outputs.latest(KIND_RECEIPT_BY_REQUEST, receipt.request_fingerprint)
    revision = 1 if latest is None else latest.revision + 1
    uow.outputs.append(KIND_RECEIPT_BY_REQUEST, receipt.request_fingerprint, revision, receipt)

class MediaPipeline:
    """Media commands over one UnitOfWork; ports are injected and may be None until a command needs them."""

    def __init__(
        self,
        uow: MediaUnitOfWork,
        *,
        probe: ProbePort | None = None,
        tool: MediaToolPort | None = None,
        transformer: TransformPort | None = None,
        audio_bed: AudioBedPort | None = None,
    ) -> None:
        self._uow = uow
        self._probe = probe
        self._tool = tool
        self._transformer = transformer
        self._audio_bed = audio_bed

    def _replay(self, operation_key: str, fingerprint: str) -> CommandResult | None:
        outputs = self._uow.outputs
        stored = outputs.latest(KIND_RECEIPT, operation_key)
        if stored is not None:
            receipt = stored.record
            if receipt.request_fingerprint != fingerprint:
                raise IdempotencyConflictError(operation_key)
            record = None
            for kind in RECORD_KINDS:
                item = outputs.latest(kind, operation_key)
                if item is not None:
                    record = item.record
                    break
            return CommandResult(receipt, record, True)
        latest = outputs.latest(KIND_RECEIPT_BY_REQUEST, fingerprint)
        if latest is not None and latest.record.disposition is Disposition.OUTCOME_UNKNOWN:
            raise RetryNotAllowedError(operation_key)
        return None

    def _commit(self, operation: str, operation_key: str, fingerprint: str, decision: _Decision) -> CommandResult:
        receipt = OperationReceipt(
            operation_key,
            operation,
            fingerprint,
            decision.disposition,
            decision.outcome,
            decision.output_refs,
            decision.output_hashes,
            decision.warnings,
            decision.error,
        )
        try:
            event = None if decision.event_factory is None else decision.event_factory()
            with self._uow as uow:
                for kind, record in decision.outputs:
                    uow.outputs.append(kind, operation_key, 1, record)
                _append_receipt(uow, receipt)
                if event is not None:
                    dedup = deduplication_id_for(event)
                    uow.outbox.append_event(event.event_name, event.aggregate_id, event.payload, dedup)
                uow.commit()
        except Exception:
            if decision.side_effect_done:
                disposition = Disposition.OUTCOME_UNKNOWN
            else:
                disposition = Disposition.FAILED
            receipt = OperationReceipt(
                operation_key, operation, fingerprint, disposition, error=ERR_RECEIPT_COMMIT_FAILED
            )
            with self._uow as uow:
                _append_receipt(uow, receipt)
                uow.commit()
            return CommandResult(receipt)
        return CommandResult(receipt, decision.outputs[0][1] if decision.outputs else None)

    def probe_media(
        self,
        operation_key: str,
        artifact_ref: ArtifactRef,
        *,
        declared_extension: str | None = None,
        declared_mime: str | None = None,
        observed_size: int,
    ) -> CommandResult:
        _check_key(operation_key)
        if self._probe is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'probe')
        if not isinstance(artifact_ref, ArtifactRef):
            raise ProcessingContractError(WRONG_TYPE, 'artifact_ref')
        parse_probe_output({}, declared_extension, declared_mime, artifact_ref.content_sha256, observed_size)
        fingerprint = request_hash({
            'operation': OP_PROBE_MEDIA,
            'input_ref': _ref_dict(artifact_ref),
            'declared_extension': declared_extension,
            'declared_mime': declared_mime,
            'observed_size': observed_size,
        })
        replay = self._replay(operation_key, fingerprint)
        if replay is not None:
            return replay
        try:
            raw = self._probe.probe(artifact_ref)
            report = parse_probe_output(
                raw, declared_extension, declared_mime, artifact_ref.content_sha256, observed_size
            )
        except Exception as exc:
            failed = _Decision(Disposition.FAILED, error=type(exc).__name__)
            return self._commit(OP_PROBE_MEDIA, operation_key, fingerprint, failed)
        warnings = report.warnings + tuple(f'corruption:{flag}' for flag in report.corruption_flags)
        if report.readability is Readability.UNREADABLE:
            warnings += ('unreadable',)
        decision = _Decision(Disposition.SUCCEEDED, warnings=warnings, outputs=((KIND_PROBE_REPORT, report),))
        return self._commit(OP_PROBE_MEDIA, operation_key, fingerprint, decision)

    def assess_image_safety(
        self,
        operation_key: str,
        context: EventContext,
        artifact_ref: ArtifactRef,
        media_kind: str,
        detector: object,
        policy: ImageSafetyPolicy | None,
    ) -> CommandResult:
        _check_key(operation_key)
        _check_context(context)
        if not isinstance(artifact_ref, ArtifactRef):
            raise ProcessingContractError(WRONG_TYPE, 'artifact_ref')
        if media_kind != IMAGE_KIND:
            raise ProcessingContractError(SAFETY_TRANSFORM_NOT_APPLICABLE, 'media_kind')
        if policy is None:
            raise ImageSafetyError(INPUT_NOT_READY, 'missing_policy')
        if not isinstance(policy, ImageSafetyPolicy):
            raise ImageSafetyError(WRONG_TYPE, 'policy')
        fingerprint = request_hash({
            'operation': OP_ASSESS_IMAGE_SAFETY,
            'input_ref': _ref_dict(artifact_ref),
            'media_kind': media_kind,
            'policy': {
                'revision': policy.revision,
                'confidence_threshold': policy.confidence_threshold,
                'transform_categories': list(policy.transform_categories),
                'require_transform_before_use': policy.require_transform_before_use,
            },
        })
        replay = self._replay(operation_key, fingerprint)
        if replay is not None:
            return replay
        assessment = domain_assess_image_safety(media_kind, detector, policy)
        assessment_ref = f'assessment:{operation_key}'

        def event() -> DomainEvent:
            return build_image_safety_assessed(
                context,
                aggregate_id=assessment_ref,
                aggregate_revision=1,
                assessment_ref=assessment_ref,
                artifact_ref=artifact_ref.ref,
                content_sha256=artifact_ref.content_sha256,
                policy_revision=policy.revision,
            )

        decision = _Decision(
            Disposition.SUCCEEDED,
            outcome=assessment.outcome.value,
            warnings=assessment.warnings,
            outputs=((KIND_IMAGE_SAFETY, assessment),),
            event_factory=event,
        )
        return self._commit(OP_ASSESS_IMAGE_SAFETY, operation_key, fingerprint, decision)

    def transform_sensitive_image(
        self,
        operation_key: str,
        context: EventContext,
        *,
        media_kind: str,
        user_visual_hook: bool,
        assessment: ImageSafetyAssessment,
        source_ref: ArtifactRef,
        regions: Sequence[TransformRegion],
        policy: TransformPolicy,
        output_profile: Mapping,
        verified_outputs: Mapping[str, VerifiedOutput] | None = None,
    ) -> CommandResult:
        _check_key(operation_key)
        _check_context(context)
        if media_kind != IMAGE_KIND:
            raise ProcessingContractError(SAFETY_TRANSFORM_NOT_APPLICABLE, 'media_kind')
        if self._transformer is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'transformer')
        for value, expected, field in (
            (source_ref, ArtifactRef, 'source_ref'),
            (assessment, ImageSafetyAssessment, 'assessment'),
            (policy, TransformPolicy, 'policy'),
            (user_visual_hook, bool, 'user_visual_hook'),
            (output_profile, Mapping, 'output_profile'),
        ):
            if not isinstance(value, expected):
                raise ImageSafetyError(WRONG_TYPE, field)
        if not isinstance(regions, (list, tuple)) or not all(isinstance(item, TransformRegion) for item in regions):
            raise ImageSafetyError(WRONG_TYPE, 'regions')
        fingerprint = request_hash({
            'operation': OP_TRANSFORM_SENSITIVE_IMAGE,
            'source_ref': _ref_dict(source_ref),
            'user_visual_hook': user_visual_hook,
            'assessment': {
                'outcome': assessment.outcome.value,
                'categories': list(assessment.categories),
                'policy_revision': assessment.policy_revision,
            },
            'transform_policy': {'revision': policy.revision, 'actions': [list(pair) for pair in policy.actions]},
            'regions': [
                {'category': item.category, 'confidence': item.confidence, 'mask_ref': item.mask_ref}
                for item in regions
            ],
            'output_profile': _plain(output_profile),
        })
        replay = self._replay(operation_key, fingerprint)
        if replay is not None:
            return replay
        tracked = _TrackedTransformPort(self._transformer)
        result = domain_transform_sensitive_image(
            media_kind, user_visual_hook, assessment, source_ref, regions, policy, output_profile, tracked
        )
        failed = SafetyOutcome.TRANSFORM_FAILED.value
        if isinstance(result, TransformSkipped):
            decision = _Decision(Disposition.SUCCEEDED, warnings=(result.reason,))
        elif result.status is TransformStatus.FAILURE:
            decision = _Decision(
                Disposition.FAILED,
                outcome=failed,
                error=result.warnings[0],
                warnings=result.warnings,
                outputs=((KIND_PROCESSED_MEDIA, result),),
                side_effect_done=tracked.completed,
            )
        else:
            processed = result.processed_ref
            reason = _verify(((processed.ref, processed.content_sha256),), verified_outputs)
            if reason is not None:
                decision = _Decision(
                    Disposition.FAILED,
                    outcome=failed,
                    error=reason,
                    warnings=(reason,),
                    side_effect_done=True,
                )
            else:
                refs, hashes = [processed.ref], [processed.content_sha256]
                decision = _Decision(
                    Disposition.SUCCEEDED,
                    outcome=result.outcome.value,
                    warnings=result.warnings,
                    outputs=((KIND_PROCESSED_MEDIA, result),),
                    output_refs=tuple(refs),
                    output_hashes=tuple(hashes),
                    event_factory=lambda: _completed_event(context, operation_key, refs, hashes),
                    side_effect_done=True,
                )
        return self._commit(OP_TRANSFORM_SENSITIVE_IMAGE, operation_key, fingerprint, decision)

    def normalize_media(
        self,
        operation_key: str,
        context: EventContext,
        *,
        input_ref: ArtifactRef,
        spec: NormalizeSpec,
        media_kind: str,
        focus_region: FocusRegion | None = None,
        output_ref: str | None = None,
        verified_outputs: Mapping[str, VerifiedOutput] | None = None,
    ) -> CommandResult:
        _check_key(operation_key)
        _check_context(context)
        if self._tool is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'tool')
        plan = plan_rendition(input_ref, spec, media_kind, focus_region, output_ref)
        focus = None if plan.focus_region is None else dataclasses.asdict(plan.focus_region)
        fingerprint = request_hash({
            'operation': OP_NORMALIZE_MEDIA,
            'plan_fingerprint': plan.plan_fingerprint,
            'output_ref': plan.output_ref,
            'media_kind': plan.media_kind,
            'focus_region': focus,
        })
        replay = self._replay(operation_key, fingerprint)
        if replay is not None:
            return replay

        def finish(decision: _Decision) -> CommandResult:
            return self._commit(OP_NORMALIZE_MEDIA, operation_key, fingerprint, decision)

        def rejected(error: str) -> CommandResult:
            return finish(_Decision(Disposition.FAILED, error=error, side_effect_done=True))

        try:
            outcome = self._tool.run(plan)
        except Exception as exc:
            return finish(_Decision(Disposition.FAILED, error=type(exc).__name__))
        if not isinstance(outcome, ToolOutcome):
            return finish(_Decision(Disposition.FAILED, error=ERR_TOOL_BAD_RESULT))
        if outcome.status is Disposition.OUTCOME_UNKNOWN:
            unknown = _Decision(
                Disposition.OUTCOME_UNKNOWN, error=outcome.error or 'tool_outcome_unknown', side_effect_done=True
            )
            return finish(unknown)
        if outcome.status is not Disposition.SUCCEEDED:
            return finish(_Decision(Disposition.FAILED, error=outcome.error or f'tool_{outcome.status.value}'))
        try:
            verify_tool_outcome(plan, outcome)
        except ProcessingContractError:
            return rejected(ERR_OUTPUT_REF_MISMATCH)
        reason = _verify(((outcome.output_ref, outcome.output_sha256),), verified_outputs)
        if reason is not None:
            return rejected(reason)
        size_bytes = verified_outputs[outcome.output_ref].size_bytes
        if self._probe is not None:
            try:
                raw = self._probe.probe(ArtifactRef(outcome.output_ref, outcome.output_sha256))
                report = parse_probe_output(raw, None, None, outcome.output_sha256, size_bytes)
            except Exception:
                return rejected(ERR_OUTPUT_NOT_READABLE)
            if report.readability is not Readability.READABLE:
                return rejected(ERR_OUTPUT_NOT_READABLE)
        record = ProcessedRendition(
            output_ref=outcome.output_ref,
            output_sha256=outcome.output_sha256,
            size_bytes=size_bytes,
            input_ref=plan.input_ref,
            lineage_refs=plan.lineage_refs,
            media_kind=plan.media_kind,
            spec_fingerprint=plan.spec_fingerprint,
            plan_fingerprint=plan.plan_fingerprint,
        )
        refs, hashes = [outcome.output_ref], [outcome.output_sha256]
        return finish(_Decision(
            Disposition.SUCCEEDED,
            outputs=((KIND_PROCESSED_MEDIA, record),),
            output_refs=tuple(refs),
            output_hashes=tuple(hashes),
            event_factory=lambda: _completed_event(context, operation_key, refs, hashes),
            side_effect_done=True,
        ))

    def prepare_audio_bed(
        self,
        operation_key: str,
        context: EventContext,
        request: AudioBedRequest,
        *,
        verified_outputs: Mapping[str, VerifiedOutput] | None = None,
    ) -> CommandResult:
        _check_key(operation_key)
        _check_context(context)
        if self._audio_bed is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'audio_bed')
        if not isinstance(request, AudioBedRequest):
            raise AudioBedError(WRONG_TYPE, 'request')
        limits = request.loudness_constraints
        if limits is None or limits.min_lufs is None or limits.max_lufs is None or limits.max_true_peak_dbtp is None:
            raise AudioBedRejected(INPUT_NOT_READY, 'missing_loudness_constraints')
        fingerprint = request_hash({
            'operation': OP_PREPARE_AUDIO_BED,
            'cues': [dataclasses.asdict(cue) for cue in request.cues],
            'voice_artifact_ref': request.voice_artifact_ref,
            'preset_audio_policy_revision': request.preset_audio_policy_revision,
            'loudness_constraints': dataclasses.asdict(limits),
            'mix_constraints': _plain(request.mix_constraints),
            'fallback_allowed': request.fallback_allowed,
            'fallback_artifact_refs': list(request.fallback_artifact_refs),
        })
        replay = self._replay(operation_key, fingerprint)
        if replay is not None:
            return replay

        def finish(decision: _Decision) -> CommandResult:
            return self._commit(OP_PREPARE_AUDIO_BED, operation_key, fingerprint, decision)

        def rejected(error: str) -> CommandResult:
            return finish(_Decision(Disposition.FAILED, error=error, side_effect_done=True))

        try:
            outcome = self._audio_bed.prepare(request)
        except Exception as exc:
            return finish(_Decision(Disposition.FAILED, error=type(exc).__name__))
        if not isinstance(outcome, AudioBedOutcome):
            return finish(_Decision(Disposition.FAILED, error=ERR_TOOL_BAD_RESULT))
        if outcome.status is Disposition.OUTCOME_UNKNOWN:
            unknown = _Decision(
                Disposition.OUTCOME_UNKNOWN, error=outcome.error or 'tool_outcome_unknown', side_effect_done=True
            )
            return finish(unknown)
        if outcome.status is not Disposition.SUCCEEDED:
            return finish(_Decision(Disposition.FAILED, error=outcome.error or f'tool_{outcome.status.value}'))
        try:
            result = build_audio_bed_result(
                request,
                renditions=outcome.renditions,
                loudness_report=outcome.loudness_report,
                provenance=outcome.provenance,
                risk_metadata=outcome.risk_metadata,
                warnings=outcome.warnings,
            )
        except AudioBedError as exc:
            return rejected(f'{exc.code}:{exc.field}')
        refs = [item.rendition_ref for item in result.renditions]
        hashes = list(outcome.output_hashes)
        if len(hashes) != len(refs) or not all(isinstance(h, str) and _SHA256_RE.fullmatch(h) for h in hashes):
            return rejected(ERR_OUTPUT_HASHES_MISMATCH)
        originals = {cue.artifact_ref for cue in request.cues}
        originals |= {request.voice_artifact_ref, *request.fallback_artifact_refs}
        if any(ref in originals for ref in refs):
            return rejected(ERR_OUTPUT_REPLACES_ORIGINAL)
        reason = _verify(tuple(zip(refs, hashes)), verified_outputs)
        if reason is not None:
            return rejected(reason)
        return finish(_Decision(
            Disposition.SUCCEEDED,
            warnings=result.warnings,
            outputs=((KIND_AUDIO_BED, result),),
            output_refs=tuple(refs),
            output_hashes=tuple(hashes),
            event_factory=lambda: _completed_event(context, operation_key, refs, hashes),
            side_effect_done=True,
        ))

    def process_image_batch(
        self,
        batch_key: str,
        items: Sequence[ImageBatchItem],
        *,
        safety_policy: ImageSafetyPolicy,
        transform_policy: TransformPolicy,
        output_profile: Mapping,
        context_for: Callable[[str], EventContext],
        verified_outputs: Mapping[str, VerifiedOutput] | None = None,
    ) -> tuple[ImageBatchResult, ...]:
        _check_key(batch_key)
        results: list[ImageBatchResult] = []
        for item in items:
            prefix = f'{batch_key}:{item.item_id}'
            assess_key = f'{prefix}:assess'
            assessed = self.assess_image_safety(
                assess_key, context_for(assess_key), item.artifact_ref, IMAGE_KIND, item.detector, safety_policy
            )
            receipts = [assessed.receipt.receipt_ref]
            assessment = assessed.record
            if assessment is None:
                warnings = (f'assessment_failed:{assessed.receipt.error}',)
                results.append(ImageBatchResult(
                    item.item_id,
                    SafetyOutcome.DETECTION_FAILED,
                    item.artifact_ref,
                    None,
                    None,
                    warnings,
                    tuple(receipts),
                ))
                continue
            outcome = assessment.outcome
            warnings = list(assessment.warnings)
            processed_ref = None
            unusable = False
            if outcome is SafetyOutcome.TRANSFORM_REQUIRED:
                transform_key = f'{prefix}:transform'
                transformed = self.transform_sensitive_image(
                    transform_key,
                    context_for(transform_key),
                    media_kind=IMAGE_KIND,
                    user_visual_hook=item.user_visual_hook,
                    assessment=assessment,
                    source_ref=item.artifact_ref,
                    regions=item.regions,
                    policy=transform_policy,
                    output_profile=output_profile,
                    verified_outputs=verified_outputs,
                )
                receipt = transformed.receipt
                receipts.append(receipt.receipt_ref)
                warnings.extend(w for w in receipt.warnings if w not in warnings)
                if receipt.disposition is Disposition.SUCCEEDED and transformed.record is not None:
                    outcome = transformed.record.outcome
                    processed_ref = transformed.record.processed_ref
                elif receipt.disposition is Disposition.OUTCOME_UNKNOWN:
                    outcome = SafetyOutcome.TRANSFORM_FAILED
                    unusable = True
                    warnings.append('transform_outcome_unknown')
                elif receipt.disposition is Disposition.FAILED:
                    outcome = SafetyOutcome.TRANSFORM_FAILED
            if processed_ref is not None:
                usable = processed_ref
            elif unusable or not original_usable_for(outcome, safety_policy.require_transform_before_use):
                usable = None
            else:
                usable = item.artifact_ref
            results.append(ImageBatchResult(
                item.item_id, outcome, item.artifact_ref, processed_ref, usable, tuple(warnings), tuple(receipts)
            ))
        return tuple(results)


__all__ = (
    'AudioBedOutcome',
    'AudioBedPort',
    'CommandResult',
    'ERR_OUTPUT_HASHES_MISMATCH',
    'ERR_OUTPUT_HASH_MISMATCH',
    'ERR_OUTPUT_NOT_READABLE',
    'ERR_OUTPUT_NOT_VERIFIED',
    'ERR_OUTPUT_REF_MISMATCH',
    'ERR_OUTPUT_REPLACES_ORIGINAL',
    'ERR_RECEIPT_COMMIT_FAILED',
    'ERR_TOOL_BAD_RESULT',
    'IdempotencyConflictError',
    'ImageBatchItem',
    'ImageBatchResult',
    'KIND_AUDIO_BED',
    'KIND_IMAGE_SAFETY',
    'KIND_PROBE_REPORT',
    'KIND_PROCESSED_MEDIA',
    'KIND_RECEIPT',
    'KIND_RECEIPT_BY_REQUEST',
    'MediaPipeline',
    'MediaUnitOfWork',
    'OP_ASSESS_IMAGE_SAFETY',
    'OP_NORMALIZE_MEDIA',
    'OP_PREPARE_AUDIO_BED',
    'OP_PROBE_MEDIA',
    'OP_TRANSFORM_SENSITIVE_IMAGE',
    'OperationReceipt',
    'ProcessedRendition',
    'RECORD_KINDS',
    'RetryNotAllowedError',
    'VerifiedOutput',
)