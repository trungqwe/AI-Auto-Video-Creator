"""Request-level Host and double-submit CSRF validation."""

from __future__ import annotations

import httpx
import secrets
import re
from http.cookies import SimpleCookie


_LOOPBACK_HOST = re.compile(r"(?:localhost|127\.0\.0\.1)(?::([0-9]+))?\Z", re.ASCII)


def enforce_host(request: httpx.Request) -> None:
    """Reject ambiguous or non-loopback authorities before dispatch."""
    hosts = request.headers.get_list("host")
    if len(hosts) != 1:
        raise PermissionError("invalid Host")
    match = _LOOPBACK_HOST.fullmatch(hosts[0])
    if match is None:
        raise PermissionError("invalid Host")
    port = match.group(1)
    if port is not None and not 1 <= int(port) <= 65535:
        raise PermissionError("invalid Host")


def enforce_csrf(request: httpx.Request) -> None:
    """Require matching nonempty cookie and header values on mutations."""
    raw_cookies = request.headers.get_list("cookie")
    if len(raw_cookies) != 1:
        raise PermissionError("CSRF cookie missing")
    csrf_cookie_count = sum(
        segment.strip().partition("=")[0] == "csrf_token"
        for segment in raw_cookies[0].split(";")
    )
    if csrf_cookie_count != 1:
        raise PermissionError("ambiguous CSRF cookie")
    parsed = SimpleCookie()
    try:
        parsed.load(raw_cookies[0])
    except Exception as exc:
        raise PermissionError("invalid CSRF cookie") from exc
    morsel = parsed.get("csrf_token")
    cookie = morsel.value if morsel is not None else None
    headers = request.headers.get_list("x-csrf-token")
    if not cookie or len(headers) != 1 or not headers[0]:
        raise PermissionError("CSRF token missing")
    if not secrets.compare_digest(cookie, headers[0]):
        raise PermissionError("CSRF token mismatch")
