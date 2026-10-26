"""CP-5-COMPLETION: PostgresCompletionUnitOfWork trên PostgreSQL 18.6 thật, không kho tạm, không fake (CT-ORC-008, TST-WF-INV-010, TST-WF-INV-017)."""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import tomllib
import uuid

import psycopg
import psycopg.errors
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from catalog.application.usage import MediaUsageRecorder
from catalog.persistence.usage import media_usage_repository_factory
from controlplane.api.wiring.completion import build_completion_service
from controlplane.application.orchestration.commit_completion import (
    CommitVideoCompletion,
    CompletionContext,
    CompletionRejectedError,
)
from controlplane.domain.orchestration.completion_gate import GateAction
from controlplane.domain.orchestration.fencing import (
    ACCEPTED,
    STALE_RECOVERY_EPOCH,
    FencingDecision,
    GrantClaims,
    evaluate_result_fencing,
)
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.orchestration.grants import PostgresRecoveryEpoch
from controlplane.infrastructure.db.orchestration.postgres_completion import (
    PostgresCompletionUnitOfWork,
    PostgresMediaUsagePort,
)
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / 'src/controlplane/infrastructure/db/migrations'
FIXTURE = json.loads((ROOT / 'tests/fixtures/contracts/g-c-i-completion/payloads.json').read_text(encoding='utf-8'))
REQUEST_TEMPLATE = FIXTURE['entities']['CommitVideoCompletionRequest']['valid'][0]
LEDGER_TEMPLATE = FIXTURE['entities']['CompletionLedgerEntry']['valid'][0]
REGISTRY_REVISION = 12
JOB_REVISION = 3


def admin_dsn() -> str:
    candidate = os.environ.get('M2_TEST_PG_DSN')
    if not candidate:
        try:
            out = subprocess.check_output(
                ['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            first_line = out.strip().splitlines()[0]
            port = first_line.rsplit(':', 1)[-1].strip()
            candidate = f'postgresql://m2test:m2test@127.0.0.1:{port}/postgres'
        except Exception as exc:
            pytest.fail(f'BLOCKED_EXTERNAL: cannot discover docker postgres port: {exc}')
    try:
        with psycopg.connect(candidate, connect_timeout=5):
            pass
    except Exception as exc:
        pytest.fail(f'BLOCKED_EXTERNAL: cannot connect to postgres admin db: {exc}')
    return candidate


@pytest.fixture(scope='module')
def dsn():
    admin = admin_dsn()
    with psycopg.connect(admin, autocommit=True) as conn:
        ver = conn.execute('SHOW server_version').fetchone()[0]
        if not ver.startswith('18.6'):
            pytest.fail(f'BLOCKED_EXTERNAL: expected PostgreSQL 18.6, got {ver}')
        db_name = f'cp5_completion_{uuid.uuid4().hex}'
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db_name)))
    db_dsn = make_conninfo(admin, dbname=db_name)
    MigrationRunner(db_dsn, MIGRATIONS, is_test_env=True, expected_database_name=db_name).migrate_up()
    try:
        yield db_dsn
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL(
                    'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s'
                ),
                (db_name,),
            )
            conn.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(db_name)))


@pytest.fixture(scope='module')
def manager(dsn):
    tm = TransactionManager(dsn, pool_max_size=4)
    try:
        yield tm
    finally:
        tm.close()


@pytest.fixture
def observer(dsn):
    with psycopg.connect(dsn, autocommit=True) as c:
        yield c


@dataclass
class Scenario:
    workspace_id: str
    batch_id: str
    job_id: str
    request: dict
    context: CompletionContext


