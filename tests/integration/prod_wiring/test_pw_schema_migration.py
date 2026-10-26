'''PW-SCHEMA: migration 0019 (stage run theo workflow và ba bảng nối dây) cùng rollback về 0018 trên CSDL tạm.

coveredIds: PW-SCHEMA-01..05, CT-ORC-003, CT-SRC-004
'''
from __future__ import annotations

import datetime
import re
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
FORWARD = MIGRATIONS_DIR / '0019_prod_wiring.sql'
ROLLBACK = MIGRATIONS_DIR / '0019_prod_wiring.rollback.sql'
CHECK_NAME = 'cp_stage_runs_job_or_workflow_check'
NEW_TABLES = {
    'cp_job_candidates': ['workspace_id', 'job_id', 'batch_id', 'candidate_ref', 'source_set_ref', 'created_at'],
    'cp_creative_selections': ['workspace_id', 'selection_id', 'job_id', 'selection_revision', 'content_sha256', 'payload', 'created_at'],
    'cp_source_cycle_marks': ['workspace_id', 'source_id', 'cycle_day', 'collection_run_ref', 'created_at'],
}
STAGE_RUN = {'stage_name': 'daily', 'attempt': 1, 'status': 'PENDING', 'recovery_epoch': '0', 'execution_generation': 0}


def table_names(connection):
    rows = connection.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = %s', ('controlplane',)).fetchall()
    return {row[0] for row in rows}


def column_info(connection, table):
    rows = connection.execute('SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position', ('controlplane', table)).fetchall()
    return {name: (data_type, nullable) for name, data_type, nullable in rows}


def constraints(connection, table, kind):
    rows = connection.execute('SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass AND contype = %s', (f'controlplane.{table}', kind)).fetchall()
    return {name: definition for name, definition in rows}


def insert_stage_run(connection, workspace_id, **extra):
    values = {**STAGE_RUN, 'workspace_id': workspace_id, **extra}
    names = ', '.join(values)
    marks = ', '.join(['%s'] * len(values))
    connection.execute(f'INSERT INTO controlplane.cp_stage_runs ({names}) VALUES ({marks})', list(values.values()))


def seed_job(connection, workspace_id, job_id):
    connection.execute('INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)', ('batch-1', workspace_id, 'CREATED', 1))
    connection.execute('INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, %s)', (job_id, 'batch-1', workspace_id, 'CREATED', 'snap-1', 1))


def test_files_exist_and_sequence_is_nineteen():
    assert FORWARD.is_file() and ROLLBACK.is_file()
    forward = [p.name for p in MIGRATIONS_DIR.iterdir() if re.fullmatch('[0-9]{4}_[a-z0-9_]+[.]sql', p.name)]
    assert sorted(int(name[:4]) for name in forward) == list(range(1, 20))
    assert len(list(MIGRATIONS_DIR.glob('*.rollback.sql'))) == 19


def test_stage_run_accepts_workflow_only_and_rejects_neither(pw_database):
    workspace_id = pw_database.workspace_id
    with pw_database.connect() as connection:
        columns = column_info(connection, 'cp_stage_runs')
        assert columns['job_id'] == ('text', 'YES')
        assert columns['workflow_id'] == ('text', 'YES')
        checks = constraints(connection, 'cp_stage_runs', 'c')
        assert CHECK_NAME in checks
        assert 'job_id IS NOT NULL' in checks[CHECK_NAME] and 'workflow_id IS NOT NULL' in checks[CHECK_NAME] and ' OR ' in checks[CHECK_NAME]
        insert_stage_run(connection, workspace_id, stage_run_id='sr-wf', workflow_id='daily-1')
        with pytest.raises(psycopg.errors.CheckViolation) as raised:
            insert_stage_run(connection, workspace_id, stage_run_id='sr-none')
        assert raised.value.diag.constraint_name == CHECK_NAME
        seed_job(connection, workspace_id, 'job-1')
        insert_stage_run(connection, workspace_id, stage_run_id='sr-job', job_id='job-1')
        insert_stage_run(connection, workspace_id, stage_run_id='sr-both', job_id='job-1', workflow_id='daily-1')
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            insert_stage_run(connection, workspace_id, stage_run_id='sr-orphan', job_id='missing-job')
        foreign = list(constraints(connection, 'cp_stage_runs', 'f').values())
        assert any('FOREIGN KEY (workspace_id, job_id)' in d and 'cp_video_jobs' in d for d in foreign)
        count = connection.execute('SELECT count(*) FROM controlplane.cp_stage_runs WHERE workspace_id = %s', (workspace_id,)).fetchone()[0]
        assert count == 3


