"""ProviderExecutorPort of D through 9Router (ADAPT-D, CT-AI-ROUTE-002, INV-013, INV-021, BL-CV-04).

Endpoint, timeout, retry and backoff come from configuration; the credential only travels through credential_method and never reaches ExecutionResult, a log or a record.
Every HTTP call goes through NineRouterHTTPAdapter; this module opens no connection itself and holds no fixed endpoint.
GIẢ ĐỊNH (D8): config_revision_id sent to 9Router is the route_revision of the decision (J-18 hands only the decision to the executor); endpoint is the origin because NineRouterHTTPAdapter appends /v1/chat (Control confirms the 9Router port at CP7, OI-ADAPT-05).
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.application.config_security.routed_invocation import ExecutionResult
from controlplane.config.adapter import ApprovedEndpointRegistry, NineRouterHTTPAdapter
from controlplane.config.models import AIRequest
from controlplane.domain.config_security.route_binding import ProviderRouteDecision

_REQUIRED_KEYS = (
    'endpoint', 'approved_endpoints', 'request_timeout_seconds', 'max_retries', 'backoff_factor', 'cost_per_request',
)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class RouteExecutorConfig:
    """Executor settings read from configuration; there are no defaults, a missing or invalid key is a ValueError."""

    endpoint: str
    approved_endpoints: tuple[str, ...]
    request_timeout_seconds: float
    max_retries: int
    backoff_factor: float
    cost_per_request: Decimal

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> RouteExecutorConfig:
        missing = [name for name in _REQUIRED_KEYS if name not in config]
        if missing:
            raise ValueError('missing executor config keys: ' + ', '.join(missing))
        endpoint = config['endpoint']
        approved = config['approved_endpoints']
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError('endpoint must be a non-empty string')
        if not isinstance(approved, (list, tuple)) or not approved or not all(isinstance(item, str) for item in approved):
            raise ValueError('approved_endpoints must be a non-empty list of strings')
        timeout = config['request_timeout_seconds']
        if not _is_number(timeout) or timeout <= 0:
            raise ValueError('request_timeout_seconds must be a positive number')
        retries = config['max_retries']
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError('max_retries must be an integer >= 0')
        backoff = config['backoff_factor']
        if not _is_number(backoff) or backoff < 0:
            raise ValueError('backoff_factor must be a number >= 0')
        try:
            cost = Decimal(str(config['cost_per_request']))
        except InvalidOperation as exc:
            raise ValueError('cost_per_request must be a decimal number') from exc
        if not cost.is_finite() or cost < 0:
            raise ValueError('cost_per_request must be finite and >= 0')
        return cls(endpoint.strip(), tuple(approved), float(timeout), retries, float(backoff), cost)


class InvocationPayloadStore:
    """In-memory hand-off between D and the executor: J-18 passes only a payload ref, so the prompt and the model output travel by ref. It holds no secret."""

    def __init__(self) -> None:
        self._requests: dict[str, str] = {}
        self._outputs: dict[str, Mapping[str, Any]] = {}

    def put_request(self, ref: str, prompt: str) -> None:
        self._requests[ref] = prompt

    def get_request(self, ref: str) -> str:
        try:
            return self._requests[ref]
        except KeyError:
            raise LookupError('unknown request payload ref') from None

    def drop_request(self, ref: str) -> None:
        self._requests.pop(ref, None)

    def put_output(self, ref: str, payload: Mapping[str, Any]) -> str:
        self._outputs[ref] = payload
        return ref

    def pop_output(self, ref: str) -> Mapping[str, Any]:
        try:
            return self._outputs.pop(ref)
        except KeyError:
            raise LookupError('unknown output ref') from None


class CredentialSourcePort(Protocol):
    def acquire(self, credential_method: str, account_ref: str) -> AbstractContextManager[str]: ...



class NineRouterExecutor:
    """ProviderExecutorPort: sends the stored prompt to 9Router through NineRouterHTTPAdapter and returns the model payload by ref."""

    def __init__(self, config: RouteExecutorConfig, store: InvocationPayloadStore, credentials: CredentialSourcePort) -> None:
        if not isinstance(config, RouteExecutorConfig):
            raise TypeError('config must be a RouteExecutorConfig')
        if not isinstance(store, InvocationPayloadStore):
            raise TypeError('store must be an InvocationPayloadStore')
        self._http = NineRouterHTTPAdapter(
            base_url=config.endpoint,
            timeout=config.request_timeout_seconds,
            max_retries=config.max_retries,
            backoff_factor=config.backoff_factor,
            registry=ApprovedEndpointRegistry.from_config(config.approved_endpoints),
        )
        self._store = store
        self._credentials = credentials
        self._cost = config.cost_per_request

    @property
    def http_adapter(self) -> NineRouterHTTPAdapter:
        return self._http

    def execute(
        self, decision: ProviderRouteDecision, candidate_ref: str, request_payload_ref: str, credential_method: str
    ) -> ExecutionResult:
        """A provider failure is returned in ExecutionResult.error so RoutedInvocationService can classify it; it is not raised."""
        try:
            if credential_method != CREDENTIAL_METHOD:
                raise ValueError('unsupported credential_method')
            prompt = self._store.get_request(request_payload_ref)
            with self._credentials.acquire(credential_method, decision.account_ref) as token:
                request = AIRequest(prompt=prompt, config_revision_id=decision.route_revision)
                response = self._http.send_request(request, secret_token=token)
        except Exception as exc:
            return ExecutionResult(False, None, Decimal('0'), exc)
        output_ref = self._store.put_output(request_payload_ref + '-output', response.payload)
        return ExecutionResult(True, output_ref, self._cost, None)


__all__ = ['CredentialSourcePort', 'InvocationPayloadStore', 'NineRouterExecutor', 'RouteExecutorConfig']