def seed(dsn: str, job_status: str = 'READY_FOR_COMPLETION', shared: Scenario | None = None) -> Scenario:
    with psycopg.connect(dsn, autocommit=True) as conn:
        if shared is None:
            ws = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) "
                "VALUES (%s, 'cp5', 'ACTIVE')",
                (ws,),
            )
            batch = f'batch-{uuid.uuid4().hex[:12]}'
            conn.execute(
                "INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) "
                "VALUES (%s, %s, 'RUNNING', 3)",
                (batch, ws),
            )
            conn.execute(
                "INSERT INTO controlplane.cp_variant_registry (workspace_id, current_registry_revision) "
                "VALUES (%s, 12)",
                (ws,),
            )
        else:
            ws = shared.workspace_id
            batch = shared.batch_id

        job_id = str(uuid.uuid4())
        reservation_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        sha = hashlib.sha256(job_id.encode()).hexdigest()

        conn.execute(
            "INSERT INTO controlplane.cp_video_jobs "
            "(job_id, batch_id, workspace_id, status, snapshot_ref, revision) "
            "VALUES (%s, %s, %s, %s, 'snap-1', 3)",
            (job_id, batch, ws, job_status),
        )
        conn.execute(
            "INSERT INTO controlplane.cp_batch_capacity_reservations "
            "(reservation_id, workspace_id, batch_id, job_id, state) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (f'cap-{job_id}', ws, batch, job_id),
        )
        conn.execute(
            "INSERT INTO controlplane.cp_artifact_versions "
            "(artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, "
            "artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) "
            "VALUES (%s, %s, %s, %s, 128, 'video/mp4', 'rendered_video', 'owner-g', 'lineage-g', 'retention-g', 'internal')",
            (artifact_id, ws, f'artifact-{job_id}', sha),
        )
        conn.execute(
            "INSERT INTO controlplane.cp_variant_reservations "
            "(reservation_id, workspace_id, job_id, fingerprint, snapshot_scope, validation_ref, "
            "variation_policy_revision, expected_registry_revision, committed_registry_revision, state) "
            "VALUES (%s, %s, %s, %s, 'scope', 'val', 'policy', 12, 12, 'ACTIVE')",
            (reservation_id, ws, job_id, f'fp-{job_id}'),
        )

        request = copy.deepcopy(REQUEST_TEMPLATE)
        request['video_job_id'] = job_id
        request['output_artifact_version_id'] = artifact_id
        request['output_sha256'] = sha
        request['variant_reservation_id'] = reservation_id
        request['expected_variant_registry_revision'] = 12
        request['media_usage_manifest'] = [
            {'media_asset_id': f'asset-{job_id}-1', 'role': 'illustration'},
            {'media_asset_id': f'asset-{job_id}-2', 'role': 'voice'},
        ]

        ledger_copy = copy.deepcopy(LEDGER_TEMPLATE)
        context = CompletionContext(
            completion_id=str(uuid.uuid4()),
            batch_ref=batch,
            session_ref=ledger_copy['session_ref'],
            cloud_location_ref=ledger_copy['cloud_location_ref'],
            preset_revision_ref=ledger_copy['preset_revision_ref'],
            output_naming_metadata=ledger_copy['output_naming_metadata'],
            cost_usage_summary=ledger_copy['cost_usage_summary'],
            audit_actor=ledger_copy['audit_actor'],
            cleanup_policy_ref=ledger_copy['cleanup_policy_ref'],
            completed_at=ledger_copy['completed_at'],
            fencing=FencingDecision(True, ACCEPTED),
        )
        return Scenario(workspace_id=ws, batch_id=batch, job_id=job_id, request=request, context=context)


def world(observer, workspace_id: str) -> dict:
    return {
        'ledger': observer.execute(
            "SELECT job_id, completion_id, output_artifact_hash FROM controlplane.cp_completion_ledger "
            "WHERE workspace_id = %s ORDER BY 1, 2, 3",
            (workspace_id,),
        ).fetchall(),
        'job': observer.execute(
            "SELECT job_id, status, revision FROM controlplane.cp_video_jobs "
            "WHERE workspace_id = %s ORDER BY 1, 2, 3",
            (workspace_id,),
        ).fetchall(),
        'capacity': observer.execute(
            "SELECT job_id, state FROM controlplane.cp_batch_capacity_reservations "
            "WHERE workspace_id = %s ORDER BY 1, 2",
            (workspace_id,),
        ).fetchall(),
        'variant': observer.execute(
            "SELECT job_id, state FROM controlplane.cp_variant_reservations "
            "WHERE workspace_id = %s ORDER BY 1, 2",
            (workspace_id,),
        ).fetchall(),
        'registry': observer.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry "
            "WHERE workspace_id = %s ORDER BY 1",
            (workspace_id,),
        ).fetchall(),
        'usage': observer.execute(
            "SELECT completion_id, media_asset_id, role, usage_kind FROM controlplane.cp_media_usage "
            "WHERE workspace_id = %s ORDER BY 1, 2, 3, 4",
            (workspace_id,),
        ).fetchall(),
        'outbox': observer.execute(
            "SELECT event_name, aggregate_id, aggregate_revision FROM controlplane.cp_outbox_events "
            "WHERE workspace_id = %s ORDER BY 1, 2, 3",
            (workspace_id,),
        ).fetchall(),
        'cleanup': observer.execute(
            "SELECT video_job_id, status FROM controlplane.cp_cleanup_eligibility "
            "WHERE workspace_id = %s ORDER BY 1, 2",
            (workspace_id,),
        ).fetchall(),
    }


