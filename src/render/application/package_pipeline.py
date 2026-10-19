"""F-17: ResolveRenderPackage and ValidateRenderPackage command handlers (CT-RND-002, CT-RND-003, TST-CTR-INV-001).

Application layer of F: render domain, render ports and controlplane types only; no I/O, no clock, no renderer, no other module.
Each command is one unit of work holding the record, the OperationState receipt and the trace; all commit together or none does.
Idempotency is by (workspace_id, command, operation_key) with request_hash: the same payload returns the stored receipt, another payload is IDEMPOTENCY_CONFLICT.
A grant that G no longer reports current is refused before any read or write. A failed validation report is a stored result, not a command failure.
F-16 has no record kind for reports, receipts or traces, so this module extends the F-16 in-memory unit of work; PostgreSQL waits for CONV-F-01.

coveredIds: TST-CTR-INV-001, TST-INT-INV-008, TST-MEDIA-INV-007, CT-RND-002, CT-RND-003
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from enum import Enum
from typing import Any, Protocol

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState, transition_operation
from render.adapters.memory import InMemoryUnitOfWork, _Table
from render.domain.package_contract import RenderPackageRecord
from render.domain.resolve_package import resolve_render_package
from render.domain.validate_package import (
    PackageValidationReport, ValidationContext, require_valid_package, validate_render_package,
)
from render.ports.inputs import PlanAssetPort, ResolveInputs
from render.ports.repositories import KIND_PACKAGE, DuplicateRecordError, RenderRepository

COMMAND_RESOLVE = 'ResolveRenderPackage'
COMMAND_VALIDATE = 'ValidateRenderPackage'
IDEMPOTENCY_CONFLICT = 'IDEMPOTENCY_CONFLICT'
STALE_GRANT = 'STALE_GRANT'
RENDER_PACKAGE_NOT_FOUND = 'RENDER_PACKAGE_NOT_FOUND'
VALIDATION_REPORT_MISSING = 'VALIDATION_REPORT_MISSING'
OUTCOME_PACKAGE_RESOLVED = 'package_resolved'
OUTCOME_VALIDATION_PASSED = 'validation_passed'
OUTCOME_VALIDATION_FAILED = 'validation_failed'


class PipelineRejected(Exception):
    """A command was refused before any write; `problem` is the structured ProblemDetail and carries no payload text."""

    def __init__(self, code: str, problem: ProblemDetail) -> None:
        super().__init__(code)
        self.code = code
        self.problem = problem


class IdempotencyConflict(PipelineRejected):
    """The operation_key is already bound to another request_hash."""


class StaleGrant(PipelineRejected):
    """The grant is not an ExecutionGrant of this workspace, or G no longer reports it current (old generation, old recovery epoch or expired)."""


class RenderPackageNotFound(LookupError):
    def __init__(self, render_package_id: str) -> None:
        super().__init__(f'{RENDER_PACKAGE_NOT_FOUND}: {render_package_id}')
        self.code = RENDER_PACKAGE_NOT_FOUND
        self.render_package_id = render_package_id


class ValidationReportMissing(LookupError):
    def __init__(self, package_fingerprint: str) -> None:
        super().__init__(f'{VALIDATION_REPORT_MISSING}: {package_fingerprint}')
        self.code = VALIDATION_REPORT_MISSING
        self.package_fingerprint = package_fingerprint


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommandContext:
    workspace_id: str
    correlation_id: str
    actor: str
    occurred_at: str

    def __post_init__(self) -> None:
        for name in ('workspace_id', 'correlation_id', 'actor', 'occurred_at'):
            _text(name, getattr(self, name))


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResolveRenderPackageCommand:
    operation_key: str
    grant: ExecutionGrant
    inputs: ResolveInputs
    context: CommandContext

    def __post_init__(self) -> None:
        _text('operation_key', self.operation_key)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ValidateRenderPackageCommand:
    operation_key: str
    grant: ExecutionGrant
    render_package_id: str
    validation_context: ValidationContext | None
    context: CommandContext

    def __post_init__(self) -> None:
        _text('operation_key', self.operation_key)
        _text('render_package_id', self.render_package_id)


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommandReceipt:
    command: str
    workspace_id: str
    operation_key: str
    request_hash: str
    receipt_ref: str
    state: OperationState
    revision: int
    render_package_id: str
    package_fingerprint: str
    report_id: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommandTrace:
    """Audit trail of one command: ids and outcome only, never payload text, paths or secrets."""

    sequence: int
    command: str
    workspace_id: str
    operation_key: str
    correlation_id: str
    actor: str
    occurred_at: str
    receipt_ref: str
    grant_id: str
    execution_generation: int
    subject_ref: str
    outcome: str


@dataclasses.dataclass(frozen=True)
class ResolveOutcome:
    receipt: CommandReceipt
    package: RenderPackageRecord
    replayed: bool


@dataclasses.dataclass(frozen=True)
class ValidateOutcome:
    receipt: CommandReceipt
    report: PackageValidationReport
    replayed: bool


class GrantCurrencyPort(Protocol):
    """G owns ExecutionGrant; F asks whether a grant (generation, recovery epoch, expiry) is still current before any work."""

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        ...


class PackageUnitOfWork(Protocol):
    """Records, reports, receipts, traces and outbox share one transaction."""

    renders: RenderRepository
    outbox: IOutboxWriter
    reports: Any
    receipts: Any
    traces: Any

    def __enter__(self) -> Any: ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    def commit(self) -> None: ...


class _ReceiptTable(_Table):
    def add(self, receipt: CommandReceipt) -> None:
        self._write()
        key = (receipt.workspace_id, receipt.command, receipt.operation_key)
        if key in self._rows:
            raise DuplicateRecordError('receipt already stored for this operation_key')
        self._rows[key] = receipt

    def get(self, workspace_id: str, command: str, operation_key: str) -> CommandReceipt | None:
        return self._rows.get((workspace_id, command, operation_key))

    def records(self) -> tuple[CommandReceipt, ...]:
        return tuple(self._rows.values())


class _ReportTable(_Table):
    """Append-only reports by package_fingerprint; an identical report_id directly after itself is not stored twice."""

    def append(self, report: PackageValidationReport) -> int:
        self._write()
        if not isinstance(report, PackageValidationReport):
            raise TypeError('report must be a PackageValidationReport')
        current = self._rows.get(report.package_fingerprint, ())
        if current and current[-1].report_id == report.report_id:
            return len(current)
        self._rows[report.package_fingerprint] = current + (report,)
        return len(current) + 1

    def latest(self, package_fingerprint: str) -> PackageValidationReport | None:
        current = self._rows.get(package_fingerprint)
        return current[-1] if current else None

    def revisions(self, package_fingerprint: str) -> tuple[PackageValidationReport, ...]:
        return self._rows.get(package_fingerprint, ())

    def by_id(self, package_fingerprint: str, report_id: str) -> PackageValidationReport | None:
        for report in self._rows.get(package_fingerprint, ()):
            if report.report_id == report_id:
                return report
        return None


class _TraceTable(_Table):
    def append(self, trace: CommandTrace) -> None:
        self._write()
        sequence = len(self._rows) + 1
        self._rows[sequence] = dataclasses.replace(trace, sequence=sequence)

    def records(self) -> tuple[CommandTrace, ...]:
        return tuple(self._rows.values())


class InMemoryPackageUnitOfWork(InMemoryUnitOfWork):
    """F-16 unit of work plus the report, receipt and trace tables of F-17; rollback covers all of them. Test and fixture use only."""

    def __init__(self) -> None:
        super().__init__()
        self.reports = _ReportTable(self)
        self.receipts = _ReceiptTable(self)
        self.traces = _TraceTable(self)
        self._tables = (*self._tables, self.reports, self.receipts, self.traces)


def _plain(value: object) -> object:
    """Plain JSON-compatible copy of a command value for request_hash; an unsupported type becomes a type-name marker so hashing never raises."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, Enum):
        return _plain(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: _plain(getattr(value, item.name)) for item in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(child) for child in value), key=repr)
    if isinstance(value, (list, tuple)):
        return [_plain(child) for child in value]
    return {'unsupported_type': type(value).__name__}


