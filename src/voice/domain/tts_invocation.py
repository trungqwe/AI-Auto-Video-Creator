"""TTS route resolution and invocation domain values (CT-AI-ROUTE-001, CT-AI-ROUTE-002, CT-TTS-001).

Constants mirror BINDING-J-PROVIDER-ROUTE; unknown additive fields are ignored.
Pure domain: no I/O, no clock, no network. E never holds secrets, so every error text is redacted before it is recorded; no default attempt limits.
"""
from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field, replace
import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from types import MappingProxyType

from voice.domain.voice_track import (
    INPUT_NOT_READY,
    VoiceTrackRejected,
    compute_voice_hash,
    verify_script_binding,
)
from voice.ports.script_text import ScriptText

BINDING_VERSION = '1.0.0'
MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
FORBIDDEN_FIELD = 'forbidden_field'
FALLBACK_NOT_ALLOWED = 'fallback_not_allowed'
REDACTED = '[REDACTED]'
ERROR_TIMEOUT = 'timeout'
ERROR_RATE_LIMIT = 'rate_limit'
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
    """Return boundary issues of a ProviderRouteRequest payload (CT-AI-ROUTE-001); request also fail-closed with secret key per INV-012."""
    return _validate(payload, ROUTE_REQUEST_REQUIRED, ROUTE_REQUEST_OPTIONAL, {}, ROUTE_DECISION_FORBIDDEN)


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


def _require_int(name: str, value: object, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
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


_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
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


def fingerprint_tts_input(script_text: ScriptText, request: Mapping[str, object]) -> str:
    """Fingerprint exact TTS input; calls verify_script_binding first; NEVER hash script_text.text."""
    verify_script_binding(request, script_text)
    return fingerprint({
        'expected_language': request['expected_language'],
        'pronunciation_hints': request.get('pronunciation_hints') or [],
        'script_fingerprint': script_text.script_fingerprint,
        'script_version_id': script_text.script_version_id,
        'style_parameters': request.get('style_parameters') or {},
        'voice_profile_ref': request['voice_profile_ref'],
    })


class TtsProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        latency_ms: int = 0,
        known_secrets: Iterable[str] = (),
    ) -> None:
        _require_text('code', code)
        if not isinstance(message, str):
            raise TypeError('message must be str')
        if not isinstance(retryable, bool):
            raise TypeError('retryable must be a bool')
        _require_int('latency_ms', latency_ms, 0)
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must not be str')
        redacted = redact_error(message, known_secrets)
        self.code = code
        self.message = redacted
        self.retryable = retryable
        self.latency_ms = latency_ms
        super().__init__(redacted)


class UsageMetrics(Mapping):
    __slots__ = ('_data',)

    def __init__(self, data: object = None) -> None:
        if data is None:
            source = {}
        elif not isinstance(data, Mapping):
            raise TypeError('data must be a Mapping')
        else:
            source = data
        for k in source.keys():
            if not isinstance(k, str):
                raise ValueError('all keys must be str')
        found: list[str] = []
        _find_forbidden(source, frozenset(ROUTE_DECISION_FORBIDDEN), found)
        if found:
            sep = ', '
            raise ValueError(f'forbidden keys in usage_metrics: {sep.join(found)}')
        try:
            json.dumps(dict(source), sort_keys=True)
        except (TypeError, ValueError) as err:
            raise ValueError(f'usage_metrics must be json serializable: {err}')
        self._data = copy.deepcopy(dict(source))

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f'UsageMetrics({self._data!r})'

    def __copy__(self) -> UsageMetrics:
        return self

    def __deepcopy__(self, memo: object) -> UsageMetrics:
        return self

    def to_dict(self) -> dict[str, object]:
        return copy.deepcopy(self._data)


@dataclass(frozen=True, kw_only=True)
class TtsSynthesis:
    audio_bytes: bytes = field(repr=False)
    voice_revision: str
    usage_metrics: Mapping
    latency_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.audio_bytes, bytes):
            raise TypeError('audio_bytes must be bytes')
        if len(self.audio_bytes) == 0:
            raise ValueError('audio_bytes must not be empty')
        _require_text('voice_revision', self.voice_revision)
        _require_int('latency_ms', self.latency_ms, 0)
        object.__setattr__(self, 'usage_metrics', UsageMetrics(self.usage_metrics))


