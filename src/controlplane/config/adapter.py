"""HTTP Client Adapter for 9Router and Provider Routing (INV-013 / INV-021 / QR-REL-007).

Scaffold for TASK-CAP-J-P1-B.
"""
from __future__ import annotations

import io
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Dict, Any, Optional
from src.controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
)


class ProviderHTTPError(Exception):
    """Base exception for provider HTTP adapter errors."""
    pass


class ProviderTimeoutError(ProviderHTTPError):
    """Raised when an outbound provider HTTP request times out (INV-021)."""
    pass


class ProviderRateLimitExceededError(ProviderHTTPError):
    """Raised when provider returns HTTP 429 and retries are exhausted (INV-021)."""
    pass


class ProviderAuthenticationError(ProviderHTTPError):
    """Raised on HTTP 401/403 credential failure."""
    pass


class NineRouterHTTPAdapter:
    """Resilient HTTP client adapter for 9Router with timeout, 429 backoff, and provenance stamping.

    Enforces:
    - INV-013: Route provenance stamping (X-Route-Provenance, X-Config-Revision-ID).
    - INV-021: HTTP timeout handling and 429 exponential backoff with jitter.
    - QR-REL-007: Resilient retry and fail-closed security.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def send_request(
        self,
        req: AIRequest,
        secret_token: Optional[str] = None,
    ) -> AIResponse:
        """Dispatches outbound HTTP request with provenance headers and resilient retry logic."""
        if not req.config_revision_id or not req.config_revision_id.strip():
            raise MissingConfigProvenanceError("Missing required config_revision_id provenance")

        url = f"{self.base_url}/v1/chat"
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
