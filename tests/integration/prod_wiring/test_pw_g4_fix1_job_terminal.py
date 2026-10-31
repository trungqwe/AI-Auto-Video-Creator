"""PW-G4-FIX1: job video tới FAILED_FINAL và trả suất khi VideoProductionWorkflow thất bại.

coveredIds: PW-G4-FIX1-01..10, CT-CMN-010, CT-ORC-002, CT-ORC-012
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone

import pytest
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler, wrap_dispatcher
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.grant_runtime import build_grant_issuer
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.variant_reservation_flow import ReserveVariantRequest, VariantReservationFlow
from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.definitions import VideoProductionWorkflow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.domain.orchestration.job_waiting import Wait, WaitReason
from controlplane.domain.statemachine import JobState, StageRunState
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.job_states import PostgresJobStates
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry

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
PROBLEM = {'code': 'ANALYZE_FAILED', 'activity': 'AnalyzeContent', 'disposition': 'failed'}
SID = 'job-1:analyze:r1'
JOB_SQL = 'SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s'
CAPACITY_SQL = 'SELECT state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id = %s AND job_id = %s'
VARIANT_SQL = 'SELECT state FROM controlplane.cp_variant_reservations WHERE workspace_id = %s AND job_id = %s'
STAGE_SQL = 'SELECT status, problem, finished_at FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND stage_run_id = %s'
ALL_JOBS_SQL = 'SELECT job_id, status, revision FROM controlplane.cp_video_jobs WHERE workspace_id = %s ORDER BY job_id'
ALL_CAPACITY_SQL = 'SELECT job_id, state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id = %s ORDER BY reservation_id'
ALL_VARIANT_SQL = 'SELECT job_id, state FROM controlplane.cp_variant_reservations WHERE workspace_id = %s ORDER BY reservation_id'
ALL_STAGE_SQL = 'SELECT stage_run_id, status, problem, finished_at, updated_at FROM controlplane.cp_stage_runs WHERE workspace_id = %s ORDER BY stage_run_id'


def seed_job(pw_database, status='ACTIVE', *, job_id='job-1', capacity=True, variant=True):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        if conn.execute('SELECT 1 FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s', (ws, 'batch-1')).fetchone() is None:
            conn.execute("INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES ('batch-1', %s, 'RUNNING', 1)", (ws,))
        first = 'ACTIVE' if status == 'WAITING' else status
        conn.execute(
            "INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, 'batch-1', %s, %s, 'snap-1', 1)",
            (job_id, ws, first),
        )
        if status == 'WAITING':
            with conn.transaction():
                PostgresJobStates(conn, ws).apply_decision(job_id, Wait(WaitReason.QUOTA_WAIT))
        if capacity:
            conn.execute(
                "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id, workspace_id, batch_id, job_id, state) VALUES (%s, %s, 'batch-1', %s, 'ACTIVE')",
                ('cap-' + job_id, ws, job_id),
            )
        if variant:
            with conn.transaction():
                VariantReservationFlow(PostgresVariantRegistry(conn)).reserve(ReserveVariantRequest(
                    workspace_id=ws, job_id=job_id, fingerprint='fp-' + job_id, snapshot_scope='scope-1', validation_ref='val-1:r1',
                    variation_policy_revision='pol-1', expected_registry_revision=1, idempotency_key='idem-' + job_id,
                ))


def seed_stage(pw_database, status='RUNNING', stage_run_id=SID):
    with pw_database.connect() as conn:
        runs = PostgresStageRuns(conn, pw_database.workspace_id)
        runs.ensure(stage_run_id, '5')
        if status in ('RUNNING', 'OUTCOME_UNKNOWN'):
            runs.transition(stage_run_id, StageRunState.RUNNING, NOW, execution_generation=1)
        if status == 'OUTCOME_UNKNOWN':
            runs.transition(stage_run_id, StageRunState.OUTCOME_UNKNOWN, NOW, problem={'code': 'X'})


def job_status(pw_database, job_id='job-1'):
    with pw_database.connect() as conn:
        row = conn.execute(JOB_SQL, (pw_database.workspace_id, job_id)).fetchone()
    return row[0] if row else None


def capacity_state(pw_database, job_id='job-1'):
    with pw_database.connect() as conn:
        row = conn.execute(CAPACITY_SQL, (pw_database.workspace_id, job_id)).fetchone()
    return row[0] if row else None


def variant_state(pw_database, job_id='job-1'):
    with pw_database.connect() as conn:
        row = conn.execute(VARIANT_SQL, (pw_database.workspace_id, job_id)).fetchone()
    return row[0] if row else None


def stage_row(pw_database, stage_run_id=SID):
    with pw_database.connect() as conn:
        row = conn.execute(STAGE_SQL, (pw_database.workspace_id, stage_run_id)).fetchone()
    return tuple(row) if row else None


def snapshot_all(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        return tuple(
            tuple(tuple(r) for r in conn.execute(sql, (ws,)).fetchall())
            for sql in (ALL_JOBS_SQL, ALL_CAPACITY_SQL, ALL_VARIANT_SQL, ALL_STAGE_SQL)
        )


def terminate(pw_database, video_job_id='job-1', stage_run_id=SID, problem=None):
    from controlplane.application.orchestration.job_terminal import FailJobRequest, JobTerminator

    return JobTerminator(pw_database.connect, lambda: NOW, workspace_id=pw_database.workspace_id).fail(
        FailJobRequest(video_job_id, stage_run_id, PROBLEM if problem is None else problem)
    )


def assert_terminated(pw_database, job_id='job-1'):
    assert job_status(pw_database, job_id) == 'FAILED_FINAL'
    assert capacity_state(pw_database, job_id) == 'RELEASED'
    assert variant_state(pw_database, job_id) == 'RELEASED'


def test_01_terminator_fails_active_job_closes_the_row_and_releases_capacity_and_variant(pw_database):
    seed_job(pw_database, 'ACTIVE')
    seed_stage(pw_database)
    result = terminate(pw_database)
    assert result.code is None
    assert_terminated(pw_database)
    assert stage_row(pw_database) == ('FAILED_FINAL', {'code': 'ANALYZE_FAILED', 'activity': 'AnalyzeContent', 'disposition': 'failed', 'retryable': False}, NOW)
    before = snapshot_all(pw_database)
    terminate(pw_database)
    assert snapshot_all(pw_database) == before


def test_01b_missing_problem_code_becomes_retry_exhausted(pw_database):
    seed_job(pw_database, 'ACTIVE')
    seed_stage(pw_database)
    result = terminate(pw_database, problem={'activity': 'AnalyzeContent', 'disposition': 'stale'})
    assert result.code is None
    assert_terminated(pw_database)
    assert stage_row(pw_database)[1] == {'code': 'RETRY_EXHAUSTED', 'activity': 'AnalyzeContent', 'disposition': 'stale', 'retryable': False}


@pytest.mark.parametrize('start', ['SNAPSHOTTED', 'WAITING', 'READY_FOR_COMPLETION'])
def test_02_failable_source_states_reach_failed_final(pw_database, start):
    seed_job(pw_database, start)
    seed_stage(pw_database)
    result = terminate(pw_database)
    assert result.code is None
    assert_terminated(pw_database)
    assert stage_row(pw_database)[0] == 'FAILED_FINAL'


def test_02b_completed_job_is_left_alone(pw_database):
    seed_job(pw_database, 'COMPLETED')
    seed_stage(pw_database)
    before = snapshot_all(pw_database)
    result = terminate(pw_database)
    assert result.code is None
    assert snapshot_all(pw_database) == before
    assert capacity_state(pw_database) == 'ACTIVE'


def test_02c_created_job_is_not_failable(pw_database):
    seed_job(pw_database, 'CREATED')
    seed_stage(pw_database)
    before = snapshot_all(pw_database)
    result = terminate(pw_database)
    assert result.code == 'JOB_NOT_FAILABLE'
    assert snapshot_all(pw_database) == before
    assert stage_row(pw_database)[0] == 'RUNNING'


def test_02d_job_without_variant_reservation(pw_database):
    seed_job(pw_database, 'ACTIVE', variant=False)
    seed_stage(pw_database)
    terminate(pw_database)
    assert job_status(pw_database) == 'FAILED_FINAL'
    assert capacity_state(pw_database) == 'RELEASED'
    assert variant_state(pw_database) is None


def test_02e_stage_owner_mismatch_and_missing_job(pw_database):
    seed_job(pw_database, 'ACTIVE')
    seed_stage(pw_database)
    before = snapshot_all(pw_database)
    assert terminate(pw_database, stage_run_id='job-2:analyze:r1').code == 'STAGE_OWNER_MISMATCH'
    assert terminate(pw_database, stage_run_id='not-a-stage-run-id').code == 'STAGE_OWNER_MISMATCH'
    assert terminate(pw_database, video_job_id='missing', stage_run_id='missing:analyze:r1').code == 'JOB_NOT_FOUND'
    assert snapshot_all(pw_database) == before


@pytest.mark.parametrize('status', ['OUTCOME_UNKNOWN', 'PENDING'])
def test_03_rows_other_than_running_are_kept(pw_database, status):
    seed_job(pw_database, 'ACTIVE')
    seed_stage(pw_database, status=status)
    row_before = stage_row(pw_database)
    terminate(pw_database)
    assert job_status(pw_database) == 'FAILED_FINAL'
    assert capacity_state(pw_database) == 'RELEASED'
    assert stage_row(pw_database) == row_before


VIDEO_PAYLOAD = {'settings': SETTINGS.to_payload(), 'input_fingerprint': 'fp-1', 'worker_lease_id': 'lease-1', 'video_job_id': 'job-1'}
AVAILABLE = {'desktop_production': {'status': 'available'}}


def ok_result(request, claims, **extra):
    return {
        'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id, 'execution_generation': claims.execution_generation,
        'recovery_epoch': claims.recovery_epoch, 'disposition': 'succeeded', 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra,
    }


def all_ok_handlers():
    return {name: ok_result for name in BINDINGS_BY_NAME}


def scripted(calls, **extra):
    def handler(request, claims):
        calls.append(request['activity_name'])
        return ok_result(request, claims, **extra)

    return handler


@asynccontextmanager
async def workers(pw_database, pw_temporal, handlers):
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
            extra = {'workflows': list(registration.workflows)} if queue == 'control-workflows' else {}
            await stack.enter_async_context(Worker(
                pw_temporal, task_queue=queue, activities=list(functions),
                workflow_runner=UnsandboxedWorkflowRunner(), **extra,
            ))
        yield


def wf_id():
    return 'pw-g4-fix1-' + uuid.uuid4().hex[:8]


async def run_to_end(pw_database, pw_temporal, handlers, name, payload):
    async with workers(pw_database, pw_temporal, handlers):
        handle = await pw_temporal.start_workflow(name, payload, id=wf_id(), task_queue='control-workflows')
        result = await asyncio.wait_for(handle.result(), timeout=300)
        history = await handle.fetch_history()
    return result, history


def scheduled(history):
    return [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events if e.HasField('activity_task_scheduled_event_attributes')]


RETRYABLE = {'code': 'ANALYZE_RETRY', 'retryable': True, 'message': 'retry'}
UNKNOWN = {'code': 'OUTCOME_UNKNOWN', 'retryable': True, 'message': 'unknown'}


@pytest.mark.asyncio
async def test_04_retryable_failed_exhausts_max_attempts(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    calls = []
    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = scripted(calls, disposition='failed', problem=RETRYABLE)
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    assert result['status'] == 'FAILED'
    assert calls == ['AnalyzeContent'] * PARAMETERS['workflow.retry']['maximum_attempts']
    assert 'FailVideoJob' in scheduled(history)
    assert_terminated(pw_database)
    assert stage_row(pw_database) == ('FAILED_FINAL', {'code': 'ANALYZE_RETRY', 'activity': 'AnalyzeContent', 'disposition': 'failed', 'retryable': False}, NOW)


@pytest.mark.asyncio
async def test_05_stale_exhausts_max_attempts(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    calls = []
    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = scripted(calls, disposition='stale', problem={'code': 'STALE_RECOVERY_EPOCH', 'retryable': True, 'message': 'stale'})
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    assert result['status'] == 'FAILED'
    assert calls == ['AnalyzeContent'] * PARAMETERS['workflow.retry']['maximum_attempts']
    assert_terminated(pw_database)
    assert stage_row(pw_database)[0] == 'FAILED_FINAL'
    assert stage_row(pw_database)[1]['code'] == 'STALE_RECOVERY_EPOCH'


@pytest.mark.asyncio
async def test_06_handler_exception_exhausts_temporal_retry_policy(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    calls = []

    def boom(request, claims):
        calls.append(request['activity_name'])
        raise RuntimeError('boom')

    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = boom
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    assert result['status'] == 'FAILED'
    assert len(calls) == PARAMETERS['workflow.retry']['maximum_attempts']
    assert_terminated(pw_database)
    assert stage_row(pw_database)[0] == 'FAILED_FINAL'
    assert stage_row(pw_database)[1]['code'] == 'ActivityError'


@pytest.mark.asyncio
async def test_07a_activity_rejected(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    calls = []

    def incomplete(request, claims):
        calls.append(request['activity_name'])
        result = ok_result(request, claims)
        del result['completed_at']
        return result

    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = incomplete
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    assert result['status'] == 'FAILED'
    assert calls == ['AnalyzeContent']
    assert_terminated(pw_database)
    assert stage_row(pw_database)[0] == 'FAILED_FINAL'
    assert stage_row(pw_database)[1]['code'] == 'INVALID_ACTIVITY_RESULT'


@pytest.mark.asyncio
async def test_07b_outcome_unknown_keeps_the_row(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = lambda request, claims: ok_result(request, claims, disposition='outcome_unknown', problem=UNKNOWN)
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    assert result['status'] == 'FAILED'
    assert stage_row(pw_database)[0] == 'OUTCOME_UNKNOWN'
    assert_terminated(pw_database)


@pytest.mark.asyncio
async def test_08a_hold_on_failure_true_keeps_the_job_active(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = scripted([], disposition='outcome_unknown', problem=UNKNOWN)
    payload = {**VIDEO_PAYLOAD, 'hold_on_failure': True}
    async with workers(pw_database, pw_temporal, handlers):
        handle = await pw_temporal.start_workflow('VideoProductionWorkflow', payload, id=wf_id(), task_queue='control-workflows')
        for _ in range(300):
            await asyncio.sleep(0.1)
            row = stage_row(pw_database)
            if row is not None and row[0] == 'OUTCOME_UNKNOWN':
                break
        else:
            pytest.fail('the stage row never reached OUTCOME_UNKNOWN')
        await asyncio.sleep(1)
        await handle.terminate()
        history = await handle.fetch_history()
    assert 'FailVideoJob' not in scheduled(history)
    assert job_status(pw_database) == 'ACTIVE'
    assert capacity_state(pw_database) == 'ACTIVE'
    assert variant_state(pw_database) == 'ACTIVE'


@pytest.mark.asyncio
async def test_08b_debug_stage_workflow_failure_does_not_fail_the_job(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    handlers = all_ok_handlers()
    handlers['GenerateStoryAngles'] = scripted([], disposition='outcome_unknown', problem=UNKNOWN)
    payload = {**VIDEO_PAYLOAD, 'target_stage': 'script'}
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'DebugStageWorkflow', payload)
    assert result['status'] == 'FAILED'
    assert 'FailVideoJob' not in scheduled(history)
    assert job_status(pw_database) == 'ACTIVE'
    assert capacity_state(pw_database) == 'ACTIVE'


class ScriptedSelector:
    def __init__(self, *candidates):
        self.pending = list(candidates)
        self.calls = []

    def next_candidate(self, batch_id, production_mode):
        self.calls.append((batch_id, production_mode))
        return self.pending.pop(0) if self.pending else None


def cands(count):
    return [AllocationCandidate(f'c{i}', f'angle-{i}', f's{i}') for i in range(1, count + 1)]


def seed_target_batch(pw_database, batch_id, target):
    with pw_database.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
            (batch_id, pw_database.workspace_id, 'RUNNING', target),
        )


@pytest.mark.asyncio
async def test_09_batch_target_one_continues_after_a_failed_candidate(pw_database, pw_temporal):
    batch_id = wf_id()
    ws = pw_database.workspace_id
    seed_target_batch(pw_database, batch_id, 1)
    selector = ScriptedSelector(*cands(3))
    handlers = all_ok_handlers()
    handlers['AllocateJob'] = service_handler(AllocateJobService(pw_database.connect, selector, workspace_id=ws), lambda: NOW)
    handlers['FinalizeBatch'] = service_handler(FinalizeBatchService(BatchLifecycle(pw_database.connect, lambda: NOW, workspace_id=ws)), lambda: NOW)

    def analyze(request, claims):
        if request['video_job_id'].endswith(':job:1'):
            return ok_result(request, claims, disposition='failed', problem=RETRYABLE)
        return ok_result(request, claims)

    handlers['AnalyzeContent'] = analyze
    async with workers(pw_database, pw_temporal, handlers):
        handle = await pw_temporal.start_workflow(
            'ProductionBatchWorkflow', {'settings': SETTINGS.to_payload(), 'target_videos': 1, 'worker_lease_id': 'lease-1'},
            id=batch_id, task_queue='control-workflows',
        )
        result = await asyncio.wait_for(handle.result(), timeout=300)
    assert (result['status'], result['completed'], result['failed'], result['allocated']) == ('TARGET_REACHED', 1, 1, 2)
    assert job_status(pw_database, batch_id + ':job:1') == 'FAILED_FINAL'
    assert capacity_state(pw_database, batch_id + ':job:1') == 'RELEASED'


@pytest.mark.asyncio
async def test_10_history_with_the_patch_marker_replays(pw_database, pw_temporal):
    seed_job(pw_database, 'ACTIVE')
    handlers = all_ok_handlers()
    handlers['AnalyzeContent'] = scripted([], disposition='failed', problem=RETRYABLE)
    result, history = await run_to_end(pw_database, pw_temporal, handlers, 'VideoProductionWorkflow', VIDEO_PAYLOAD)
    events = list(history.events)
    marker_index = next(
        (i for i, e in enumerate(events) if e.HasField('marker_recorded_event_attributes') and 'job-terminal-on-failure' in str(e.marker_recorded_event_attributes)),
        None,
    )
    fail_index = next(
        (i for i, e in enumerate(events) if e.HasField('activity_task_scheduled_event_attributes') and e.activity_task_scheduled_event_attributes.activity_type.name == 'FailVideoJob'),
        None,
    )
    assert marker_index is not None and fail_index is not None and marker_index < fail_index
    await Replayer(workflows=[VideoProductionWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)
