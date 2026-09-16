"""Verified loopback TLS server running the actual FastAPI app."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Thread
import time
from typing import Iterator

import uvicorn

from controlplane.api.main import create_app
from controlplane.infrastructure.security.loopback_certificate import (
    LoopbackCertificate, provision_loopback_certificate,
)


@dataclass(frozen=True)
class LoopbackTlsEndpoint:
    host: str
    port: int
    ca_certificate_pem: str


def _configuration(*, manager: object | None, certificate: LoopbackCertificate,
                   port: int, allowed_origins: set[str] | None = None) -> uvicorn.Config:
    return uvicorn.Config(
        create_app(manager=manager, allowed_origins=allowed_origins),
        host="127.0.0.1", port=port,
        ssl_certfile=certificate.certificate_path,
        ssl_keyfile=certificate.private_key_path,
        log_level="warning", access_log=False,
    )


def serve_loopback_tls(*, manager: object, port: int) -> None:
    """Run the same TLS/app composition as the verified test listener."""
    if not 1 <= port <= 65535:
        raise ValueError("Control API port must be within 1..65535")
    origins = {f"https://localhost:{port}", f"https://127.0.0.1:{port}"}
    with provision_loopback_certificate() as certificate:
        uvicorn.Server(_configuration(
            manager=manager, certificate=certificate, port=port,
            allowed_origins=origins,
        )).run()


@contextmanager
def start_loopback_tls_server(*, manager: object | None = None) -> Iterator[LoopbackTlsEndpoint]:
    """Run the production app composition behind a transient trusted certificate."""
    with provision_loopback_certificate() as certificate:
        server = uvicorn.Server(_configuration(
            manager=manager, certificate=certificate, port=0,
        ))
        thread = Thread(target=server.run, name="controlplane-loopback-tls", daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not server.started or not server.servers:
            server.should_exit = True
            thread.join(timeout=5)
            raise RuntimeError("loopback TLS server did not start")
        sockets = server.servers[0].sockets
        if not sockets:
            server.should_exit = True
            thread.join(timeout=5)
            raise RuntimeError("loopback TLS listener unavailable")
        port = sockets[0].getsockname()[1]
        try:
            yield LoopbackTlsEndpoint("127.0.0.1", port, certificate.certificate_pem)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
