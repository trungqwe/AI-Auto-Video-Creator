"""AI routing and invocation ports (CT-AI-ROUTE-001, CT-AI-010).

D never receives a secret: J resolves the route and capacity, D only gets a ProviderRouteDecision (refs, never credentials).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from creative.domain.invocation import AIInvocationResult, ProviderRouteDecision
from creative.domain.untrusted import PromptEnvelope


@runtime_checkable
class ProviderRoutePort(Protocol):
    """Resolve a ProviderRouteRequest payload (binding j-provider-route) into a decision; raises RouteContractViolation on a request that breaks the binding."""

    def resolve(self, request: Mapping[str, object]) -> ProviderRouteDecision: ...


@runtime_checkable
class AIInvocationPort(Protocol):
    """Invoke the routed model with an instruction/data envelope; the result always carries a redacted AIInvocationRecord and never a secret."""

    def invoke(self, decision: ProviderRouteDecision, envelope: PromptEnvelope) -> AIInvocationResult: ...
