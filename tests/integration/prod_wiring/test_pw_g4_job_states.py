"""PW-G4: CapabilityReader, PostgresJobStates, JobLifecycleListener và BatchLifecycle trên PostgreSQL thử.

coveredIds: PW-G4-01..05, CT-ORC-007, CT-ORC-010, CT-WF-007
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import pytest

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services
from controlplane.application.orchestration.capability_view import CapabilityReader
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle, JobLifecycleListener
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.workflows.activities import ActivityDispatcher
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.batch_outcome import BatchOutcome
from controlplane.domain.orchestration.job_waiting import Proceed, Wait, WaitReason, evaluate_wait
from controlplane.domain.statemachine import ForbiddenTransitionError, JobState
from controlplane.infrastructure.db.orchestration.job_states import PostgresJobStates

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 26, 1, 2, 9, tzinfo=timezone.utc)
SOURCES = (
    ROOT / 'src/controlplane/application/orchestration/capability_view.py',
    ROOT / 'src/controlplane/application/orchestration/job_lifecycle.py',
    ROOT / 'src/controlplane/infrastructure/db/orchestration/job_states.py',
)
PROBES = ('app_session_active', 'ffmpeg_pinned', 'gpu_lease_ready')
SNAPSHOT, PROBE, PERSIST = 'BuildProductionSnapshot', 'ProbeMedia', 'PersistVideoOutput'


def probes_of(*values):
    return {name: (lambda value=value: value) for name, value in zip(PROBES, values)}


def raising():
    raise RuntimeError('probe down')


@pytest.mark.parametrize('values', list(product((True, False), repeat=3)))
def test_status_follows_the_probe_truth_table(values):
    app, ffmpeg, _gpu = values
    expected = 'available' if all(values) else 'degraded' if app and ffmpeg else 'unavailable'
    assert CapabilityReader(probes_of(*values))() == {'desktop_production': {'status': expected}}


@pytest.mark.parametrize('broken', PROBES)
@pytest.mark.parametrize('others', [True, False])
def test_a_raising_probe_makes_the_status_unknown_and_the_workflow_waits(broken, others):
    probes = probes_of(others, others, others)
    probes[broken] = raising
    view = CapabilityReader(probes)()
    assert view == {'desktop_production': {'status': 'unknown'}}
    assert evaluate_wait('script', view) == Wait(WaitReason.DESKTOP_OFFLINE)


@pytest.mark.parametrize('value', [None, 1, 0, 'yes', [], {}])
def test_a_non_bool_probe_result_is_unknown(value):
    probes = probes_of(True, True, True)
    probes['gpu_lease_ready'] = lambda: value
    assert CapabilityReader(probes)() == {'desktop_production': {'status': 'unknown'}}


def test_every_probe_runs_on_each_call():
    calls = []
    reader = CapabilityReader({name: (lambda name=name: calls.append(name) or True) for name in PROBES})
    reader()
    reader()
    assert calls == list(PROBES) * 2


def test_only_available_and_degraded_let_a_desktop_stage_run():
    for status, runs in (('available', True), ('degraded', True), ('unavailable', False), ('unknown', False)):
        assert isinstance(evaluate_wait('tts', {'desktop_production': {'status': status}}), Proceed) is runs
    assert isinstance(evaluate_wait('render', {'desktop_production': {'status': 'unknown'}}), Proceed)


def test_constructor_requires_exactly_the_three_callable_probes():
    good = probes_of(True, True, True)
    with pytest.raises(ValueError):
        CapabilityReader({k: v for k, v in good.items() if k != 'ffmpeg_pinned'})
    with pytest.raises(ValueError):
        CapabilityReader({**good, 'extra': lambda: True})
    with pytest.raises(ValueError):
        CapabilityReader(None)
    with pytest.raises(TypeError):
        CapabilityReader({**good, 'ffmpeg_pinned': True})


PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}


def capability_activity(capability_reader):
    services = build_workflow_services(parameters=PARAMETERS, handlers={}, clock=lambda: NOW, timezone_approved=False)
    registration = build_temporal_registration(services, grant_issuer=lambda *args: None, capability_reader=capability_reader)
    for fn in registration.activities_by_queue['control-workflows']:
        if getattr(fn, '__temporal_activity_definition').name == 'ReadCapabilityView':
            return fn
    raise AssertionError('ReadCapabilityView')


async def run_with_ticks(awaitable):
    ticks = []

    async def heartbeat():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.ensure_future(heartbeat())
    try:
        result = await awaitable
    finally:
        task.cancel()
    return result, len(ticks)


def test_probes_run_off_the_event_loop_through_the_capability_activity():
    threads = []

    def slow_probe():
        threads.append(threading.get_ident())
        time.sleep(0.1)
        return True

    reader = CapabilityReader({name: slow_probe for name in PROBES})
    view, ticks = asyncio.run(run_with_ticks(capability_activity(reader)({})))
    assert view == {'desktop_production': {'status': 'available'}}
    assert len(threads) == 3 and threading.get_ident() not in threads
    assert ticks >= 10


JOB_SQL = 'SELECT status, revision, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s'


def seed_batch(conn, ws, batch_id='batch-1', status='RUNNING'):
    conn.execute('INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, 1)', (batch_id, ws, status))


def seed_job(pw_database, status='CREATED', job_id='job-1', batch_id='batch-1'):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        if conn.execute('SELECT 1 FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s', (ws, batch_id)).fetchone() is None:
            seed_batch(conn, ws, batch_id)
        conn.execute('INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, 1)', (job_id, batch_id, ws, status, 'snap-1'))


def job_row(pw_database, job_id='job-1'):
    with pw_database.connect() as conn:
        return conn.execute(JOB_SQL, (pw_database.workspace_id, job_id)).fetchone()


def with_states(pw_database, action):
    with pw_database.connect() as conn:
        with conn.transaction():
            return action(PostgresJobStates(conn, pw_database.workspace_id))


def test_store_walks_the_job_graph_and_bumps_the_revision(pw_database):
    seed_job(pw_database)
    steps = [
        (lambda s: s.transition('job-1', JobState.SNAPSHOTTED), JobState.SNAPSHOTTED, ('SNAPSHOTTED', 2, None)),
        (lambda s: s.transition('job-1', JobState.ACTIVE), JobState.ACTIVE, ('ACTIVE', 3, None)),
        (lambda s: s.apply_decision('job-1', Wait(WaitReason.DESKTOP_OFFLINE)), JobState.WAITING, ('WAITING', 4, 'desktop_offline')),
        (lambda s: s.apply_decision('job-1', Proceed()), JobState.ACTIVE, ('ACTIVE', 5, None)),
        (lambda s: s.apply_decision('job-1', Proceed()), None, ('ACTIVE', 5, None)),
        (lambda s: s.transition('job-1', JobState.READY_FOR_COMPLETION), JobState.READY_FOR_COMPLETION, ('READY_FOR_COMPLETION', 6, None)),
    ]
    for action, returned, row in steps:
        assert with_states(pw_database, action) == returned
        assert job_row(pw_database) == row


FORBIDDEN = [
    ('CREATED', 'ACTIVE'), ('CREATED', 'READY_FOR_COMPLETION'), ('CREATED', 'COMPLETED'), ('SNAPSHOTTED', 'WAITING'),
    ('SNAPSHOTTED', 'READY_FOR_COMPLETION'), ('SNAPSHOTTED', 'FAILED_FINAL'), ('ACTIVE', 'COMPLETED'), ('ACTIVE', 'SNAPSHOTTED'),
    ('ACTIVE', 'ACTIVE'), ('READY_FOR_COMPLETION', 'ACTIVE'), ('COMPLETED', 'ACTIVE'), ('FAILED_FINAL', 'ACTIVE'),
]


@pytest.mark.parametrize('start, requested', FORBIDDEN)
def test_store_rejects_edges_outside_ct_state_and_writes_nothing(pw_database, start, requested):
    seed_job(pw_database, start)
    before = job_row(pw_database)
    with pytest.raises(ForbiddenTransitionError):
        with_states(pw_database, lambda s: s.transition('job-1', JobState(requested)))
    assert job_row(pw_database) == before


@pytest.mark.parametrize('start', ['CREATED', 'SNAPSHOTTED', 'READY_FOR_COMPLETION', 'COMPLETED', 'FAILED_FINAL'])
@pytest.mark.parametrize('decision', [Proceed(), Wait(WaitReason.QUOTA_WAIT)])
def test_store_decisions_are_only_legal_between_active_and_waiting(pw_database, start, decision):
    seed_job(pw_database, start)
    before = job_row(pw_database)
    with pytest.raises(ForbiddenTransitionError):
        with_states(pw_database, lambda s: s.apply_decision('job-1', decision))
    assert job_row(pw_database) == before


def test_store_unknown_job(pw_database):
    with pw_database.connect() as conn:
        assert PostgresJobStates(conn, pw_database.workspace_id).state_of('missing') is None
    with pytest.raises(OrchestrationContractError) as info:
        with_states(pw_database, lambda s: s.transition('missing', JobState.SNAPSHOTTED))
    assert info.value.code == 'JOB_NOT_FOUND'


def listener_for(pw_database):
    return JobLifecycleListener(pw_database.connect, workspace_id=pw_database.workspace_id)


def call(listener, activity, disposition, job_id='job-1', **extra):
    request = {'stage_run_id': job_id + ':process:r1', 'activity_name': activity}
    listener.on_result(request, {'disposition': disposition, **extra})


def test_listener_walks_snapshotted_active_waiting_active_ready(pw_database):
    seed_job(pw_database)
    listener = listener_for(pw_database)
    plan = [
        ((SNAPSHOT, 'succeeded', {}), ('SNAPSHOTTED', 2, None)),
        ((PROBE, 'succeeded', {}), ('ACTIVE', 3, None)),
        ((PROBE, 'waiting', {'problem': {'code': 'quota_wait'}}), ('WAITING', 4, 'quota_wait')),
        ((PROBE, 'succeeded', {}), ('ACTIVE', 5, None)),
        ((PERSIST, 'succeeded', {}), ('READY_FOR_COMPLETION', 6, None)),
    ]
    for (activity, disposition, extra), row in plan:
        call(listener, activity, disposition, **extra)
        assert job_row(pw_database) == row


def test_listener_waiting_right_after_the_snapshot_passes_through_active(pw_database):
    seed_job(pw_database, 'SNAPSHOTTED')
    call(listener_for(pw_database), PROBE, 'waiting')
    assert job_row(pw_database) == ('WAITING', 3, 'provider_unavailable')


ADVANCE_CASES = [
    ('ACTIVE', PROBE, 'failed', {'problem': {'code': 'X', 'retryable': False}}, ('FAILED_FINAL', 2, None)),
    ('ACTIVE', PROBE, 'failed', {}, ('FAILED_FINAL', 2, None)),
    ('WAITING', PROBE, 'failed', {'problem': {'code': 'X'}}, ('FAILED_FINAL', 2, None)),
    ('SNAPSHOTTED', PROBE, 'failed', {}, ('FAILED_FINAL', 3, None)),
    ('READY_FOR_COMPLETION', PERSIST, 'failed', {}, ('FAILED_FINAL', 2, None)),
    ('WAITING', PERSIST, 'succeeded', {}, ('READY_FOR_COMPLETION', 2, None)),
    ('SNAPSHOTTED', PERSIST, 'succeeded', {}, ('READY_FOR_COMPLETION', 3, None)),
    ('ACTIVE', PROBE, 'failed', {'problem': {'code': 'X', 'retryable': True}}, ('ACTIVE', 1, None)),
    ('ACTIVE', PROBE, 'outcome_unknown', {}, ('ACTIVE', 1, None)),
    ('WAITING', PROBE, 'stale', {}, ('ACTIVE', 2, None)),
    ('CREATED', PROBE, 'succeeded', {}, ('CREATED', 1, None)),
    ('CREATED', PROBE, 'failed', {}, ('CREATED', 1, None)),
    ('CREATED', PERSIST, 'succeeded', {}, ('CREATED', 1, None)),
    ('SNAPSHOTTED', SNAPSHOT, 'succeeded', {}, ('SNAPSHOTTED', 1, None)),
    ('ACTIVE', SNAPSHOT, 'succeeded', {}, ('ACTIVE', 1, None)),
    ('ACTIVE', PROBE, 'succeeded', {}, ('ACTIVE', 1, None)),
    ('READY_FOR_COMPLETION', PROBE, 'waiting', {}, ('READY_FOR_COMPLETION', 1, None)),
    ('READY_FOR_COMPLETION', PERSIST, 'succeeded', {}, ('READY_FOR_COMPLETION', 1, None)),
    ('COMPLETED', PROBE, 'waiting', {}, ('COMPLETED', 1, None)),
    ('FAILED_FINAL', PROBE, 'succeeded', {}, ('FAILED_FINAL', 1, None)),
]


@pytest.mark.parametrize('start, activity, disposition, extra, row', ADVANCE_CASES)
def test_listener_applies_only_legal_edges_for_each_result(pw_database, start, activity, disposition, extra, row):
    seed_job(pw_database, start)
    call(listener_for(pw_database), activity, disposition, **extra)
    assert job_row(pw_database) == row


def test_listener_ignores_owners_that_are_not_jobs_and_malformed_requests(pw_database):
    seed_job(pw_database, 'ACTIVE')
    listener = listener_for(pw_database)
    call(listener, PROBE, 'waiting', job_id='wf-1')
    for request in (42, {}, {'stage_run_id': 'bad'}, {'stage_run_id': 'job-1:process:r0'}):
        listener.on_result(request, {'disposition': 'waiting'})
    listener.on_result({'stage_run_id': 'job-1:process:r1'}, 'not-a-mapping')
    assert job_row(pw_database) == ('ACTIVE', 1, None)


@pytest.mark.parametrize('extra, reason', [
    ({}, 'provider_unavailable'),
    ({'problem': {'code': 'weird'}}, 'provider_unavailable'),
    ({'problem': 'x'}, 'provider_unavailable'),
    ({'problem': {'code': 'desktop_offline'}}, 'desktop_offline'),
])
def test_listener_writes_the_same_wait_reason_as_the_stage_run(pw_database, extra, reason):
    seed_job(pw_database, 'ACTIVE')
    call(listener_for(pw_database), PROBE, 'waiting', **extra)
    assert job_row(pw_database) == ('WAITING', 2, reason)


def request_for(activity, stage, revision):
    sid = f'job-1:{stage}:r{revision}'
    grant = {'grant_id': 'grant-' + sid, 'stage_run_id': sid, 'execution_generation': 1, 'recovery_epoch': '5', 'worker_lease_id': 'lease-1', 'issued_at': '2026-10-26T01:00:00Z', 'expires_at': '2026-10-26T02:00:00Z', 'allowed_operation': activity, 'input_fingerprint': 'fp-1'}
    return {'workflow_id': 'wf-1', 'workflow_run_id': 'run-1', 'stage_run_id': sid, 'activity_name': activity, 'activity_version': '1', 'input_refs': [], 'operation_key': 'op-' + sid, 'capability_requirements': {}, 'retry_policy_ref': 'retry-1', 'execution_grant': grant}


def test_job_chain_through_the_result_recording_dispatcher(pw_database):
    seed_job(pw_database)
    outcomes = []

    def handler(request, claims):
        disposition, extra = outcomes.pop(0)
        g = request['execution_grant']
        return {'stage_run_id': g['stage_run_id'], 'grant_id': g['grant_id'], 'execution_generation': 1, 'recovery_epoch': '5', 'disposition': disposition, 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra}

    inner = ActivityDispatcher({SNAPSHOT: handler, PROBE: handler, PERSIST: handler})
    dispatcher = ResultRecordingDispatcher(inner, pw_database.connect, lambda: NOW, [listener_for(pw_database)], workspace_id=pw_database.workspace_id)
    steps = [
        (SNAPSHOT, 'analyze', 1, 'succeeded', {}, ('SNAPSHOTTED', 2, None)),
        (PROBE, 'process', 1, 'succeeded', {}, ('ACTIVE', 3, None)),
        (PROBE, 'process', 2, 'waiting', {'problem': {'code': 'desktop_offline'}}, ('WAITING', 4, 'desktop_offline')),
        (PROBE, 'process', 3, 'succeeded', {}, ('ACTIVE', 5, None)),
        (PERSIST, 'sync', 1, 'succeeded', {}, ('READY_FOR_COMPLETION', 6, None)),
    ]
    for activity, stage, revision, disposition, extra, row in steps:
        outcomes.append((disposition, extra))
        dispatcher.dispatch(request_for(activity, stage, revision))
        assert job_row(pw_database) == row
    with pw_database.connect() as conn:
        runs = sorted(conn.execute('SELECT stage_run_id, status FROM controlplane.cp_stage_runs WHERE workspace_id = %s', (pw_database.workspace_id,)).fetchall())
    assert runs == [('job-1:analyze:r1', 'RUNNING'), ('job-1:process:r1', 'RUNNING'), ('job-1:process:r2', 'RUNNING'), ('job-1:process:r3', 'RUNNING'), ('job-1:sync:r1', 'SUCCEEDED')]


BATCH_SQL = 'SELECT status, stop_reason, stopped_at FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s'


def seed_one_batch(pw_database, status='RUNNING', batch_id='batch-1'):
    with pw_database.connect() as conn:
        seed_batch(conn, pw_database.workspace_id, batch_id, status)


def batch_row(pw_database, batch_id='batch-1'):
    with pw_database.connect() as conn:
        return conn.execute(BATCH_SQL, (pw_database.workspace_id, batch_id)).fetchone()


def lifecycle_for(pw_database, now=NOW):
    return BatchLifecycle(pw_database.connect, lambda: now, workspace_id=pw_database.workspace_id)


def test_finish_twice_does_not_change_the_row(pw_database):
    seed_one_batch(pw_database)
    assert lifecycle_for(pw_database, NOW).finish('batch-1', 'COMPLETED_TARGET', 'target reached') is True
    first = batch_row(pw_database)
    assert first == ('COMPLETED_TARGET', 'target reached', NOW)
    assert lifecycle_for(pw_database, LATER).finish('batch-1', BatchOutcome.COMPLETED_TARGET, 'again') is False
    assert batch_row(pw_database) == first


def test_finish_waiting_capability_twice_keeps_the_first_stop(pw_database):
    seed_one_batch(pw_database)
    assert lifecycle_for(pw_database, NOW).finish('batch-1', 'WAITING_CAPABILITY', 'desktop offline') is True
    assert lifecycle_for(pw_database, LATER).finish('batch-1', 'WAITING_CAPABILITY', 'still offline') is False
    assert batch_row(pw_database) == ('WAITING_CAPABILITY', 'desktop offline', NOW)


@pytest.mark.parametrize('start, outcome', [
    ('RUNNING', 'COMPLETED_TARGET'), ('RUNNING', 'COMPLETED_EXHAUSTED'), ('RUNNING', 'WAITING_CAPABILITY'), ('RUNNING', 'FAILED_SYSTEM'),
    ('WAITING_CAPABILITY', 'COMPLETED_TARGET'), ('WAITING_CAPABILITY', 'COMPLETED_EXHAUSTED'), ('WAITING_CAPABILITY', 'FAILED_SYSTEM'),
])
def test_finish_writes_status_reason_and_stopped_at_for_every_stop(pw_database, start, outcome):
    seed_one_batch(pw_database, start)
    seed_one_batch(pw_database, 'RUNNING', 'batch-2')
    assert lifecycle_for(pw_database).finish('batch-1', outcome, 'reason for ' + outcome) is True
    assert batch_row(pw_database) == (outcome, 'reason for ' + outcome, NOW)
    assert batch_row(pw_database, 'batch-2') == ('RUNNING', None, None)


@pytest.mark.parametrize('start, outcome', [
    ('CREATED', 'COMPLETED_TARGET'), ('CREATED', 'WAITING_CAPABILITY'), ('COMPLETED_TARGET', 'FAILED_SYSTEM'),
    ('COMPLETED_EXHAUSTED', 'COMPLETED_TARGET'), ('FAILED_SYSTEM', 'COMPLETED_TARGET'),
])
def test_finish_rejects_edges_outside_ct_state_and_writes_nothing(pw_database, start, outcome):
    seed_one_batch(pw_database, start)
    before = batch_row(pw_database)
    with pytest.raises(ForbiddenTransitionError):
        lifecycle_for(pw_database).finish('batch-1', outcome, 'why')
    assert batch_row(pw_database) == before


@pytest.mark.parametrize('status, reason, code', [
    ('CONTINUE', 'why', 'INVALID_BATCH_STATUS'), ('BOGUS', 'why', 'INVALID_BATCH_STATUS'), (None, 'why', 'INVALID_BATCH_STATUS'),
    ('COMPLETED_TARGET', '', 'INVALID_STOP_REASON'), ('COMPLETED_TARGET', '   ', 'INVALID_STOP_REASON'), ('COMPLETED_TARGET', None, 'INVALID_STOP_REASON'),
])
def test_finish_rejects_invalid_status_or_reason_and_writes_nothing(pw_database, status, reason, code):
    seed_one_batch(pw_database)
    with pytest.raises(OrchestrationContractError) as info:
        lifecycle_for(pw_database).finish('batch-1', status, reason)
    assert info.value.code == code
    assert batch_row(pw_database) == ('RUNNING', None, None)


def test_finish_of_a_missing_batch_is_rejected(pw_database):
    with pytest.raises(OrchestrationContractError) as info:
        lifecycle_for(pw_database).finish('missing', 'COMPLETED_TARGET', 'why')
    assert info.value.code == 'BATCH_NOT_FOUND'


def test_sources_are_synchronous_and_use_the_state_machine():
    for path in SOURCES:
        text = path.read_text(encoding='utf-8').lower()
        for token in ('from src.', 'import src', 'fake', 'mock', 'inmemory', 'pw_support', 'asyncio', 'async def', 'await '):
            assert token not in text, (path.name, token)
    assert 'connection.transaction()' in SOURCES[1].read_text(encoding='utf-8')
    assert 'plan_job_transition' in SOURCES[2].read_text(encoding='utf-8')
    assert 'plan_batch_transition' in SOURCES[2].read_text(encoding='utf-8')
