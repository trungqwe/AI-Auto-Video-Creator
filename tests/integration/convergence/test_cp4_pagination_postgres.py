"""CP-4-PAGINATION: phân trang keyset của PostgresControlQueries trên PostgreSQL 18.6 thật, không qua service giả."""
from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.projections.list_query import ListQuery, decode_cursor
from controlplane.infrastructure.db.control_api_queries import PostgresControlQueries
from controlplane.infrastructure.db.migration_runner import MigrationRunner

MIGRATIONS = Path(__file__).parents[3] / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
TEST_DATABASE_NAME = re.compile(r'^cp4_pagination_[0-9a-f]+$')
WORKSPACE_ID = '00000000-0000-0000-0000-0000000004c1'
ROW_COUNT = 230
BASE = '2026-01-01T00:00:00+00:00'
TIMES = '%s::timestamptz + make_interval(secs => (g / 3)::double precision)'


def _seed(connection):
    connection.execute("INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'cp4-pagination', 'ACTIVE')", (WORKSPACE_ID,))
    params = (WORKSPACE_ID, BASE, ROW_COUNT)
    tail = ' FROM generate_series(1, %s) AS g'
    connection.execute("INSERT INTO controlplane.cp_command_receipts (receipt_id, workspace_id, command_id, disposition, operation_id, accepted_at) SELECT gen_random_uuid(), %s, 'cmd-' || lpad(g::text, 4, '0'), 'accepted', gen_random_uuid(), " + TIMES + tail, params)
    connection.execute("INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count, created_at) SELECT 'b-' || lpad(g::text, 4, '0'), %s, 'CREATED', 1, " + TIMES + tail, params)
    connection.execute("INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision, created_at) SELECT 'j-' || lpad(g::text, 4, '0'), 'b-0001', %s, 'CREATED', 'snap-' || g::text, 1, " + TIMES + tail, params)
    connection.execute("INSERT INTO controlplane.cp_config_revisions (config_revision_id, workspace_id, scope_kind, scope_key, config_revision_number, content_hash, payload, status, actor_ref, change_reason, created_at) SELECT gen_random_uuid(), %s, 'workspace', 'cp4', g, repeat('a', 64), '{}'::jsonb, 'DRAFT', 'cp4-test', 'cp4-test', " + TIMES + tail, params)


@pytest.fixture
def seeded_dsn() -> Iterator[str]:
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no skip and no fallback is permitted.')
    try:
        psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5).close()
    except psycopg.OperationalError as exc:
        pytest.fail(f'BLOCKED_EXTERNAL: PostgreSQL test server is unreachable: {exc}')
    name = f'cp4_pagination_{uuid.uuid4().hex}'
    assert TEST_DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute('SHOW server_version').fetchone()[0].startswith('18.6')
        assert admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as connection:
            _seed(connection)
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s', (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


RESOURCES = {
    'operations': {'sort': 'accepted_at', 'id_field': 'receipt_id', 'raw': 'SELECT receipt_id::text, accepted_at FROM controlplane.cp_command_receipts WHERE workspace_id = %s'},
    'batches': {'sort': 'created_at', 'id_field': 'batch_id', 'raw': 'SELECT batch_id, created_at FROM controlplane.cp_production_batches WHERE workspace_id = %s'},
    'jobs': {'sort': 'created_at', 'id_field': 'job_id', 'raw': 'SELECT job_id, created_at FROM controlplane.cp_video_jobs WHERE workspace_id = %s'},
    'configs': {'sort': 'created_at', 'id_field': 'config_revision_id', 'raw': 'SELECT config_revision_id::text, created_at FROM controlplane.cp_config_revisions WHERE workspace_id = %s'},
}


def _expected_rows(connection, resource):
    rows = connection.execute(RESOURCES[resource]['raw'], (WORKSPACE_ID,)).fetchall()
    return sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)


def _walk(queries, resource, limit, direction='desc'):
    pages, cursor = [], None
    while True:
        query = ListQuery(limit=limit, cursor=cursor, sort_key=RESOURCES[resource]['sort'], direction=direction, filters=())
        page = getattr(queries, resource)(workspace_id=WORKSPACE_ID, query=query)
        pages.append(page)
        if page.next_cursor is None:
            return pages
        cursor = decode_cursor(page.next_cursor)
        assert len(pages) <= ROW_COUNT


def _ids(pages, resource):
    return [item[RESOURCES[resource]['id_field']] for page in pages for item in page.items]


@pytest.mark.parametrize('limit', [25, 100])
@pytest.mark.parametrize('resource', list(RESOURCES))
def test_walk_returns_every_row_once_newest_first(seeded_dsn, resource, limit):
    with psycopg.connect(seeded_dsn) as connection:
        expected = _expected_rows(connection, resource)
        pages = _walk(PostgresControlQueries(connection), resource, limit)
    assert len(expected) == ROW_COUNT > 100
    assert len({row[1] for row in expected}) < ROW_COUNT
    assert pages[0].next_cursor is not None
    assert pages[-1].next_cursor is None
    assert all(len(page.items) == limit for page in pages[:-1])
    assert len(pages) == -(-ROW_COUNT // limit)
    got = _ids(pages, resource)
    assert len(got) == len(set(got)) == ROW_COUNT
    assert got == [row[0] for row in expected]
    stamps = [datetime.fromisoformat(item[RESOURCES[resource]['sort']]) for page in pages for item in page.items]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.parametrize('resource', list(RESOURCES))
def test_walk_ascending_is_exact_reverse_of_default_order(seeded_dsn, resource):
    with psycopg.connect(seeded_dsn) as connection:
        expected = _expected_rows(connection, resource)
        pages = _walk(PostgresControlQueries(connection), resource, 100, direction='asc')
    assert pages[-1].next_cursor is None
    assert _ids(pages, resource) == [row[0] for row in reversed(expected)]


@pytest.mark.parametrize('resource', list(RESOURCES))
def test_exact_page_boundary_has_no_next_cursor(seeded_dsn, resource):
    with psycopg.connect(seeded_dsn) as connection:
        queries = PostgresControlQueries(connection)
        whole = _walk(queries, resource, ROW_COUNT)
        short = _walk(queries, resource, ROW_COUNT - 1)
    assert len(whole) == 1 and whole[0].next_cursor is None and len(whole[0].items) == ROW_COUNT
    assert len(short) == 2 and len(short[1].items) == 1 and short[1].next_cursor is None
