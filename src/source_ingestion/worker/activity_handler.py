"""Worker activity handler of CollectSource for workflow G (A-18; A-RULE-014, A-RULE-016).

Receives an ActivityRequest with controlplane GrantClaims (YC-HT-G-10), runs CollectSource and returns an ActivityResult.
Temporal registration belongs to workflow G (CONV-A-06): this module imports no workflow runtime, UI, render, voice
or desktop code. Results are built from codes and counters only, so no exception text or secret reaches a result.
"""
from __future__ import annotations

import copy
import datetime
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

from controlplane.domain.orchestration.fencing import GrantClaims

from source_ingestion.application.collect_source import (
    CollectionRunResult,
    CollectionUnitOfWork,
    CollectSourceRequest,
    SourceCollectionJob,
    collect_source,
)
from source_ingestion.application.package_builder import HtmlExtractor
from source_ingestion.domain.collection_run import RetryPolicy, RunStatus
from source_ingestion.domain.package import ExtractionPolicy
from source_ingestion.ports.source_adapter import SourceAdapter

ACTIVITY_NAME = 'CollectSource'
REF_TYPE_SOURCE = 'collection_source'
REF_TYPE_BUSINESS_DATE = 'business_date'
REF_TYPE_RUN = 'collection_run'
REF_TYPE_DOCUMENT = 'collected_document'
VALIDATION_ERROR = 'VALIDATION_ERROR'
STALE_GRANT = 'STALE_GRANT'
OPERATION_KEY_CONFLICT = 'OPERATION_KEY_CONFLICT'
COLLECTION_ABORTED = 'COLLECTION_ABORTED'
COLLECTION_FAILED = 'COLLECTION_FAILED'
COLLECTION_WAITING_RETRY = 'COLLECTION_WAITING_RETRY'
COLLECTION_OUTCOME_UNKNOWN = 'COLLECTION_OUTCOME_UNKNOWN'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
WAITING = 'waiting'
OUTCOME_UNKNOWN = 'outcome_unknown'
STALE = 'stale'
Issue = tuple[str, str]


class ClaimsCurrencyPort(Protocol):
    """G owns GrantClaims; A asks whether the claims are still current (generation, recovery epoch, expiry) before accepting work."""

    def is_grant_current(self, grant: GrantClaims) -> bool:
        ...


