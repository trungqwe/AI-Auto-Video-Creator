"""Worker activity handler of module F for workflow G (F-20; CT-WF-003, CT-WF-006).

Receives an ActivityRequest with a controlplane ExecutionGrant, runs exactly the one F-17/F-18/F-19 command named by
activity_name and returns an ActivityResult. Temporal registration, the WAITING_CAPABILITY precondition for the desktop and
the GPU slot, and the choice of the next stage belong to workflow G (CONV-F-05): this module imports no workflow runtime, UI,
API, creative, voice or catalog code, never waits and never starts a second stage. Results are built from codes, refs and
counters only, so no exception text or secret reaches a result.
"""
from __future__ import annotations

import copy
import datetime
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState
from render.application.inspect_output import InspectOutcome, InspectOutputCommand, OutputPipeline, OutputReadyOutcome, PrepareOutputReadyCommand
from render.application.package_pipeline import (
    STALE_GRANT, GrantCurrencyPort, IdempotencyConflict, PackagePipeline, PipelineRejected, ResolveOutcome,
    ResolveRenderPackageCommand, StaleGrant, ValidateOutcome, ValidateRenderPackageCommand,
)
from render.application.render_video import (
    RENDER_ATTEMPT_FAILED, RENDER_OUTCOME_UNKNOWN, GpuLeaseNotAvailable, ReconcileRenderCommand, RenderPipeline, RenderResult,
    RenderVideoCommand,
)
from render.domain.quality_report import GATE_KINDS, GateKind, GateStatus

ACTIVITY_RESOLVE = 'resolve_render_package'
ACTIVITY_VALIDATE = 'validate_render_package'
ACTIVITY_RENDER = 'render_video'
ACTIVITY_RECONCILE = 'reconcile_render'
ACTIVITY_INSPECT = 'inspect_output'
ACTIVITY_PREPARE = 'prepare_output_ready'
REF_TYPE_PACKAGE = 'render_package'
REF_TYPE_VALIDATION_REPORT = 'package_validation_report'
REF_TYPE_ATTEMPT = 'render_attempt'
REF_TYPE_OUTPUT = 'render_output'
REF_TYPE_QUALITY_REPORT = 'quality_report'
REF_TYPE_VIDEO_OUTPUT = 'video_output'
VALIDATION_ERROR = 'VALIDATION_ERROR'
UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
OPERATION_KEY_CONFLICT = 'OPERATION_KEY_CONFLICT'
OPERATION_KEY_MISMATCH = 'OPERATION_KEY_MISMATCH'
GRANT_MISMATCH = 'GRANT_MISMATCH'
COMMAND_TYPE_MISMATCH = 'COMMAND_TYPE_MISMATCH'
ACTIVITY_ABORTED = 'ACTIVITY_ABORTED'
PACKAGE_VALIDATION_FAILED = 'package_validation_failed'
QUALITY_GATES_FAILED = 'quality_gates_failed'
OUTPUT_NOT_READY = 'output_not_ready'
NOTHING_TO_RECONCILE = 'nothing_to_reconcile'
REDACTED_WARNING = 'warning_redacted'
UNKNOWN_REF = 'unknown'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
OUTCOME_UNKNOWN = 'outcome_unknown'
STALE = 'stale'
Issue = tuple[str, str]


REQUEST_REQUIRED = MappingProxyType({
    'workflow_id': 'string',
    'workflow_run_id': 'string',
    'stage_run_id': 'string',
    'activity_name': 'string',
    'activity_version': 'string',
    'input_refs': 'array',
    'operation_key': 'string',
    'capability_requirements': 'object',
    'retry_policy_ref': 'string',
})
REQUEST_OPTIONAL = MappingProxyType({'video_job_id': 'string', 'execution_grant': 'object', 'deadline_at': 'string'})
REQUEST_FORBIDDEN = ('secret_value', 'raw_blob')
_SAFE_TOKEN_RE = re.compile(r'[A-Za-z0-9_.:-]{1,80}')
_SECRET_WORD_RE = re.compile(r'secret|token|password|passwd|bearer|api[_-]?key|credential', re.IGNORECASE)

