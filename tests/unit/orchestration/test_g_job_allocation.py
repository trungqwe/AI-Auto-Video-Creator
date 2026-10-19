"""G-07: JobAllocationService qua AllocationStorePort với fake có khóa luồng (CT-ORC-002; INV-018, TST-WF-INV-018 mức logic).

coveredIds: CT-ORC-002, INV-018
"""
from __future__ import annotations

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from controlplane.application.orchestration.job_allocation import (
    BatchTargetReachedError,
    JobAllocationService,
    JobReservation,
)
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate

THREADS = 8


class FakeStore:
    def __init__(self, targets, ledger=None):
        self._targets = dict(targets)
        self._ledger = dict(ledger or {})
        self._locks = {batch_id: threading.Lock() for batch_id in targets}
        self._seq = itertools.count(1)
        self.jobs = {}  # job_id -> batch_id
        self.reservations = {}  # job_id -> JobReservation
        self.create_calls = []
        self.events = []
        self.fail_after_job = False
        self.files_on_disk = 0  # nhiễu: số tệp không được dùng làm completed

    def seed_active(self, batch_id, count):
        for i in range(count):
            job_id = f'seed-{batch_id}-{i}'
            self.jobs[job_id] = batch_id
            self.reservations[job_id] = JobReservation(batch_id, job_id, f'seed-res-{batch_id}-{i}', 'angle-seed')

    @contextmanager
    def lock_batch(self, batch_id):
        with self._locks[batch_id]:
            snapshot = (dict(self.jobs), dict(self.reservations))
            self.events.append('lock')
            try:
                yield self._targets[batch_id]
            except BaseException:
                self.jobs, self.reservations = snapshot
                self.events.append('rollback')
                raise
            self.events.append('commit')

    def count_ledger(self, batch_id):
        self.events.append('count_ledger')
        return self._ledger.get(batch_id, 0)

    def count_active(self, batch_id):
        self.events.append('count_active')
        count = sum(1 for r in self.reservations.values() if r.batch_id == batch_id)
        time.sleep(0.001)  # mở rộng cửa sổ race nếu service không giữ khóa
        return count

    def find_reservation(self, job_id):
        self.events.append('find')
        return self.reservations.get(job_id)

    def create_job_and_reservation(self, batch_id, job_id, candidate):
        self.events.append('create')
        self.create_calls.append(job_id)
        self.jobs[job_id] = batch_id
        if self.fail_after_job:
            raise RuntimeError('boom after job insert')
        reservation = JobReservation(batch_id, job_id, f'res-{next(self._seq)}', candidate.angle_slot)
        self.reservations[job_id] = reservation
        return reservation


def cand(job_id):
    return AllocationCandidate(f'cand-{job_id}', 'angle-1')


def make(targets, ledger=None):
    store = FakeStore(targets, ledger)
    return store, JobAllocationService(store)


def test_allocate_creates_job_and_reservation_inside_lock():
    store, service = make({'b1': 3}, {'b1': 1})
    result = service.allocate('b1', 'job-1', cand('job-1'))
    assert result == JobReservation('b1', 'job-1', 'res-1', 'angle-1')
    assert store.jobs == {'job-1': 'b1'} and store.reservations == {'job-1': result}
    assert store.events == ['lock', 'find', 'count_ledger', 'count_active', 'create', 'commit']


def test_allocate_counts_ledger_not_files():
    store, service = make({'b1': 2}, {'b1': 0})
    store.files_on_disk = 99
    assert service.allocate('b1', 'job-1', cand('job-1')).job_id == 'job-1'
    store, service = make({'b1': 2}, {'b1': 2})
    store.files_on_disk = 0
    with pytest.raises(BatchTargetReachedError):
        service.allocate('b1', 'job-1', cand('job-1'))


@pytest.mark.parametrize(('target', 'ledger', 'seeded', 'blocked'), [
    (3, 1, 2, True), (3, 3, 0, True), (3, 0, 3, True), (3, 1, 1, False), (1, 0, 0, False),
])
def test_allocate_respects_target(target, ledger, seeded, blocked):
    store, service = make({'b1': target}, {'b1': ledger})
    store.seed_active('b1', seeded)
    if blocked:
        with pytest.raises(BatchTargetReachedError) as info:
            service.allocate('b1', 'job-new', cand('job-new'))
        assert info.value.batch_id == 'b1'
        assert store.create_calls == [] and 'job-new' not in store.jobs
    else:
        service.allocate('b1', 'job-new', cand('job-new'))
        assert len(store.reservations) == seeded + 1


