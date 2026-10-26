"""PW-VERT: một video đi hết VideoProductionWorkflow trên temporalio và PostgreSQL thử.

coveredIds: PW-VERT-01, CT-WF-004, CT-WF-007, CT-ORC-010
"""
from __future__ import annotations

import ast
import asyncio
from collections import Counter
import re
from pathlib import Path

import pytest
import pytest_asyncio
from temporalio.client import WorkflowExecutionStatus
import temporalio.api.testservice.v1 as testservice

from pw_vertical import (
    CapabilitySwitch,
    DesktopAdapters,
    EXPECTED_ACTIVITIES,
    FAKE_ACTIVITIES,
    G_ACTIVITIES,
    VIDEO_ACTIVITIES,
    VIDEO_STAGES,
    Vertical,
    batch_row,
    count,
    grants_by_stage,
    job_row,
    live_grants,
    rows,
    scalar,
    stage_runs,
    wait_until,
)

ROOT = Path(__file__).resolve().parents[3]
VERTICAL_SOURCE = ROOT / 'tests/integration/prod_wiring/pw_vertical.py'
START_EVENT = 'production_batch.start_accepted'
TRACE = ('SNAPSHOTTED', 'ACTIVE', 'READY_FOR_COMPLETION', 'COMPLETED')


@pytest_asyncio.fixture
async def make_vertical(pw_database, pw_temporal):
    started = []

    async def factory(**kwargs):
        vertical = Vertical(pw_database, pw_temporal, **kwargs)
        started.append(vertical)
        await vertical.start()
        return vertical

    try:
        yield factory
    finally:
        for v in reversed(started):
            await v.stop()


def check_finished_video(
    verticals,
    database,
    batch_id,
    child,
    *,
    expected=None,
    trace=None,
    extra_calls=None,
    epochs=None,
):
    if expected is None:
        expected = EXPECTED_ACTIVITIES
    if trace is None:
        trace = TRACE
    if epochs is None:
        epochs = {s: '5' for s in VIDEO_STAGES}
    job_id = f'{batch_id}:job:1'

    # (a) snapshot child
    assert child['status'] == 'COMPLETED', child
    assert child['failed_stage'] is None, child
    assert child['unbound'] == [], child
    assert child['last_problem'] is None, child
    assert child['rejected_signals'] == [], child
    assert sorted(child['completed']) == sorted(VIDEO_STAGES)
    assert len(child['completed']) == 11
    assert child['attempts'] == expected

    # (b) cp_stage_runs
    assert sorted((r[0], r[1], r[2], r[3]) for r in stage_runs(database, job_id)) == sorted(
        (s, 'SUCCEEDED', 1, epochs[s]) for s in VIDEO_STAGES
    )

    # (c) cp_execution_grants
    grants = grants_by_stage(database)
    for stage in VIDEO_STAGES:
        entries = grants[f'{job_id}:{stage}:r1']
        assert [e[0] for e in entries] == list(range(1, expected[stage] + 1))
        assert all(e[2] for e in entries)
        assert {e[1] for e in entries} == {epochs[stage]}
        for e in entries:
            assert re.fullmatch(r'[0-9]+', e[1]), e[1]
    assert live_grants(database) == 0

    # (d) trace
    combined_history = []
    for v in verticals:
        for status in v.job_trace.history.get(job_id, []):
            if not combined_history or combined_history[-1] != status:
                combined_history.append(status)
    assert combined_history == list(trace)

    # (e) calls
    total_calls = Counter()
    for v in verticals:
        total_calls.update(v.adapters.calls)
    expected_calls = {name: 1 for name in FAKE_ACTIVITIES}
    expected_calls['ValidateVariant'] = 2
    if extra_calls:
        expected_calls.update(extra_calls)
    assert dict(total_calls) == expected_calls

    # (f) CSDL
    assert count(database, 'cp_completion_ledger') == 1
    assert job_row(database, job_id)[0] == 'COMPLETED'
    var_state = scalar(
        database,
        'SELECT state FROM controlplane.cp_variant_reservations WHERE workspace_id = %s AND job_id = %s',
        job_id,
    )
    assert var_state == 'CONVERTED'
    cap_state = scalar(
        database,
        'SELECT state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id = %s AND job_id = %s',
        job_id,
    )
    assert cap_state == 'CONVERTED'

    # (g) bound activities
    assert verticals[0].services.bound_activities >= set(VIDEO_ACTIVITIES) | set(G_ACTIVITIES)


