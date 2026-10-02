"""Targeted behavioral tests for 9Router HTTP Client Adapter (INV-013 / INV-021 / QR-REL-007).

Task: TASK-CAP-J-P1-B
"""
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io
import json
import socket

from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
)
from src.controlplane.config.adapter import (
    NineRouterHTTPAdapter,
    ProviderTimeoutError,
    ProviderRateLimitExceededError,
)


class MockHTTPResponse:
    def __init__(self, status: int = 200, body: bytes = b"{}", headers: dict | None = None):
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestHTTPRouterAdapter(unittest.TestCase):

    def test_http_adapter_timeout_handling(self):
        """Oracle 1 (INV-021): HTTP client intercepts socket/request timeout and raises ProviderTimeoutError."""
        adapter = NineRouterHTTPAdapter(base_url="http://mock-9router:8000", timeout=1.0)
        req = AIRequest(prompt="Test timeout", config_revision_id="rev-test-001")

        with patch("urllib.request.urlopen", side_effect=socket.timeout("Request timed out")):
            with self.assertRaises(ProviderTimeoutError):
                adapter.send_request(req)

    def test_http_adapter_429_exponential_backoff_and_retry(self):
        """Oracle 2 (INV-021): HTTP client handles HTTP 429 with retry/backoff and raises when exhausted.

        - Case A: 429 then succeeds on 2nd retry -> returns AIResponse with fallback/retry metadata.
        - Case B: 429 on all attempts -> raises ProviderRateLimitExceededError.
        """
        adapter = NineRouterHTTPAdapter(base_url="http://mock-9router:8000", max_retries=2, backoff_factor=0.01)
        req = AIRequest(prompt="Test 429", config_revision_id="rev-test-002")

        # Mock 429 error
        error_429 = urllib.error.HTTPError(
            url="http://mock-9router:8000/v1/chat",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": "rate_limited"}')
        )
        success_200 = MockHTTPResponse(status=200, body=b'{"choices": [{"text": "success"}]}')

        # Case A: Retry succeeds
        with patch("urllib.request.urlopen", side_effect=[error_429, success_200]):
            res = adapter.send_request(req)
            self.assertIsNotNone(res.payload)
            self.assertIn("choices", res.payload)

        # Case B: Exhausted retries -> raises ProviderRateLimitExceededError
        with patch("urllib.request.urlopen", side_effect=[error_429, error_429, error_429]):
            with self.assertRaises(ProviderRateLimitExceededError):
                adapter.send_request(req)

    def test_http_adapter_route_provenance_stamping(self):
        """Oracle 3 (INV-013): Outbound HTTP request stamps provenance headers and rejects missing revision."""
        adapter = NineRouterHTTPAdapter(base_url="http://mock-9router:8000")

        # Missing config_revision_id must fail-closed
        bad_req = AIRequest(prompt="No provenance", config_revision_id="")
        with self.assertRaises(MissingConfigProvenanceError):
            adapter.send_request(bad_req)

        # Valid request must stamp headers
        good_req = AIRequest(prompt="Valid req", config_revision_id="rev-prod-999")
        success_200 = MockHTTPResponse(status=200, body=b'{"result": "ok"}')

        with patch("urllib.request.urlopen", return_value=success_200) as mock_urlopen:
            res = adapter.send_request(good_req, secret_token="test_token_123")
            self.assertEqual(res.payload, {"result": "ok"})
            self.assertTrue(mock_urlopen.called)
            # Inspect outbound Request object
            outbound_req = mock_urlopen.call_args[0][0]
            headers = {k.lower(): v for k, v in outbound_req.headers.items()}
            self.assertEqual(headers.get("x-config-revision-id"), "rev-prod-999")
            self.assertIn("x-route-provenance", headers)


if __name__ == "__main__":
    unittest.main()
