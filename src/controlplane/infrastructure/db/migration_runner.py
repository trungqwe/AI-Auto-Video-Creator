"""Raw PostgreSQL migration runner for the M2-P1 foundation."""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import psycopg

from .safety import DestructiveRollbackGuard


class MigrationChecksumMismatchError(RuntimeError):
    """An applied migration no longer matches its recorded checksum."""


class MigrationDiscoveryError(RuntimeError):
    """Migration files are not strictly sequential and unique."""


class MigrationLockTimeoutError(TimeoutError):
    """The bounded session-level advisory lock could not be acquired."""


class MigrationMissingFileError(RuntimeError):
    """An applied migration file is unavailable on disk."""


_FORWARD_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
_ROLLBACK_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.rollback\.sql$")
_ADVISORY_LOCK_KEY = 0x4D325031


class MigrationRunner:
    """Apply raw SQL files under one session-level advisory lock."""

    def __init__(self, dsn: str, migration_dir: Path, *, is_test_env: bool) -> None:
        self.dsn = dsn
        self.migration_dir = Path(migration_dir)
        self.is_test_env = is_test_env
        self._lock_connection: psycopg.Connection | None = None
        self._lock_held = False

    def _discover(self) -> list[tuple[int, str, Path]]:
        migrations: list[tuple[int, str, Path]] = []
        for path in self.migration_dir.iterdir():
            if not path.is_file():
                continue
            match = _FORWARD_RE.fullmatch(path.name)
            if match is None:
                if path.suffix == ".sql" and _ROLLBACK_RE.fullmatch(path.name) is None:
                    raise MigrationDiscoveryError(f"Invalid migration filename: {path.name}")
                continue
            migrations.append((int(match.group(1)), match.group(2), path))
        migrations.sort(key=lambda item: item[0])
        versions = [item[0] for item in migrations]
        if len(versions) != len(set(versions)):
            raise MigrationDiscoveryError("Duplicate migration version detected")
        expected = list(range(1, len(versions) + 1))
        if versions != expected:
            raise MigrationDiscoveryError(
                f"Migration versions must be sequential from 1; observed {versions}"
            )
        return migrations

    def _discover_rollbacks(self) -> dict[int, Path]:
        rollbacks: dict[int, Path] = {}
        for path in self.migration_dir.iterdir():
            if not path.is_file():
                continue
            match = _ROLLBACK_RE.fullmatch(path.name)
            if match is None:
                continue
            version = int(match.group(1))
            if version in rollbacks:
                raise MigrationDiscoveryError(f"Duplicate rollback version detected: {version}")
            rollbacks[version] = path
        return rollbacks

    @staticmethod
    def _checksum(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _tracking_exists(connection: psycopg.Connection) -> bool:
        return connection.execute(
            "SELECT to_regclass('controlplane.cp_schema_migrations')"
        ).fetchone()[0] is not None

    def _applied(self, connection: psycopg.Connection) -> dict[int, tuple[str, str]]:
        if not self._tracking_exists(connection):
            return {}
        rows = connection.execute(
            "SELECT version, name, checksum_sha256 "
            "FROM controlplane.cp_schema_migrations ORDER BY version"
        ).fetchall()
        return {int(version): (str(name), str(checksum)) for version, name, checksum in rows}

    def acquire_advisory_lock(self, *, timeout_seconds: float) -> None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        if self._lock_held:
            return
        connection = psycopg.connect(self.dsn, autocommit=True)
        deadline = time.monotonic() + timeout_seconds
        try:
            while True:
                acquired = connection.execute(
                    "SELECT pg_try_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,)
                ).fetchone()[0]
                if acquired:
                    self._lock_connection = connection
                    self._lock_held = True
                    return
                if time.monotonic() >= deadline:
                    raise MigrationLockTimeoutError(
                        f"Could not acquire migration advisory lock within {timeout_seconds:.3f}s"
                    )
                time.sleep(min(0.01, max(0.001, deadline - time.monotonic())))
        except Exception:
            connection.close()
            raise

    def release_advisory_lock(self) -> None:
        connection = self._lock_connection
        self._lock_connection = None
        self._lock_held = False
        if connection is None or connection.closed:
            return
        try:
            connection.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))
        finally:
            connection.close()

    def _apply_one(
        self,
        connection: psycopg.Connection,
        version: int,
        name: str,
        path: Path,
    ) -> None:
        checksum = self._checksum(path)
        started = time.perf_counter()
        with connection.transaction():
            connection.execute(path.read_text(encoding="utf-8"))
            if not self._tracking_exists(connection):
                connection.execute("CREATE SCHEMA IF NOT EXISTS controlplane")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS controlplane.cp_schema_migrations ("
                    "version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
                    "checksum_sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "execution_ms DOUBLE PRECISION NOT NULL)"
                )
            execution_ms = (time.perf_counter() - started) * 1000
            connection.execute(
                "INSERT INTO controlplane.cp_schema_migrations "
                "(version, name, checksum_sha256, execution_ms) VALUES (%s, %s, %s, %s)",
                (version, name, checksum, execution_ms),
            )

    def _require_lock_connection(self) -> psycopg.Connection:
        if self._lock_connection is None or not self._lock_held:
            raise RuntimeError("Migration advisory lock is not held")
        return self._lock_connection

    def migrate_up(self) -> None:
        migrations = self._discover()
        self.acquire_advisory_lock(timeout_seconds=5.0)
        try:
            connection = self._require_lock_connection()
            applied = self._applied(connection)
            by_version = {version: (name, path) for version, name, path in migrations}
            for version, (applied_name, applied_checksum) in applied.items():
                current = by_version.get(version)
                if current is None:
                    raise MigrationMissingFileError(
                        f"Applied migration file is missing for version {version}"
                    )
                current_name, current_path = current
                if current_name != applied_name or self._checksum(current_path) != applied_checksum:
                    raise MigrationChecksumMismatchError(
                        f"Migration checksum mismatch for version {version}"
                    )
            for version, name, path in migrations:
                if version not in applied:
                    self._apply_one(connection, version, name, path)
                    applied[version] = (name, self._checksum(path))
        finally:
            self.release_advisory_lock()

    def migrate_down(self) -> None:
        with psycopg.connect(self.dsn, autocommit=True) as connection:
            database_name = connection.execute("SELECT current_database()").fetchone()[0]
        DestructiveRollbackGuard().assert_allowed(database_name, is_test_env=self.is_test_env)
        self._discover()
        rollbacks = self._discover_rollbacks()
        self.acquire_advisory_lock(timeout_seconds=5.0)
        try:
            connection = self._require_lock_connection()
            applied = self._applied(connection)
            for version in sorted(applied, reverse=True):
                rollback = rollbacks.get(version)
                if rollback is None:
                    raise MigrationDiscoveryError(f"Missing rollback migration for version {version}")
                with connection.transaction():
                    connection.execute(rollback.read_text(encoding="utf-8"))
                    if self._tracking_exists(connection):
                        connection.execute(
                            "DELETE FROM controlplane.cp_schema_migrations WHERE version = %s",
                            (version,),
                        )
        finally:
            self.release_advisory_lock()

    def validate_applied_files(self) -> None:
        self.acquire_advisory_lock(timeout_seconds=5.0)
        try:
            connection = self._require_lock_connection()
            applied = self._applied(connection)
            discovered = {version: (name, path) for version, name, path in self._discover()}
            for version, (name, checksum) in applied.items():
                current = discovered.get(version)
                if current is None:
                    raise MigrationMissingFileError(
                        f"Applied migration file is missing for version {version}"
                    )
                current_name, current_path = current
                if name != current_name or checksum != self._checksum(current_path):
                    raise MigrationChecksumMismatchError(
                        f"Migration checksum mismatch for version {version}"
                    )
        finally:
            self.release_advisory_lock()
