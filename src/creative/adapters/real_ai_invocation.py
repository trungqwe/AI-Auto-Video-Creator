"""AIInvocationPort of D over RoutedInvocationService (ADAPT-D, J-18, CT-AI-ROUTE-002, CT-COST-001, CT-AI-010).

D never receives a secret and never resolves a route: RoutedInvocationService resolves the route, checks the budget, executes, falls back and records cost through CostLedgerPort.
This module only translates the InvocationRecord into an AIInvocationResult whose record is redacted. BUDGET_BLOCKED, and WAITING_PROVIDER caused by a rate limit or timeout, are retryable waiting results, never a final error.
GIẢ ĐỊNH (D8): request_for maps the capacity_reservation_ref of the decision to the ProviderRouteRequest that produced it (ADAPT-WIRE supplies it); the prompt reaches the executor by payload ref, so the request given to J-18 carries that ref as snapshot_ref.
"""
from __future__ import annotations

import dataclasses
import itertools
import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation

from controlplane.application.config_security.fallback_policy import RATE_LIMIT, TIMEOUT, FallbackIntentPolicy
from controlplane.application.config_security.routed_invocation import (
    BUDGET_BLOCKED,
    SUCCEEDED,
    WAITING_PROVIDER,
    InvocationRecord,
    RoutedInvocationService,
)
from controlplane.domain.config_security.incremental_cost import BudgetPolicy
from controlplane.domain.config_security.route_binding import ProviderRouteRequest
from creative.adapters.real_route_executor import InvocationPayloadStore
from creative.domain.invocation import (
    AIInvocationRecord,
    AIInvocationResult,
    InvocationUsage,
    ProviderRouteDecision,
    fingerprint_envelope,
    fingerprint_output,
    redact_error,
)
from creative.domain.untrusted import PromptEnvelope, read_model_output

_RETRYABLE_FAILURES = frozenset({RATE_LIMIT, TIMEOUT})


def budget_policy_from_config(config: Mapping[str, object]) -> BudgetPolicy:
    """Build the BudgetPolicy from configuration; monthly_limit and hard_stop have no defaults and are never hard-coded."""
    for name in ('monthly_limit', 'hard_stop'):
        if name not in config:
            raise ValueError(f'missing budget config key: {name}')
    hard_stop = config['hard_stop']
    if not isinstance(hard_stop, bool):
        raise ValueError('hard_stop must be a bool')
    raw = config['monthly_limit']
    if isinstance(raw, bool) or not isinstance(raw, (int, str, Decimal)):
        raise ValueError('monthly_limit must be an int, a str or a Decimal')
    try:
        limit = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError('monthly_limit must be a decimal number') from exc
    extra: dict[str, object] = {}
    if 'warn_ratio' in config:
        extra['warn_ratio'] = Decimal(str(config['warn_ratio']))
    if 'currency' in config:
        extra['currency'] = config['currency']
    return BudgetPolicy(monthly_limit=limit, hard_stop=hard_stop, **extra)


@dataclasses.dataclass(frozen=True)
class WaitingAIInvocationResult(AIInvocationResult):
    """A retryable waiting result: the record carries the redacted reason and no output; the job waits and tries again when the quota or budget recovers."""

    wait_reason: str
    retryable: bool = True


def _prompt_text(envelope: PromptEnvelope) -> str:
    """Instructions and untrusted data stay in separate JSON members; data is never merged into the instructions."""
    return json.dumps(
        {'instructions': envelope.instructions, 'data': [item.text for item in envelope.data]},
        ensure_ascii=False,
        sort_keys=True,
    )


def _model_mapping(payload: Mapping[str, object]) -> dict[str, object]:
    text = payload.get('text')
    if not isinstance(text, str):
        text = ''
        choices = payload.get('choices')
        if isinstance(choices, (list, tuple)) and choices and isinstance(choices[0], Mapping):
            first = choices[0]
            message = first.get('message')
            candidate = message.get('content') if isinstance(message, Mapping) else first.get('text')
            if isinstance(candidate, str):
                text = candidate
    return {'text': text, 'refs': payload.get('refs')}


def _token_counts(payload: Mapping[str, object]) -> tuple[int, int]:
    usage = payload.get('usage')
    counts: list[int] = []
    for name in ('prompt_tokens', 'completion_tokens'):
        value = usage.get(name) if isinstance(usage, Mapping) else None
        counts.append(value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0)
    return counts[0], counts[1]


def _classify_outcome(outcome: InvocationRecord) -> tuple[str, bool]:
    """Return (error code, retryable). Waiting: BUDGET_BLOCKED, or WAITING_PROVIDER with no attempt (no route yet) or a last attempt that was RATE_LIMIT or TIMEOUT.

    A WAITING_PROVIDER after an AUTH or UNKNOWN failure is a final provider_failed, so a bad credential never waits forever.
    """
    if outcome.outcome == BUDGET_BLOCKED:
        return 'budget_blocked', True
    if outcome.outcome == WAITING_PROVIDER:
        last = outcome.attempts[-1].outcome if outcome.attempts else None
        if last is None or last in _RETRYABLE_FAILURES:
            return 'waiting_provider', True
        return 'provider_failed', False
    return outcome.outcome.casefold(), False

