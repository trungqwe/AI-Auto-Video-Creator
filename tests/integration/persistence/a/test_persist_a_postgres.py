'''PERSIST-A: adapter PostgreSQL của source_ingestion trên PostgreSQL 18.6 dùng một lần.'''
from __future__ import annotations

import datetime
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
import psycopg.errors
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from source_ingestion.domain import collection_run as run_domain
from source_ingestion.domain import source as source_domain
from source_ingestion.domain import source_candidate as candidate_domain
from source_ingestion.domain.checkpoint import (
    CheckpointCompleteness,
    CheckpointRejected,
    CollectionCheckpoint,
    seal_checkpoint,
)
from source_ingestion.domain.source_candidate import IdentityMatchKind
from source_ingestion.persistence import (
    PostgresSourceIngestionUnitOfWork,
    UnitOfWorkAlreadyActiveError,
    UnitOfWorkNotActiveError,
)
from source_ingestion.ports.repositories import (
    CommandReceipt,
    DuplicatePackageError,
    DuplicateReceiptError,
    DuplicateRecordError,
    DuplicateSourceIdentityError,
    PackageRecord,
    RecordNotFoundError,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
DB_NAME_RE = re.compile(r'^persist_a_[0-9a-f]+$')
AT = datetime.datetime(2026, 10, 20, 8, 0, tzinfo=datetime.UTC)


@dataclass
class Db:
    name: str
    dsn: str
    admin_dsn: str


@pytest.fixture
def db():
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.')
    with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
        row = admin_conn.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()
        if not row or not row[0]:
            pytest.fail('BLOCKED_EXTERNAL: user lacks CREATEDB privilege.')
    name = 'persist_a_' + uuid.uuid4().hex
    assert DB_NAME_RE.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
        admin_conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        yield Db(name=name, dsn=dsn, admin_dsn=admin_dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
            admin_conn.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s', (name,))
            admin_conn.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            orphan_count = admin_conn.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (name,)).fetchone()[0]
            assert orphan_count == 0


@pytest.fixture
def manager(db):
    tm = TransactionManager(db.dsn, pool_max_size=4)
    yield tm
    tm.close()


def run_sql(db, statement, params=()):
    with psycopg.connect(db.dsn, autocommit=True) as c:
        cur = c.execute(statement, params)
        return cur.fetchall() if cur.description else []


def insert_workspace(db) -> str:
    ws_id = str(uuid.uuid4())
    run_sql(db, "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'w', 'ACTIVE')", (ws_id,))
    return ws_id


@pytest.fixture
def ws(db):
    return insert_workspace(db)


@pytest.fixture
def ws2(db):
    return insert_workspace(db)


def count(db, table):
    return run_sql(db, f'SELECT count(*) FROM controlplane.{table}')[0][0]


def make_uow(manager, ws):
    return PostgresSourceIngestionUnitOfWork(manager, workspace_id=ws)


POLICY = source_domain.SourcePolicy(
    policy_revision='pol-1',
    source_kinds=frozenset({'rss'}),
    tiers=frozenset({'T1'}),
    admin_metadata_keys=frozenset({'owner'}),
)


def make_source(ws, source_id='src-1', locator='https://example.org/feed'):
    return source_domain.register_source(
        source_id=source_id,
        workspace_id=ws,
        canonical_locator=locator,
        name='Feed',
        source_kind='rss',
        tier='T1',
        topics=['tech', 'ai'],
        notes='n1',
        collection_enabled=True,
        admin_metadata={'owner': 'qa'},
        actor='tester',
        at=AT,
        policy=POLICY,
    )


def make_candidate(ws, candidate_id='cand-1', locator='https://example.org/new'):
    return candidate_domain.discover_candidate(
        candidate_id=candidate_id,
        workspace_id=ws,
        observed_locator=locator,
        canonical_locator=locator,
        discovery_method='feed_link',
        discovery_evidence='ev',
        source_kind_candidates=['rss'],
        topic_candidates=['tech'],
        actor='tester',
        at=AT,
    )


def make_run(ws, run_id='run-1', source_id='src-1', date=datetime.date(2026, 10, 20), purpose=run_domain.CollectionPurpose.PERIODIC):
    return run_domain.schedule_run(
        run_id=run_id,
        workspace_id=ws,
        source_id=source_id,
        business_date=date,
        purpose=purpose,
        retry_policy=run_domain.RetryPolicy('retry-1', 3),
    )


def make_checkpoint(revision=1, items=('item-1',), run_id='run-1', source_id='src-1'):
    cp = CollectionCheckpoint(
        checkpoint_version=1,
        revision=revision,
        source_id=source_id,
        source_revision=1,
        adapter_type='rss',
        adapter_revision='r1',
        cursor=f'cur-{revision}',
        item_ids=tuple(items),
        run_id=run_id,
        attempt_id='att-1',
        execution_generation=0,
        completeness=CheckpointCompleteness.PARTIAL,
        recorded_at='2026-10-20T08:00:00Z',
        fingerprint='pending',
    )
    return seal_checkpoint(cp)


def make_package(run_id='run-1', fingerprint='fp-1', locator='https://example.org/a'):
    return PackageRecord(
        'src-1',
        locator,
        fingerprint,
        run_id,
        {'collected_document_id': 'doc-1', 'title': 'T', 'fetched_at': '2026-10-20T08:00:00Z', 'tags': ['x']},
    )


def make_receipt(ws, key='key-1'):
    return CommandReceipt(ws, key, 'hash-1', 'src-1', 1)


def seed_run(manager, ws, **kw):
    with make_uow(manager, ws) as uow:
        run = make_run(ws, **kw)
        uow.runs.add(run)
        uow.commit()
        return run


def test_persist_a_migrations_and_schema(db):
    versions = [r[0] for r in run_sql(db, 'SELECT version FROM controlplane.cp_schema_migrations ORDER BY version')]
    assert versions == list(range(1, 19))
    expected_tables = {
        'cp_sources': {'workspace_id', 'source_id', 'canonical_locator', 'status', 'revision', 'payload', 'created_at', 'updated_at'},
        'cp_source_identities': {'workspace_id', 'canonical_locator', 'source_id', 'is_tombstone', 'tombstoned_at', 'updated_at'},
        'cp_source_candidates': {'workspace_id', 'candidate_id', 'canonical_locator', 'status', 'revision', 'payload', 'updated_at'},
        'cp_collection_runs': {'run_id', 'workspace_id', 'source_id', 'run_kind', 'business_date', 'status', 'revision', 'payload', 'updated_at'},
        'cp_collection_attempts': {'attempt_id', 'run_id', 'workspace_id', 'attempt_index', 'status', 'payload', 'updated_at'},
        'cp_collection_checkpoints': {'checkpoint_id', 'workspace_id', 'source_id', 'sequence_no', 'payload'},
        'cp_fetch_observations': {'observation_id', 'workspace_id', 'run_id', 'source_id', 'canonical_locator', 'observation_fingerprint', 'observed_at', 'payload'},
        'cp_collected_document_packages': {'workspace_id', 'source_id', 'canonical_locator', 'observation_fingerprint', 'collection_run_id', 'payload'},
        'cp_source_command_receipts': {'workspace_id', 'idempotency_key', 'request_hash', 'aggregate_ref', 'aggregate_revision'},
        'cp_outbox_events': {'event_id', 'workspace_id', 'event_name', 'aggregate_id', 'payload', 'recovery_epoch', 'published'},
    }
    for table_name, req_cols in expected_tables.items():
        actual_cols = {
            r[0]
            for r in run_sql(
                db,
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = %s",
                (table_name,),
            )
        }
        assert req_cols.issubset(actual_cols), f'{table_name} missing columns: {req_cols - actual_cols}'


def test_source_round_trip(db, manager, ws):
    source = make_source(ws)
    with make_uow(manager, ws) as uow:
        uow.sources.add(source)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.sources.get(ws, 'src-1') == source
        assert uow.sources.list_sources(ws) == (source,)
        match = uow.sources.resolve_identity(ws, source.canonical_locator)
        assert match.kind is IdentityMatchKind.EXISTING_SOURCE
        assert match.ref == 'src-1'
        unknown_match = uow.sources.resolve_identity(ws, 'https://example.org/unknown')
        assert unknown_match.kind is IdentityMatchKind.NONE
        updated = source_domain.update_source_metadata(
            source, expected_revision=1, actor='tester', at=AT, policy=POLICY, notes='n2'
        )
        uow.sources.save(updated)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.sources.get(ws, 'src-1') == updated
        rev = run_sql(db, 'SELECT revision FROM controlplane.cp_sources')[0][0]
        assert rev == 2
        assert count(db, 'cp_source_identities') == 1
        with pytest.raises(RevisionConflictError):
            uow.sources.save(updated)
        with pytest.raises(RecordNotFoundError):
            uow.sources.save(make_source(ws, 'src-9', 'https://example.org/other'))


def test_candidate_round_trip(db, manager, ws):
    cand = make_candidate(ws)
    with make_uow(manager, ws) as uow:
        uow.candidates.add(cand)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.candidates.get(ws, 'cand-1') == cand
        assert uow.candidates.find_by_canonical_locator(ws, cand.canonical_locator) == (cand,)
        decision = candidate_domain.begin_validation(cand, expected_revision=1, actor='tester', at=AT)
        uow.candidates.save(decision.candidate)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.candidates.get(ws, 'cand-1') == decision.candidate
        with pytest.raises(RevisionConflictError):
            uow.candidates.save(decision.candidate)
        with pytest.raises(DuplicateRecordError):
            uow.candidates.add(cand)


def test_run_round_trip_with_attempts(db, manager, ws):
    run = make_run(ws)
    with make_uow(manager, ws) as uow:
        uow.runs.add(run)
        uow.commit()

    with make_uow(manager, ws) as uow:
        run = run_domain.start_run(run, source_active=True, checkpoint_ref='cp-1')
        uow.runs.save(run)
        run = run_domain.record_attempt_outcome(
            run,
            run_domain.AttemptOutcome.FAILED_RETRYABLE,
            source_active=True,
            deadline_passed=False,
            checkpoint_ref='cp-2',
        )
        uow.runs.save(run)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.runs.get('run-1') == run
        assert uow.runs.get_periodic(ws, 'src-1', datetime.date(2026, 10, 20)) == run
        assert uow.runs.list_by_source(ws, 'src-1') == (run,)
        assert count(db, 'cp_collection_attempts') == 1
        rev = run_sql(db, 'SELECT revision FROM controlplane.cp_collection_runs')[0][0]
        assert rev == 3
        assert uow.runs.get('khong-co') is None


def test_package_round_trip(db, manager, ws):
    seed_run(manager, ws)
    record = make_package()
    with make_uow(manager, ws) as uow:
        uow.packages.add(record)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.packages.get('src-1', record.canonical_locator, 'fp-1') == record
        assert uow.packages.list_by_run('run-1') == (record,)
        row_ws = run_sql(db, 'SELECT workspace_id::text FROM controlplane.cp_collected_document_packages')[0][0]
        assert row_ws == ws
        assert count(db, 'cp_fetch_observations') == 1
        with pytest.raises(RecordNotFoundError):
            uow.packages.add(make_package(run_id='khong-co'))


def test_checkpoint_round_trip(db, manager, ws):
    seed_run(manager, ws)
    with make_uow(manager, ws) as uow:
        assert uow.checkpoints.get_latest('src-1') is None
        cp = make_checkpoint(1, ('item-1',))
        assert uow.checkpoints.advance(cp, ['item-1']) == cp
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.checkpoints.get_latest('src-1') == cp


def test_receipt_round_trip(db, manager, ws):
    with make_uow(manager, ws) as uow:
        assert uow.receipts.get(ws, 'key-1') is None
        receipt = make_receipt(ws)
        uow.receipts.put(receipt)
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.receipts.get(ws, 'key-1') == receipt


def test_tombstone_blocks_reregistration(db, manager, ws):
    source = make_source(ws)
    with make_uow(manager, ws) as uow:
        uow.sources.add(source)
        uow.commit()

    with make_uow(manager, ws) as uow:
        removed = source_domain.remove_source(source, expected_revision=1, actor='tester', at=AT)
        uow.sources.save(removed)
        uow.commit()

    with make_uow(manager, ws) as uow:
        match = uow.sources.resolve_identity(ws, source.canonical_locator)
        assert match.kind is IdentityMatchKind.TOMBSTONE
        assert match.ref == 'src-1'
        is_tomb = run_sql(db, 'SELECT is_tombstone FROM controlplane.cp_source_identities')[0][0]
        assert is_tomb is True
        with pytest.raises(DuplicateSourceIdentityError):
            uow.sources.add(make_source(ws, 'src-2', source.canonical_locator))
        assert uow.sources.get(ws, 'src-1') == removed
        with pytest.raises(DuplicateSourceIdentityError):
            uow.sources.add(make_source(ws, 'src-1', 'https://example.org/new-loc'))
        assert count(db, 'cp_sources') == 1


def test_periodic_run_unique(db, manager, ws):
    run1 = make_run(ws, run_id='run-1')
    with make_uow(manager, ws) as uow:
        uow.runs.add(run1)
        uow.commit()

    with make_uow(manager, ws) as uow:
        with pytest.raises(run_domain.DuplicatePeriodicRunError):
            uow.runs.add(make_run(ws, run_id='run-2'))
        assert uow.runs.get('run-1') == run1
        with pytest.raises(DuplicateRecordError):
            uow.runs.add(make_run(ws, run_id='run-1', date=datetime.date(2026, 10, 21)))
        uow.runs.add(make_run(ws, run_id='run-3', date=datetime.date(2026, 10, 21)))
        uow.runs.add(make_run(ws, run_id='run-4', purpose=run_domain.CollectionPurpose.SOURCE_TEST))
        uow.runs.add(make_run(ws, run_id='run-5', purpose=run_domain.CollectionPurpose.SOURCE_TEST))
        uow.commit()

    assert count(db, 'cp_collection_runs') == 4
    cols = {
        r[0]
        for r in run_sql(
            db,
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = 'cp_collection_runs'",
        )
    }
    assert not any('policy' in c for c in cols)


def test_package_unique(db, manager, ws):
    seed_run(manager, ws)
    record = make_package()
    with make_uow(manager, ws) as uow:
        uow.packages.add(record)
        uow.commit()

    with make_uow(manager, ws) as uow:
        with pytest.raises(DuplicatePackageError):
            uow.packages.add(record)
        uow.packages.add(make_package(fingerprint='fp-2'))
        uow.packages.add(make_package(locator='https://example.org/b'))
        uow.commit()

    assert count(db, 'cp_collected_document_packages') == 3
    assert count(db, 'cp_fetch_observations') == 3


def test_receipt_unique(db, manager, ws, ws2):
    receipt = make_receipt(ws)
    with make_uow(manager, ws) as uow:
        uow.receipts.put(receipt)
        uow.commit()

    with make_uow(manager, ws) as uow:
        with pytest.raises(DuplicateReceiptError):
            uow.receipts.put(receipt)
        uow.receipts.put(make_receipt(ws2))
        uow.receipts.put(make_receipt(ws, 'key-2'))
        uow.commit()


def test_append_only_tables_reject_update_delete(db, manager, ws):
    seed_run(manager, ws)
    with make_uow(manager, ws) as uow:
        uow.packages.add(make_package())
        uow.receipts.put(make_receipt(ws))
        uow.checkpoints.advance(make_checkpoint(), ['item-1'])
        uow.commit()

    tables = (
        'cp_source_command_receipts',
        'cp_collected_document_packages',
        'cp_fetch_observations',
        'cp_collection_checkpoints',
    )
    for t in tables:
        with pytest.raises(psycopg.errors.RaiseException):
            run_sql(db, f'UPDATE controlplane.{t} SET created_at = CURRENT_TIMESTAMP')
        with pytest.raises(psycopg.errors.RaiseException):
            run_sql(db, f'DELETE FROM controlplane.{t}')


def test_checkpoint_advance_only_over_durable_items(db, manager, ws):
    seed_run(manager, ws)
    cp1 = make_checkpoint(1, ('item-1',))
    with make_uow(manager, ws) as uow:
        uow.checkpoints.advance(cp1, ['item-1'])
        uow.commit()

    with make_uow(manager, ws) as uow:
        cp2 = make_checkpoint(2, ('item-1b', 'item-2'))
        with pytest.raises(CheckpointRejected) as exc_info:
            uow.checkpoints.advance(cp2, ['item-1b'])
        assert exc_info.value.code == 'CHECKPOINT_ITEM_NOT_DURABLE'
        assert uow.checkpoints.get_latest('src-1') == cp1
        assert count(db, 'cp_collection_checkpoints') == 1
        with pytest.raises(CheckpointRejected) as exc_info2:
            uow.checkpoints.advance(make_checkpoint(3, ('x',)), ['x'])
        assert exc_info2.value.code == 'CHECKPOINT_REVISION_CONFLICT'
        assert uow.checkpoints.advance(cp2, ['item-1b', 'item-2']) == cp2
        uow.commit()

    with make_uow(manager, ws) as uow:
        assert uow.checkpoints.get_latest('src-1') == cp2
        assert count(db, 'cp_collection_checkpoints') == 2


def test_uow_rollback_discards_aggregate_and_outbox(db, manager, ws):
    with pytest.raises(RuntimeError):
        with make_uow(manager, ws) as uow:
            uow.sources.add(make_source(ws))
            uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dedup-1')
            raise RuntimeError('boom')
    assert count(db, 'cp_sources') == 0
    assert count(db, 'cp_source_identities') == 0
    assert count(db, 'cp_outbox_events') == 0


def test_uow_exit_without_commit_rolls_back(db, manager, ws):
    with make_uow(manager, ws) as uow:
        uow.sources.add(make_source(ws))
        uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dedup-1')
    assert count(db, 'cp_sources') == 0
    assert count(db, 'cp_source_identities') == 0
    assert count(db, 'cp_outbox_events') == 0


def test_uow_commit_persists_aggregate_and_outbox_together(db, manager, ws):
    with make_uow(manager, ws) as uow:
        uow.sources.add(make_source(ws))
        uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dedup-1')
        uow.commit()
    assert count(db, 'cp_sources') == 1
    assert count(db, 'cp_outbox_events') == 1
    row = run_sql(db, 'SELECT workspace_id::text, event_name, aggregate_id, published, payload FROM controlplane.cp_outbox_events')[0]
    assert row[0] == ws
    assert row[1] == 'SourceRegistered'
    assert row[2] == 'src-1'
    assert row[3] is False
    assert row[4] == {'k': 'v'}


def test_outbox_deduplication_id_keeps_one_row(db, manager, ws):
    with make_uow(manager, ws) as uow:
        id1 = uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dup-1')
        id2 = uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dup-1')
        assert id1 == id2 == str(uuid.uuid5(uuid.NAMESPACE_URL, 'dup-1'))
        uow.commit()
    with make_uow(manager, ws) as uow:
        id3 = uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dup-1')
        assert id3 == id1
        uow.commit()
    assert count(db, 'cp_outbox_events') == 1


def test_outbox_unsafe_payload_aborts_aggregate(db, manager, ws):
    with pytest.raises(ValueError):
        with make_uow(manager, ws) as uow:
            uow.sources.add(make_source(ws))
            uow.outbox.append_event('SourceRegistered', 'src-1', {'access_token': 'x'}, 'dedup-unsafe')
    assert count(db, 'cp_sources') == 0


def test_outbox_workspace_and_recovery_epoch(db, manager, ws, ws2):
    uow_no_ws = PostgresSourceIngestionUnitOfWork(manager)
    with pytest.raises(ValueError):
        with uow_no_ws:
            uow_no_ws.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'dedup-nows')
    with PostgresSourceIngestionUnitOfWork(manager) as uow:
        uow.outbox.append_event('SourceRegistered', 'src-1', {'workspace_id': ws2, 'recovery_epoch': '7'}, 'dedup-epoch-num')
        uow.commit()
    target_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'dedup-epoch-num'))
    row = run_sql(db, 'SELECT workspace_id::text, recovery_epoch FROM controlplane.cp_outbox_events WHERE event_id = %s', (target_id,))[0]
    assert row[0] == ws2
    assert row[1] == 7
    with PostgresSourceIngestionUnitOfWork(manager) as uow:
        uow.outbox.append_event('SourceRegistered', 'src-1', {'workspace_id': ws2, 'recovery_epoch': 'epoch-x'}, 'dedup-epoch-str')
        uow.commit()
    target_id2 = str(uuid.uuid5(uuid.NAMESPACE_URL, 'dedup-epoch-str'))
    row2 = run_sql(db, 'SELECT workspace_id::text, recovery_epoch FROM controlplane.cp_outbox_events WHERE event_id = %s', (target_id2,))[0]
    assert row2[0] == ws2
    assert row2[1] is None


