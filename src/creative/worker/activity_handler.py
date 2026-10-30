"""Worker activity handler of module D for workflow G (D-16; CT-WF-003, CT-WF-006).

coveredIds: CT-WF-003, CT-WF-006

Receives an ActivityRequest with a controlplane ExecutionGrant, runs exactly the one D-14 command named by
activity_name and returns an ActivityResult. Temporal registration, the WAITING_CAPABILITY precondition for the desktop
and the choice of the next stage belong to workflow G (CONV-D-05): this module imports no workflow runtime, UI, API,
voice or render code, never waits and never starts a second stage. Results are built from codes, refs and counters
only, so no exception text, model output or secret reaches a result.
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
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.orchestration import ExecutionGrant
from creative.application.pipeline import (
    AI_INVOCATION_FAILED,
    IDEMPOTENCY_CONFLICT_CODE,
    CommandResult,
    CreativePipeline,
    IdempotencyConflict,
    ProviderWaiting,
)
from creative.ports.repositories import DuplicateRecordError, EventContext

COMMAND_VALIDATE_VARIANT = 'ValidateVariant'
VALIDATION_ERROR = 'VALIDATION_ERROR'
STALE_GRANT = 'STALE_GRANT'
UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
OPERATION_KEY_CONFLICT = 'OPERATION_KEY_CONFLICT'
GRANT_CONTEXT_MISMATCH = 'GRANT_CONTEXT_MISMATCH'
INVALID_COMMAND_INPUT = 'INVALID_COMMAND_INPUT'
REVISION_CONFLICT = 'REVISION_CONFLICT'
DUPLICATE_RECORD = 'DUPLICATE_RECORD'
ACTIVITY_ABORTED = 'ACTIVITY_ABORTED'
REDACTED_WARNING = 'warning_redacted'
UNKNOWN_REF = 'unknown'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
WAITING = 'waiting'
WAIT_FALLBACK = 'provider_unavailable'
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
_TOKEN_JUNK_RE = re.compile(r'[^A-Za-z0-9_.:-]+')

# kind -> (ProblemDetail category, fixed detail); detail is never built from exception text
_PROBLEMS = MappingProxyType({
    'STALE_GRANT': ('conflict', 'execution grant or generation is no longer current; nothing was committed'),
    'UNKNOWN_ACTIVITY': ('validation', 'activity_name is not an activity of module D; nothing was run'),
    'OPERATION_KEY_CONFLICT': ('conflict', 'operation_key was already used for a different activity or input_refs'),
    'IDEMPOTENCY_CONFLICT': ('conflict', 'operation_key was already used with a different payload'),
    'COMMAND_REJECTED': ('validation', 'the D command rejected its input; nothing was committed'),
    'COMMAND_CONFLICT': ('conflict', 'the D command conflicts with a stored record; nothing was committed'),
    'AI_INVOCATION_FAILED': ('dependency', 'the AI invocation of the D command failed; nothing was committed'),
    'AI_WAITING': ('capacity', 'the AI provider has no capacity right now; the stage waits and G tries again when it recovers'),
    'ACTIVITY_ABORTED': ('internal', 'the activity stopped on an unexpected error; retry with the same operation_key'),
})
# activity_name -> (CreativePipeline method, ref_type of the output ref); no route chains to another command
_ROUTES = MappingProxyType({
    'BuildProductionSnapshot': ('build_production_snapshot', 'production_snapshot'),
    'AnalyzeContent': ('analyze_content', 'content_analysis'),
    'GenerateStoryAngles': ('generate_story_angles', 'story_angle_set'),
    'GenerateScript': ('generate_script', 'script_version'),
    'SelectCreativeAssets': ('select_creative_assets', 'creative_asset_selection'),
    'BuildProductionPlan': ('build_production_plan', 'production_plan'),
    'ValidateVariant': ('validate_variant', 'variant_validation'),
    'GenerateOutputMetadata': ('generate_output_metadata', 'output_metadata'),
})
ACTIVITY_NAMES = tuple(_ROUTES)


class ActivityRequestError(Exception):
    """VALIDATION_ERROR: the request or grant is rejected before any grant check, lookup or write; no ActivityResult is built."""

    def __init__(self, code: str, issues: tuple[Issue, ...] | list[Issue] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.issues = tuple(issues)


class GrantCurrencyPort(Protocol):
    """G owns ExecutionGrant; D asks whether a grant (generation and recovery epoch) is still current before any work."""

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        ...


class ActivityInputPort(Protocol):
    """Resolves the input_refs of an ActivityRequest to the keyword arguments of the one D-14 command.

    Returns the arguments of the CreativePipeline method named by activity_name, including `context` (an EventContext
    of the grant's workspace_id and recovery_epoch) and excluding `idempotency_key` (the handler passes operation_key).
    """

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> Mapping[str, Any]:
        ...


class InMemoryActivityResultStore:
    """Succeeded ActivityResults by (workspace_id, operation_key); fixture use until persistence in CONV-D-01 / CONV-D-05."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def get(self, workspace_id: str, operation_key: str) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        row = self._rows.get((workspace_id, operation_key))
        return None if row is None else (row[0], copy.deepcopy(row[1]))

    def put(self, workspace_id: str, operation_key: str, input_key: tuple[Any, ...], result: Mapping[str, Any]) -> None:
        self._rows.setdefault((workspace_id, operation_key), (input_key, copy.deepcopy(dict(result))))


@dataclass(frozen=True)
class CreativeActivityDeps:
    pipeline: CreativePipeline
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


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_text(value: object, default: str) -> str:
    """A code-like token without secret words; free text, URLs and secrets fall back to the default."""
    if not isinstance(value, str) or not _SAFE_TOKEN_RE.fullmatch(value) or _SECRET_WORD_RE.search(value):
        return default
    return value


def _token(value: object, default: str) -> str:
    """A stable machine token from a reason or a field path: runs of other characters become one underscore; text with a secret word or nothing left gives the default."""
    text = _TOKEN_JUNK_RE.sub('_', value).strip('_')[:80] if isinstance(value, str) else ''
    return _safe_text(text, default)


def _output_field_errors(exc: Exception) -> dict[str, str] | None:
    """field_errors of a model-output failure that used up its attempts: reason, field and the number of attempts, all tokens; None for any other rejection."""
    attempts = getattr(exc, 'attempts', 0)
    if type(attempts) is not int or attempts < 1:
        return None
    return {'reason': _token(getattr(exc, 'reason', None), 'unknown'), 'field': _token(getattr(exc, 'field', None), 'root'), 'attempts': str(attempts)}


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


def _problem(
    request: Mapping[str, Any], grant: ExecutionGrant, kind: str, code: str, *, retryable: bool = False,
    field_errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Standard ProblemDetail: fixed detail per kind, code token only; never exception text or secret."""
    category, detail = _PROBLEMS[kind]
    stage = _safe_text(grant.stage_run_id, UNKNOWN_REF)
    extra = {} if field_errors is None else {'field_errors': dict(field_errors)}
    problem = ProblemDetail.create(
        type=f'urn:creative:problem:{kind.lower()}',
        title=kind.replace('_', ' ').title(),
        detail=detail,
        instance=f'urn:stage-run:{stage}',
        code=code,
        category=category,
        retryable=retryable,
        correlation_id=_safe_text(request['workflow_run_id'], UNKNOWN_REF),
        **extra,
    )
    return dict(problem.values)


def _activity_result(
    request: Mapping[str, Any],
    grant: ExecutionGrant,
    deps: CreativeActivityDeps,
    outcome: _Outcome,
    problem: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """grant_id is ExecutionGrant.operation_id; recovery_epoch is its str (CONV-D-05)."""
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
    if problem is not None:
        result['problem'] = problem
    return result


def _rejected(
    request: Mapping[str, Any],
    grant: ExecutionGrant,
    deps: CreativeActivityDeps,
    disposition: str,
    kind: str,
    code: str,
    *,
    retryable: bool = False,
    field_errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    problem = _problem(request, grant, kind, code, retryable=retryable, field_errors=field_errors)
    return _activity_result(request, grant, deps, _Outcome(disposition), problem)


def _command_outcome(result: CommandResult, ref_type: str) -> _Outcome:
    """Refs and counters from the receipt, so a replay without output gives the same refs; never the output text."""
    receipt = result.receipt
    output = result.output
    warnings: list[str] = []
    if result.command == COMMAND_VALIDATE_VARIANT and output is not None and output.valid is False:
        warnings = [_safe_text(f'variant_invalid:{code}', REDACTED_WARNING) for code in output.reason_codes]
    return _Outcome(
        SUCCEEDED,
        [{'ref_type': ref_type, 'ref_id': receipt.aggregate_ref, 'revision_id': str(receipt.aggregate_revision)}],
        {
            'replayed': result.replayed,
            'aggregate_revision': receipt.aggregate_revision,
            'ai_invoked': result.trace is not None and result.trace.invocation_key is not None,
        },
        warnings,
        f'receipt:{receipt.idempotency_key}',
    )


class GrantContextMismatch(Exception):
    """The EventContext from the input port names another workspace or recovery epoch than the grant."""

    def __init__(self) -> None:
        super().__init__(GRANT_CONTEXT_MISMATCH)
        self.code = GRANT_CONTEXT_MISMATCH


def _require_context(inputs: Mapping[str, Any], grant: ExecutionGrant) -> None:
    context = inputs.get('context')
    if (
        not isinstance(context, EventContext)
        or context.workspace_id != grant.workspace_id
        or context.recovery_epoch != str(grant.recovery_epoch)
    ):
        raise GrantContextMismatch()


def _exception_result(
    request: Mapping[str, Any], grant: ExecutionGrant, deps: CreativeActivityDeps, exc: Exception
) -> dict[str, Any]:
    """Map an exception of the input port or of a D command to a result built from a code token only, never its text."""
    if isinstance(exc, IdempotencyConflict):
        return _rejected(request, grant, deps, FAILED, 'IDEMPOTENCY_CONFLICT', IDEMPOTENCY_CONFLICT_CODE)
    if isinstance(exc, RevisionConflictError):
        return _rejected(request, grant, deps, FAILED, 'COMMAND_CONFLICT', REVISION_CONFLICT)
    if isinstance(exc, DuplicateRecordError):
        return _rejected(request, grant, deps, FAILED, 'COMMAND_CONFLICT', DUPLICATE_RECORD)
    if isinstance(exc, ProviderWaiting):
        return _rejected(request, grant, deps, WAITING, 'AI_WAITING', _safe_text(exc.code, WAIT_FALLBACK), retryable=True)
    raw = getattr(exc, 'code', None)
    code = _safe_text(raw, '') if isinstance(raw, str) else ''
    if code == AI_INVOCATION_FAILED:
        return _rejected(request, grant, deps, FAILED, 'AI_INVOCATION_FAILED', code)
    if code:
        return _rejected(request, grant, deps, FAILED, 'COMMAND_REJECTED', code, field_errors=_output_field_errors(exc))
    if isinstance(exc, ValueError):
        return _rejected(request, grant, deps, FAILED, 'COMMAND_REJECTED', INVALID_COMMAND_INPUT)
    return _rejected(request, grant, deps, FAILED, 'ACTIVITY_ABORTED', ACTIVITY_ABORTED, retryable=True)


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


def handle_activity(request: Mapping[str, Any], grant: ExecutionGrant, deps: CreativeActivityDeps) -> dict[str, Any]:
    """Run the one D-14 command named by activity_name for an ActivityRequest and return an ActivityResult (CT-WF-003, CT-WF-006).

    An invalid request or grant raises ActivityRequestError(VALIDATION_ERROR) and builds no result. A grant that the
    grant port no longer reports current (old execution_generation or recovery_epoch) gives a 'stale' result before any
    input lookup, command or write. Only a 'succeeded' result is stored under (workspace_id, operation_key): the same
    key returns it, re-stamped with the identity of the current grant, without running the command again; the same key
    for another activity or input_refs is OPERATION_KEY_CONFLICT. Exactly one command runs per call; the next stage is
    G's decision and D never waits for a capability. A provider that has no capacity (ProviderWaiting) gives a 'waiting'
    result whose problem code is a WaitReason value; it is never stored, so G calls again with the same operation_key.
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
    method, ref_type = route
    try:
        inputs = deps.inputs.resolve(activity_name, request, grant)
        _require_context(inputs, grant)
        outcome = _command_outcome(getattr(deps.pipeline, method)(idempotency_key=operation_key, **inputs), ref_type)
    except Exception as exc:
        return _exception_result(request, grant, deps, exc)
    result = _activity_result(request, grant, deps, outcome)
    deps.results.put(grant.workspace_id, operation_key, input_key, result)
    return result


__all__ = [
    'ACTIVITY_NAMES',
    'ActivityInputPort',
    'ActivityRequestError',
    'CreativeActivityDeps',
    'GrantContextMismatch',
    'GrantCurrencyPort',
    'InMemoryActivityResultStore',
    'handle_activity',
    'validate_activity_request',
]
