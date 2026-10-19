"""Worker activity handler of module E for workflow G (E-18; CT-WF-003, CT-WF-006).

Receives an ActivityRequest with a controlplane ExecutionGrant, runs exactly the one E-16/E-17 command named by
activity_name and returns an ActivityResult. Temporal registration, the WAITING_CAPABILITY precondition for the desktop
and the choice of the next stage belong to workflow G (CONV-E-05): this module imports no workflow runtime, UI, API,
creative, render or catalog code, never waits and never starts a second stage. Results are built from codes, refs and
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
from voice.application.media_pipeline import (
    OP_ASSESS_IMAGE_SAFETY,
    OP_NORMALIZE_MEDIA,
    OP_PREPARE_AUDIO_BED,
    OP_PROBE_MEDIA,
    OP_TRANSFORM_SENSITIVE_IMAGE,
    CommandResult,
    MediaPipeline,
)
from voice.application.voice_pipeline import (
    COMMAND_CREATE_VOICE_TRACK,
    COMMAND_CREATE_WORD_TIMING,
    VoiceGenerationFailed,
    VoicePipeline,
    VoiceTrackOutcome,
    WordTimingOutcome,
)

REF_TYPE_VOICE = 'voice_artifact'
REF_TYPE_TIMING = 'word_timing_artifact'
REF_TYPE_TIMING_REPORT = 'timing_validation_report'
REF_TYPE_MEDIA = 'media_artifact'
VALIDATION_ERROR = 'VALIDATION_ERROR'
STALE_GRANT = 'STALE_GRANT'
UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
OPERATION_KEY_CONFLICT = 'OPERATION_KEY_CONFLICT'
OPERATION_KEY_MISMATCH = 'OPERATION_KEY_MISMATCH'
ACTIVITY_ABORTED = 'ACTIVITY_ABORTED'
MEDIA_COMMAND_FAILED = 'MEDIA_COMMAND_FAILED'
MEDIA_OUTCOME_UNKNOWN = 'MEDIA_OUTCOME_UNKNOWN'
IDEMPOTENCY_CODES = ('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD', 'IDEMPOTENCY_CONFLICT')
RETRY_NOT_ALLOWED_CODE = 'OUTCOME_UNKNOWN_RETRY_NOT_ALLOWED'
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
    'UNKNOWN_ACTIVITY': ('validation', 'activity_name is not an activity of module E; nothing was run'),
    'OPERATION_KEY_CONFLICT': ('conflict', 'operation_key was already used for a different activity or input_refs'),
    'IDEMPOTENCY_CONFLICT': ('conflict', 'operation_key was already used with a different payload'),
    'COMMAND_REJECTED': ('validation', 'the E command rejected its input; nothing was committed'),
    'VOICE_GENERATION_FAILED': ('dependency', 'voice generation failed on every attempt'),
    'MEDIA_FAILED': ('dependency', 'the media command ended without a verified output'),
    'OUTCOME_UNKNOWN': ('conflict', 'the command outcome is unknown and needs reconciliation by G'),
    'ACTIVITY_ABORTED': ('internal', 'the activity stopped on an unexpected error; retry with the same operation_key'),
})


class ActivityRequestError(Exception):
    """VALIDATION_ERROR: the request or grant is rejected before any grant check, lookup or write; no ActivityResult is built."""

    def __init__(self, code: str, issues: tuple[Issue, ...] | list[Issue] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.issues = tuple(issues)


class OperationKeyMismatch(Exception):
    """The operation_key inside the resolved command differs from the operation_key of the ActivityRequest."""

    def __init__(self) -> None:
        super().__init__(OPERATION_KEY_MISMATCH)
        self.code = OPERATION_KEY_MISMATCH


class GrantCurrencyPort(Protocol):
    """G owns ExecutionGrant; E asks whether a grant (generation and recovery epoch) is still current before any work."""

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        ...


class ActivityInputPort(Protocol):
    """Resolves the input_refs of an ActivityRequest to the keyword arguments of the one E command.

    CreateVoiceTrack and CreateWordTiming return {'command': <the E-16 command object>}. Media activities return the
    keyword arguments of the MediaPipeline method without operation_key (the handler passes the request operation_key).
    """

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> Mapping[str, Any]:
        ...


class InMemoryActivityResultStore:
    """Succeeded ActivityResults by (workspace_id, operation_key); fixture use until persistence in CONV-E-01 / CONV-E-05."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def get(self, workspace_id: str, operation_key: str) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        row = self._rows.get((workspace_id, operation_key))
        return None if row is None else (row[0], copy.deepcopy(row[1]))

    def put(self, workspace_id: str, operation_key: str, input_key: tuple[Any, ...], result: Mapping[str, Any]) -> None:
        self._rows.setdefault((workspace_id, operation_key), (input_key, copy.deepcopy(dict(result))))


