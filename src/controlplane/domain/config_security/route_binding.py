"""J-01: validator binding ProviderRouteRequest và ProviderRouteDecision (BINDING-J-PROVIDER-ROUTE 1.0.0, CT-AI-ROUTE-001).

Pure domain: no I/O, no clock, no mutation. Issues are plain dicts `{code, field}`; an empty list means valid.
Unknown fields are ignored (additive_optional_only); only the forbidden fields of a decision are rejected, whatever their value.
Forbidden keys are matched case-insensitively and reported by their canonical binding name. The module does not import the P1 router or adapter modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
FORBIDDEN_FIELD = 'forbidden_field'

# field name -> (binding type, required), in binding order
REQUEST_FIELDS = MappingProxyType({
    'ai_role': ('string', True),
    'job_ref': ('string', True),
    'snapshot_ref': ('string', True),
    'config_refs': ('array', True),
    'data_sensitivity': ('string', True),
    'quality_latency_cost_bounds': ('object', True),
    'allowed_fallbacks': ('array', True),
    'health_quota_ref': ('string', False),
})
DECISION_FIELDS = MappingProxyType({
    'provider_ref': ('string', True),
    'model_ref': ('string', True),
    'account_ref': ('string', True),
    'route_revision': ('string', True),
    'rationale_codes': ('array', True),
    'fallback_order': ('array', True),
    'capacity_reservation_ref': ('string', True),
    'credential_acquisition_method': ('string', True),
    'estimated_cost_class': ('string', True),
    'project_ref': ('string', False),
})
DECISION_ARRAY_ITEMS = MappingProxyType({'rationale_codes': 'string'})
FORBIDDEN_DECISION_FIELDS = ('secret_value', 'api_key', 'access_token', 'refresh_token')


@dataclass(frozen=True)
class ProviderRouteRequest:
    ai_role: str
    job_ref: str
    snapshot_ref: str
    config_refs: list[Any]
    data_sensitivity: str
    quality_latency_cost_bounds: dict[str, Any]
    allowed_fallbacks: list[Any]
    health_quota_ref: str | None = None


@dataclass(frozen=True)
class ProviderRouteDecision:
    provider_ref: str
    model_ref: str
    account_ref: str
    route_revision: str
    rationale_codes: list[str]
    fallback_order: list[Any]
    capacity_reservation_ref: str
    credential_acquisition_method: str
    estimated_cost_class: str
    project_ref: str | None = None


_NO_ITEMS = MappingProxyType({})


def _issue(code: str, field: str) -> dict[str, str]:
    return {'code': code, 'field': field}


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'object':
        return isinstance(value, dict)
    return False


def _check_fields(payload: dict, fields: MappingProxyType, array_items: MappingProxyType) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for name, (type_name, required) in fields.items():
        if name not in payload:
            if required:
                issues.append(_issue(MISSING_REQUIRED, name))
        elif not _matches_type(payload[name], type_name):
            issues.append(_issue(WRONG_TYPE, name))
        elif name in array_items and not all(_matches_type(item, array_items[name]) for item in payload[name]):
            issues.append(_issue(WRONG_TYPE, name))
    return issues


def validate_route_request(payload: dict) -> list[dict]:
    """Return `{code, field}` issues of a ProviderRouteRequest payload (CT-AI-ROUTE-001); empty list means valid.

    A present field whose value is None or of the wrong type is wrong_type. A payload that is not a dict is wrong_type on '$'.
    """
    if not isinstance(payload, dict):
        return [_issue(WRONG_TYPE, '$')]
    return _check_fields(payload, REQUEST_FIELDS, _NO_ITEMS)


def validate_route_decision(payload: dict) -> list[dict]:
    """Return `{code, field}` issues of a ProviderRouteDecision payload (CT-AI-ROUTE-001); empty list means valid.

    rationale_codes must be an array of strings. secret_value, api_key, access_token and refresh_token are forbidden_field whatever
    their value; keys are compared case-insensitively and each canonical name is reported once, after the field issues.
    """
    if not isinstance(payload, dict):
        return [_issue(WRONG_TYPE, '$')]
    issues = _check_fields(payload, DECISION_FIELDS, DECISION_ARRAY_ITEMS)
    present = {key.casefold() for key in payload if isinstance(key, str)}
    issues.extend(_issue(FORBIDDEN_FIELD, name) for name in FORBIDDEN_DECISION_FIELDS if name in present)
    return issues
