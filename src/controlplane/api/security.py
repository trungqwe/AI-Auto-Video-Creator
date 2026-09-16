"""Unimplemented HTTP security boundaries for the P7A Behavioral RED oracle."""

from __future__ import annotations

import httpx


def enforce_host(request: httpx.Request) -> None:
    """Eventually reject non-loopback Host headers before request dispatch."""
    raise NotImplementedError("P7A-001 Host validation unimplemented")


def enforce_csrf(request: httpx.Request) -> None:
    """Eventually validate the double-submit cookie on browser mutations."""
    raise NotImplementedError("P7A-002 CSRF protection unimplemented")
