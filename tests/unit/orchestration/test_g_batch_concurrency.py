"""PW-G5-FIX1: lô chạy tối đa K video con cùng lúc (không DB, gateway giả asyncio).

coveredIds: PW-G5-FIX1-01
"""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

from controlplane.application.orchestration.workflows.batch import BatchParams, ProductionBatchFlow
from controlplane.application.orchestration.workflows.flow import STATUS_COMPLETED, STATUS_FAILED
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.workflow_catalog import get_workflow

PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
BASE = {'batch_id': 'batch-1', 'settings': SETTINGS.to_payload(), 'worker_lease_id': 'lease-1'}


class FakeHandle:
    def __init__(self, child_id):
        self.child_id = child_id
        self.future = asyncio.get_running_loop().create_future()
        self.cancel_called = False

    def done(self):
        return self.future.done()

    def result(self):
        return self.future.result()

    def cancel(self):
        self.cancel_called = True
        return True


class FakeGateway:
    def __init__(self, candidates=(), statuses=None, start_fail=(), alloc_fail_at=None, cancel_on_wait=False):
        self.candidates = list(candidates)
        self.statuses = dict(statuses or {})
        self.start_fail = set(start_fail)
        self.alloc_fail_at = alloc_fail_at
        self.cancel_on_wait = cancel_on_wait
        self.events = []
        self.payloads = []
        self.handles = []
        self.open = {}
        self.peak = 0
        self.inflight = 0
        self.overlap = False
        self.finalize_reasons = []

    def _status(self, child_id):
        return self.statuses.get(int(child_id.rsplit(':', 1)[1]), STATUS_COMPLETED)

    async def issue_grant(self, stage_run_id, allowed_operation, input_fingerprint, worker_lease_id):
        return {'grant_id': 'grant-' + stage_run_id, 'stage_run_id': stage_run_id}

    async def execute(self, activity_name, request):
        refs = {r['ref_type']: r['ref_id'] for r in request['input_refs']}
        if activity_name == 'FinalizeBatch':
            self.events.append(('finalize', len(self.open)))
            self.finalize_reasons.append(refs['batch_stop_reason'])
            return {'disposition': 'succeeded', 'output_refs': []}
        ordinal = int(refs['allocation_job'].rsplit(':', 1)[1])
        self.events.append(('allocate_begin', ordinal))
        self.inflight += 1
        self.overlap = self.overlap or self.inflight > 1
        await asyncio.sleep(0)
        self.inflight -= 1
        self.events.append(('allocate_end', ordinal, len(self.open)))
        if ordinal == self.alloc_fail_at:
            return {'disposition': 'failed', 'problem': {'code': 'ALLOC_BOOM'}}
        if ordinal > len(self.candidates):
            return {'disposition': 'succeeded', 'output_refs': [{'ref_type': 'no_more_jobs', 'ref_id': 'candidates_exhausted'}]}
        return {
            'disposition': 'succeeded',
            'output_refs': [
                {'ref_type': 'allocated_job', 'ref_id': refs['allocation_job']},
                {'ref_type': 'job_candidate', 'ref_id': self.candidates[ordinal - 1]},
            ],
        }

    async def start_child(self, workflow_name, payload):
        child_id = payload['child_id']
        self.events.append(('start', child_id))
        if child_id in self.start_fail:
            raise RuntimeError('start failed')
        handle = FakeHandle(child_id)
        self.handles.append(handle)
        self.payloads.append(dict(payload))
        self.open[child_id] = handle
        self.peak = max(self.peak, len(self.open))
        return handle

    async def wait_first(self, handles):
        self.events.append(('wait_first', len(handles)))
        if self.cancel_on_wait:
            raise asyncio.CancelledError()
        if not any(h.done() for h in handles):
            handle = next(h for h in handles if not h.done())  # con khởi sớm nhất
            status = self._status(handle.child_id)
            if status == 'RAISE':
                handle.future.set_exception(RuntimeError('child failed'))
            else:
                handle.future.set_result({'status': status})
            del self.open[handle.child_id]
            self.events.append(('finish', handle.child_id))

    async def run_child(self, workflow_name, payload):
        child_id = payload['child_id']
        self.events.append(('run_child', child_id))
        self.peak = max(self.peak, 1)
        if workflow_name == 'DebugStageWorkflow':
            return {'status': 'STAGE_OBSERVED'}
        status = self._status(child_id)
        if status == 'RAISE':
            raise RuntimeError('child failed')
        return {'status': status}