class CountingManager:
    def __init__(self, inner):
        self.inner = inner
        self.borrowed = 0

    def borrow_connection(self):
        self.borrowed += 1
        return self.inner.borrow_connection()


def test_uow_borrows_exactly_one_connection(db, manager, ws):
    counting = CountingManager(manager)
    uow = PostgresSourceIngestionUnitOfWork(counting, workspace_id=ws)
    with uow:
        uow.sources.add(make_source(ws))
        uow.runs.add(make_run(ws))
        uow.receipts.put(make_receipt(ws))
        uow.packages.get('src-1', 'l', 'f')
        uow.candidates.get(ws, 'x')
        uow.checkpoints.get_latest('src-1')
        uow.outbox.append_event('SourceRegistered', 'src-1', {'k': 'v'}, 'd1')
        uow.commit()
        assert counting.borrowed == 1
    assert counting.borrowed == 1
    with uow:
        pass
    assert counting.borrowed == 2


def test_uow_not_active_and_not_reentrant(db, manager, ws):
    uow = make_uow(manager, ws)
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.sources.get(ws, 'src-1')
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.outbox.append_event('E', 'a', {}, 'd')
    with uow:
        with pytest.raises(UnitOfWorkAlreadyActiveError):
            uow.__enter__()
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.sources.get(ws, 'src-1')


def test_uow_connection_returned_to_pool(db, manager, ws):
    for _ in range(10):
        with make_uow(manager, ws) as uow:
            uow.sources.get(ws, 'src-1')
