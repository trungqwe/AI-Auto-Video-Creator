"""Targeted behavioral tests for 9Router HTTP Client Adapter (INV-013 / INV-021 / QR-REL-007).

Task: TASK-CAP-J-P1-B
"""
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
)
from controlplane.config.adapter import (
    ApprovedEndpointRegistry,
    ChatAIRequest,
    NineRouterHTTPAdapter,
    ProviderTimeoutError,
    ProviderRateLimitExceededError,
    UnapprovedEndpointError,
)


class _RecordingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length)
        self.server.hits.append({
            'path': self.path,
            'body': json.loads(raw.decode('utf-8')),
            'headers': {k.lower(): v for k, v in self.headers.items()},
        })
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        body = json.dumps({'choices': [{'message': {'content': 'hi'}}]}).encode('utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _start_router():
    server = ThreadingHTTPServer(('127.0.0.1', 0), _RecordingHandler)
    server.daemon_threads = True
    server.hits = []
    port = server.server_address[1]
    server.origin = 'http://127.0.0.1:' + str(port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


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
            url="http://mock-9router:8000/v1/chat/completions",
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

    def test_http_adapter_posts_chat_completions_for_origin_and_v1_endpoint(self):
        server = _start_router()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        for suffix in ('', '/v1'):
            endpoint = server.origin + suffix
            registry = ApprovedEndpointRegistry.from_config([endpoint])
            adapter = NineRouterHTTPAdapter(base_url=endpoint, registry=registry, max_retries=0)
            request = ChatAIRequest(prompt='xin chao', config_revision_id='rev-r15', model='model-r15')
            res = adapter.send_request(request, secret_token='tok-r15')
            self.assertEqual(res.payload['choices'][0]['message']['content'], 'hi')
            hit = server.hits[-1]
            self.assertEqual(hit['path'], '/v1/chat/completions')
            self.assertEqual(hit['body'], {'model': 'model-r15', 'messages': [{'role': 'user', 'content': 'xin chao'}]})
            self.assertEqual(hit['headers']['x-config-revision-id'], 'rev-r15')
            self.assertEqual(hit['headers']['x-route-provenance'], '9router-adapter')
            self.assertEqual(hit['headers']['authorization'], 'Bearer tok-r15')
        self.assertEqual(len(server.hits), 2)

    def test_http_adapter_endpoint_registry_and_drift_checks_still_apply_with_v1_suffix(self):
        registry = ApprovedEndpointRegistry.from_config(['http://127.0.0.1:20128/v1'])
        adapter = NineRouterHTTPAdapter(base_url='http://127.0.0.1:20128/v1', registry=registry)
        self.assertEqual(adapter.bound_endpoint, 'http://127.0.0.1:20128/v1')
        with self.assertRaises(UnapprovedEndpointError):
            NineRouterHTTPAdapter(base_url='http://127.0.0.1:20129/v1', registry=registry)


if __name__ == "__main__":
    unittest.main()