@pytest.mark.asyncio
async def test_one_video_batch_runs_all_eleven_stages_to_completed(pw_database, pw_temporal, make_vertical):
    v = await make_vertical(session=('ses-1', '5'))
    batch_id = v.start_batch(1)
    relay = v.relay()
    assert await relay.run_once() == 1
    result = await asyncio.wait_for(pw_temporal.get_workflow_handle(batch_id).result(), 300)
    assert (
        result['status'],
        result['completed'],
        result['failed'],
        result['allocated'],
        result['finalized'],
    ) == ('TARGET_REACHED', 1, 0, 1, True), result
    assert result['children'] == [{'child_id': f'{batch_id}:video:0', 'status': 'COMPLETED'}]
    child = await asyncio.wait_for(pw_temporal.get_workflow_handle(f'{batch_id}:video:0').result(), 60)
    check_finished_video([v], pw_database, batch_id, child)

    brow = batch_row(pw_database, batch_id)
    assert brow[0] == 'COMPLETED_TARGET'
    assert brow[1].startswith('TARGET_REACHED')
    assert brow[2] is not None

    grants = grants_by_stage(pw_database)
    assert len(grants[f'{batch_id}:allocate:r1']) == 1 and grants[f'{batch_id}:allocate:r1'][0][2] is True
    assert len(grants[f'{batch_id}:run_videos:r1']) == 1 and grants[f'{batch_id}:run_videos:r1'][0][2] is True
    assert v.selector.calls == [(batch_id, 'single_article')]

    assert len(v.start_client.calls) == 1
    args, kwargs = v.start_client.calls[0]
    assert args[0] == 'ProductionBatchWorkflow'
    assert kwargs['id'] == batch_id
    assert await relay.run_once() == 0
    assert len(v.start_client.calls) == 1
    assert rows(
        pw_database,
        'SELECT published FROM controlplane.cp_outbox_events WHERE workspace_id = %s AND event_name = %s',
        START_EVENT,
    ) == [(True,)]


@pytest.mark.asyncio
async def test_capability_unavailable_holds_before_the_desktop_stage_then_resumes(pw_database, pw_temporal, make_vertical):
    switch = CapabilitySwitch()
    switch.ffmpeg_pinned = False
    v = await make_vertical(session=('ses-1', '5'), switch=switch)
    batch_id = v.start_batch(1)
    assert await v.relay().run_once() == 1
    job_id = f'{batch_id}:job:1'
    await wait_until(lambda: v.adapters.calls['AnalyzeContent'] == 1 and switch.reads >= 3, what='gate wait after analyze')

    assert {r[0] for r in stage_runs(pw_database, job_id)} == {'analyze'}
    assert job_row(pw_database, job_id) == ('ACTIVE', None)
    assert v.adapters.calls['GenerateStoryAngles'] == 0
    desc = await pw_temporal.get_workflow_handle(f'{batch_id}:video:0').describe()
    assert desc.status == WorkflowExecutionStatus.RUNNING

    switch.ffmpeg_pinned = True
    await asyncio.wait_for(pw_temporal.get_workflow_handle(batch_id).result(), 300)
    child = await asyncio.wait_for(pw_temporal.get_workflow_handle(f'{batch_id}:video:0').result(), 60)
    check_finished_video([v], pw_database, batch_id, child)


@pytest.mark.asyncio
async def test_a_capability_drop_during_an_activity_marks_the_job_waiting_then_it_resumes(pw_database, pw_temporal, make_vertical):
    switch = CapabilitySwitch()
    adapters = DesktopAdapters(pw_database, switch=switch, drop_capability_on='CreateVoiceTrack')
    v = await make_vertical(session=('ses-1', '5'), switch=switch, adapters=adapters)
    batch_id = v.start_batch(1)
    assert await v.relay().run_once() == 1
    job_id = f'{batch_id}:job:1'
    await wait_until(lambda: job_row(pw_database, job_id) == ('WAITING', 'desktop_offline'), what='job WAITING')

    runs = {r[0]: r for r in stage_runs(pw_database, job_id)}
    assert runs['tts'][1] == 'RUNNING'
    assert runs['tts'][4] == 'desktop_offline'
    assert 'align' not in runs
    assert switch.ffmpeg_pinned is False
    assert v.job_trace.history[job_id] == ['SNAPSHOTTED', 'ACTIVE', 'WAITING']

    switch.ffmpeg_pinned = True
    await asyncio.wait_for(pw_temporal.get_workflow_handle(batch_id).result(), 300)
    child = await asyncio.wait_for(pw_temporal.get_workflow_handle(f'{batch_id}:video:0').result(), 60)
    check_finished_video(
        [v],
        pw_database,
        batch_id,
        child,
        expected={**EXPECTED_ACTIVITIES, 'tts': 2},
        trace=('SNAPSHOTTED', 'ACTIVE', 'WAITING', 'ACTIVE', 'READY_FOR_COMPLETION', 'COMPLETED'),
        extra_calls={'CreateVoiceTrack': 2},
    )