@dataclass(frozen=True)
class VoiceActivityDeps:
    voice: VoicePipeline
    media: MediaPipeline
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
    error: str | None = None


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
    """Standard ProblemDetail: fixed detail per kind, code token only; never exception text or secret."""
    category, detail = _PROBLEMS[kind]
    stage = _safe_text(grant.stage_run_id, UNKNOWN_REF)
    problem = ProblemDetail.create(
        type=f'urn:voice:problem:{kind.lower()}',
        title=kind.replace('_', ' ').title(),
        detail=detail,
        instance=f'urn:stage-run:{stage}',
        code=code,
        category=category,
        retryable=retryable,
        correlation_id=_safe_text(request['workflow_run_id'], UNKNOWN_REF),
    )
    return dict(problem.values)


def _activity_result(
    request: Mapping[str, Any],
    grant: ExecutionGrant,
    deps: VoiceActivityDeps,
    outcome: _Outcome,
    problem: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """grant_id is ExecutionGrant.operation_id; recovery_epoch is its str (CONV-E-05)."""
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
    deps: VoiceActivityDeps,
    disposition: str,
    kind: str,
    code: str,
    *,
    retryable: bool = False,
) -> dict[str, Any]:
    problem = _problem(request, grant, kind, code, retryable=retryable)
    return _activity_result(request, grant, deps, _Outcome(disposition), problem)


def _outcome_problem(request: Mapping[str, Any], grant: ExecutionGrant, outcome: _Outcome) -> dict[str, Any] | None:
    if outcome.disposition == SUCCEEDED:
        return None
    if outcome.disposition == OUTCOME_UNKNOWN:
        return _problem(request, grant, 'OUTCOME_UNKNOWN', _safe_text(outcome.error, MEDIA_OUTCOME_UNKNOWN))
    return _problem(request, grant, 'MEDIA_FAILED', _safe_text(outcome.error, MEDIA_COMMAND_FAILED))


def _voice_track_outcome(outcome: VoiceTrackOutcome) -> _Outcome:
    voice = outcome.voice_track
    return _Outcome(
        SUCCEEDED,
        [{'ref_type': REF_TYPE_VOICE, 'ref_id': voice.voice_artifact_ref}],
        {'actual_duration_ms': voice.actual_duration_ms, 'replayed': outcome.replayed},
        [_safe_text(item, REDACTED_WARNING) for item in voice.warnings],
        outcome.receipt.receipt_ref,
    )


def _word_timing_outcome(outcome: WordTimingOutcome) -> _Outcome:
    timing = outcome.timing
    return _Outcome(
        SUCCEEDED,
        [
            {'ref_type': REF_TYPE_TIMING, 'ref_id': timing.timing_artifact_ref},
            {'ref_type': REF_TYPE_TIMING_REPORT, 'ref_id': timing.validation_report_ref},
        ],
        {'word_count': len(timing.words), 'replayed': outcome.replayed},
        [],
        outcome.receipt.receipt_ref,
    )


def _media_outcome(result: CommandResult) -> _Outcome:
    receipt = result.receipt
    return _Outcome(
        receipt.disposition.value,
        [{'ref_type': REF_TYPE_MEDIA, 'ref_id': ref} for ref in receipt.output_refs],
        {'output_count': len(receipt.output_refs), 'replayed': result.replayed},
        [_safe_text(item, REDACTED_WARNING) for item in receipt.warnings],
        receipt.receipt_ref,
        receipt.error,
    )


def _require_operation_key(voice_request: Mapping[str, Any], operation_key: str) -> None:
    if voice_request.get('operation_key') != operation_key:
        raise OperationKeyMismatch()


