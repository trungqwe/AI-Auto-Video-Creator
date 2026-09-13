"""Mandatory Behavioral RED oracles for M2-P1 PostgreSQL foundation.

Each oracle intentionally describes its required GREEN behavior.  During the
authorized RED phase, the corresponding structural port is expected to raise
``NotImplementedError`` until a later, separately authorized implementation
phase.  The fixtures are real PostgreSQL fixtures: they never fall back to a
local credential or a mock database.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.identity.ports import (
    ActorUseCases,
    AuthSessionUseCases,
    WorkspaceUseCases,
)
from controlplane.infrastructure.db.migration_runner import (
    MigrationChecksumMismatchError,
    MigrationDiscoveryError,
    MigrationLockTimeoutError,
    MigrationMissingFileError,
    MigrationRunner,
)
from controlplane.infrastructure.db.safety import (
    DestructiveOperationBlockedError,
    DestructiveRollbackGuard,
)
from controlplane.infrastructure.db.uow import TransactionManager


REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_MIGRATIONS = (
    REPO_ROOT / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
)
TEST_DATABASE_NAME = re.compile(r"^m2_p1_test_[0-9a-f]+$")


@dataclass
class DisposableDatabase:
    """Test-owned target database; connections are closed before admin teardown."""

    name: str
    dsn: str
    _target_connections: list[psycopg.Connection] = field(default_factory=list)

    def connect(self) -> psycopg.Connection:
        connection = psycopg.connect(self.dsn)
        self._target_connections.append(connection)
        return connection

    def close_target_connections(self) -> None:
        for connection in self._target_connections:
            if not connection.closed:
                connection.close()


def _production_tree_digest(root: Path) -> str:
    """Return a deterministic content digest without changing production files."""
    digest = hashlib.sha256()
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            digest.update(entry.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(entry.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _write_sandbox_migration(sandbox: Path, name: str, content: str) -> Path:
    """Create a test-only migration fixture inside the temporary sandbox."""
    path = sandbox / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def disposable_db() -> Iterator[DisposableDatabase]:
    """Create one exact-name PostgreSQL database per test run using only M2_TEST_PG_DSN."""
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail(
            "BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required for M2-P1 integration RED; "
            "no fallback credential or mock database is permitted."
        )

    database_name = f"m2_p1_test_{uuid.uuid4().hex}"
    assert TEST_DATABASE_NAME.fullmatch(database_name), "Fixture database identity must be exact."

    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin_connection:
            with admin_connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), rolcreatedb FROM pg_roles WHERE rolname = current_user")
                admin_database, can_create_database = cursor.fetchone()
                if not can_create_database:
                    pytest.fail(
                        "BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB for the disposable database."
                    )
                assert admin_database != database_name
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    except pytest.fail.Exception:
        raise
    except Exception as exc:
        pytest.fail(
            "BLOCKED_EXTERNAL: PostgreSQL disposable-database prerequisite failed "
            f"({type(exc).__name__}); DSN value is intentionally redacted."
        )

    target_dsn = make_conninfo(admin_dsn, dbname=database_name)
    database = DisposableDatabase(name=database_name, dsn=target_dsn)
    try:
        with database.connect() as target_connection:
            with target_connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                assert cursor.fetchone()[0] == database_name
        yield database
    finally:
        database.close_target_connections()
        try:
            with psycopg.connect(admin_dsn, autocommit=True) as admin_connection:
                with admin_connection.cursor() as cursor:
                    # The admin session must not be connected to the target database.
                    cursor.execute("SELECT current_database()")
                    assert cursor.fetchone()[0] != database_name
                    assert TEST_DATABASE_NAME.fullmatch(database_name)
                    cursor.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = %s AND pid <> pg_backend_pid()",
                        (database_name,),
                    )
                    cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
        except Exception as exc:
            pytest.fail(
                "BLOCKED_EXTERNAL: disposable PostgreSQL teardown failed "
                f"({type(exc).__name__}); target name was fixture-verified."
            )


@pytest.fixture
def migration_sandbox(tmp_path: Path) -> Iterator[Path]:
    """Copy migrations before fault injection and prove the production tree is unchanged."""
    assert PRODUCTION_MIGRATIONS.is_dir(), "Structural migration source must exist before RED."
    before = _production_tree_digest(PRODUCTION_MIGRATIONS)
    sandbox = tmp_path / "migration-sandbox"
    shutil.copytree(PRODUCTION_MIGRATIONS, sandbox)
    try:
        yield sandbox
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        assert _production_tree_digest(PRODUCTION_MIGRATIONS) == before, (
            "Production migration source changed during a sandbox-only fault test."
        )


def test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db(
    disposable_db: DisposableDatabase,
) -> None:
    """ARCH-002, ADR-0002: up/down/up must use the fixture-created database only."""
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)

    runner.migrate_up()
    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace('controlplane')")
            assert cursor.fetchone()[0] == "controlplane"

    runner.migrate_down()
    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace('controlplane')")
            assert cursor.fetchone()[0] is None

    runner.migrate_up()


def test_tst_m2_p1_002_migration_checksum_tamper_rejected(
    disposable_db: DisposableDatabase, migration_sandbox: Path
) -> None:
    """ADR-0002, QR-MNT-002: byte-level migration tampering must fail closed."""
    forward_file = _write_sandbox_migration(
        migration_sandbox, "0001_initial_controlplane.sql", "SELECT 1;\n"
    )
    runner = MigrationRunner(disposable_db.dsn, migration_sandbox, is_test_env=True)

    runner.migrate_up()
    forward_file.write_text("SELECT 2;\n", encoding="utf-8")
    with pytest.raises(MigrationChecksumMismatchError):
        runner.migrate_up()


def test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected(
    disposable_db: DisposableDatabase, migration_sandbox: Path
) -> None:
    """ADR-0002, QR-MNT-002: discovery rejects both version gaps and duplicates."""
    _write_sandbox_migration(migration_sandbox, "0001_initial_controlplane.sql", "SELECT 1;\n")
    _write_sandbox_migration(migration_sandbox, "0003_gap.sql", "SELECT 1;\n")
    runner = MigrationRunner(disposable_db.dsn, migration_sandbox, is_test_env=True)

    with pytest.raises(MigrationDiscoveryError):
        runner.migrate_up()

    (migration_sandbox / "0003_gap.sql").unlink()
    _write_sandbox_migration(migration_sandbox, "0001_duplicate.sql", "SELECT 1;\n")
    with pytest.raises(MigrationDiscoveryError):
        runner.migrate_up()


def test_tst_m2_p1_004_bounded_advisory_lock_and_timeout(
    disposable_db: DisposableDatabase,
) -> None:
    """ADR-0002, QR-MNT-002: a second runner must time out under a held lock."""
    first_runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)
    second_runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)

    first_runner.acquire_advisory_lock(timeout_seconds=5.0)
    with pytest.raises(MigrationLockTimeoutError):
        second_runner.acquire_advisory_lock(timeout_seconds=0.1)
    first_runner.release_advisory_lock()


def test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback(
    disposable_db: DisposableDatabase,
) -> None:
    """ARCH-002, QR-MNT-002: one failed UoW leaves no partial identity records."""
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)
    runner.migrate_up()
    manager = TransactionManager(disposable_db.dsn)

    with pytest.raises(RuntimeError, match="force rollback"):
        with manager.unit_of_work() as unit_of_work:
            unit_of_work.workspaces.create("workspace-a", "Workspace A", "active")
            unit_of_work.actors.create("workspace-a", "actor-a", "human", "Actor A", "active")
            unit_of_work.auth_sessions.create("workspace-a", "actor-a", "session-a", "active")
            raise RuntimeError("force rollback")

    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM controlplane.cp_workspaces")
            assert cursor.fetchone()[0] == 0
            assert connection.info.transaction_status.name == "IDLE"


def test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement(
    disposable_db: DisposableDatabase,
) -> None:
    """ADR-0002, CT-API-001: a session may not bind an actor from another workspace."""
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)
    runner.migrate_up()

    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES "
                "('00000000-0000-0000-0000-000000000001', 'A', 'active'), "
                "('00000000-0000-0000-0000-000000000002', 'B', 'active')"
            )
            cursor.execute(
                "INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) "
                "VALUES ('00000000-0000-0000-0000-000000000010', "
                "'00000000-0000-0000-0000-000000000001', 'human', 'Actor', 'active')"
            )
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                cursor.execute(
                    "INSERT INTO controlplane.cp_auth_sessions "
                    "(session_id, workspace_id, actor_id, status) VALUES "
                    "('00000000-0000-0000-0000-000000000020', "
                    "'00000000-0000-0000-0000-000000000002', "
                    "'00000000-0000-0000-0000-000000000010', 'active')"
                )


def test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented(
    disposable_db: DisposableDatabase,
) -> None:
    """CT-API-001/010, ADR-0009: scoped reads/status/revoke/expire reveal no foreign data."""
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)
    runner.migrate_up()
    workspace_port = WorkspaceUseCases(disposable_db.dsn)
    actor_port = ActorUseCases(disposable_db.dsn)
    session_port = AuthSessionUseCases(disposable_db.dsn)

    assert workspace_port.get("workspace-a", "workspace-b") is None
    assert workspace_port.list("workspace-a") == []
    assert workspace_port.update_status("workspace-a", "workspace-b", "suspended") is None
    assert actor_port.get("workspace-a", "actor-b") is None
    assert actor_port.list("workspace-a") == []
    assert actor_port.update_status("workspace-a", "actor-b", "suspended") is None
    assert session_port.revoke("workspace-a", "session-b") is None
    assert session_port.expire("workspace-a", "session-b") is None


def test_tst_m2_p1_008_destructive_guard_rejects_non_test_db() -> None:
    """ADR-0002, QR-MNT-002: destructive rollback accepts only exact fixture identity."""
    guard = DestructiveRollbackGuard()

    with pytest.raises(DestructiveOperationBlockedError):
        guard.assert_allowed("controlplane", is_test_env=True)
    with pytest.raises(DestructiveOperationBlockedError):
        guard.assert_allowed("m2_p1_test_deadbeef", is_test_env=False)


def test_tst_m2_p1_009_applied_migration_file_missing_rejected(
    disposable_db: DisposableDatabase, migration_sandbox: Path
) -> None:
    """ADR-0002, QR-MNT-002: deletion of an applied sandbox file must fail closed."""
    forward_file = _write_sandbox_migration(
        migration_sandbox, "0001_initial_controlplane.sql", "SELECT 1;\n"
    )
    runner = MigrationRunner(disposable_db.dsn, migration_sandbox, is_test_env=True)

    runner.migrate_up()
    forward_file.unlink()
    with pytest.raises(MigrationMissingFileError):
        runner.validate_applied_files()


def test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record(
    disposable_db: DisposableDatabase, migration_sandbox: Path
) -> None:
    """ADR-0002, QR-MNT-002: broken sandbox SQL leaves no side effect or applied row."""
    _write_sandbox_migration(
        migration_sandbox,
        "0001_broken.sql",
        "CREATE SCHEMA controlplane;\nTHIS IS INTENTIONALLY BROKEN SQL;\n",
    )
    runner = MigrationRunner(disposable_db.dsn, migration_sandbox, is_test_env=True)

    with pytest.raises(psycopg.Error):
        runner.migrate_up()

    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace('controlplane')")
            assert cursor.fetchone()[0] is None


def test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool(
    disposable_db: DisposableDatabase,
) -> None:
    """ARCH-002, QR-MNT-002: a borrower after rollback receives a clean connection."""
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True)
    runner.migrate_up()
    manager = TransactionManager(disposable_db.dsn)

    with pytest.raises(RuntimeError, match="force rollback"):
        with manager.unit_of_work() as unit_of_work:
            unit_of_work.workspaces.create("workspace-a", "Workspace A", "active")
            raise RuntimeError("force rollback")

    with manager.borrow_connection() as borrower:
        with borrower.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
        assert borrower.info.transaction_status.name == "IDLE"
