"""HTTP Client Adapter for 9Router and Provider Routing (INV-013 / INV-021 / QR-REL-007).

Scaffold for TASK-CAP-J-P1-B.
"""
from __future__ import annotations

import io
import json
import socket
import time
from typing import Dict, Any, Optional, Iterable, Set
import urllib.error
from urllib.parse import urlparse
import urllib.request

from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
    RateLimitError,
)


class ProviderHTTPError(Exception):
    """Base exception for provider HTTP adapter errors."""
    pass


class ProviderSecurityError(ProviderHTTPError):
    """Base exception for provider security policy violations."""
    pass


class UnapprovedEndpointError(ProviderSecurityError):
    """Raised when an unapproved or untrusted endpoint is provided (INV-013 / CT-SEC-001 fail-closed)."""
    pass

InvalidEndpointError = UnapprovedEndpointError


class ProviderTimeoutError(ProviderHTTPError):
    """Raised when an outbound provider HTTP request times out (INV-021)."""
    pass


class ProviderRateLimitExceededError(ProviderHTTPError, RateLimitError):
    """Raised when provider returns HTTP 429 and retries are exhausted (INV-021)."""
    def __init__(self, message: str = "Rate limit exceeded after retries", code: int = 429):
        super().__init__(message)
        self.code = code


class ProviderAuthenticationError(ProviderHTTPError):
    """Raised on HTTP 401/403 credential failure."""
    pass


DEFAULT_APPROVED_ENDPOINTS: frozenset[str] = frozenset({
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://mock-9router:8000",
    "https://localhost:8000",
    "https://127.0.0.1:8000",
    "https://mock-9router:8000",
    "http://localhost",
    "http://127.0.0.1",
    "https://localhost",
    "https://127.0.0.1",
    "https://localhost:8443",
    "http://localhost:8443",
})


class ApprovedEndpointRegistry:
    """Registry of approved endpoints for AI routing and providers (INV-013 / CT-SEC-001).

    Enforces fail-closed endpoint validation against approved authorities.
    """

    def __init__(self, initial_endpoints: Optional[Iterable[str]] = None) -> None:
        self._approved: Set[str] = set()
        defaults = initial_endpoints if initial_endpoints is not None else DEFAULT_APPROVED_ENDPOINTS
        for ep in defaults:
            self.register(ep)

    def _normalize(self, endpoint: str) -> str:
        if not endpoint or not isinstance(endpoint, str):
            raise UnapprovedEndpointError("Endpoint must be a non-empty string")
        clean = endpoint.strip().rstrip("/")
        parsed = urlparse(clean)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise UnapprovedEndpointError(f"Invalid endpoint URI format: '{endpoint}'")
        return clean

    def register(self, endpoint: str) -> None:
        """Registers an endpoint into the approved authority registry."""
        normalized = self._normalize(endpoint)
        self._approved.add(normalized)

    def is_approved(self, endpoint: str) -> bool:
        """Checks if the endpoint is registered."""
        try:
            normalized = self._normalize(endpoint)
            return normalized in self._approved
        except UnapprovedEndpointError:
            return False

    def validate(self, endpoint: str) -> str:
        """Validates endpoint against registry; raises UnapprovedEndpointError if not approved (fail-closed)."""
        normalized = self._normalize(endpoint)
        if normalized not in self._approved:
            raise UnapprovedEndpointError(
                f"Endpoint '{endpoint}' is not in approved endpoint registry (fail-closed)"
            )
        return normalized

    @property
    def endpoints(self) -> frozenset[str]:
        return frozenset(self._approved)


DEFAULT_ENDPOINT_REGISTRY = ApprovedEndpointRegistry()


class NineRouterHTTPAdapter:
    """Resilient HTTP client adapter for 9Router with timeout, 429 backoff, and provenance stamping.

    Enforces:
    - INV-013: Route provenance stamping (X-Route-Provenance, X-Config-Revision-ID) and registry-approved endpoints.
    - INV-021: HTTP timeout handling and 429 exponential backoff with jitter.
    - QR-REL-007: Resilient retry and fail-closed security.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        registry: Optional[ApprovedEndpointRegistry] = None,
    ) -> None:
        self._registry = registry if registry is not None else DEFAULT_ENDPOINT_REGISTRY
        self._base_url = self._registry.validate(base_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def registry(self) -> ApprovedEndpointRegistry:
        return self._registry

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = self._registry.validate(value)

    def call(self, request: AIRequest) -> Dict[str, Any]:
        """Implements ProviderProtocol interface for ProviderRouter integration."""
        response = self.send_request(request)
        return response.payload

    def send_request(
        self,
        req: AIRequest,
        secret_token: Optional[str] = None,
    ) -> AIResponse:
        """Dispatches outbound HTTP request with provenance headers and resilient retry logic."""
        if not req.config_revision_id or not req.config_revision_id.strip():
            raise MissingConfigProvenanceError("Missing required config_revision_id provenance")

        validated_base = self._registry.validate(self._base_url)
        url = f"{validated_base}/v1/chat"
        payload_data = json.dumps({"prompt": req.prompt}).encode("utf-8")

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "X-Config-Revision-ID": req.config_revision_id,
            "X-Route-Provenance": "9router-adapter",
        }
        if secret_token:
            headers["Authorization"] = f"Bearer {secret_token}"

        total_attempts = self.max_retries + 1
        for attempt in range(total_attempts):
            req_obj = urllib.request.Request(
                url=url,
                data=payload_data,
                headers=headers,
            )
            try:
                with urllib.request.urlopen(req_obj, timeout=self.timeout) as resp:
                    raw_body = resp.read()
                    payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                    return AIResponse(payload=payload, fallback_triggered=(attempt > 0))
            except (socket.timeout, TimeoutError) as exc:
                raise ProviderTimeoutError(f"Provider request timed out: {exc}") from exc
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    if attempt < self.max_retries:
                        sleep_time = self.backoff_factor * (2 ** attempt)
                        time.sleep(sleep_time)
                        continue
                    raise ProviderRateLimitExceededError(
                        f"Rate limit exceeded after {self.max_retries} retries"
                    ) from exc
                elif exc.code in (401, 403):
                    raise ProviderAuthenticationError(f"Authentication failure: {exc}") from exc
                raise ProviderHTTPError(f"HTTP error {exc.code}: {exc}") from exc
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                    raise ProviderTimeoutError(f"Provider request timed out: {exc.reason}") from exc
                raise ProviderHTTPError(f"Provider connection error: {exc}") from exc

        raise ProviderRateLimitExceededError("Rate limit exceeded")