class InjectedFailure(RuntimeError):
    pass


STORE_STEPS = (
    'insert_ledger',
    'set_job_state',
    'convert_capacity_reservation',
    'convert_variant_reservation',
    'set_registry_revision',
    'increment_batch_completed',
    'insert_outbox',
    'insert_cleanup_eligibility',
)
WRITE_STEPS = STORE_STEPS[:6] + ('record_usage',) + STORE_STEPS[6:]
POINTS = [f'{when}:{name}' for name in WRITE_STEPS for when in ('before', 'after')] + ['before:commit']


class FaultingUow(PostgresCompletionUnitOfWork):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fail_at = None
        self.log = []

    def hit(self, point: str) -> None:
        self.log.append(point)
        if point == self.fail_at:
            raise InjectedFailure(point)

    def commit(self) -> None:
        self.hit('before:commit')
        super().commit()


def _wrap(name: str):
    def method(self, *args, **kwargs):
        self.hit(f'before:{name}')
        result = getattr(PostgresCompletionUnitOfWork, name)(self, *args, **kwargs)
        self.hit(f'after:{name}')
        return result
    return method


for name in STORE_STEPS:
    setattr(FaultingUow, name, _wrap(name))


class FaultingUsage(PostgresMediaUsagePort):
    def record(self, manifest: list) -> None:
        self._uow.hit('before:record_usage')
        super().record(manifest)
        self._uow.hit('after:record_usage')


def compose(manager, scenario: Scenario, fail_at: str | None = None, usage_cls=FaultingUsage):
    uow = FaultingUow(manager, scenario.workspace_id, scenario.request)
    uow.fail_at = fail_at
    recorder = MediaUsageRecorder(media_usage_repository_factory(scenario.workspace_id))
    return uow, CommitVideoCompletion(lambda: uow, usage_cls(uow, recorder))


def test_commit_is_one_transaction_on_one_connection(dsn, manager, observer, monkeypatch):
    sc = seed(dsn)
    before = world(observer, sc.workspace_id)

    def _boom(*a, **k):
        raise AssertionError('mở kết nối thứ hai')

    class ProbingUsage(FaultingUsage):
        def record(self, manifest):
            repo = media_usage_repository_factory(sc.workspace_id)(self._uow)
            assert repo._connection is self._uow.connection
            with monkeypatch.context() as patched:
                patched.setattr(psycopg, 'connect', _boom)
                patched.setattr(psycopg.Connection, 'connect', _boom)
                super().record(manifest)
            assert world(observer, sc.workspace_id) == before

    uow, service = compose(manager, sc, usage_cls=ProbingUsage)
    result = service.execute(sc.request, sc.context)
    assert result.code == 'COMPLETED'
    w = world(observer, sc.workspace_id)
    assert len(w['ledger']) == 1
    assert w['job'] == [(sc.job_id, 'COMPLETED', 4)]
    assert w['capacity'] == [(sc.job_id, 'CONVERTED')]
    assert w['variant'] == [(sc.job_id, 'CONVERTED')]
    assert w['registry'] == [(13,)]
    assert len(w['usage']) == 2
    assert all(r[3] == 'production' for r in w['usage'])
    assert w['outbox'] == [('VideoCompleted', sc.job_id, 4)]
    assert w['cleanup'] == [(sc.job_id, 'ELIGIBLE')]
    assert [p[7:] for p in uow.log if p.startswith('before:') and p != 'before:commit'] == list(WRITE_STEPS)
    assert uow.log[-1] == 'before:commit'