def make_flow(gateway, *, target, k=None, jobs=(), variants=None, debug=None):
    payload = {**BASE, 'target_videos': target, 'jobs': list(jobs)}
    if k is not None:
        payload['max_concurrent_videos'] = k
    params = BatchParams.from_payload(payload)
    return ProductionBatchFlow(
        get_workflow('ProductionBatchWorkflow'),
        params,
        gateway,
        [] if variants is None else variants,
        [] if debug is None else debug,
    )


def run(flow):
    return asyncio.run(flow.run())


def kinds(gateway, kind):
    return [e for e in gateway.events if e[0] == kind]


def position(gateway, kind, key):
    for i, event in enumerate(gateway.events):
        if event[0] == kind and event[1] == key:
            return i
    raise AssertionError(f'no event {kind} {key}')


def assert_allocation_is_sequential(gateway):
    assert gateway.overlap is False
    seq = [e[0] for e in gateway.events if e[0] in ('allocate_begin', 'allocate_end', 'start')]
    for i, name in enumerate(seq):
        if name == 'allocate_begin':
            assert seq[i + 1] == 'allocate_end'
        if name == 'allocate_end' and i + 1 < len(seq):
            assert seq[i + 1] == 'start'


def test_params_default_is_one():
    assert BatchParams.from_payload({**BASE, 'target_videos': 1}).max_concurrent_videos == 1
    assert BatchParams.from_payload({**BASE, 'target_videos': 1, 'max_concurrent_videos': 4}).max_concurrent_videos == 4
    assert dataclasses.fields(BatchParams)[-1].name == 'max_concurrent_videos'


@pytest.mark.parametrize('bad', [0, -1, True, False, '4', 1.5, None])
def test_params_reject_invalid_concurrency(bad):
    with pytest.raises(ValueError, match='max_concurrent_videos'):
        BatchParams.from_payload({**BASE, 'target_videos': 1, 'max_concurrent_videos': bad})


@pytest.mark.parametrize('k', [None, 1])
def test_k1_uses_only_run_child(k):
    gateway = FakeGateway(candidates=['a', 'b', 'c'])
    result = run(make_flow(gateway, target=3, k=k))
    assert result['status'] == 'TARGET_REACHED'
    assert result['completed'] == 3
    assert kinds(gateway, 'start') == []
    assert kinds(gateway, 'wait_first') == []
    assert len(kinds(gateway, 'run_child')) == 3
    assert gateway.peak == 1


def test_k4_target10_peak_exactly_4():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(20)])
    result = run(make_flow(gateway, target=10, k=4))
    assert result['status'] == 'TARGET_REACHED'
    assert result['completed'] == 10
    assert result['failed'] == 0
    assert result['allocated'] == 10
    assert result['allocated'] == result['completed'] + result['failed']
    assert gateway.peak == 4
    assert len(kinds(gateway, 'start')) == 10
    assert len(kinds(gateway, 'allocate_begin')) == 10
    assert {c['child_id'] for c in result['children']} == {f'batch-1:video:{i}' for i in range(10)}
    assert result['finalized'] is True
    assert len(kinds(gateway, 'finalize')) == 1
    assert gateway.events[-1][0] == 'finalize'
    assert gateway.events[-1][1] == 0
    assert_allocation_is_sequential(gateway)
    assert all(not h.cancel_called for h in gateway.handles)


def test_failed_child_does_not_stop_the_batch():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(20)], statuses={2: 'FAILED', 5: 'RAISE'})
    result = run(make_flow(gateway, target=10, k=4))
    assert result['status'] == 'TARGET_REACHED'
    assert result['completed'] == 10
    assert result['failed'] == 2
    assert result['allocated'] == 12
    assert {'child_id': 'batch-1:video:2', 'status': 'FAILED'} in result['children']
    assert {'child_id': 'batch-1:video:5', 'status': STATUS_FAILED} in result['children']
    assert len(kinds(gateway, 'finalize')) == 1


def test_two_consecutive_jobs_with_same_candidate_run_together():
    gateway = FakeGateway(candidates=['news-a', 'news-a', 'news-b', 'news-b', 'news-c'])
    result = run(make_flow(gateway, target=4, k=4))
    assert [p['input_refs'][0]['ref_id'] for p in gateway.payloads] == ['news-a', 'news-a', 'news-b', 'news-b']
    assert gateway.peak == 4
    first_wait = position(gateway, 'wait_first', 4)
    assert len([e for e in gateway.events[:first_wait] if e[0] == 'start']) == 4
    assert result['status'] == 'TARGET_REACHED'
    assert result['allocated'] == 4


