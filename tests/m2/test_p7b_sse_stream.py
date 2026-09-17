"""Exact five M2-P7B Behavioral RED oracles; no GREEN implementation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Event
import uuid

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.api.main import create_app
from controlplane.application.session_security import BootstrapCapabilityRegistry
from controlplane.application.sse.stream import SseStreamService
from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.projections.postgres import PostgresOperationStreamRepository
from controlplane.infrastructure.db.sse.postgres import PostgresSseReader
from controlplane.infrastructure.db.uow import TransactionManager


MIGRATIONS = Path(__file__).parents[2] / "src/controlplane/infrastructure/db/migrations"
WORKSPACE_A = "00000000-0000-0000-0000-0000000007b1"
WORKSPACE_B = "00000000-0000-0000-0000-0000000007b2"
ACTOR_A = "00000000-0000-0000-0000-0000000007b3"


@contextmanager
def database():
    admin_dsn = os.environ["M2_TEST_PG_DSN"]
    name = f"m2_p7b_test_{uuid.uuid4().hex}"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "18.6"
        assert admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
                "VALUES (%s,'P7B A','ACTIVE'),(%s,'P7B B','ACTIVE')",
                (WORKSPACE_A, WORKSPACE_B),
            )
            connection.execute(
                "INSERT INTO controlplane.cp_actors"
                "(actor_id,workspace_id,actor_type,display_name,status) "
                "VALUES (%s,%s,'user','P7B','ACTIVE')", (ACTOR_A, WORKSPACE_A),
            )
            connection.commit()
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (name,)).fetchone()[0] == 0


def _event(workspace_id: str, aggregate_id: str) -> DomainEvent:
    return DomainEvent(
        contract_name="controlplane.event.contract", contract_version=11,
        message_id=str(uuid.uuid4()), workspace_id=workspace_id,
        correlation_id="p7b-correlation", causation_id=None, trace_context=None,
        occurred_at="2026-09-17T00:00:00Z", actor="system", recovery_epoch=1,
        payload={"safe": "value"}, event_id=str(uuid.uuid4()),
        event_name="operation.changed", aggregate_type="operation",
        aggregate_id=aggregate_id, aggregate_revision=1, producer="workflow-owner",
        schema_version=1, sensitivity="internal",
    )


def _append(dsn: str, workspace_id: str, aggregate_id: str) -> int:
    with psycopg.connect(dsn) as connection:
        cursor = PostgresOperationStreamRepository(connection).append(
            event=_event(workspace_id, aggregate_id),
        )
        connection.commit()
        return cursor


@contextmanager
def authenticated_app(dsn: str):
    manager = TransactionManager(dsn)
    registry = BootstrapCapabilityRegistry()
    app = create_app(
        manager=manager, allowed_origins={"https://localhost:8443"},
        bootstrap_registry=registry,
    )
    capability = registry.issue(workspace_id=WORKSPACE_A, actor_id=ACTOR_A)
    try:
        with TestClient(app, base_url="https://localhost:8443", raise_server_exceptions=False) as client:
            response = client.post(
                "/v1/session/bootstrap",
                headers={"Origin": "https://localhost:8443", "X-Launch-Capability": capability,
                         "Cookie": "csrf_token=bootstrap", "X-CSRF-Token": "bootstrap"},
            )
            assert response.status_code == 200
            yield client, app, manager
    finally:
        manager.close()


def test_tst_m2_p7b_000_stream_cursor_commit_order_concurrent_writers():
    with database() as dsn:
        release_t1 = Event()
        t1_allocated = Event()
        t2_committed = Event()
        outcome = {}

        def first_writer():
            with psycopg.connect(dsn) as connection:
                outcome["n"] = PostgresOperationStreamRepository(connection).append(
                    event=_event(WORKSPACE_A, "first-aggregate"),
                )
                t1_allocated.set()
                assert release_t1.wait(10), "bounded T1 release timed out"
                connection.commit()

        def second_writer():
            assert t1_allocated.wait(10), "T1 did not allocate cursor"
            with psycopg.connect(dsn) as connection:
                outcome["m"] = PostgresOperationStreamRepository(connection).append(
                    event=_event(WORKSPACE_A, "second-aggregate"),
                )
                connection.commit()
            t2_committed.set()

        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(first_writer)
            second = workers.submit(second_writer)
            try:
                assert t1_allocated.wait(10), "T1 append did not complete"
                inverted = t2_committed.wait(2)
                if inverted:
                    with psycopg.connect(dsn) as reader:
                        seen = reader.execute(
                            "SELECT stream_event_id FROM controlplane.cp_operation_stream "
                            "WHERE workspace_id=%s ORDER BY stream_event_id", (WORKSPACE_A,),
                        ).fetchall()
                        outcome["reader_cursor"] = seen[-1][0]
                        assert seen == [(outcome["m"],)]
                release_t1.set()
                first.result(timeout=10)
                second.result(timeout=10)
            finally:
                release_t1.set()
        if inverted:
            with psycopg.connect(dsn) as reader:
                after = reader.execute(
                    "SELECT stream_event_id FROM controlplane.cp_operation_stream "
                    "WHERE workspace_id=%s AND stream_event_id > %s ORDER BY stream_event_id",
                    (WORKSPACE_A, outcome["reader_cursor"]),
                ).fetchall()
            assert outcome["m"] > outcome["n"]
            assert after == []
        assert not inverted, (
            f"UPSTREAM_INVARIANT_RED: T1 cursor N={outcome['n']} committed late; "
            f"T2 cursor M={outcome['m']} committed first; reader advanced to "
            f"{outcome['reader_cursor']}; replay > M omits late N"
        )


def test_tst_m2_p7b_001_sse_stream_format_and_headers():
    with database() as dsn:
        cursor = _append(dsn, WORKSPACE_A, "format-event")
        with authenticated_app(dsn) as (client, _, _):
            response = client.get(
                "/v1/operations/stream", headers={"Origin": "https://localhost:8443"},
            )
            assert response.status_code != 404, "P7B SSE route was not mounted"
            if response.status_code == 500:
                with psycopg.connect(dsn) as connection:
                    assert connection.execute(
                        "SELECT error_type FROM controlplane.cp_technical_details "
                        "WHERE detail_ref=%s AND workspace_id=%s",
                        (response.json()["technical_detail_ref"], WORKSPACE_A),
                    ).fetchone() == ("NotImplementedError",)
            assert response.status_code == 200, response.text
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert f"id: {cursor}\n" in response.text
            assert "event: operation.changed\n" in response.text
            assert "data: " in response.text


def test_tst_m2_p7b_002_sse_reconnect_with_cursor_delivers_missed_events():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "before-disconnect")
        missed = [_append(dsn, WORKSPACE_A, f"missed-{index}") for index in range(3)]
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT count(*) FROM controlplane.cp_operation_stream WHERE workspace_id=%s",
                (WORKSPACE_A,),
            ).fetchone()[0] == 4
            replay = SseStreamService(PostgresSseReader(connection)).replay_after(
                workspace_id=WORKSPACE_A, cursor=first,
            )
        assert [row.stream_event_id for row in replay] == missed


def test_tst_m2_p7b_003_sse_cursor_expired_triggers_resync_required():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "expired-cursor")
        boundary = _append(dsn, WORKSPACE_A, "retention-boundary")
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_operation_stream_retention_watermarks "
                "(workspace_id,minimum_available_cursor,minimum_available_at) "
                "VALUES (%s,%s,%s)",
                (WORKSPACE_A, boundary, datetime.now(timezone.utc)),
            )
            connection.commit()
            assert connection.execute(
                "SELECT minimum_available_cursor FROM "
                "controlplane.cp_operation_stream_retention_watermarks WHERE workspace_id=%s",
                (WORKSPACE_A,),
            ).fetchone()[0] == boundary
            classification = SseStreamService(PostgresSseReader(connection)).classify_cursor(
                workspace_id=WORKSPACE_A, cursor=first,
            )
        assert classification == "resync_required"


def test_tst_m2_p7b_004_sse_session_workspace_isolation():
    with database() as dsn:
        own = _append(dsn, WORKSPACE_A, "own-event")
        foreign = _append(dsn, WORKSPACE_B, "foreign-event")
        with authenticated_app(dsn) as (client, app, manager):
            denied = client.get(
                "/v1/operations/stream", cookies={"cp_session": ""},
                headers={"Origin": "https://localhost:8443"},
            )
            assert denied.status_code == 403
            with manager.borrow_connection() as connection:
                identity = app.state.session_service.resolve(
                    connection=connection, token=client.cookies["cp_session"],
                )
                assert identity["workspace_id"] == WORKSPACE_A
                page = PostgresSseReader(connection).fetch_workspace_page(
                    workspace_id=identity["workspace_id"], after_cursor=0,
                )
        assert [row.stream_event_id for row in page] == [own]
        assert foreign not in [row.stream_event_id for row in page]