@pytest.mark.parametrize('point', POINTS)
def test_failure_at_any_point_rolls_back_everything(point, dsn, manager, observer):
    sc = seed(dsn)
    before = world(observer, sc.workspace_id)
    uow, service = compose(manager, sc, fail_at=point)
    with pytest.raises(InjectedFailure):
        service.execute(sc.request, sc.context)
    assert world(observer, sc.workspace_id) == before
    assert world(observer, sc.workspace_id)['outbox'] == []
    assert uow.log[-1] == point

    uow2, service2 = compose(manager, sc)
    assert service2.execute(sc.request, sc.context).code == 'COMPLETED'
    w = world(observer, sc.workspace_id)
    assert len(w['ledger']) == 1
    assert len(w['usage']) == 2
    assert len(w['outbox']) == 1


def test_repeat_five_times_counts_once(dsn, manager, observer):
    sc = seed(dsn)
    service = build_completion_service(manager, sc.workspace_id)
    results = [service.complete(copy.deepcopy(sc.request), sc.context) for _ in range(5)]
    assert [r.code for r in results] == ['COMPLETED'] + ['ALREADY_COMPLETED'] * 4
    first_completion_id = results[0].ledger['completion_id']
    assert all(r.ledger['completion_id'] == first_completion_id for r in results)
    w = world(observer, sc.workspace_id)
    assert len(w['ledger']) == 1
    assert len(w['usage']) == 2
    assert len(w['outbox']) == 1
    assert len(w['cleanup']) == 1
    assert w['registry'] == [(13,)]
    assert w['job'][0][2] == 4


@pytest.mark.parametrize('field', ['output_sha256', 'snapshot_ref', 'variant_validation_ref', 'media_usage_manifest'])
def test_same_job_different_input_is_conflict(field, dsn, manager, observer):
    sc = seed(dsn)
    service = build_completion_service(manager, sc.workspace_id)
    service.complete(copy.deepcopy(sc.request), sc.context)
    before = world(observer, sc.workspace_id)
    req = copy.deepcopy(sc.request)
    if field == 'output_sha256':
        req[field] = 'f' * 64
    elif field == 'media_usage_manifest':
        req[field] = []
    else:
        req[field] = str(req[field]) + '-changed'
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(req, sc.context)
    assert info.value.code == 'CONFLICT'
    assert world(observer, sc.workspace_id) == before


def test_missing_cloud_verification(dsn, manager, observer):
    sc = seed(dsn)
    service = build_completion_service(manager, sc.workspace_id)
    sc.request['cloud_location_verification_ref'] = '  '
    before = world(observer, sc.workspace_id)
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(copy.deepcopy(sc.request), sc.context)
    assert info.value.code == 'CLOUD_VERIFICATION_MISSING'
    assert info.value.action == GateAction.REJECT
    assert world(observer, sc.workspace_id) == before
    assert world(observer, sc.workspace_id)['ledger'] == []


def test_stale_registry_writes_nothing(dsn, manager, observer):
    sc = seed(dsn)
    service = build_completion_service(manager, sc.workspace_id)
    observer.execute(
        'UPDATE controlplane.cp_variant_registry SET current_registry_revision = 13 WHERE workspace_id = %s',
        (sc.workspace_id,),
    )
    before = world(observer, sc.workspace_id)
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(copy.deepcopy(sc.request), sc.context)
    assert info.value.code == 'VARIANT_REGISTRY_STALE'
    assert info.value.action == GateAction.KEEP_WAITING
    assert world(observer, sc.workspace_id) == before


def test_job_not_ready(dsn, manager, observer):
    sc = seed(dsn, job_status='ACTIVE')
    service = build_completion_service(manager, sc.workspace_id)
    before = world(observer, sc.workspace_id)
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(copy.deepcopy(sc.request), sc.context)
    assert info.value.code == 'JOB_NOT_READY'
    assert world(observer, sc.workspace_id) == before


