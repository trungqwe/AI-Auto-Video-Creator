"""F-18: RenderVideo and ReconcileRender command handlers (CT-RND-004, CT-STATE-011, TST-SEC-INV-012).

Application layer of F: render domain, render ports and controlplane types only; no I/O, no clock, no process execution.
RenderVideo checks the grant, replays a stored attempt by render_attempt_id, then needs a passing validation report for the package fingerprint (package_not_validated) and no earlier attempt of the package that is OUTCOME_UNKNOWN (reconcile_required) or still running (attempt_in_progress).
It takes one GPU slot through GpuLeasePort and always returns it. The held lease is handed to a renderer that declares takes_held_lease = True (RealFfmpegRenderer), which never acquires; a renderer without that flag (the fakes) is called with the spec only, so one render takes exactly one slot. The attempt is stored STARTED in one unit of work before the renderer runs and settled in a second one, so a crash leaves STARTED and never a ready output. A GpuLeaseWaitExpired from a waiting adapter is rejected as gpu_lease_wait_expired (capacity, not retryable) so the flow does not repeat the whole wait.
SUCCEEDED needs an output that exists, a claimed sha256 equal to the observed one and a decodable probe (then RenderCompleted goes to the outbox); a reported failure, a crash or an unverifiable output is FAILED; RendererTimeout is OUTCOME_UNKNOWN.
ReconcileRender probes the output (OutputProbePort of F-13 and OutputObservationPort) and resolves OUTCOME_UNKNOWN with reconcile_attempt; only a FAILED attempt may be followed by a new attempt with a new output_artifact_ref. An attempt left STARTED by a dead worker is adopted as OUTCOME_UNKNOWN only when it is older than orphan_after_seconds, then probed like any unknown attempt. Nothing here deletes or overwrites an output.
Error text is redacted with the declared secret_values; ProblemDetail and events carry codes and refs only.

coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012, TST-E2E-001 (đoạn render), TST-CTR-INV-001
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
from types import MappingProxyType
from typing import Any, Protocol

from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState
from render.adapters.memory import _Table
from render.application.package_pipeline import (
    STALE_GRANT, CommandContext, CommandTrace, GrantCurrencyPort, InMemoryPackageUnitOfWork, PackageUnitOfWork,
    PipelineRejected, RenderPackageNotFound, StaleGrant,
)
from render.domain.events import EventContext, build_render_completed, deduplication_id_for
from render.domain.package_contract import RenderPackageRecord
from render.domain.render_attempt import (
    ProbeEvidence, RenderAttempt, fail_attempt, mark_outcome_unknown, prepare_attempt, reconcile_attempt, start_attempt,
    succeed_attempt,
)
from render.domain.render_command import RenderCommandSpec
from render.domain.validate_package import ValidationContext, validate_render_package
from render.ports.lease import GpuLease, GpuLeasePort, GpuLeaseUnavailable, GpuLeaseWaitExpired
from render.ports.output_probe import OutputProbePort
from render.ports.renderer import (
    OutputObservationPort, RendererMetrics, RendererOutcome, RendererPort, RendererStatus, RendererTimeout,
)
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE

COMMAND_RENDER = 'RenderVideo'
COMMAND_RECONCILE = 'ReconcileRender'
PACKAGE_NOT_VALIDATED = 'package_not_validated'
RECONCILE_REQUIRED = 'reconcile_required'
ATTEMPT_IN_PROGRESS = 'attempt_in_progress'
GPU_LEASE_UNAVAILABLE = 'gpu_lease_unavailable'
GPU_LEASE_WAIT_EXPIRED = 'gpu_lease_wait_expired'
RECONCILE_NOT_NEEDED = 'reconcile_not_needed'
RENDER_ATTEMPT_NOT_FOUND = 'RENDER_ATTEMPT_NOT_FOUND'
RENDER_ATTEMPT_FAILED = 'render_attempt_failed'
RENDER_OUTCOME_UNKNOWN = 'render_outcome_unknown'
REASON_RENDERER_FAILED = 'renderer_failed'
REASON_RENDERER_CRASHED = 'renderer_crashed'
REASON_OUTCOME_INVALID = 'renderer_outcome_invalid'
REASON_TIMEOUT = 'renderer_timeout_after_side_effect'
REASON_WORKER_LOST = 'worker_lost_after_start'
REASON_OUTPUT_REF_MISMATCH = 'output_ref_mismatch'
REASON_OUTPUT_MISSING = 'output_missing'
REASON_OUTPUT_HASH_MISMATCH = 'output_hash_mismatch'
REASON_OUTPUT_NOT_DECODABLE = 'output_not_decodable'


class PackageNotValidated(PipelineRejected):
    """No passing validation report exists for the package fingerprint (or the fresh validation failed)."""


class ReconcileRequired(PipelineRejected):
    """An earlier attempt of the package is OUTCOME_UNKNOWN: reconcile it before any new attempt."""


class AttemptInProgress(PipelineRejected):
    """An earlier attempt of the package is PREPARED or STARTED."""


class GpuLeaseNotAvailable(PipelineRejected):
    """No LOCK-DESKTOP-GPU slot is free, or none became free within the wait limit of the adapter; nothing was stored or rendered."""


class ReconcileNotNeeded(PipelineRejected):
    """ReconcileRender only applies to an OUTCOME_UNKNOWN attempt."""


class RenderAttemptNotFound(LookupError):
    def __init__(self, render_attempt_id: str) -> None:
        super().__init__(f'{RENDER_ATTEMPT_NOT_FOUND}: {render_attempt_id}')
        self.code = RENDER_ATTEMPT_NOT_FOUND
        self.render_attempt_id = render_attempt_id


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


@dataclasses.dataclass(frozen=True, kw_only=True)
class RenderVideoCommand:
    """Ids are inputs: G issues render_attempt_id (the idempotency key), output_artifact_ref and receipt_ref. validation_context, when given, re-validates the package right before the render."""

    grant: ExecutionGrant
    render_package_id: str
    render_attempt_id: str
    output_artifact_ref: str
    receipt_ref: str
    command_spec: RenderCommandSpec
    context: CommandContext
    validation_context: ValidationContext | None = None
    secret_values: tuple[str, ...] = dataclasses.field(default=(), repr=False)

    def __post_init__(self) -> None:
        for name in ('render_package_id', 'render_attempt_id', 'output_artifact_ref', 'receipt_ref'):
            _text(name, getattr(self, name))


@dataclasses.dataclass(frozen=True, kw_only=True)
class ReconcileRenderCommand:
    """expected_sha256 comes from the verified source (G or I): the renderer never returned a receipt."""

    grant: ExecutionGrant
    render_attempt_id: str
    context: CommandContext
    expected_sha256: str | None = None
    orphan_after_seconds: int | None = None

    def __post_init__(self) -> None:
        _text('render_attempt_id', self.render_attempt_id)
        if self.orphan_after_seconds is not None and (type(self.orphan_after_seconds) is not int or self.orphan_after_seconds < 0):
            raise ValueError('orphan_after_seconds must be a non-negative int or None')


@dataclasses.dataclass(frozen=True)
class RenderResult:
    """problem is set for FAILED and OUTCOME_UNKNOWN attempts and carries codes only, never renderer text. output_sha256 is the lower-case sha256 that _verify matched against the observed file; it is set only by a render that just SUCCEEDED and is None for FAILED, OUTCOME_UNKNOWN, replayed and reconciled results."""

    attempt: RenderAttempt
    replayed: bool
    problem: ProblemDetail | None = None
    output_sha256: str | None = None


_SHA256_RE = re.compile(r'[0-9A-Fa-f]{64}')
_OUTCOMES = MappingProxyType({
    OperationState.SUCCEEDED: 'render_succeeded',
    OperationState.FAILED: 'render_failed',
    OperationState.OUTCOME_UNKNOWN: 'render_outcome_unknown',
})
_RECONCILE_OUTCOMES = MappingProxyType({
    OperationState.SUCCEEDED: 'reconcile_succeeded',
    OperationState.FAILED: 'reconcile_failed',
    OperationState.OUTCOME_UNKNOWN: 'reconcile_outcome_unknown',
})


class RenderUnitOfWork(PackageUnitOfWork, Protocol):
    """F-17 unit of work plus the index of attempt ids by package_fingerprint."""

    attempt_index: Any


class _AttemptIndexTable(_Table):
    def add(self, package_fingerprint: str, attempt_id: str) -> None:
        self._write()
        current = self._rows.get(package_fingerprint, ())
        if attempt_id not in current:
            self._rows[package_fingerprint] = current + (attempt_id,)

    def ids(self, package_fingerprint: str) -> tuple[str, ...]:
        return self._rows.get(package_fingerprint, ())


class InMemoryRenderUnitOfWork(InMemoryPackageUnitOfWork):
    """F-17 unit of work plus the attempt index of F-18; rollback covers it. Test and fixture use only."""

    def __init__(self) -> None:
        super().__init__()
        self.attempt_index = _AttemptIndexTable(self)
        self._tables = (*self._tables, self.attempt_index)


def _problem(
    code: str, title: str, detail: str, command_name: str, context: CommandContext, *, category: str, retryable: bool, status: int,
) -> ProblemDetail:
    slug = code.lower().replace('_', '-')
    return ProblemDetail.create(
        type=f'urn:render:problem:{slug}', title=title, detail=detail, instance=f'urn:render:command:{command_name}', code=code,
        category=category, retryable=retryable, correlation_id=context.correlation_id, status=status,
    )


def _reject(
    kind: type[PipelineRejected], code: str, title: str, detail: str, command_name: str, context: CommandContext,
    *, category: str = 'conflict', retryable: bool = False, status: int = 409,
) -> PipelineRejected:
    return kind(code, _problem(code, title, detail, command_name, context, category=category, retryable=retryable, status=status))


def _moment(context: CommandContext) -> datetime.datetime:
    return datetime.datetime.fromisoformat(context.occurred_at)


def _sha(value: object) -> str | None:
    return value.lower() if isinstance(value, str) and _SHA256_RE.fullmatch(value) else None


def _measured(metrics: RendererMetrics) -> dict[str, Any]:
    return {
        'wall_time_ms': metrics.wall_time_ms, 'cpu_metrics': metrics.cpu_metrics, 'gpu_metrics': metrics.gpu_metrics,
        'peak_disk_bytes': metrics.peak_disk_bytes,
    }


def _store(uow: Any, attempt: RenderAttempt) -> None:
    current = uow.renders.latest(KIND_ATTEMPT, attempt.render_attempt_id)
    uow.renders.append(KIND_ATTEMPT, attempt.render_attempt_id, 1 if current is None else current.revision + 1, attempt)


def _trace(uow: Any, attempt: RenderAttempt, command_name: str, grant: ExecutionGrant, context: CommandContext, outcome: str) -> None:
    uow.traces.append(CommandTrace(
        sequence=0, command=command_name, workspace_id=context.workspace_id, operation_key=attempt.render_attempt_id,
        correlation_id=context.correlation_id, actor=context.actor, occurred_at=context.occurred_at, receipt_ref=attempt.receipt_ref,
        grant_id=grant.operation_id, execution_generation=grant.execution_generation, subject_ref=attempt.render_attempt_id,
        outcome=outcome,
    ))


def _completed_event(uow: Any, attempt: RenderAttempt, grant: ExecutionGrant, context: CommandContext) -> None:
    """RenderCompleted for a SUCCEEDED attempt, written to the outbox of the same unit of work."""
    key = f'{attempt.render_attempt_id}-{attempt.revision}'
    event = build_render_completed(
        EventContext(
            workspace_id=context.workspace_id, correlation_id=context.correlation_id, actor=context.actor,
            occurred_at=context.occurred_at, recovery_epoch=str(grant.recovery_epoch), event_id=f'evt-render-completed-{key}',
            message_id=f'msg-render-completed-{key}', causation_id=attempt.receipt_ref,
        ),
        attempt=attempt,
    )
    uow.outbox.append_event(event.event_name, event.aggregate_id, event.payload, deduplication_id_for(event))


def _problem_for(attempt: RenderAttempt, command_name: str, context: CommandContext) -> ProblemDetail | None:
    if attempt.receipt_state is OperationState.FAILED:
        return _problem(
            RENDER_ATTEMPT_FAILED, 'Render attempt failed', 'The render attempt failed; the redacted error is in the stored attempt.',
            command_name, context, category='dependency', retryable=True, status=502,
        )
    if attempt.receipt_state is OperationState.OUTCOME_UNKNOWN:
        return _problem(
            RENDER_OUTCOME_UNKNOWN, 'Render outcome unknown', 'The render outcome is unknown; reconcile the attempt before any retry.',
            command_name, context, category='dependency', retryable=False, status=502,
        )
    return None


class RenderPipeline:
    def __init__(
        self, *, uow: RenderUnitOfWork, renderer: RendererPort, lease: GpuLeasePort, probe: OutputProbePort,
        observer: OutputObservationPort, grants: GrantCurrencyPort,
    ) -> None:
        self._uow = uow
        self._renderer = renderer
        self._lease = lease
        self._probe = probe
        self._observer = observer
        self._grants = grants

    def _require_current_grant(self, command_name: str, grant: object, context: CommandContext) -> None:
        if isinstance(grant, ExecutionGrant) and grant.workspace_id == context.workspace_id and self._grants.is_grant_current(grant):
            return
        raise _reject(StaleGrant, STALE_GRANT, 'Stale execution grant', 'The execution grant is not current for this workspace.', command_name, context)

    def _attempts(self, uow: Any, package: RenderPackageRecord) -> tuple[RenderAttempt, ...]:
        ids = uow.attempt_index.ids(package.package_fingerprint)
        return tuple(uow.renders.latest(KIND_ATTEMPT, attempt_id).record for attempt_id in ids)

    def _gate(self, uow: Any, command: RenderVideoCommand) -> RenderPackageRecord:
        """Read-only checks before any lease: stored package, passing report for its fingerprint, no unfinished earlier attempt."""
        context = command.context
        stored = uow.renders.latest(KIND_PACKAGE, command.render_package_id)
        if stored is None:
            raise RenderPackageNotFound(command.render_package_id)
        package = stored.record
        report = uow.reports.latest(package.package_fingerprint)
        fresh = None if command.validation_context is None else validate_render_package(package, command.validation_context)
        if report is None or report.package_fingerprint != package.package_fingerprint or not report.passed or (fresh is not None and not fresh.passed):
            raise _reject(
                PackageNotValidated, PACKAGE_NOT_VALIDATED, 'Package not validated',
                'The render package has no passing validation report for its fingerprint.', COMMAND_RENDER, context,
            )
        for attempt in self._attempts(uow, package):
            if attempt.receipt_state is OperationState.OUTCOME_UNKNOWN:
                raise _reject(
                    ReconcileRequired, RECONCILE_REQUIRED, 'Reconcile required',
                    'An earlier attempt has an unknown outcome; reconcile it before a new attempt.', COMMAND_RENDER, context,
                )
            if attempt.receipt_state in (OperationState.PREPARED, OperationState.STARTED):
                raise _reject(
                    AttemptInProgress, ATTEMPT_IN_PROGRESS, 'Attempt in progress',
                    'An earlier attempt of this package has not finished.', COMMAND_RENDER, context,
                )
        return package

    def _begin(self, command: RenderVideoCommand) -> RenderAttempt:
        """Unit of work 1: PREPARED then STARTED are stored and committed before the renderer is called."""
        with self._uow as uow:
            package = self._gate(uow, command)
            previous = tuple(item.output_artifact_ref for item in self._attempts(uow, package))
            prepared = prepare_attempt(
                render_attempt_id=command.render_attempt_id, package_fingerprint=package.package_fingerprint,
                output_artifact_ref=command.output_artifact_ref, command_spec=command.command_spec,
                receipt_ref=command.receipt_ref, previous_output_artifact_refs=previous,
            )
            _store(uow, prepared)
            started = start_attempt(prepared, expected_revision=prepared.revision, started_at=_moment(command.context))
            _store(uow, started)
            uow.attempt_index.add(package.package_fingerprint, started.render_attempt_id)
            uow.commit()
        return started

    def render_video(self, command: RenderVideoCommand) -> RenderResult:
        """Grant, replay by render_attempt_id, gates, GPU lease; the lease is returned in every case, including an exception."""
        context = command.context
        self._require_current_grant(COMMAND_RENDER, command.grant, context)
        with self._uow as uow:
            stored = uow.renders.latest(KIND_ATTEMPT, command.render_attempt_id)
            if stored is not None:
                return RenderResult(stored.record, True, _problem_for(stored.record, COMMAND_RENDER, context))
            self._gate(uow, command)
        try:
            lease = self._lease.acquire(command.render_attempt_id)
        except GpuLeaseWaitExpired:
            raise _reject(
                GpuLeaseNotAvailable, GPU_LEASE_WAIT_EXPIRED, 'GPU lease wait expired',
                'No GPU slot became free within the wait limit; nothing was rendered.',
                COMMAND_RENDER, context, category='capacity', retryable=False, status=503,
            ) from None
        except GpuLeaseUnavailable:
            raise _reject(
                GpuLeaseNotAvailable, GPU_LEASE_UNAVAILABLE, 'GPU lease unavailable', 'No GPU slot is free; try again later.',
                COMMAND_RENDER, context, category='capacity', retryable=True, status=503,
            ) from None
        try:
            started = self._begin(command)
            final, output_sha256 = self._finish(command, started, lease)
            self._settle(command, final)
        finally:
            self._lease.release(lease)
        return RenderResult(final, False, _problem_for(final, COMMAND_RENDER, context), output_sha256=output_sha256)

    def _verify(self, started: RenderAttempt, outcome: RendererOutcome) -> tuple[str | None, str | None]:
        """(None, sha256) when the output exists, its observed sha256 equals the claimed one and the probe says decodable; sha256 is the lower-case hash that matched. Otherwise (static reason, None)."""
        target_ref = started.output_artifact_ref
        if outcome.output_ref != target_ref:
            norm_outcome = outcome.output_ref.replace(chr(92), '/') if outcome.output_ref else ''
            norm_target = target_ref.replace(chr(92), '/')
            if norm_outcome and (norm_outcome.endswith('/' + norm_target) or norm_outcome.endswith(norm_target)):
                target_ref = outcome.output_ref
            else:
                return REASON_OUTPUT_REF_MISMATCH, None
        seen = self._observer.observe(target_ref)
        if not seen.exists:
            return REASON_OUTPUT_MISSING, None
        claimed = _sha(outcome.sha256)
        if claimed is None or claimed != _sha(seen.sha256):
            return REASON_OUTPUT_HASH_MISMATCH, None
        if self._probe.probe(target_ref).decodable is not True:
            return REASON_OUTPUT_NOT_DECODABLE, None
        return None, claimed

    def _settle(self, command: RenderVideoCommand, final: RenderAttempt) -> None:
        """Unit of work 2: the final attempt, RenderCompleted (SUCCEEDED only) and the trace commit together."""
        with self._uow as uow:
            _store(uow, final)
            if final.receipt_state is OperationState.SUCCEEDED:
                _completed_event(uow, final, command.grant, command.context)
            _trace(uow, final, COMMAND_RENDER, command.grant, command.context, _OUTCOMES[final.receipt_state])
            uow.commit()

    def _run_renderer(self, spec: RenderCommandSpec, lease: GpuLease) -> RendererOutcome:
        """The lease taken in render_video is the only one; a renderer that declares takes_held_lease receives it and never acquires a second slot."""
        if getattr(self._renderer, 'takes_held_lease', False) is True:
            return self._renderer.run(spec, lease=lease)
        return self._renderer.run(spec)

    def _finish(self, command: RenderVideoCommand, started: RenderAttempt, lease: GpuLease) -> tuple[RenderAttempt, str | None]:
        """Run the renderer outside any unit of work and turn what it did into the final attempt and, for SUCCEEDED only, the sha256 verified by _verify; nothing is stored here."""
        secrets = command.secret_values
        finished_at = _moment(command.context)
        revision = started.revision
        try:
            outcome = self._run_renderer(command.command_spec, lease)
        except RendererTimeout:
            return mark_outcome_unknown(started, expected_revision=revision, reason=REASON_TIMEOUT, secret_values=secrets), None
        except Exception as error:
            text = f'{REASON_RENDERER_CRASHED}: {type(error).__name__}: {error}'
            return fail_attempt(started, expected_revision=revision, finished_at=finished_at, error=text, secret_values=secrets), None
        if not isinstance(outcome, RendererOutcome) or not isinstance(outcome.metrics, RendererMetrics):
            return fail_attempt(
                started, expected_revision=revision, finished_at=finished_at, error=REASON_OUTCOME_INVALID, secret_values=secrets,
            ), None
        measured = _measured(outcome.metrics)
        if outcome.status is not RendererStatus.SUCCEEDED:
            detail = f': {outcome.error}' if isinstance(outcome.error, str) and outcome.error.strip() else ''
            return fail_attempt(
                started, expected_revision=revision, finished_at=finished_at, error=REASON_RENDERER_FAILED + detail,
                secret_values=secrets, **measured,
            ), None
        reason, verified_sha256 = self._verify(started, outcome)
        if reason is not None:
            return fail_attempt(
                started, expected_revision=revision, finished_at=finished_at, error=reason, secret_values=secrets, **measured,
            ), None
        return succeed_attempt(started, expected_revision=revision, finished_at=finished_at, secret_values=secrets, **measured), verified_sha256

    def _evidence(self, attempt: RenderAttempt, command: ReconcileRenderCommand) -> ProbeEvidence:
        ref = attempt.output_artifact_ref
        seen = self._observer.observe(ref)
        measured = self._probe.probe(ref)
        digest = hashlib.sha256(f'{ref}:{attempt.revision}'.encode('utf-8')).hexdigest()[:32]
        return ProbeEvidence(
            output_artifact_ref=ref, exists=seen.exists, sha256=seen.sha256, expected_sha256=command.expected_sha256,
            playable=measured.decodable, evidence_ref=f'probe-{digest}', observed_at=_moment(command.context),
        )

    def reconcile_render(self, command: ReconcileRenderCommand) -> RenderResult:
        """Probe first, then resolve an OUTCOME_UNKNOWN attempt; inconclusive evidence keeps it OUTCOME_UNKNOWN and writes nothing."""
        context = command.context
        self._require_current_grant(COMMAND_RECONCILE, command.grant, context)
        stored = self._uow.renders.latest(KIND_ATTEMPT, command.render_attempt_id)
        if stored is None:
            raise RenderAttemptNotFound(command.render_attempt_id)
        attempt = stored.record
        adopted: RenderAttempt | None = None
        if attempt.receipt_state is OperationState.STARTED and command.orphan_after_seconds is not None:
            moment = _moment(context)
            age = command.orphan_after_seconds if attempt.started_at is None else (moment - attempt.started_at).total_seconds()
            if age < command.orphan_after_seconds:
                raise _reject(
                    AttemptInProgress, ATTEMPT_IN_PROGRESS, 'Attempt in progress',
                    'The started attempt is younger than the orphan limit; its worker may still run.', COMMAND_RECONCILE, context,
                )
            adopted = mark_outcome_unknown(attempt, expected_revision=attempt.revision, reason=REASON_WORKER_LOST, finished_at=moment)
            attempt = adopted
        if attempt.receipt_state is not OperationState.OUTCOME_UNKNOWN:
            raise _reject(
                ReconcileNotNeeded, RECONCILE_NOT_NEEDED, 'Reconcile not needed',
                'Only an attempt with an unknown outcome is reconciled.', COMMAND_RECONCILE, context,
            )
        resolved = reconcile_attempt(attempt, self._evidence(attempt, command))
        if adopted is not None or resolved is not attempt:
            with self._uow as uow:
                if adopted is not None:
                    _store(uow, adopted)
                if resolved is not attempt:
                    _store(uow, resolved)
                if resolved.receipt_state is OperationState.SUCCEEDED:
                    _completed_event(uow, resolved, command.grant, context)
                _trace(uow, resolved, COMMAND_RECONCILE, command.grant, context, _RECONCILE_OUTCOMES[resolved.receipt_state])
                uow.commit()
        return RenderResult(resolved, False, _problem_for(resolved, COMMAND_RECONCILE, context))


__all__ = [
    'COMMAND_RECONCILE', 'COMMAND_RENDER', 'AttemptInProgress', 'GpuLeaseNotAvailable', 'InMemoryRenderUnitOfWork',
    'PackageNotValidated', 'ReconcileNotNeeded', 'ReconcileRenderCommand', 'ReconcileRequired', 'RenderAttemptNotFound',
    'RenderPipeline', 'RenderResult', 'RenderUnitOfWork', 'RenderVideoCommand',
]
