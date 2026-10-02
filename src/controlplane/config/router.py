from __future__ import annotations

from typing import Optional, Dict, Any
from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
    RateLimitError,
)
from src.controlplane.security.interfaces import ProviderProtocol
from src.controlplane.config.adapter import (
    ApprovedEndpointRegistry,
    DEFAULT_ENDPOINT_REGISTRY,
    DEFAULT_APPROVED_ENDPOINTS,
    UnapprovedEndpointError,
    InvalidEndpointError,
    ProviderRateLimitExceededError,
)


class ProviderRouter:
    """Coordinates resilient AI provider dispatch and fallback with immutable endpoint registry enforcement.

    Enforces:
    - INV-013: Fail-closed fallback on rate limits and endpoint authority validation against ApprovedEndpointRegistry.
    - INV-021: Strict config revision provenance verification.
    """

    def __init__(
        self,
        primary: ProviderProtocol,
        fallback: ProviderProtocol | None = None,
        registry: Optional[ApprovedEndpointRegistry] = None,
    ):
        if registry is not None and registry is not DEFAULT_ENDPOINT_REGISTRY:
            raise UnapprovedEndpointError(
                "Caller-supplied registry is rejected: authority is strictly host/configuration-owned (INV-013)"
            )
        self._registry = DEFAULT_ENDPOINT_REGISTRY
        self._primary = primary
        self._fallback = fallback
        self._primary_endpoint = self._validate_and_bind_provider_authority(self._primary)
        self._fallback_endpoint = (
            self._validate_and_bind_provider_authority(self._fallback)
            if self._fallback is not None
            else None
        )

    @property
    def registry(self) -> ApprovedEndpointRegistry:
        return self._registry

    @property
    def primary(self) -> ProviderProtocol:
        return self._primary

    @property
    def fallback(self) -> ProviderProtocol | None:
        return self._fallback

    def _validate_and_bind_provider_authority(self, provider: ProviderProtocol) -> str | None:
        """Enforces INV-013 / CT-SEC-001: Validates and binds provider endpoint against registry (fail-closed)."""
        if provider is None:
            raise UnapprovedEndpointError("Provider instance cannot be None (fail-closed)")
        raw_endpoint = getattr(provider, "base_url", None) or getattr(provider, "endpoint", None)
        if raw_endpoint is None:
            return None
        endpoint = raw_endpoint() if callable(raw_endpoint) else raw_endpoint
        if not endpoint or not isinstance(endpoint, str) or not endpoint.strip():
            raise UnapprovedEndpointError(
                f"Provider {provider!r} missing approved endpoint metadata (fail-closed)"
            )
        return self._registry.validate(endpoint)

    def _validate_provider_authority(self, provider: ProviderProtocol) -> None:
        """Enforces INV-013 / CT-SEC-001: Validates that provider endpoint is approved in registry (fail-closed)."""
        self._validate_and_bind_provider_authority(provider)

    @property
    def approved_endpoints(self) -> frozenset[str]:
        return self._registry.endpoints

    def is_endpoint_approved(self, endpoint: str) -> bool:
        return self._registry.is_approved(endpoint)

    def dispatch(self, req: AIRequest) -> AIResponse:
        # Invariant 3 (INV-021 / CT-CFG-001): Fail-closed nếu thiếu provenance config_revision_id
        if not req.config_revision_id or not req.config_revision_id.strip():
            raise MissingConfigProvenanceError(
                "AI request rejected: missing required config_revision_id provenance"
            )

        # Invariant 1 (INV-013 / CT-SEC-001): Re-validate provider authority and detect endpoint drift prior to dispatch
        current_primary_endpoint = self._validate_and_bind_provider_authority(self._primary)
        if current_primary_endpoint != self._primary_endpoint:
            raise UnapprovedEndpointError("Endpoint drift detected on primary provider (fail-closed)")

        # Invariant 2 (INV-013 / CT-AI-ROUTE-001): Tự động fallback khi gặp HTTP 429 RateLimitError
        try:
            raw_res = self._primary.call(req)
            return AIResponse(payload=raw_res, fallback_triggered=False)
        except (RateLimitError, ProviderRateLimitExceededError):
            if self._fallback is not None:
                current_fallback_endpoint = self._validate_and_bind_provider_authority(self._fallback)
                if current_fallback_endpoint != self._fallback_endpoint:
                    raise UnapprovedEndpointError("Endpoint drift detected on fallback provider (fail-closed)")
                fallback_res = self._fallback.call(req)
                return AIResponse(payload=fallback_res, fallback_triggered=True)
            raise


__all__ = [
    "ProviderRouter",
    "ApprovedEndpointRegistry",
    "DEFAULT_ENDPOINT_REGISTRY",
    "DEFAULT_APPROVED_ENDPOINTS",
    "UnapprovedEndpointError",
    "InvalidEndpointError",
]
