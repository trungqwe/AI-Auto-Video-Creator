"""CP-4-QUERIES: truy vấn danh sách trên PostgreSQL 18.6 thật qua PostgresControlQueries, không qua service giả."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
import math
import os
from pathlib import Path
import re
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.projections.list_query import ListQuery, decode_cursor
from controlplane.infrastructure.db import control_api_queries as queries
from controlplane.infrastructure.db.control_api_queries import PostgresControlQueries
from controlplane.infrastructure.db.migration_runner import MigrationRunner

MIGRATIONS = Path(__file__).resolve().parents[3] / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
TEST_DATABASE_NAME = re.compile(r"^cp4_queries_[0-9a-f]+$")
WS_A = "00000000-0000-0000-0000-0000000004d1"
WS_B = "00000000-0000-0000-0000-0000000004d2"
COUNT_A = 230
COUNT_B = 130
BASE = "2026-01-01T00:00:00+00:00"
TIMES = "%s::timestamptz + make_interval(secs => (g / 3)::double precision)"
NINE = ("sources", "articles", "events", "media", "hooks", "stage_runs", "sessions", "logs", "capabilities")


def _seed_workspace(connection: psycopg.Connection, workspace_id: str, count: int, prefix: str) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, 'ACTIVE')",
        (workspace_id, "cp4-queries-" + prefix),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, 'CREATED', 1)",
        ("batch-" + prefix, workspace_id),
    )
    for job in (prefix + "-j1", prefix + "-j2"):
        connection.execute(
            "INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) "
            "VALUES (%s, %s, %s, 'CREATED', 'snap', 1)",
            (job, "batch-" + prefix, workspace_id),
        )
    stage_insert_sql = (
        "INSERT INTO controlplane.cp_stage_runs (stage_run_id, workspace_id, job_id, stage_name, attempt, status, recovery_epoch, execution_generation, created_at, started_at, finished_at) "
        "SELECT 'sr-' || lpad(g::text, 4, '0'), %s, "
        "CASE WHEN mod(g, 2) = 0 THEN %s ELSE %s END, "
        "'script', 1, "
        "CASE mod(g, 3) WHEN 0 THEN 'PENDING' WHEN 1 THEN 'RUNNING' ELSE 'SUCCEEDED' END, "
        "'epoch-1', 0, "
        + TIMES + ", "
        + "CASE WHEN mod(g, 3) = 0 THEN NULL ELSE " + TIMES + " END, "
        + "NULL FROM generate_series(1, %s) AS g"
    )
    connection.execute(
        stage_insert_sql,
        (workspace_id, prefix + "-j2", prefix + "-j1", BASE, BASE, count),
    )


def _seed_all(connection: psycopg.Connection) -> None:
    _seed_workspace(connection, WS_A, COUNT_A, "a")
    _seed_workspace(connection, WS_B, COUNT_B, "b")


@pytest.fixture
def seeded_dsn() -> Iterator[str]:
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no skip and no fallback is permitted.")
    try:
        psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5).close()
    except psycopg.OperationalError as exc:
        pytest.fail(f"BLOCKED_EXTERNAL: PostgreSQL test server is unreachable: {exc}")
    name = f"cp4_queries_{uuid.uuid4().hex}"
    assert TEST_DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].startswith("18.6")
        assert admin.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user").fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as connection:
            _seed_all(connection)
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _walk(
    repo: PostgresControlQueries,
    workspace_id: str,
    limit: int,
    direction: str = "desc",
    filters: tuple[tuple[str, str], ...] = (),
) -> list[queries.Page]:
    pages = []
    cursor = None
    while True:
        assert len(pages) <= 300
        query = ListQuery(limit=limit, cursor=cursor, sort_key="created_at", direction=direction, filters=filters)
        page = repo.stage_runs(workspace_id=workspace_id, query=query)
        pages.append(page)
        if page.next_cursor is None:
            return pages
        cursor = decode_cursor(page.next_cursor)


def _expected(connection: psycopg.Connection, workspace_id: str) -> list[tuple[str, datetime]]:
    rows = connection.execute(
        "SELECT stage_run_id, created_at FROM controlplane.cp_stage_runs WHERE workspace_id = %s",
        (workspace_id,),
    ).fetchall()
    return sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)


@pytest.mark.parametrize("limit", [25, 100])
def test_walk_every_row_once_newest_first(seeded_dsn: str, limit: int):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        pages = _walk(repo, WS_A, limit)
        expected = _expected(connection, WS_A)
        assert len(expected) == COUNT_A
        assert COUNT_A > 100
        distinct_created = {row[1] for row in expected}
        assert len(distinct_created) < COUNT_A
        num_pages = math.ceil(COUNT_A / limit)
        assert len(pages) == num_pages
        for p in pages[:-1]:
            assert len(p.items) == limit
        assert pages[-1].next_cursor is None
        all_items = [item for p in pages for item in p.items]
        collected_ids = [item["stage_run_id"] for item in all_items]
        expected_ids = [row[0] for row in expected]
        assert collected_ids == expected_ids
        assert len(set(collected_ids)) == COUNT_A
        for item in all_items:
            assert item["stage"] == "script"
            assert "stage_name" not in item
            if item["status"] == "PENDING":
                assert item["started_at"] is None
            elif item["status"] == "RUNNING":
                assert isinstance(item["started_at"], str)


def test_walk_ascending_is_exact_reverse(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        pages = _walk(repo, WS_A, limit=100, direction="asc")
        expected = _expected(connection, WS_A)
        collected_ids = [item["stage_run_id"] for p in pages for item in p.items]
        expected_reversed = [row[0] for row in reversed(expected)]
        assert collected_ids == expected_reversed


def test_exact_boundary_has_no_next_cursor(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        pages_all = _walk(repo, WS_A, limit=COUNT_A)
        assert len(pages_all) == 1
        assert pages_all[0].next_cursor is None
        assert len(pages_all[0].items) == COUNT_A

        pages_split = _walk(repo, WS_A, limit=COUNT_A - 1)
        assert len(pages_split) == 2
        assert len(pages_split[0].items) == COUNT_A - 1
        assert len(pages_split[1].items) == 1
        assert pages_split[1].next_cursor is None


def test_workspaces_are_isolated(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        pages_a = _walk(repo, WS_A, limit=100)
        items_a = [item for p in pages_a for item in p.items]
        assert len(items_a) == COUNT_A
        assert all(item["job_id"].startswith("a-") for item in items_a)

        pages_b = _walk(repo, WS_B, limit=100)
        items_b = [item for p in pages_b for item in p.items]
        assert len(items_b) == COUNT_B
        assert COUNT_B > 100
        assert all(item["job_id"].startswith("b-") for item in items_b)

        pages_a_25 = _walk(repo, WS_A, limit=25)
        cursor_a = decode_cursor(pages_a_25[0].next_cursor)
        query_b_with_a_cursor = ListQuery(limit=100, cursor=cursor_a, sort_key="created_at", direction="desc", filters=())
        page_b_cross = repo.stage_runs(workspace_id=WS_B, query=query_b_with_a_cursor)
        assert all(item["job_id"].startswith("b-") for item in page_b_cross.items)

        query_cross_filter = ListQuery(limit=100, cursor=None, sort_key="created_at", direction="desc", filters=(("job_id", "a-j1"),))
        page_b_filter = repo.stage_runs(workspace_id=WS_B, query=query_cross_filter)
        assert len(page_b_filter.items) == 0


def test_filters_match_sql(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        pages_running = _walk(repo, WS_A, limit=25, filters=(("status", "RUNNING"),))
        items_running = [item for p in pages_running for item in p.items]
        count_db = connection.execute(
            "SELECT count(*) FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND status = 'RUNNING'",
            (WS_A,),
        ).fetchone()[0]
        assert len(items_running) == count_db
        assert all(item["status"] == "RUNNING" for item in items_running)

        pages_job = _walk(repo, WS_A, limit=25, filters=(("job_id", "a-j1"),))
        items_job = [item for p in pages_job for item in p.items]
        assert len(items_job) > 0
        assert all(item["job_id"] == "a-j1" for item in items_job)


def test_ready_spec_columns_exist_in_information_schema(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        for name, spec in queries.LIST_SPECS.items():
            schema, table = spec.table.split(".")
            rows = connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                (schema, table),
            ).fetchall()
            columns = {row[0] for row in rows}
            assert set(spec.select_columns).issubset(columns)
            assert set(spec.filter_columns).issubset(columns)
            assert {spec.id_column}.issubset(columns)
            assert set(spec.sort_columns).issubset(columns)


def test_blocked_gaps_are_real(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        assert (set(queries.LIST_SPECS) | set(queries.BLOCKED_LIST_RESOURCES)) == set(NINE)
        assert not (set(queries.LIST_SPECS) & set(queries.BLOCKED_LIST_RESOURCES))
        for name, (table, missing) in queries.BLOCKED_LIST_RESOURCES.items():
            if table is not None:
                schema, tbl = table.split(".")
                table_exists = connection.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                    (schema, tbl),
                ).fetchone()
                assert table_exists is not None
                rows = connection.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                    (schema, tbl),
                ).fetchall()
                cols = {row[0] for row in rows}
                for m in missing:
                    assert m not in cols
            else:
                if missing:
                    for m in missing:
                        col_in_cp = connection.execute(
                            "SELECT 1 FROM information_schema.columns WHERE table_schema = 'controlplane' AND column_name = %s",
                            (m,),
                        ).fetchone()
                        assert col_in_cp is None
                else:
                    row_cap = connection.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'controlplane' AND position('capabilit' in table_name) > 0"
                    ).fetchall()
                    assert row_cap == []


def test_blocked_methods_raise_on_real_connection(seeded_dsn: str):
    with psycopg.connect(seeded_dsn) as connection:
        repo = PostgresControlQueries(connection)
        for n in NINE:
            if n == "stage_runs":
                continue
            with pytest.raises(CapabilityUnavailableError):
                getattr(repo, n)(
                    workspace_id=WS_A,
                    query=ListQuery(limit=1, cursor=None, sort_key="created_at", direction="desc", filters=()),
                )