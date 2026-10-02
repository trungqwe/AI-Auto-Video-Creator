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
    """Coordinates resilient AI provider dispatch and fallback with endpoint registry enforcement.

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
        self.registry = registry if registry is not None else DEFAULT_ENDPOINT_REGISTRY
        self.primary = primary
        self.fallback = fallback
        self._validate_provider_authority(self.primary)
        if self.fallback is not None:
            self._validate_provider_authority(self.fallback)

    def _validate_provider_authority(self, provider: ProviderProtocol) -> None:
        """Enforces INV-013 / CT-SEC-001: Validates that provider endpoint is approved in registry (fail-closed)."""
        endpoint = getattr(provider, "base_url", None) or getattr(provider, "endpoint", None)
        if endpoint is not None:
            self.registry.validate(endpoint)

    @property
    def approved_endpoints(self) -> frozenset[str]:
        return self.registry.endpoints

    def is_endpoint_approved(self, endpoint: str) -> bool:
        return self.registry.is_approved(endpoint)

    def dispatch(self, req: AIRequest) -> AIResponse:
        # Invariant 3 (INV-021 / CT-CFG-001): Fail-closed nếu thiếu provenance config_revision_id
        if not req.config_revision_id or not req.config_revision_id.strip():
            raise MissingConfigProvenanceError(
                "AI request rejected: missing required config_revision_id provenance"
            )

        # Re-validate provider authority prior to dispatch (fail-closed)
        self._validate_provider_authority(self.primary)

        # Invariant 2 (INV-013 / CT-AI-ROUTE-001): Tự động fallback khi gặp HTTP 429 RateLimitError
        try:
            raw_res = self.primary.call(req)
            return AIResponse(payload=raw_res, fallback_triggered=False)
        except (RateLimitError, ProviderRateLimitExceededError):
            if self.fallback is not None:
                self._validate_provider_authority(self.fallback)
                fallback_res = self.fallback.call(req)
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