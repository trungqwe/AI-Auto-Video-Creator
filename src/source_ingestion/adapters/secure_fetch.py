"""Secure HTTP(S) fetch boundary (A-12; A-RULE-013, A-RULE-014).

Transport and resolver are injected and this module opens no socket. Every hop, including each
redirect target, passes the A-04 SSRF policy before the transport is called, and the transport
must connect only to the pinned addresses in TransportRequest. Limits come from the FetchPolicy
passed in; a missing policy returns INPUT_NOT_READY. Credentials, cookies and token headers never
reach the observation or the log.
"""
from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urljoin

from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.domain.locator import (
    IPAddress,
    LocatorError,
    Resolver,
    ValidatedLocator,
    canonicalize_locator,
    validate_locator,
)
from source_ingestion.domain.package import INPUT_NOT_READY
from source_ingestion.ports.source_adapter import FetchedDocument, FetchObservation

_LOG = logging.getLogger(__name__)

PROBLEM_TYPE_PREFIX = 'urn:source-ingestion:problem:'
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
SENSITIVE_HEADER_MARKERS = ('auth', 'cookie', 'token', 'secret', 'api-key', 'apikey', 'password', 'session', 'signature')


@dataclass(frozen=True)
class FetchPolicy:
    """Fetch limits supplied by configuration; no default values (MODULE-A-OPEN-009)."""

    revision: str
    max_redirects: int
    max_body_bytes: int
    allowed_media_types: frozenset[str]
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError('INVALID_FETCH_POLICY')
        if type(self.max_redirects) is not int or self.max_redirects < 0:
            raise ValueError('INVALID_FETCH_POLICY')
        if type(self.max_body_bytes) is not int or self.max_body_bytes <= 0:
            raise ValueError('INVALID_FETCH_POLICY')
        media = self.allowed_media_types
        if not isinstance(media, frozenset) or not media or not all(
            isinstance(item, str) and item == item.strip().lower() and item.count('/') == 1 for item in media
        ):
            raise ValueError('INVALID_FETCH_POLICY')
        timeout = self.timeout_seconds
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('INVALID_FETCH_POLICY')


@dataclass(frozen=True)
class TransportRequest:
    """One hop: the transport connects only to `addresses` and never follows redirects itself."""

    locator: str
    host: str
    addresses: tuple[IPAddress, ...]
    timeout_seconds: float


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: Iterable[bytes] = field(repr=False)


class Transport(Protocol):
    def send(self, request: TransportRequest) -> TransportResponse: ...