@pytest.mark.asyncio
async def test_retry_stage_after_the_second_activity_failed_reruns_only_that_activity(pw_database, pw_temporal, make_vertical):
    switch = CapabilitySwitch()
    adapters = DesktopAdapters(pw_database, switch=switch, fail_plan_validation=3)
    v = await make_vertical(session=('ses-1', '5'), switch=switch, adapters=adapters)
    batch_id = v.start_batch(1)
    handle, job_id = await v.start_video(batch_id, hold_on_failure=True)
    outcome = asyncio.ensure_future(handle.result())
    await wait_until(lambda: adapters.stage_calls[('plan', 'ValidateVariant')] == 3, timeout=60, what='three failed validations')
    try:
        await pw_temporal.test_service.lock_time_skipping(testservice.LockTimeSkippingRequest())
    except Exception:
        pass
    await asyncio.sleep(1.0)
    assert not outcome.done()
    assert adapters.stage_calls[('plan', 'ValidateVariant')] == 3
    assert adapters.calls['BuildProductionPlan'] == 1
    assert job_row(pw_database, job_id) == ('ACTIVE', None)

    await handle.signal('RetryStage', 'plan')
    try:
        await pw_temporal.test_service.unlock_time_skipping(testservice.UnlockTimeSkippingRequest())
    except Exception:
        pass
    child = await asyncio.wait_for(outcome, 300)
    check_finished_video(
        [v],
        pw_database,
        batch_id,
        child,
        expected={**EXPECTED_ACTIVITIES, 'plan': 7},
        extra_calls={'ValidateVariant': 5},
    )
    assert adapters.calls['BuildProductionPlan'] == 1
    assert count(pw_database, 'cp_variant_reservations') == 1


@pytest.mark.asyncio
async def test_stopping_the_worker_between_two_stages_and_starting_a_new_one_reruns_nothing(pw_database, pw_temporal, make_vertical):
    switch1 = CapabilitySwitch()
    switch1.ffmpeg_pinned = False
    v1 = await make_vertical(session=('ses-1', '5'), switch=switch1, max_cached_workflows=0)
    batch_id = v1.start_batch(1)
    assert await v1.relay().run_once() == 1
    job_id = f'{batch_id}:job:1'
    await wait_until(lambda: v1.adapters.calls['AnalyzeContent'] == 1 and switch1.reads >= 3, what='gate wait after analyze')
    await v1.stop()
    v2 = await make_vertical(session=('ses-2', '6'), max_cached_workflows=0)
    await asyncio.wait_for(pw_temporal.get_workflow_handle(batch_id).result(), 300)
    child = await asyncio.wait_for(pw_temporal.get_workflow_handle(f'{batch_id}:video:0').result(), 60)
    assert v2.adapters.calls['BuildProductionSnapshot'] == 0
    assert v2.adapters.calls['AnalyzeContent'] == 0
    assert sum(1 for r in stage_runs(pw_database, job_id) if r[0] == 'analyze') == 1
    check_finished_video(
        [v1, v2],
        pw_database,
        batch_id,
        child,
        epochs={s: ('5' if s == 'analyze' else '6') for s in VIDEO_STAGES},
    )


@pytest.mark.asyncio
async def test_without_grant_revocation_the_second_activity_hits_active_grant_exists(pw_database, pw_temporal, make_vertical):
    v = await make_vertical(session=('ses-1', '5'), revoke_grants=False)
    batch_id = v.start_batch(1)
    handle, job_id = await v.start_video(batch_id, hold_on_failure=False)
    child = await asyncio.wait_for(handle.result(), 300)
    assert child['status'] == 'FAILED', child
    assert child['failed_stage'] == 'analyze', child
    assert v.adapters.calls['BuildProductionSnapshot'] == 1
    assert v.adapters.calls['AnalyzeContent'] == 0
    assert grants_by_stage(pw_database)[f'{job_id}:analyze:r1'] == [(1, '5', False)]
    assert live_grants(pw_database) == 1


def test_pw_vertical_assembles_the_real_g_components_without_in_memory_stores():
    text = VERTICAL_SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(text)
    names = set()
    called = set()
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)

    assert 'InMemoryGrantStore' not in text
    assert 'from src.' not in text
    assert 'import src' not in text
    assert 'pw_support' not in text
    assert not any('inmemory' in item.lower() for item in (names | defined))
    assert {
        'PostgresAppSessions',
        'ResultRecordingDispatcher',
        'GrantRevokingDispatcher',
        'build_grant_issuer',
        'CapabilityReader',
        'OutboxRelay',
        'AllocateJobService',
        'FinalizeBatchService',
        'reserve_variant_handler',
        'commit_video_completion_handler',
        'JobLifecycleListener',
        'BatchLifecycle',
        'build_workflow_services',
        'build_temporal_registration',
        'service_handler',
    } <= names
    assert {
        'ResultRecordingDispatcher',
        'GrantRevokingDispatcher',
        'CapabilityReader',
        'OutboxRelay',
        'AllocateJobService',
        'FinalizeBatchService',
        'reserve_variant_handler',
        'commit_video_completion_handler',
        'build_workflow_services',
        'build_temporal_registration',
        'build_grant_issuer',
    } <= called
    for name in defined:
        lower = name.lower()
        for forbidden in ('reserve', 'commit', 'allocat', 'finalize'):
            assert forbidden not in lower, f'forbidden substring {forbidden} in {name}'
    assert set(FAKE_ACTIVITIES).isdisjoint(G_ACTIVITIES)
    assert set(VIDEO_ACTIVITIES) - set(FAKE_ACTIVITIES) == {'ReserveVariant', 'CommitVideoCompletion'}
    assert sum(EXPECTED_ACTIVITIES.values()) == 26


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: PW-VERT-01, CT-WF-004, CT-WF-007, CT-ORC-010' in (__doc__ or '')