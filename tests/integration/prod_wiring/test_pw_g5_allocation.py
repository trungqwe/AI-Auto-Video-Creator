"""PW-G5: AllocateJob, FinalizeBatch và vòng lô ProductionBatchFlow trên PostgreSQL thử.

coveredIds: PW-G5-01, CT-ORC-002, CT-ORC-010, INV-018
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import uuid
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.grant_runtime import GrantRevokingDispatcher, build_grant_issuer
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.workflows.activities import (
    BATCH_STAGE_ACTIVITIES, BINDINGS_BY_NAME, ActivityDispatcher, ActivityRejected,
)
from controlplane.application.orchestration.workflows.batch import BatchParams, ProductionBatchFlow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate, plan_round
from controlplane.domain.orchestration.workflow_catalog import TaskQueue, get_workflow, route_stage
from controlplane.infrastructure.db.orchestration.allocation import PostgresAllocationStore
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions

ROOT = Path(__file__).resolve().parents[3]
BATCH_ALLOCATION = ROOT / 'src/controlplane/application/orchestration/batch_allocation.py'
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
CANDIDATE_SQL = 'SELECT job_id, batch_id, candidate_ref, source_set_ref FROM controlplane.cp_job_candidates WHERE workspace_id = %s ORDER BY job_id'
BATCH_SQL = 'SELECT status, stop_reason, stopped_at FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s'
JOBS_SQL = 'SELECT job_id FROM controlplane.cp_video_jobs WHERE workspace_id = %s ORDER BY job_id'
RESERVATION_SQL = 'SELECT job_id FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id = %s AND state = %s ORDER BY job_id'


def fingerprint(candidate_ref, source_set_ref):
    text = json.dumps([candidate_ref, source_set_ref], separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ScriptedSelector:
    def __init__(self, *candidates):
        self.pending = list(candidates)
        self.calls = []

    def next_candidate(self, batch_id, production_mode):
        self.calls.append((batch_id, production_mode))
        return self.pending.pop(0) if self.pending else None


def cands(count):
    return [AllocationCandidate(f'c{i}', f'angle-{i}', f's{i}') for i in range(1, count + 1)]


def seed_batch(pw_database, batch_id='batch-1', target=2):
    with pw_database.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
            (batch_id, pw_database.workspace_id, 'RUNNING', target),
        )


def rows(pw_database, sql, *params):
    with pw_database.connect() as conn:
        return conn.execute(sql, (pw_database.workspace_id, *params)).fetchall()


def refs_of(result):
    return {ref['ref_type']: ref['ref_id'] for ref in result['output_refs']}


def allocate_service(pw_database, selector):
    return AllocateJobService(pw_database.connect, selector, workspace_id=pw_database.workspace_id)


def allocate_request(batch_id, job_id, mode='single_article'):
    return {'input_refs': [
        {'ref_type': 'production_batch', 'ref_id': batch_id},
        {'ref_type': 'allocation_job', 'ref_id': job_id},
        {'ref_type': 'production_mode', 'ref_id': mode},
    ]}


def test_bindings_are_internal_g_bindings_on_the_control_queue():
    for name, stage in (('AllocateJob', 'allocate'), ('FinalizeBatch', 'run_videos')):
        binding = BINDINGS_BY_NAME[name]
        assert (binding.owner, binding.stage_type, binding.side_effect) == ('G', stage, True)
        assert binding.queue == route_stage(stage) == TaskQueue.CONTROL_WORKFLOWS
    assert dict(BATCH_STAGE_ACTIVITIES) == {'allocate': ('AllocateJob',), 'run_videos': ('FinalizeBatch',)}
    assert [s.stage_type for s in get_workflow('ProductionBatchWorkflow').stages] == ['allocate', 'run_videos']


def test_allocation_candidate_adds_only_a_trailing_optional_source_set_ref():
    assert [f.name for f in dataclasses.fields(AllocationCandidate)] == ['candidate_ref', 'angle_slot', 'source_set_ref']
    assert AllocationCandidate('c', 'a').source_set_ref is None
    assert AllocationCandidate('c', 'a', 's').source_set_ref == 's'
    with pytest.raises(dataclasses.FrozenInstanceError):
        AllocationCandidate('c', 'a').source_set_ref = 'x'
    pair = [AllocationCandidate('c1', 'a1'), AllocationCandidate('c2', 'a2', 's2')]
    assert plan_round(pair, 1) == (pair[0],)


def test_target_two_allocates_exactly_two_jobs_and_stores_the_candidates(pw_database):
    seed_batch(pw_database, target=2)
    selector = ScriptedSelector(*cands(3))
    service = allocate_service(pw_database, selector)
    results = [service(allocate_request('batch-1', f'batch-1:job:{n}'), None) for n in (1, 2, 3)]
    assert [r['disposition'] for r in results] == ['succeeded'] * 3
    first, second = refs_of(results[0]), refs_of(results[1])
    assert (first['allocated_job'], first['job_candidate'], first['source_set']) == ('batch-1:job:1', 'c1', 's1')
    assert (second['allocated_job'], second['job_candidate'], second['source_set']) == ('batch-1:job:2', 'c2', 's2')
    assert first['job_reservation'] != second['job_reservation']
    assert refs_of(results[2]) == {'no_more_jobs': 'target_reached'}
    assert rows(pw_database, CANDIDATE_SQL) == [
        ('batch-1:job:1', 'batch-1', 'c1', 's1'),
        ('batch-1:job:2', 'batch-1', 'c2', 's2'),
    ]
    assert [r[0] for r in rows(pw_database, JOBS_SQL)] == ['batch-1:job:1', 'batch-1:job:2']
    assert [r[0] for r in rows(pw_database, RESERVATION_SQL, 'ACTIVE')] == ['batch-1:job:1', 'batch-1:job:2']
    assert selector.calls[0] == ('batch-1', 'single_article')


def test_retry_with_the_same_job_id_returns_the_old_reservation_and_selects_nothing(pw_database):
    seed_batch(pw_database, target=2)
    selector = ScriptedSelector(*cands(2))
    service = allocate_service(pw_database, selector)
    request = allocate_request('batch-1', 'batch-1:job:1')
    first = service(request, None)
    again = service(request, None)
    assert again == first
    assert len(selector.calls) == 1
    assert len(rows(pw_database, JOBS_SQL)) == 1
    assert len(rows(pw_database, CANDIDATE_SQL)) == 1
    assert len(rows(pw_database, RESERVATION_SQL, 'ACTIVE')) == 1


def test_a_selector_without_candidates_returns_no_more_jobs_and_writes_nothing(pw_database):
    seed_batch(pw_database, target=2)
    result = allocate_service(pw_database, ScriptedSelector())(allocate_request('batch-1', 'batch-1:job:1'), None)
    assert result['disposition'] == 'succeeded'
    assert refs_of(result) == {'no_more_jobs': 'candidates_exhausted'}
    assert rows(pw_database, JOBS_SQL) == []
    assert rows(pw_database, CANDIDATE_SQL) == []


def test_a_request_without_the_batch_ref_is_rejected(pw_database):
    service = allocate_service(pw_database, ScriptedSelector(*cands(1)))
    request = allocate_request('batch-1', 'batch-1:job:1')
    request['input_refs'] = request['input_refs'][1:]
    with pytest.raises(ActivityRejected):
        service(request, None)


def test_store_saves_candidate_ref_and_source_set_ref_and_reads_them_back(pw_database):
    seed_batch(pw_database, target=3)
    with pw_database.connect() as conn:
        with conn.transaction():
            store = PostgresAllocationStore(conn, pw_database.workspace_id)
            store.create_job_and_reservation('batch-1', 'job-a', AllocationCandidate('cand-a', 'angle-a', 'set-a'))
            store.create_job_and_reservation('batch-1', 'job-b', AllocationCandidate('cand-b', 'angle-b'))
            assert store.find_candidate('job-a') == AllocationCandidate('cand-a', 'angle-a', 'set-a')
            assert store.find_candidate('job-b') == AllocationCandidate('cand-b', 'angle-b', None)
            assert store.find_candidate('missing') is None
    assert rows(pw_database, CANDIDATE_SQL) == [
        ('job-a', 'batch-1', 'cand-a', 'set-a'),
        ('job-b', 'batch-1', 'cand-b', None),
    ]


def test_batch_params_do_not_require_jobs_but_need_a_lease_without_them():
    payload = {'batch_id': 'b', 'target_videos': 1, 'settings': SETTINGS.to_payload()}
    with pytest.raises(ValueError, match='worker_lease_id'):
        BatchParams.from_payload(payload)
    params = BatchParams.from_payload({**payload, 'worker_lease_id': 'lease-1'})
    assert params.jobs == () and params.production_mode == 'single_article'
    assert BatchParams.from_payload({**payload, 'jobs': [{'job': '1'}]}).jobs == ({'job': '1'},)


def test_batch_allocation_source_is_synchronous_and_uses_the_real_services():
    text = BATCH_ALLOCATION.read_text(encoding='utf-8').lower()
    for needle in ('allocatejob', 'joballocationservice', 'next_candidate', 'batchlifecycle'):
        assert needle in text, needle
    for token in ('fake', 'mock', 'from src.', 'import src', 'async def', 'await '):
        assert token not in text, token


class DbBatchGateway:
    def __init__(self, dispatcher, child_script=()):
        self.dispatcher = dispatcher
        self.child_script = list(child_script)
        self.grants = []
        self.executed = []
        self.children = []

    async def issue_grant(self, stage_run_id, allowed_operation, input_fingerprint, worker_lease_id):
        self.grants.append((stage_run_id, allowed_operation, input_fingerprint, worker_lease_id))
        return {
            'grant_id': 'grant-' + stage_run_id, 'stage_run_id': stage_run_id, 'execution_generation': 1,
            'recovery_epoch': '1', 'worker_lease_id': worker_lease_id, 'issued_at': '2026-10-26T01:00:00Z',
            'expires_at': '2026-10-26T02:00:00Z', 'allowed_operation': allowed_operation,
            'input_fingerprint': input_fingerprint,
        }

    async def execute(self, activity_name, request):
        self.executed.append((activity_name, dict(request)))
        return self.dispatcher.dispatch(request)

    async def run_child(self, workflow_name, payload):
        self.children.append((workflow_name, dict(payload)))
        return {'status': self.child_script.pop(0) if self.child_script else 'COMPLETED'}


def build_gateway(pw_database, selector, child_script=()):
    ws = pw_database.workspace_id
    lifecycle = BatchLifecycle(pw_database.connect, lambda: NOW, workspace_id=ws)
    handlers = {
        'AllocateJob': service_handler(AllocateJobService(pw_database.connect, selector, workspace_id=ws), lambda: NOW),
        'FinalizeBatch': service_handler(FinalizeBatchService(lifecycle), lambda: NOW),
    }
    return DbBatchGateway(ActivityDispatcher(handlers), child_script)


def run_flow(gateway, batch_id='batch-1', target=2, jobs=()):
    params = BatchParams(
        batch_id=batch_id, target_videos=target, jobs=tuple(jobs),
        settings_payload=SETTINGS.to_payload(), worker_lease_id='lease-1',
    )
    flow = ProductionBatchFlow(get_workflow('ProductionBatchWorkflow'), params, gateway, [], [])
    return asyncio.run(flow.run())


def test_flow_without_payload_jobs_runs_two_allocated_children_and_records_target_reached(pw_database):
    seed_batch(pw_database, target=2)
    selector = ScriptedSelector(*cands(5))
    gateway = build_gateway(pw_database, selector)
    result = run_flow(gateway)
    assert (result['status'], result['completed'], result['failed'], result['allocated'], result['finalized']) == ('TARGET_REACHED', 2, 0, 2, True)
    assert [c['child_id'] for c in result['children']] == ['batch-1:video:0', 'batch-1:video:1']
    payloads = [p for name, p in gateway.children if name == 'VideoProductionWorkflow']
    assert [p['video_job_id'] for p in payloads] == ['batch-1:job:1', 'batch-1:job:2']
    assert [p['input_fingerprint'] for p in payloads] == [fingerprint('c1', 's1'), fingerprint('c2', 's2')]
    assert {p['worker_lease_id'] for p in payloads} == {'lease-1'}
    assert payloads[0]['input_refs'] == [{'ref_type': 'job_candidate', 'ref_id': 'c1'}, {'ref_type': 'source_set', 'ref_id': 's1'}]
    assert len(selector.calls) == 2 and len(rows(pw_database, CANDIDATE_SQL)) == 2
    assert [(g[0], g[1]) for g in gateway.grants] == [
        ('batch-1:allocate:r1', 'AllocateJob'), ('batch-1:allocate:r2', 'AllocateJob'), ('batch-1:run_videos:r1', 'FinalizeBatch'),
    ]
    status, reason, stopped_at = rows(pw_database, BATCH_SQL, 'batch-1')[0]
    assert status == 'COMPLETED_TARGET' and reason.startswith('TARGET_REACHED') and stopped_at == NOW


def test_flow_records_exhausted_when_candidates_run_out_before_the_target(pw_database):
    seed_batch(pw_database, target=3)
    gateway = build_gateway(pw_database, ScriptedSelector(*cands(1)))
    result = run_flow(gateway, target=3)
    assert (result['status'], result['completed'], result['allocated'], result['finalized']) == ('EXHAUSTED', 1, 1, True)
    status, reason, _ = rows(pw_database, BATCH_SQL, 'batch-1')[0]
    assert status == 'COMPLETED_EXHAUSTED' and 'candidates_exhausted' in reason


def test_flow_stops_when_a_failed_child_keeps_its_reservation_and_blocks_the_target(pw_database):
    seed_batch(pw_database, target=1)
    gateway = build_gateway(pw_database, ScriptedSelector(*cands(3)), ['FAILED'])
    result = run_flow(gateway, target=1)
    assert (result['status'], result['completed'], result['failed'], result['allocated']) == ('EXHAUSTED', 0, 1, 1)
    assert len(gateway.children) == 1
    assert len(rows(pw_database, CANDIDATE_SQL)) == 1
    assert rows(pw_database, BATCH_SQL, 'batch-1')[0][0] == 'COMPLETED_EXHAUSTED'


def test_payload_jobs_bypass_allocation_and_allocation_grants_but_the_batch_still_finishes(pw_database):
    seed_batch(pw_database, target=1)
    selector = ScriptedSelector(*cands(2))
    gateway = build_gateway(pw_database, selector)
    result = run_flow(gateway, target=1, jobs=[{'job': '1'}])
    assert (result['status'], result['completed'], result['allocated'], result['finalized']) == ('TARGET_REACHED', 1, 0, True)
    assert selector.calls == [] and rows(pw_database, CANDIDATE_SQL) == []
    assert [(g[0], g[1]) for g in gateway.grants] == [('batch-1:run_videos:r1', 'FinalizeBatch')]
    assert [name for name, _ in gateway.executed] == ['FinalizeBatch']
    assert rows(pw_database, BATCH_SQL, 'batch-1')[0][0] == 'COMPLETED_TARGET'


def test_flow_still_returns_when_the_batch_row_is_missing(pw_database):
    gateway = build_gateway(pw_database, ScriptedSelector(*cands(2)))
    result = run_flow(gateway, batch_id='batch-missing', target=2)
    assert (result['status'], result['completed'], result['allocated'], result['finalized']) == ('EXHAUSTED', 0, 0, False)
    assert result['problem']['code'] == 'BATCH_NOT_FOUND'
    assert gateway.children == []


def generic_handler(name, log):
    def handler(request, claims):
        log.append(name)
        return {
            'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation, 'recovery_epoch': claims.recovery_epoch,
            'disposition': 'succeeded', 'completed_at': '2026-10-26T01:02:03Z',
            'output_refs': [{'ref_type': name + '_out', 'ref_id': request['operation_key']}],
        }

    return handler


def logged(name, handler, log):
    def wrapper(request, claims):
        log.append(name)
        return handler(request, claims)

    return wrapper


@pytest.mark.asyncio
async def test_batch_workflow_allocates_runs_children_and_finalizes_on_temporal(pw_database, pw_temporal):
    batch_id = 'pw-g5-' + uuid.uuid4().hex[:8]
    ws = pw_database.workspace_id
    seed_batch(pw_database, batch_id, target=2)
    with pw_database.connect() as connection:
        PostgresAppSessions(connection, ws).begin('ses-1', '5')
    log = []
    selector = ScriptedSelector(*cands(3))
    allocate = service_handler(AllocateJobService(pw_database.connect, selector, workspace_id=ws), lambda: NOW)
    finalize = service_handler(
        FinalizeBatchService(BatchLifecycle(pw_database.connect, lambda: NOW, workspace_id=ws)), lambda: NOW
    )
    handlers = {name: generic_handler(name, log) for name in BINDINGS_BY_NAME}
    handlers['AllocateJob'] = logged('AllocateJob', allocate, log)
    handlers['FinalizeBatch'] = logged('FinalizeBatch', finalize, log)
    services = build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=lambda: NOW, timezone_approved=False)
    services = replace(services, dispatcher=GrantRevokingDispatcher(services.dispatcher, pw_database.connect, ws))
    registration = build_temporal_registration(
        services,
        grant_issuer=build_grant_issuer(pw_database.connect, ws, None, lambda: NOW),
        capability_reader=lambda: {'desktop_production': {'status': 'available'}},
    )
    payload = {'settings': SETTINGS.to_payload(), 'target_videos': 2, 'worker_lease_id': 'lease-1'}
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows)} if queue == 'control-workflows' else {}
            await stack.enter_async_context(Worker(
                pw_temporal, task_queue=queue, activities=list(functions),
                workflow_runner=UnsandboxedWorkflowRunner(), **extra,
            ))
        handle = await pw_temporal.start_workflow('ProductionBatchWorkflow', payload, id=batch_id, task_queue='control-workflows')
        result = await asyncio.wait_for(handle.result(), timeout=300)
    assert (result['status'], result['completed'], result['allocated'], result['finalized']) == ('TARGET_REACHED', 2, 2, True)
    assert log.count('AllocateJob') == 2 and log.count('FinalizeBatch') == 1
    assert [r[0] for r in rows(pw_database, CANDIDATE_SQL)] == [f'{batch_id}:job:1', f'{batch_id}:job:2']
    assert rows(pw_database, BATCH_SQL, batch_id)[0][0] == 'COMPLETED_TARGET'