# kind -> (ProblemDetail category, fixed detail); detail is never built from exception text
_PROBLEMS = MappingProxyType({
    'STALE_GRANT': ('conflict', 'execution grant or generation is no longer current; nothing was committed'),
    'UNKNOWN_ACTIVITY': ('validation', 'activity_name is not an activity of module F; nothing was run'),
    'OPERATION_KEY_CONFLICT': ('conflict', 'operation_key was already used for a different activity or input_refs'),
    'IDEMPOTENCY_CONFLICT': ('conflict', 'operation_key was already used with a different payload'),
    'COMMAND_REJECTED': ('validation', 'the F command rejected its input; nothing was committed'),
    'PIPELINE_REJECTED': ('conflict', 'a precondition of the F command is not met; nothing was committed'),
    'CAPACITY_UNAVAILABLE': ('capacity', 'no GPU slot is free; F did not wait and nothing was rendered'),
    'PACKAGE_VALIDATION_FAILED': ('validation', 'the render package has validation findings; the report is stored'),
    'QUALITY_GATES_FAILED': ('validation', 'the output failed its quality gates; the report is stored'),
    'OUTPUT_NOT_READY': ('conflict', 'the output is not ready for G; the reasons are in the stored receipt'),
    'RENDER_FAILED': ('dependency', 'the render attempt failed; the redacted error is in the stored attempt'),
    'OUTCOME_UNKNOWN': ('conflict', 'the render outcome is unknown and needs reconciliation by G'),
    'ACTIVITY_ABORTED': ('internal', 'the activity stopped on an unexpected error; retry with the same operation_key'),
})


class ActivityRequestError(Exception):
    """VALIDATION_ERROR: the request or grant is rejected before any grant check, lookup or write; no ActivityResult is built."""

    def __init__(self, code: str, issues: tuple[Issue, ...] | list[Issue] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.issues = tuple(issues)


class CommandMismatch(Exception):
    """The resolved command does not belong to this request (wrong type, another grant or another operation key); code is a fixed token."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ActivityInputPort(Protocol):
    """Resolves the input_refs of an ActivityRequest to the one F command of the activity.

    Returns {'command': <the F-17, F-18 or F-19 command object>}. The command carries the ExecutionGrant of the request and
    the operation_key of the request (for render_video the render_attempt_id is that operation_key). For reconcile_render it may return {'nothing_to_reconcile': True} instead of a command when the package has no open attempt.
    """

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> Mapping[str, Any]:
        ...


class InMemoryActivityResultStore:
    """Succeeded ActivityResults by (workspace_id, operation_key); fixture use until persistence in CONV-F-01 / CONV-F-05."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def get(self, workspace_id: str, operation_key: str) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        row = self._rows.get((workspace_id, operation_key))
        return None if row is None else (row[0], copy.deepcopy(row[1]))

    def put(self, workspace_id: str, operation_key: str, input_key: tuple[Any, ...], result: Mapping[str, Any]) -> None:
        self._rows.setdefault((workspace_id, operation_key), (input_key, copy.deepcopy(dict(result))))


@dataclass(frozen=True)
class RenderActivityDeps:
    package: PackagePipeline
    render: RenderPipeline
    output: OutputPipeline
    grants: GrantCurrencyPort
    inputs: ActivityInputPort
    clock: Callable[[], datetime.datetime]
    results: InMemoryActivityResultStore = field(default_factory=InMemoryActivityResultStore)


@dataclass(frozen=True)
class _Outcome:
    disposition: str
    output_refs: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] | None = None
    warnings: list[str] | None = None
    receipt_ref: str | None = None
    problem: tuple[str, str, bool] | None = None  # (kind, code, retryable)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_text(value: object, default: str) -> str:
    """A code-like token without secret words; free text, URLs and secrets fall back to the default."""
    if not isinstance(value, str) or not _SAFE_TOKEN_RE.fullmatch(value) or _SECRET_WORD_RE.search(value):
        return default
    return value


