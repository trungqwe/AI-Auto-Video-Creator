"""Composition root: đọc cấu hình, dựng TransactionManager, gọi create_app."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os

from fastapi import FastAPI

from controlplane.api.main import create_app
from controlplane.entrypoint import main as serve
from controlplane.infrastructure.db.uow import TransactionManager

DEFAULT_PORT = 8443


@dataclass(frozen=True)
class ControlPlaneConfig:
    dsn: str
    port: int

    @property
    def allowed_origins(self) -> set[str]:
        return {f"https://localhost:{self.port}", f"https://127.0.0.1:{self.port}"}


def read_config(environ: Mapping[str, str]) -> ControlPlaneConfig:
    dsn = environ.get("CONTROLPLANE_DSN", "").strip()
    if not dsn:
        raise ValueError("CONTROLPLANE_DSN is required")
    try:
        port = int(environ.get("CONTROLPLANE_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise ValueError("CONTROLPLANE_PORT must be an integer") from exc
    if not (1 <= port <= 65535):
        raise ValueError("CONTROLPLANE_PORT must be within 1..65535")
    return ControlPlaneConfig(dsn=dsn, port=port)


def build_app(environ: Mapping[str, str] | None = None) -> FastAPI:
    """ASGI factory: đọc cấu hình, khởi tạo TransactionManager và gọi create_app.

    Việc nghe TLS loopback vẫn do controlplane.entrypoint (P7A).
    Chưa gọi build_<phân hệ>_services vì api/wiring ngoài phong bì (BL-CV-06).
    """
    config = read_config(os.environ if environ is None else environ)
    manager = TransactionManager(config.dsn)
    return create_app(manager=manager, allowed_origins=config.allowed_origins)


if __name__ == "__main__":
    raise SystemExit(serve())