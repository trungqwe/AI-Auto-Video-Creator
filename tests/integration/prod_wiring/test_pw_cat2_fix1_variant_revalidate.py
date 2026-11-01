"""PW-CAT2-FIX1: VideoProductionWorkflow đối chiếu lại ValidateVariant khi registry biến thể đổi, trên Temporal time-skipping và PostgreSQL thử.

coveredIds: PW-CAT2-FIX1-02
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone

import pytest
from psycopg.types.json import Jsonb
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler, wrap_dispatcher
from controlplane.application.orchestration.grant_runtime import build_grant_issuer
from controlplane.application.orchestration.variant_handlers import reserve_variant_handler
from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.definitions import VideoProductionWorkflow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry
from controlplane.infrastructure.db.uow import TransactionManager

NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
AVAILABLE = {'desktop_production': {'status': 'available'}}
VIDEO_PAYLOAD = {'settings': SETTINGS.to_payload(), 'input_fingerprint': 'fp-1', 'worker_lease_id': 'lease-1', 'video_job_id': 'job-1'}
VALIDATION_KEY = 'variant:job-1'
PATCH_ID = 'variant-stale-revalidate'


def ok_result(request, claims, **extra):
    return {
        'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id, 'execution_generation': claims.execution_generation,
        'recovery_epoch': claims.recovery_epoch, 'disposition': 'succeeded', 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra,
    }


def all_ok_handlers():
    return {name: ok_result for name in BINDINGS_BY_NAME}


@pytest.fixture
def manager(pw_database):
    tm = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield tm
    finally:
        tm.close()


def seed_job(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        if conn.execute('SELECT 1 FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s', (ws, 'batch-1')).fetchone() is None:
            conn.execute("INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES ('batch-1', %s, 'RUNNING', 1)", (ws,))
        conn.execute(
            "INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES ('job-1', 'batch-1', %s, 'ACTIVE', 'snap-1', 1)",
            (ws,),
        )
        conn.execute(
            "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id, workspace_id, batch_id, job_id, state) VALUES ('cap-job-1', %s, 'batch-1', 'job-1', 'ACTIVE')",
            (ws,),
        )


class ValidationWriter:
    def __init__(self, pw_database, bump_first):
        self.db = pw_database
        self.bump_first = bump_first
        self.calls = []

    def handler(self, request, claims):
        stage = request['stage_run_id'].split(':')[1]
        self.calls.append((stage, request['operation_key']))
        if stage != 'plan':
            return ok_result(request, claims)
        ws = self.db.workspace_id
        with self.db.connect() as conn:
            with conn.transaction():
                registry = PostgresVariantRegistry(conn)
                current = registry.current_revision(ws)
                n = conn.execute(
                    'SELECT coalesce(max(revision), 0) + 1 FROM controlplane.cp_variant_validations WHERE workspace_id = %s AND record_key = %s',
                    (ws, VALIDATION_KEY),
                ).fetchone()[0]
                payload = {'valid': True, 'phase': 'plan', 'registry_revision': current, 'variation_policy_revision': 'policy-r1', 'input_hashes': {'candidate': 'fp-job-1'}, 'output_hash': None, 'own_reservation_id': None, 'exact_duplicate': False, 'reason_codes': ['valid']}
                conn.execute(
                    'INSERT INTO controlplane.cp_variant_validations (workspace_id, record_key, revision, payload) VALUES (%s, %s, %s, %s)',
                    (ws, VALIDATION_KEY, n, Jsonb(payload)),
                )
                if self.bump_first and n == 1:
                    registry.bump_revision(ws)
        return ok_result(request, claims, output_refs=[{'ref_type': 'variant_validation', 'ref_id': VALIDATION_KEY, 'revision_id': str(n)}])


class CountingHandler:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def __call__(self, request, claims):
        self.calls += 1
        return self.inner(request, claims)


def make_handlers(pw_database, manager, writer):
    handlers = all_ok_handlers()
    handlers['BuildProductionSnapshot'] = lambda request, claims: ok_result(request, claims, output_refs=[{'ref_type': 'production_snapshot', 'ref_id': 'snapshot-job-1'}])
    handlers['ValidateVariant'] = writer.handler
    reserve = CountingHandler(service_handler(reserve_variant_handler(manager, workspace_id=pw_database.workspace_id), lambda: NOW))
    handlers['ReserveVariant'] = reserve
    return handlers, reserve


@asynccontextmanager
async def workers(pw_database, pw_temporal, handlers, patch_callback=None):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        PostgresAppSessions(conn, ws).begin('ses-1', '5')
    services = wrap_dispatcher(
        build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=lambda: NOW, timezone_approved=False),
        connection_factory=pw_database.connect, workspace_id=ws, clock=lambda: NOW,
    )
    registration = build_temporal_registration(
        services, grant_issuer=build_grant_issuer(pw_database.connect, ws, None, lambda: NOW), capability_reader=lambda: AVAILABLE,
    )
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows), 'patch_activation_callback': patch_callback} if queue == 'control-workflows' else {}
            await stack.enter_async_context(Worker(
                pw_temporal, task_queue=queue, activities=list(functions),
                workflow_runner=UnsandboxedWorkflowRunner(), **extra,
            ))
        yield


def wf_id():
    return 'pw-cat2-fix1-' + uuid.uuid4().hex[:8]


def scheduled(history):
    return [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events if e.HasField('activity_task_scheduled_event_attributes')]


def has_marker(history, name):
    return any(
        e.HasField('marker_recorded_event_attributes') and name in str(e.marker_recorded_event_attributes)
        for e in history.events
    )


def reservation_rows(pw_database):
    with pw_database.connect() as conn:
        rows = conn.execute(
            'SELECT job_id, state, validation_ref FROM controlplane.cp_variant_reservations WHERE workspace_id = %s ORDER BY reservation_id',
            (pw_database.workspace_id,),
        ).fetchall()
    return [tuple(row) for row in rows]


def registry_revision(pw_database):
    with pw_database.connect() as conn:
        row = conn.execute(
            'SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id = %s',
            (pw_database.workspace_id,),
        ).fetchone()
    return row[0]


@pytest.mark.asyncio
async def test_stale_registry_revalidates_then_reserves_and_replays(pw_database, pw_temporal, manager):
    seed_job(pw_database)
    writer = ValidationWriter(pw_database, bump_first=True)
    handlers, reserve = make_handlers(pw_database, manager, writer)
    async with workers(pw_database, pw_temporal, handlers):
        handle = await pw_temporal.start_workflow('VideoProductionWorkflow', VIDEO_PAYLOAD, id=wf_id(), task_queue='control-workflows')
        result = await asyncio.wait_for(handle.result(), timeout=120)
        history = await handle.fetch_history()
    assert result['status'] == 'COMPLETED'
    assert reservation_rows(pw_database) == [('job-1', 'ACTIVE', 'variant:job-1:r2')]
    keys = [key.split(':', 1)[1] for stage, key in writer.calls if stage == 'plan']
    assert keys == ['plan:ValidateVariant:0:r1', 'plan:ValidateVariant:0:r1:v1']
    assert reserve.calls == 2
    assert scheduled(history).count('ReserveVariant') == 2
    assert scheduled(history).count('BuildProductionPlan') == 1
    assert registry_revision(pw_database) == 3
    assert has_marker(history, PATCH_ID) is True
    await Replayer(workflows=[VideoProductionWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)


@pytest.mark.asyncio
async def test_patch_inactive_worker_keeps_waiting_and_replays(pw_database, pw_temporal, manager):
    seed_job(pw_database)
    writer = ValidationWriter(pw_database, bump_first=True)
    handlers, reserve = make_handlers(pw_database, manager, writer)
    callback = lambda patch: patch.patch_id != PATCH_ID
    async with workers(pw_database, pw_temporal, handlers, patch_callback=callback):
        handle = await pw_temporal.start_workflow('VideoProductionWorkflow', VIDEO_PAYLOAD, id=wf_id(), task_queue='control-workflows')
        for _ in range(300):
            await asyncio.sleep(0.1)
            if reserve.calls >= 1:
                break
        else:
            pytest.fail('ReserveVariant was never called')
        await asyncio.sleep(1)
        assert reserve.calls == 1
        assert len([1 for stage, _ in writer.calls if stage == 'plan']) == 1
        history = await handle.fetch_history()
        assert has_marker(history, PATCH_ID) is False
        await handle.terminate()
    assert reservation_rows(pw_database) == []
    await Replayer(workflows=[VideoProductionWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)
