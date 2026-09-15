"""The exact five M2-P5A behavioral RED oracles, prior to implementation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

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
from controlplane.infrastructure.db.uow import TransactionManager


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


@contextmanager
def _create_disposable_database(migration_dir: Path) -> Iterator[DisposableDatabase]:
    """Create one exact P5A database and migrate only the supplied directory."""
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
        MigrationRunner(database.dsn, migration_dir, is_test_env=True).migrate_up()
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


@pytest.fixture
def p5a_database() -> Iterator[DisposableDatabase]:
    """Normal P5A behavior database; future production 0004 may be present."""
    with _create_disposable_database(PRODUCTION_MIGRATIONS) as database:
        yield database


@pytest.fixture
def p5a_migration_004_baseline() -> Iterator[tuple[DisposableDatabase, Path]]:
    """Real runner baseline pinned at accepted production migrations 0001--0003."""
    with tempfile.TemporaryDirectory(prefix="m2_p5a_migration_baseline_") as temporary:
        sandbox = Path(temporary)
        for version in range(1, 4):
            forward = next(path for path in PRODUCTION_MIGRATIONS.glob(f"{version:04d}_*.sql") if not path.name.endswith(".rollback.sql"))
            rollback = next(PRODUCTION_MIGRATIONS.glob(f"{version:04d}_*.rollback.sql"))
            shutil.copy2(forward, sandbox / forward.name)
            shutil.copy2(rollback, sandbox / rollback.name)
        with _create_disposable_database(sandbox) as database:
            with database.connect() as connection:
                assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,)]
            yield database, sandbox


def _assert_p1_to_p3_prerequisites(database: DisposableDatabase) -> None:
    with database.connect() as connection:
        applied = [row[0] for row in connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall()]
        assert {1, 2, 3} <= set(applied)
        assert connection.execute("SELECT to_regclass('controlplane.cp_outbox_events')").fetchone()[0] == "controlplane.cp_outbox_events"


def _seed_workspaces(connection: psycopg.Connection) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'P5A A', 'ACTIVE'), (%s, 'P5A B', 'ACTIVE')",
        (WORKSPACE_A, WORKSPACE_B),
    )


def _assert_immutable_identity(before: object, after: object) -> None:
    for name in ("config_revision_id", "config_revision_number", "payload", "content_hash"):
        assert getattr(after, name) == getattr(before, name)


def _assert_successful_transition(before: object, after: object, status: ConfigRevisionStatus) -> None:
    _assert_immutable_identity(before, after)
    assert after.status is status
    assert after.revision == before.revision + 1


def _revision_snapshot(revision: object) -> tuple[object, ...]:
    """Capture every dataclass field with payload frozen as canonical bytes."""
    return tuple(
        (item.name, canonicalize_json(getattr(revision, item.name)) if item.name == "payload" else getattr(revision, item.name))
        for item in fields(revision)
    )


def _config_revision_immutable_snapshot(revision: object) -> tuple[object, ...]:
    """Capture the name-defined immutable facts preserved by a successful publish."""
    return (
        revision.config_revision_id,
        revision.workspace_id,
        revision.scope_kind,
        revision.scope_key,
        revision.config_revision_number,
        revision.content_hash,
        canonicalize_json(revision.payload),
    )


@contextmanager
def _p5a_transaction_manager(database: DisposableDatabase) -> Iterator[TransactionManager]:
    """Provide P1's pool/UoW boundary; callers own each active UoW explicitly."""
    manager = TransactionManager(database.dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


def _p5a_outbox_count(connection: psycopg.Connection, config_revision_id: str) -> int:
    return connection.execute("SELECT count(*) FROM controlplane.cp_outbox_events WHERE workspace_id=%s AND aggregate_type='config_revision' AND aggregate_id=%s", (WORKSPACE_A, config_revision_id)).fetchone()[0]


def _clone_duplicate_config_revision(connection: psycopg.Connection, config_revision_id: str) -> None:
    """Clone all final-schema values, changing only identity, to target UNIQUE precisely."""
    columns = [row[0] for row in connection.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='controlplane' AND table_name='cp_config_revisions' "
        "ORDER BY ordinal_position"
    ).fetchall()]
    assert "config_revision_id" in columns
    target_columns = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    source_columns = sql.SQL(", ").join(
        sql.Placeholder() if column == "config_revision_id" else sql.Identifier(column)
        for column in columns
    )
    statement = sql.SQL(
        "INSERT INTO controlplane.cp_config_revisions ({targets}) "
        "SELECT {sources} FROM controlplane.cp_config_revisions WHERE config_revision_id=%s"
    ).format(targets=target_columns, sources=source_columns)
    connection.execute(statement, (str(uuid.uuid4()), config_revision_id))


