"""PP-8: assembly of the eight ProductionRuntime port values and a read-only description of them (CT-SEC-001, INV-012, ADR-0006).

build_production_ports wires the PP-1 to PP-7 adapters from the production profile and the ports config and returns exactly the keyword values ProductionRuntime expects. Every port error (DrivePlacementError, DriveTokenError, ProviderCredentialError, ValueError) propagates unchanged and no placement value is ever invented; the Drive placement is built last so a configuration error fails before any network call.
describe_runtime_ports only checks that aliases, the OAuth client file, the staging directory and the placement state file exist: it decrypts nothing and opens no connection.
ASSUMPTION (D8): the Drive placement requests use profile drive.chunk_timeout_seconds as their timeout.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
from controlplane.infrastructure.production_ports.credentials import RouterKeyCredentials
from controlplane.infrastructure.production_ports.drive_placement import DrivePlacementBootstrap
from controlplane.infrastructure.production_ports.drive_token import build_drive_token_broker
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from controlplane.infrastructure.production_ports.route_catalog import ProfileRouteCatalog
from controlplane.infrastructure.production_ports.vision_route import RouterVisionRoute
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF as DRIVE_SECRET_REF

if TYPE_CHECKING:
    from controlplane.api.wiring.production_profile import ProductionProfile
    from controlplane.infrastructure.production_ports.ports_config import PortsConfig


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _profile_value(profile: ProductionProfile, name: str, key: str) -> Any:
    section = profile.parameters.get(name)
    if not isinstance(section, Mapping) or key not in section:
        raise ValueError(f'profile parameter {name} must contain {key}')
    return section[key]


def build_production_ports(
    profile: ProductionProfile,
    *,
    vault_dir: Path,
    staging_dir: Path,
    state_dir: Path,
    oauth_client_secrets_path: Path,
    ports_config: PortsConfig,
    http_factory: Callable[[float], Any] | None = None,
) -> dict[str, Any]:
    store = DpapiSecretStore(Path(vault_dir))
    router = ports_config.router
    model_refs = profile.ai.route_model_refs
    provider_credentials = RouterKeyCredentials(store, router.account_ref, router.secret_ref)
    route_catalog = ProfileRouteCatalog(model_refs, router.account_ref, router.secret_ref, store)
    vision_route = RouterVisionRoute(profile.ai.route_endpoint, model_refs, provider_credentials, router.account_ref)
    artifact_source = StagingArtifactSource(Path(staging_dir))
    drive_token_broker = build_drive_token_broker(
        Path(oauth_client_secrets_path), profile.credential_max_ttl_seconds, store, _utc_now,
    )
    gpu_lease = LocalGpuLease(
        _profile_value(profile, 'gpu.slots', 'slots'),
        math.ceil(profile.render.timeout_seconds) + ports_config.gpu_lease.grace_seconds,
    )
    retry = profile.drive.retry
    bootstrap = DrivePlacementBootstrap(
        drive_token_broker,
        Path(state_dir) / ports_config.drive.placement_state_file,
        _profile_value(profile, 'drive.folders', 'root'),
        ports_config.drive.artifact_namespaces,
        retry_max_attempts=retry.max_attempts,
        backoff_base_seconds=retry.backoff_base_seconds,
        backoff_cap_seconds=retry.backoff_max_seconds,
        timeout_seconds=profile.drive.chunk_timeout_seconds,
        http_factory=http_factory,
    )
    placement = bootstrap.ensure()
    return {
        'route_catalog': route_catalog,
        'provider_credentials': provider_credentials,
        'vision_route': vision_route,
        'artifact_source': artifact_source,
        'drive_token_broker': drive_token_broker,
        'gpu_lease': gpu_lease,
        'drive_placement': placement.placement,
        'drive_fallback_parent_id': placement.fallback_parent_id,
    }


def describe_runtime_ports(
    *,
    vault_dir: Path,
    staging_dir: Path,
    state_dir: Path,
    oauth_client_secrets_path: Path,
    ports_config: PortsConfig,
) -> list[tuple[str, bool, str]]:
    store = DpapiSecretStore(Path(vault_dir))
    router_ready = store.current_version(ports_config.router.secret_ref) is not None
    router_reason = 'khóa 9Router có trong kho' if router_ready else 'thiếu khóa 9Router trong kho'
    staging_ready = Path(staging_dir).is_dir()
    token_problems = [
        text
        for ok, text in (
            (store.current_version(DRIVE_SECRET_REF) is not None, 'thiếu bí danh OAuth Drive trong kho'),
            (Path(oauth_client_secrets_path).is_file(), 'thiếu tệp OAuth client'),
        )
        if not ok
    ]
    placement_ready = (Path(state_dir) / ports_config.drive.placement_state_file).is_file()
    return [
        ('route_catalog', router_ready, router_reason),
        ('provider_credentials', router_ready, router_reason),
        ('vision_route', router_ready, router_reason),
        ('artifact_source', staging_ready, 'thư mục staging có sẵn' if staging_ready else 'thiếu thư mục staging'),
        ('drive_token_broker', not token_problems, '; '.join(token_problems) or 'có bí danh OAuth Drive và tệp OAuth client'),
        ('gpu_lease', True, 'chạy trong tiến trình, không cần tài nguyên ngoài'),
        ('drive_placement', placement_ready, 'có tệp trạng thái placement' if placement_ready else 'chưa có tệp trạng thái placement; lần dựng đầu sẽ tạo thư mục Drive'),
    ]


__all__ = ['build_production_ports', 'describe_runtime_ports']
