import unittest
from src.controlplane.security.interfaces import SecretCredential
from src.controlplane.security.sanitizer import sanitize_for_log
from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
    RateLimitError
)
from src.controlplane.config.router import ProviderRouter

class MockPrimaryProvider:
    def __init__(self, fail_with_429: bool = False):
        self.fail_with_429 = fail_with_429

    def call(self, request: AIRequest):
        if self.fail_with_429:
            raise RateLimitError(429, "Primary rate limit reached")
        return {"status": "ok", "provider": "primary"}

class MockFallbackProvider:
    def call(self, request: AIRequest):
        return {"status": "ok", "provider": "secondary"}

class TestProviderRouting(unittest.TestCase):

    def test_secret_credential_never_exposes_raw_value_in_string_or_log(self):
        """Oracle 1 (INV-015 / CT-SEC-001): Secret phải được che giấu trong str, repr và sanitizer."""
        raw_token = "SECRET_ORACLE_KEY_9999_EXPLICIT"
        cred = SecretCredential(alias="gemini_key", raw_secret=raw_token)
        
        masked_str = sanitize_for_log(cred)
        str_repr = str(cred)
        obj_repr = repr(cred)
        
        # Ở pha RED: scaffold trả về raw_secret nên fail ngay tại assert đầu tiên
        self.assertNotIn(raw_token, masked_str)
        self.assertIn("[REDACTED]", masked_str)
        self.assertNotIn(raw_token, str_repr)
        self.assertNotIn(raw_token, obj_repr)

    def test_provider_router_automatically_fallbacks_on_http_429(self):
        """Oracle 2 (INV-013 / CT-AI-ROUTE-001): Tự động fallback sang secondary khi gặp HTTP 429."""
        router = ProviderRouter(
            primary=MockPrimaryProvider(fail_with_429=True),
            fallback=MockFallbackProvider()
        )
        req = AIRequest(prompt="generate video hook", config_revision_id="rev-20261002-001")
        
        # Ở pha RED: Router gọi thẳng primary và không bắt RateLimitError -> Ném RateLimitError
        try:
            resp = router.dispatch(req)
        except RateLimitError as e:
            self.fail(f"Router failed to catch 429 and fallback; propagated error: {e}")
            
        self.assertEqual(resp.payload.get("provider"), "secondary")
        self.assertTrue(resp.fallback_triggered)

    def test_ai_dispatch_rejects_request_without_config_provenance(self):
        """Oracle 3 (INV-021 / CT-CFG-001): Từ chối fail-closed nếu thiếu config_revision_id."""
        router = ProviderRouter(primary=MockPrimaryProvider(fail_with_429=False))
        invalid_req = AIRequest(prompt="generate video hook", config_revision_id=None)
        
        # Ở pha RED: Router không kiểm tra provenance -> không raise MissingConfigProvenanceError
        with self.assertRaises(MissingConfigProvenanceError):
            router.dispatch(invalid_req)

if __name__ == "__main__":
    unittest.main()