def _context_payload(validation_context: object) -> dict[str, object]:
    """Hash basis of the validation inputs; a context that is not a ValidationContext counts as empty, like validate_render_package."""
    ctx = validation_context if isinstance(validation_context, ValidationContext) else ValidationContext()
    return {
        'voice': _plain(ctx.voice),
        'word_timing': _plain(ctx.word_timing),
        'verified': _plain(ctx.verified),
        'issued_paths': _plain(ctx.issued_paths),
        'language_evidence': _plain(ctx.language_evidence),
        'language_policy': _plain(ctx.language_policy),
        'preset_requirements': _plain(getattr(ctx.preset, 'compatibility_requirements', None)),
        'capability': _plain(ctx.capability),
    }


def _digest(command_name: str, context: CommandContext, request: object) -> str:
    return request_hash({'command': command_name, 'workspace_id': context.workspace_id, 'request': request})


def _rejected(kind: type[PipelineRejected], code: str, title: str, detail: str, command_name: str, context: CommandContext) -> PipelineRejected:
    slug = code.lower().replace('_', '-')
    problem = ProblemDetail.create(
        type=f'urn:render:problem:{slug}',
        title=title,
        detail=detail,
        instance=f'urn:render:command:{command_name}',
        code=code,
        category='conflict',
        retryable=False,
        correlation_id=context.correlation_id,
        status=409,
    )
    return kind(code, problem)