@dataclass(frozen=True, kw_only=True)
class TtsInvocationRecord:
    provider_ref: str
    model_ref: str
    account_ref: str
    route_revision: str
    input_fingerprint: str
    usage_metrics: Mapping
    latency_ms: int
    attempt: int
    fallback_path: tuple[str, ...]
    validation_result: str
    project_ref: str | None = None
    voice_revision: str | None = None
    output_fingerprint: str | None = None
    error: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        _require_text('provider_ref', self.provider_ref)
        _require_text('model_ref', self.model_ref)
        _require_text('account_ref', self.account_ref)
        _require_text('route_revision', self.route_revision)
        if self.project_ref is not None:
            _require_text('project_ref', self.project_ref)
        if not _is_sha256(self.input_fingerprint):
            raise ValueError('input_fingerprint must be a 64 lowercase hex characters')
        if not isinstance(self.usage_metrics, Mapping):
            raise TypeError('usage_metrics must be a Mapping')
        object.__setattr__(self, 'usage_metrics', UsageMetrics(self.usage_metrics))
        _require_int('latency_ms', self.latency_ms, 0)
        _require_int('attempt', self.attempt, 1)
        if isinstance(self.fallback_path, (str, bytes)) or not isinstance(self.fallback_path, Iterable):
            raise ValueError('fallback_path must be an Iterable, not str/bytes')
        path_tuple = tuple(self.fallback_path)
        if not path_tuple:
            raise ValueError('fallback_path must not be empty')
        for item in path_tuple:
            _require_text('fallback_path item', item)
        if path_tuple[-1] != self.provider_ref:
            raise ValueError('last item in fallback_path must be provider_ref')
        object.__setattr__(self, 'fallback_path', path_tuple)
        if self.validation_result not in VALIDATION_RESULTS:
            raise ValueError(f'validation_result must be in {VALIDATION_RESULTS}')
        if self.error is None:
            _require_text('voice_revision', self.voice_revision)
            if not _is_sha256(self.output_fingerprint):
                raise ValueError('output_fingerprint must be sha256 hex string when error is None')
            if self.error_code is not None:
                raise ValueError('error_code must be None when error is None')
        else:
            if not isinstance(self.error, str) or not self.error:
                raise ValueError('error must be a non-empty string')
            if redact_error(self.error) != self.error:
                raise ValueError('error must be redacted')
            _require_text('error_code', self.error_code)
            if self.voice_revision is not None:
                raise ValueError('voice_revision must be None when error is present')
            if self.output_fingerprint is not None:
                raise ValueError('output_fingerprint must be None when error is present')

    def to_payload(self) -> dict[str, object]:
        return {
            'provider_ref': self.provider_ref,
            'model_ref': self.model_ref,
            'account_ref': self.account_ref,
            'project_ref': self.project_ref,
            'route_revision': self.route_revision,
            'voice_revision': self.voice_revision,
            'input_fingerprint': self.input_fingerprint,
            'output_fingerprint': self.output_fingerprint,
            'usage_metrics': self.usage_metrics.to_dict() if isinstance(self.usage_metrics, UsageMetrics) else dict(self.usage_metrics),
            'latency_ms': self.latency_ms,
            'attempt': self.attempt,
            'fallback_path': list(self.fallback_path),
            'validation_result': self.validation_result,
            'error': self.error,
            'error_code': self.error_code,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True, kw_only=True)
class TtsAttemptPolicy:
    max_attempts: int
    max_attempts_per_provider: int

    def __post_init__(self) -> None:
        _require_int('max_attempts', self.max_attempts, 1)
        _require_int('max_attempts_per_provider', self.max_attempts_per_provider, 1)


def parse_attempt_policy(policy: object) -> TtsAttemptPolicy:
    """Parse attempt limits from policy; missing policy or missing bound raises VoiceTrackRejected(INPUT_NOT_READY)."""
    if policy is None:
        raise VoiceTrackRejected(INPUT_NOT_READY, 'missing_attempt_policy')
    if not isinstance(policy, Mapping):
        raise TypeError('policy must be a Mapping')
    for name in ('max_attempts', 'max_attempts_per_provider'):
        value = policy.get(name)
        if value is None:
            raise VoiceTrackRejected(INPUT_NOT_READY, 'missing_attempt_policy')
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f'{name} must be an integer >= 1')
    return TtsAttemptPolicy(
        max_attempts=policy['max_attempts'],
        max_attempts_per_provider=policy['max_attempts_per_provider'],
    )


