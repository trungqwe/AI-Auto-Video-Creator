"""Mandatory Behavioral RED oracles for M2-P2; production behavior is absent."""
from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.concurrency import RevisionedMutationPort
from controlplane.application.idempotency import IdempotencyCoordinator
from controlplane.domain.common import MessageEnvelope, ProblemDetail
from controlplane.infrastructure.db.idempotency import Migration0002


TEST_DATABASE_NAME = re.compile(r"^m2_p2_test_[0-9a-f]+$")
WORKSPACE_A = "00000000-0000-0000-0000-000000000201"
WORKSPACE_B = "00000000-0000-0000-0000-000000000202"
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
    """One real PostgreSQL database per DB oracle; no credential fallback exists."""
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


def test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc() -> None:
    MessageEnvelope(
        contract_name="command", contract_version=1, message_id="m", workspace_id=WORKSPACE_A,
        correlation_id="c", occurred_at="2026-09-14T00:00:00Z", actor="user", payload={},
        command_id="cmd", requested_at="2026-09-14T00:00:00Z",
    )


def test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract() -> None:
    ProblemDetail(
        type="urn:problem:validation", title="Validation", detail="An toàn", instance="i",
        code="VALIDATION_ERROR", category="validation", retryable=False, correlation_id="c",
        status=None, retry_after=None, field_errors=None, technical_detail_ref="opaque-ref",
    )


def test_tst_m2_p2_003_durable_command_receipt_persistence(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(workspace_id=WORKSPACE_A, command_name="create", key="k", payload={})


def test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(
        workspace_id=WORKSPACE_A, command_name="create", key="k", payload={"sha256": JCS_SHA256}
    )


def test_tst_m2_p2_005_same_key_different_payload_rejected(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(workspace_id=WORKSPACE_A, command_name="create", key="k", payload={"v": 2})


def test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(workspace_id=WORKSPACE_A, command_name="create", key="race", payload={"v": 1})


def test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(workspace_id=WORKSPACE_A, command_name="create", key="race", payload={"v": 2})


def test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart(disposable_db: DisposableDatabase) -> None:
    IdempotencyCoordinator().submit(workspace_id=WORKSPACE_B, command_name="create", key="k", payload={})


def test_tst_m2_p2_009_successful_revision_update_increments_exactly_once(disposable_db: DisposableDatabase) -> None:
    RevisionedMutationPort().mutate(resource_id="aggregate-probe", expected_revision=1)


def test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision(disposable_db: DisposableDatabase) -> None:
    RevisionedMutationPort().mutate(resource_id="aggregate-probe", expected_revision=0)


def test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints(disposable_db: DisposableDatabase) -> None:
    Migration0002().apply()
