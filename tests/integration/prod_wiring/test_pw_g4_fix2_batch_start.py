"""PW-G4-FIX2: lô chuyển CREATED -> RUNNING khi ProductionBatchWorkflow bắt đầu (StartBatch sau workflow.patched) trên Temporal time-skipping và PostgreSQL thử.

coveredIds: CT-STATE-010, CT-ORC-001, CT-ORC-010
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone

import psycopg
import pytest
from temporalio.client import WorkflowFailureError
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler, wrap_dispatcher
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.grant_runtime import build_grant_issuer
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.definitions import ProductionBatchWorkflow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.domain.statemachine import ForbiddenTransitionError
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.outbox_relay import OutboxRelay
from controlplane.infrastructure.db.uow import TransactionManager

NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 36000, 'cloud-io': 36000, 'cloud-ai': 36000, 'desktop-cpu': 36000, 'desktop-gpu': 36000, 'desktop-render': 36000},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
AVAILABLE = {'desktop_production': {'status': 'available'}}
PATCH = 'batch-running-on-start'


def seed_batch(pw_database, status, target=2):
    batch_id = 'pw-g4-fix2-' + uuid.uuid4().hex[:8]
    with pw_database.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
            (batch_id, pw_database.workspace_id, status, target),
        )
    return batch_id


def batch_row(pw_database, batch_id):
    with pw_database.connect() as conn:
        return conn.execute(
            'SELECT status, stop_reason, stopped_at FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s',
            (pw_database.workspace_id, batch_id),
        ).fetchone()


def lifecycle_for(pw_database):
    return BatchLifecycle(pw_database.connect, lambda: NOW, workspace_id=pw_database.workspace_id)


def create_batch(pw_database, target=2):
    manager = TransactionManager(pw_database.dsn)
    try:
        receipt = compose_command_service(manager.unit_of_work).start_batch(
            workspace_id=pw_database.workspace_id,
            actor_id=pw_database.actor_id,
            correlation_id='pw-g4-fix2',
            idempotency_key=str(uuid.uuid4()),
            payload={'target_completed_videos': target},
        )
        return receipt['resource_ref']['batch_id']
    finally:
        manager.close()


def ok_result(request, claims):
    return {
        'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id, 'execution_generation': claims.execution_generation,
        'recovery_epoch': claims.recovery_epoch, 'disposition': 'succeeded', 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z',
    }


class ScriptedSelector:
    def __init__(self, count):
        self.pending = [AllocationCandidate(f'c{i}', f'angle-{i}', f's{i}') for i in range(1, count + 1)]

    def next_candidate(self, batch_id, production_mode):
        return self.pending.pop(0) if self.pending else None


def batch_handlers(pw_database, selector, seen):
    handlers = {name: ok_result for name in BINDINGS_BY_NAME}
    allocate = service_handler(AllocateJobService(pw_database.connect, selector, workspace_id=pw_database.workspace_id), lambda: NOW)

    def allocate_job(request, claims):
        batch_id = next(ref['ref_id'] for ref in request['input_refs'] if ref['ref_type'] == 'production_batch')
        seen.append(batch_row(pw_database, batch_id)[0])
        return allocate(request, claims)

    handlers['AllocateJob'] = allocate_job
    handlers['FinalizeBatch'] = service_handler(FinalizeBatchService(lifecycle_for(pw_database)), lambda: NOW)
    return handlers


@asynccontextmanager
async def workers(pw_database, pw_temporal, handlers, *, wrap=True, decorate=None, patch_callback=None):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        PostgresAppSessions(conn, ws).begin('ses-1', '5')
    services = build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=lambda: NOW, timezone_approved=False)
    if wrap:
        services = wrap_dispatcher(services, connection_factory=pw_database.connect, workspace_id=ws, clock=lambda: NOW)
    if decorate is not None:
        services = decorate(services)
    registration = build_temporal_registration(
        services, grant_issuer=build_grant_issuer(pw_database.connect, ws, None, lambda: NOW), capability_reader=lambda: AVAILABLE,
    )
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows)} if queue == 'control-workflows' else {}
            await stack.enter_async_context(Worker(
                pw_temporal, task_queue=queue, activities=list(functions), workflow_runner=UnsandboxedWorkflowRunner(),
                max_cached_workflows=0, patch_activation_callback=patch_callback, **extra,
            ))
        yield


async def run_batch(pw_database, pw_temporal, batch_id, handlers, *, relay=False, **options):
    async with workers(pw_database, pw_temporal, handlers, **options):
        if relay:
            relay_run = OutboxRelay(lambda: psycopg.connect(pw_database.dsn), pw_temporal, pw_database.workspace_id, SETTINGS, lambda: NOW)
            assert await relay_run.run_once() == 1
        else:
            await pw_temporal.start_workflow(
                'ProductionBatchWorkflow', {'settings': SETTINGS.to_payload(), 'target_videos': 2, 'worker_lease_id': 'lease-1'},
                id=batch_id, task_queue='control-workflows',
            )
        handle = pw_temporal.get_workflow_handle(batch_id)
        try:
            outcome = await asyncio.wait_for(handle.result(), timeout=300)
        except WorkflowFailureError as exc:
            outcome = exc
        return outcome, await handle.fetch_history()


async def replay(history):
    await Replayer(workflows=[ProductionBatchWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)


def timeline(history):
    items = []
    for event in history.events:
        if event.HasField('marker_recorded_event_attributes') and PATCH in str(event.marker_recorded_event_attributes):
            items.append(PATCH)
        elif event.HasField('activity_task_scheduled_event_attributes'):
            items.append(event.activity_task_scheduled_event_attributes.activity_type.name)
    return items


def mentions(history, text):
    return any(text in str(event) for event in history.events)


def causes(exc):
    texts = []
    while exc is not None:
        texts.append(str(exc))
        exc = exc.__cause__
    return ' | '.join(texts)


def test_start_moves_created_to_running_once_and_leaves_other_batches(pw_database):
    batch_id = seed_batch(pw_database, 'CREATED')
    other = seed_batch(pw_database, 'CREATED')
    lifecycle = lifecycle_for(pw_database)
    assert lifecycle.start(batch_id) is True
    assert batch_row(pw_database, batch_id) == ('RUNNING', None, None)
    assert lifecycle.start(batch_id) is False
    assert batch_row(pw_database, batch_id) == ('RUNNING', None, None)
    assert batch_row(pw_database, other) == ('CREATED', None, None)


def test_start_leaves_waiting_capability_unchanged(pw_database):
    batch_id = seed_batch(pw_database, 'WAITING_CAPABILITY')
    assert lifecycle_for(pw_database).start(batch_id) is False
    assert batch_row(pw_database, batch_id) == ('WAITING_CAPABILITY', None, None)


@pytest.mark.parametrize('status', ['COMPLETED_TARGET', 'COMPLETED_EXHAUSTED', 'FAILED_SYSTEM'])
def test_start_rejects_finished_batches_and_writes_nothing(pw_database, status):
    batch_id = seed_batch(pw_database, status)
    other = seed_batch(pw_database, 'CREATED')
    with pytest.raises(ForbiddenTransitionError):
        lifecycle_for(pw_database).start(batch_id)
    assert batch_row(pw_database, batch_id) == (status, None, None)
    assert batch_row(pw_database, other) == ('CREATED', None, None)


def test_start_of_a_missing_batch_is_batch_not_found(pw_database):
    with pytest.raises(OrchestrationContractError) as caught:
        lifecycle_for(pw_database).start('batch-missing')
    assert caught.value.code == 'BATCH_NOT_FOUND'


@pytest.mark.asyncio
async def test_batch_is_running_before_the_first_job_and_finishes_with_stop_fields(pw_database, pw_temporal):
    batch_id = create_batch(pw_database, target=2)
    assert batch_row(pw_database, batch_id)[0] == 'CREATED'
    seen = []
    handlers = batch_handlers(pw_database, ScriptedSelector(3), seen)
    result, history = await run_batch(pw_database, pw_temporal, batch_id, handlers, relay=True)
    assert (result['status'], result['completed'], result['failed'], result['allocated'], result['finalized']) == ('TARGET_REACHED', 2, 0, 2, True)
    status, reason, stopped_at = batch_row(pw_database, batch_id)
    assert status == 'COMPLETED_TARGET' and reason and stopped_at is not None
    assert seen == ['RUNNING', 'RUNNING']
    line = timeline(history)
    assert line.count('StartBatch') == 1
    assert line.index(PATCH) < line.index('StartBatch') < line.index('IssueExecutionGrant')
    await replay(history)


@pytest.mark.asyncio
async def test_batch_without_candidates_finalizes_exhausted(pw_database, pw_temporal):
    batch_id = create_batch(pw_database, target=2)
    handlers = batch_handlers(pw_database, ScriptedSelector(0), [])
    result, history = await run_batch(pw_database, pw_temporal, batch_id, handlers, relay=True)
    assert result['status'] == 'EXHAUSTED' and result['finalized'] is True
    status, reason, stopped_at = batch_row(pw_database, batch_id)
    assert status == 'COMPLETED_EXHAUSTED' and reason and stopped_at is not None
    assert timeline(history).count('StartBatch') == 1


@pytest.mark.asyncio
async def test_history_without_the_patch_marker_keeps_the_old_path_and_replays(pw_database, pw_temporal):
    batch_id = create_batch(pw_database, target=2)
    handlers = batch_handlers(pw_database, ScriptedSelector(3), [])
    result, history = await run_batch(
        pw_database, pw_temporal, batch_id, handlers, relay=True, patch_callback=lambda info: info.patch_id != PATCH,
    )
    line = timeline(history)
    assert PATCH not in line and 'StartBatch' not in line
    assert result['finalized'] is False
    assert mentions(history, 'FORBIDDEN_TRANSITION')
    assert batch_row(pw_database, batch_id)[0] == 'CREATED'
    await replay(history)


class CommitThenFailOnce:
    def __init__(self, inner):
        self.inner = inner
        self.results = []
        self.failed = False

    def start(self, batch_id):
        changed = self.inner.start(batch_id)
        self.results.append(changed)
        if not self.failed:
            self.failed = True
            raise RuntimeError('injected failure after commit')
        return changed


@pytest.mark.asyncio
async def test_retry_after_a_committed_start_is_idempotent(pw_database, pw_temporal):
    batch_id = create_batch(pw_database, target=2)
    flaky = CommitThenFailOnce(lifecycle_for(pw_database))
    handlers = batch_handlers(pw_database, ScriptedSelector(3), [])
    result, history = await run_batch(
        pw_database, pw_temporal, batch_id, handlers, relay=True, decorate=lambda services: replace(services, batch_lifecycle=flaky),
    )
    assert flaky.results == [True, False]
    assert timeline(history).count('StartBatch') == 1
    assert result['status'] == 'TARGET_REACHED'
    assert batch_row(pw_database, batch_id)[0] == 'COMPLETED_TARGET'


@pytest.mark.asyncio
@pytest.mark.parametrize('case, code', [
    ('unbound', 'BATCH_LIFECYCLE_UNBOUND'), ('finished', 'FORBIDDEN_TRANSITION'), ('missing', 'BATCH_NOT_FOUND'),
])
async def test_start_batch_failure_fails_the_workflow_before_any_job(pw_database, pw_temporal, case, code):
    batch_id = 'pw-g4-fix2-missing'
    before = None
    if case != 'missing':
        batch_id = seed_batch(pw_database, 'COMPLETED_TARGET' if case == 'finished' else 'CREATED')
        before = batch_row(pw_database, batch_id)
    seen = []
    handlers = batch_handlers(pw_database, ScriptedSelector(3), seen)
    outcome, history = await run_batch(pw_database, pw_temporal, batch_id, handlers, wrap=(case != 'unbound'))
    assert isinstance(outcome, WorkflowFailureError)
    assert code in causes(outcome)
    assert seen == []
    assert 'AllocateJob' not in timeline(history)
    if before is not None:
        assert batch_row(pw_database, batch_id) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['RUNNING', 'WAITING_CAPABILITY'])
async def test_running_or_waiting_batch_is_not_changed_by_start_and_completes(pw_database, pw_temporal, status):
    batch_id = seed_batch(pw_database, status)
    seen = []
    handlers = batch_handlers(pw_database, ScriptedSelector(3), seen)
    result, history = await run_batch(pw_database, pw_temporal, batch_id, handlers)
    assert result['status'] == 'TARGET_REACHED' and result['finalized'] is True
    assert seen[0] == status
    assert batch_row(pw_database, batch_id)[0] == 'COMPLETED_TARGET'