class FallbackNotAllowed(ValueError):
    def __init__(self, provider_ref: str) -> None:
        self.provider_ref = provider_ref
        self.code = FALLBACK_NOT_ALLOWED
        super().__init__(f'{FALLBACK_NOT_ALLOWED}: {provider_ref}')


def plan_provider_path(
    decision: ProviderRouteDecision,
    route_request: Mapping[str, object],
) -> tuple[str, ...]:
    """Determine provider path following decision.fallback_order within route_request allowed_fallbacks."""
    if not isinstance(decision, ProviderRouteDecision):
        raise TypeError('decision must be ProviderRouteDecision')
    issues = validate_provider_route_request(route_request)
    if issues:
        raise RouteContractViolation('ProviderRouteRequest', issues)
    allowed = route_request['allowed_fallbacks']
    if not all(isinstance(x, str) for x in allowed):
        raise RouteContractViolation('ProviderRouteRequest', [ValidationIssue(WRONG_TYPE, 'allowed_fallbacks')])
    path = [decision.provider_ref]
    for ref in decision.fallback_order:
        if ref not in allowed:
            raise FallbackNotAllowed(ref)
        if ref not in path:
            path.append(ref)
    return tuple(path)


@dataclass(frozen=True)
class TtsRunOutcome:
    synthesis: TtsSynthesis | None
    records: tuple[TtsInvocationRecord, ...]
    error: TtsProviderError | None

    def __post_init__(self) -> None:
        if (self.synthesis is None) == (self.error is None):
            raise ValueError('exactly one of synthesis or error must be non-None')
        object.__setattr__(self, 'records', tuple(self.records))


def run_tts_attempts(
    engine: object,
    decision: ProviderRouteDecision,
    route_request: Mapping[str, object],
    voice_request: Mapping[str, object],
    script_text: ScriptText,
    policy: object,
) -> TtsRunOutcome:
    """Execute TTS attempts bounded by policy with deterministic fallback path.

    model_ref and account_ref of decision apply to all fallback attempts (GIẢ ĐỊNH; J assigns decision per provider at CONV-E-11).
    True retry/fallback decisions belong to G (CONV-E-05).
    """
    if not isinstance(decision, ProviderRouteDecision) or not isinstance(script_text, ScriptText):
        raise TypeError('decision must be ProviderRouteDecision and script_text must be ScriptText')
    input_fp = fingerprint_tts_input(script_text, voice_request)
    budget = parse_attempt_policy(policy)
    path = plan_provider_path(decision, route_request)
    attempt = 0
    records: list[TtsInvocationRecord] = []
    last_error: TtsProviderError | None = None
    for index, provider_ref in enumerate(path):
        for _ in range(budget.max_attempts_per_provider):
            if attempt >= budget.max_attempts:
                break
            attempt += 1
            try:
                synthesis = engine.synthesize(replace(decision, provider_ref=provider_ref), script_text, voice_request)
            except TtsProviderError as error:
                last_error = error
                records.append(TtsInvocationRecord(
                    provider_ref=provider_ref,
                    model_ref=decision.model_ref,
                    account_ref=decision.account_ref,
                    route_revision=decision.route_revision,
                    project_ref=decision.project_ref,
                    input_fingerprint=input_fp,
                    usage_metrics={},
                    latency_ms=error.latency_ms,
                    attempt=attempt,
                    fallback_path=path[:index + 1],
                    validation_result='not_run',
                    error=error.message,
                    error_code=error.code,
                ))
                if not error.retryable:
                    break
                continue
            if not isinstance(synthesis, TtsSynthesis):
                raise TypeError('engine.synthesize must return TtsSynthesis')
            records.append(TtsInvocationRecord(
                provider_ref=provider_ref,
                model_ref=decision.model_ref,
                account_ref=decision.account_ref,
                route_revision=decision.route_revision,
                project_ref=decision.project_ref,
                input_fingerprint=input_fp,
                voice_revision=synthesis.voice_revision,
                output_fingerprint=compute_voice_hash(synthesis.audio_bytes),
                usage_metrics=synthesis.usage_metrics,
                latency_ms=synthesis.latency_ms,
                attempt=attempt,
                fallback_path=path[:index + 1],
                validation_result='not_run',
                error=None,
                error_code=None,
            ))
            return TtsRunOutcome(synthesis=synthesis, records=tuple(records), error=None)
        if attempt >= budget.max_attempts:
            break
    return TtsRunOutcome(synthesis=None, records=tuple(records), error=last_error)
