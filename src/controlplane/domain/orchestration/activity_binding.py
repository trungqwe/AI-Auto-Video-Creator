"""G-01: validator binding ActivityRequest và ActivityResult (BINDING-G-ACTIVITY-EXECUTION 1.0.0, CT-WF-003, CT-WF-006).

Pure domain: no I/O, no clock, no mutation. Issues are plain dicts `{code, field}`; an empty list means valid.
Unknown fields are ignored (additive_optional_only); only the forbidden fields of ActivityRequest are rejected.
`recovery_epoch` is a string here; comparing epochs with `str()` is the caller's concern (D8-G-03).
"""
from __future__ import annotations

import re
from datetime import datetime
from types import MappingProxyType

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
FORBIDDEN_FIELD = 'forbidden_field'

EXECUTION_GRANT = 'execution_grant'
ACTIVITY_REQUEST_FIELDS = MappingProxyType({
    'workflow_id': 'string',
    'workflow_run_id': 'string',
    'stage_run_id': 'string',
    'activity_name': 'string',
    'activity_version': 'string',
    'input_refs': 'array',
    'operation_key': 'string',
    'capability_requirements': 'object',
    'retry_policy_ref': 'string',
    'video_job_id': 'string',
    'execution_grant': 'object',
    'deadline_at': 'datetime',
})
ACTIVITY_REQUEST_REQUIRED = frozenset({
    'workflow_id', 'workflow_run_id', 'stage_run_id', 'activity_name', 'activity_version',
    'input_refs', 'operation_key', 'capability_requirements', 'retry_policy_ref',
})
ACTIVITY_REQUEST_FORBIDDEN = ('secret_value', 'raw_blob')
ACTIVITY_RESULT_FIELDS = MappingProxyType({
    'stage_run_id': 'string',
    'grant_id': 'string',
    'execution_generation': 'integer',
    'recovery_epoch': 'string',
    'disposition': 'string',
    'output_refs': 'array',
    'completed_at': 'datetime',
    'metrics': 'object',
    'warnings': 'array',
    'problem': 'object',
    'operation_receipt_ref': 'string',
})
ACTIVITY_RESULT_REQUIRED = frozenset({
    'stage_run_id', 'grant_id', 'execution_generation', 'recovery_epoch', 'disposition', 'output_refs', 'completed_at',
})
DISPOSITIONS = ('succeeded', 'failed', 'waiting', 'outcome_unknown', 'stale')

_RFC3339_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})')


def _issue(code: str, field: str) -> dict[str, str]:
    return {'code': code, 'field': field}


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_RE.fullmatch(value):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, dict)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'datetime':
        return _is_rfc3339(value)
    return False


def _check_fields(payload: dict, fields: MappingProxyType, required: frozenset, enums: dict) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for name, type_name in fields.items():
        if name not in payload:
            if name in required:
                issues.append(_issue(MISSING_REQUIRED, name))
        elif not _matches_type(payload[name], type_name):
            issues.append(_issue(WRONG_TYPE, name))
        elif name in enums and payload[name] not in enums[name]:
            issues.append(_issue(ENUM_VIOLATION, name))
    return issues


def validate_activity_request(payload: dict, side_effect: bool = False) -> list[dict]:
    """Return `{code, field}` issues of an ActivityRequest payload (CT-WF-003); empty list means valid.

    With side_effect=True a missing execution_grant is missing_required. secret_value and raw_blob are forbidden_field
    whatever their value. Raises TypeError for a non-bool side_effect.
    """
    if not isinstance(side_effect, bool):
        raise TypeError('side_effect must be bool')
    if not isinstance(payload, dict):
        return [_issue(WRONG_TYPE, '$')]
    required = (ACTIVITY_REQUEST_REQUIRED | {EXECUTION_GRANT}) if side_effect else ACTIVITY_REQUEST_REQUIRED
    issues = _check_fields(payload, ACTIVITY_REQUEST_FIELDS, required, {})
    issues.extend(_issue(FORBIDDEN_FIELD, name) for name in ACTIVITY_REQUEST_FORBIDDEN if name in payload)
    return issues


def validate_activity_result(payload: dict) -> list[dict]:
    """Return `{code, field}` issues of an ActivityResult payload (CT-WF-006); empty list means valid."""
    if not isinstance(payload, dict):
        return [_issue(WRONG_TYPE, '$')]
    return _check_fields(payload, ACTIVITY_RESULT_FIELDS, ACTIVITY_RESULT_REQUIRED, {'disposition': DISPOSITIONS})
