"""Unimplemented local HTTPS listener boundary for P7A Behavioral RED."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass


@dataclass(frozen=True)
class LoopbackTlsEndpoint:
    host: str
    port: int
    ca_certificate_pem: str


def start_loopback_tls_server() -> AbstractContextManager[LoopbackTlsEndpoint]:
    """Eventually start an ephemeral loopback HTTPS server with verifiable TLS."""
    raise NotImplementedError("P7A-004 local TLS listener/handshake unimplemented")