def test_output_hash_must_match_registered_artifact(dsn, manager, observer):
    sc = seed(dsn)
    service = build_completion_service(manager, sc.workspace_id)
    req = copy.deepcopy(sc.request)
    req['output_sha256'] = 'f' * 64
    before = world(observer, sc.workspace_id)
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(req, sc.context)
    assert info.value.code == 'RESERVATION_INVALID'
    assert world(observer, sc.workspace_id) == before


def run_parallel(manager, scenarios: list[Scenario]) -> list[str]:
    barrier = threading.Barrier(len(scenarios))
    outcomes: list[str] = []
    lock = threading.Lock()

    def work(sc: Scenario):
        service = build_completion_service(manager, sc.workspace_id)
        barrier.wait(timeout=30)
        try:
            res = service.complete(copy.deepcopy(sc.request), sc.context)
            with lock:
                outcomes.append(res.code)
        except CompletionRejectedError as exc:
            with lock:
                outcomes.append(exc.code)

    threads = [threading.Thread(target=work, args=(sc,)) for sc in scenarios]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
        assert not t.is_alive()
    return sorted(outcomes)


def test_two_workers_same_job_one_wins(dsn, manager, observer):
    sc = seed(dsn)
    outcomes = run_parallel(manager, [sc, sc])
    assert outcomes == ['ALREADY_COMPLETED', 'COMPLETED']
    w = world(observer, sc.workspace_id)
    assert len(w['ledger']) == 1
    assert len(w['usage']) == 2
    assert len(w['outbox']) == 1
    assert len(w['cleanup']) == 1
    assert w['registry'] == [(13,)]


def test_two_jobs_same_registry_revision_one_wins(dsn, manager, observer):
    a = seed(dsn)
    b = seed(dsn, shared=a)
    outcomes = run_parallel(manager, [a, b])
    assert outcomes == ['COMPLETED', 'VARIANT_REGISTRY_STALE']
    w = world(observer, a.workspace_id)
    assert len(w['ledger']) == 1
    assert len(w['usage']) == 2
    assert len(w['outbox']) == 1
    assert w['registry'] == [(13,)]


def test_job_row_is_locked_for_update(dsn, manager, observer):
    sc = seed(dsn)
    uow = PostgresCompletionUnitOfWork(manager, sc.workspace_id, sc.request)
    uow.begin()
    try:
        job = uow.get_job(sc.job_id)
        assert job is not None and job.revision == 3
        with psycopg.connect(dsn, autocommit=True) as other:
            with pytest.raises(psycopg.errors.LockNotAvailable):
                other.execute(
                    'SELECT 1 FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s FOR UPDATE NOWAIT',
                    (sc.workspace_id, sc.job_id),
                )
    finally:
        uow.rollback()
    with psycopg.connect(dsn, autocommit=True) as other:
        row = other.execute(
            'SELECT 1 FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s FOR UPDATE NOWAIT',
            (sc.workspace_id, sc.job_id),
        ).fetchone()
        assert row == (1,)
    uow.rollback()


def test_recovery_epoch_is_compared_as_text(dsn, manager, observer):
    sc = seed(dsn)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO controlplane.cp_app_sessions (workspace_id, session_ref, status, recovery_epoch, started_at) "
            "VALUES (%s, 's1', 'ACTIVE', '007', CURRENT_TIMESTAMP)",
            (sc.workspace_id,),
        )
        current = PostgresRecoveryEpoch(conn, sc.workspace_id).current()
    assert current == '007'
    claims = GrantClaims(
        grant_id='g',
        stage_run_id='st',
        execution_generation=1,
        recovery_epoch='007',
        worker_lease_id='l',
        issued_at='2026-10-22T08:00:00Z',
        expires_at='2026-10-22T09:00:00Z',
        allowed_operation='render',
        input_fingerprint='fp',
    )
    now = datetime(2026, 10, 22, 8, 30, tzinfo=timezone.utc)
    result = {'recovery_epoch': 7, 'execution_generation': 1, 'grant_id': 'g', 'stage_run_id': 'st'}
    stale = evaluate_result_fencing(claims, 1, current, result, 'fp', now, False)
    assert stale.accepted is False
    assert stale.code == STALE_RECOVERY_EPOCH
    before = world(observer, sc.workspace_id)
    service = build_completion_service(manager, sc.workspace_id)
    with pytest.raises(CompletionRejectedError) as info:
        service.complete(copy.deepcopy(sc.request), replace(sc.context, fencing=stale))
    assert info.value.code == STALE_RECOVERY_EPOCH
    assert world(observer, sc.workspace_id) == before
    ok = evaluate_result_fencing(claims, 1, current, {**result, 'recovery_epoch': '007'}, 'fp', now, False)
    assert ok.accepted is True
    assert service.complete(copy.deepcopy(sc.request), replace(sc.context, fencing=ok)).code == 'COMPLETED'


