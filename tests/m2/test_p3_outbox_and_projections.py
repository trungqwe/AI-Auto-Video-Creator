"""The fixed 11 M2-P3 behavioral RED oracles; production behavior is prohibited."""
from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.outbox import OutboxPublisher, OutboxWriter
from controlplane.application.projections import EventConsumer, OperationStreamProjector
from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.migration_runner import MigrationRunner

REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_MIGRATIONS = REPO_ROOT / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
TEST_DATABASE_NAME = re.compile(r"^m2_p3_test_[0-9a-f]+$")
WORKSPACE_ID = "00000000-0000-0000-0000-000000000301"


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
    """One exact real PostgreSQL disposable database per P3 oracle."""
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.")
    name = f"m2_p3_test_{uuid.uuid4().hex}"
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
                cursor.execute("SELECT count(*) FROM pg_database WHERE datname = %s", (name,))
                assert cursor.fetchone()[0] == 0, "disposable database orphaned"


@pytest.fixture
def p3_bootstrap_schema(disposable_db: DisposableDatabase) -> DisposableDatabase:
    """Direct test-only P3 prerequisites; never a production migration proof."""
    with disposable_db.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA controlplane")
            cursor.execute("CREATE TABLE controlplane.cp_workspaces (workspace_id UUID PRIMARY KEY)")
            cursor.execute("INSERT INTO controlplane.cp_workspaces VALUES (%s)", (WORKSPACE_ID,))
            cursor.execute("CREATE TABLE controlplane.p3_business_probe (probe_id TEXT PRIMARY KEY, value TEXT NOT NULL)")
            cursor.execute("CREATE TABLE controlplane.cp_outbox_events (event_id UUID PRIMARY KEY, workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces, payload JSONB NOT NULL, published BOOLEAN NOT NULL DEFAULT false, published_at TIMESTAMPTZ NULL)")
            cursor.execute("CREATE TABLE controlplane.cp_event_checkpoints (consumer_id TEXT NOT NULL, event_id UUID NOT NULL, status TEXT NOT NULL, PRIMARY KEY (consumer_id, event_id))")
            cursor.execute("CREATE TABLE controlplane.cp_event_quarantine (consumer_id TEXT NOT NULL, event_id UUID NOT NULL, workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces, reason_code TEXT NOT NULL, quarantined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (consumer_id, event_id))")
            cursor.execute("CREATE TABLE controlplane.cp_operation_stream (stream_event_id BIGSERIAL PRIMARY KEY, workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, resource_revision BIGINT NOT NULL, event_kind TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, summary TEXT NOT NULL, correlation_id TEXT NOT NULL)")
            cursor.execute("CREATE TABLE controlplane.cp_operation_stream_retention_watermarks (workspace_id UUID PRIMARY KEY REFERENCES controlplane.cp_workspaces, minimum_available_cursor BIGINT NOT NULL, minimum_available_at TIMESTAMPTZ NOT NULL)")
    return disposable_db


def _event(*, revision: int = 1, schema_version: int = 1, recovery_epoch: int | None = 7, payload: dict[str, object] | None = None) -> DomainEvent:
    return DomainEvent(contract_name="controlplane.event.contract", contract_version=11, message_id="message-303", workspace_id=WORKSPACE_ID, correlation_id="correlation-303", causation_id="cause-303", trace_context="trace-303", occurred_at="2026-09-14T00:00:00Z", actor="user:303", recovery_epoch=recovery_epoch, payload=payload or {"safe": "value"}, event_id=str(uuid.uuid4()), event_name="operation.changed", aggregate_type="operation", aggregate_id="operation-303", aggregate_revision=revision, producer="workflow-owner", schema_version=schema_version, sensitivity="internal")


def test_tst_m2_p3_001_production_0003_forward_rollback_and_schema_constraints(disposable_db: DisposableDatabase) -> None:
    MigrationRunner(disposable_db.dsn, PRODUCTION_MIGRATIONS, is_test_env=True).migrate_up()
    assert (PRODUCTION_MIGRATIONS / "0003_outbox_and_projections.sql").is_file(), "P3-001 requires production 0003"
    # GREEN must inspect all five tables, envelope/domain fields and nullability, independent versions,
    # event identity, non-unique aggregate ordering, consumer quarantine key, publish check, stream cursor,
    # P3-only rollback, and surviving P1/P2 tables/tracker versions 1 and 2.