def test_retry_same_job_id_returns_old_reservation_without_new_slot():
    store, service = make({'b1': 3}, {'b1': 0})
    first = service.allocate('b1', 'job-1', cand('job-1'))
    second = service.allocate('b1', 'job-1', cand('job-1'))
    assert second == first and store.create_calls == ['job-1'] and len(store.reservations) == 1
    assert store.events[-3:] == ['lock', 'find', 'commit']


def test_retry_at_full_capacity_returns_old_reservation_but_new_job_is_blocked():
    store, service = make({'b1': 1}, {'b1': 0})
    first = service.allocate('b1', 'job-1', cand('job-1'))
    assert service.allocate('b1', 'job-1', cand('job-1')) == first
    with pytest.raises(BatchTargetReachedError):
        service.allocate('b1', 'job-2', cand('job-2'))


def test_job_id_owned_by_other_batch_raises_value_error():
    store, service = make({'b1': 3, 'b2': 3})
    service.allocate('b1', 'job-1', cand('job-1'))
    with pytest.raises(ValueError):
        service.allocate('b2', 'job-1', cand('job-1'))
    assert store.create_calls == ['job-1'] and len(store.reservations) == 1


@pytest.mark.parametrize(('batch_id', 'job_id', 'candidate'), [
    ('', 'job-1', cand('job-1')), ('b1', '', cand('job-1')), ('b1', 'job-1', {'angle_slot': 'a'}), (None, 'job-1', cand('job-1')),
])
def test_invalid_arguments_raise_value_error_before_locking(batch_id, job_id, candidate):
    store, service = make({'b1': 3})
    with pytest.raises(ValueError):
        service.allocate(batch_id, job_id, candidate)
    assert store.events == []


def test_mid_failure_after_job_insert_leaves_no_orphan_job():
    store, service = make({'b1': 3}, {'b1': 0})
    store.fail_after_job = True
    with pytest.raises(RuntimeError):
        service.allocate('b1', 'job-1', cand('job-1'))
    assert store.jobs == {} and store.reservations == {}
    assert store.events[-1] == 'rollback'
    store.fail_after_job = False
    assert service.allocate('b1', 'job-1', cand('job-1')).job_id == 'job-1'
    assert list(store.jobs) == ['job-1'] and list(store.reservations) == ['job-1']


def test_failed_allocation_does_not_consume_last_slot():
    store, service = make({'b1': 1}, {'b1': 0})
    store.fail_after_job = True
    with pytest.raises(RuntimeError):
        service.allocate('b1', 'job-1', cand('job-1'))
    store.fail_after_job = False
    assert service.allocate('b1', 'job-2', cand('job-2')).job_id == 'job-2'
    assert store.jobs == {'job-2': 'b1'}


def _race(service, batch_id, job_ids):
    barrier = threading.Barrier(len(job_ids), timeout=10)

    def worker(job_id):
        barrier.wait()
        try:
            return service.allocate(batch_id, job_id, cand(job_id))
        except BatchTargetReachedError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=len(job_ids)) as pool:
        return list(pool.map(worker, job_ids))


@pytest.mark.parametrize('round_no', range(5))
def test_eight_threads_race_for_last_slot_single_winner(round_no):
    store, service = make({'b1': 5}, {'b1': 2})
    store.seed_active('b1', 2)
    results = _race(service, 'b1', [f'job-{i}' for i in range(THREADS)])
    winners = [r for r in results if isinstance(r, JobReservation)]
    losers = [r for r in results if isinstance(r, BatchTargetReachedError)]
    assert len(winners) == 1 and len(losers) == THREADS - 1
    assert len(store.reservations) == 2 + 1 and len(store.create_calls) == 1
    assert 2 + len(store.reservations) <= 5


def test_eight_threads_with_six_slots_grant_exactly_six():
    store, service = make({'b1': 6}, {'b1': 0})
    results = _race(service, 'b1', [f'job-{i}' for i in range(THREADS)])
    assert sum(isinstance(r, JobReservation) for r in results) == 6
    assert sum(isinstance(r, BatchTargetReachedError) for r in results) == 2
    assert len(store.reservations) == 6


def test_eight_threads_retrying_same_job_id_share_one_reservation():
    store, service = make({'b1': 1}, {'b1': 0})
    results = _race(service, 'b1', ['job-1'] * THREADS)
    assert all(isinstance(r, JobReservation) for r in results)
    assert len({r.reservation_id for r in results}) == 1
    assert store.create_calls == ['job-1'] and len(store.reservations) == 1