ORCH = ROOT / 'src/controlplane/infrastructure/db/orchestration'
ADAPTER = ORCH / 'postgres_completion.py'
WIRING = ROOT / 'src/controlplane/api/wiring/completion.py'

WIRING_REQUIRED = ('__init__.py', 'completion.py')


def wiring_problems(wiring_dir: Path) -> list[str]:
    present = {p.name for p in wiring_dir.glob('*.py')}
    return [f'thiếu {name}' for name in WIRING_REQUIRED if name not in present]


def test_adapter_placement_and_packaging():
    d = tomllib.loads((ROOT / 'src/controlplane/pyproject.toml').read_text(encoding='utf-8'))
    s = d['tool']['setuptools']
    k = 'controlplane.infrastructure.db.orchestration'
    assert k in s['packages'] and k in s['package-dir']
    assert ADAPTER.is_file() and WIRING.is_file()
    assert not (ROOT / 'src/controlplane/infrastructure/db/completion').exists()
    assert {
        '__init__.py', 'allocation.py', 'grants.py', 'postgres_completion.py', 'start_batch.py', 'variants.py'
    } <= {p.name for p in ORCH.glob('*.py')}
    assert wiring_problems(WIRING.parent) == []


def make_wiring_dir(directory: Path, names: list[str]) -> Path:
    for name in names:
        (directory / name).write_text('', encoding='utf-8')
    return directory


def test_wiring_problems_only_required_modules(tmp_path):
    make_wiring_dir(tmp_path, ['__init__.py', 'completion.py'])
    assert wiring_problems(tmp_path) == []


def test_wiring_problems_allows_other_modules(tmp_path):
    make_wiring_dir(
        tmp_path,
        ['__init__.py', 'completion.py', 'collection.py', 'workflow.py', 'production.py'],
    )
    assert wiring_problems(tmp_path) == []


def test_wiring_problems_reports_missing_completion(tmp_path):
    make_wiring_dir(tmp_path, ['__init__.py', 'collection.py', 'production.py'])
    problems = wiring_problems(tmp_path)
    assert problems == ['thiếu completion.py']


def test_wiring_problems_reports_missing_init(tmp_path):
    make_wiring_dir(tmp_path, ['completion.py', 'collection.py', 'workflow.py'])
    problems = wiring_problems(tmp_path)
    assert problems == ['thiếu __init__.py']


def test_no_delete_command_and_no_ddl():
    for path in (ADAPTER, WIRING):
        text = path.read_text(encoding='utf-8')
        assert re.search(r'\bDELETE\b|unlink|rmtree|os\.remove|shutil', text) is None
        assert 'CREATE TABLE' not in text
        assert 'ALTER TABLE' not in text
        assert 'connect(' not in text
        assert 'ConnectionPool' not in text
        assert 'from src.' not in text
        assert 'import src' not in text
    text_adapter = ADAPTER.read_text(encoding='utf-8')
    assert 'FOR UPDATE' in text_adapter
    assert [n for n in dir(PostgresCompletionUnitOfWork) if any(w in n.lower() for w in ('delete', 'remove', 'unlink', 'purge'))] == []


def test_usage_goes_through_recorder_on_same_uow():
    text = ADAPTER.read_text(encoding='utf-8')
    assert 'record_production_usage(self._uow' in text
