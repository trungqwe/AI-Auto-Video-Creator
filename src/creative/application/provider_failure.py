"""Provider failure and fallback of D (D-15, CT-AI-ROUTE-002): bounded attempts, redacted problems, one AIInvocationRecord per attempt, waiting outcome for G.

coveredIds: CT-AI-ROUTE-002, CT-AI-010

Application layer: depends on domain and ports only, never on adapters, clock, id generation or network.
GIẢ ĐỊNH (D8): model_ref and account_ref of the primary ProviderRouteDecision apply to every fallback provider until J assigns a decision per provider (CONV-D-11), as in run_tts_attempts of E.
GIẢ ĐỊNH (D8): a provider error arrives as AIInvocationRecord.error (a WaitingAIInvocationResult marks a retryable wait), or as an OSError (TimeoutError included) raised by the port. A validator rejection that carries a str code and a str reason is a failed attempt unless the code is input-determined (INPUT_NOT_READY or any code ending in context_mismatch); any other exception is a defect: its attempt is recorded and committed, then it propagates.
The handler tries each provider of the path at most once per run, never beyond policy.max_attempts, and only appends records: stored output and history are never edited or deleted; G decides retry or wait from a WAITING outcome.
D-15-FIX1: pipeline.py imports this module, so the names of pipeline.py are imported inside the functions that need them.
"""
from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Mapping
from typing import Any

from controlplane.domain.interfaces.uow import IUnitOfWork
from creative.domain.invocation import (
    WRONG_TYPE,
    AIInvocationRecord,
    AIInvocationResult,
    InvocationUsage,
    ProviderRouteDecision,
    RouteContractViolation,
    ValidationIssue,
    fingerprint_envelope,
    redact_error,
    validate_provider_route_request,
)
from creative.domain.untrusted import PromptEnvelope
from creative.ports.ai import AIInvocationPort, ProviderRoutePort

PROVIDER_TIMEOUT = 'provider_timeout'
PROVIDER_RATE_LIMITED = 'provider_rate_limited'
PROVIDER_UNREACHABLE = 'provider_unreachable'
PROVIDER_ERROR = 'provider_error'
WAIT_QUOTA = 'quota_wait'
WAIT_PROVIDER_UNAVAILABLE = 'provider_unavailable'
FALLBACK_CHANGES_INTENT = 'fallback_changes_intent'
WAIT_BUDGET_EXHAUSTED = 'attempt_budget_exhausted'
WAIT_PROVIDERS_EXHAUSTED = 'providers_exhausted'
INTENT_WAIT = 'wait'
INTENT_NEW_REVISION = 'new_revision'
INTENT_MODES = (INTENT_WAIT, INTENT_NEW_REVISION)


def classify_provider_error(message: str) -> str:
    """Map a redacted provider error text to a stable problem code; unknown text is PROVIDER_ERROR."""
    text = message.casefold()
    if 'timeout' in text or 'timed out' in text:
        return PROVIDER_TIMEOUT
    if 'rate limit' in text or 'rate_limit' in text or 'rate-limit' in text or '429' in text:
        return PROVIDER_RATE_LIMITED
    return PROVIDER_ERROR


def provider_wait_code(message: str) -> str:
    """WaitReason value of a retryable waiting result: budget, quota and rate limit wait for quota, anything else (timeout, no route yet) waits for the provider."""
    text = message.casefold()
    if 'budget_blocked' in text or 'quota' in text or classify_provider_error(message) == PROVIDER_RATE_LIMITED:
        return WAIT_QUOTA
    return WAIT_PROVIDER_UNAVAILABLE


def _input_determined(code: str) -> bool:
    """INPUT_NOT_READY and every code ending in context_mismatch come from inputs known before the model call: never a model-output failure, never retried."""
    from creative.application.pipeline import INPUT_NOT_READY  # deferred: pipeline.py imports this module
    return code == INPUT_NOT_READY or code.endswith('context_mismatch')


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProviderFailurePolicy:
    """Attempt budget and intent rule from the policy input; max_attempts has no default (CT-AI-ROUTE-002)."""

    max_attempts: int
    intent_preserving_providers: frozenset[str] = frozenset()
    on_intent_change: str = INTENT_WAIT

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError('max_attempts must be an integer >= 1')
        providers = self.intent_preserving_providers
        if isinstance(providers, (str, bytes)) or not all(isinstance(item, str) for item in providers):
            raise ValueError('intent_preserving_providers must be an iterable of str')
        object.__setattr__(self, 'intent_preserving_providers', frozenset(providers))
        if self.on_intent_change not in INTENT_MODES:
            raise ValueError(f'on_intent_change must be one of {INTENT_MODES!r}')


