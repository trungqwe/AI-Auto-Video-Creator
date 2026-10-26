"""Shared fixtures for the prod_wiring tests (PW-H0): temporary PostgreSQL database and time-skipping Temporal."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
import pytest_asyncio
from psycopg import sql
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment

from controlplane.infrastructure.db.migration_runner import MigrationRunner

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
LOOPBACK_HOSTS = frozenset({'127.0.0.1', 'localhost', '::1'})


@dataclass(frozen=True)
class PwDatabase:
    name: str
    dsn: str
    admin_dsn: str
    workspace_id: str
    actor_id: str

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn, autocommit=True)


def pw_admin_dsn() -> str:
    dsn = os.environ.get('M2_TEST_PG_DSN', '')
    if not dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required for prod_wiring tests; no skip and no fallback is permitted.', pytrace=False)
    try:
        host = urlsplit(dsn).hostname
    except ValueError:
        host = None
    if host not in LOOPBACK_HOSTS:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN must point to a loopback PostgreSQL (127.0.0.1, localhost or ::1); refusing to create databases elsewhere.', pytrace=False)
    return dsn


@contextmanager
def pw_temp_database() -> Iterator[PwDatabase]:
    admin_dsn = pw_admin_dsn()
    name = 'pw_' + uuid.uuid4().hex[:8]
    dsn = urlunsplit(urlsplit(admin_dsn)._replace(path='/' + name))
    workspace_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())
    admin = psycopg.connect(admin_dsn, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as seed:
            seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'pw-workspace', 'ACTIVE'))
            seed.execute('INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s, %s, %s, %s, %s)', (actor_id, workspace_id, 'user', 'pw-actor', 'ACTIVE'))
        yield PwDatabase(name=name, dsn=dsn, admin_dsn=admin_dsn, workspace_id=workspace_id, actor_id=actor_id)
    finally:
        try:
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
        finally:
            admin.close()


@pytest.fixture
def pw_database() -> Iterator[PwDatabase]:
    with pw_temp_database() as database:
        yield database


@pytest_asyncio.fixture
async def pw_temporal() -> AsyncIterator[Client]:
    environment = await WorkflowEnvironment.start_time_skipping()
    try:
        yield environment.client
    finally:
        await environment.shutdown()