def test_tst_m2_p3_002_business_mutation_and_outbox_atomic_commit_rollback(p3_bootstrap_schema: DisposableDatabase) -> None:
    from controlplane.infrastructure.db.uow import TransactionManager

    manager = TransactionManager(p3_bootstrap_schema.dsn)
    try:
        with manager.unit_of_work() as uow:
            OutboxWriter().enqueue(connection=uow.connection, event=_event())
            uow.connection.execute("INSERT INTO controlplane.p3_business_probe VALUES ('commit', 'yes')")
        with p3_bootstrap_schema.connect() as connection:
            assert connection.execute("SELECT count(*) FROM controlplane.p3_business_probe WHERE probe_id='commit'").fetchone()[0] == 1
        with pytest.raises(RuntimeError):
            with manager.unit_of_work() as uow:
                OutboxWriter().enqueue(connection=uow.connection, event=_event())
                uow.connection.execute("INSERT INTO controlplane.p3_business_probe VALUES ('rollback', 'no')")
                raise RuntimeError("force rollback")
        with p3_bootstrap_schema.connect() as connection:
            assert connection.execute("SELECT count(*) FROM controlplane.p3_business_probe WHERE probe_id='rollback'").fetchone()[0] == 0
    finally:
        manager.close()


def test_tst_m2_p3_003_at_least_once_dispatch_crash_before_published_ack_redispatch(p3_bootstrap_schema: DisposableDatabase) -> None:
    event = _event()
    with p3_bootstrap_schema.connect() as connection:
        connection.execute("INSERT INTO controlplane.cp_outbox_events (event_id, workspace_id, payload) VALUES (%s, %s, '{}'::jsonb)", (event.event_id, WORKSPACE_ID))
    OutboxPublisher().dispatch(event_id=event.event_id, crash_before_ack=True, delivery_observer=[])
    # GREEN: same event dispatches twice across crash/retry; ACK alone sets published and published_at.
    with p3_bootstrap_schema.connect() as connection:
        assert connection.execute("SELECT published, published_at FROM controlplane.cp_outbox_events WHERE event_id=%s", (event.event_id,)).fetchone() == (False, None)


def test_tst_m2_p3_004_consumer_deduplicates_same_event_id(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(), consumer_id="projection")
    # GREEN: second identical event is deduplicated; SQL counts are one checkpoint/effect/stream item.


def test_tst_m2_p3_005_concurrent_consumers_same_event_exactly_one_logical_effect(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(), consumer_id="projection", require_real_postgres_concurrency=True)
    # GREEN: two real connections yield one checkpoint, projection effect, and stream item.


def test_tst_m2_p3_006_checkpoint_projection_atomic_rollback(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(), consumer_id="projection", inject_before_commit=RuntimeError("rollback"))
    # GREEN: rollback leaves no checkpoint/projection/stream effect and clean retry applies.


def test_tst_m2_p3_007_unsupported_schema_durably_quarantined(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(schema_version=999), consumer_id="projection")
    # GREEN: no apply; consumer-scoped durable quarantine is QUARANTINED_UNSUPPORTED_SCHEMA.


def test_tst_m2_p3_008_aggregate_revision_gap_and_out_of_order_blocked(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(revision=2), consumer_id="projection", expected_current_revision=1)
    EventConsumer().process(event=_event(revision=1), consumer_id="projection", expected_current_revision=2)
    EventConsumer().process(event=_event(revision=4), consumer_id="projection", expected_current_revision=2)
    with p3_bootstrap_schema.connect() as connection:
        statuses = connection.execute("SELECT status FROM controlplane.cp_event_checkpoints ORDER BY event_id").fetchall()
        assert "APPLIED" in [status for (status,) in statuses]
        assert any(status in {"GAP_BLOCKED", "SNAPSHOT_REQUIRED"} for (status,) in statuses)


def test_tst_m2_p3_009_stale_recovery_epoch_quarantined(p3_bootstrap_schema: DisposableDatabase) -> None:
    EventConsumer().process(event=_event(recovery_epoch=6), consumer_id="projection", current_recovery_epoch=7)
    # GREEN: event remains historical, projection unchanged, and quarantine reason is STALE_RECOVERY_EPOCH.


def test_tst_m2_p3_010_operation_stream_monotonic_cursor_under_concurrency(p3_bootstrap_schema: DisposableDatabase) -> None:
    OperationStreamProjector().append(event=_event(), require_real_postgres_concurrency=True)
    # GREEN: concurrent rows have unique monotonic stream_event_id, which is exactly the durable cursor.


def test_tst_m2_p3_011_operation_stream_safe_projection_and_payload_policy(p3_bootstrap_schema: DisposableDatabase) -> None:
    OperationStreamProjector().append(event=_event(payload={"unknown_optional": "ok", "open_enum": "FUTURE"}), safe_summary="safe")
    for unsafe_payload, unsafe_summary in (({"password": "redacted"}, "safe"), ({"blob": b"bytes"}, "safe"), ({"safe": "value"}, "Traceback (most recent call last)")):
        with pytest.raises(ValueError):
            OperationStreamProjector().append(event=_event(payload=unsafe_payload), safe_summary=unsafe_summary)
    with p3_bootstrap_schema.connect() as connection:
        row = connection.execute("SELECT stream_event_id, resource_type, resource_id, resource_revision, event_kind, occurred_at, recorded_at, summary, correlation_id FROM controlplane.cp_operation_stream").fetchone()
        assert row is not None and row[0] > 0
