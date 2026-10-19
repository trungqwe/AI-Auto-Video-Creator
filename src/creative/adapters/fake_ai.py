"""In-memory fakes of the AI route and invocation ports (CT-AI-ROUTE-001, CT-AI-010).

Responses are scripted per ai_role and calls are counted. The module imports no network, process or file API,
so a fake can never open a connection; D never sees a secret, only the route decision.
"""
from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping

from creative.domain.invocation import (
    AIInvocationRecord,
    AIInvocationResult,
    InvocationUsage,
    ProviderRouteDecision,
    RouteContractViolation,
    fingerprint_envelope,
    fingerprint_output,
    redact_error,
    validate_provider_route_request,
)
from creative.domain.untrusted import PromptEnvelope, read_model_output


class NoScriptedResponse(LookupError):
    """The fake has neither a scripted response nor a scripted error for this ai_role."""


class UnknownReservation(LookupError):
    """The decision's capacity reservation was not issued by this FakeProviderRoute."""


class FakeProviderRoute:
    """ProviderRoutePort fake: validates the request, returns a deterministic decision and remembers the ai_role of each reservation."""

    def __init__(
        self,
        *,
        route_revision: str = 'fake-route-v1',
        provider_ref: str = 'fake-provider',
        model_ref: str = 'fake-model',
        account_ref: str = 'fake-account',
        project_ref: str | None = None,
        estimated_cost_class: str = 'free',
    ) -> None:
        self._fields = {
            'provider_ref': provider_ref,
            'model_ref': model_ref,
            'account_ref': account_ref,
            'route_revision': route_revision,
            'estimated_cost_class': estimated_cost_class,
            'project_ref': project_ref,
        }
        self.resolve_calls = 0
        self._reservations: dict[str, str] = {}

    def resolve(self, request: Mapping[str, object]) -> ProviderRouteDecision:
        self.resolve_calls += 1
        issues = validate_provider_route_request(request)
        if issues:
            raise RouteContractViolation('ProviderRouteRequest', issues)
        reservation_ref = f'fake-reservation-{id(self)}-{self.resolve_calls}'
        decision = ProviderRouteDecision(
            **self._fields,
            rationale_codes=('FAKE_ROUTE',),
            fallback_order=tuple(request['allowed_fallbacks']),
            capacity_reservation_ref=reservation_ref,
            credential_acquisition_method='secret_broker_handle',
        )
        self._reservations[reservation_ref] = request['ai_role']
        return decision

    def role_for_reservation(self, reservation_ref: str) -> str:
        try:
            return self._reservations[reservation_ref]
        except KeyError:
            raise UnknownReservation(reservation_ref) from None


class FakeAIAdapter:
    """AIInvocationPort fake: answers with the response scripted for the reservation's ai_role, counts calls and never touches the network."""

    def __init__(
        self,
        route: FakeProviderRoute,
        *,
        responses: Mapping[str, Mapping[str, object]],
        config_revision: str,
        errors: Mapping[str, str] | None = None,
        known_secrets: Iterable[str] = (),
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        attempt: int = 1,
    ) -> None:
        if not isinstance(route, FakeProviderRoute):
            raise TypeError('route must be a FakeProviderRoute')
        if not isinstance(config_revision, str) or not config_revision:
            raise ValueError('config_revision must be a non-empty string')
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must be an iterable of str, not a single str')
        self._route = route
        self._responses = copy.deepcopy(dict(responses))
        self._errors = dict(errors or {})
        self._known_secrets = tuple(known_secrets)
        self._config_revision = config_revision
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._latency_ms = latency_ms
        self._attempt = attempt
        self.invoke_calls = 0
        self.calls_by_role: dict[str, int] = {}
        self.records: list[AIInvocationRecord] = []

    def invoke(self, decision: ProviderRouteDecision, envelope: PromptEnvelope) -> AIInvocationResult:
        if not isinstance(decision, ProviderRouteDecision):
            raise TypeError('decision must be a ProviderRouteDecision')
        if not isinstance(envelope, PromptEnvelope):
            raise TypeError('envelope must be a PromptEnvelope')
        self.invoke_calls += 1
        role = self._route.role_for_reservation(decision.capacity_reservation_ref)
        self.calls_by_role[role] = self.calls_by_role.get(role, 0) + 1
        if role not in self._errors and role not in self._responses:
            raise NoScriptedResponse(role)
        fields = {
            'ai_role': role,
            'provider_ref': decision.provider_ref,
            'model_ref': decision.model_ref,
            'account_ref': decision.account_ref,
            'project_ref': decision.project_ref,
            'route_revision': decision.route_revision,
            'prompt_revision': envelope.prompt_ref.revision_id,
            'config_revision': self._config_revision,
            'input_fingerprint': fingerprint_envelope(envelope),
            'usage': InvocationUsage(self._input_tokens, self._output_tokens, decision.estimated_cost_class),
            'latency_ms': self._latency_ms,
            'attempt': self._attempt,
            'fallback_path': (decision.provider_ref,),
            'validation_result': 'not_run',
        }
        if role in self._errors:
            output = None
            outcome = {'error': redact_error(self._errors[role], self._known_secrets)}
        else:
            output = read_model_output(self._responses[role])
            outcome = {'output_fingerprint': fingerprint_output(output)}
        record = AIInvocationRecord(**fields, **outcome)
        self.records.append(record)
        return AIInvocationResult(record=record, output=output)
