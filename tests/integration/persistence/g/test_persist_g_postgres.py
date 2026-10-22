"""PERSIST-G: kiem tra cac kho PostgreSQL cua orchestration tren PostgreSQL 18.6."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import threading
import uuid

import psycopg
import psycopg.errors
import pytest

from controlplane.application.orchestration.grant_issuance import ActiveGrantExistsError, GrantIssuer
from controlplane.application.orchestration.job_allocation import (
    BatchTargetReachedError,
    JobAllocationService,
    JobReservation,
)
from controlplane.application.orchestration.variant_reservation_flow import (
    ReserveVariantRequest,
    VariantReservationFlow,
)
from controlplane.domain.events import DomainEvent
from controlplane.domain.orchestration import OrchestrationContractError, ReservationState
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.statemachine import JobState
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.orchestration.allocation import PostgresAllocationStore
from controlplane.infrastructure.db.orchestration.grants import PostgresGrantStore, PostgresRecoveryEpoch
from controlplane.infrastructure.db.orchestration.start_batch import PostgresStartBatchRepository
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from controlplane.infrastructure.db.uow import TransactionManager

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
ORCH_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'orchestration'
# Kế hoạch IMPL-PLAN-CONVERGENCE-EXT đã duyệt (docs/implementation/convergence-ext/slices.md, dòng 122-137)
# giao CP-5-COMPLETION tạo adapter này trong đúng thư mục orchestration; chỉ tệp này được miễn quét token cấm.
EXT_COMPLETION_ADAPTER = 'postgres_completion.py'
BANNED_ADAPTER_TOKENS = (
    'CREATE TABLE', 'ALTER TABLE', 'CREATE INDEX',
    'CompletionStorePort', 'connect(', 'ConnectionPool',
    'TransactionManager', '.commit(', '.rollback(',
    'from src.', 'import src',
)

try:
    _port = subprocess.check_output(
        ['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)
NOW = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)
CAND = AllocationCandidate('cand-1', 'angle-1')


def add_workspace(dsn: str) -> str:
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as seed:
        seed.execute(
            'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
            (workspace_id, 'w', 'ACTIVE'),
        )
    return str(workspace_id)


def count(connection, table, where='true', params=()):
    return connection.execute(
        f'SELECT count(*) FROM controlplane.{table} WHERE {where}', params
    ).fetchone()[0]


@pytest.fixture
def db():
    name = f'persist_g_{uuid.uuid4().hex[:8]}'
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


def seed_batch(conn, ws, batch_id='batch-1', target=2):
    conn.execute(
        'INSERT INTO controlplane.cp_production_batches '
        '(batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
        (batch_id, ws, 'RUNNING', target),
    )
    conn.commit()


def seed_job(conn, ws, job_id='job-1', batch_id='batch-1'):
    conn.execute(
        'INSERT INTO controlplane.cp_video_jobs '
        '(job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, %s)',
        (job_id, batch_id, ws, 'ACTIVE', 'snap-1', 1),
    )
    conn.commit()


def seed_stage(conn, ws, stage_run_id='stage-1', job_id='job-1', epoch='7'):
    conn.execute(
        'INSERT INTO controlplane.cp_stage_runs '
        '(stage_run_id, workspace_id, job_id, stage_name, attempt, status, recovery_epoch, execution_generation) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
        (stage_run_id, ws, job_id, 'render', 1, 'PENDING', epoch, 0),
    )
    conn.commit()


def seed_session(conn, ws, session_ref, status, epoch, started_at):
    conn.execute(
        'INSERT INTO controlplane.cp_app_sessions '
        '(workspace_id, session_ref, status, recovery_epoch, started_at) VALUES (%s, %s, %s, %s, %s)',
        (ws, session_ref, status, epoch, started_at),
    )
    conn.commit()


def test_migrations_to_18_and_schema_matches_0011(db):
    with psycopg.connect(db[0], autocommit=True) as connection:
        rows = connection.execute(
            'SELECT version FROM controlplane.cp_schema_migrations ORDER BY version'
        ).fetchall()
        assert [r[0] for r in rows] == list(range(1, 19))

        table_cols = {
            'cp_execution_grants': {
                'grant_id', 'workspace_id', 'stage_run_id', 'execution_generation',
                'recovery_epoch', 'worker_lease_id', 'issued_at', 'expires_at',
                'allowed_operation', 'input_fingerprint', 'revoked_at', 'created_at',
            },
            'cp_stage_runs': {
                'stage_type', 'input_refs', 'dependency_refs', 'wait_reason',
                'problem', 'started_at', 'finished_at', 'updated_at', 'superseded_by',
            },
            'cp_video_jobs': {
                'wait_reason', 'parent_variant_ref', 'prior_variant_ref',
            },
            'cp_completion_ledger': {
                'completion_id', 'session_ref', 'cloud_location_ref',
                'cloud_location_verification_ref', 'snapshot_ref', 'script_version_ref',
                'production_plan_ref', 'preset_revision_ref', 'quality_report_ref',
                'variant_validation_ref', 'media_usage_manifest', 'output_naming_metadata',
                'cost_usage_summary', 'cleanup_policy_ref',
            },
            'cp_production_batches': {
                'stop_reason', 'stopped_at',
            },
            'cp_orchestration_receipts': {
                'workspace_id', 'idempotency_key', 'request_hash', 'aggregate_ref',
                'aggregate_revision', 'created_at',
            },
            'cp_cleanup_eligibility': {
                'workspace_id', 'cleanup_eligibility_id', 'video_job_id',
                'artifact_version_id', 'cleanup_policy_ref', 'eligible_at', 'status',
                'created_at', 'updated_at',
            },
            'cp_app_sessions': {
                'workspace_id', 'session_ref', 'status', 'recovery_epoch',
                'started_at', 'ended_at', 'created_at', 'updated_at',
            },
        }

        for table, expected in table_cols.items():
            cols = connection.execute(
                'SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s',
                ('controlplane', table),
            ).fetchall()
            col_names = {r[0] for r in cols}
            assert expected <= col_names, f'Missing columns in {table}: {expected - col_names}'

        for table in ('cp_stage_runs', 'cp_execution_grants', 'cp_app_sessions'):
            dt = connection.execute(
                'SELECT data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s AND column_name = %s',
                ('controlplane', table, 'recovery_epoch'),
            ).fetchone()[0]
            assert dt == 'text', f'recovery_epoch in {table} is {dt}, expected text'


class FixedEpoch:
    def __init__(self, value: object) -> None:
        self._value = value

    def current(self) -> object:
        return self._value


def issue(conn, ws, stage='stage-1', lease='lease-1', epoch='7', op='render', fp='fp-1') -> GrantClaims:
    return GrantIssuer(PostgresGrantStore(conn, ws), FixedEpoch(epoch)).issue(stage, op, fp, lease, 3600, NOW)


def test_grant_round_trip_revoke_and_monotonic_generation(conn, db):
    seed_batch(conn, db[1])
    seed_job(conn, db[1])
    seed_stage(conn, db[1])
    claims = issue(conn, db[1])
    conn.commit()
    assert claims.execution_generation == 1 and claims.recovery_epoch == '7'

    with psycopg.connect(db[0]) as other:
        store_other = PostgresGrantStore(other, db[1])
        assert store_other.active_grant('stage-1', NOW) == claims
        assert store_other.latest_generation('stage-1') == 1
        assert store_other.active_grant('missing', NOW) is None
        assert store_other.latest_generation('missing') == 0

    assert issue(conn, db[1]) == claims
    assert count(conn, 'cp_execution_grants') == 1

    store = PostgresGrantStore(conn, db[1])
    store.revoke(claims.grant_id)
    assert store.active_grant('stage-1', NOW) is None
    assert store.latest_generation('stage-1') == 1
    store.revoke(claims.grant_id)

    second = issue(conn, db[1])
    assert second.execution_generation == 2 and second.grant_id != claims.grant_id
    assert count(conn, 'cp_execution_grants') == 2
    assert count(conn, 'cp_execution_grants', 'revoked_at IS NULL') == 1


def test_active_grant_blocks_other_lease_and_epoch_change_supersedes(conn, db):
    seed_batch(conn, db[1])
    seed_job(conn, db[1])
    seed_stage(conn, db[1])
    claims = issue(conn, db[1])
    conn.commit()
    assert count(conn, 'cp_execution_grants') == 1

    with pytest.raises(ActiveGrantExistsError):
        issue(conn, db[1], lease='lease-2')

    second = issue(conn, db[1], epoch='8')
    assert second.execution_generation == 2 and second.recovery_epoch == '8'
    assert count(conn, 'cp_execution_grants', 'revoked_at IS NOT NULL') == 1


def test_db_rejects_duplicate_generation_and_second_active_lease(conn, db):
    seed_batch(conn, db[1])
    seed_job(conn, db[1])
    seed_stage(conn, db[1])
    claims = issue(conn, db[1])
    conn.commit()
    store = PostgresGrantStore(conn, db[1])

    def raw_insert(conn, ws, generation):
        conn.execute(
            'INSERT INTO controlplane.cp_execution_grants '
            '(grant_id, workspace_id, stage_run_id, execution_generation, recovery_epoch, worker_lease_id, '
            'issued_at, expires_at, allowed_operation, input_fingerprint) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (
                str(uuid.uuid4()), ws, 'stage-1', generation, '7', 'lease-9',
                NOW, NOW + timedelta(hours=1), 'render', 'fp-1'
            ),
        )

    assert count(conn, 'cp_execution_grants') == 1
    with pytest.raises(psycopg.errors.UniqueViolation):
        raw_insert(conn, db[1], 1)
    conn.rollback()

    with pytest.raises(psycopg.errors.UniqueViolation):
        raw_insert(conn, db[1], 2)
    conn.rollback()

    store.revoke(claims.grant_id)
    conn.commit()

    with pytest.raises(psycopg.errors.UniqueViolation):
        raw_insert(conn, db[1], 1)
    conn.rollback()

    with pytest.raises(ValueError):
        store.insert(GrantClaims(
            grant_id=str(uuid.uuid4()),
            stage_run_id='stage-1',
            execution_generation=1,
            recovery_epoch='7',
            worker_lease_id='lease-9',
            issued_at='2026-10-22T08:00:00Z',
            expires_at='2026-10-22T09:00:00Z',
            allowed_operation='render',
            input_fingerprint='fp-1',
        ))
    assert store.latest_generation('stage-1') == 1

    store.insert(GrantClaims(
        grant_id=str(uuid.uuid4()),
        stage_run_id='stage-1',
        execution_generation=2,
        recovery_epoch='7',
        worker_lease_id='lease-9',
        issued_at='2026-10-22T08:00:00Z',
        expires_at='2026-10-22T09:00:00Z',
        allowed_operation='render',
        input_fingerprint='fp-1',
    ))
    assert store.latest_generation('stage-1') == 2

    with pytest.raises(ValueError):
        store.insert(GrantClaims(
            grant_id=str(uuid.uuid4()),
            stage_run_id='stage-1',
            execution_generation=2,
            recovery_epoch='7',
            worker_lease_id='lease-9',
            issued_at='2026-10-22T08:00:00Z',
            expires_at='2026-10-22T09:00:00Z',
            allowed_operation='render',
            input_fingerprint='fp-1',
        ))
    assert count(conn, 'cp_execution_grants') == 2


def make_event(ws: str) -> DomainEvent:
    return DomainEvent(
        contract_name='orchestration.grant.issued',
        contract_version=1,
        message_id=str(uuid.uuid4()),
        workspace_id=ws,
        correlation_id='corr-1',
        causation_id=None,
        trace_context=None,
        occurred_at='2026-10-22T08:00:00Z',
        actor='persist-g-test',
        recovery_epoch=7,
        payload={'stage_run_id': 'stage-1'},
        event_id=str(uuid.uuid4()),
        event_name='GrantIssued',
        aggregate_type='stage_run',
        aggregate_id='stage-1',
        aggregate_revision=1,
        producer='persist-g-test',
        schema_version=1,
        sensitivity='internal',
    )


def test_recovery_epoch_is_text_and_compared_with_str(conn, db):
    ws = db[1]
    seed_batch(conn, ws)
    seed_job(conn, ws)
    seed_stage(conn, ws, 'stage-1', epoch='007')
    seed_stage(conn, ws, 'stage-2', epoch='12')
    seed_stage(conn, ws, 'stage-3')
    seed_stage(conn, ws, 'stage-4')

    seed_session(conn, ws, 's1', 'ACTIVE', '7', datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc))
    seed_session(conn, ws, 's2', 'ENDED', '9', datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc))

    epochs = PostgresRecoveryEpoch(conn, ws)
    assert epochs.current() == '7'

    seed_session(conn, ws, 's3', 'ACTIVE', 'epoch-b', datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc))
    assert epochs.current() == 'epoch-b'

    epoch_val = conn.execute("SELECT recovery_epoch FROM controlplane.cp_stage_runs WHERE stage_run_id = 'stage-1'").fetchone()[0]
    assert epoch_val == '007' and isinstance(epoch_val, str)

    a = GrantIssuer(PostgresGrantStore(conn, ws), FixedEpoch(7)).issue('stage-2', 'render', 'fp', 'lease-1', 3600, NOW)
    b = GrantIssuer(PostgresGrantStore(conn, ws), FixedEpoch('7')).issue('stage-3', 'render', 'fp', 'lease-1', 3600, NOW)
    assert a.recovery_epoch == b.recovery_epoch == '7' and str(a.recovery_epoch) == str(b.recovery_epoch)

    ga = PostgresGrantStore(conn, ws).active_grant('stage-2', NOW)
    gb = PostgresGrantStore(conn, ws).active_grant('stage-3', NOW)
    assert ga is not None and gb is not None
    assert str(ga.recovery_epoch) == '7' and str(gb.recovery_epoch) == '7'

    c = GrantIssuer(PostgresGrantStore(conn, ws), PostgresRecoveryEpoch(conn, ws)).issue('stage-4', 'render', 'fp', 'lease-1', 3600, NOW)
    assert c.recovery_epoch == 'epoch-b'
    gc = PostgresGrantStore(conn, ws).active_grant('stage-4', NOW)
    assert gc is not None and gc.recovery_epoch == 'epoch-b'

    d = GrantIssuer(PostgresGrantStore(conn, ws), FixedEpoch('007')).issue('stage-1', 'render', 'fp', 'lease-1', 3600, NOW)
    gd = PostgresGrantStore(conn, ws).active_grant('stage-1', NOW)
    assert gd is not None and gd.recovery_epoch == '007' and '007' != str(7)

    ws2 = add_workspace(db[0])
    with pytest.raises(OrchestrationContractError) as exc_info:
        PostgresRecoveryEpoch(conn, ws2).current()
    assert exc_info.value.code == 'NOT_FOUND'


def test_grant_and_outbox_roll_back_together(db):
    dsn, ws = db
    with psycopg.connect(dsn, autocommit=True) as seed_c:
        seed_batch(seed_c, ws, target=1)
        seed_job(seed_c, ws, 'job-1')
        seed_stage(seed_c, ws, 'stage-1', epoch='7')

    manager = TransactionManager(dsn, pool_max_size=2)
    observer = psycopg.connect(dsn, autocommit=True)

    try:
        def work(uow):
            JobAllocationService(PostgresAllocationStore(uow.connection, ws)).allocate(
                'batch-1', 'job-new', AllocationCandidate('cand-1', 'angle-1')
            )
            GrantIssuer(PostgresGrantStore(uow.connection, ws), FixedEpoch('7')).issue(
                'stage-1', 'render', 'fp-1', 'lease-1', 3600, NOW
            )
            PostgresOutboxRepository(uow.connection).enqueue(make_event(ws))

        with pytest.raises(RuntimeError, match='boom'):
            with manager.unit_of_work() as uow:
                work(uow)
                assert count(observer, 'cp_execution_grants') == 0
                raise RuntimeError('boom')

        assert count(observer, 'cp_execution_grants') == 0
        assert count(observer, 'cp_outbox_events') == 0
        assert count(observer, 'cp_video_jobs') == 1
        assert count(observer, 'cp_batch_capacity_reservations') == 0

        with manager.unit_of_work() as uow:
            work(uow)

        assert count(observer, 'cp_execution_grants') == 1
        assert count(observer, 'cp_outbox_events') == 1
        assert count(observer, 'cp_video_jobs') == 2
        assert count(observer, 'cp_batch_capacity_reservations') == 1
    finally:
        manager.close()
        observer.close()


def test_allocation_round_trip_and_idempotent_replay(conn, db):
    ws = db[1]
    seed_batch(conn, ws, 'batch-1', target=2)
    seed_batch(conn, ws, 'batch-2')
    store = PostgresAllocationStore(conn, ws)
    service = JobAllocationService(store)

    first = service.allocate('batch-1', 'job-1', CAND)
    conn.commit()

    assert count(conn, 'cp_video_jobs') == 1
    assert count(conn, 'cp_batch_capacity_reservations', "state = 'ACTIVE'") == 1
    assert first == JobReservation('batch-1', 'job-1', first.reservation_id, 'angle-1')
    assert first.reservation_id != ''

    assert store.find_reservation('job-1') == first
    assert store.find_reservation('missing') is None

    assert service.allocate('batch-1', 'job-1', CAND) == first
    assert count(conn, 'cp_video_jobs') == 1

    snap = conn.execute("SELECT snapshot_ref FROM controlplane.cp_video_jobs WHERE job_id = 'job-1'").fetchone()[0]
    assert snap == 'allocation:angle-1'

    with pytest.raises(ValueError):
        service.allocate('batch-2', 'job-1', CAND)

    with pytest.raises(OrchestrationContractError) as exc_info:
        service.allocate('missing', 'job-9', CAND)
    assert exc_info.value.code == 'NOT_FOUND'

    with pytest.raises(RuntimeError):
        with store.lock_batch('batch-1') as target:
            assert target == 2
            store.create_job_and_reservation('batch-1', 'job-x', AllocationCandidate('c-x', 'angle-x'))
            raise RuntimeError('boom')

    assert count(conn, 'cp_video_jobs') == 1
    assert count(conn, 'cp_batch_capacity_reservations') == 1


def test_allocation_counts_ledger_and_active_and_respects_target(conn, db):
    ws = db[1]
    seed_batch(conn, ws, 'batch-1', target=2)
    store = PostgresAllocationStore(conn, ws)
    service = JobAllocationService(store)

    reservation = service.allocate('batch-1', 'job-1', CAND)
    assert count(conn, 'cp_video_jobs') == 1
    conn.execute(
        'INSERT INTO controlplane.cp_artifact_versions '
        '(artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, '
        'artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
        (
            '00000000-0000-0000-0000-000000005b01', ws, 'artifact-g', 'a' * 64, 128,
            'video/mp4', 'rendered_video', 'owner-g', 'lineage-g', 'retention-g', 'internal'
        ),
    )
    conn.execute(
        'INSERT INTO controlplane.cp_variant_reservations '
        '(reservation_id, workspace_id, job_id, fingerprint, snapshot_scope, validation_ref, '
        'variation_policy_revision, expected_registry_revision, committed_registry_revision, state) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
        ('variant-1', ws, 'job-1', 'fp-1', 'scope', 'val', 'policy', 1, 1, 'ACTIVE'),
    )
    conn.execute(
        'INSERT INTO controlplane.cp_completion_ledger '
        '(ledger_id, workspace_id, job_id, batch_id, capacity_reservation_id, variant_reservation_id, '
        'output_artifact_version_id, output_artifact_hash, actor_ref, completed_at, audit_ref) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)',
        (
            str(uuid.uuid4()), ws, 'job-1', 'batch-1', reservation.reservation_id,
            'variant-1', '00000000-0000-0000-0000-000000005b01', 'a' * 64, 'actor-1', 'audit-1'
        ),
    )
    conn.execute(
        "UPDATE controlplane.cp_batch_capacity_reservations SET state = 'CONVERTED' "
        "WHERE workspace_id = %s AND reservation_id = %s",
        (ws, reservation.reservation_id),
    )
    conn.commit()

    assert store.count_ledger('batch-1') == 1
    assert store.count_active('batch-1') == 0
    assert store.count_active('missing') == 0

    service.allocate('batch-1', 'job-2', AllocationCandidate('cand-2', 'angle-2'))
    conn.commit()
    assert store.count_active('batch-1') == 1
    assert count(conn, 'cp_video_jobs') == 2

    with pytest.raises(BatchTargetReachedError):
        service.allocate('batch-1', 'job-3', AllocationCandidate('cand-3', 'angle-3'))
    conn.rollback()
    assert count(conn, 'cp_video_jobs') == 2


def test_two_parallel_connections_never_exceed_target(db):
    dsn, ws = db
    with psycopg.connect(dsn, autocommit=True) as c:
        seed_batch(c, ws, 'batch-t1', target=1)
        seed_batch(c, ws, 'batch-t2', target=2)

    def race(dsn, ws, batch_id, workers):
        barrier = threading.Barrier(workers)
        outcomes = []
        lock = threading.Lock()

        def worker_fn(i):
            with psycopg.connect(dsn) as c:
                service = JobAllocationService(PostgresAllocationStore(c, ws))
                barrier.wait(timeout=30)
                try:
                    service.allocate(
                        batch_id,
                        f'{batch_id}-job-{i}',
                        AllocationCandidate(f'cand-{i}', f'angle-{i}'),
                    )
                    c.commit()
                    result = 'ok'
                except BatchTargetReachedError:
                    c.rollback()
                    result = 'full'
                except Exception as exc:
                    c.rollback()
                    result = repr(exc)
                with lock:
                    outcomes.append(result)

        threads = [threading.Thread(target=worker_fn, args=(i,)) for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads)
        return sorted(outcomes)

    assert race(dsn, ws, 'batch-t1', 4) == ['full', 'full', 'full', 'ok']
    assert race(dsn, ws, 'batch-t2', 4) == ['full', 'full', 'ok', 'ok']

    with psycopg.connect(dsn) as obs:
        assert count(obs, 'cp_video_jobs', 'batch_id = %s', ('batch-t1',)) == 1
        assert count(obs, 'cp_video_jobs', 'batch_id = %s', ('batch-t2',)) == 2
        assert count(obs, 'cp_batch_capacity_reservations', "batch_id = %s AND state = 'ACTIVE'", ('batch-t1',)) == 1
        assert count(obs, 'cp_batch_capacity_reservations', "batch_id = %s AND state = 'ACTIVE'", ('batch-t2',)) == 2


def req(ws, job, fp, expected, key):
    return ReserveVariantRequest(
        workspace_id=ws,
        job_id=job,
        fingerprint=fp,
        snapshot_scope='scope-1',
        validation_ref='val-1',
        variation_policy_revision='policy-1',
        expected_registry_revision=expected,
        idempotency_key=key,
    )


def test_variant_registry_round_trip_conflicts_and_settle(conn, db):
    ws = db[1]
    seed_batch(conn, ws)
    seed_job(conn, ws, 'job-a')
    seed_job(conn, ws, 'job-b')
    seed_job(conn, ws, 'job-c')
    seed_job(conn, ws, 'job-d')

    registry = PostgresVariantRegistry(conn)
    flow = VariantReservationFlow(registry)
    assert registry.current_revision(ws) == 1

    r1 = flow.reserve(req(ws, 'job-a', 'fp-a', 1, 'idem-a'))
    conn.commit()

    assert r1.state == ReservationState.ACTIVE
    assert r1.committed_registry_revision == 2
    assert registry.current_revision(ws) == 2
    assert flow.reserve(req(ws, 'job-a', 'fp-a', 1, 'idem-a')) == r1

    with psycopg.connect(db[0]) as other:
        reg_other = PostgresVariantRegistry(other)
        rec = reg_other.find_by_job(ws, 'job-a')
        assert rec is not None
        assert rec.idempotency_key == 'idem-a'
        assert rec.fingerprint == 'fp-a'
        assert rec.expected_registry_revision == 1
        assert rec.committed_registry_revision == 2
        assert rec.state == ReservationState.ACTIVE
        assert reg_other.find_active_by_fingerprint(ws, 'fp-a') == rec
        assert reg_other.find_by_job(ws, 'missing') is None
        assert reg_other.find_active_by_fingerprint(ws, 'nope') is None

    assert count(conn, 'cp_orchestration_receipts') == 1
    with pytest.raises(OrchestrationContractError) as e1:
        flow.reserve(req(ws, 'job-a', 'fp-x', 2, 'idem-x'))
    assert e1.value.code == 'VARIANT_CONFLICT'

    with pytest.raises(OrchestrationContractError) as e2:
        flow.reserve(req(ws, 'job-b', 'fp-a', 2, 'idem-b'))
    assert e2.value.code == 'VARIANT_CONFLICT'

    with pytest.raises(OrchestrationContractError) as e3:
        flow.reserve(req(ws, 'job-b', 'fp-b', 1, 'idem-b'))
    assert e3.value.code == 'VARIANT_VALIDATION_STALE'

    r2 = flow.reserve(req(ws, 'job-b', 'fp-b', 2, 'idem-b'))
    assert r2.committed_registry_revision == 3

    assert flow.convert(ws, 'job-a', JobState.COMPLETED).state == ReservationState.CONVERTED
    assert flow.release(ws, 'job-b', JobState.FAILED_FINAL).state == ReservationState.RELEASED

    r3 = flow.reserve(req(ws, 'job-c', 'fp-b', 5, 'idem-c'))
    assert r3.state == ReservationState.ACTIVE
    assert r3.committed_registry_revision == 6
    conn.commit()
    assert count(conn, 'cp_orchestration_receipts') == 3

    with pytest.raises(psycopg.errors.UniqueViolation):
        flow.reserve(req(ws, 'job-d', 'fp-d', 6, 'idem-a'))
    conn.rollback()

    assert registry.current_revision(ws) == 6
    assert registry.find_by_job(ws, 'job-d') is None


def test_start_batch_repository_records_stop_reason(conn, db):
    repo = PostgresStartBatchRepository(conn)
    repo.insert(workspace_id=db[1], batch_id='batch-s', target_count=3)
    assert repo.stop(workspace_id=db[1], batch_id='batch-s', reason='USER_STOP') is True

    row = conn.execute(
        'SELECT stop_reason, stopped_at FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s',
        (db[1], 'batch-s'),
    ).fetchone()
    assert row is not None
    assert row[0] == 'USER_STOP' and row[1] is not None

    assert repo.stop(workspace_id=db[1], batch_id='batch-s', reason='OTHER') is False
    row2 = conn.execute(
        'SELECT stop_reason FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s',
        (db[1], 'batch-s'),
    ).fetchone()
    assert row2[0] == 'USER_STOP'

    assert repo.stop(workspace_id=db[1], batch_id='missing', reason='OTHER') is False

    with pytest.raises(ValueError):
        repo.stop(workspace_id=db[1], batch_id='batch-s', reason='  ')


def banned_tokens_in(orch_dir: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for source in sorted(orch_dir.rglob('*.py')):
        name = source.relative_to(orch_dir).as_posix()
        if name == EXT_COMPLETION_ADAPTER:
            continue
        text = source.read_text(encoding='utf-8')
        for banned in BANNED_ADAPTER_TOKENS:
            if banned in text:
                found.append((name, banned))
    return found


def test_adapter_source_has_no_ddl_completion_store_or_transaction_control():
    files = list(ORCH_DIR.rglob('*.py'))
    assert (ORCH_DIR / 'grants.py') in files
    assert (ORCH_DIR / 'allocation.py') in files
    assert (ORCH_DIR / 'variants.py') in files

    assert banned_tokens_in(ORCH_DIR) == []


def write_orch_files(orch_dir: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        (orch_dir / name).write_text(content, encoding='utf-8')


def test_banned_tokens_in_ignores_ext_completion_adapter(tmp_path):
    write_orch_files(tmp_path, {
        'grants.py': 'x = 1\n',
        EXT_COMPLETION_ADAPTER: (
            'from controlplane.infrastructure.db.uow import TransactionManager\n'
            'class CompletionStorePort: ...\n'
            'connection.commit()\n'
            'connection.rollback()\n'
            '# .commit( .rollback(\n'
        ),
    })
    assert banned_tokens_in(tmp_path) == []


def test_banned_tokens_in_flags_commit_in_grants(tmp_path):
    write_orch_files(tmp_path, {
        'grants.py': 'connection.commit()\n',
        EXT_COMPLETION_ADAPTER: 'x = 1\n',
    })
    assert banned_tokens_in(tmp_path) == [('grants.py', '.commit(')]


def test_banned_tokens_in_flags_ddl_in_variants(tmp_path):
    write_orch_files(tmp_path, {
        'variants.py': "SQL = 'CREATE TABLE t (id int)'\n",
        EXT_COMPLETION_ADAPTER: 'x = 1\n',
    })
    assert banned_tokens_in(tmp_path) == [('variants.py', 'CREATE TABLE')]


def test_banned_tokens_in_flags_transaction_manager_in_new_file(tmp_path):
    write_orch_files(tmp_path, {
        'extra.py': 'from controlplane.infrastructure.db.uow import TransactionManager\n',
        EXT_COMPLETION_ADAPTER: 'x = 1\n',
    })
    assert banned_tokens_in(tmp_path) == [('extra.py', 'TransactionManager')]
