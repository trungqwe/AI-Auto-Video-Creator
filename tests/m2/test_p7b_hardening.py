"""Independent P7B GREEN hardening catalogue H01–H38."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
from threading import Event
import time

from fastapi.testclient import TestClient
import httpx
import psycopg
import pytest

from controlplane.api.main import create_app
from controlplane.api.sse.stream import SseStreamPresenter, router as sse_router
from controlplane.api.tls import start_loopback_tls_server
from controlplane.application.session_security import BootstrapBinding, SessionSecurityService
from controlplane.application.sse.stream import SseStreamService, parse_cursor
from controlplane.infrastructure.db.projections.postgres import PostgresOperationStreamRepository
from controlplane.infrastructure.db.session_security import PostgresSessionRepository
from controlplane.infrastructure.db.sse.postgres import PostgresSseReader
from controlplane.infrastructure.db.uow import TransactionManager
from tests.m2.test_p7b_sse_stream import (
    ACTOR_A, WORKSPACE_A, WORKSPACE_B, _append, _event,
    authenticated_app, database,
)


def _reader(dsn: str) -> tuple[psycopg.Connection, PostgresSseReader]:
    connection = psycopg.connect(dsn)
    return connection, PostgresSseReader(connection)


def _https_session(dsn: str):
    manager = TransactionManager(dsn)
    with manager.unit_of_work() as uow:
        _, token = SessionSecurityService(PostgresSessionRepository).create(
            connection=uow.connection,
            binding=BootstrapBinding(WORKSPACE_A, ACTOR_A,
                                     datetime.now(timezone.utc) + timedelta(seconds=60)),
        )
    return manager, token


def _first_frame(lines):
    frame = []
    for line in lines:
        if line:
            frame.append(line)
        elif any(value.startswith("data: ") for value in frame):
            return frame
        else:
            frame = []
    raise AssertionError("SSE stream closed before data frame")


def _route_response(client: TestClient, cursor: str | None = None, **headers):
    params = {} if cursor is None else {"cursor": cursor}
    return client.get("/v1/operations/stream", params=params, headers=headers)


def test_h01_actual_route_mounted():
    app = create_app()
    assert any(getattr(route, "original_router", None) is sse_router for route in app.routes)
    assert any(route.path == "/v1/operations/stream" and "GET" in route.methods
               for route in sse_router.routes)


def test_h02_event_stream_headers():
    with database() as dsn:
        baseline = _append(dsn, WORKSPACE_A, "h02-baseline")
        _append(dsn, WORKSPACE_A, "h02-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                       params={"cursor": str(baseline)}, cookies={"cp_session": token}) as response:
                        assert response.status_code == 200
                        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                        assert response.headers["cache-control"] == "no-cache, no-transform"
                        assert response.headers["x-accel-buffering"] == "no"
                        assert _first_frame(response.iter_lines())
        finally:
            manager.close()


def test_h03_utf8_compact_framing():
    with database() as dsn:
        cursor = _append(dsn, WORKSPACE_A, "h03")
        with psycopg.connect(dsn) as connection:
            row = PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=WORKSPACE_A, after_cursor=0)[0]
        frame = SseStreamPresenter._event_frame(row)
        assert frame.startswith(f"id: {cursor}\nevent: operation.changed\ndata: {{")
        assert frame.endswith("\n\n")
        payload = json.loads(frame.split("data: ", 1)[1])
        assert payload["cursor"] == str(cursor)
        assert json.dumps(payload, ensure_ascii=False, separators=(",", ":")) in frame


def test_h04_authenticated_workspace_binding():
    with database() as dsn, authenticated_app(dsn) as (client, app, manager):
        with manager.borrow_connection() as connection:
            identity = app.state.session_service.resolve(
                connection=connection, token=client.cookies["cp_session"])
        assert identity["workspace_id"] == WORKSPACE_A
        assert _route_response(client, "1", Origin="https://localhost:8443").status_code in {200, 409}


def test_h05_foreign_workspace_excluded():
    with database() as dsn:
        own = _append(dsn, WORKSPACE_A, "h05-own")
        foreign = _append(dsn, WORKSPACE_B, "h05-foreign")
        with psycopg.connect(dsn) as connection:
            rows = PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=WORKSPACE_A, after_cursor=0)
        assert [row.stream_event_id for row in rows] == [own]
        assert foreign not in [row.stream_event_id for row in rows]


def test_h06_monotonic_workspace_cursors():
    with database() as dsn:
        cursors = [_append(dsn, WORKSPACE_A, f"h06-{index}") for index in range(5)]
        assert cursors == sorted(set(cursors))


def test_h07_reconnect_exclusive_replay():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h07-first")
        expected = [_append(dsn, WORKSPACE_A, f"h07-{index}") for index in range(3)]
        with psycopg.connect(dsn) as connection:
            rows = SseStreamService(PostgresSseReader(connection)).replay_after(
                workspace_id=WORKSPACE_A, cursor=first)
        assert [row.stream_event_id for row in rows] == expected


def test_h08_expired_cursor_exact_resync_close():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h08-old")
        boundary = _append(dsn, WORKSPACE_A, "h08-boundary")
        with psycopg.connect(dsn) as connection:
            connection.execute("INSERT INTO controlplane.cp_operation_stream_retention_watermarks "
                               "(workspace_id,minimum_available_cursor,minimum_available_at) "
                               "VALUES (%s,%s,CURRENT_TIMESTAMP)", (WORKSPACE_A, boundary))
            connection.commit()
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                       params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                        body = response.read().decode("utf-8")
                        assert response.status_code == 200
                        assert body == ('event: resync_required\n'
                                        'data: {"resync_required":true,"reason":"cursor_expired",'
                                        '"action":"query_resource_snapshots"}\n\n')
                        assert "id:" not in body
        finally:
            manager.close()


def _invalid_cursor_case(bad):
    with pytest.raises(ValueError, match="INVALID_CURSOR"):
        parse_cursor(bad)


def test_h09_malformed_cursor():
    for bad in ("0", "01", "+1", "-1", " 1", "1 ", "１", "9223372036854775808"):
        _invalid_cursor_case(bad)


def test_h10_query_header_mismatch():
    with database() as dsn, authenticated_app(dsn) as (client, _, _):
        _append(dsn, WORKSPACE_A, "h10-a")
        _append(dsn, WORKSPACE_A, "h10-b")
        response = _route_response(client, "1", Origin="https://localhost:8443", **{"Last-Event-ID": "2"})
        assert response.status_code == 400 and response.json()["code"] == "CURSOR_MISMATCH"


def test_h11_future_cursor_safe_conflict():
    with database() as dsn, authenticated_app(dsn) as (client, _, _):
        response = _route_response(client, "9223372036854775807", Origin="https://localhost:8443")
        assert response.status_code == 409 and response.json()["code"] == "CURSOR_AHEAD"


def test_h12_foreign_cursor_safe_conflict():
    with database() as dsn:
        _append(dsn, WORKSPACE_A, "h12-own")
        foreign = _append(dsn, WORKSPACE_B, "h12-foreign")
        _append(dsn, WORKSPACE_A, "h12-later")
        with authenticated_app(dsn) as (client, _, _):
            response = _route_response(client, str(foreign), Origin="https://localhost:8443")
        assert response.status_code == 409 and response.json()["code"] == "UNKNOWN_CURSOR"


def test_h13_get_only_no_mutation():
    with database() as dsn, authenticated_app(dsn) as (client, _, _):
        before = 0
        response = client.post("/v1/operations/stream", headers={"Origin": "https://localhost:8443"})
        with psycopg.connect(dsn) as connection:
            after = connection.execute("SELECT count(*) FROM controlplane.cp_operation_stream").fetchone()[0]
        assert response.status_code in {403, 405, 422} and after == before


def test_h14_safe_projection_allowlist():
    with database() as dsn:
        _append(dsn, WORKSPACE_A, "h14")
        with psycopg.connect(dsn) as connection:
            row = PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=WORKSPACE_A, after_cursor=0)[0]
        payload = json.loads(SseStreamPresenter._event_frame(row).split("data: ", 1)[1])
        assert set(payload) == {"cursor", "resource_type", "resource_id", "resource_revision",
                                "event_kind", "occurred_at", "recorded_at", "summary", "correlation_id"}


def test_h15_no_secret_or_stack_surface():
    with database() as dsn:
        _append(dsn, WORKSPACE_A, "h15")
        with psycopg.connect(dsn) as connection:
            row = PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=WORKSPACE_A, after_cursor=0)[0]
        frame = SseStreamPresenter._event_frame(row).lower()
        assert not any(value in frame for value in ("password", "token", "secret", "traceback", "payload"))


def test_h16_concurrent_https_clients():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h16-first")
        second = _append(dsn, WORKSPACE_A, "h16-second")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                def receive():
                    with httpx.Client(verify=context, timeout=5) as client:
                        with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                           params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                            assert response.status_code == 200
                            return _first_frame(response.iter_lines())[0]
                with ThreadPoolExecutor(max_workers=2) as workers:
                    assert list(workers.map(lambda _: receive(), range(2))) == [f"id: {second}"] * 2
        finally:
            manager.close()


def test_h17_abrupt_disconnect_releases_client_slot():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h17-first")
        _append(dsn, WORKSPACE_A, "h17-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    url = f"https://localhost:{endpoint.port}/v1/operations/stream"
                    for _ in range(3):
                        with client.stream("GET", url, params={"cursor": str(first)},
                                           cookies={"cp_session": token}) as response:
                            assert response.status_code == 200
                            assert _first_frame(response.iter_lines())
        finally:
            manager.close()


def test_h18_bounded_limit_100_and_query_plan():
    with database() as dsn, psycopg.connect(dsn) as connection:
        connection.execute(
            "INSERT INTO controlplane.cp_workspaces(workspace_id,name,status) "
            "SELECT ('10000000-0000-0000-0000-'||lpad(g::text,12,'0'))::uuid,"
            "'H18 '||g,'ACTIVE' FROM generate_series(1,98) g")
        connection.execute(
            "INSERT INTO controlplane.cp_operation_stream "
            "(workspace_id,resource_type,resource_id,resource_revision,event_kind,occurred_at,summary,correlation_id) "
            "SELECT CASE WHEN mod(g,99)=0 THEN %s::uuid ELSE "
            "('10000000-0000-0000-0000-'||lpad((mod(g,98)+1)::text,12,'0'))::uuid END,"
            "'operation',g::text,1,'operation.changed',CURRENT_TIMESTAMP,'safe','h18' "
            "FROM generate_series(1,100000) g", (WORKSPACE_A,))
        connection.execute("ANALYZE controlplane.cp_operation_stream")
        connection.commit()
        query = (
            "SELECT stream_event_id,resource_type,resource_id,resource_revision,event_kind,"
            "occurred_at,recorded_at,summary,correlation_id "
            "FROM controlplane.cp_operation_stream "
            "WHERE workspace_id=%s AND stream_event_id>%s "
            "ORDER BY stream_event_id ASC LIMIT 100"
        )
        for workspace, cursor, expected_count in ((WORKSPACE_B, 0, 0),
                                                  (WORKSPACE_A, 50000, 100)):
            plan = connection.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query,
                                      (workspace, cursor)).fetchone()[0][0]["Plan"]
            scan = plan["Plans"][0]
            assert plan["Node Type"] == "Limit"
            assert scan["Node Type"] == "Index Scan"
            assert scan["Index Name"] == "cp_operation_stream_workspace_cursor_idx"
            assert "workspace_id =" in scan["Index Cond"]
            assert "stream_event_id >" in scan["Index Cond"]
            assert scan.get("Rows Removed by Filter", 0) == 0
            assert scan["Actual Rows"] == expected_count
            rows = PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=workspace, after_cursor=cursor)
            assert len(rows) == expected_count
            assert [row.stream_event_id for row in rows] == sorted(row.stream_event_id for row in rows)


def test_h19_no_unbounded_thread_growth():
    import threading
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h19-first")
        _append(dsn, WORKSPACE_A, "h19-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                baseline = threading.active_count()
                with httpx.Client(verify=context, timeout=5) as client:
                    for _ in range(3):
                        with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                           params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                            assert _first_frame(response.iter_lines())
                time.sleep(0.2)
                assert threading.active_count() <= baseline + 4
        finally:
            manager.close()


def test_h20_no_borrowed_connection_after_yield():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h20-first")
        _append(dsn, WORKSPACE_A, "h20-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                       params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                        assert _first_frame(response.iter_lines())
                        with psycopg.connect(dsn) as connection:
                            active = connection.execute(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname=current_database() AND state='active' "
                                "AND query LIKE 'SELECT stream_event_id, resource_type%'").fetchone()[0]
                        assert active == 0
        finally:
            manager.close()


def test_h21_real_p7a_https_ca_verified():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h21-first")
        _append(dsn, WORKSPACE_A, "h21-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=5) as client:
                    with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                       params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                        assert response.status_code == 200 and _first_frame(response.iter_lines())
        finally:
            manager.close()


def test_h22_host_validation_precedes_stream():
    with database() as dsn, authenticated_app(dsn) as (client, _, _):
        response = client.get("/v1/operations/stream", headers={"Host": "evil.example"})
        assert response.status_code == 403


def test_h23_origin_validation_precedes_stream():
    with database() as dsn, authenticated_app(dsn) as (client, _, _):
        response = client.get("/v1/operations/stream", headers={"Origin": "https://evil.example"})
        assert response.status_code == 403


def test_h24_session_revocation_closes_live_stream():
    with database() as dsn:
        first = _append(dsn, WORKSPACE_A, "h24-first")
        _append(dsn, WORKSPACE_A, "h24-next")
        manager, token = _https_session(dsn)
        try:
            with start_loopback_tls_server(manager=manager) as endpoint:
                context = ssl.create_default_context(cadata=endpoint.ca_certificate_pem)
                with httpx.Client(verify=context, timeout=40) as client:
                    with client.stream("GET", f"https://localhost:{endpoint.port}/v1/operations/stream",
                                       params={"cursor": str(first)}, cookies={"cp_session": token}) as response:
                        lines = iter(response.iter_lines())
                        assert _first_frame(lines)
                        with psycopg.connect(dsn) as connection:
                            connection.execute("UPDATE controlplane.cp_auth_sessions SET status='REVOKED' "
                                               "WHERE workspace_id=%s", (WORKSPACE_A,))
                            connection.commit()
                        remaining = list(lines)
                        assert all(not line.startswith("id: ") for line in remaining)
        finally:
            manager.close()


_REGRESSION_SUITES = {
    "p7a_oracle": ("tests/m2/test_p7a_control_api_security.py", 4),
    "p7a_hardening": ("tests/m2/test_p7a_hardening.py", 36),
    "p6": ("tests/m2/test_p6_orchestration_shell.py", 4),
    "p5b": ("tests/m2/test_p5b_artifact_metadata.py", 5),
    "p5a": ("tests/m2/test_p5a_config_and_secrets.py", 5),
    "p4": ("tests/m2/test_p4_statemachines.py", 9),
    "p3": ("tests/m2/test_p3_outbox_and_projections.py", 11),
    "p2": ("tests/m2/test_p2_envelopes_and_idempotency.py", 11),
    "p1": ("tests/m2/test_p1_db_and_workspace.py", 11),
    "p0": (("tests/m2/test_p0_architecture_rules.py",
            "tests/m2/test_p0_evidence_validator.py",
            "tests/m2/test_p0_packaging.py"), 33),
    "architecture": ("tests/m2/test_p0_architecture_rules.py", 6),
    "m1": ("tests/m1", 93),
}


def _run_regression(name: str) -> None:
    path, expected = _REGRESSION_SUITES[name]
    paths = (path,) if isinstance(path, str) else path
    runtime = (Path(".venv/Scripts/python.exe") if name == "m1" else Path(sys.executable))
    root = Path(__file__).parents[2]
    historical_evidence = root / "docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json"
    original_evidence = historical_evidence.read_bytes() if name == "m1" else None
    try:
        result = subprocess.run(
            [str(runtime), "-m", "pytest", "-q", "-rN", *paths],
            cwd=root, env=os.environ.copy(),
            capture_output=True, text=True, timeout=600, check=False,
        )
    finally:
        if original_evidence is not None and historical_evidence.read_bytes() != original_evidence:
            historical_evidence.write_bytes(original_evidence)
            assert historical_evidence.read_bytes() == original_evidence
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]
    assert re.search(rf"\b{expected} passed\b", result.stdout), result.stdout[-3000:]
    assert not re.search(r"\b[1-9][0-9]* (?:failed|error|skipped)\b", result.stdout)


def test_h25_accepted_p7a_oracle_regression():
    _run_regression("p7a_oracle")


def test_h26_accepted_p7a_hardening_regression():
    _run_regression("p7a_hardening")


def test_h27_accepted_p6_regression():
    _run_regression("p6")


def test_h28_accepted_p5b_regression():
    _run_regression("p5b")


def test_h29_accepted_p5a_regression():
    _run_regression("p5a")


def test_h30_accepted_p4_regression():
    _run_regression("p4")


def test_h31_accepted_p3_regression():
    _run_regression("p3")


def test_h32_accepted_p2_regression():
    _run_regression("p2")


def test_h33_accepted_p1_regression():
    _run_regression("p1")


def test_h34_accepted_p0_regression():
    _run_regression("p0")


def test_h35_architecture_regression():
    _run_regression("architecture")


def test_h36_m1_regression():
    _run_regression("m1")


def test_h37_concurrent_two_writer_commit_order_no_loss():
    for iteration in range(3):
        with database() as dsn:
            first_allocated = Event()
            second_started = Event()
            release_first = Event()
            outcome: dict[str, int] = {}

            def first_writer():
                with psycopg.connect(dsn) as connection:
                    outcome["first"] = PostgresOperationStreamRepository(connection).append(
                        event=_event(WORKSPACE_A, f"h37-first-{iteration}"))
                    first_allocated.set()
                    assert release_first.wait(10)
                    connection.commit()

            def second_writer():
                assert first_allocated.wait(10)
                with psycopg.connect(dsn) as connection:
                    outcome["second_pid"] = connection.execute("SELECT pg_backend_pid()").fetchone()[0]
                    second_started.set()
                    outcome["second"] = PostgresOperationStreamRepository(connection).append(
                        event=_event(WORKSPACE_A, f"h37-second-{iteration}"))
                    connection.commit()

            with ThreadPoolExecutor(max_workers=2) as workers:
                one = workers.submit(first_writer)
                two = workers.submit(second_writer)
                try:
                    assert second_started.wait(10)
                    with psycopg.connect(dsn) as observer:
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            wait_type = observer.execute(
                                "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                                (outcome["second_pid"],)).fetchone()[0]
                            observer.commit()
                            if wait_type == "Lock":
                                break
                            time.sleep(0.02)
                        assert wait_type == "Lock", "T2 did not block at transaction fence"
                        sequence = observer.execute(
                            "SELECT last_value FROM controlplane.cp_operation_stream_stream_event_id_seq"
                        ).fetchone()[0]
                        assert sequence == outcome["first"], "T2 allocated before fence release"
                        assert observer.execute(
                            "SELECT count(*) FROM controlplane.cp_operation_stream WHERE workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0] == 0
                    with psycopg.connect(dsn, autocommit=True) as other:
                        foreign = PostgresOperationStreamRepository(other).append(
                            event=_event(WORKSPACE_B, f"h37-foreign-{iteration}"))
                        assert foreign > outcome["first"]
                finally:
                    release_first.set()
                one.result(timeout=10)
                two.result(timeout=10)
            with psycopg.connect(dsn) as reader:
                rows = PostgresSseReader(reader).fetch_workspace_page(
                    workspace_id=WORKSPACE_A, after_cursor=0)
                replay = PostgresSseReader(reader).fetch_workspace_page(
                    workspace_id=WORKSPACE_A, after_cursor=outcome["first"])
            assert [row.stream_event_id for row in rows] == [outcome["first"], outcome["second"]]
            assert [row.stream_event_id for row in replay] == [outcome["second"]]

    with database() as dsn:
        with psycopg.connect(dsn) as connection:
            aborted = PostgresOperationStreamRepository(connection).append(
                event=_event(WORKSPACE_A, "h37-rollback"))
            connection.rollback()
        committed = _append(dsn, WORKSPACE_A, "h37-after-rollback")
        assert committed > aborted
        with psycopg.connect(dsn) as connection:
            assert [row.stream_event_id for row in PostgresSseReader(connection).fetch_workspace_page(
                workspace_id=WORKSPACE_A, after_cursor=0)] == [committed]


def test_h38_p3_autocommit_and_uow_append_compatibility():
    with database() as dsn:
        with psycopg.connect(dsn, autocommit=True) as connection:
            first = PostgresOperationStreamRepository(connection).append(
                event=_event(WORKSPACE_A, "h38-autocommit"), safe_summary="safe")
            assert connection.execute(
                "SELECT summary FROM controlplane.cp_operation_stream WHERE stream_event_id=%s",
                (first,)).fetchone()[0] == "safe"
        manager = TransactionManager(dsn)
        release = Event()
        allocated = Event()
        second_started = Event()
        outcome: dict[str, int] = {}

        def uow_writer():
            with manager.unit_of_work() as uow:
                outcome["uow"] = PostgresOperationStreamRepository(uow.connection).append(
                    event=_event(WORKSPACE_A, "h38-uow"))
                allocated.set()
                assert release.wait(10)

        def autocommit_writer():
            assert allocated.wait(10)
            with psycopg.connect(dsn, autocommit=True) as connection:
                outcome["second_pid"] = connection.execute("SELECT pg_backend_pid()").fetchone()[0]
                second_started.set()
                outcome["autocommit"] = PostgresOperationStreamRepository(connection).append(
                    event=_event(WORKSPACE_A, "h38-after-uow"))

        try:
            with ThreadPoolExecutor(max_workers=2) as workers:
                one = workers.submit(uow_writer)
                two = workers.submit(autocommit_writer)
                assert second_started.wait(10)
                with psycopg.connect(dsn) as observer:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        wait_type = observer.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                            (outcome["second_pid"],)).fetchone()[0]
                        observer.commit()
                        if wait_type == "Lock":
                            break
                        time.sleep(0.02)
                    assert wait_type == "Lock"
                    assert observer.execute(
                        "SELECT last_value FROM controlplane.cp_operation_stream_stream_event_id_seq"
                    ).fetchone()[0] == outcome["uow"]
                release.set()
                one.result(timeout=10)
                two.result(timeout=10)
            assert first < outcome["uow"] < outcome["autocommit"]
        finally:
            release.set()
            manager.close()
