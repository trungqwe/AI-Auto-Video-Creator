"""ResolveCollectedDocument activity handler for module B (CT-WF-003, CT-WF-006, D8-B-11, D8-B-12).

One ActivityRequest carries exactly one collected document and resolves in its own unit-of-work transaction.
Only a succeeded result is stored under its operation_key; a failed result may be retried with the same key.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from ingestion.application.ports import SourceTierLookup, UnitOfWork
from ingestion.application.resolve_document import (
    FAILED_FINAL,
    FAILED_RETRYABLE,
    VALIDATION_ERROR,
    ResolveDocumentError,
    resolve_collected_document,
)
from ingestion.domain.package_validation import ENUM_VIOLATION, MISSING_REQUIRED, WRONG_TYPE, ValidationIssue

ACTIVITY_NAME = 'ResolveCollectedDocument'
FORBIDDEN_FIELD = 'forbidden_field'
INVALID_VALUE = 'invalid_value'
OPERATION_KEY_CONFLICT = 'OPERATION_KEY_CONFLICT'
KIND_ACTIVITY_RESULT = 'activity_result'
REF_TYPE_RESOLUTION = 'collected_document_resolution'
SUCCEEDED = 'succeeded'
FAILED = 'failed'
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
REQUEST_OPTIONAL = MappingProxyType({'video_job_id': 'string', 'execution_grant': 'object', 'deadline_at': 'datetime'})
REQUEST_FORBIDDEN = ('secret_value', 'raw_blob')
RESULT_REQUIRED = MappingProxyType({
    'stage_run_id': 'string',
    'grant_id': 'string',
    'execution_generation': 'integer',
    'recovery_epoch': 'string',
    'disposition': 'string',
    'output_refs': 'array',
    'completed_at': 'datetime',
})
RESULT_OPTIONAL = MappingProxyType({
    'metrics': 'object',
    'warnings': 'array',
    'problem': 'object',
    'operation_receipt_ref': 'string',
})
RESULT_ENUM = MappingProxyType({'disposition': ('succeeded', 'failed', 'waiting', 'outcome_unknown', 'stale')})
GRANT_FIELDS = MappingProxyType({'grant_id': 'string', 'execution_generation': 'integer', 'recovery_epoch': 'string'})


class ActivityRequestError(Exception):
    """VALIDATION_ERROR: the request is rejected before any lookup, load or write and no ActivityResult is built (D8-B-12)."""

    def __init__(self, code: str, issues: Sequence[ValidationIssue] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.issues = tuple(issues)


@dataclass(frozen=True)
class ResolveActivityDeps:
    uow: UnitOfWork
    tier_lookup: SourceTierLookup
    id_factory: Callable[[], str]
    dedup_policy: Mapping[str, Any]
    topic_rules: Sequence[Mapping[str, Any]] = ()


_RFC3339_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})')


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_RE.fullmatch(value):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _matches(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, Mapping)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'datetime':
        return _is_rfc3339(value)
    return False


def _is_token(value: str) -> bool:
    return 0 < len(value) <= 256 and not any(char.isspace() for char in value)


def _field_issues(
    payload: object,
    required: Mapping[str, str],
    optional: Mapping[str, str],
    enum: Mapping[str, tuple[str, ...]],
) -> list[ValidationIssue]:
    if not isinstance(payload, Mapping):
        return [ValidationIssue(WRONG_TYPE, '$')]
    issues: list[ValidationIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        if name not in payload:
            if name in required:
                issues.append(ValidationIssue(MISSING_REQUIRED, name))
            continue
        value = payload[name]
        if value is None:
            if name in required:
                issues.append(ValidationIssue(WRONG_TYPE, name))
            continue
        if not _matches(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in enum and value not in enum[name]:
            issues.append(ValidationIssue(ENUM_VIOLATION, name))
    return issues


def _is_ref(value: object) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(value.get(key), str) and value[key].strip() for key in ('ref_type', 'ref_id')
    )


def _grant_issues(grant: Mapping[str, Any], stage_run_id: object) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name, type_name in GRANT_FIELDS.items():
        field = f'execution_grant.{name}'
        value = grant.get(name)
        if value is None:
            issues.append(ValidationIssue(MISSING_REQUIRED, field))
        elif not _matches(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, field))
        elif (type_name == 'string' and not _is_token(value)) or (type_name == 'integer' and value < 0):
            issues.append(ValidationIssue(INVALID_VALUE, field))
    if grant.get('stage_run_id') is not None and grant['stage_run_id'] != stage_run_id:
        issues.append(ValidationIssue(INVALID_VALUE, 'execution_grant.stage_run_id'))
    return issues


def validate_activity_request(payload: object) -> list[ValidationIssue]:
    """Return binding issues of an ActivityRequest (CT-WF-003): required fields, types and forbidden fields."""
    forbidden = [
        ValidationIssue(FORBIDDEN_FIELD, name)
        for name in REQUEST_FORBIDDEN
        if isinstance(payload, Mapping) and name in payload
    ]
    return [*forbidden, *_field_issues(payload, REQUEST_REQUIRED, REQUEST_OPTIONAL, {})]


def validate_resolve_request(payload: object) -> list[ValidationIssue]:
    """Binding issues plus the ResolveCollectedDocument rules: activity_name, one input_ref, execution_grant (D8-B-12)."""
    issues = validate_activity_request(payload)
    if not isinstance(payload, Mapping):
        return issues
    invalid = {issue.field for issue in issues}
    if 'activity_name' not in invalid and payload['activity_name'] != ACTIVITY_NAME:
        issues.append(ValidationIssue(INVALID_VALUE, 'activity_name'))
    if 'operation_key' not in invalid and not payload['operation_key'].strip():
        issues.append(ValidationIssue(INVALID_VALUE, 'operation_key'))
    if 'input_refs' not in invalid:
        refs = payload['input_refs']
        if len(refs) != 1:
            issues.append(ValidationIssue(INVALID_VALUE, 'input_refs'))
        elif not _is_ref(refs[0]):
            issues.append(ValidationIssue(WRONG_TYPE, 'input_refs'))
    grant = payload.get('execution_grant')
    if grant is None:
        issues.append(ValidationIssue(MISSING_REQUIRED, 'execution_grant'))
    elif 'execution_grant' not in invalid:
        issues.extend(_grant_issues(grant, payload.get('stage_run_id')))
    return issues


def validate_activity_result(payload: object) -> list[ValidationIssue]:
    """Return binding issues of an ActivityResult (CT-WF-006); empty list means valid."""
    return _field_issues(payload, RESULT_REQUIRED, RESULT_OPTIONAL, RESULT_ENUM)


_PROBLEM_MESSAGES = MappingProxyType({
    VALIDATION_ERROR: 'collected document package failed validation',
    FAILED_RETRYABLE: 'infrastructure error while resolving the collected document; retry with the same operation_key',
    FAILED_FINAL: 'deterministic error while resolving the collected document',
    OPERATION_KEY_CONFLICT: 'operation_key was already used for a different input_ref',
})


def _utc(moment: datetime) -> str:
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _problem(code: str, issues: Sequence[ValidationIssue] = ()) -> dict[str, Any]:
    """Standard problem without exception text, so no host, URL or secret from a port reaches the result."""
    problem: dict[str, Any] = {'code': code, 'retryable': code == FAILED_RETRYABLE, 'message': _PROBLEM_MESSAGES[code]}
    if issues:
        problem['issues'] = [{'code': issue.code, 'field': issue.field} for issue in issues]
    return problem


def _stored_result(uow: UnitOfWork, operation_key: str) -> dict[str, Any] | None:
    with uow:
        stored = uow.records.get(KIND_ACTIVITY_RESULT, operation_key)
    return None if stored is None else copy.deepcopy(dict(stored))


def _store_result(uow: UnitOfWork, operation_key: str, input_ref: Mapping[str, Any], outcome: Mapping[str, Any]) -> None:
    record = {
        'operation_key': operation_key,
        'input_ref': copy.deepcopy(dict(input_ref)),
        'result': copy.deepcopy(dict(outcome)),
    }
    with uow:
        uow.records.put(KIND_ACTIVITY_RESULT, operation_key, record)
        uow.commit()


def handle_resolve_activity(
    request: Mapping[str, Any],
    package_loader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    deps: ResolveActivityDeps,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Resolve the one collected document of an ActivityRequest and return an ActivityResult (CT-WF-003, CT-WF-006).

    An invalid request, including a missing execution_grant, raises ActivityRequestError(VALIDATION_ERROR) and builds no
    result (D8-B-12). grant_id, execution_generation and recovery_epoch come only from the request's execution_grant.
    OSError from the loader or a port gives a failed result with a retryable problem; LookupError or an invalid package
    gives a failed result that is not retryable. Only a succeeded result is stored under operation_key; the same key
    returns that stored result without loading or resolving again, and a different input_ref is OPERATION_KEY_CONFLICT.
    """
    issues = validate_resolve_request(request)
    if issues:
        raise ActivityRequestError(VALIDATION_ERROR, issues)
    grant = request['execution_grant']
    input_ref = request['input_refs'][0]
    operation_key = request['operation_key']

    def build(disposition: str, output_refs: list[dict[str, str]], problem: dict[str, Any] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            'stage_run_id': request['stage_run_id'],
            'grant_id': grant['grant_id'],
            'execution_generation': grant['execution_generation'],
            'recovery_epoch': grant['recovery_epoch'],
            'disposition': disposition,
            'output_refs': output_refs,
            'completed_at': _utc(clock()),
        }
        if problem is not None:
            result['problem'] = problem
        result_issues = validate_activity_result(result)
        if result_issues:
            raise ValueError(f'invalid ActivityResult: {result_issues}')
        return result

    try:
        stored = _stored_result(deps.uow, operation_key)
        if stored is not None:
            if stored['input_ref'] != dict(input_ref):
                return build(FAILED, [], _problem(OPERATION_KEY_CONFLICT))
            return copy.deepcopy(stored['result'])
        package = package_loader(input_ref)
        resolution = resolve_collected_document(
            package,
            deps.dedup_policy,
            deps.uow,
            deps.tier_lookup,
            clock,
            deps.id_factory,
            topic_rules=deps.topic_rules,
            recovery_epoch=grant['recovery_epoch'],
        )
        ref_id = f"{resolution['collected_document_id']}:{resolution['dedup_policy_revision']}"
        outcome = build(SUCCEEDED, [{'ref_type': REF_TYPE_RESOLUTION, 'ref_id': ref_id}])
        _store_result(deps.uow, operation_key, input_ref, outcome)
        return outcome
    except ResolveDocumentError as exc:
        return build(FAILED, [], _problem(exc.code, exc.issues))
    except OSError:
        return build(FAILED, [], _problem(FAILED_RETRYABLE))
    except LookupError:
        return build(FAILED, [], _problem(FAILED_FINAL))
