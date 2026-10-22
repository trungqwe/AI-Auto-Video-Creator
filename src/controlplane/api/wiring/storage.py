from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ I (storage).
Đấu nối DriveObjectStore và PostgresStorageMetaRepository.
Không gọi Google lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from controlplane.application.storage_meta.cloud_persist import (
    ObjectAlreadyExistsError,
)
from controlplane.domain.storage_meta.verification import IntegrityObservation
from controlplane.infrastructure.db.storage_meta import (
    PostgresStorageMetaRepository,
)
from controlplane.infrastructure.storage.drive_object_store import (
    DriveObjectStore,
    DriveStoreConfig,
)


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


__all__ = ['InMemoryCloudObjectStore', 'StorageServices', 'build_storage_services']
