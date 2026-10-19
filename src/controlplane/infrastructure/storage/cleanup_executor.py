"""Thực thi cleanup local có fencing: chỉ unlink tệp thường đã xác thực (CT-STO-008, ADR-0010, INV-011)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from controlplane.application.storage_meta.cleanup_evaluation import check_cleanup_authorization
from controlplane.domain.storage_meta import ArtifactLocation, CleanupAuthorization
from controlplane.infrastructure.storage.staging_paths import StagingPathError, resolve_staging_path

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class CleanupResult:
    deleted: bool
    reason_codes: tuple[str, ...]


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


class LocalCleanupExecutor:
    def __init__(self, staging_root: Path) -> None:
        self._staging_root = Path(staging_root)

    def execute(
        self,
        authorization: CleanupAuthorization,
        location: ArtifactLocation,
        relative_path: str,
        current_recovery_epoch: str,
        now: datetime,
        active_lease: bool,
    ) -> CleanupResult:
        try:
            target = resolve_staging_path(self._staging_root, relative_path)
        except StagingPathError:
            return CleanupResult(False, ("PATH_OUTSIDE_STAGING",))

        allowed, reasons = check_cleanup_authorization(
            authorization,
            location,
            current_recovery_epoch,
            now,
            path_within_staging=True,
            active_lease=active_lease,
        )
        if not allowed:
            return CleanupResult(False, reasons)

        if not target.is_file():
            return CleanupResult(False, ("NOT_A_FILE",))

        try:
            digest = _sha256_of(target)
        except OSError:
            return CleanupResult(False, ("HASH_MISMATCH",))
        if digest != authorization.artifact_hash:
            return CleanupResult(False, ("HASH_MISMATCH",))

        try:
            target.unlink()
        except OSError:
            return CleanupResult(False, ("DELETE_FAILED",))
        return CleanupResult(True, ())


__all__ = ["CleanupResult", "LocalCleanupExecutor"]
