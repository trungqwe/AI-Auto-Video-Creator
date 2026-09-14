"""Mandatory M2-P2 Behavioral RED oracles; P2 production behavior is absent."""
from __future__ import annotations

import math
import os
import re
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.concurrency import RevisionConflictError
from controlplane.application.idempotency import IdempotencyCoordinator, canonicalize_json, request_hash
from controlplane.domain.common import MessageEnvelope, ProblemDetail
from controlplane.infrastructure.db.concurrency import PostgresRevisionedMutationAdapter
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager

REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_MIGRATIONS = REPO_ROOT / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
TEST_DATABASE_NAME = re.compile(r"^m2_p2_test_[0-9a-f]+$")
WORKSPACE_A = "00000000-0000-0000-0000-000000000201"
WORKSPACE_B = "00000000-0000-0000-0000-000000000202"
JCS_TEXT = '{"array":[{"𐀀":"y","":"x"}],"z":{"𐀀":1,"":0},"𐀀":"nonbmp","":"bmp"}'
JCS_BYTES = bytes.fromhex("7b226172726179223a5b7b22f0908080223a2279222c22ee8080223a2278227d5d2c227a223a7b22f0908080223a312c22ee8080223a307d2c22f0908080223a226e6f6e626d70222c22ee8080223a22626d70227d")
JCS_SHA256 = "26ba19fb0f713fb75a3113fbfb9bc2617149606043eb5958991b68ce4d175afb"


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
def disposable_db() -> Iterator[DisposableDatabase]:
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.")
    name = f"m2_p2_test_{uuid.uuid4().hex}"
    assert TEST_DATABASE_NAME.fullmatch(name)
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            with admin.cursor() as cursor:
                cursor.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user")
                if not cursor.fetchone()[0]:
                    pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.")
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except pytest.fail.Exception:
        raise
    except Exception as exc:
        pytest.fail(f"BLOCKED_EXTERNAL: PostgreSQL prerequisite failed ({type(exc).__name__}); DSN redacted.")
    database = DisposableDatabase(name=name, dsn=make_conninfo(admin_dsn, dbname=name))
    try:
        yield database
    finally:
        for connection in database.connections:
            if not connection.closed:
                connection.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            with admin.cursor() as cursor:
                assert TEST_DATABASE_NAME.fullmatch(name)
                cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def p2_bootstrap_schema(disposable_db: DisposableDatabase) -> DisposableDatabase:
    """Test-only P2 prerequisites for 003–010; not a production-0002 proof."""
    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA controlplane")
            cursor.execute("CREATE TABLE controlplane.cp_workspaces (workspace_id UUID PRIMARY KEY)")
            cursor.execute("INSERT INTO controlplane.cp_workspaces VALUES (%s), (%s)", (WORKSPACE_A, WORKSPACE_B))
            cursor.execute("CREATE TABLE controlplane.cp_command_receipts (receipt_id UUID PRIMARY KEY, workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces, command_id TEXT NOT NULL, disposition TEXT NOT NULL CHECK (disposition IN ('accepted','rejected')), operation_id UUID NULL, resource_ref JSONB NULL, accepted_at TIMESTAMPTZ NOT NULL, current_revision BIGINT NULL, UNIQUE (workspace_id, command_id), UNIQUE (workspace_id, receipt_id))")
            cursor.execute("CREATE TABLE controlplane.cp_idempotency_records (workspace_id UUID NOT NULL, command_name TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL, receipt_id UUID NOT NULL, created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NULL, PRIMARY KEY (workspace_id, command_name, idempotency_key), FOREIGN KEY (workspace_id, receipt_id) REFERENCES controlplane.cp_command_receipts (workspace_id, receipt_id))")
            cursor.execute("CREATE TABLE controlplane.cp_revision_probe (resource_id TEXT PRIMARY KEY, revision BIGINT NOT NULL, payload TEXT NOT NULL)")
    return disposable_db


def _complete_envelope() -> dict[str, object]:
    return {"contract_name": "controlplane.command", "contract_version": 1, "message_id": "message-1", "workspace_id": WORKSPACE_A, "correlation_id": "correlation-1", "occurred_at": "2026-09-14T00:00:00Z", "actor": "user", "payload": {"title": "payload"}, "command_id": "command-1", "requested_at": "2026-09-14T00:00:00Z"}


def _field(value: Any, name: str) -> Any:
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _coordinator(database: DisposableDatabase) -> tuple[IdempotencyCoordinator, TransactionManager]:
    manager = TransactionManager(database.dsn)
    return IdempotencyCoordinator(uow_factory=manager.unit_of_work, repository_factory=object), manager


