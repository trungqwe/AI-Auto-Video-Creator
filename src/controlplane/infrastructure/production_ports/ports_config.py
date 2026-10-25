"""PP-2: strict loader for tools/launcher/prod/ports.json (aliases, GPU lease grace, Drive placement layout).

Every key is required and type-checked; this module holds no built-in values, so a missing or mistyped key fails with ValueError.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RouterPortsConfig:
    account_ref: str
    secret_ref: str


@dataclass(frozen=True)
class GpuLeasePortsConfig:
    grace_seconds: int


@dataclass(frozen=True)
class DrivePortsConfig:
    placement_state_file: str
    artifact_namespaces: tuple[str, ...]


@dataclass(frozen=True)
class PortsConfig:
    revision: int
    router: RouterPortsConfig
    gpu_lease: GpuLeasePortsConfig
    drive: DrivePortsConfig


def _section(raw: object, name: str, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f'{name} must be a JSON object')
    missing = [key for key in keys if key not in raw]
    if missing:
        listed = ', '.join(missing)
        raise ValueError(f'{name} is missing keys: {listed}')
    unknown = sorted(set(raw) - set(keys))
    if unknown:
        listed = ', '.join(unknown)
        raise ValueError(f'{name} has unknown keys: {listed}')
    return raw


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'{name} must be a positive int')
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _file_name(value: object, name: str) -> str:
    text = _text(value, name)
    if '/' in text or chr(92) in text or text in ('.', '..'):
        raise ValueError(f'{name} must be a bare file name')
    return text


def _names(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f'{name} must be a non-empty list')
    names = tuple(_text(item, name + ' item') for item in value)
    if len(set(names)) != len(names):
        raise ValueError(f'{name} must not contain duplicates')
    return names


def load_ports_config(path: Path) -> PortsConfig:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    top = _section(data, 'ports', ('revision', 'router', 'gpu_lease', 'drive'))
    router = _section(top['router'], 'router', ('account_ref', 'secret_ref'))
    gpu_lease = _section(top['gpu_lease'], 'gpu_lease', ('grace_seconds',))
    drive = _section(top['drive'], 'drive', ('placement_state_file', 'artifact_namespaces'))
    return PortsConfig(
        revision=_positive_int(top['revision'], 'revision'),
        router=RouterPortsConfig(
            account_ref=_text(router['account_ref'], 'router.account_ref'),
            secret_ref=_text(router['secret_ref'], 'router.secret_ref'),
        ),
        gpu_lease=GpuLeasePortsConfig(grace_seconds=_positive_int(gpu_lease['grace_seconds'], 'gpu_lease.grace_seconds')),
        drive=DrivePortsConfig(
            placement_state_file=_file_name(drive['placement_state_file'], 'drive.placement_state_file'),
            artifact_namespaces=_names(drive['artifact_namespaces'], 'drive.artifact_namespaces'),
        ),
    )


__all__ = ['DrivePortsConfig', 'GpuLeasePortsConfig', 'PortsConfig', 'RouterPortsConfig', 'load_ports_config']