def _run_create_voice_track(deps: VoiceActivityDeps, operation_key: str, inputs: Mapping[str, Any]) -> _Outcome:
    command = inputs['command']
    _require_operation_key(command.voice_request, operation_key)
    return _voice_track_outcome(deps.voice.create_voice_track(command))


def _run_create_word_timing(deps: VoiceActivityDeps, operation_key: str, inputs: Mapping[str, Any]) -> _Outcome:
    command = inputs['command']
    _require_operation_key(command.voice_request, operation_key)
    return _word_timing_outcome(deps.voice.create_word_timing(command))


# activity_name -> the one E-16/E-17 command it runs; no route chains to another one
_ROUTES = MappingProxyType({
    COMMAND_CREATE_VOICE_TRACK: _run_create_voice_track,
    COMMAND_CREATE_WORD_TIMING: _run_create_word_timing,
    OP_PROBE_MEDIA: lambda deps, key, inputs: _media_outcome(deps.media.probe_media(operation_key=key, **inputs)),
    OP_ASSESS_IMAGE_SAFETY: lambda deps, key, inputs: _media_outcome(
        deps.media.assess_image_safety(operation_key=key, **inputs)
    ),
    OP_TRANSFORM_SENSITIVE_IMAGE: lambda deps, key, inputs: _media_outcome(
        deps.media.transform_sensitive_image(operation_key=key, **inputs)
    ),
    OP_NORMALIZE_MEDIA: lambda deps, key, inputs: _media_outcome(deps.media.normalize_media(operation_key=key, **inputs)),
    OP_PREPARE_AUDIO_BED: lambda deps, key, inputs: _media_outcome(
        deps.media.prepare_audio_bed(operation_key=key, **inputs)
    ),
})
ACTIVITY_NAMES = tuple(_ROUTES)


def _exception_result(
    request: Mapping[str, Any], grant: ExecutionGrant, deps: VoiceActivityDeps, exc: Exception
) -> dict[str, Any]:
    """Map an exception of an E command or of the input port to a result built from its code token only, never its text."""
    raw = getattr(exc, 'code', None)
    code = _safe_text(raw, '') if isinstance(raw, str) else ''
    if code and isinstance(exc, VoiceGenerationFailed):
        return _rejected(
            request, grant, deps, FAILED, 'VOICE_GENERATION_FAILED', code, retryable=exc.retryable is True
        )
    if code in IDEMPOTENCY_CODES:
        return _rejected(request, grant, deps, FAILED, 'IDEMPOTENCY_CONFLICT', code)
    if code == RETRY_NOT_ALLOWED_CODE:
        return _rejected(request, grant, deps, OUTCOME_UNKNOWN, 'OUTCOME_UNKNOWN', code)
    if code:
        return _rejected(request, grant, deps, FAILED, 'COMMAND_REJECTED', code)
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


def handle_activity(request: Mapping[str, Any], grant: ExecutionGrant, deps: VoiceActivityDeps) -> dict[str, Any]:
    """Run the one E command named by activity_name for an ActivityRequest and return an ActivityResult (CT-WF-003, CT-WF-006).

    An invalid request or grant raises ActivityRequestError(VALIDATION_ERROR) and builds no result. A grant that the
    grant port no longer reports current (old execution_generation or recovery_epoch) gives a 'stale' result before any
    input lookup, command or write. Only a 'succeeded' result is stored under (workspace_id, operation_key): the same
    key returns it, re-stamped with the identity of the current grant, without running the command again; the same key
    for another activity or input_refs is OPERATION_KEY_CONFLICT. An unknown activity_name gives a failed result with
    a structured problem. Exactly one command runs per call; the next stage is G's decision and E never waits.
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
        outcome = route(deps, operation_key, deps.inputs.resolve(activity_name, request, grant))
    except Exception as exc:
        return _exception_result(request, grant, deps, exc)
    result = _activity_result(request, grant, deps, outcome, _outcome_problem(request, grant, outcome))
    if result['disposition'] == SUCCEEDED:
        deps.results.put(grant.workspace_id, operation_key, input_key, result)
    return result


__all__ = [
    'ACTIVITY_NAMES',
    'ActivityInputPort',
    'ActivityRequestError',
    'GrantCurrencyPort',
    'InMemoryActivityResultStore',
    'OperationKeyMismatch',
    'VoiceActivityDeps',
    'handle_activity',
    'validate_activity_request',
]