def test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc() -> None:
    envelope = MessageEnvelope.create(**_complete_envelope())
    assert _field(envelope, "occurred_at") == "2026-09-14T00:00:00Z"
    for field in ("contract_name", "message_id", "workspace_id", "correlation_id", "actor", "payload", "command_id"):
        invalid = _complete_envelope(); invalid.pop(field)
        with pytest.raises(ValueError, match="ENVELOPE_VALIDATION_ERROR"):
            MessageEnvelope.create(**invalid)
    for invalid in ("2026-09-14T00:00:00", "2026-09-14T00:00:00+07:00", "not-a-timestamp"):
        with pytest.raises(ValueError, match="ENVELOPE_VALIDATION_ERROR"):
            MessageEnvelope.create(**(_complete_envelope() | {"occurred_at": invalid}))
    conditional = _complete_envelope() | {"derived": True, "process_boundary": True, "internal_mutation": True, "external_boundary": True, "revisioned_update": True, "policy_dependent": True}
    for field in ("causation_id", "trace_context", "recovery_epoch", "idempotency_key", "expected_revision", "policy_revision_id"):
        with pytest.raises(ValueError, match="ENVELOPE_VALIDATION_ERROR"):
            MessageEnvelope.create(**conditional)


def test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract() -> None:
    detail = ProblemDetail.create(type="urn:problem:validation", title="Validation", detail="Dữ liệu không hợp lệ", instance="urn:instance:1", code="VALIDATION_ERROR", category="validation", retryable=False, correlation_id="correlation-1", status=None, retry_after=None, field_errors=None, technical_detail_ref="opaque:detail:1")
    for field in ("type", "title", "detail", "instance", "code", "category", "retryable", "correlation_id"):
        assert _field(detail, field) is not None
    assert _field(detail, "status") is None
    assert _field(detail, "technical_detail_ref") == "opaque:detail:1"
    assert "Traceback" not in _field(detail, "detail") and "password=" not in _field(detail, "detail")
    with pytest.raises(ValueError, match="PROBLEM_DETAIL_VALIDATION_ERROR"):
        ProblemDetail.create(type=None, title="Validation", detail="safe", instance="i", code="VALIDATION_ERROR", category="validation", retryable=False, correlation_id="c")


def test_tst_m2_p2_003_durable_command_receipt_persistence(p2_bootstrap_schema: DisposableDatabase) -> None:
    coordinator, manager = _coordinator(p2_bootstrap_schema)
    receipt = coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-003", payload={"v": 1})
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT workspace_id::text, command_id, disposition FROM controlplane.cp_command_receipts")
            assert cursor.fetchall() == [(WORKSPACE_A, _field(receipt, "command_id"), "accepted")]
            cursor.execute("SELECT receipt_id::text FROM controlplane.cp_idempotency_records")
            assert cursor.fetchall() == [(str(_field(receipt, "receipt_id")),)]
    manager.close()


def test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt(p2_bootstrap_schema: DisposableDatabase) -> None:
    input_a = {"": "bmp", "𐀀": "nonbmp", "z": {"": 0, "𐀀": 1}, "array": [{"": "x", "𐀀": "y"}]}
    input_b = {"array": [{"": "x", "𐀀": "y"}], "z": {"": 0, "𐀀": 1}, "": "bmp", "𐀀": "nonbmp"}
    assert canonicalize_json(input_a) == JCS_BYTES == JCS_TEXT.encode("utf-8")
    assert canonicalize_json(input_b) == JCS_BYTES
    assert request_hash(input_a) == request_hash(input_b) == JCS_SHA256
    assert canonicalize_json({"array": [2, 1], "text": "e\u0301", "number": -0.0}) != canonicalize_json({"array": [1, 2], "text": "é", "number": 0})
    for invalid in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError): canonicalize_json({"number": invalid})
    coordinator, manager = _coordinator(p2_bootstrap_schema)
    first = coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-004", payload=input_a)
    replay = coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-004", payload=input_b)
    assert _field(replay, "receipt_id") == _field(first, "receipt_id") and _field(replay, "disposition") == "duplicate"
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM controlplane.cp_command_receipts"); assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM controlplane.cp_idempotency_records"); assert cursor.fetchone()[0] == 1
    manager.close()


def test_tst_m2_p2_005_same_key_different_payload_rejected(p2_bootstrap_schema: DisposableDatabase) -> None:
    coordinator, manager = _coordinator(p2_bootstrap_schema)
    coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-005", payload={"v": 1})
    with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"):
        coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-005", payload={"v": 2})
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM controlplane.cp_command_receipts"); assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM controlplane.cp_idempotency_records"); assert cursor.fetchone()[0] == 1
    manager.close()


