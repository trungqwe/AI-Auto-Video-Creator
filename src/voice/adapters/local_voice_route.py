"""Real VoiceRoutePort for local Kokoro only (PW-E2, CT-AI-ROUTE-001). The decision always names the local provider with no fallback, no credential and no network path; the constructor takes no provider argument."""
from __future__ import annotations

from collections.abc import Mapping

from voice.domain.tts_invocation import ProviderRouteDecision, RouteContractViolation, validate_provider_route_request

LOCAL_PROVIDER_REF = 'kokoro-local'
LOCAL_MODEL_REF = 'kokoro-v1.0'
LOCAL_ACCOUNT_REF = 'local'
DEFAULT_ROUTE_REVISION = 'kokoro-local-1'


class LocalVoiceRoute:
    def __init__(self, *, route_revision: str = DEFAULT_ROUTE_REVISION) -> None:
        if not isinstance(route_revision, str) or not route_revision:
            raise ValueError('route_revision must be a non-empty string')
        self._route_revision = route_revision

    def resolve(self, request: Mapping[str, object]) -> ProviderRouteDecision:
        issues = validate_provider_route_request(request)
        if issues:
            raise RouteContractViolation('ProviderRouteRequest', issues)
        return ProviderRouteDecision(
            provider_ref=LOCAL_PROVIDER_REF,
            model_ref=LOCAL_MODEL_REF,
            account_ref=LOCAL_ACCOUNT_REF,
            route_revision=self._route_revision,
            rationale_codes=('LOCAL_ONLY',),
            fallback_order=(),
            capacity_reservation_ref='local-' + str(request['job_ref']),
            credential_acquisition_method='none',
            estimated_cost_class='free',
        )


__all__ = ('LocalVoiceRoute',)