def safe_headers(headers: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Lower-cased headers without credentials, cookies or token-like names (A-RULE-014)."""
    kept: list[tuple[str, str]] = []
    for name, value in headers:
        lowered = name.strip().lower()
        if not any(marker in lowered for marker in SENSITIVE_HEADER_MARKERS):
            kept.append((lowered, value))
    return tuple(kept)


def parse_retry_after(value: str | None, now: datetime) -> int | None:
    """Retry-After as delta-seconds or HTTP-date; unparseable values give None."""
    if value is None:
        return None
    text = value.strip()
    if text.isascii() and text.isdigit():
        return int(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        return None
    return max(0, math.ceil((when - now).total_seconds()))


def _header(headers: Iterable[tuple[str, str]], name: str) -> str | None:
    for key, value in headers:
        if key.strip().lower() == name:
            return value
    return None


def _close(body: object) -> None:
    close = getattr(body, 'close', None)
    if callable(close):
        close()


_PROBLEMS: dict[str, tuple[str, bool, str]] = {
    INPUT_NOT_READY: ('policy', False, 'Fetch policy is missing.'),
    'UNSAFE_LOCATOR': ('security', False, 'Locator rejected by the SSRF policy.'),
    'UNSAFE_REDIRECT': ('security', False, 'Redirect target rejected by the SSRF policy.'),
    'RESOLUTION_FAILED': ('dependency', True, 'Host name resolution failed.'),
    'REDIRECT_WITHOUT_LOCATION': ('dependency', False, 'Redirect response has no Location header.'),
    'REDIRECT_LOOP': ('dependency', False, 'Redirect chain revisits a locator.'),
    'TOO_MANY_REDIRECTS': ('policy', False, 'Redirect limit of the fetch policy exceeded.'),
    'FETCH_TIMEOUT': ('dependency', True, 'Fetch exceeded the policy time limit.'),
    'CONNECTION_FAILED': ('dependency', True, 'Transport connection failed.'),
    'RATE_LIMITED': ('capacity', True, 'Upstream returned HTTP 429.'),
    'UPSTREAM_ERROR': ('dependency', True, 'Upstream returned a retryable HTTP status.'),
    'HTTP_STATUS_REJECTED': ('dependency', False, 'Upstream returned a non-success HTTP status.'),
    'MEDIA_TYPE_NOT_ALLOWED': ('policy', False, 'Response media type is not allowed by the fetch policy.'),
    'BODY_TOO_LARGE': ('policy', False, 'Response body exceeds the fetch policy size limit.'),
}


def fetch_problem(
    code: str,
    correlation_id: str,
    *,
    policy_revision: str | None = None,
    reason: str | None = None,
    status: int | None = None,
    retry_after_seconds: int | None = None,
) -> ProblemDetail:
    """Structured fetch problem; the detail is fixed text that never echoes locators or headers."""
    category, retryable, detail = _PROBLEMS[code]
    _LOG.info('secure fetch problem code=%s retryable=%s', code, retryable)
    return ProblemDetail.create(
        type=PROBLEM_TYPE_PREFIX + code.lower(),
        title=code,
        detail=detail,
        instance=f'urn:source-ingestion:fetch:{correlation_id}',
        code=code,
        category=category,
        retryable=retryable,
        correlation_id=correlation_id,
        status=status,
        reason=reason,
        policy_revision=policy_revision,
        retry_after_seconds=retry_after_seconds,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SecureFetcher:
    """Fetch through an injected transport and resolver; SSRF validation runs before every hop."""

    def __init__(
        self,
        transport: Transport,
        resolver: Resolver,
        *,
        clock: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._transport = transport
        self._resolver = resolver
        self._clock = clock
        self._utc_now = utc_now

    def fetch(self, locator: str, policy: FetchPolicy | None, *, correlation_id: str) -> FetchedDocument | ProblemDetail:
        if not isinstance(policy, FetchPolicy):
            return fetch_problem(INPUT_NOT_READY, correlation_id)
        deadline = self._clock() + policy.timeout_seconds
        target = self._validate(locator, 'UNSAFE_LOCATOR', policy, correlation_id)
        if isinstance(target, ProblemDetail):
            return target
        chain = [target.locator]
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return fetch_problem('FETCH_TIMEOUT', correlation_id, policy_revision=policy.revision)
            request = TransportRequest(target.locator, target.host, target.addresses, remaining)
            try:
                response = self._transport.send(request)
            except TimeoutError:
                return fetch_problem('FETCH_TIMEOUT', correlation_id, policy_revision=policy.revision)
            except OSError:
                return fetch_problem('CONNECTION_FAILED', correlation_id, policy_revision=policy.revision)
            _LOG.debug('secure fetch hop=%d status=%d', len(chain), response.status)
            try:
                if response.status not in REDIRECT_STATUSES:
                    return self._complete(response, chain, policy, correlation_id, deadline)
                target = self._next_hop(response, chain, policy, correlation_id)
                if isinstance(target, ProblemDetail):
                    return target
                chain.append(target.locator)
            finally:
                _close(response.body)

    def _validate(
        self, locator: str, code: str, policy: FetchPolicy, correlation_id: str
    ) -> ValidatedLocator | ProblemDetail:
        try:
            return validate_locator(locator, self._resolver)
        except LocatorError as error:
            if error.reason == 'RESOLUTION_FAILED':
                code = 'RESOLUTION_FAILED'
            return fetch_problem(code, correlation_id, policy_revision=policy.revision, reason=error.reason)

    def _next_hop(
        self, response: TransportResponse, chain: list[str], policy: FetchPolicy, correlation_id: str
    ) -> ValidatedLocator | ProblemDetail:
        revision = policy.revision
        location = _header(response.headers, 'location')
        if location is None or not location.strip():
            return fetch_problem(
                'REDIRECT_WITHOUT_LOCATION', correlation_id, policy_revision=revision, status=response.status
            )
        try:
            candidate = canonicalize_locator(urljoin(chain[-1], location.strip()))
        except ValueError as error:
            reason = getattr(error, 'reason', 'INVALID_LOCATOR')
            return fetch_problem('UNSAFE_REDIRECT', correlation_id, policy_revision=revision, reason=reason)
        if candidate in chain:
            return fetch_problem('REDIRECT_LOOP', correlation_id, policy_revision=revision)
        if len(chain) > policy.max_redirects:
            return fetch_problem('TOO_MANY_REDIRECTS', correlation_id, policy_revision=revision)
        return self._validate(candidate, 'UNSAFE_REDIRECT', policy, correlation_id)

    def _complete(
        self, response: TransportResponse, chain: list[str], policy: FetchPolicy, correlation_id: str, deadline: float
    ) -> FetchedDocument | ProblemDetail:
        revision, status = policy.revision, response.status
        if status == 429:
            retry_after = parse_retry_after(_header(response.headers, 'retry-after'), self._utc_now())
            return fetch_problem(
                'RATE_LIMITED', correlation_id, policy_revision=revision, status=status, retry_after_seconds=retry_after
            )
        if status == 408 or 500 <= status <= 599:
            return fetch_problem('UPSTREAM_ERROR', correlation_id, policy_revision=revision, status=status)
        if not 200 <= status <= 299:
            return fetch_problem('HTTP_STATUS_REJECTED', correlation_id, policy_revision=revision, status=status)
        media_type = (_header(response.headers, 'content-type') or '').split(';', 1)[0].strip().lower()
        if media_type not in policy.allowed_media_types:
            return fetch_problem('MEDIA_TYPE_NOT_ALLOWED', correlation_id, policy_revision=revision, status=status)
        declared = (_header(response.headers, 'content-length') or '').strip()
        if declared.isascii() and declared.isdigit() and int(declared) > policy.max_body_bytes:
            return fetch_problem('BODY_TOO_LARGE', correlation_id, policy_revision=revision, status=status)
        body = bytearray()
        try:
            for chunk in response.body:
                body += chunk
                if len(body) > policy.max_body_bytes:
                    return fetch_problem('BODY_TOO_LARGE', correlation_id, policy_revision=revision, status=status)
                if self._clock() >= deadline:
                    return fetch_problem('FETCH_TIMEOUT', correlation_id, policy_revision=revision)
        except TimeoutError:
            return fetch_problem('FETCH_TIMEOUT', correlation_id, policy_revision=revision)
        except OSError:
            return fetch_problem('CONNECTION_FAILED', correlation_id, policy_revision=revision)
        observation = FetchObservation(
            requested_locator=chain[0],
            final_locator=chain[-1],
            redirect_chain=tuple(chain),
            status=status,
            media_type=media_type,
            size_bytes=len(body),
            safe_headers=safe_headers(response.headers),
            policy_revision=revision,
        )
        return FetchedDocument(observation, bytes(body))
