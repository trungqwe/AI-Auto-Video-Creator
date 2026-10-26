"""PERSIST-J: kiem tra adapter PostgreSQL cua config va security tren PostgreSQL 18.6."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import uuid
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import psycopg.errors
import pytest

from controlplane.application.config_security import SecretHandleStore
from controlplane.application.config_security.account_test import AccountTestReceipt, ExternalAccountTester, ProbeResult
from controlplane.application.config_security.bundle_resolution import BundleRequest, EffectiveConfigRevision, resolve_bundle
from controlplane.application.config_security.capacity_reservation import CapacityReservationBook, CapacityUnavailableError, Reservation
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus
from controlplane.domain.config_security.audit_record import build_audit_record
from controlplane.domain.config_security.capacity_snapshot import DomainCapacity
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.incremental_cost import BudgetPolicy, IncrementalCostRecord, evaluate_budget
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.db.config_security import PostgresConfigSecurityRepository
from controlplane.infrastructure.db.config_security.stores import PostgresAccountTestReceiptStore, PostgresAuditSink, PostgresCostLedger, PostgresReservationStore
from controlplane.infrastructure.db.migration_runner import MigrationRunner

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
CONFIG_SECURITY_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'config_security'
try:
    _port = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True, stderr=subprocess.DEVNULL).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)
NOW = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)


def add_workspace(dsn: str) -> str:
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as seed:
        seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'w', 'ACTIVE'))
    return str(workspace_id)


def count(connection, table, where='true', params=()):
    return connection.execute(f'SELECT count(*) FROM controlplane.{table} WHERE {where}', params).fetchone()[0]


@pytest.fixture
def db():
    name = f'persist_j_{uuid.uuid4().hex[:8]}'
    admin = psycopg.connect(PG_DSN, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        yield dsn, add_workspace(dsn)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        admin.close()


@pytest.fixture
def conn(db):
    with psycopg.connect(db[0]) as connection:
        yield connection


NEW_TABLE_COLUMNS = {
    'cp_external_accounts': {'workspace_id', 'external_account_id', 'provider', 'account_label', 'status', 'project_ref', 'capabilities_json', 'credential_version', 'credential_updated_at', 'credential_expires_at', 'quota_observation_ref', 'health', 'revision', 'created_at', 'updated_at'},
    'cp_provider_capacity_snapshots': {'snapshot_id', 'workspace_id', 'domain_key', 'remaining_requests', 'retry_after_at', 'observed_at', 'confidence_flag', 'created_at', 'updated_at'},
    'cp_capacity_reservations': {'reservation_ref', 'workspace_id', 'domain_key', 'units', 'expires_at', 'operation_key', 'confidence_flag', 'created_at', 'updated_at'},
    'cp_cost_records': {'record_id', 'workspace_id', 'provider', 'service', 'operation_ref', 'job_ref', 'batch_ref', 'quantity', 'unit', 'estimated_cost', 'actual_cost', 'currency', 'source', 'occurred_at', 'cost_category', 'created_at', 'updated_at'},
    'cp_audit_records': {'audit_id', 'workspace_id', 'actor_ref', 'action', 'resource_ref', 'revision_before', 'revision_after', 'occurred_at', 'correlation_id', 'outcome', 'redacted_reason', 'created_at'},
}


def test_migrations_to_18_and_schema_matches_0009(db):
    with psycopg.connect(db[0], autocommit=True) as connection:
        versions = [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()]
        assert versions == list(range(1, 20))

        def columns(table):
            rows = connection.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s', ('controlplane', table)).fetchall()
            return {r[0] for r in rows}

        for table, expected in NEW_TABLE_COLUMNS.items():
            assert columns(table) == expected, table
        assert {'credential_version', 'revocation_version'} <= columns('cp_secret_handles')
        constraint = connection.execute('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=%s', ('cp_config_revisions_scope_kind_check',)).fetchone()
        assert constraint is not None and 'scope_kind' in constraint[0]
        triggers = connection.execute('SELECT count(*) FROM pg_trigger WHERE tgname=%s AND NOT tgisinternal', ('cp_audit_records_append_only',)).fetchone()[0]
        assert triggers == 1


def test_scope_kind_check_rejects_unknown_kind(db, conn):
    repo = PostgresConfigSecurityRepository(conn)
    kwargs = dict(config_revision_id=str(uuid.uuid4()), workspace_id=db[1], scope_kind='prompt', scope_key='k', config_revision_number=1, content_hash='a' * 64, payload={}, actor_ref='t', change_reason='seed')
    assert repo.create_revision(**kwargs).scope_kind == 'prompt'
    conn.commit()
    kwargs.update(config_revision_id=str(uuid.uuid4()), scope_kind='bogus', config_revision_number=2)
    with pytest.raises(psycopg.errors.CheckViolation):
        repo.create_revision(**kwargs)
    conn.rollback()


def test_reservation_store_round_trip_and_workspace_isolation(db, conn):
    ws, other = db[1], add_workspace(db[0])
    store = PostgresReservationStore(conn, ws)
    res = Reservation('res-1', 'prov/proj/model', 3, NOW + timedelta(minutes=5), 'op-1', 'KNOWN')
    assert store.get_by_operation('op-1') is None
    store.add(res)
    conn.commit()
    assert store.get_by_operation('op-1') == res
    assert store.list_by_domain('prov/proj/model') == (res,)
    assert store.list_all() == (res,)
    assert store.list_by_domain('other-domain') == ()
    assert PostgresReservationStore(conn, other).list_all() == ()
    assert store.remove('res-2') is None
    assert store.remove('res-1') == res
    conn.commit()
    assert store.list_all() == ()
    assert count(conn, 'cp_capacity_reservations') == 0


def test_reservation_operation_key_is_unique_per_workspace(db, conn):
    store = PostgresReservationStore(conn, db[1])
    store.add(Reservation('res-1', 'd', 1, NOW + timedelta(minutes=5), 'op-1', 'KNOWN'))
    conn.commit()
    assert store.get_by_operation('op-1') is not None
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.add(Reservation('res-2', 'd', 1, NOW + timedelta(minutes=5), 'op-1', 'KNOWN'))
    conn.rollback()
    assert len(store.list_all()) == 1


def test_capacity_book_runs_on_postgres_store_with_expiry(db, conn):
    store = PostgresReservationStore(conn, db[1])
    book = CapacityReservationBook(store, ref_factory=iter(['res-a', 'res-b', 'res-c']).__next__)
    capacity = DomainCapacity('d', 10, 7, 3, 'ok', 'KNOWN', None, NOW)
    first = book.reserve('d', 2, 60, 'op-1', NOW, capacity)
    assert book.reserve('d', 2, 60, 'op-1', NOW, capacity) == first
    assert first.confidence_flag == 'KNOWN' and store.get_by_operation('op-1') == first
    with pytest.raises(CapacityUnavailableError):
        book.reserve('d', 2, 60, 'op-2', NOW, capacity)
    conn.commit()
    assert book.expire(NOW + timedelta(seconds=60)) == ('res-a',)
    assert store.list_all() == ()
    third = book.reserve('d', 2, 60, 'op-2', NOW + timedelta(seconds=61), capacity)
    assert third.reservation_ref == 'res-b' and store.list_all() == (third,)


def cost(record_id, occurred_at, **overrides):
    values = dict(record_id=record_id, provider='prov', service='model', operation_ref=f'op-{record_id}', job_ref='job-1', batch_ref=None, quantity=Decimal('2'), unit='request', estimated_cost=Decimal('0.123456'), actual_cost=Decimal('0.120000'), currency='USD', source='routed_invocation', occurred_at=occurred_at.isoformat(), cost_category='api_paid')
    values.update(overrides)
    return IncrementalCostRecord(**values)


def test_cost_ledger_round_trip_window_and_idempotent_append(db, conn):
    ws = db[1]
    ledger = PostgresCostLedger(conn)
    inside = cost('c-1', NOW)
    no_actual = cost('c-2', NOW + timedelta(hours=1), actual_cost=None, batch_ref='batch-1', job_ref=None)
    outside = cost('c-3', NOW + timedelta(days=40))
    for record in (inside, no_actual, outside):
        ledger.append(ws, record)
    ledger.append(ws, inside)
    conn.commit()
    assert count(conn, 'cp_cost_records', 'workspace_id=%s', (ws,)) == 3
    start, end = NOW - timedelta(days=1), NOW + timedelta(days=30)
    got = tuple(ledger.records(ws, start, end))
    assert got == (inside, no_actual)
    assert isinstance(got[0].estimated_cost, Decimal) and got[0].estimated_cost == Decimal('0.123456')
    assert got[1].actual_cost is None and got[1].job_ref is None and got[1].batch_ref == 'batch-1'
    assert tuple(ledger.records(ws, NOW + timedelta(days=39), NOW + timedelta(days=41))) == (outside,)
    assert tuple(ledger.records(add_workspace(db[0]), start, end)) == ()
    status = evaluate_budget(got, BudgetPolicy(Decimal('1')), start, end, NOW)
    assert status.spent == Decimal('0.243456')


def audit(ws, audit_id, **overrides):
    values = dict(audit_id=audit_id, workspace_id=ws, actor_ref='actor-1', action='config_change', resource_ref='cfg/1', revision_before=1, revision_after='2', occurred_at=NOW, correlation_id='corr-1', outcome='succeeded', reason='ok')
    values.update(overrides)
    return build_audit_record(**values)


def test_audit_sink_appends_and_rows_are_immutable(db, conn):
    ws = db[1]
    sink = PostgresAuditSink(conn)
    sink.append(audit(ws, 'a-1'))
    sink.append(audit(ws, 'a-2', revision_before=None, revision_after=None, outcome='denied'))
    conn.commit()
    sql = 'SELECT audit_id, revision_before, revision_after, outcome, redacted_reason, occurred_at FROM controlplane.cp_audit_records WHERE workspace_id=%s ORDER BY audit_id'
    rows = conn.execute(sql, (ws,)).fetchall()
    assert [r[0] for r in rows] == ['a-1', 'a-2']
    assert (rows[0][1], rows[0][2], rows[0][3], rows[0][4], rows[0][5]) == (1, 2, 'succeeded', 'ok', NOW)
    assert (rows[1][1], rows[1][2], rows[1][3]) == (None, None, 'denied')
    with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
        conn.execute('UPDATE controlplane.cp_audit_records SET outcome=%s WHERE workspace_id=%s AND audit_id=%s', ('failed', ws, 'a-1'))
    conn.rollback()
    with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
        conn.execute('DELETE FROM controlplane.cp_audit_records WHERE workspace_id=%s', (ws,))
    conn.rollback()
    assert count(conn, 'cp_audit_records', 'workspace_id=%s', (ws,)) == 2
    assert conn.execute(sql, (ws,)).fetchall() == rows


def test_audit_sink_rejects_duplicate_ids_and_non_numeric_revisions(db, conn):
    ws = db[1]
    sink = PostgresAuditSink(conn)
    sink.append(audit(ws, 'a-1'))
    conn.commit()
    assert count(conn, 'cp_audit_records', 'workspace_id=%s', (ws,)) == 1
    with pytest.raises(psycopg.errors.UniqueViolation):
        sink.append(audit(ws, 'a-1'))
    conn.rollback()
    with pytest.raises(ValueError):
        sink.append(audit(ws, 'a-2', revision_before='cfg-ref-1'))
    assert count(conn, 'cp_audit_records', 'workspace_id=%s', (ws,)) == 1


class FakeProbe:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0

    def probe(self, account_ref, minimal):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def make_account(ws):
    return ExternalAccount('acct-1', ws, 'gemini', 'main', ExternalAccountStatus.ENABLED, None, frozenset({'script'}), 1, None, None, None, None, 1)


def test_account_test_receipt_round_trip_and_idempotent_replay(db, conn):
    ws = db[1]
    store = PostgresAccountTestReceiptStore(conn, ws)
    probe = FakeProbe(ProbeResult(True, 42))
    tester = ExternalAccountTester(probe, store, lambda: NOW.isoformat())
    first = tester.run(make_account(ws), 'op-1')
    conn.commit()
    assert first.ok is True and first.latency_ms == 42 and probe.calls == 1
    with psycopg.connect(db[0]) as other_conn:
        assert PostgresAccountTestReceiptStore(other_conn, ws).get('op-1') == first
    assert tester.run(make_account(ws), 'op-1') == first and probe.calls == 1
    row = conn.execute('SELECT action, resource_ref, correlation_id, outcome FROM controlplane.cp_audit_records WHERE workspace_id=%s', (ws,)).fetchone()
    assert row == ('account_test', 'acct-1', 'op-1', 'succeeded')
    assert store.get('op-unknown') is None
    assert PostgresAccountTestReceiptStore(conn, add_workspace(db[0])).get('op-1') is None


def test_account_test_failure_receipt_keeps_error_class(db, conn):
    ws = db[1]
    store = PostgresAccountTestReceiptStore(conn, ws)
    tester = ExternalAccountTester(FakeProbe(TimeoutError('upstream timeout')), store, lambda: NOW.isoformat())
    receipt = tester.run(make_account(ws), 'op-2')
    conn.commit()
    assert receipt.ok is False and receipt.error_class == 'TimeoutError'
    assert PostgresAccountTestReceiptStore(conn, ws).get('op-2') == receipt
    assert conn.execute('SELECT outcome FROM controlplane.cp_audit_records WHERE workspace_id=%s AND correlation_id=%s', (ws, 'op-2')).fetchone()[0] == 'failed'


def test_plain_audit_record_is_not_mistaken_for_receipt(db, conn):
    ws = db[1]
    PostgresAuditSink(conn).append(audit(ws, 'a-9', action='account_test', correlation_id='op-9'))
    conn.commit()
    assert count(conn, 'cp_audit_records', 'workspace_id=%s', (ws,)) == 1
    assert PostgresAccountTestReceiptStore(conn, ws).get('op-9') is None


def test_receipt_store_requires_aware_tested_at_and_receipt_prefix(db, conn):
    store = PostgresAccountTestReceiptStore(conn, db[1])
    good = AccountTestReceipt('acctest-1', 'op-1', 'acct-1', True, 5, None, None, NOW.isoformat())
    store.save(good)
    store.save(good)
    conn.commit()
    assert store.get('op-1') == good
    assert count(conn, 'cp_audit_records') == 1
    with pytest.raises(ValueError):
        store.save(AccountTestReceipt('acctest-2', 'op-2', 'acct-1', True, 5, None, None, '2026-10-22T08:00:00'))
    with pytest.raises(ValueError):
        store.save(AccountTestReceipt('other-3', 'op-3', 'acct-1', True, 5, None, None, NOW.isoformat()))


def make_revision(conn, ws, number, payload, effective_at=None, publish=True, scope=('workspace', 'default')):
    repo = PostgresConfigSecurityRepository(conn)
    revision = repo.create_revision(config_revision_id=str(uuid.uuid4()), workspace_id=ws, scope_kind=scope[0], scope_key=scope[1], config_revision_number=number, content_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest(), payload=payload, effective_at=effective_at, actor_ref='tester', change_reason='seed')
    if publish:
        revision = repo.transition(workspace_id=ws, config_revision_id=revision.config_revision_id, expected_revision=1, current_status=ConfigRevisionStatus.DRAFT, requested_status=ConfigRevisionStatus.PUBLISHED, actor_ref='tester', change_reason='publish')
    conn.commit()
    return revision


def seed_effective(conn, ws):
    past = datetime(2026, 10, 1, 7, 0, tzinfo=timezone(timedelta(hours=7)))
    future = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
    revisions = [make_revision(conn, ws, 1, {'a': 1}), make_revision(conn, ws, 2, {'a': 2}, effective_at=past), make_revision(conn, ws, 3, {'a': 3}, effective_at=future), make_revision(conn, ws, 4, {'a': 4}, publish=False)]
    return revisions, [None, past, future, None]


def test_list_effective_revisions_builds_wrappers_with_aware_effective_at(db, conn):
    ws, other = db[1], add_workspace(db[0])
    revisions, written = seed_effective(conn, ws)
    make_revision(conn, other, 1, {'a': 99})
    items = PostgresConfigSecurityRepository(conn).list_effective_revisions(workspace_id=ws)
    assert [i.revision for i in items] == revisions
    assert all(isinstance(i, EffectiveConfigRevision) for i in items)
    assert [i.effective_at for i in items] == written
    assert all(i.effective_at is None or i.effective_at.utcoffset() is not None for i in items)
    assert len(fields(ConfigRevision)) == 9 and not hasattr(items[0].revision, 'effective_at')
    assert {i.revision.workspace_id for i in items} == {ws}


def bundle_request(ws, when, state='NOT_COMMITTED', pins=None):
    return BundleRequest(ws, 'job-1', 'stage-1', when, (('workspace', 'default'),), state, pins or {})


def test_resolve_bundle_uses_effective_at_read_from_postgres(db, conn):
    ws = db[1]
    (r1, r2, r3, _r4), _written = seed_effective(conn, ws)
    items = PostgresConfigSecurityRepository(conn).list_effective_revisions(workspace_id=ws)
    assert len(items) == 4
    utc = timezone.utc
    cases = [(datetime(2026, 9, 1, tzinfo=utc), r1), (datetime(2026, 10, 22, tzinfo=utc), r2), (datetime(2026, 12, 2, tzinfo=utc), r3)]
    for when, expected in cases:
        bundle = resolve_bundle(items, bundle_request(ws, when))
        assert bundle.revision_refs == (expected.config_revision_id,)
        assert bundle.values == expected.payload
    pinned = resolve_bundle(items, bundle_request(ws, cases[0][0], 'COMMITTED', {('workspace', 'default'): r2.config_revision_id}))
    assert pinned.values == {'a': 2}


def test_resolve_bundle_rejects_bare_revisions_and_naive_effective_at(db, conn):
    ws = db[1]
    r1 = make_revision(conn, ws, 1, {'a': 1})
    with pytest.raises(AttributeError):
        resolve_bundle([r1], bundle_request(ws, NOW))
    with pytest.raises(ValueError, match='naive_effective_at'):
        EffectiveConfigRevision(r1, datetime(2026, 1, 1))


SECRET_TABLES = ['cp_secret_handles', 'cp_external_accounts', 'cp_provider_capacity_snapshots', 'cp_capacity_reservations', 'cp_cost_records', 'cp_audit_records']
FORBIDDEN_COLUMNS = {'value', 'secret_value', 'plaintext', 'plaintext_secret', 'token', 'access_token', 'refresh_token', 'password', 'private_key', 'credential', 'raw_credential', 'raw_secret', 'secret_blob', 'blob', 'api_key'}


def register_args(ws, **extra):
    return dict(workspace_id=ws, provider_ref='gemini', account_ref='acct-1', alias_ref='main', redacted_fingerprint_or_version='v1', validation_status='valid', audit_ref='audit-1', **extra)


def test_secret_handle_versions_round_trip_and_defaults(db, conn):
    ws, other = db[1], add_workspace(db[0])
    repo = PostgresConfigSecurityRepository(conn)
    store = SecretHandleStore(PostgresConfigSecurityRepository)
    h1 = store.register(connection=conn, **register_args(ws))
    h2 = store.register(connection=conn, **register_args(ws, credential_version=3, revocation_version=2))
    conn.commit()
    assert repo.secret_handle_versions(workspace_id=ws, secret_handle_id=h1.secret_handle_id) == (0, 0)
    assert repo.secret_handle_versions(workspace_id=ws, secret_handle_id=h2.secret_handle_id) == (3, 2)
    assert repo.secret_handle_versions(workspace_id=other, secret_handle_id=h2.secret_handle_id) is None
    with pytest.raises(psycopg.errors.CheckViolation):
        store.register(connection=conn, **register_args(ws, credential_version=-1))
    conn.rollback()


def test_postgres_never_holds_secret_values(db, conn):
    rows = conn.execute('SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema=%s AND table_name = ANY(%s)', ('controlplane', SECRET_TABLES)).fetchall()
    assert {r[0] for r in rows} == set(SECRET_TABLES)
    assert not [r for r in rows if r[1] in FORBIDDEN_COLUMNS or r[2] == 'bytea']
    store = SecretHandleStore(PostgresConfigSecurityRepository)
    with pytest.raises(ValueError, match='plaintext'):
        store.register(connection=conn, **register_args(db[1], secret_value='CANARY-SECRET-VALUE'))
    assert count(conn, 'cp_secret_handles') == 0


def test_no_postgres_secret_store_adapter_and_no_ddl_in_adapters():
    import controlplane.infrastructure.db.config_security as package
    import controlplane.infrastructure.db.config_security.stores as stores
    members = {'put', 'revoke', 'current_version'}
    classes = [c for module in (package, stores) for _name, c in inspect.getmembers(module, inspect.isclass) if c.__module__.startswith('controlplane.infrastructure.db.config_security')]
    assert classes
    assert not [c for c in classes if members <= set(dir(c)) or 'SecretStore' in c.__name__]
    source = ' '.join(f.read_text(encoding='utf-8') for f in CONFIG_SECURITY_DIR.rglob('*.py'))
    assert 'EffectiveConfigRevision' in source
    assert 'CREATE TABLE' not in source and 'ALTER TABLE' not in source and 'SecretStorePort' not in source