def _required_columns(connection: psycopg.Connection, table_name: str) -> list[tuple[str, str, str | None, str, str]]:
    return connection.execute(
        "SELECT column_name, is_nullable, column_default, data_type, udt_name "
        "FROM information_schema.columns WHERE table_schema='controlplane' AND table_name=%s "
        "ORDER BY ordinal_position",
        (table_name,),
    ).fetchall()


def _test_value(column_name: str, data_type: str, udt_name: str, overrides: dict[str, object]) -> object:
    if column_name in overrides:
        return overrides[column_name]
    if column_name == "workspace_id":
        return WORKSPACE_A
    if column_name.endswith("_id"):
        return str(uuid.uuid4())
    if column_name in {"scope_kind", "scope_key"}:
        return "prompt"
    if column_name == "config_revision_number":
        return 1
    if column_name == "revision":
        return 1
    if column_name == "content_hash":
        return "a" * 64
    if column_name == "payload":
        return Jsonb({"enabled": True})
    if column_name == "status":
        return "DRAFT"
    if data_type == "boolean":
        return False
    if data_type in {"smallint", "integer", "bigint", "numeric", "double precision", "real"}:
        return 1
    if "timestamp" in data_type:
        return datetime.now(timezone.utc)
    if udt_name == "jsonb":
        return Jsonb({})
    return "test"


def _insert_required_row(connection: psycopg.Connection, table_name: str, overrides: dict[str, object]) -> str:
    columns = _required_columns(connection, table_name)
    names: list[str] = []
    values: list[object] = []
    for name, nullable, default, data_type, udt_name in columns:
        if name in overrides:
            names.append(name)
            values.append(overrides[name])
        elif nullable == "NO" and default is None:
            names.append(name)
            values.append(_test_value(name, data_type, udt_name, overrides))
    statement = sql.SQL("INSERT INTO controlplane.{table} ({columns}) VALUES ({values}) RETURNING {id}").format(
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in names),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in values),
        id=sql.Identifier("config_revision_id" if table_name == "cp_config_revisions" else "secret_handle_id"),
    )
    return str(connection.execute(statement, values).fetchone()[0])


def _constraint_columns(connection: psycopg.Connection, table_name: str, constraint_type: str) -> list[tuple[str, list[str], str | None, list[str]]]:
    return connection.execute(
        "SELECT c.conname, "
        "COALESCE((SELECT array_agg(a.attname ORDER BY u.ordinality) FROM unnest(c.conkey) WITH ORDINALITY AS u(attnum, ordinality) "
        "JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=u.attnum), ARRAY[]::text[]), "
        "NULLIF(c.confrelid::regclass::text, '-'), "
        "COALESCE((SELECT array_agg(a.attname ORDER BY u.ordinality) FROM unnest(c.confkey) WITH ORDINALITY AS u(attnum, ordinality) "
        "JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=u.attnum), ARRAY[]::text[]) "
        "FROM pg_constraint c WHERE c.conrelid=%s::regclass AND c.contype=%s",
        (f"controlplane.{table_name}", constraint_type),
    ).fetchall()


