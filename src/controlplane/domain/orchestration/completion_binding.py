"""G-02: CommitVideoCompletionRequest and CompletionLedgerEntry boundary validators
(CT-ORC-008, CT-ORC-009, BINDING-G-C-I-COMPLETION 1.0.0).

Field specs mirror the binding entities in binding order; unknown additive fields are ignored.

Pure domain: no I/O, no clock.

coveredIds: CT-ORC-008, CT-ORC-009
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
BINDING_VERSION = '1.0.0'


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool


def _required(**types: str) -> tuple[FieldSpec, ...]:
    return tuple(FieldSpec(name, kind, True) for name, kind in types.items())


COMMIT_REQUEST_FIELDS = _required(
    video_job_id='string',
    snapshot_ref='string',
    script_version_ref='string',
    production_plan_ref='string',
    render_attempt_ref='string',
    quality_report_ref='string',
    output_artifact_version_id='string',
    output_sha256='sha256',
    cloud_location_verification_ref='string',
    output_metadata_revision='string',
    variant_validation_ref='string',
    variant_reservation_id='string',
    expected_variant_registry_revision='integer',
    media_usage_manifest='array',
    grant_id='string',
    execution_generation='integer',
    recovery_epoch='string',
)

LEDGER_ENTRY_FIELDS = _required(
    completion_id='string',
    video_job_id='string',
    batch_ref='string',
    session_ref='string',
    output_artifact_version_id='string',
    output_sha256='sha256',
    cloud_location_ref='string',
    snapshot_ref='string',
    script_version_ref='string',
    production_plan_ref='string',
    preset_revision_ref='string',
    quality_report_ref='string',
    variant_validation_ref='string',
    media_usage_manifest='array',
    completed_at='datetime',
    output_naming_metadata='object',
    cost_usage_summary='object',
    audit_actor='string',
    cleanup_policy_ref='string',
)

_SHA256_RE = re.compile(r'[0-9a-f]{64}')
_DATETIME_RE = re.compile(
    r'([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?(?:Z|[+-]([0-9]{2}):([0-9]{2}))'
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = _DATETIME_RE.fullmatch(value)
    if match is None:
        return False
    year, month, day, hour, minute, second = (int(match.group(index)) for index in range(1, 7))
    offset_hour = int(match.group(7) or 0)
    offset_minute = int(match.group(8) or 0)
    if offset_hour > 23 or offset_minute > 59 or second > 60:
        return False
    try:
        datetime(year, month, day, hour, minute, min(second, 59))
    except ValueError:
        return False
    return True


_TYPE_CHECKS = {
    'string': lambda value: isinstance(value, str),
    'integer': _is_int,
    'object': lambda value: isinstance(value, Mapping),
    'array': lambda value: isinstance(value, list),
    'sha256': lambda value: isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
    'datetime': _is_rfc3339,
}


def _error(code: str, field: str) -> dict[str, str]:
    return {'code': code, 'field': field}


def _validate(payload: object, specs: tuple[FieldSpec, ...]) -> list[dict[str, str]]:
    if not isinstance(payload, Mapping):
        return [_error(WRONG_TYPE, '$')]
    errors = []
    for spec in specs:
        if spec.name not in payload:
            if spec.required:
                errors.append(_error(MISSING_REQUIRED, spec.name))
            continue
        value = payload[spec.name]
        if value is None or not _TYPE_CHECKS[spec.type](value):
            errors.append(_error(WRONG_TYPE, spec.name))
    return errors


def validate_commit_request(payload: object) -> list[dict[str, str]]:
    """Return binding errors [{code, field}] for a CommitVideoCompletionRequest; [] when valid."""
    return _validate(payload, COMMIT_REQUEST_FIELDS)


def validate_ledger_entry(payload: object) -> list[dict[str, str]]:
    """Return binding errors [{code, field}] for a CompletionLedgerEntry; [] when valid."""
    return _validate(payload, LEDGER_ENTRY_FIELDS)


__all__ = [
    'BINDING_VERSION',
    'COMMIT_REQUEST_FIELDS',
    'FieldSpec',
    'LEDGER_ENTRY_FIELDS',
    'MISSING_REQUIRED',
    'WRONG_TYPE',
    'validate_commit_request',
    'validate_ledger_entry',
]
