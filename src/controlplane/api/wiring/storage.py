from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ I (storage).
Đấu nối DriveObjectStore và PostgresStorageMetaRepository.
Không gọi Google lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    ProductionProfileError,
    WiringConfig,
)
from controlplane.application.storage_meta.cloud_persist import (
    ObjectAlreadyExistsError,
)
from controlplane.application.storage_meta.handlers import (
    materialize_artifact_set_handler,
    reconcile_storage_handler,
    request_cleanup_evaluation_handler,
)
from controlplane.application.storage_meta.persist_handler import persist_video_output_handler
from controlplane.application.storage_meta.reconciliation import CloudObjectObservation
from controlplane.domain.storage_meta.verification import IntegrityObservation
from controlplane.infrastructure.db.storage_meta import (
    PostgresStorageMetaRepository,
)
from controlplane.infrastructure.storage.drive_object_store import (
    DriveObjectStore,
    DriveStoreConfig,
)

OUTPUT_NAMESPACE = 'output'


class InMemoryCloudObjectStore:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[str, int]] = {}
        self._counter: int = 0

    def reserve_object_id(self, namespace_ref: str) -> str:
        self._counter += 1
        return f'memory-{namespace_ref}-{self._counter}'

    def upload(
        self,
        object_id: str,
        artifact_version_id: str,
        content_sha256: str,
        size_bytes: int,
    ) -> None:
        if object_id in self._objects:
            raise ObjectAlreadyExistsError(object_id)
        self._objects[object_id] = (content_sha256, size_bytes)

    def lookup(self, object_id: str) -> IntegrityObservation:
        if object_id in self._objects:
            sha, size = self._objects[object_id]
            return IntegrityObservation(True, sha, size, 'memory:' + object_id)
        return IntegrityObservation(False, None, None, None)


@dataclass(frozen=True)
class StorageServices:
    mode: str
    manager: Any
    cloud_store: Any
    meta_repository_factory: Any


def build_storage_services(manager: Any, config: WiringConfig) -> StorageServices:
    if config.mode != PROFILE_PRODUCTION:
        return StorageServices(config.mode, manager, InMemoryCloudObjectStore(), None)

    profile, runtime = config.production_parts()
    d = profile.drive
    drive_config = DriveStoreConfig(
        chunk_bytes=d.chunk_bytes,
        chunk_timeout_seconds=d.chunk_timeout_seconds,
        retry_max_attempts=d.retry.max_attempts,
        retry_backoff_base_seconds=d.retry.backoff_base_seconds,
        retry_backoff_cap_seconds=d.retry.backoff_max_seconds,
        session_ttl_seconds=d.session_ttl_seconds,
        quota_reserve_ratio=d.quota_reserve_ratio,
        placement=dict(runtime.drive_placement),
        fallback_parent_id=runtime.drive_fallback_parent_id,
    )
    store = DriveObjectStore(drive_config, runtime.drive_token_broker, runtime.artifact_source)
    meta_repository_factory = partial(PostgresStorageMetaRepository, workspace_id=config.workspace_id)
    return StorageServices('production', manager, store, meta_repository_factory)


def _cloud_observer(cloud: Any) -> Callable[[str], CloudObjectObservation | None]:
    def observe(provider_object_ref: str) -> CloudObjectObservation | None:
        found = cloud.lookup(provider_object_ref)
        if found.object_present is None:
            raise RuntimeError('CLOUD_LOOKUP_UNKNOWN')
        if not found.object_present:
            return None
        return CloudObjectObservation(provider_object_ref, found.observed_sha256, found.observed_size_bytes)

    return observe


def storage_activity_services(
    services: StorageServices,
    *,
    transactions: Any,
    workspace_id: str,
    staging_root: Path,
    namespace_ref: str = OUTPUT_NAMESPACE,
) -> dict[str, Callable[..., Any]]:
    if services.mode != PROFILE_PRODUCTION:
        raise ProductionProfileError('storage.mode', 'not a production profile')
    return {
        'MaterializeArtifactSet': materialize_artifact_set_handler(transactions, workspace_id=workspace_id, staging_root=staging_root),
        'PersistVideoOutput': persist_video_output_handler(
            transactions, workspace_id=workspace_id, staging_root=staging_root, cloud=services.cloud_store, namespace_ref=namespace_ref
        ),
        'RequestCleanupEvaluation': request_cleanup_evaluation_handler(transactions, workspace_id=workspace_id),
        'ReconcileStorage': reconcile_storage_handler(transactions, workspace_id=workspace_id, observe=_cloud_observer(services.cloud_store)),
    }


__all__ = ['InMemoryCloudObjectStore', 'OUTPUT_NAMESPACE', 'StorageServices', 'build_storage_services', 'storage_activity_services']