class RoutedAIInvocation:
    """AIInvocationPort over RoutedInvocationService: J resolves, checks the budget, executes, falls back and records cost; D only translates the outcome."""

    def __init__(
        self,
        service: RoutedInvocationService,
        store: InvocationPayloadStore,
        *,
        request_for: Callable[[str], ProviderRouteRequest],
        clock: Callable[[], datetime],
        config_revision: str,
        intent_policy: FallbackIntentPolicy,
        units: int,
        ttl_seconds: int,
        desktop_online: Callable[[], bool],
        local_candidate_refs: frozenset[str] = frozenset(),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(service, RoutedInvocationService):
            raise TypeError('service must be a RoutedInvocationService')
        if not isinstance(store, InvocationPayloadStore):
            raise TypeError('store must be an InvocationPayloadStore')
        if not isinstance(config_revision, str) or not config_revision.strip():
            raise ValueError('config_revision must be a non-empty string')
        for name, value in (('request_for', request_for), ('clock', clock), ('desktop_online', desktop_online), ('monotonic', monotonic)):
            if not callable(value):
                raise TypeError(f'{name} must be callable')
        self._service = service
        self._store = store
        self._request_for = request_for
        self._clock = clock
        self._config_revision = config_revision
        self._intent_policy = intent_policy
        self._units = units
        self._ttl_seconds = ttl_seconds
        self._desktop_online = desktop_online
        self._local_candidate_refs = frozenset(local_candidate_refs)
        self._monotonic = monotonic
        self._sequence = itertools.count(1)

    def invoke(self, decision: ProviderRouteDecision, envelope: PromptEnvelope) -> AIInvocationResult:
        if not isinstance(decision, ProviderRouteDecision):
            raise TypeError('decision must be a ProviderRouteDecision')
        if not isinstance(envelope, PromptEnvelope):
            raise TypeError('envelope must be a PromptEnvelope')
        request = self._request_for(decision.capacity_reservation_ref)
        if not isinstance(request, ProviderRouteRequest):
            raise TypeError('request_for must return a ProviderRouteRequest')
        payload_ref = f'adapt-d-payload-{next(self._sequence)}'
        self._store.put_request(payload_ref, _prompt_text(envelope))
        started = self._monotonic()
        try:
            outcome = self._service.invoke(
                dataclasses.replace(request, snapshot_ref=payload_ref),
                envelope.prompt_ref.workspace_id,
                self._clock(),
                self._units,
                self._ttl_seconds,
                self._desktop_online(),
                self._intent_policy,
                True,
                self._config_revision,
                envelope.prompt_ref.revision_id,
                self._local_candidate_refs,
            )
        finally:
            self._store.drop_request(payload_ref)
        latency_ms = max(0, int((self._monotonic() - started) * 1000))
        return self._to_result(outcome, request, decision, fingerprint_envelope(envelope), latency_ms)

    def _to_result(
        self,
        outcome: InvocationRecord,
        request: ProviderRouteRequest,
        decision: ProviderRouteDecision,
        fingerprint: str,
        latency_ms: int,
    ) -> AIInvocationResult:
        source = outcome.route_decision if outcome.route_decision is not None else decision
        attempts = outcome.attempts
        fields = {
            'ai_role': request.ai_role,
            'provider_ref': source.provider_ref,
            'model_ref': source.model_ref,
            'account_ref': source.account_ref,
            'project_ref': source.project_ref,
            'route_revision': source.route_revision,
            'prompt_revision': outcome.prompt_revision_id,
            'config_revision': outcome.config_revision_id,
            'input_fingerprint': fingerprint,
            'latency_ms': latency_ms,
            'attempt': max(1, len(attempts)),
            'fallback_path': tuple(item.candidate_ref for item in attempts) or (source.provider_ref,),
            'validation_result': 'not_run',
        }
        if outcome.outcome == SUCCEEDED:
            payload = self._store.pop_output(outcome.output_ref)
            output = read_model_output(_model_mapping(payload))
            tokens_in, tokens_out = _token_counts(payload)
            usage = InvocationUsage(tokens_in, tokens_out, source.estimated_cost_class)
            record = AIInvocationRecord(**fields, usage=usage, output_fingerprint=fingerprint_output(output))
            return AIInvocationResult(record=record, output=output)
        code, retryable = _classify_outcome(outcome)
        detail = attempts[-1].error if attempts and attempts[-1].error else outcome.outcome
        usage = InvocationUsage(0, 0, source.estimated_cost_class)
        record = AIInvocationRecord(**fields, usage=usage, error=redact_error(f'{code}: {detail}'))
        if retryable:
            return WaitingAIInvocationResult(record=record, output=None, wait_reason=outcome.outcome)
        return AIInvocationResult(record=record, output=None)


__all__ = ['RoutedAIInvocation', 'WaitingAIInvocationResult', 'budget_policy_from_config']
