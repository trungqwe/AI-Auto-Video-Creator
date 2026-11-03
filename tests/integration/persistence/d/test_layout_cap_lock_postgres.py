'''PRS-LAYOUT-QUOTA-FIX1: khoá tư vấn theo lô của creative.adapters.batch_layout_usage trên PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test.

Hai unit of work của hai job cùng lô lưu kế hoạch cùng lúc: unit thứ hai chờ ở locked_usage tới khi unit thứ nhất commit, rồi thấy kế hoạch
vừa commit, nên phép kiểm trần lúc lưu không bao giờ dùng số cũ. Unit của lô khác không chờ.

coveredIds: FR-PRS-005
'''
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from creative.persistence import PostgresCreativeUnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
DATABASE_NAME = re.compile(r'^layout_cap_[0-9a-f]+$')
WORKSPACE = '00000000-0000-0000-0000-00000000d0f1'
WAIT_SECONDS = 0.7


@pytest.fixture
def dsn():
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.')
    name = f'layout_cap_{uuid.uuid4().hex}'
    assert DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if not admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]:
            pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.')
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    target = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(target, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(target, autocommit=True) as connection:
            connection.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (WORKSPACE, 'w', 'ACTIVE'))
            for batch, size in (('batch-a', 5), ('batch-b', 5)):
                connection.execute(
                    'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
                    (batch, WORKSPACE, 'RUNNING', size))
            for job, batch, status in (
                ('batch-a:job:1', 'batch-a', 'ACTIVE'), ('batch-a:job:2', 'batch-a', 'ACTIVE'), ('batch-a:job:3', 'batch-a', 'ACTIVE'),
                ('batch-a:job:4', 'batch-a', 'FAILED_FINAL'), ('batch-b:job:1', 'batch-b', 'ACTIVE'),
            ):
                connection.execute(
                    'INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, 1)',
                    (job, batch, WORKSPACE, status, 'snap'))
            _insert_plan(connection, 'plan:batch-a:job:3:r1', 'SPLIT_STACK')
            _insert_plan(connection, 'plan:batch-a:job:3:r2', 'HERO_STRIP')
            _insert_plan(connection, 'plan:batch-a:job:4:r1', 'HERO_STRIP')
        yield target
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()', (name,))
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))


def _insert_plan(connection, plan_id, layout_key):
    connection.execute(
        'INSERT INTO controlplane.cp_production_plans (workspace_id, record_key, revision, payload, production_plan_id) '
        'VALUES (%s, %s, 1, %s::jsonb, %s)',
        (WORKSPACE, plan_id, json.dumps({'layout_choice': {'layout_key': layout_key}}), plan_id))


def test_a_second_plan_of_the_batch_waits_for_the_first_commit_and_counts_it(dsn):
    manager = TransactionManager(dsn, pool_max_size=4)
    try:
        first = PostgresCreativeUnitOfWork(manager, workspace_id=WORKSPACE)
        first.begin()
        # Job 3 holds HERO_STRIP (its latest plan); job 4 failed and is left out.
        assert first.layout_usage.locked_usage('plan:batch-a:job:1:r1') == ({'HERO_STRIP': 1}, 5)
        _insert_plan(first._require_connection(), 'plan:batch-a:job:1:r1', 'HERO_STRIP')
        seen = {}

        def second_plan():
            unit = PostgresCreativeUnitOfWork(manager, workspace_id=WORKSPACE)
            with unit:
                seen['usage'] = unit.layout_usage.locked_usage('plan:batch-a:job:2:r1')
                unit.rollback()

        def other_batch():
            unit = PostgresCreativeUnitOfWork(manager, workspace_id=WORKSPACE)
            with unit:
                seen['other'] = unit.layout_usage.locked_usage('plan:batch-b:job:1:r1')
                unit.rollback()

        waiting = threading.Thread(target=second_plan)
        waiting.start()
        free = threading.Thread(target=other_batch)
        free.start()
        free.join(10)
        assert seen.get('other') == ({}, 5), 'a plan of another batch must not wait for this batch'
        waiting.join(WAIT_SECONDS)
        assert waiting.is_alive() and 'usage' not in seen, 'the second plan of the batch must wait for the batch lock'
        first.commit()
        waiting.join(10)
        assert not waiting.is_alive()
        assert seen['usage'] == ({'HERO_STRIP': 2}, 5), 'after the lock the count includes the plan committed by the first unit'
    finally:
        manager.close()


def test_plan_ids_without_a_job_or_without_a_batch_take_no_lock(dsn):
    manager = TransactionManager(dsn, pool_max_size=2)
    try:
        unit = PostgresCreativeUnitOfWork(manager, workspace_id=WORKSPACE)
        with unit:
            assert unit.layout_usage.locked_usage('plan:unknown-job:r1') is None
            assert unit.layout_usage.locked_usage('selection:batch-a:job:1') is None
            held = unit._require_connection().execute(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()").fetchone()[0]
            assert held == 0
            assert unit.layout_usage.locked_usage('plan:batch-a:job:1:r1') == ({'HERO_STRIP': 1}, 5)
            held = unit._require_connection().execute(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()").fetchone()[0]
            assert held == 1
            unit.rollback()
    finally:
        manager.close()
