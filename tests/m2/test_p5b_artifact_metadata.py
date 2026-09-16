"""Exact five M2-P5B behavioral RED oracles; no P5B implementation exists."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.artifact_metadata import (
    ArtifactLocationStore,
    ArtifactVersionStore,
    CleanupAuthorizationStore,
)
from controlplane.domain.artifact_metadata import ArtifactLocation, ArtifactVersion, CleanupAuthorization
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ArtifactLocationState, ForbiddenTransitionError
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager


REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_MIGRATIONS = REPO_ROOT / "src/controlplane/infrastructure/db/migrations"
TEST_DATABASE_NAME = re.compile(r"^m2_p5b_test_[0-9a-f]+$")
WORKSPACE_A = "00000000-0000-0000-0000-0000000005b1"
WORKSPACE_B = "00000000-0000-0000-0000-0000000005b2"
HASH_A = "a" * 64
HASH_B = "b" * 64


@dataclass
class DisposableDatabase:
    name: str
    dsn: str = field(repr=False)


@contextmanager
def _disposable_database(migration_dir: Path) -> Iterator[DisposableDatabase]:
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted")
    name = f"m2_p5b_test_{uuid.uuid4().hex}"
    assert TEST_DATABASE_NAME.fullmatch(name)
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            if not admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0]:
                pytest.fail("BLOCKED_EXTERNAL: M2 PostgreSQL role lacks CREATEDB")
            version = admin.execute("SHOW server_version").fetchone()[0].split()[0]
            assert version == "18.6"
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except pytest.fail.Exception:
        raise
    except Exception as exc:
        pytest.fail(f"BLOCKED_EXTERNAL: PostgreSQL prerequisite failed ({type(exc).__name__}); DSN redacted")
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, migration_dir, is_test_env=True).migrate_up()
        yield DisposableDatabase(name=name, dsn=dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            assert TEST_DATABASE_NAME.fullmatch(name)
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (name,)).fetchone()[0] == 0


@pytest.fixture
def p5b_database() -> Iterator[DisposableDatabase]:
    with _disposable_database(PRODUCTION_MIGRATIONS) as database:
        with psycopg.connect(database.dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES "
                "(%s, 'P5B A', 'ACTIVE'), (%s, 'P5B B', 'ACTIVE')",
                (WORKSPACE_A, WORKSPACE_B),
            )
            connection.commit()
        yield database


@pytest.fixture
def p5b_migration_baseline() -> Iterator[tuple[DisposableDatabase, Path]]:
    with tempfile.TemporaryDirectory(prefix="m2_p5b_migration_baseline_") as temporary:
        sandbox = Path(temporary)
        for version in range(1, 5):
            forward = next(path for path in PRODUCTION_MIGRATIONS.glob(f"{version:04d}_*.sql") if not path.name.endswith(".rollback.sql"))
            rollback = next(PRODUCTION_MIGRATIONS.glob(f"{version:04d}_*.rollback.sql"))
            shutil.copy2(forward, sandbox / forward.name)
            shutil.copy2(rollback, sandbox / rollback.name)
        with _disposable_database(sandbox) as database:
            yield database, sandbox


@contextmanager
def _manager(dsn: str) -> Iterator[TransactionManager]:
    manager = TransactionManager(dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


def _version_input(hash_value: str = HASH_A) -> dict[str, object]:
    return {
        "workspace_id": WORKSPACE_A,
        "artifact_id": "artifact-5b",
        "sha256_hash": hash_value,
        "size_bytes": 128,
        "mime_type": "video/mp4",
        "artifact_kind": "rendered_video",
        "owner_ref": "owner-5b",
        "lineage_ref": "lineage-5b",
        "retention_ref": "retention-5b",
        "sensitivity_ref": "internal",
    }


def _location_input(artifact_version_id: str) -> dict[str, object]:
    return {
        "workspace_id": WORKSPACE_A,
        "artifact_version_id": artifact_version_id,
        "backend_ref": "cloud-object-store",
        "provider_namespace_ref": "provider-account-ref",
        "provider_object_ref": "opaque-object-ref",
        "logical_locator": "render/output",
    }


def _artifact_version_fixture() -> ArtifactVersion:
    return ArtifactVersion(
        workspace_id=WORKSPACE_A,
        artifact_id="artifact-5b",
        artifact_version_id="00000000-0000-0000-0000-000000005b01",
        sha256_hash=HASH_A,
        size_bytes=128,
        mime_type="video/mp4",
        artifact_kind="rendered_video",
        owner_ref="owner-5b",
        lineage_ref="lineage-5b",
        retention_ref="retention-5b",
        sensitivity_ref="internal",
        created_at="2026-09-16T00:00:00Z",
    )


def _artifact_location_fixture(state: ArtifactLocationState = ArtifactLocationState.DECLARED, revision: int = 1) -> ArtifactLocation:
    return ArtifactLocation(
        workspace_id=WORKSPACE_A,
        location_id="00000000-0000-0000-0000-000000005b02",
        artifact_version_id=_artifact_version_fixture().artifact_version_id,
        backend_ref="cloud-object-store",
        provider_namespace_ref="provider-account-ref",
        provider_object_ref="opaque-object-ref",
        logical_locator="render/output",
        observed_hash=None,
        observed_size_bytes=None,
        provider_metadata_revision=None,
        verification_evidence_ref=None,
        state=state,
        revision=revision,
        created_at="2026-09-16T00:00:00Z",
        updated_at="2026-09-16T00:00:00Z",
    )


def test_tst_m2_p5b_001_artifact_version_registration_and_hash_integrity(p5b_database: DisposableDatabase) -> None:
    store = ArtifactVersionStore()
    with _manager(p5b_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            first = store.register(**_version_input(), connection=uow.connection)
        assert isinstance(first, ArtifactVersion)
        assert first.sha256_hash == HASH_A and first.size_bytes == 128 and first.mime_type == "video/mp4"
        immutable_before = tuple(getattr(first, field.name) for field in fields(first))
        with manager.unit_of_work() as uow:
            persisted = store.get_scoped(workspace_id=WORKSPACE_A, artifact_version_id=first.artifact_version_id, connection=uow.connection)
        assert tuple(getattr(persisted, field.name) for field in fields(persisted)) == immutable_before
        assert not hasattr(store, "update") and not hasattr(store, "overwrite")
        with manager.unit_of_work() as uow:
            reused = store.register(**_version_input(), connection=uow.connection)
        assert reused.artifact_version_id == first.artifact_version_id
        with manager.unit_of_work() as uow:
            changed = store.register(**_version_input(HASH_B), connection=uow.connection)
        assert changed.artifact_version_id != first.artifact_version_id and changed.sha256_hash == HASH_B
        assert tuple(getattr(first, field.name) for field in fields(first)) == immutable_before
        for overrides in ({"sha256_hash": "not-a-sha256"}, {"size_bytes": 0}, {"size_bytes": -1}, {"mime_type": ""}):
            with manager.unit_of_work() as uow:
                with pytest.raises(ValueError) as rejected:
                    store.register(**{**_version_input(), **overrides}, connection=uow.connection)
            assert getattr(rejected.value, "code", "VALIDATION_ERROR") == "VALIDATION_ERROR"


def test_tst_m2_p5b_002_location_state_lifecycle_and_verification(p5b_database: DisposableDatabase) -> None:
    location_store = ArtifactLocationStore()
    version = _artifact_version_fixture()
    with _manager(p5b_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            location = location_store.declare(**_location_input(version.artifact_version_id), connection=uow.connection)
        assert isinstance(location, ArtifactLocation)
        assert location.state is ArtifactLocationState.DECLARED and location.revision == 1
        unsafe_locators = ("../escape", "/outside/staging", "C:\\outside\\staging", "file:///outside", "https://example.test/object?signature=redacted", "; remove-item")
        for unsafe_locator in unsafe_locators:
            with manager.unit_of_work() as uow:
                with pytest.raises(ValueError) as unsafe:
                    location_store.declare(**{**_location_input(version.artifact_version_id), "logical_locator": unsafe_locator}, connection=uow.connection)
            assert getattr(unsafe.value, "code", "VALIDATION_ERROR") == "VALIDATION_ERROR"
        for requested in (
            ArtifactLocationState.MATERIALIZING,
            ArtifactLocationState.AVAILABLE_UNVERIFIED,
            ArtifactLocationState.VERIFYING,
            ArtifactLocationState.VERIFIED,
        ):
            with manager.unit_of_work() as uow:
                location = location_store.transition(
                    workspace_id=WORKSPACE_A,
                    location_id=location.location_id,
                    expected_revision=location.revision,
                    requested_state=requested,
                    verification_evidence_ref="verify-5b" if requested is ArtifactLocationState.VERIFIED else None,
                    connection=uow.connection,
                )
        assert location.state is ArtifactLocationState.VERIFIED and location.revision == 5
        with manager.unit_of_work() as uow:
            missing = location_store.transition(workspace_id=WORKSPACE_A, location_id=location.location_id, expected_revision=5, requested_state=ArtifactLocationState.MISSING, verification_evidence_ref="absence-5b", connection=uow.connection)
        assert missing.state is ArtifactLocationState.MISSING
        for terminal in (ArtifactLocationState.MISSING, ArtifactLocationState.CORRUPT, ArtifactLocationState.OUTCOME_UNKNOWN):
            with pytest.raises(ForbiddenTransitionError):
                location_store.validate_transition(current_state=terminal, current_revision=1, expected_revision=1, requested_state=ArtifactLocationState.VERIFYING)
        with pytest.raises(ForbiddenTransitionError):
            location_store.validate_transition(current_state=ArtifactLocationState.VERIFIED, current_revision=5, expected_revision=5, requested_state=ArtifactLocationState.CLEANUP_AUTHORIZED)
        assert not hasattr(location_store, "delete") and missing.state is not ArtifactLocationState.DELETED


def test_tst_m2_p5b_003_cleanup_authorization_requires_verified_location(p5b_database: DisposableDatabase) -> None:
    location_store = ArtifactLocationStore()
    authorization_store = CleanupAuthorizationStore()
    now = datetime.now(timezone.utc)
    version = _artifact_version_fixture()
    location = _artifact_location_fixture()
    with _manager(p5b_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            with pytest.raises((ForbiddenTransitionError, ValueError)):
                authorization_store.authorize(workspace_id=WORKSPACE_A, location_id=location.location_id, expected_revision=1, recovery_epoch=7, current_recovery_epoch=7, connection=uow.connection)
        with manager.unit_of_work() as uow:
            location = location_store.declare(**_location_input(version.artifact_version_id), connection=uow.connection)
        for requested in (ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING, ArtifactLocationState.VERIFIED, ArtifactLocationState.CLEANUP_ELIGIBLE):
            with manager.unit_of_work() as uow:
                location = location_store.transition(workspace_id=WORKSPACE_A, location_id=location.location_id, expected_revision=location.revision, requested_state=requested, verification_evidence_ref="verify-5b", connection=uow.connection)
        authorization_input = {
            "workspace_id": WORKSPACE_A,
            "location_id": location.location_id,
            "artifact_version_id": version.artifact_version_id,
            "artifact_hash": HASH_A,
            "reason": "retention-complete",
            "policy_revision": "policy-r7",
            "completion_evidence_ref": "completion-5b",
            "verification_evidence_ref": "verify-5b",
            "issued_at": now,
            "expires_at": now + timedelta(hours=1),
            "recovery_epoch": 7,
            "current_recovery_epoch": 7,
            "authorizing_owner_ref": "owner-5b",
            "actor_ref": "actor-5b",
            "audit_ref": "audit-5b",
            "correlation_ref": "correlation-5b",
        }
        with manager.unit_of_work() as uow:
            authorization = authorization_store.authorize(**authorization_input, expected_revision=location.revision, connection=uow.connection)
        assert isinstance(authorization, CleanupAuthorization)
        assert authorization.location_id == location.location_id and authorization.artifact_hash == HASH_A
        assert "status" not in {field.name for field in fields(authorization)}
        with manager.unit_of_work() as uow:
            persisted = location_store.get_scoped(workspace_id=WORKSPACE_A, location_id=location.location_id, connection=uow.connection)
        assert persisted.state is ArtifactLocationState.CLEANUP_AUTHORIZED and persisted.state is not ArtifactLocationState.DELETED
        with manager.unit_of_work() as uow:
            with pytest.raises((RevisionConflictError, ValueError)):
                authorization_store.authorize(**{**authorization_input, "recovery_epoch": 6}, expected_revision=persisted.revision, connection=uow.connection)
        assert authorization_store.is_expired(authorization=authorization, evaluated_at=now) is False
        assert authorization_store.is_expired(authorization=authorization, evaluated_at=now + timedelta(hours=2)) is True
        assert not hasattr(location_store, "delete") and not hasattr(authorization_store, "revoke")
        assert not hasattr(authorization_store, "emit_cleanup_completed")
        with manager.unit_of_work() as uow:
            cleanup_completed = uow.connection.execute("SELECT count(*) FROM controlplane.cp_outbox_events WHERE workspace_id=%s AND event_name='CleanupCompleted'", (WORKSPACE_A,)).fetchone()[0]
        assert cleanup_completed == 0


def test_tst_m2_p5b_004_production_0005_forward_rollback_and_constraints(p5b_migration_baseline: tuple[DisposableDatabase, Path]) -> None:
    database, sandbox = p5b_migration_baseline
    forward = PRODUCTION_MIGRATIONS / "0005_artifact_metadata.sql"
    rollback = PRODUCTION_MIGRATIONS / "0005_artifact_metadata.rollback.sql"
    assert forward.is_file() and rollback.is_file(), "P5B-004 requires missing production migration 0005 and exact rollback"
    shutil.copy2(forward, sandbox / forward.name)
    shutil.copy2(rollback, sandbox / rollback.name)
    MigrationRunner(database.dsn, sandbox, is_test_env=True).migrate_up()
    with psycopg.connect(database.dsn, autocommit=True) as connection:
        assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,), (4,), (5,)]
        tables = {row[0] for row in connection.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='controlplane'").fetchall()}
        assert {"cp_artifact_versions", "cp_artifact_locations", "cp_cleanup_authorizations"} <= tables
        authorization_columns = {row[0] for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_cleanup_authorizations'").fetchall()}
        assert "status" not in authorization_columns
        unique_defs = [row[0] for row in connection.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='controlplane.cp_artifact_versions'::regclass AND contype='u'").fetchall()]
        assert any("workspace_id, artifact_id, sha256_hash" in definition for definition in unique_defs)
        with connection.transaction():
            connection.execute(rollback.read_text(encoding="utf-8"))
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=5")
        assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,), (4,)]
        assert all(connection.execute("SELECT to_regclass(%s)", (f"controlplane.{name}",)).fetchone()[0] is None for name in ("cp_artifact_versions", "cp_artifact_locations", "cp_cleanup_authorizations"))
        assert all(connection.execute("SELECT to_regclass(%s)", (f"controlplane.{name}",)).fetchone()[0] == f"controlplane.{name}" for name in ("cp_workspaces", "cp_outbox_events", "cp_config_revisions", "cp_secret_handles", "cp_schema_migrations"))


def test_tst_m2_p5b_005_workspace_isolation_and_location_revision_conflict(p5b_database: DisposableDatabase) -> None:
    location_store = ArtifactLocationStore()
    version = _artifact_version_fixture()
    assert not hasattr(location_store, "get_by_id") and not hasattr(location_store, "update_unscoped")
    with _manager(p5b_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            location = location_store.declare(**_location_input(version.artifact_version_id), connection=uow.connection)
        with manager.unit_of_work() as uow:
            assert location_store.get_scoped(workspace_id=WORKSPACE_B, location_id=location.location_id, connection=uow.connection) is None

        def transition_once() -> object:
            try:
                with manager.unit_of_work() as uow:
                    return location_store.transition(workspace_id=WORKSPACE_A, location_id=location.location_id, expected_revision=1, requested_state=ArtifactLocationState.MATERIALIZING, connection=uow.connection)
            except RevisionConflictError as conflict:
                return conflict

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: transition_once(), range(2)))
        winners = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
        losers = [outcome for outcome in outcomes if isinstance(outcome, RevisionConflictError)]
        assert len(winners) == 1 and winners[0].revision == 2
        assert len(losers) == 1 and losers[0].current_revision == 2
        with manager.unit_of_work() as uow:
            persisted = location_store.get_scoped(workspace_id=WORKSPACE_A, location_id=location.location_id, connection=uow.connection)
            foreign = location_store.get_scoped(workspace_id=WORKSPACE_B, location_id=location.location_id, connection=uow.connection)
            duplicates = uow.connection.execute("SELECT count(*) FROM controlplane.cp_artifact_locations WHERE workspace_id=%s AND location_id=%s", (WORKSPACE_A, location.location_id)).fetchone()[0]
        assert persisted.revision == 2 and persisted.state is ArtifactLocationState.MATERIALIZING
        assert foreign is None and duplicates == 1
