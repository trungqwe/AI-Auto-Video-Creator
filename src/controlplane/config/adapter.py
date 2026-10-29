"""HTTP Client Adapter for 9Router and Provider Routing (INV-013 / INV-021 / QR-REL-007).

Scaffold for TASK-CAP-J-P1-B.
"""
from __future__ import annotations

import io
import json
import socket
import time
from typing import Dict, Any, Optional, Iterable
from dataclasses import dataclass
import urllib.error
from urllib.parse import urlparse
import urllib.request

from controlplane.config.models import (
    AIRequest,
    AIResponse,
    MissingConfigProvenanceError,
    RateLimitError,
)


@dataclass
class ChatAIRequest(AIRequest):
    """AIRequest that also carries the model of the route decision for the chat completions body (R15)."""
    model: Optional[str] = None


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
    """Immutable registry of approved endpoints for AI routing and providers (INV-013 / CT-SEC-001).

    Enforces fail-closed endpoint validation against approved authorities.
    Only approved configuration authorities may define endpoints; dynamic or caller-controlled
    mutations are strictly forbidden.
    """

    def __init__(self, initial_endpoints: Optional[Iterable[str]] = None) -> None:
        if initial_endpoints is not None:
            normalized_list = [self._normalize(ep) for ep in initial_endpoints]
            for ep in normalized_list:
                if ep not in DEFAULT_APPROVED_ENDPOINTS:
                    raise UnapprovedEndpointError(
                        f"Endpoint '{ep}' is not within approved authority boundary (fail-closed)"
                    )
            self._approved: frozenset[str] = frozenset(normalized_list)
        else:
            self._approved = DEFAULT_APPROVED_ENDPOINTS
        self._config_owned: bool = False

    @classmethod
    def from_config(cls, endpoints: Iterable[str]) -> "ApprovedEndpointRegistry":
        """Build the registry from the endpoint list of the configuration (BL-CV-04, D8-ADAPT-01).

        The list is host/configuration-owned, so the DEFAULT_APPROVED_ENDPOINTS subset check of the constructor does not apply.
        An empty list or an invalid entry fails closed with UnapprovedEndpointError.
        """
        if isinstance(endpoints, (str, bytes)):
            raise UnapprovedEndpointError("Config endpoints must be an iterable of endpoint strings")
        normalized = frozenset(cls._normalize(ep) for ep in endpoints)
        if not normalized:
            raise UnapprovedEndpointError("Config endpoint list must not be empty (fail-closed)")
        registry = cls.__new__(cls)
        registry._approved = normalized
        registry._config_owned = True
        return registry

    @property
    def config_owned(self) -> bool:
        return self._config_owned

    @staticmethod
    def _normalize(endpoint: str) -> str:
        if not endpoint or not isinstance(endpoint, str):
            raise UnapprovedEndpointError("Endpoint must be a non-empty string")
        clean = endpoint.strip().rstrip("/")
        parsed = urlparse(clean)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise UnapprovedEndpointError(f"Invalid endpoint URI format: '{endpoint}'")
        return clean

    def register(self, endpoint: str) -> None:
        """Registration after initialization is strictly prohibited (INV-013 immutable authority)."""
        raise UnapprovedEndpointError(
            "ApprovedEndpointRegistry is immutable: dynamic endpoint registration is prohibited"
        )

    def is_approved(self, endpoint: str) -> bool:
        """Checks if the endpoint is in the immutable approved authority."""
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
        return self._approved


DEFAULT_ENDPOINT_REGISTRY = ApprovedEndpointRegistry()


_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_V1_SUFFIX = "/v1"


def _response_content_type(resp: Any) -> str:
    headers = getattr(resp, "headers", None)
    getter = getattr(headers, "get", None)
    value = getter("Content-Type") if callable(getter) else None
    return value.lower() if isinstance(value, str) else ""


class NineRouterHTTPAdapter:
    """Resilient HTTP client adapter for 9Router with timeout, 429 backoff, and provenance stamping.

    Enforces:
    - INV-013: Route provenance stamping (X-Route-Provenance, X-Config-Revision-ID) and registry-approved endpoints.
    - INV-021: HTTP timeout handling and 429 exponential backoff with jitter.
    - QR-REL-007: Resilient retry and fail-closed security.
    - R15: POST to <origin>/v1/chat/completions with an OpenAI-compatible body (model, messages); a trailing /v1 of the endpoint is dropped so one URL results.
    - R16: request body carries "stream": false and the Accept: application/json header; a text/event-stream reply is a clear ProviderHTTPError (no SSE assembling).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        registry: Optional[ApprovedEndpointRegistry] = None,
    ) -> None:
        if registry is not None and registry is not DEFAULT_ENDPOINT_REGISTRY and not (
            isinstance(registry, ApprovedEndpointRegistry) and registry.config_owned
        ):
            raise UnapprovedEndpointError(
                "Caller-supplied endpoint registry is rejected: authority is strictly host/configuration-owned (INV-013)"
            )
        self._registry = registry if registry is not None else DEFAULT_ENDPOINT_REGISTRY
        self._bound_endpoint: str = self._registry.validate(base_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def registry(self) -> ApprovedEndpointRegistry:
        return self._registry

    @property
    def base_url(self) -> str:
        return self._bound_endpoint

    @property
    def bound_endpoint(self) -> str:
        return self._bound_endpoint

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

        validated_base = self._registry.validate(self._bound_endpoint)
        if validated_base != self._bound_endpoint:
            raise UnapprovedEndpointError("Endpoint drift detected prior to dispatch (fail-closed)")

        root = validated_base[: -len(_V1_SUFFIX)] if validated_base.endswith(_V1_SUFFIX) else validated_base
        url = f"{root}{_CHAT_COMPLETIONS_PATH}"
        body: Dict[str, Any] = {"messages": [{"role": "user", "content": req.prompt}], "stream": False}
        model = getattr(req, "model", None)
        if isinstance(model, str) and model.strip():
            body = {"model": model, **body}
        payload_data = json.dumps(body).encode("utf-8")

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
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
                    content_type = _response_content_type(resp)
                    if "text/event-stream" in content_type:
                        raise ProviderHTTPError(
                            f"Provider returned a text/event-stream (SSE) response although stream=false and Accept: application/json were requested; streaming responses are not supported (Content-Type: {content_type})"
                        )
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