class ActivityRequestError(Exception):
    """VALIDATION_ERROR: the request or grant is rejected before any lookup or write and no ActivityResult is built."""

    def __init__(self, code: str, issues: tuple[Issue, ...] | list[Issue] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.issues = tuple(issues)


class InMemoryActivityResultStore:
    """Succeeded ActivityResults by (workspace_id, operation_key); fixture use until persistence in CONV-A-01 / CONV-A-06."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[tuple[tuple[str, str], ...], dict[str, Any]]] = {}

    def get(self, workspace_id: str, operation_key: str) -> tuple[tuple[tuple[str, str], ...], dict[str, Any]] | None:
        row = self._rows.get((workspace_id, operation_key))
        return None if row is None else (row[0], copy.deepcopy(row[1]))

    def put(
        self, workspace_id: str, operation_key: str, input_key: tuple[tuple[str, str], ...], result: Mapping[str, Any]
    ) -> None:
        self._rows.setdefault((workspace_id, operation_key), (input_key, copy.deepcopy(dict(result))))


@dataclass(frozen=True)
class CollectActivityDeps:
    uow: CollectionUnitOfWork
    grants: ClaimsCurrencyPort
    adapter_for: Callable[[str], SourceAdapter]
    extractor: HtmlExtractor
    retry_policy: RetryPolicy
    adapter_revision: str
    workspace_id: str
    extraction_policy: ExtractionPolicy | None = None
    results: InMemoryActivityResultStore = field(default_factory=InMemoryActivityResultStore)

    def __post_init__(self) -> None:
        if not _is_text(self.workspace_id):
            raise ValueError('workspace_id must be a non-empty string')


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
_ISO_DATE_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_CODE_RE = re.compile(r'[A-Z0-9_]{1,64}')


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
    if not isinstance(grant, GrantClaims):
        return [('wrong_type', 'execution_grant')]
    issues: list[Issue] = []
    for name in ('grant_id', 'stage_run_id', 'worker_lease_id', 'recovery_epoch', 'allowed_operation', 'input_fingerprint'):
        if not _is_text(getattr(grant, name)):
            issues.append(('invalid_value', f'execution_grant.{name}'))
    if type(grant.execution_generation) is not int or grant.execution_generation < 0:
        issues.append(('invalid_value', 'execution_grant.execution_generation'))
    if isinstance(stage_run_id, str) and _is_text(grant.stage_run_id) and grant.stage_run_id != stage_run_id:
        issues.append(('invalid_value', 'execution_grant.stage_run_id'))
    return issues


def _parse_input_refs(refs: object) -> tuple[str, datetime.date] | None:
    """Exactly two refs: one collection_source (ref_id is the source_id) and one business_date (YYYY-MM-DD)."""
    if not isinstance(refs, list) or len(refs) != 2:
        return None
    found: dict[str, str] = {}
    for ref in refs:
        if not isinstance(ref, Mapping) or not _is_text(ref.get('ref_type')) or not _is_text(ref.get('ref_id')):
            return None
        found[ref['ref_type']] = ref['ref_id']
    if set(found) != {REF_TYPE_SOURCE, REF_TYPE_BUSINESS_DATE}:
        return None
    if not _ISO_DATE_RE.fullmatch(found[REF_TYPE_BUSINESS_DATE]):
        return None
    try:
        business_date = datetime.date.fromisoformat(found[REF_TYPE_BUSINESS_DATE])
    except ValueError:
        return None
    return found[REF_TYPE_SOURCE], business_date


def validate_collect_request(request: object, grant: object) -> list[Issue]:
    """Return (code, field) issues of the ActivityRequest binding and of the typed GrantClaims; empty means valid."""
    issues = _request_issues(request)
    if not isinstance(request, Mapping):
        return issues
    invalid = {name for _, name in issues}
    issues.extend(_grant_issues(grant, request.get('stage_run_id')))
    if 'activity_name' not in invalid and request['activity_name'] != ACTIVITY_NAME:
        issues.append(('invalid_value', 'activity_name'))
    if 'operation_key' not in invalid and not _is_text(request['operation_key']):
        issues.append(('invalid_value', 'operation_key'))
    if 'input_refs' not in invalid and _parse_input_refs(request['input_refs']) is None:
        issues.append(('invalid_value', 'input_refs'))
    return issues


_PROBLEM_MESSAGES = MappingProxyType({
    STALE_GRANT: 'execution grant or generation is no longer current; nothing was committed',
    OPERATION_KEY_CONFLICT: 'operation_key was already used for different input_refs',
    COLLECTION_ABORTED: 'collection stopped on an unexpected error; retry with the same operation_key',
    COLLECTION_FAILED: 'collection run ended without a committed document',
    COLLECTION_WAITING_RETRY: 'collection run is waiting to retry; retry with the same operation_key',
    COLLECTION_OUTCOME_UNKNOWN: 'collection run outcome needs reconciliation',
})


def _utc(moment: datetime.datetime) -> str:
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'


def _safe_code(value: object, default: str) -> str:
    text = str(value)
    return text if _CODE_RE.fullmatch(text) else default


def _problem(code: str, message_key: str, *, retryable: bool = False) -> dict[str, Any]:
    """Standard problem: fixed message and a code token; never exception text, URL or secret."""
    return {'code': code, 'retryable': retryable, 'message': _PROBLEM_MESSAGES[message_key]}


def _activity_result(
    grant: GrantClaims,
    disposition: str,
    output_refs: list[dict[str, str]],
    clock: Callable[[], datetime.datetime],
    *,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    problem: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """grant_id is GrantClaims.grant_id and recovery_epoch is GrantClaims.recovery_epoch, a string (YC-HT-G-10)."""
    result: dict[str, Any] = {
        'stage_run_id': grant.stage_run_id,
        'grant_id': grant.grant_id,
        'execution_generation': grant.execution_generation,
        'recovery_epoch': grant.recovery_epoch,
        'disposition': disposition,
        'output_refs': output_refs,
        'completed_at': _utc(clock()),
    }
    if metrics is not None:
        result['metrics'] = metrics
    if warnings is not None:
        result['warnings'] = warnings
    if problem is not None:
        result['problem'] = problem
    return result


def _collection_result(
    grant: GrantClaims, outcome: CollectionRunResult, clock: Callable[[], datetime.datetime]
) -> dict[str, Any]:
    """COMPLETED and COMPLETED_PARTIAL succeed (item errors are warnings); other statuses carry a standard problem."""
    output_refs = [{'ref_type': REF_TYPE_RUN, 'ref_id': outcome.run_id}]
    output_refs.extend({'ref_type': REF_TYPE_DOCUMENT, 'ref_id': ref} for ref in outcome.package_refs)
    metrics = {
        'urls_seen': outcome.urls_seen,
        'fetched': outcome.fetched,
        'skipped': outcome.skipped,
        'failed': outcome.failed,
        'packages_committed': outcome.packages_committed,
        'replayed': outcome.replayed,
    }
    codes = [_safe_code(error.code, COLLECTION_FAILED) for error in outcome.errors]
    warnings = [f'{code}:{error.locator}' if error.locator else code for code, error in zip(codes, outcome.errors)]
    code = codes[0] if codes else None
    problem: dict[str, Any] | None = None
    if outcome.status in (RunStatus.COMPLETED, RunStatus.COMPLETED_PARTIAL):
        disposition = SUCCEEDED
    elif outcome.status is RunStatus.WAITING_RETRY:
        disposition = WAITING
        problem = _problem(code or COLLECTION_WAITING_RETRY, COLLECTION_WAITING_RETRY, retryable=True)
    elif outcome.status is RunStatus.FAILED_FINAL:
        disposition = FAILED
        problem = _problem(code or COLLECTION_FAILED, COLLECTION_FAILED)
    else:
        disposition = OUTCOME_UNKNOWN
        problem = _problem(code or COLLECTION_OUTCOME_UNKNOWN, COLLECTION_OUTCOME_UNKNOWN)
    return _activity_result(
        grant, disposition, output_refs, clock, metrics=metrics, warnings=warnings, problem=problem
    )


def handle_collect_source_activity(
    request: Mapping[str, Any],
    grant: GrantClaims,
    deps: CollectActivityDeps,
    clock: Callable[[], datetime.datetime],
) -> dict[str, Any]:
    """Run CollectSource for one ActivityRequest and return an ActivityResult (CT-WF-003, CT-WF-006).

    An invalid request or grant raises ActivityRequestError(VALIDATION_ERROR) and builds no result. A grant that the
    grant port no longer reports current gives a 'stale' result before any lookup, collection or write. Only a
    'succeeded' result is stored under (workspace_id, operation_key): the same key returns it without collecting again,
    and a different input_refs list under that key is OPERATION_KEY_CONFLICT. execution_generation of the grant is the
    CollectSource execution_generation, so a stale checkpoint write is rejected by the checkpoint repository too.
    Without a GrantClaims (execution_grant missing) the request is rejected with VALIDATION_ERROR before any lookup, collection or write.
    """
    issues = validate_collect_request(request, grant)
    if issues:
        raise ActivityRequestError(VALIDATION_ERROR, issues)
    source_id, business_date = _parse_input_refs(request['input_refs'])
    operation_key = request['operation_key']
    input_key = tuple(sorted((ref['ref_type'], ref['ref_id']) for ref in request['input_refs']))
    if not deps.grants.is_grant_current(grant):
        return _activity_result(grant, STALE, [], clock, problem=_problem(STALE_GRANT, STALE_GRANT))
    stored = deps.results.get(deps.workspace_id, operation_key)
    if stored is not None:
        if stored[0] != input_key:
            problem = _problem(OPERATION_KEY_CONFLICT, OPERATION_KEY_CONFLICT)
            return _activity_result(grant, FAILED, [], clock, problem=problem)
        return stored[1]
    try:
        job = SourceCollectionJob(
            CollectSourceRequest(
                workspace_id=deps.workspace_id,
                source_id=source_id,
                business_date=business_date,
                run_id=f'run:{operation_key}',
                retry_policy=deps.retry_policy,
                adapter_revision=deps.adapter_revision,
                execution_generation=grant.execution_generation,
                extraction_policy=deps.extraction_policy,
            ),
            deps.adapter_for(source_id),
            deps.extractor,
        )
        outcome = collect_source(deps.uow, job, clock=clock)
    except Exception:
        problem = _problem(COLLECTION_ABORTED, COLLECTION_ABORTED, retryable=True)
        return _activity_result(grant, FAILED, [], clock, problem=problem)
    result = _collection_result(grant, outcome, clock)
    if result['disposition'] == SUCCEEDED:
        deps.results.put(deps.workspace_id, operation_key, input_key, result)
    return result


__all__ = [
    'ACTIVITY_NAME',
    'ActivityRequestError',
    'ClaimsCurrencyPort',
    'CollectActivityDeps',
    'InMemoryActivityResultStore',
    'handle_collect_source_activity',
    'validate_collect_request',
]
