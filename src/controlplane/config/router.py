from src.controlplane.config.models import AIRequest, AIResponse
from src.controlplane.security.interfaces import ProviderProtocol

class ProviderRouter:
    def __init__(self, primary: ProviderProtocol, fallback: ProviderProtocol | None = None):
        self.primary = primary
        self.fallback = fallback

    def dispatch(self, req: AIRequest) -> AIResponse:
        # Scaffold RED: Gọi thẳng primary, KHÔNG kiểm tra provenance, KHÔNG có try/except fallback
        raw_res = self.primary.call(req)
        return AIResponse(payload=raw_res, fallback_triggered=False)
