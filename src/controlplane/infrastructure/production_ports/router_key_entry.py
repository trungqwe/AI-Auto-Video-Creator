"""PP-2: one-time entry of the 9Router key into the DPAPI vault.

The value comes only from the injected read_value callable (getpass in the launcher script), never from arguments; the only line printed names the alias and version, never the value.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from controlplane.infrastructure.production_ports.ports_config import load_ports_config
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.secret_redaction import SecretValue


def store_router_key(store: DpapiSecretStore, secret_ref: str, read_value: Callable[[], str]) -> int:
    raw = read_value()
    if not isinstance(raw, str):
        raise ValueError('router key must be a string')
    value = raw.strip()
    if not value:
        raise ValueError('router key must not be empty')
    return store.put(secret_ref, SecretValue(value))


def run(vault_dir: Path, ports_config_path: Path, read_value: Callable[[], str], out: Callable[[str], None]) -> int:
    config = load_ports_config(ports_config_path)
    version = store_router_key(DpapiSecretStore(vault_dir), config.router.secret_ref, read_value)
    out(f'Đã lưu khóa 9Router qua kho DPAPI: {config.router.secret_ref} (v{version})')
    return version


__all__ = ['run', 'store_router_key']
