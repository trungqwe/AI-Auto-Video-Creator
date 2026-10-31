"""PW-G5-FIX1: lô chạy K video con cùng lúc trên Temporal time-skipping và PostgreSQL thử.

coveredIds: PW-G5-FIX1-02
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone

import pytest
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler, wrap_dispatcher
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.grant_runtime import build_grant_issuer
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.definitions import ProductionBatchWorkflow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions

NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
# start_to_close lớn vì môi trường time-skipping có thể làm timeout chạy sớm khi handler chờ Barrier.
PARAMETERS = {
    'workflow.start_to_close_seconds': {
        'control-workflows': 36000, 'cloud-io': 36000, 'cloud-ai': 36000,
        'desktop-cpu': 36000, 'desktop-gpu': 36000, 'desktop-render': 36000,
    },
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
AVAILABLE = {'desktop_production': {'status': 'available'}}
CHILD_CLOSED_FIELDS = (
    'child_workflow_execution_completed_event_attributes',
    'child_workflow_execution_failed_event_attributes',
    'child_workflow_execution_timed_out_event_attributes',
    'child_workflow_execution_canceled_event_attributes',
    'child_workflow_execution_terminated_event_attributes',
)


def ok_result(request, claims, **extra):
    return {
        'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id, 'execution_generation': claims.execution_generation,
        'recovery_epoch': claims.recovery_epoch, 'disposition': 'succeeded', 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra,
    }


def all_ok_handlers():
    return {name: ok_result for name in BINDINGS_BY_NAME}


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


class ConcurrencyProbe:
    def __init__(self):
        self.lock = threading.Lock()
        self.barrier = threading.Barrier(4, timeout=30)
        self.calls = 0
        self.inside = 0
        self.peak = 0

    def handler(self, request, claims):
        with self.lock:
            self.calls += 1
            call_no = self.calls
            self.inside += 1
            self.peak = max(self.peak, self.inside)
        try:
            if call_no <= 4:
                self.barrier.wait()
            return ok_result(request, claims)
        finally:
            with self.lock:
                self.inside -= 1


def open_children_peak(history):
    opened = 0
    peak = 0
    for event in history.events:
        if event.HasField('start_child_workflow_execution_initiated_event_attributes'):
            opened += 1
            peak = max(peak, opened)
        elif any(event.HasField(field) for field in CHILD_CLOSED_FIELDS):
            opened -= 1
    return peak


def has_marker(history, name):
    return any(
        e.HasField('marker_recorded_event_attributes') and name in str(e.marker_recorded_event_attributes)
        for e in history.events
    )


def batch_handlers(pw_database, selector, analyze):
    handlers = all_ok_handlers()
    ws = pw_database.workspace_id
    handlers['AllocateJob'] = service_handler(AllocateJobService(pw_database.connect, selector, workspace_id=ws), lambda: NOW)
    handlers['FinalizeBatch'] = service_handler(
        FinalizeBatchService(BatchLifecycle(pw_database.connect, lambda: NOW, workspace_id=ws)), lambda: NOW
    )
    if analyze is not None:
        handlers['AnalyzeContent'] = analyze
    return handlers


async def run_batch(pw_database, pw_temporal, target, extra, analyze=None):
    batch_id = 'pw-g5-fix1-' + uuid.uuid4().hex[:8]
    seed_target_batch(pw_database, batch_id, target)
    selector = ScriptedSelector(*cands(10))
    async with workers(pw_database, pw_temporal, batch_handlers(pw_database, selector, analyze)):
        handle = await pw_temporal.start_workflow(
            'ProductionBatchWorkflow',
            {'settings': SETTINGS.to_payload(), 'target_videos': target, 'worker_lease_id': 'lease-1', **extra},
            id=batch_id, task_queue='control-workflows',
        )
        result = await asyncio.wait_for(handle.result(), timeout=300)
        history = await handle.fetch_history()
    return result, history


@pytest.mark.asyncio
async def test_k4_runs_four_children_at_once_and_replays(pw_database, pw_temporal):
    probe = ConcurrencyProbe()
    result, history = await run_batch(pw_database, pw_temporal, 6, {'max_concurrent_videos': 4}, probe.handler)
    assert result['status'] == 'TARGET_REACHED'
    assert result['completed'] == 6
    assert result['failed'] == 0
    assert result['allocated'] == 6
    assert result['finalized'] is True
    assert probe.calls == 6
    assert probe.peak == 4
    assert open_children_peak(history) == 4
    assert has_marker(history, 'batch-concurrent-videos') is True
    await Replayer(workflows=[ProductionBatchWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)


@pytest.mark.asyncio
async def test_k1_without_key_has_no_marker_and_replays(pw_database, pw_temporal):
    result, history = await run_batch(pw_database, pw_temporal, 2, {})
    assert result['status'] == 'TARGET_REACHED'
    assert result['completed'] == 2
    assert result['allocated'] == 2
    assert open_children_peak(history) == 1
    assert has_marker(history, 'batch-concurrent-videos') is False
    await Replayer(workflows=[ProductionBatchWorkflow], workflow_runner=UnsandboxedWorkflowRunner()).replay_workflow(history)
