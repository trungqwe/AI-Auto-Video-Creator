"""AI route and invocation domain values (CT-AI-ROUTE-001, CT-AI-010, TST-SEC-INV-012).

Constants mirror BINDING-J-PROVIDER-ROUTE; unknown additive fields are ignored.
Pure domain: no I/O, no clock, no network. D never holds a secret, so every error text is redacted before it is recorded.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType

from creative.domain.untrusted import ModelOutput, PromptEnvelope

BINDING_VERSION = '1.0.0'
MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
FORBIDDEN_FIELD = 'forbidden_field'
REDACTED = '[REDACTED]'
VALIDATION_RESULTS = ('not_run', 'passed', 'failed')

ROUTE_REQUEST_REQUIRED = MappingProxyType({
    'ai_role': 'string',
    'job_ref': 'string',
    'snapshot_ref': 'string',
    'config_refs': 'array',
    'data_sensitivity': 'string',
    'quality_latency_cost_bounds': 'object',
    'allowed_fallbacks': 'array',
})
ROUTE_REQUEST_OPTIONAL = MappingProxyType({'health_quota_ref': 'string'})
ROUTE_DECISION_REQUIRED = MappingProxyType({
    'provider_ref': 'string',
    'model_ref': 'string',
    'account_ref': 'string',
    'route_revision': 'string',
    'rationale_codes': 'array',
    'fallback_order': 'array',
    'capacity_reservation_ref': 'string',
    'credential_acquisition_method': 'string',
    'estimated_cost_class': 'string',
})
ROUTE_DECISION_OPTIONAL = MappingProxyType({'project_ref': 'string'})
ROUTE_DECISION_ITEMS = MappingProxyType({'rationale_codes': 'string'})
ROUTE_DECISION_FORBIDDEN = ('secret_value', 'api_key', 'access_token', 'refresh_token')


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


def matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'object':
        return isinstance(value, Mapping)
    if type_name == 'array':
        return isinstance(value, (list, tuple))
    return False


def _find_forbidden(value: object, forbidden: frozenset[str], found: list[str]) -> None:
    """Collect forbidden key names (case-insensitive) at any nesting depth of mappings, lists and tuples."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = key.casefold() if isinstance(key, str) else None
            if name in forbidden and name not in found:
                found.append(name)
            _find_forbidden(item, forbidden, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _find_forbidden(item, forbidden, found)


def _validate(
    payload: object,
    required: Mapping[str, str],
    optional: Mapping[str, str],
    items: Mapping[str, str],
    forbidden: Iterable[str],
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
        if not matches_type(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in items and any(not matches_type(item, items[name]) for item in value):
            issues.append(ValidationIssue(WRONG_TYPE, name))
    found: list[str] = []
    _find_forbidden(payload, frozenset(forbidden), found)
    issues.extend(ValidationIssue(FORBIDDEN_FIELD, name) for name in found)
    return issues


def validate_provider_route_request(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a ProviderRouteRequest payload (CT-AI-ROUTE-001); empty list means valid."""
    return _validate(payload, ROUTE_REQUEST_REQUIRED, ROUTE_REQUEST_OPTIONAL, {}, ())


def validate_provider_route_decision(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a ProviderRouteDecision payload; a forbidden secret key at any nesting depth is a forbidden_field issue."""
    return _validate(
        payload, ROUTE_DECISION_REQUIRED, ROUTE_DECISION_OPTIONAL, ROUTE_DECISION_ITEMS, ROUTE_DECISION_FORBIDDEN
    )


class RouteContractViolation(ValueError):
    """A route payload breaks the binding; the message carries issue codes and field names only, never values."""

    def __init__(self, entity: str, issues: Iterable[ValidationIssue]) -> None:
        self.entity = entity
        self.issues = tuple(issues)
        super().__init__(f'{entity}: ' + ', '.join(f'{issue.code}:{issue.field}' for issue in self.issues))


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _listed(value: object) -> object:
    return list(value) if isinstance(value, (list, tuple)) else value


@dataclass(frozen=True, kw_only=True)
class ProviderRouteDecision:
    """CT-AI-ROUTE-001 output: refs only, never a secret; a decision carrying a forbidden field at any depth cannot be constructed."""

    provider_ref: str
    model_ref: str
    account_ref: str
    route_revision: str
    rationale_codes: tuple[str, ...]
    fallback_order: tuple[str, ...]
    capacity_reservation_ref: str
    credential_acquisition_method: str
    estimated_cost_class: str
    project_ref: str | None = None

    def __post_init__(self) -> None:
        issues = validate_provider_route_decision(self.to_payload())
        if not issues and not all(isinstance(item, str) for item in self.fallback_order):
            issues = [ValidationIssue(WRONG_TYPE, 'fallback_order')]
        if issues:
            raise RouteContractViolation('ProviderRouteDecision', issues)
        object.__setattr__(self, 'rationale_codes', tuple(self.rationale_codes))
        object.__setattr__(self, 'fallback_order', tuple(self.fallback_order))

    def to_payload(self) -> dict[str, object]:
        """Return the binding payload (plain dict/list); project_ref is omitted when None."""
        names = (*ROUTE_DECISION_REQUIRED, *ROUTE_DECISION_OPTIONAL)
        payload: dict[str, object] = {name: _listed(getattr(self, name)) for name in names}
        if payload['project_ref'] is None:
            del payload['project_ref']
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> ProviderRouteDecision:
        """Build a decision from a binding payload; unknown additive fields are ignored, violations raise RouteContractViolation."""
        issues = validate_provider_route_decision(payload)
        if issues:
            raise RouteContractViolation('ProviderRouteDecision', issues)
        names = (*ROUTE_DECISION_REQUIRED, *ROUTE_DECISION_OPTIONAL)
        return cls(**{name: payload[name] for name in names if payload.get(name) is not None})


@dataclass(frozen=True)
class InvocationUsage:
    """Token usage and cost class of one invocation, scoped to the project."""

    input_tokens: int
    output_tokens: int
    cost_class: str

    def __post_init__(self) -> None:
        for name in ('input_tokens', 'output_tokens'):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f'{name} must be a non-negative integer')
        _require_text('cost_class', self.cost_class)


_SHA256_RE = re.compile(r'[0-9a-f]{64}')
_SECRET_PATTERNS = (
    (
        re.compile(
            r'(?i)\b(secret_value|api_key|access_token|refresh_token|authorization|password)'
            r'([\x22\x27]?\s*[=:]\s*[\x22\x27]?)(?:bearer\s+)?[^\s,;&\x22\x27}]+'
        ),
        r'\1\2' + REDACTED,
    ),
    (re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+'), 'Bearer ' + REDACTED),
    (re.compile(r'\bsk-[A-Za-z0-9_-]{8,}'), REDACTED),
)


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def redact_error(message: str, known_secrets: Iterable[str] = ()) -> str:
    """Return message with each known secret value and every credential-looking token replaced by [REDACTED]."""
    if not isinstance(message, str):
        raise TypeError('message must be str')
    if isinstance(known_secrets, str):
        raise TypeError('known_secrets must be an iterable of str, not a single str')
    secrets = tuple(known_secrets)
    if not all(isinstance(secret, str) for secret in secrets):
        raise TypeError('known_secrets items must be str')
    text = message
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def fingerprint(value: object) -> str:
    """Return the SHA-256 hex of the canonical JSON (sorted keys, no whitespace) of value."""
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def fingerprint_envelope(envelope: PromptEnvelope) -> str:
    """Fingerprint the exact model input: prompt ref, instructions and every untrusted data item with its provenance."""
    if not isinstance(envelope, PromptEnvelope):
        raise TypeError('envelope must be a PromptEnvelope')
    return fingerprint({
        'prompt_ref': asdict(envelope.prompt_ref),
        'instructions': envelope.instructions,
        'data': [{'text': item.text, 'provenance': asdict(item.provenance)} for item in envelope.data],
    })


def fingerprint_output(output: ModelOutput) -> str:
    """Fingerprint the model output: text and proposed refs."""
    if not isinstance(output, ModelOutput):
        raise TypeError('output must be a ModelOutput')
    return fingerprint({'text': output.text, 'proposed_refs': [dict(ref) for ref in output.proposed_refs]})


@dataclass(frozen=True, kw_only=True)
class AIInvocationRecord:
    """CT-AI-010 record of one invocation: refs, revisions and fingerprints only; its error text is always redacted."""

    ai_role: str
    provider_ref: str
    model_ref: str
    account_ref: str
    route_revision: str
    prompt_revision: str
    config_revision: str
    input_fingerprint: str
    usage: InvocationUsage
    latency_ms: int
    attempt: int
    fallback_path: tuple[str, ...]
    validation_result: str
    project_ref: str | None = None
    output_fingerprint: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name in ('ai_role', 'provider_ref', 'model_ref', 'account_ref', 'route_revision', 'prompt_revision', 'config_revision'):
            _require_text(name, getattr(self, name))
        if self.project_ref is not None:
            _require_text('project_ref', self.project_ref)
        if not isinstance(self.usage, InvocationUsage):
            raise TypeError('usage must be an InvocationUsage')
        for name, minimum in (('latency_ms', 0), ('attempt', 1)):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f'{name} must be an integer >= {minimum}')
        path = self.fallback_path
        if isinstance(path, (str, bytes)) or not isinstance(path, Iterable):
            raise ValueError('fallback_path must be a non-empty sequence of strings')
        path = tuple(path)
        if not path:
            raise ValueError('fallback_path must name at least the primary provider')
        for item in path:
            _require_text('fallback_path item', item)
        object.__setattr__(self, 'fallback_path', path)
        if self.validation_result not in VALIDATION_RESULTS:
            raise ValueError(f'validation_result must be one of {VALIDATION_RESULTS!r}')
        if not _is_sha256(self.input_fingerprint):
            raise ValueError('input_fingerprint must be 64 lowercase hex characters')
        if self.error is None:
            if not _is_sha256(self.output_fingerprint):
                raise ValueError('output_fingerprint is required when there is no error')
        else:
            if self.output_fingerprint is not None:
                raise ValueError('output_fingerprint must be None when there is an error')
            if not isinstance(self.error, str) or redact_error(self.error) != self.error:
                raise ValueError('error must be redacted')

    def to_payload(self) -> dict[str, object]:
        """Return the JSON-safe record payload (plain dict/list); every field is present, None where absent."""
        return {
            'ai_role': self.ai_role,
            'provider_ref': self.provider_ref,
            'model_ref': self.model_ref,
            'account_ref': self.account_ref,
            'project_ref': self.project_ref,
            'route_revision': self.route_revision,
            'prompt_revision': self.prompt_revision,
            'config_revision': self.config_revision,
            'input_fingerprint': self.input_fingerprint,
            'output_fingerprint': self.output_fingerprint,
            'usage': {
                'input_tokens': self.usage.input_tokens,
                'output_tokens': self.usage.output_tokens,
                'cost_class': self.usage.cost_class,
            },
            'latency_ms': self.latency_ms,
            'attempt': self.attempt,
            'fallback_path': list(self.fallback_path),
            'validation_result': self.validation_result,
            'error': self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class AIInvocationResult:
    """Outcome of AIInvocationPort.invoke: the record, plus the model output exactly when the invocation had no error."""

    record: AIInvocationRecord
    output: ModelOutput | None

    def __post_init__(self) -> None:
        if not isinstance(self.record, AIInvocationRecord):
            raise TypeError('record must be an AIInvocationRecord')
        if (self.output is None) != (self.record.error is not None):
            raise ValueError('output must be present exactly when the record has no error')
