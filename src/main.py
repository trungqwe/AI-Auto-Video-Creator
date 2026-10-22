"""Composition root: đọc cấu hình, chọn hồ sơ test hoặc production, dựng TransactionManager, gọi create_app."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os

from controlplane.api.main import create_app
from controlplane.entrypoint import main as serve
from controlplane.infrastructure.db.uow import TransactionManager

DEFAULT_PORT = 8443
PROFILE_TEST = 'test'
PROFILE_PRODUCTION = 'production'

@dataclass(frozen=True)
class ControlPlaneConfig:
    dsn: str
    port: int
    profile: str = PROFILE_TEST

    @property
    def allowed_origins(self) -> set[str]:
        return {f'https://localhost:{self.port}', f'https://127.0.0.1:{self.port}'}

def read_config(environ: Mapping[str, str]) -> ControlPlaneConfig:
    dsn = environ.get('CONTROLPLANE_DSN', '').strip()
    if not dsn:
        raise ValueError('CONTROLPLANE_DSN is required')
    try:
        port = int(environ.get('CONTROLPLANE_PORT', str(DEFAULT_PORT)))
    except ValueError as exc:
        raise ValueError('CONTROLPLANE_PORT must be an integer') from exc
    if not (1 <= port <= 65535):
        raise ValueError('CONTROLPLANE_PORT must be within 1..65535')
    profile = environ.get('CONTROLPLANE_PROFILE', PROFILE_TEST).strip() or PROFILE_TEST
    if profile not in (PROFILE_TEST, PROFILE_PRODUCTION):
        raise ValueError('CONTROLPLANE_PROFILE must be test or production')
    return ControlPlaneConfig(dsn=dsn, port=port, profile=profile)

def _production_module() -> object:
    # Nạp muộn: hồ sơ test không kéo adapter thật; __import__ giữ main.py trong phong bì import của CP-4-WIRING.
    return __import__("controlplane.api.wiring.production", fromlist=["build_production_app"])


def build_app(environ: Mapping[str, str] | None = None,
              runtime_factory: Callable[[object], object] | None = None) -> object:
    """ASGI factory cho hai hồ sơ.

    test (mặc định): giữ hành vi CP-4-WIRING, TransactionManager rồi create_app.
    production: nạp profile và kiểm mọi tham số trước khi mở DB (thiếu thì ném ProductionProfileError,
    không khởi động), rồi gọi các build_<phân hệ>_services và create_app qua wiring.production.
    runtime_factory(profile) do launcher cấp ProductionRuntime.
    """
    env = os.environ if environ is None else environ
    config = read_config(env)
    if config.profile == PROFILE_TEST:
        manager = TransactionManager(config.dsn)
        return create_app(manager=manager, allowed_origins=config.allowed_origins)
    production = _production_module()
    wiring = production.load_wiring_config(env, runtime_factory=runtime_factory)
    manager = TransactionManager(config.dsn)
    try:
        return production.build_production_app(manager=manager, config=wiring, port=config.port)
    except BaseException:
        manager.close()
        raise

if __name__ == "__main__":
    if os.environ.get("CONTROLPLANE_PROFILE", PROFILE_TEST).strip() == PROFILE_PRODUCTION:
        raise SystemExit("production profile must be started by the launcher (build_app + serve_production_tls)")
    raise SystemExit(serve())
