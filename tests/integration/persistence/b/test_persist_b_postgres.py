'''PERSIST-B: oracle schema 0013 phải chứa được giá trị chuỗi của port (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test).'''
from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.migration_runner import MigrationRunner

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
DB_NAME = re.compile(r'^persist_b_[0-9a-f]+$')


@pytest.fixture
def migrated_dsn() -> Iterator[str]:
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.')
    name = f'persist_b_{uuid.uuid4().hex}'
    assert DB_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if not admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]:
            pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.')
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s', (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (name,)).fetchone()[0] == 0


def test_migration_0013_dedup_policy_revision_fits_string_port(migrated_dsn: str) -> None:
    '''ResolutionRepository.get và dedup_evidence nhận dedup_policy_revision kiểu str (ports.py:27, binding a-b-collected-document.json:151).'''
    with psycopg.connect(migrated_dsn, autocommit=True) as connection:
        types = dict(connection.execute(
            'SELECT table_name, data_type FROM information_schema.columns '
            'WHERE table_schema = %s AND column_name = %s AND table_name IN (%s, %s)',
            ('controlplane', 'dedup_policy_revision', 'cp_collected_document_resolutions', 'cp_dedup_evidence'),
        ).fetchall())
    assert types == {'cp_collected_document_resolutions': 'text', 'cp_dedup_evidence': 'text'}, types