def test_exhausted_while_children_still_running():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(1, 7)])
    result = run(make_flow(gateway, target=10, k=4))
    assert result['status'] == 'EXHAUSTED'
    assert result['completed'] == 6
    assert result['failed'] == 0
    assert result['allocated'] == 6
    assert len(kinds(gateway, 'allocate_begin')) == 7
    assert kinds(gateway, 'allocate_end')[-1][1] == 7
    assert kinds(gateway, 'allocate_end')[-1][2] >= 1
    finalize_at = position(gateway, 'finalize', 0)
    assert all(i < finalize_at for i, e in enumerate(gateway.events) if e[0] == 'finish')
    assert gateway.finalize_reasons == ['EXHAUSTED: completed=6 failed=0; no_more_jobs: candidates_exhausted']
    assert gateway.events[-1] == ('finalize', 0)


def test_allocation_failed_while_children_running():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(20)], alloc_fail_at=5)
    result = run(make_flow(gateway, target=10, k=4))
    assert result['status'] == 'EXHAUSTED'
    assert result['completed'] == 4
    assert result['allocated'] == 4
    assert len(kinds(gateway, 'allocate_begin')) == 5
    assert kinds(gateway, 'allocate_end')[-1][2] >= 1
    assert gateway.finalize_reasons == ['EXHAUSTED: completed=4 failed=0; allocation_failed: ALLOC_BOOM']
    assert len(kinds(gateway, 'finalize')) == 1
    assert gateway.events[-1][0] == 'finalize'


def test_target_reached_starts_no_surplus_child():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(10)])
    result = run(make_flow(gateway, target=3, k=4))
    assert len(kinds(gateway, 'start')) == 3
    assert len(kinds(gateway, 'allocate_begin')) == 3
    assert gateway.peak == 3
    assert result['completed'] == 3
    assert result['allocated'] == 3
    assert result['status'] == 'TARGET_REACHED'


def test_start_child_failure_does_not_take_a_slot():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(10)], start_fail={'batch-1:video:1'})
    result = run(make_flow(gateway, target=3, k=2))
    assert result['completed'] == 3
    assert result['failed'] == 1
    assert result['allocated'] == 4
    assert {'child_id': 'batch-1:video:1', 'status': STATUS_FAILED} in result['children']
    assert gateway.peak == 2
    first_wait = next(i for i, e in enumerate(gateway.events) if e[0] == 'wait_first')
    assert position(gateway, 'start', 'batch-1:video:2') < first_wait
    assert result['status'] == 'TARGET_REACHED'


def test_static_jobs_and_variant_inbox_with_concurrency():
    variants = [{'job': 'v'}]
    gateway = FakeGateway()
    result = run(make_flow(gateway, target=5, k=3, jobs=[{'job': '1'}, {'job': '2'}, {'job': '3'}], variants=variants))
    assert result['status'] == 'EXHAUSTED'
    assert result['completed'] == 4
    assert result['allocated'] == 0
    assert kinds(gateway, 'allocate_begin') == []
    assert gateway.peak == 3
    assert variants == []
    assert len(kinds(gateway, 'finalize')) == 1
    assert gateway.events[-1][0] == 'finalize'


def test_debug_inbox_runs_sequentially_after_a_wave():
    debug = [{'target_stage': 'plan'}]
    gateway = FakeGateway()
    result = run(make_flow(gateway, target=2, k=2, jobs=[{'job': '1'}, {'job': '2'}], debug=debug))
    assert gateway.peak == 2
    assert debug == []
    assert kinds(gateway, 'run_child') == [('run_child', 'batch-1:debug:0')]
    assert {'child_id': 'batch-1:debug:0', 'status': 'STAGE_OBSERVED'} in result['children']
    debug_at = position(gateway, 'run_child', 'batch-1:debug:0')
    assert debug_at > position(gateway, 'finish', 'batch-1:video:0')
    assert debug_at < position(gateway, 'finalize', 0)


def test_cancel_while_waiting_cancels_every_running_child():
    gateway = FakeGateway(candidates=[f'c{i}' for i in range(5)], cancel_on_wait=True)

    async def scenario():
        try:
            await make_flow(gateway, target=5, k=2).run()
        except asyncio.CancelledError:
            return 'cancelled'
        return 'returned'

    assert asyncio.run(scenario()) == 'cancelled'
    assert len(gateway.handles) == 2
    assert all(h.cancel_called for h in gateway.handles)
    assert kinds(gateway, 'finalize') == []