def test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt(p2_bootstrap_schema: DisposableDatabase) -> None:
    barrier = threading.Barrier(2)
    def submit() -> object:
        coordinator, manager = _coordinator(p2_bootstrap_schema)
        try:
            barrier.wait(timeout=5)
            return coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-006", payload={"v": 1})
        finally: manager.close()
    with ThreadPoolExecutor(max_workers=2) as executor: first, second = list(executor.map(lambda _: submit(), range(2)))
    assert _field(first, "receipt_id") == _field(second, "receipt_id")
    assert {_field(first, "disposition"), _field(second, "disposition")} <= {"accepted", "duplicate"}
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM controlplane.cp_command_receipts"); assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM controlplane.cp_idempotency_records"); assert cursor.fetchone()[0] == 1


def test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser(p2_bootstrap_schema: DisposableDatabase) -> None:
    barrier = threading.Barrier(2)
    def submit(payload: dict[str, int]) -> object:
        coordinator, manager = _coordinator(p2_bootstrap_schema)
        try:
            barrier.wait(timeout=5); return coordinator.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="k-007", payload=payload)
        except ValueError as error: return error
        finally: manager.close()
    with ThreadPoolExecutor(max_workers=2) as executor: outcomes = list(executor.map(submit, ({"v": 1}, {"v": 2})))
    assert sum(not isinstance(value, ValueError) for value in outcomes) == 1
    assert any(isinstance(value, ValueError) and "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD" in str(value) for value in outcomes)
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM controlplane.cp_command_receipts"); assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM controlplane.cp_idempotency_records"); assert cursor.fetchone()[0] == 1


def test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart(p2_bootstrap_schema: DisposableDatabase) -> None:
    first, manager_a = _coordinator(p2_bootstrap_schema)
    receipt_a = first.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="shared", payload={"v": 1}); manager_a.close()
    second, manager_b = _coordinator(p2_bootstrap_schema)
    receipt_b = second.submit(workspace_id=WORKSPACE_B, command_name="create", idempotency_key="shared", payload={"v": 1})
    replay_a = second.submit(workspace_id=WORKSPACE_A, command_name="create", idempotency_key="shared", payload={"v": 1})
    assert _field(receipt_a, "receipt_id") != _field(receipt_b, "receipt_id")
    assert _field(replay_a, "receipt_id") == _field(receipt_a, "receipt_id")
    manager_b.close()


def test_tst_m2_p2_009_successful_revision_update_increments_exactly_once(p2_bootstrap_schema: DisposableDatabase) -> None:
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor: cursor.execute("INSERT INTO controlplane.cp_revision_probe VALUES ('probe', 1, 'before')")
    manager = TransactionManager(p2_bootstrap_schema.dsn); adapter = PostgresRevisionedMutationAdapter(manager.unit_of_work)
    assert _field(adapter.mutate(resource_id="probe", expected_revision=1, payload="one"), "revision") == 2
    assert _field(adapter.mutate(resource_id="probe", expected_revision=2, payload="two"), "revision") == 3
    with pytest.raises(RuntimeError):
        with manager.unit_of_work(): adapter.mutate(resource_id="probe", expected_revision=3, payload="rollback"); raise RuntimeError("force rollback")
    barrier = threading.Barrier(2)
    def mutate() -> object: barrier.wait(timeout=5); return adapter.mutate(resource_id="probe", expected_revision=3, payload="race")
    with ThreadPoolExecutor(max_workers=2) as executor: outcomes = list(executor.map(lambda _: mutate(), range(2)))
    assert sum(not isinstance(value, Exception) for value in outcomes) == 1
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor: cursor.execute("SELECT revision FROM controlplane.cp_revision_probe WHERE resource_id = 'probe'"); assert cursor.fetchone()[0] == 4
    manager.close()


def test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision(p2_bootstrap_schema: DisposableDatabase) -> None:
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor: cursor.execute("INSERT INTO controlplane.cp_revision_probe VALUES ('probe', 3, 'before')")
    manager = TransactionManager(p2_bootstrap_schema.dsn); adapter = PostgresRevisionedMutationAdapter(manager.unit_of_work)
    with pytest.raises(RevisionConflictError) as error: adapter.mutate(resource_id="probe", expected_revision=2, payload="after")
    assert error.value.current_revision == 3
    with p2_bootstrap_schema.connect() as connection:
        with connection.cursor() as cursor: cursor.execute("SELECT revision, payload FROM controlplane.cp_revision_probe WHERE resource_id = 'probe'"); assert cursor.fetchone() == (3, "before")
    manager.close()


def test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints(disposable_db: DisposableDatabase) -> None:
    runner = MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True); runner.migrate_up()
    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('controlplane.cp_workspaces')"); assert cursor.fetchone()[0] == "controlplane.cp_workspaces"
            cursor.execute("SELECT to_regclass('controlplane.cp_command_receipts')"); assert cursor.fetchone()[0] == "controlplane.cp_command_receipts"
            cursor.execute("SELECT to_regclass('controlplane.cp_idempotency_records')"); assert cursor.fetchone()[0] == "controlplane.cp_idempotency_records"