def test_new_tables_have_exact_columns_and_keys(pw_database):
    workspace_id = pw_database.workspace_id
    with pw_database.connect() as connection:
        infos = {table: column_info(connection, table) for table in NEW_TABLES}
        for table, names in NEW_TABLES.items():
            assert list(infos[table]) == names, table
            nullable = [name for name, (_, flag) in infos[table].items() if flag == 'YES']
            assert nullable == (['source_set_ref'] if table == 'cp_job_candidates' else []), table
        assert infos['cp_source_cycle_marks']['cycle_day'][0] == 'date'
        assert infos['cp_creative_selections']['payload'][0] == 'jsonb'
        assert list(constraints(connection, 'cp_job_candidates', 'p').values()) == ['PRIMARY KEY (workspace_id, job_id)']
        assert list(constraints(connection, 'cp_source_cycle_marks', 'p').values()) == ['PRIMARY KEY (workspace_id, source_id, cycle_day)']
        assert list(constraints(connection, 'cp_creative_selections', 'u').values()) == ['UNIQUE (workspace_id, job_id, selection_revision)']
        candidate = 'INSERT INTO controlplane.cp_job_candidates (workspace_id, job_id, batch_id, candidate_ref) VALUES (%s, %s, %s, %s)'
        connection.execute(candidate, (workspace_id, 'job-1', 'batch-1', 'cand-1'))
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute(candidate, (workspace_id, 'job-1', 'batch-2', 'cand-2'))
        mark = 'INSERT INTO controlplane.cp_source_cycle_marks (workspace_id, source_id, cycle_day, collection_run_ref) VALUES (%s, %s, %s, %s)'
        day = datetime.date(2026, 10, 26)
        connection.execute(mark, (workspace_id, 'src-1', day, 'run-1'))
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute(mark, (workspace_id, 'src-1', day, 'run-2'))
        connection.execute(mark, (workspace_id, 'src-1', datetime.date(2026, 10, 27), 'run-3'))
        selection = 'INSERT INTO controlplane.cp_creative_selections (workspace_id, selection_id, job_id, selection_revision, content_sha256, payload) VALUES (%s, %s, %s, %s, %s, %s)'
        sha = 'a' * 64
        connection.execute(selection, (workspace_id, 'sel-1', 'job-1', 1, sha, Jsonb({})))
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute(selection, (workspace_id, 'sel-2', 'job-1', 1, sha, Jsonb({})))
        connection.execute(selection, (workspace_id, 'sel-3', 'job-1', 2, sha, Jsonb({})))


def test_rollback_restores_0018_and_forward_reapplies(pw_database):
    with pw_database.connect() as connection:
        tables_up = table_names(connection)
        assert set(NEW_TABLES) <= tables_up
        checks_up = constraints(connection, 'cp_stage_runs', 'c')
        with connection.transaction():
            connection.execute(ROLLBACK.read_text(encoding='utf-8'))
            connection.execute('DELETE FROM controlplane.cp_schema_migrations WHERE version = 19')
        assert tables_up - table_names(connection) == set(NEW_TABLES)
        assert table_names(connection) - tables_up == set()
        columns = column_info(connection, 'cp_stage_runs')
        assert 'workflow_id' not in columns
        assert columns['job_id'] == ('text', 'NO')
        checks_down = constraints(connection, 'cp_stage_runs', 'c')
        assert set(checks_up) - set(checks_down) == {CHECK_NAME}
        assert set(checks_down) - set(checks_up) == set()
        versions = [row[0] for row in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()]
        assert versions == list(range(1, 19))
        with pytest.raises(psycopg.errors.NotNullViolation):
            insert_stage_run(connection, pw_database.workspace_id, stage_run_id='sr-none')
        connection.execute(FORWARD.read_text(encoding='utf-8'))
        assert table_names(connection) == tables_up
        assert set(constraints(connection, 'cp_stage_runs', 'c')) == set(checks_up)
