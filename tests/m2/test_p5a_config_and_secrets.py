"""The exact five M2-P5A behavioral RED oracles, prior to implementation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.config_security import (
    ConfigEventFactory,
    ConfigRevisionRepository,
    ConfigRevisionService,
    SecretHandleStore,
)
from controlplane.application.idempotency import canonicalize_json, request_hash
from controlplane.domain.config_security import ConfigRevisionStatus, SecretHandle
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events import ensure_safe_event_payload
from controlplane.domain.statemachine import ForbiddenTransitionError
from controlplane.infrastructure.db.migration_runner import MigrationRunner


REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_MIGRATIONS = REPO_ROOT / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
TEST_DATABASE_NAME = re.compile(r"^m2_p5a_test_[0-9a-f]+$")
WORKSPACE_A = "00000000-0000-0000-0000-0000000005a1"
WORKSPACE_B = "00000000-0000-0000-0000-0000000005a2"


@dataclass
class DisposableDatabase:
    name: str
    dsn: str = field(repr=False)
    connections: list[psycopg.Connection] = field(default_factory=list)

    def connect(self) -> psycopg.Connection:
        connection = psycopg.connect(self.dsn, autocommit=True)
        self.connections.append(connection)
        return connection


@pytest.fixture
def p5a_database() -> Iterator[DisposableDatabase]:
    """One P1--P3 production-migrated PostgreSQL database per P5A oracle."""
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.")
    name = f"m2_p5a_test_{uuid.uuid4().hex}"
    assert TEST_DATABASE_NAME.fullmatch(name)
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            createdb = admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0]
            if not createdb:
                pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except pytest.fail.Exception:
        raise
    except Exception as exc:
        pytest.fail(f"BLOCKED_EXTERNAL: PostgreSQL prerequisite failed ({type(exc).__name__}); DSN redacted.")
    database = DisposableDatabase(name=name, dsn=make_conninfo(admin_dsn, dbname=name))
    try:
        MigrationRunner(database.dsn, PRODUCTION_MIGRATIONS, is_test_env=True).migrate_up()
        yield database
    finally:
        for connection in database.connections:
            if not connection.closed:
                connection.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            assert TEST_DATABASE_NAME.fullmatch(name)
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (name,)).fetchone()[0] == 0


def _assert_p1_to_p3_prerequisites(database: DisposableDatabase) -> None:
    with database.connect() as connection:
        assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,)]
        assert connection.execute("SELECT to_regclass('controlplane.cp_outbox_events')").fetchone()[0] == "controlplane.cp_outbox_events"


def _seed_workspaces(connection: psycopg.Connection) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'P5A A', 'ACTIVE'), (%s, 'P5A B', 'ACTIVE')",
        (WORKSPACE_A, WORKSPACE_B),
    )


def _assert_immutable_identity(before: object, after: object) -> None:
    for name in ("config_revision_id", "config_revision_number", "payload", "content_hash"):
        assert getattr(after, name) == getattr(before, name)


def test_tst_m2_p5a_001_config_revision_immutability_and_hash(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    first_payload = json.loads('{ "scope": "prompt", "values": { "a": 1, "b": [true, null] } }')
    equivalent_payload = json.loads('{"values":{"b":[true,null],"a":1},"scope":"prompt"}')
    changed_payload = {"scope": "prompt", "values": {"a": 2, "b": [True, None]}}
    assert canonicalize_json(first_payload) == canonicalize_json(equivalent_payload)
    assert request_hash(first_payload) == request_hash(equivalent_payload)
    assert request_hash(first_payload) == hashlib.sha256(canonicalize_json(first_payload)).hexdigest()
    assert request_hash(first_payload) != request_hash(changed_payload)

    service = ConfigRevisionService()
    draft = service.create_revision(
        workspace_id=WORKSPACE_A,
        scope_kind="prompt",
        scope_key="primary",
        config_revision_number=1,
        payload=first_payload,
        actor_ref="actor-a",
        change_reason="initial",
    )
    assert draft.config_revision_number == 1 and draft.revision == 1 and draft.status is ConfigRevisionStatus.DRAFT
    assert draft.content_hash == request_hash(first_payload)
    published = service.transition(revision=draft, expected_revision=1, requested_status=ConfigRevisionStatus.PUBLISHED, actor_ref="actor-a")
    _assert_immutable_identity(draft, published)
    assert published.revision == 2 and published.status is ConfigRevisionStatus.PUBLISHED
    superseded = service.transition(revision=published, expected_revision=2, requested_status=ConfigRevisionStatus.SUPERSEDED, actor_ref="actor-a")
    _assert_immutable_identity(draft, superseded)
    assert superseded.revision == 3
    invalidated = service.transition(revision=superseded, expected_revision=3, requested_status=ConfigRevisionStatus.INVALIDATED, actor_ref="security-owner")
    _assert_immutable_identity(draft, invalidated)
    assert invalidated.revision == 4 and invalidated.status is ConfigRevisionStatus.INVALIDATED
    for current, target in ((draft, ConfigRevisionStatus.SUPERSEDED), (published, ConfigRevisionStatus.DRAFT), (invalidated, ConfigRevisionStatus.PUBLISHED), (invalidated, ConfigRevisionStatus.INVALIDATED)):
        with pytest.raises(ForbiddenTransitionError) as forbidden:
            service.transition(revision=current, expected_revision=current.revision, requested_status=target, actor_ref="actor-a")
        assert forbidden.value.code == "FORBIDDEN_TRANSITION"
    with pytest.raises(RevisionConflictError) as stale:
        service.transition(revision=published, expected_revision=1, requested_status=ConfigRevisionStatus.SUPERSEDED, actor_ref="actor-a")
    assert stale.value.current_revision == 2


def test_tst_m2_p5a_002_secret_handle_storage_blocks_plaintext(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    metadata_fields = {item.name for item in fields(SecretHandle)}
    prohibited = {"plaintext", "secret_value", "token", "password", "private_key", "blob", "raw_credential", "value"}
    assert not (metadata_fields & prohibited)
    assert not hasattr(SecretHandleStore, "read_secret_value")
    store = SecretHandleStore()
    try:
        store.register(
            workspace_id=WORKSPACE_A,
            provider_ref="provider",
            account_ref="account",
            alias_ref="alias",
            **{"plaintext_secret": "p5a-canary"},
        )
    except NotImplementedError:
        raise
    except ValueError:
        pass
    else:
        pytest.fail("plaintext-shaped input must be rejected at the secret-store boundary")
    with p5a_database.connect() as connection:
        columns = {row[0].lower() for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_secret_handles'").fetchall()}
    assert columns and not (columns & prohibited)


def test_tst_m2_p5a_003_secret_redaction_in_domain_events(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    safe_payload = {"workspace_id": WORKSPACE_A, "config_revision_id": "revision-5a", "config_revision_number": 1, "revision": 2, "status": "PUBLISHED", "reason": "approved", "correlation_id": "corr-5a", "audit_ref": "audit-5a"}
    ensure_safe_event_payload(safe_payload)
    factory = ConfigEventFactory()
    event = factory.publish_event(payload=safe_payload, workspace_id=WORKSPACE_A)
    assert event.payload == safe_payload
    for canary in (b"secret-bytes", "password=secret", "token=abcdef", "api_key=abcdef", "refresh token=abcdef", "credential=abcdef", "https://example.test/signed?signature=abcdef", "Traceback (most recent call last)", {"secret": "value"}):
        with pytest.raises(ValueError):
            factory.publish_event(payload={"safe": canary}, workspace_id=WORKSPACE_A)
    assert event.payload == safe_payload


def test_tst_m2_p5a_004_production_0004_forward_rollback_and_constraints(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    forward = PRODUCTION_MIGRATIONS / "0004_config_and_secrets.sql"
    rollback = PRODUCTION_MIGRATIONS / "0004_config_and_secrets.rollback.sql"
    assert forward.is_file() and rollback.is_file(), "P5A-004 requires production migration 0004 and its exact rollback"
    MigrationRunner(p5a_database.dsn, PRODUCTION_MIGRATIONS, is_test_env=True).migrate_up()
    with p5a_database.connect() as connection:
        _seed_workspaces(connection)
        config_columns = dict(connection.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_config_revisions'").fetchall())
        assert all(config_columns[name] == "NO" for name in {"config_revision_id", "workspace_id", "scope_kind", "scope_key", "config_revision_number", "revision", "content_hash", "payload", "status"})
        constraints = [row[0] for row in connection.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='controlplane.cp_config_revisions'::regclass").fetchall()]
        assert any("UNIQUE (workspace_id, scope_kind, scope_key, config_revision_number)" in item for item in constraints)
        assert any("config_revision_number" in item and "> 0" in item for item in constraints)
        assert any("revision" in item and ">= 1" in item for item in constraints)
        assert any("content_hash" in item and "[0-9a-f]" in item for item in constraints)
        secret_columns = {row[0].lower() for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_secret_handles'").fetchall()}
        assert not any(word in column for column in secret_columns for word in ("value", "token", "password", "blob", "secret"))
        rollback_sql = rollback.read_text(encoding="utf-8")
        with connection.transaction():
            connection.execute(rollback_sql)
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=4")
        assert [connection.execute("SELECT to_regclass(%s)", (f"controlplane.{table}",)).fetchone()[0] for table in ("cp_config_revisions", "cp_secret_handles")] == [None, None]
        assert [connection.execute("SELECT to_regclass(%s)", (f"controlplane.{table}",)).fetchone()[0] for table in ("cp_workspaces", "cp_command_receipts", "cp_idempotency_records", "cp_outbox_events", "cp_schema_migrations")] == [f"controlplane.{table}" for table in ("cp_workspaces", "cp_command_receipts", "cp_idempotency_records", "cp_outbox_events", "cp_schema_migrations")]
        assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,)]


def test_tst_m2_p5a_005_workspace_isolation_and_concurrent_publish(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    with p5a_database.connect() as connection:
        _seed_workspaces(connection)
    repository = ConfigRevisionRepository()
    assert not hasattr(repository, "get_by_id")
    revision = repository.get_scoped(workspace_id=WORKSPACE_A, config_revision_id="revision-5a")
    assert revision is not None
    assert repository.get_scoped(workspace_id=WORKSPACE_B, config_revision_id="revision-5a") is None
    with pytest.raises(PermissionError):
        repository.publish(workspace_id=WORKSPACE_B, config_revision_id="revision-5a", expected_revision=1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: repository.publish(workspace_id=WORKSPACE_A, config_revision_id="revision-5a", expected_revision=1), range(2)))
    winners = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    losers = [outcome for outcome in outcomes if isinstance(outcome, RevisionConflictError)]
    assert len(winners) == 1 and winners[0].revision == 2
    assert len(losers) == 1 and losers[0].current_revision == 2
    with p5a_database.connect() as connection:
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute("INSERT INTO controlplane.cp_config_revisions (workspace_id, scope_kind, scope_key, config_revision_number) VALUES (%s, 'prompt', 'primary', 1)", (WORKSPACE_A,))
