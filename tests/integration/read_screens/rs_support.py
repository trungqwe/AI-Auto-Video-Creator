"""Shared support for the read_screens PostgreSQL tests (RS-1): temporary database and fake request."""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
ACTOR_ID = '00000000-0000-0000-0000-0000000000a1'
SESSION_ID = '00000000-0000-0000-0000-0000000000b1'


def admin_dsn() -> str:
    dsn = os.environ.get('M2_TEST_PG_DSN', '')
    if not dsn:
        pytest.fail('BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN', pytrace=False)
    return dsn


def database_exists(name: str) -> bool:
    with psycopg.connect(admin_dsn(), autocommit=True) as admin:
        return admin.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone() is not None


@contextmanager
def temp_database() -> Iterator[tuple[TransactionManager, str, str]]:
    dsn = admin_dsn()
    name = 'rs_' + uuid.uuid4().hex[:12]
    admin = psycopg.connect(dsn, autocommit=True)
    manager = None
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        new_dsn = dsn.rsplit('/', 1)[0] + '/' + name
        MigrationRunner(new_dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        workspace_id = str(uuid.uuid4())
        other_workspace_id = str(uuid.uuid4())
        with psycopg.connect(new_dsn, autocommit=True) as seed:
            for seeded_id, label in ((workspace_id, 'rs-w1'), (other_workspace_id, 'rs-w2')):
                seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (seeded_id, label, 'ACTIVE'))
        manager = TransactionManager(new_dsn)
        yield (manager, workspace_id, other_workspace_id)
    finally:
        try:
            if manager is not None:
                manager.close()
        finally:
            try:
                admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
            finally:
                admin.close()


class FakeRequest:
    """Minimal stand-in for a Starlette request: state.identity and query_params."""

    def __init__(self, workspace_id: str, params: Mapping[str, str] | None = None) -> None:
        self.state = SimpleNamespace(identity={'workspace_id': workspace_id, 'actor_id': ACTOR_ID, 'session_id': SESSION_ID})
        self.query_params = dict(params or {})