def _matches(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'object':
        return isinstance(value, Mapping)
    return isinstance(value, list)


def _request_issues(request: object) -> list[Issue]:
    if not isinstance(request, Mapping):
        return [('wrong_type', '$')]
    issues: list[Issue] = [('forbidden_field', name) for name in REQUEST_FORBIDDEN if name in request]
    for name, type_name in REQUEST_REQUIRED.items():
        if request.get(name) is None:
            issues.append(('missing_required', name))
        elif not _matches(request[name], type_name):
            issues.append(('wrong_type', name))
    for name, type_name in REQUEST_OPTIONAL.items():
        if request.get(name) is not None and not _matches(request[name], type_name):
            issues.append(('wrong_type', name))
    return issues


def _grant_issues(grant: object, stage_run_id: object) -> list[Issue]:
    if not isinstance(grant, ExecutionGrant):
        return [('wrong_type', 'execution_grant')]
    issues: list[Issue] = []
    for name in ('workspace_id', 'operation_id', 'job_id', 'stage_run_id'):
        if not _is_text(getattr(grant, name)):
            issues.append(('invalid_value', f'execution_grant.{name}'))
    for name in ('execution_generation', 'recovery_epoch'):
        value = getattr(grant, name)
        if type(value) is not int or value < 0:
            issues.append(('invalid_value', f'execution_grant.{name}'))
    if isinstance(stage_run_id, str) and _is_text(grant.stage_run_id) and grant.stage_run_id != stage_run_id:
        issues.append(('invalid_value', 'execution_grant.stage_run_id'))
    return issues


def _input_refs_valid(refs: object) -> bool:
    """A non-empty list of refs; how the refs map to command inputs is decided by the ActivityInputPort."""
    return (
        isinstance(refs, list)
        and bool(refs)
        and all(isinstance(ref, Mapping) and _is_text(ref.get('ref_type')) and _is_text(ref.get('ref_id')) for ref in refs)
    )


def _utc(moment: datetime.datetime) -> str:
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'


def _problem(request: Mapping[str, Any], grant: ExecutionGrant, kind: str, code: str, *, retryable: bool = False) -> dict[str, Any]:
    # fixed detail per kind, code token only; never exception text or secret
    category, detail = _PROBLEMS[kind]
    stage = _safe_text(grant.stage_run_id, UNKNOWN_REF)
    problem = ProblemDetail.create(
        type=f'urn:render:problem:{kind.lower()}',
        title=kind.replace('_', ' ').title(),
        detail=detail,
        instance=f'urn:stage-run:{stage}',
        code=code,
        category=category,
        retryable=retryable,
        correlation_id=_safe_text(request['workflow_run_id'], UNKNOWN_REF),
    )
    return dict(problem.values)


def _activity_result(request: Mapping[str, Any], grant: ExecutionGrant, deps: RenderActivityDeps, outcome: _Outcome) -> dict[str, Any]:
    # grant_id is ExecutionGrant.operation_id; recovery_epoch is its str (CONV-F-05)
    result: dict[str, Any] = {
        'stage_run_id': grant.stage_run_id,
        'grant_id': grant.operation_id,
        'execution_generation': grant.execution_generation,
        'recovery_epoch': str(grant.recovery_epoch),
        'disposition': outcome.disposition,
        'output_refs': outcome.output_refs,
        'completed_at': _utc(deps.clock()),
    }
    if outcome.metrics is not None:
        result['metrics'] = outcome.metrics
    if outcome.warnings is not None:
        result['warnings'] = outcome.warnings
    if outcome.receipt_ref is not None:
        result['operation_receipt_ref'] = outcome.receipt_ref
    if outcome.problem is not None:
        kind, code, retryable = outcome.problem
        result['problem'] = _problem(request, grant, kind, code, retryable=retryable)
    return result


def _rejected(
    request: Mapping[str, Any], grant: ExecutionGrant, deps: RenderActivityDeps, disposition: str, kind: str, code: str,
    *, retryable: bool = False,
) -> dict[str, Any]:
    return _activity_result(request, grant, deps, _Outcome(disposition, problem=(kind, code, retryable)))


def _metrics(**values: Any) -> dict[str, Any]:
    return {name: value for name, value in values.items() if value is not None}


def _resolve_outcome(outcome: ResolveOutcome) -> _Outcome:
    package = outcome.package
    return _Outcome(
        SUCCEEDED,
        [{'ref_type': REF_TYPE_PACKAGE, 'ref_id': package.render_package_id}],
        _metrics(input_artifact_count=len(package.input_artifacts), replayed=outcome.replayed),
        [],
        outcome.receipt.receipt_ref,
    )


def _validate_outcome(outcome: ValidateOutcome) -> _Outcome:
    # a failed report is a stored result of F-17; for G it is a failed activity that still names the stored report
    report = outcome.report
    refs = [{'ref_type': REF_TYPE_VALIDATION_REPORT, 'ref_id': report.report_id}]
    metrics = _metrics(finding_count=len(report.findings), replayed=outcome.replayed)
    if report.passed:
        return _Outcome(SUCCEEDED, refs, metrics, [], outcome.receipt.receipt_ref)
    return _Outcome(FAILED, refs, metrics, [], outcome.receipt.receipt_ref, ('PACKAGE_VALIDATION_FAILED', PACKAGE_VALIDATION_FAILED, False))


def _render_outcome(result: RenderResult) -> _Outcome:
    # the output ref is given only for a SUCCEEDED attempt; any state that is neither SUCCEEDED nor FAILED is outcome_unknown
    attempt = result.attempt
    refs = [{'ref_type': REF_TYPE_ATTEMPT, 'ref_id': attempt.render_attempt_id}]
    metrics = _metrics(wall_time_ms=attempt.wall_time_ms, peak_disk_bytes=attempt.peak_disk_bytes, replayed=result.replayed)
    warnings = [_safe_text(item, REDACTED_WARNING) for item in attempt.warnings]
    if attempt.receipt_state is OperationState.SUCCEEDED:
        refs.append({'ref_type': REF_TYPE_OUTPUT, 'ref_id': attempt.output_artifact_ref})
        return _Outcome(SUCCEEDED, refs, metrics, warnings, attempt.receipt_ref)
    if attempt.receipt_state is OperationState.FAILED:
        return _Outcome(FAILED, refs, metrics, warnings, attempt.receipt_ref, ('RENDER_FAILED', RENDER_ATTEMPT_FAILED, True))
    return _Outcome(OUTCOME_UNKNOWN, refs, metrics, warnings, attempt.receipt_ref, ('OUTCOME_UNKNOWN', RENDER_OUTCOME_UNKNOWN, False))


def _inspect_outcome(outcome: InspectOutcome) -> _Outcome:
    report = outcome.report
    blocking = [gate.value for gate in report.blocking_gates]
    refs = [{'ref_type': REF_TYPE_QUALITY_REPORT, 'ref_id': report.report_id}]
    metrics = _metrics(
        gate_count=len(report.gates), blocking_gate_count=len(blocking), blocking_gates=blocking, replayed=outcome.replayed,
    )
    warnings = [
        _safe_text(f'{item.gate.value}:{item.status.value}', REDACTED_WARNING)
        for item in report.gates
        if GATE_KINDS[item.gate] is GateKind.WARNING and item.status is not GateStatus.PASSED
    ]
    if report.passed:
        return _Outcome(SUCCEEDED, refs, metrics, warnings, outcome.receipt.receipt_ref)
    return _Outcome(FAILED, refs, metrics, warnings, outcome.receipt.receipt_ref, ('QUALITY_GATES_FAILED', QUALITY_GATES_FAILED, False))


def _reconcile_outcome(result: RenderResult) -> _Outcome:
    # a reconciled attempt is a definite answer for G: SUCCEEDED keeps its output, FAILED means a new attempt may follow; only a still unknown attempt stays outcome_unknown
    attempt = result.attempt
    if attempt.receipt_state is OperationState.FAILED:
        refs = [{'ref_type': REF_TYPE_ATTEMPT, 'ref_id': attempt.render_attempt_id}]
        return _Outcome(SUCCEEDED, refs, _metrics(reconciled_state='failed', replayed=result.replayed), [], attempt.receipt_ref)
    outcome = _render_outcome(result)
    if outcome.disposition == SUCCEEDED:
        return _Outcome(SUCCEEDED, outcome.output_refs, {**(outcome.metrics or {}), 'reconciled_state': 'succeeded'}, outcome.warnings, outcome.receipt_ref)
    return outcome


def _prepare_outcome(outcome: OutputReadyOutcome) -> _Outcome:
    receipt = outcome.receipt
    refs = [{'ref_type': REF_TYPE_QUALITY_REPORT, 'ref_id': receipt.report_id}]
    metrics = _metrics(ready=outcome.ready, reason_count=len(outcome.reasons), replayed=outcome.replayed)
    warnings = [_safe_text(reason, REDACTED_WARNING) for reason in outcome.reasons]
    if outcome.video_output is not None:
        refs.insert(0, {'ref_type': REF_TYPE_VIDEO_OUTPUT, 'ref_id': outcome.video_output.video_output_id})
        return _Outcome(SUCCEEDED, refs, metrics, warnings, receipt.receipt_ref)
    return _Outcome(FAILED, refs, metrics, warnings, receipt.receipt_ref, ('OUTPUT_NOT_READY', OUTPUT_NOT_READY, False))


def _command(inputs: Mapping[str, Any], kind: type, grant: ExecutionGrant, operation_key: str, key_field: str | None) -> Any:
    # the command must have the expected type, the grant of the request and the operation_key of the request
    command = inputs.get('command')
    if not isinstance(command, kind):
        raise CommandMismatch(COMMAND_TYPE_MISMATCH)
    if command.grant != grant:
        raise CommandMismatch(GRANT_MISMATCH)
    if key_field is not None and getattr(command, key_field) != operation_key:
        raise CommandMismatch(OPERATION_KEY_MISMATCH)
    return command


def _run_resolve(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    command = _command(inputs, ResolveRenderPackageCommand, grant, key, 'operation_key')
    return _resolve_outcome(deps.package.resolve_render_package(command))


def _run_validate(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    command = _command(inputs, ValidateRenderPackageCommand, grant, key, 'operation_key')
    return _validate_outcome(deps.package.validate_render_package(command))


def _run_reconcile(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    # nothing_to_reconcile: the input port found no STARTED or OUTCOME_UNKNOWN attempt of the package, so G may render
    if inputs.get(NOTHING_TO_RECONCILE) is True:
        return _Outcome(SUCCEEDED, [], _metrics(reconciled_state='none'), [])
    command = _command(inputs, ReconcileRenderCommand, grant, key, None)
    return _reconcile_outcome(deps.render.reconcile_render(command))


def _run_render(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    command = _command(inputs, RenderVideoCommand, grant, key, 'render_attempt_id')
    return _render_outcome(deps.render.render_video(command))


def _run_inspect(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    command = _command(inputs, InspectOutputCommand, grant, key, 'operation_key')
    return _inspect_outcome(deps.output.inspect_output(command))


def _run_prepare(deps: RenderActivityDeps, key: str, grant: ExecutionGrant, inputs: Mapping[str, Any]) -> _Outcome:
    command = _command(inputs, PrepareOutputReadyCommand, grant, key, 'operation_key')
    return _prepare_outcome(deps.output.prepare_output_ready(command))


# activity_name -> the one F-17/F-18/F-19 command it runs; no route chains to another one
_ROUTES = MappingProxyType({
    ACTIVITY_RESOLVE: _run_resolve,
    ACTIVITY_VALIDATE: _run_validate,
    ACTIVITY_RECONCILE: _run_reconcile,
    ACTIVITY_RENDER: _run_render,
    ACTIVITY_INSPECT: _run_inspect,
    ACTIVITY_PREPARE: _run_prepare,
})
ACTIVITY_NAMES = tuple(_ROUTES)


def _exception_result(request: Mapping[str, Any], grant: ExecutionGrant, deps: RenderActivityDeps, exc: Exception) -> dict[str, Any]:
    # map an exception of an F command or of the input port to a result built from its code token only, never its text
    if isinstance(exc, StaleGrant):
        return _rejected(request, grant, deps, STALE, 'STALE_GRANT', STALE_GRANT)
    raw = getattr(exc, 'code', None)
    code = _safe_text(raw, '') if isinstance(raw, str) else ''
    if not code:
        return _rejected(request, grant, deps, FAILED, 'ACTIVITY_ABORTED', ACTIVITY_ABORTED, retryable=True)
    if isinstance(exc, IdempotencyConflict):
        return _rejected(request, grant, deps, FAILED, 'IDEMPOTENCY_CONFLICT', code)
    if isinstance(exc, PipelineRejected):
        kind = 'CAPACITY_UNAVAILABLE' if isinstance(exc, GpuLeaseNotAvailable) else 'PIPELINE_REJECTED'
        return _rejected(request, grant, deps, FAILED, kind, code, retryable=exc.problem.values.get('retryable') is True)
    return _rejected(request, grant, deps, FAILED, 'COMMAND_REJECTED', code)


def validate_activity_request(request: object, grant: object) -> list[Issue]:
    """Return (code, field) issues of the ActivityRequest binding and of the typed ExecutionGrant; empty means valid.

    An unknown activity_name is not an issue here: handle_activity answers it with a structured problem.
    """
    issues = _request_issues(request)
    if not isinstance(request, Mapping):
        return issues
    invalid = {name for _, name in issues}
    issues.extend(_grant_issues(grant, request.get('stage_run_id')))
    if 'activity_name' not in invalid and not _is_text(request['activity_name']):
        issues.append(('invalid_value', 'activity_name'))
    if 'operation_key' not in invalid and not _is_text(request['operation_key']):
        issues.append(('invalid_value', 'operation_key'))
    if 'input_refs' not in invalid and not _input_refs_valid(request['input_refs']):
        issues.append(('invalid_value', 'input_refs'))
    return issues


def handle_activity(request: Mapping[str, Any], grant: ExecutionGrant, deps: RenderActivityDeps) -> dict[str, Any]:
    """Run the one F command named by activity_name for an ActivityRequest and return an ActivityResult (CT-WF-003, CT-WF-006).

    An invalid request or grant raises ActivityRequestError(VALIDATION_ERROR) and builds no result. A grant that the grant
    port no longer reports current (old execution_generation or recovery_epoch) gives a 'stale' result before any input
    lookup, command or write. Only a 'succeeded' result is stored under (workspace_id, operation_key): the same key returns
    it, re-stamped with the identity of the current grant, without running the command again; the same key for another
    activity or input_refs is OPERATION_KEY_CONFLICT. An unknown activity_name gives a failed result with a structured
    problem. Exactly one command runs per call; the next stage is G's decision and F never waits.
    """
    issues = validate_activity_request(request, grant)
    if issues:
        raise ActivityRequestError(VALIDATION_ERROR, issues)
    if not deps.grants.is_grant_current(grant):
        return _rejected(request, grant, deps, STALE, 'STALE_GRANT', STALE_GRANT)
    operation_key = request['operation_key']
    activity_name = request['activity_name']
    input_key = (activity_name, tuple(sorted((ref['ref_type'], ref['ref_id']) for ref in request['input_refs'])))
    stored = deps.results.get(grant.workspace_id, operation_key)
    if stored is not None:
        if stored[0] != input_key:
            return _rejected(request, grant, deps, FAILED, 'OPERATION_KEY_CONFLICT', OPERATION_KEY_CONFLICT)
        return {
            **stored[1],
            'stage_run_id': grant.stage_run_id,
            'grant_id': grant.operation_id,
            'execution_generation': grant.execution_generation,
            'recovery_epoch': str(grant.recovery_epoch),
        }
    route = _ROUTES.get(activity_name)
    if route is None:
        return _rejected(request, grant, deps, FAILED, 'UNKNOWN_ACTIVITY', UNKNOWN_ACTIVITY)
    try:
        outcome = route(deps, operation_key, grant, deps.inputs.resolve(activity_name, request, grant))
    except Exception as exc:
        return _exception_result(request, grant, deps, exc)
    result = _activity_result(request, grant, deps, outcome)
    if result['disposition'] == SUCCEEDED:
        deps.results.put(grant.workspace_id, operation_key, input_key, result)
    return result



__all__ = [
    'ACTIVITY_NAMES',
    'ActivityInputPort',
    'ActivityRequestError',
    'CommandMismatch',
    'InMemoryActivityResultStore',
    'RenderActivityDeps',
    'handle_activity',
    'validate_activity_request',
]