def parse_failure_policy(policy: object) -> ProviderFailurePolicy:
    """Accept a ProviderFailurePolicy or a mapping; a missing max_attempts is INPUT_NOT_READY, never a default number."""
    from creative.application.pipeline import INPUT_NOT_READY, PipelineRejected  # deferred: pipeline.py imports this module
    if isinstance(policy, ProviderFailurePolicy):
        return policy
    if not isinstance(policy, Mapping):
        raise TypeError('policy must be a Mapping or a ProviderFailurePolicy')
    if policy.get('max_attempts') is None:
        raise PipelineRejected(INPUT_NOT_READY, 'missing_attempt_policy', 'max_attempts')
    names = ('max_attempts', 'intent_preserving_providers', 'on_intent_change')
    return ProviderFailurePolicy(**{name: policy[name] for name in names if name in policy})


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProviderProblem:
    """Structured problem of one failed attempt; reason and field are always redacted. wait_code is a WaitReason value when the provider answered with a retryable waiting result (quota, budget, rate limit, timeout), otherwise empty; it is not part of to_payload."""

    code: str
    reason: str
    provider_ref: str
    attempt: int
    field: str = ''
    wait_code: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'reason', redact_error(self.reason))
        object.__setattr__(self, 'field', redact_error(self.field))

    def to_payload(self) -> dict[str, object]:
        return {
            'code': self.code, 'reason': self.reason, 'provider_ref': self.provider_ref,
            'attempt': self.attempt, 'field': self.field,
        }


class ProviderCallStatus(enum.Enum):
    ACCEPTED = 'accepted'
    NEW_REVISION = 'new_revision'
    WAITING = 'waiting'


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProviderCallOutcome:
    """Result of one run: ACCEPTED or NEW_REVISION carry the validated output and the revision it must be stored under; WAITING carries the reason and the last problem for G."""

    status: ProviderCallStatus
    output: object | None
    output_revision: int | None
    records: tuple[AIInvocationRecord, ...]
    problems: tuple[ProviderProblem, ...]
    wait_reason: str | None
    provider_path: tuple[str, ...]
    skipped_fallbacks: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status is ProviderCallStatus.WAITING:
            if self.output is not None or self.output_revision is not None or not self.wait_reason:
                raise ValueError('a WAITING outcome has a wait_reason and no output')
        elif self.output is None or self.output_revision is None or self.wait_reason is not None:
            raise ValueError('an accepted outcome has an output and an output_revision and no wait_reason')

    @property
    def problem(self) -> ProviderProblem | None:
        """The last problem when the outcome is WAITING, otherwise None."""
        if self.status is ProviderCallStatus.WAITING and self.problems:
            return self.problems[-1]
        return None

    @property
    def final_record(self) -> AIInvocationRecord | None:
        return self.records[-1] if self.records else None


def _allowed_fallbacks(route_request: Mapping[str, object]) -> tuple[str, ...]:
    issues = validate_provider_route_request(route_request)
    if issues:
        raise RouteContractViolation('ProviderRouteRequest', issues)
    allowed = route_request['allowed_fallbacks']
    if not all(isinstance(item, str) for item in allowed):
        raise RouteContractViolation('ProviderRouteRequest', [ValidationIssue(WRONG_TYPE, 'allowed_fallbacks')])
    return tuple(allowed)


