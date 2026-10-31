"""F-19: InspectOutput and PrepareOutputReady command handlers (CT-QC-001, CT-RND-005, TST-E2E-INV-009).

Application layer of F: render domain, render ports and controlplane types only; no I/O, no clock, no file API.
InspectOutput checks the grant, replays a stored receipt by (workspace, command, operation_key), then needs a SUCCEEDED attempt of the stored package. It runs the F-13 technical gates (OutputProbePort) and the F-14 content gates (OutputInspectorPort), adds the caller-given warning gates, builds the F-12 QualityReport and stores report, receipt, trace and the OutputQualityChecked outbox event in ONE unit of work; the event is written for a passed and for a failed report.
PrepareOutputReady needs the current stored report of the attempt and asks F-15 for the verdict: QC pass plus every other condition gives a VideoOutput for G, anything else gives reasons and no VideoOutput. upload_verified (I) and completion_committed (G) are inputs; completion_eligible is derived and never implies completion. Nothing here deletes or overwrites an output.
A failed report or a not-ready verdict is a stored result, not a command failure.

coveredIds: CT-QC-001, CT-RND-005, TST-E2E-INV-009, TST-QC-INV-019, TST-E2E-001 (đoạn QC)
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState, transition_operation
from render.application.package_pipeline import (
    IDEMPOTENCY_CONFLICT, STALE_GRANT, CommandContext, CommandReceipt, CommandTrace, GrantCurrencyPort, IdempotencyConflict,
    PackageUnitOfWork, PipelineRejected, RenderPackageNotFound, StaleGrant, _digest, _plain,
)
from render.application.render_video import RenderAttemptNotFound
from render.domain.content_gates import ExpectedLanguageRevisions, evaluate_content_gates
from render.domain.events import EventContext, build_output_quality_checked, deduplication_id_for
from render.domain.output_ready import (
    OUTPUT_NOT_READY, QUALITY_NOT_PASSED, MilestoneState, OutputReadyError, VideoOutput, create_video_output, derive_milestones,
)
from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import (
    GATE_KINDS, GateKind, GateName, GateResult, GateStatus, QualityPolicy, QualityReport, build_quality_report,
)
from render.domain.render_attempt import RenderAttempt
from render.domain.technical_gates import GateResult as TechnicalGateResult
from render.domain.technical_gates import evaluate_technical_gates
from render.ports.output_inspector import OutputInspectorPort
from render.ports.output_probe import OutputProbePort
from render.ports.renderer import OutputObservationPort
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE, KIND_QUALITY_REPORT


COMMAND_INSPECT = 'InspectOutput'
COMMAND_PREPARE = 'PrepareOutputReady'
ATTEMPT_NOT_SUCCEEDED = 'attempt_not_succeeded'
ATTEMPT_PACKAGE_MISMATCH = 'attempt_package_mismatch'
QUALITY_REPORT_NOT_FOUND = 'QUALITY_REPORT_NOT_FOUND'
OUTCOME_QC_PASSED = 'qc_passed'
OUTCOME_QC_FAILED = 'qc_failed'
OUTCOME_OUTPUT_READY = 'output_ready'
OUTCOME_OUTPUT_NOT_READY = 'output_not_ready'


class OutputNotInspectable(PipelineRejected):
    """The render attempt is not SUCCEEDED, so there is no rendered output to inspect."""


class AttemptPackageMismatch(PipelineRejected):
    """The attempt was rendered from another package fingerprint than the stored package."""


class QualityReportNotFound(LookupError):
    """No stored report, or not the current report of the attempt, matches quality_report_ref."""

    def __init__(self, quality_report_ref: str) -> None:
        super().__init__(f'{QUALITY_REPORT_NOT_FOUND}: {quality_report_ref}')
        self.code = QUALITY_REPORT_NOT_FOUND
        self.quality_report_ref = quality_report_ref


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _problem(code: str, title: str, detail: str, command_name: str, context: CommandContext) -> ProblemDetail:
    slug = code.lower().replace('_', '-')
    return ProblemDetail.create(
        type=f'urn:render:problem:{slug}', title=title, detail=detail, instance=f'urn:render:command:{command_name}', code=code,
        category='conflict', retryable=False, correlation_id=context.correlation_id, status=409,
    )


def _reject(kind: type[PipelineRejected], code: str, title: str, detail: str, command_name: str, context: CommandContext) -> PipelineRejected:
    return kind(code, _problem(code, title, detail, command_name, context))


@dataclasses.dataclass(frozen=True, kw_only=True)
class InspectOutputCommand:
    """G issues operation_key (the idempotency key) and the refs. policy carries the thresholds of every gate; word_timings (start_ms per word) and segments (segment_id, claim_mode) come from E and D; warning_results holds warning gates only."""

    grant: ExecutionGrant
    operation_key: str
    render_package_id: str
    render_attempt_id: str
    policy: QualityPolicy
    expected_language: ExpectedLanguageRevisions
    word_timings: Sequence[Mapping[str, object]]
    segments: Sequence[Mapping[str, object]]
    context: CommandContext
    warning_results: tuple[GateResult, ...] = ()

    def __post_init__(self) -> None:
        for name in ('operation_key', 'render_package_id', 'render_attempt_id'):
            _text(name, getattr(self, name))
        if not isinstance(self.policy, QualityPolicy):
            raise ValueError('policy must be a QualityPolicy')
        if not isinstance(self.expected_language, ExpectedLanguageRevisions):
            raise ValueError('expected_language must be ExpectedLanguageRevisions')
        warnings = tuple(self.warning_results)
        if not all(isinstance(item, GateResult) and GATE_KINDS[item.gate] is GateKind.WARNING for item in warnings):
            raise ValueError('warning_results must hold warning gates only')
        object.__setattr__(self, 'warning_results', warnings)


@dataclasses.dataclass(frozen=True, kw_only=True)
class PrepareOutputReadyCommand:
    """quality_report_ref is the report_id returned by InspectOutput; expected_sha256 comes from the verified source (G or I); upload_verified (I) and completion_committed (G) are facts given by the caller."""

    grant: ExecutionGrant
    operation_key: str
    render_package_id: str
    render_attempt_id: str
    quality_report_ref: str
    video_output_id: str
    expected_sha256: str | None
    context: CommandContext
    upload_verified: bool = False
    completion_committed: bool = False

    def __post_init__(self) -> None:
        for name in ('operation_key', 'render_package_id', 'render_attempt_id', 'quality_report_ref', 'video_output_id'):
            _text(name, getattr(self, name))
        for name in ('upload_verified', 'completion_committed'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be a bool')


@dataclasses.dataclass(frozen=True, kw_only=True)
class OutputReadyReceipt(CommandReceipt):
    """Receipt of PrepareOutputReady: it stores the verdict so that a replay returns the same answer."""

    render_attempt_id: str
    ready: bool
    reasons: tuple[str, ...]
    video_output: VideoOutput | None
    milestones: MilestoneState


@dataclasses.dataclass(frozen=True)
class InspectOutcome:
    receipt: CommandReceipt
    report: QualityReport
    replayed: bool


@dataclasses.dataclass(frozen=True)
class OutputReadyOutcome:
    receipt: OutputReadyReceipt
    replayed: bool

    @property
    def ready(self) -> bool:
        return self.receipt.ready

    @property
    def video_output(self) -> VideoOutput | None:
        return self.receipt.video_output

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.receipt.reasons

    @property
    def milestones(self) -> MilestoneState:
        return self.receipt.milestones


def _entry(policy: QualityPolicy, gate: GateName) -> Mapping[str, object]:
    value = policy.thresholds.get(gate.value)
    return value if isinstance(value, Mapping) else {}


def _technical_inputs(policy: QualityPolicy) -> tuple[dict[str, object], Mapping[str, object] | None]:
    """Map QualityPolicy.thresholds to the flat policy and expected_profile of F-13; a missing threshold stays missing so the gate is not_evaluated."""
    flat: dict[str, object] = {}
    duration = _entry(policy, GateName.DURATION_RANGE).get('duration_range_ms')
    if duration is not None:
        flat['duration_range_ms'] = duration
    minimum = _entry(policy, GateName.VOICE_AUDIBLE).get('min_voice_level')
    if minimum is not None:
        flat['min_voice_level'] = minimum
    profile = policy.thresholds.get(GateName.OUTPUT_PROFILE_VALID.value)
    return flat, profile if isinstance(profile, Mapping) else None


def _report_gate(item: TechnicalGateResult) -> GateResult:
    """F-13 declares its own GateResult; copy it field by field into the F-12 GateResult."""
    return GateResult(
        gate=item.gate.value, status=item.status.value, evidence_ref=item.evidence_ref, time_range=item.time_range,
        measured_value=item.measured_value, threshold_revision=item.threshold_revision, reason=item.reason,
    )


def _seal(kind: type[CommandReceipt], command_name: str, context: CommandContext, operation_key: str, digest: str, **fields: Any) -> CommandReceipt:
    """PREPARED, STARTED, SUCCEEDED through transition_operation, like F-17; receipt_ref comes from the scope and the request_hash."""
    started = transition_operation(current_state=OperationState.PREPARED, current_revision=0, expected_revision=0, requested_state=OperationState.STARTED)
    done = transition_operation(current_state=OperationState.STARTED, current_revision=started.revision, expected_revision=started.revision, requested_state=OperationState.SUCCEEDED)
    scope = request_hash({'scope': [context.workspace_id, command_name, operation_key], 'request_hash': digest})
    return kind(
        command=command_name, workspace_id=context.workspace_id, operation_key=operation_key, request_hash=digest,
        receipt_ref=f'receipt-{scope[:32]}', state=OperationState(done.state), revision=done.revision, **fields,
    )


def _trace(uow: Any, receipt: CommandReceipt, grant: ExecutionGrant, context: CommandContext, subject_ref: str, outcome: str) -> None:
    uow.traces.append(CommandTrace(
        sequence=0, command=receipt.command, workspace_id=receipt.workspace_id, operation_key=receipt.operation_key,
        correlation_id=context.correlation_id, actor=context.actor, occurred_at=context.occurred_at, receipt_ref=receipt.receipt_ref,
        grant_id=grant.operation_id, execution_generation=grant.execution_generation, subject_ref=subject_ref, outcome=outcome,
    ))


def _store_report(uow: Any, render_attempt_id: str, report: QualityReport) -> int:
    """Append the report as the next revision of the attempt; a report identical to the latest one is not stored twice. Returns the revision."""
    latest = uow.renders.latest(KIND_QUALITY_REPORT, render_attempt_id)
    if latest is not None and latest.record.report_id == report.report_id:
        return latest.revision
    revision = 1 if latest is None else latest.revision + 1
    uow.renders.append(KIND_QUALITY_REPORT, render_attempt_id, revision, report)
    return revision


def _stored_report(uow: Any, render_attempt_id: str, report_id: str | None) -> QualityReport | None:
    for stored in uow.renders.revisions(KIND_QUALITY_REPORT, render_attempt_id):
        if stored.record.report_id == report_id:
            return stored.record
    return None


def _quality_event(uow: Any, attempt: RenderAttempt, report: QualityReport, revision: int, grant: ExecutionGrant, receipt: CommandReceipt, context: CommandContext) -> None:
    """OutputQualityChecked to the outbox of the same unit of work, for a passed and for a failed report; the dedup id binds report_id and revision."""
    key = f'{report.report_id[:32]}-{revision}'
    event = build_output_quality_checked(
        EventContext(
            workspace_id=context.workspace_id, correlation_id=context.correlation_id, actor=context.actor, occurred_at=context.occurred_at,
            recovery_epoch=str(grant.recovery_epoch), event_id=f'evt-output-quality-checked-{key}', message_id=f'msg-output-quality-checked-{key}',
            causation_id=receipt.receipt_ref,
        ),
        attempt=attempt, report=report, aggregate_revision=revision,
    )
    uow.outbox.append_event(event.event_name, event.aggregate_id, event.payload, deduplication_id_for(event))


class OutputPipeline:
    def __init__(
        self, *, uow: PackageUnitOfWork, probe: OutputProbePort, inspector: OutputInspectorPort, observer: OutputObservationPort,
        grants: GrantCurrencyPort, probe_for: Callable[[RenderPackageRecord], OutputProbePort] | None = None,
    ) -> None:
        self._uow = uow
        self._probe = probe
        self._probe_for = probe_for
        self._inspector = inspector
        self._observer = observer
        self._grants = grants

    def _require_current_grant(self, command_name: str, grant: object, context: CommandContext) -> None:
        if isinstance(grant, ExecutionGrant) and grant.workspace_id == context.workspace_id and self._grants.is_grant_current(grant):
            return
        raise _reject(StaleGrant, STALE_GRANT, 'Stale execution grant', 'The execution grant is not current for this workspace.', command_name, context)

    def _replay(self, uow: Any, command_name: str, context: CommandContext, operation_key: str, digest: str) -> CommandReceipt | None:
        stored = uow.receipts.get(context.workspace_id, command_name, operation_key)
        if stored is None:
            return None
        if stored.request_hash != digest:
            raise _reject(IdempotencyConflict, IDEMPOTENCY_CONFLICT, 'Idempotency conflict', 'The operation key is already bound to another request.', command_name, context)
        return stored

    def _load(self, uow: Any, command: Any, command_name: str, *, require_succeeded: bool) -> tuple[RenderAttempt, RenderPackageRecord]:
        """Stored attempt and package of the command; the attempt must belong to the package fingerprint and, when asked, be SUCCEEDED. Reads only."""
        stored_attempt = uow.renders.latest(KIND_ATTEMPT, command.render_attempt_id)
        if stored_attempt is None:
            raise RenderAttemptNotFound(command.render_attempt_id)
        stored_package = uow.renders.latest(KIND_PACKAGE, command.render_package_id)
        if stored_package is None:
            raise RenderPackageNotFound(command.render_package_id)
        attempt, package = stored_attempt.record, stored_package.record
        if attempt.package_fingerprint != package.package_fingerprint:
            raise _reject(AttemptPackageMismatch, ATTEMPT_PACKAGE_MISMATCH, 'Attempt and package differ', 'The render attempt was not rendered from this package.', command_name, command.context)
        if require_succeeded and attempt.receipt_state is not OperationState.SUCCEEDED:
            raise _reject(OutputNotInspectable, ATTEMPT_NOT_SUCCEEDED, 'Attempt not succeeded', 'Only a SUCCEEDED render attempt has an output to inspect.', command_name, command.context)
        return attempt, package

    def _build_report(self, command: InspectOutputCommand, attempt: RenderAttempt, package: RenderPackageRecord) -> QualityReport:
        """Probe once (F-13) and inspect once (F-14), then add the warning results; INFERENCE_DISCLOSURE_PRESENT is marked not applicable only when F-14 says so."""
        output_ref = attempt.output_artifact_ref
        flat, profile = _technical_inputs(command.policy)
        probe = self._probe if self._probe_for is None else self._probe_for(package)
        technical = evaluate_technical_gates(probe, output_ref, policy=flat, expected_profile=profile, threshold_revision=command.policy.revision)
        content = evaluate_content_gates(self._inspector, output_ref, package, command.policy, command.expected_language, command.word_timings, command.segments)
        applicability = {item.gate: False for item in content if item.gate is GateName.INFERENCE_DISCLOSURE_PRESENT and item.status is GateStatus.NOT_APPLICABLE}
        results = (*(_report_gate(item) for item in technical), *content, *command.warning_results)
        return build_quality_report(results, applicability, policy=command.policy)

    def _verdict(self, command: PrepareOutputReadyCommand, attempt: RenderAttempt, package: RenderPackageRecord, report: QualityReport, observed_sha256: str | None) -> tuple[VideoOutput | None, tuple[str, ...]]:
        """F-15 decides. refs_committed is True because attempt and report were just read from the store inside this unit of work; grant_valid asks G again."""
        try:
            video = create_video_output(
                video_output_id=command.video_output_id, attempt=attempt, observed_sha256=observed_sha256, expected_sha256=command.expected_sha256,
                report=report, refs_committed=True, grant_valid=self._grants.is_grant_current(command.grant),
                output_metadata_revision=package.output_metadata_revision,
            )
        except OutputReadyError as error:
            if error.code not in (QUALITY_NOT_PASSED, OUTPUT_NOT_READY):
                raise
            return None, error.reasons
        return video, ()

    def inspect_output(self, command: InspectOutputCommand) -> InspectOutcome:
        """One unit of work: grant first, then replay or conflict, then ports, report, receipt, trace and OutputQualityChecked."""
        context = command.context
        self._require_current_grant(COMMAND_INSPECT, command.grant, context)
        digest = _digest(COMMAND_INSPECT, context, {
            'render_package_id': command.render_package_id, 'render_attempt_id': command.render_attempt_id,
            'policy': _plain(command.policy), 'expected_language': _plain(command.expected_language),
            'word_timings': _plain(command.word_timings), 'segments': _plain(command.segments),
            'warning_results': _plain(command.warning_results),
        })
        with self._uow as uow:
            replayed = self._replay(uow, COMMAND_INSPECT, context, command.operation_key, digest)
            if replayed is not None:
                return InspectOutcome(replayed, _stored_report(uow, command.render_attempt_id, replayed.report_id), True)
            attempt, package = self._load(uow, command, COMMAND_INSPECT, require_succeeded=True)
            report = self._build_report(command, attempt, package)
            revision = _store_report(uow, attempt.render_attempt_id, report)
            receipt = _seal(
                CommandReceipt, COMMAND_INSPECT, context, command.operation_key, digest,
                render_package_id=package.render_package_id, package_fingerprint=package.package_fingerprint, report_id=report.report_id,
            )
            uow.receipts.add(receipt)
            _trace(uow, receipt, command.grant, context, report.report_id, OUTCOME_QC_PASSED if report.passed else OUTCOME_QC_FAILED)
            _quality_event(uow, attempt, report, revision, command.grant, receipt, context)
            uow.commit()
        return InspectOutcome(receipt, report, False)

    def prepare_output_ready(self, command: PrepareOutputReadyCommand) -> OutputReadyOutcome:
        """One unit of work: grant first, then replay or conflict, then the current stored report, F-15 verdict, receipt and trace."""
        context = command.context
        self._require_current_grant(COMMAND_PREPARE, command.grant, context)
        digest = _digest(COMMAND_PREPARE, context, {
            'render_package_id': command.render_package_id, 'render_attempt_id': command.render_attempt_id,
            'quality_report_ref': command.quality_report_ref, 'video_output_id': command.video_output_id,
            'expected_sha256': command.expected_sha256, 'upload_verified': command.upload_verified,
            'completion_committed': command.completion_committed,
        })
        with self._uow as uow:
            replayed = self._replay(uow, COMMAND_PREPARE, context, command.operation_key, digest)
            if replayed is not None:
                return OutputReadyOutcome(replayed, True)
            attempt, package = self._load(uow, command, COMMAND_PREPARE, require_succeeded=False)
            latest = uow.renders.latest(KIND_QUALITY_REPORT, attempt.render_attempt_id)
            if latest is None or latest.record.report_id != command.quality_report_ref:
                raise QualityReportNotFound(command.quality_report_ref)
            report = latest.record
            seen = self._observer.observe(attempt.output_artifact_ref)
            video, reasons = self._verdict(command, attempt, package, report, seen.sha256 if seen.exists else None)
            milestones = derive_milestones(
                attempt, report, upload_verified=command.upload_verified, completion_committed=command.completion_committed,
            )
            receipt = _seal(
                OutputReadyReceipt, COMMAND_PREPARE, context, command.operation_key, digest,
                render_package_id=package.render_package_id, package_fingerprint=package.package_fingerprint, report_id=report.report_id,
                render_attempt_id=attempt.render_attempt_id, ready=video is not None, reasons=reasons, video_output=video,
                milestones=milestones,
            )
            uow.receipts.add(receipt)
            outcome = OUTCOME_OUTPUT_READY if video is not None else OUTCOME_OUTPUT_NOT_READY
            _trace(uow, receipt, command.grant, context, attempt.render_attempt_id, outcome)
            uow.commit()
        return OutputReadyOutcome(receipt, False)


__all__ = [
    'COMMAND_INSPECT', 'COMMAND_PREPARE', 'AttemptPackageMismatch', 'InspectOutcome', 'InspectOutputCommand', 'OutputNotInspectable',
    'OutputPipeline', 'OutputReadyOutcome', 'OutputReadyReceipt', 'PrepareOutputReadyCommand', 'QualityReportNotFound',
]