def _migration_ledger_ddl_snapshot(connection: psycopg.Connection) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Capture every user trigger and controlplane function before 0004 runs."""
    triggers = connection.execute(
        "SELECT trigger_name, action_statement FROM information_schema.triggers "
        "WHERE event_object_schema='controlplane' AND event_object_table='cp_schema_migrations' "
        "ORDER BY trigger_name, action_statement"
    ).fetchall()
    functions = connection.execute(
        "SELECT p.proname, pg_get_functiondef(p.oid) "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='controlplane' ORDER BY p.proname, p.oid"
    ).fetchall()
    return triggers, functions


def test_tst_m2_p5a_001_config_revision_immutability_and_hash(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    with p5a_database.connect() as connection:
        _seed_workspaces(connection)
    first_payload = json.loads('{ "scope": "prompt", "values": { "a": 1, "b": [true, null] } }')
    equivalent_payload = json.loads('{"values":{"b":[true,null],"a":1},"scope":"prompt"}')
    changed_payload = {"scope": "prompt", "values": {"a": 2, "b": [True, None]}}
    assert canonicalize_json(first_payload) == canonicalize_json(equivalent_payload)
    assert request_hash(first_payload) == request_hash(equivalent_payload)
    assert request_hash(first_payload) == hashlib.sha256(canonicalize_json(first_payload)).hexdigest()
    assert request_hash(first_payload) != request_hash(changed_payload)

    first_persisted_hash = request_hash(first_payload)
    with _p5a_transaction_manager(p5a_database) as manager:
        with manager.unit_of_work() as uow:
            service = ConfigRevisionService()

            def create(scope_key: str, payload: object = first_payload) -> object:
                return service.create_revision(
                    workspace_id=WORKSPACE_A,
                    scope_kind="prompt",
                    scope_key=scope_key,
                    config_revision_number=1,
                    payload=payload,
                    actor_ref="actor-a",
                    change_reason="initial",
                    connection=uow.connection,
                )

            def transition(revision: object, expected_revision: int, requested_status: ConfigRevisionStatus, actor_ref: str) -> object:
                return service.transition(
                    revision=revision,
                    expected_revision=expected_revision,
                    requested_status=requested_status,
                    actor_ref=actor_ref,
                    connection=uow.connection,
                )

            draft = create("draft-published")
            assert draft.config_revision_number == 1 and draft.revision == 1 and draft.status is ConfigRevisionStatus.DRAFT
            assert draft.content_hash == first_persisted_hash
            assert uow.connection.execute(
                "SELECT content_hash FROM controlplane.cp_config_revisions WHERE config_revision_id=%s",
                (draft.config_revision_id,),
            ).fetchone() == (first_persisted_hash,)
            equivalent_revision = create("equivalent-payload", equivalent_payload)
            assert equivalent_revision.content_hash == request_hash(first_payload)
            assert equivalent_revision.content_hash == first_persisted_hash
            assert uow.connection.execute(
                "SELECT content_hash FROM controlplane.cp_config_revisions WHERE config_revision_id=%s",
                (equivalent_revision.config_revision_id,),
            ).fetchone() == (first_persisted_hash,)
            changed_revision = create("changed-payload", changed_payload)
            changed_hash = request_hash(changed_payload)
            assert changed_revision.content_hash == changed_hash
            assert changed_hash != first_persisted_hash
            assert uow.connection.execute(
                "SELECT content_hash FROM controlplane.cp_config_revisions WHERE config_revision_id=%s",
                (changed_revision.config_revision_id,),
            ).fetchone() == (changed_hash,)
            published = transition(draft, 1, ConfigRevisionStatus.PUBLISHED, "actor-a")
            _assert_successful_transition(draft, published, ConfigRevisionStatus.PUBLISHED)
            superseded = transition(published, 2, ConfigRevisionStatus.SUPERSEDED, "actor-a")
            _assert_successful_transition(published, superseded, ConfigRevisionStatus.SUPERSEDED)
            draft_for_invalidation = create("draft-invalidated")
            invalidated_draft = transition(draft_for_invalidation, 1, ConfigRevisionStatus.INVALIDATED, "security-owner")
            _assert_successful_transition(draft_for_invalidation, invalidated_draft, ConfigRevisionStatus.INVALIDATED)
            published_for_invalidation = transition(create("published-invalidated"), 1, ConfigRevisionStatus.PUBLISHED, "actor-a")
            invalidated_published = transition(published_for_invalidation, 2, ConfigRevisionStatus.INVALIDATED, "security-owner")
            _assert_successful_transition(published_for_invalidation, invalidated_published, ConfigRevisionStatus.INVALIDATED)
            invalidated_superseded = transition(superseded, 3, ConfigRevisionStatus.INVALIDATED, "security-owner")
            _assert_successful_transition(superseded, invalidated_superseded, ConfigRevisionStatus.INVALIDATED)
            for current, target in ((draft, ConfigRevisionStatus.SUPERSEDED), (published, ConfigRevisionStatus.DRAFT), (superseded, ConfigRevisionStatus.PUBLISHED), (draft, ConfigRevisionStatus.DRAFT), (published, ConfigRevisionStatus.PUBLISHED), (superseded, ConfigRevisionStatus.SUPERSEDED)):
                before = _revision_snapshot(current)
                with pytest.raises(ForbiddenTransitionError) as forbidden:
                    transition(current, current.revision, target, "actor-a")
                assert forbidden.value.code == "FORBIDDEN_TRANSITION"
                assert _revision_snapshot(current) == before
            for target in ConfigRevisionStatus:
                before = _revision_snapshot(invalidated_draft)
                with pytest.raises(ForbiddenTransitionError):
                    transition(invalidated_draft, invalidated_draft.revision, target, "actor-a")
                assert _revision_snapshot(invalidated_draft) == before
            stale_seed = create("persisted-current-cas")
            stale_before = _revision_snapshot(stale_seed)
            advanced = transition(stale_seed, 1, ConfigRevisionStatus.PUBLISHED, "actor-a")
            assert advanced.revision == 2
            with pytest.raises(RevisionConflictError) as stale:
                transition(stale_seed, 1, ConfigRevisionStatus.PUBLISHED, "actor-a")
            assert stale.value.current_revision == 2
            assert _revision_snapshot(stale_seed) == stale_before
    with p5a_database.connect() as connection:
        durable_hashes = connection.execute(
            "SELECT config_revision_id::text, content_hash FROM controlplane.cp_config_revisions "
            "WHERE config_revision_id IN (%s, %s, %s)",
            (draft.config_revision_id, equivalent_revision.config_revision_id, changed_revision.config_revision_id),
        ).fetchall()
    assert dict(durable_hashes) == {
        draft.config_revision_id: first_persisted_hash,
        equivalent_revision.config_revision_id: first_persisted_hash,
        changed_revision.config_revision_id: request_hash(changed_payload),
    }


def test_tst_m2_p5a_002_secret_handle_storage_blocks_plaintext(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    with p5a_database.connect() as connection:
        _seed_workspaces(connection)
    metadata_fields = {item.name for item in fields(SecretHandle)}
    prohibited = {"plaintext", "secret_value", "token", "password", "private_key", "blob", "raw_credential", "value"}
    assert not (metadata_fields & prohibited)
    assert not hasattr(SecretHandleStore, "read_secret_value")
    metadata = {"workspace_id": WORKSPACE_A, "provider_ref": "vault", "account_ref": "account", "alias_ref": "alias", "redacted_fingerprint_or_version": "version-redacted", "validation_status": "VALID", "expires_at": "2027-01-01T00:00:00Z", "audit_ref": "audit-5a"}
    with _p5a_transaction_manager(p5a_database) as manager:
        with manager.unit_of_work() as uow:
            store = SecretHandleStore()
            registered = store.register(**metadata, connection=uow.connection)
    assert registered.workspace_id == WORKSPACE_A
    assert registered.provider_ref == metadata["provider_ref"]
    assert not hasattr(registered, "secret_value") and not hasattr(registered, "plaintext")
    with p5a_database.connect() as connection:
        assert connection.execute("SELECT workspace_id::text FROM controlplane.cp_secret_handles WHERE secret_handle_id=%s", (registered.secret_handle_id,)).fetchone() == (WORKSPACE_A,)
    try:
        with _p5a_transaction_manager(p5a_database) as manager:
            with manager.unit_of_work() as uow:
                SecretHandleStore().register(
                    workspace_id=WORKSPACE_A,
                    provider_ref="provider",
                    account_ref="account",
                    alias_ref="alias",
                    connection=uow.connection,
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
    invalidation_payload = {**safe_payload, "status": "INVALIDATED", "reason": "security defect"}
    invalidation_event = factory.invalidation_event(payload=invalidation_payload, workspace_id=WORKSPACE_A)
    assert event.payload == safe_payload
    assert invalidation_event.payload == invalidation_payload
    for canary in (b"secret-bytes", "password=secret", "token=abcdef", "api_key=abcdef", "refresh token=abcdef", "credential=abcdef", "https://example.test/signed?signature=abcdef", "Traceback (most recent call last)", {"secret": "value"}):
        with pytest.raises(ValueError):
            factory.publish_event(payload={"safe": canary}, workspace_id=WORKSPACE_A)
        with pytest.raises(ValueError):
            factory.invalidation_event(payload={"safe": canary}, workspace_id=WORKSPACE_A)
    assert event.payload == safe_payload


def test_tst_m2_p5a_004_production_0004_forward_rollback_and_constraints(p5a_migration_004_baseline: tuple[DisposableDatabase, Path]) -> None:
    p5a_database, baseline_migrations = p5a_migration_004_baseline
    forward = PRODUCTION_MIGRATIONS / "0004_config_and_secrets.sql"
    rollback = PRODUCTION_MIGRATIONS / "0004_config_and_secrets.rollback.sql"
    assert forward.is_file() and rollback.is_file(), "P5A-004 requires production migration 0004 and its exact rollback"
    shutil.copy2(forward, baseline_migrations / forward.name)
    shutil.copy2(rollback, baseline_migrations / rollback.name)
    with p5a_database.connect() as connection:
        ledger_ddl_before = _migration_ledger_ddl_snapshot(connection)
    MigrationRunner(p5a_database.dsn, baseline_migrations, is_test_env=True).migrate_up()
    with p5a_database.connect() as connection:
        assert _migration_ledger_ddl_snapshot(connection) == ledger_ddl_before
        _seed_workspaces(connection)
        config_columns = dict(connection.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_config_revisions'").fetchall())
        assert all(config_columns[name] == "NO" for name in {"config_revision_id", "workspace_id", "scope_kind", "scope_key", "config_revision_number", "revision", "content_hash", "payload", "status"})
        config_fks = _constraint_columns(connection, "cp_config_revisions", "f")
        secret_fks = _constraint_columns(connection, "cp_secret_handles", "f")
        assert any(columns == ["workspace_id"] and referenced == "controlplane.cp_workspaces" and referenced_columns == ["workspace_id"] for _, columns, referenced, referenced_columns in config_fks)
        assert any(columns == ["workspace_id"] and referenced == "controlplane.cp_workspaces" and referenced_columns == ["workspace_id"] for _, columns, referenced, referenced_columns in secret_fks)
        config_uniques = _constraint_columns(connection, "cp_config_revisions", "u")
        assert any(columns == ["workspace_id", "scope_kind", "scope_key", "config_revision_number"] for _, columns, _, _ in config_uniques)
        check_constraints = connection.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='controlplane.cp_config_revisions'::regclass AND contype='c'"
        ).fetchall()
        assert any("config_revision_number" in definition and "> 0" in definition for _, definition in check_constraints)
        assert any("revision" in definition and ">= 1" in definition for _, definition in check_constraints)
        assert any("content_hash" in definition for _, definition in check_constraints)
        _insert_required_row(connection, "cp_config_revisions", {"workspace_id": WORKSPACE_A, "scope_key": "valid", "content_hash": "a" * 64})
        for index, invalid_hash in enumerate(("A" * 64, "a" * 63, "a" * 65, "g" * 64)):
            try:
                with connection.transaction():
                    _insert_required_row(connection, "cp_config_revisions", {"workspace_id": WORKSPACE_A, "scope_key": f"invalid-hash-{index}", "content_hash": invalid_hash})
            except psycopg.errors.CheckViolation:
                pass
            else:
                pytest.fail(f"invalid content hash was accepted: {invalid_hash!r}")
        try:
            with connection.transaction():
                _insert_required_row(connection, "cp_config_revisions", {"workspace_id": WORKSPACE_A, "scope_key": "invalid-number", "config_revision_number": 0})
        except psycopg.errors.CheckViolation:
            pass
        else:
            pytest.fail("non-positive config_revision_number was accepted")
        try:
            with connection.transaction():
                _insert_required_row(connection, "cp_config_revisions", {"workspace_id": WORKSPACE_A, "scope_key": "invalid-revision", "revision": 0})
        except psycopg.errors.CheckViolation:
            pass
        else:
            pytest.fail("revision=0 was accepted")
        try:
            with connection.transaction():
                _insert_required_row(connection, "cp_config_revisions", {"workspace_id": "00000000-0000-0000-0000-0000000005af", "scope_key": "invalid-config-fk"})
        except psycopg.errors.ForeignKeyViolation:
            pass
        else:
            pytest.fail("invalid config workspace FK was accepted")
        try:
            with connection.transaction():
                _insert_required_row(connection, "cp_secret_handles", {"workspace_id": "00000000-0000-0000-0000-0000000005af"})
        except psycopg.errors.ForeignKeyViolation:
            pass
        else:
            pytest.fail("invalid secret workspace FK was accepted")
        secret_columns = {row[0].lower() for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='controlplane' AND table_name='cp_secret_handles'").fetchall()}
        plaintext_columns = {"value", "secret_value", "plaintext", "plaintext_secret", "token", "access_token", "refresh_token", "password", "private_key", "credential", "raw_credential", "blob", "secret_blob"}
        assert not (secret_columns & plaintext_columns)
        rollback_sql = rollback.read_text(encoding="utf-8")
        with connection.transaction():
            connection.execute(rollback_sql)
            connection.execute("DELETE FROM controlplane.cp_schema_migrations WHERE version=4")
        assert [connection.execute("SELECT to_regclass(%s)", (f"controlplane.{table}",)).fetchone()[0] for table in ("cp_config_revisions", "cp_secret_handles")] == [None, None]
        assert [connection.execute("SELECT to_regclass(%s)", (f"controlplane.{table}",)).fetchone()[0] for table in ("cp_workspaces", "cp_command_receipts", "cp_idempotency_records", "cp_outbox_events", "cp_schema_migrations")] == [f"controlplane.{table}" for table in ("cp_workspaces", "cp_command_receipts", "cp_idempotency_records", "cp_outbox_events", "cp_schema_migrations")]
        assert connection.execute("SELECT version FROM controlplane.cp_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,)]


def test_tst_m2_p5a_005_workspace_isolation_and_concurrent_publish(p5a_database: DisposableDatabase) -> None:
    _assert_p1_to_p3_prerequisites(p5a_database)
    assert not hasattr(psycopg.Connection, "_p5a_original_execute")
    assert psycopg.Connection.execute.__module__ == "psycopg.connection"
    with p5a_database.connect() as connection:
        _seed_workspaces(connection)
    with _p5a_transaction_manager(p5a_database) as manager:
        with manager.unit_of_work() as uow:
            seed = ConfigRevisionService().create_revision(
                workspace_id=WORKSPACE_A,
                scope_kind="prompt",
                scope_key="primary",
                config_revision_number=1,
                payload={"enabled": True},
                actor_ref="actor-a",
                change_reason="fixture seed",
                connection=uow.connection,
            )
        with manager.unit_of_work() as uow:
            rollback_seed = ConfigRevisionService().create_revision(
                workspace_id=WORKSPACE_A,
                scope_kind="prompt",
                scope_key="rollback-probe",
                config_revision_number=1,
                payload={"enabled": False},
                actor_ref="actor-a",
                change_reason="rollback fixture",
                connection=uow.connection,
            )
        with manager.unit_of_work() as uow:
            rollback_repository = ConfigRevisionRepository()
            rollback_before_revision = rollback_repository.get_scoped(
                workspace_id=WORKSPACE_A,
                config_revision_id=rollback_seed.config_revision_id,
                connection=uow.connection,
            )
            assert rollback_before_revision is not None
            rollback_before_snapshot = _revision_snapshot(rollback_before_revision)
            rollback_outbox_before = _p5a_outbox_count(uow.connection, rollback_seed.config_revision_id)

        class _RollbackProbe(Exception):
            pass

        with pytest.raises(_RollbackProbe):
            with manager.unit_of_work() as uow:
                published = ConfigRevisionRepository().publish(
                    workspace_id=WORKSPACE_A,
                    config_revision_id=rollback_seed.config_revision_id,
                    expected_revision=rollback_before_revision.revision,
                    connection=uow.connection,
                )
                assert published.revision == rollback_before_revision.revision + 1
                assert _p5a_outbox_count(uow.connection, rollback_seed.config_revision_id) == rollback_outbox_before + 1
                raise _RollbackProbe()
        with manager.unit_of_work() as uow:
            rollback_persisted = ConfigRevisionRepository().get_scoped(
                workspace_id=WORKSPACE_A,
                config_revision_id=rollback_seed.config_revision_id,
                connection=uow.connection,
            )
            assert rollback_persisted is not None
            assert _revision_snapshot(rollback_persisted) == rollback_before_snapshot
            assert _p5a_outbox_count(uow.connection, rollback_seed.config_revision_id) == rollback_outbox_before
        with manager.unit_of_work() as uow:
            repository = ConfigRevisionRepository()
            revision = repository.get_scoped(workspace_id=WORKSPACE_A, config_revision_id=seed.config_revision_id, connection=uow.connection)
            assert not hasattr(repository, "get_by_id")
            assert revision is not None
            before_foreign = _revision_snapshot(revision)
            before_immutable = _config_revision_immutable_snapshot(revision)
            outbox_before = _p5a_outbox_count(uow.connection, seed.config_revision_id)
        with manager.unit_of_work() as uow:
            assert ConfigRevisionRepository().get_scoped(workspace_id=WORKSPACE_B, config_revision_id=seed.config_revision_id, connection=uow.connection) is None

        def publish_foreign() -> object:
            with manager.unit_of_work() as uow:
                return ConfigRevisionRepository().publish(
                    workspace_id=WORKSPACE_B,
                    config_revision_id=seed.config_revision_id,
                    expected_revision=1,
                    connection=uow.connection,
                )

        with pytest.raises(PermissionError):
            publish_foreign()
        with manager.unit_of_work() as uow:
            repository = ConfigRevisionRepository()
            persisted = repository.get_scoped(workspace_id=WORKSPACE_A, config_revision_id=seed.config_revision_id, connection=uow.connection)
            assert persisted is not None and _revision_snapshot(persisted) == before_foreign
            assert _p5a_outbox_count(uow.connection, seed.config_revision_id) == outbox_before

        def publish_once() -> object:
            try:
                with manager.unit_of_work() as uow:
                    return ConfigRevisionRepository().publish(
                        workspace_id=WORKSPACE_A,
                        config_revision_id=seed.config_revision_id,
                        expected_revision=1,
                        connection=uow.connection,
                    )
            except RevisionConflictError as conflict:
                return conflict

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: publish_once(), range(2)))
    winners = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    losers = [outcome for outcome in outcomes if isinstance(outcome, RevisionConflictError)]
    assert len(winners) == 1 and winners[0].revision == 2
    assert len(losers) == 1 and losers[0].current_revision == 2
    with _p5a_transaction_manager(p5a_database) as manager:
        with manager.unit_of_work() as uow:
            repository = ConfigRevisionRepository()
            persisted = repository.get_scoped(workspace_id=WORKSPACE_A, config_revision_id=seed.config_revision_id, connection=uow.connection)
            assert persisted is not None
            assert persisted.revision == 2
            assert persisted.status is ConfigRevisionStatus.PUBLISHED
            assert _config_revision_immutable_snapshot(persisted) == before_immutable
            assert _p5a_outbox_count(uow.connection, seed.config_revision_id) == outbox_before + 1
        def publish_stale() -> object:
            with manager.unit_of_work() as uow:
                return ConfigRevisionRepository().publish(workspace_id=WORKSPACE_A, config_revision_id=seed.config_revision_id, expected_revision=1, connection=uow.connection)
        with pytest.raises(RevisionConflictError):
            publish_stale()
        with manager.unit_of_work() as uow:
            assert type(uow.connection) is psycopg.Connection
            assert type(uow.connection).execute is psycopg.Connection.execute
            assert _p5a_outbox_count(uow.connection, seed.config_revision_id) == outbox_before + 1
            with pytest.raises(psycopg.errors.UniqueViolation) as duplicate:
                with uow.connection.transaction():
                    _clone_duplicate_config_revision(uow.connection, seed.config_revision_id)
            expected_constraints = uow.connection.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid='controlplane.cp_config_revisions'::regclass "
                "AND contype='u' AND pg_get_constraintdef(oid) LIKE '%workspace_id, scope_kind, scope_key, config_revision_number%'"
            ).fetchall()
            assert duplicate.value.diag.constraint_name in {row[0] for row in expected_constraints}