class PackagePipeline:
    def __init__(self, *, uow: PackageUnitOfWork, plan_assets: PlanAssetPort, grants: GrantCurrencyPort) -> None:
        self._uow = uow
        self._plan_assets = plan_assets
        self._grants = grants

    def _require_current_grant(self, command_name: str, grant: object, context: CommandContext) -> None:
        if isinstance(grant, ExecutionGrant) and grant.workspace_id == context.workspace_id and self._grants.is_grant_current(grant):
            return
        raise _rejected(StaleGrant, STALE_GRANT, 'Stale execution grant', 'The execution grant is not current for this workspace.', command_name, context)

    def _replay(self, uow: Any, command_name: str, context: CommandContext, operation_key: str, digest: str) -> CommandReceipt | None:
        stored = uow.receipts.get(context.workspace_id, command_name, operation_key)
        if stored is None:
            return None
        if stored.request_hash != digest:
            raise _rejected(IdempotencyConflict, IDEMPOTENCY_CONFLICT, 'Idempotency conflict', 'The operation key is already bound to another request.', command_name, context)
        return stored

    def _seal_receipt(self, command_name: str, context: CommandContext, operation_key: str, digest: str, **refs: str | None) -> CommandReceipt:
        started = transition_operation(current_state=OperationState.PREPARED, current_revision=0, expected_revision=0, requested_state=OperationState.STARTED)
        done = transition_operation(current_state=OperationState.STARTED, current_revision=started.revision, expected_revision=started.revision, requested_state=OperationState.SUCCEEDED)
        scope = request_hash({'scope': [context.workspace_id, command_name, operation_key], 'request_hash': digest})
        return CommandReceipt(command=command_name, workspace_id=context.workspace_id, operation_key=operation_key, request_hash=digest, receipt_ref=f'receipt-{scope[:32]}', state=OperationState(done.state), revision=done.revision, **refs)

    def _trace(self, uow: Any, receipt: CommandReceipt, grant: ExecutionGrant, context: CommandContext, subject_ref: str, outcome: str) -> None:
        uow.traces.append(CommandTrace(
            sequence=0, command=receipt.command, workspace_id=receipt.workspace_id, operation_key=receipt.operation_key,
            correlation_id=context.correlation_id, actor=context.actor, occurred_at=context.occurred_at, receipt_ref=receipt.receipt_ref,
            grant_id=grant.operation_id, execution_generation=grant.execution_generation, subject_ref=subject_ref, outcome=outcome,
        ))

    def resolve_render_package(self, command: ResolveRenderPackageCommand) -> ResolveOutcome:
        """One unit of work: grant check first, then replay or conflict by request_hash, then package, receipt and trace; a ResolveError writes nothing."""
        context = command.context
        self._require_current_grant(COMMAND_RESOLVE, command.grant, context)
        digest = _digest(COMMAND_RESOLVE, context, _plain(command.inputs))
        with self._uow as uow:
            replayed = self._replay(uow, COMMAND_RESOLVE, context, command.operation_key, digest)
            if replayed is not None:
                return ResolveOutcome(replayed, uow.renders.latest(KIND_PACKAGE, replayed.render_package_id).record, True)
            package = resolve_render_package(command.inputs, self._plan_assets)
            if uow.renders.latest(KIND_PACKAGE, package.render_package_id) is None:
                uow.renders.append(KIND_PACKAGE, package.render_package_id, 1, package)
            receipt = self._seal_receipt(
                COMMAND_RESOLVE, context, command.operation_key, digest,
                render_package_id=package.render_package_id, package_fingerprint=package.package_fingerprint,
            )
            uow.receipts.add(receipt)
            self._trace(uow, receipt, command.grant, context, package.render_package_id, OUTCOME_PACKAGE_RESOLVED)
            uow.commit()
        return ResolveOutcome(receipt, package, False)

    def validate_render_package(self, command: ValidateRenderPackageCommand) -> ValidateOutcome:
        """One unit of work: grant check first, then the stored package, replay or conflict, then report, receipt and trace; a failed report is stored and the command still succeeds."""
        context = command.context
        self._require_current_grant(COMMAND_VALIDATE, command.grant, context)
        with self._uow as uow:
            stored = uow.renders.latest(KIND_PACKAGE, command.render_package_id)
            if stored is None:
                raise RenderPackageNotFound(command.render_package_id)
            package = stored.record
            digest = _digest(COMMAND_VALIDATE, context, {
                'render_package_id': package.render_package_id,
                'package_fingerprint': package.package_fingerprint,
                'validation_context': _context_payload(command.validation_context),
            })
            replayed = self._replay(uow, COMMAND_VALIDATE, context, command.operation_key, digest)
            if replayed is not None:
                return ValidateOutcome(replayed, uow.reports.by_id(replayed.package_fingerprint, replayed.report_id), True)
            report = validate_render_package(package, command.validation_context)
            uow.reports.append(report)
            receipt = self._seal_receipt(
                COMMAND_VALIDATE, context, command.operation_key, digest,
                render_package_id=package.render_package_id, package_fingerprint=package.package_fingerprint, report_id=report.report_id,
            )
            uow.receipts.add(receipt)
            outcome = OUTCOME_VALIDATION_PASSED if report.passed else OUTCOME_VALIDATION_FAILED
            self._trace(uow, receipt, command.grant, context, report.report_id, outcome)
            uow.commit()
        return ValidateOutcome(receipt, report, False)

    def require_renderable(self, render_package_id: str) -> RenderPackageRecord:
        """Gate before any renderer call: the newest stored report of the package must have passed; reads only, no write."""
        stored = self._uow.renders.latest(KIND_PACKAGE, render_package_id)
        if stored is None:
            raise RenderPackageNotFound(render_package_id)
        report = self._uow.reports.latest(stored.record.package_fingerprint)
        if report is None:
            raise ValidationReportMissing(stored.record.package_fingerprint)
        require_valid_package(report)
        return stored.record


__all__ = [
    'COMMAND_RESOLVE', 'COMMAND_VALIDATE', 'CommandContext', 'CommandReceipt', 'CommandTrace', 'GrantCurrencyPort',
    'IDEMPOTENCY_CONFLICT', 'IdempotencyConflict', 'InMemoryPackageUnitOfWork', 'PackagePipeline', 'PackageUnitOfWork',
    'PipelineRejected', 'RENDER_PACKAGE_NOT_FOUND', 'RenderPackageNotFound', 'ResolveOutcome', 'ResolveRenderPackageCommand',
    'STALE_GRANT', 'StaleGrant', 'VALIDATION_REPORT_MISSING', 'ValidateOutcome', 'ValidateRenderPackageCommand',
    'ValidationReportMissing',
]