def plan_fallback_path(
    decision: ProviderRouteDecision, route_request: Mapping[str, object]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (path, skipped): the primary, then decision.fallback_order restricted to route_request allowed_fallbacks in the order of the decision; the other entries are skipped and never invoked."""
    if not isinstance(decision, ProviderRouteDecision):
        raise TypeError('decision must be a ProviderRouteDecision')
    allowed = _allowed_fallbacks(route_request)
    path = [decision.provider_ref]
    skipped: list[str] = []
    for ref in decision.fallback_order:
        if ref in allowed:
            if ref not in path:
                path.append(ref)
        elif ref not in skipped:
            skipped.append(ref)
    return tuple(path), tuple(skipped)


def _problem(
    code: str, reason: str, provider_ref: str, attempt: int, known_secrets: tuple[str, ...], field: str = '',
    wait_code: str = ''
) -> ProviderProblem:
    return ProviderProblem(
        code=code, reason=redact_error(reason, known_secrets), provider_ref=provider_ref, attempt=attempt,
        field=redact_error(field, known_secrets), wait_code=wait_code)


class ProviderFailureHandler:
    """Calls the routed provider with bounded fallback; every attempt is recorded in one unit of work and stored output is never edited."""

    def __init__(self, *, uow_factory: Callable[[], IUnitOfWork], route: ProviderRoutePort, ai: AIInvocationPort) -> None:
        if not callable(uow_factory):
            raise TypeError('uow_factory must be callable')
        if not isinstance(route, ProviderRoutePort) or not isinstance(ai, AIInvocationPort):
            raise TypeError('route and ai must implement the D ports')
        self._uow_factory = uow_factory
        self._route = route
        self._ai = ai

    def run(
        self,
        *,
        idempotency_key: str,
        route_request: Mapping[str, object],
        envelope: PromptEnvelope,
        config_revision: str,
        validator: Callable[[AIInvocationResult], object],
        policy: object,
        current_output_revision: int = 0,
        known_secrets: tuple[str, ...] = (),
        retry_same_provider: bool = False,
    ) -> ProviderCallOutcome:
        """Try the primary provider, then decision.fallback_order within route_request allowed_fallbacks: each provider once, at most policy.max_attempts calls; a validated output is ACCEPTED or NEW_REVISION (output_revision = current_output_revision + 1), anything else is WAITING for G. With retry_same_provider the primary provider is called again, with the same decision, envelope and config, after the path is used up and the last attempt failed validation; a provider error, a waiting result or a defect never triggers a repeat."""
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError('idempotency_key must be a non-empty string')
        if not isinstance(envelope, PromptEnvelope):
            raise TypeError('envelope must be a PromptEnvelope')
        if not isinstance(config_revision, str) or not config_revision:
            raise ValueError('config_revision must be a non-empty string')
        if not callable(validator):
            raise TypeError('validator must be callable')
        if type(current_output_revision) is not int or current_output_revision < 0:
            raise ValueError('current_output_revision must be an integer >= 0')
        secrets = tuple(known_secrets)
        redact_error('', secrets)
        _allowed_fallbacks(route_request)
        limits = parse_failure_policy(policy)
        decision = self._route.resolve(route_request)
        path, skipped = plan_fallback_path(decision, route_request)
        key = f'{envelope.prompt_ref.workspace_id}:{idempotency_key}'
        records: list[AIInvocationRecord] = []
        problems: list[ProviderProblem] = []
        invoked: list[str] = []
        output: object | None = None
        succeeded = False
        intent_changed = False
        schedule = path + (path[0],) * limits.max_attempts if retry_same_provider else path
        defect: Exception | None = None
        with self._uow_factory() as uow:
            latest = uow.invocations.latest(key)
            stored = 0 if latest is None else latest.revision
            for index, provider_ref in enumerate(schedule):
                if len(invoked) >= limits.max_attempts:
                    break
                if index >= len(path) and (not records or records[-1].validation_result != 'failed'):
                    break
                primary = provider_ref == decision.provider_ref
                intent_changed = not primary and provider_ref not in limits.intent_preserving_providers
                if intent_changed and limits.on_intent_change == INTENT_WAIT:
                    problems.append(
                        _problem(FALLBACK_CHANGES_INTENT, FALLBACK_CHANGES_INTENT, provider_ref, stored + len(invoked), secrets))
                    continue
                invoked.append(provider_ref)
                attempt = stored + len(invoked)
                call = decision if primary else dataclasses.replace(decision, provider_ref=provider_ref, fallback_order=())
                record, validated, problem, defect = self._attempt(
                    call, ai_role=route_request['ai_role'], envelope=envelope, config_revision=config_revision,
                    validator=validator, attempt=attempt, invoked=tuple(invoked), secrets=secrets)
                uow.invocations.append(key, attempt, record)
                records.append(record)
                if defect is not None:
                    break
                if problem is not None:
                    problems.append(problem)
                    if problem.wait_code:
                        break
                    continue
                output, succeeded = validated, True
                break
            uow.commit()
        if defect is not None:
            raise defect
        shared = {
            'records': tuple(records), 'problems': tuple(problems), 'provider_path': tuple(invoked),
            'skipped_fallbacks': skipped,
        }
        if succeeded:
            status = ProviderCallStatus.NEW_REVISION if intent_changed else ProviderCallStatus.ACCEPTED
            return ProviderCallOutcome(
                status=status, output=output, output_revision=current_output_revision + 1, wait_reason=None, **shared)
        if len(invoked) >= limits.max_attempts:
            reason = WAIT_BUDGET_EXHAUSTED
        elif problems and problems[-1].code == FALLBACK_CHANGES_INTENT:
            reason = FALLBACK_CHANGES_INTENT
        else:
            reason = WAIT_PROVIDERS_EXHAUSTED
        return ProviderCallOutcome(
            status=ProviderCallStatus.WAITING, output=None, output_revision=None, wait_reason=reason, **shared)

    def _attempt(
        self,
        call: ProviderRouteDecision,
        *,
        ai_role: str,
        envelope: PromptEnvelope,
        config_revision: str,
        validator: Callable[[AIInvocationResult], object],
        attempt: int,
        invoked: tuple[str, ...],
        secrets: tuple[str, ...],
    ) -> tuple[AIInvocationRecord, Any, ProviderProblem | None, Exception | None]:
        """One provider call: the stamped record, the validated output, the problem and the defect; exactly one of validated output, problem and defect describes the outcome."""
        provider_ref = call.provider_ref
        stamp = {'attempt': attempt, 'fallback_path': invoked}
        try:
            result = self._ai.invoke(call, envelope)
        except OSError as error:
            code = PROVIDER_TIMEOUT if isinstance(error, TimeoutError) else PROVIDER_UNREACHABLE
            text = redact_error(f'{code}: {type(error).__name__}: {error}', secrets)
            record = AIInvocationRecord(
                ai_role=ai_role, provider_ref=provider_ref, model_ref=call.model_ref, account_ref=call.account_ref,
                project_ref=call.project_ref, route_revision=call.route_revision,
                prompt_revision=envelope.prompt_ref.revision_id, config_revision=config_revision,
                input_fingerprint=fingerprint_envelope(envelope), usage=InvocationUsage(0, 0, call.estimated_cost_class),
                latency_ms=0, validation_result='not_run', error=text, **stamp)
            return record, None, _problem(code, text, provider_ref, attempt, secrets), None
        record = result.record
        if record.error is not None:
            text = redact_error(record.error, secrets)
            stamped = dataclasses.replace(record, error=text, validation_result='not_run', **stamp)
            waiting = getattr(result, 'retryable', False) is True and isinstance(getattr(result, 'wait_reason', None), str)
            problem = _problem(
                classify_provider_error(text), text, provider_ref, attempt, secrets, wait_code=provider_wait_code(text) if waiting else '')
            return stamped, None, problem, None
        try:
            validated = validator(result)
        except Exception as rejected:
            stamped = dataclasses.replace(record, validation_result='failed', **stamp)
            code, reason = getattr(rejected, 'code', None), getattr(rejected, 'reason', None)
            if not isinstance(code, str) or not isinstance(reason, str) or _input_determined(code):
                return stamped, None, None, rejected
            field = getattr(rejected, 'field', '')
            return stamped, None, _problem(code, reason, provider_ref, attempt, secrets, field if isinstance(field, str) else ''), None
        return dataclasses.replace(record, validation_result='passed', **stamp), validated, None, None


__all__ = [
    'FALLBACK_CHANGES_INTENT', 'INTENT_MODES', 'INTENT_NEW_REVISION', 'INTENT_WAIT', 'PROVIDER_ERROR',
    'PROVIDER_RATE_LIMITED', 'PROVIDER_TIMEOUT', 'PROVIDER_UNREACHABLE', 'ProviderCallOutcome', 'ProviderCallStatus',
    'ProviderFailureHandler', 'ProviderFailurePolicy', 'ProviderProblem', 'WAIT_BUDGET_EXHAUSTED',
    'WAIT_PROVIDERS_EXHAUSTED', 'WAIT_PROVIDER_UNAVAILABLE', 'WAIT_QUOTA', 'classify_provider_error', 'parse_failure_policy',
    'plan_fallback_path', 'provider_wait_code',
]
