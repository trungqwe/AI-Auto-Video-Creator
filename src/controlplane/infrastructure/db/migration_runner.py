"""Structural M2-P1 migration-runner port; behavior is intentionally absent."""
from __future__ import annotations

from pathlib import Path


class MigrationChecksumMismatchError(RuntimeError):
    """Expected GREEN error for an applied migration checksum mismatch."""


class MigrationDiscoveryError(RuntimeError):
    """Expected GREEN error for a migration version gap or duplicate."""


class MigrationLockTimeoutError(TimeoutError):
    """Expected GREEN error when bounded advisory-lock acquisition expires."""


class MigrationMissingFileError(RuntimeError):
    """Expected GREEN error when an applied migration file is unavailable."""


class MigrationRunner:
    """Importable migration port only; it performs no database work in RED."""

    def __init__(self, dsn: str, migration_dir: Path, *, is_test_env: bool) -> None:
        self.dsn = dsn
        self.migration_dir = Path(migration_dir)
        self.is_test_env = is_test_env

    def migrate_up(self) -> None:
        raise NotImplementedError("M2-P1 RED: MigrationRunner.migrate_up is not implemented.")

    def migrate_down(self) -> None:
        raise NotImplementedError("M2-P1 RED: MigrationRunner.migrate_down is not implemented.")

    def acquire_advisory_lock(self, *, timeout_seconds: float) -> None:
        raise NotImplementedError(
            "M2-P1 RED: MigrationRunner.acquire_advisory_lock is not implemented."
        )

    def release_advisory_lock(self) -> None:
        raise NotImplementedError(
            "M2-P1 RED: MigrationRunner.release_advisory_lock is not implemented."
        )

    def validate_applied_files(self) -> None:
        raise NotImplementedError(
            "M2-P1 RED: MigrationRunner.validate_applied_files is not implemented."
        )
