from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
    RateLimitError
)
from src.controlplane.security.interfaces import ProviderProtocol

class ProviderRouter:
    def __init__(self, primary: ProviderProtocol, fallback: ProviderProtocol | None = None):
        self.primary = primary
        self.fallback = fallback

    def dispatch(self, req: AIRequest) -> AIResponse:
        # Invariant 3 (INV-021 / CT-CFG-001): Fail-closed nếu thiếu provenance config_revision_id
        if not req.config_revision_id:
            raise MissingConfigProvenanceError(
                "AI request rejected: missing required config_revision_id provenance"
            )

        # Invariant 2 (INV-013 / CT-AI-ROUTE-001): Tự động fallback khi gặp HTTP 429 RateLimitError
        try:
            raw_res = self.primary.call(req)
            return AIResponse(payload=raw_res, fallback_triggered=False)
        except RateLimitError:
            if self.fallback is not None:
                fallback_res = self.fallback.call(req)
                return AIResponse(payload=fallback_res, fallback_triggered=True)
            raise
