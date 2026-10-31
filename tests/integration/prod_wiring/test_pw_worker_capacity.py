"""ADAPT-PROD-FIX4: trần tài nguyên cho tối đa 10 luồng video (pool DB, executor, trần activity theo queue)."""
from __future__ import annotations

import inspect
import threading
import time
from types import SimpleNamespace

import pytest
from psycopg_pool import PoolTimeout

from controlplane.infrastructure import capacity
from controlplane.infrastructure.db.uow import TransactionManager

STREAMS = capacity.MAX_VIDEO_STREAMS


def run_threads(count, target):
    errors = []

    def runner():
        try:
            target()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=runner) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads)
    return errors


def test_capacity_constants():
    assert capacity.MAX_VIDEO_STREAMS == 10
    assert capacity.DB_POOL_MAX_SIZE == 36
    assert capacity.ACTIVITY_THREADS == 48
    assert dict(capacity.ACTIVITY_QUEUE_CAPS) == {'cloud-io': 16, 'cloud-ai': 8}
    assert capacity.ACTIVITY_THREADS >= capacity.MAX_VIDEO_STREAMS + sum(capacity.ACTIVITY_QUEUE_CAPS.values()) + 14
    with pytest.raises(TypeError):
        capacity.ACTIVITY_QUEUE_CAPS['cloud-io'] = 1


def test_ten_streams_borrow_a_second_connection_on_the_capacity_pool(pw_database):
    manager = TransactionManager(pw_database.dsn, pool_max_size=capacity.DB_POOL_MAX_SIZE)
    barrier = threading.Barrier(STREAMS, timeout=10)

    def stream():
        with manager.unit_of_work() as uow:
            uow.connection.execute('SELECT 1').fetchone()
            barrier.wait()
            with manager.borrow_connection() as borrowed:
                borrowed.execute('SELECT 1').fetchone()

    try:
        started = time.monotonic()
        errors = run_threads(STREAMS, stream)
        elapsed = time.monotonic() - started
    finally:
        manager.close()
    assert errors == []
    assert elapsed < 10


def test_four_streams_on_a_pool_of_four_hit_pool_timeout(pw_database):
    manager = TransactionManager(pw_database.dsn, pool_max_size=4, pool_timeout=1.0)
    barrier = threading.Barrier(4, timeout=10)

    def stream():
        with manager.unit_of_work() as uow:
            uow.connection.execute('SELECT 1').fetchone()
            barrier.wait()
            with manager.borrow_connection() as borrowed:
                borrowed.execute('SELECT 1').fetchone()

    try:
        errors = run_threads(4, stream)
    finally:
        manager.close()
    assert errors
    assert all(isinstance(error, PoolTimeout) for error in errors)


@pytest.mark.parametrize('bad', [0, 0.0, -1, True, False, float('nan'), float('inf')])
def test_pool_timeout_must_be_a_positive_finite_number(pw_database, bad):
    with pytest.raises(ValueError):
        TransactionManager(pw_database.dsn, pool_max_size=4, pool_timeout=bad)


def recording_worker_class(created):
    class RecordingWorker:
        def __init__(self, client, **kwargs):
            self.client = client
            self.kwargs = kwargs
            created.append(self)

    return RecordingWorker


def test_capped_worker_factory_caps_only_cloud_queues():
    from controlplane.api.wiring.production import TemporalWorkerGroup, capped_worker_factory

    created = []
    registration = SimpleNamespace(
        workflows=(),
        activities_by_queue={'cloud-io': (), 'cloud-ai': (), 'desktop-render': (), 'control-workflows': ()},
    )
    client = object()
    TemporalWorkerGroup(client, registration, graceful_shutdown_seconds=30, worker_factory=capped_worker_factory(recording_worker_class(created)))
    by_queue = {worker.kwargs['task_queue']: worker.kwargs for worker in created}
    assert set(by_queue) == {'cloud-io', 'cloud-ai', 'desktop-render', 'control-workflows'}
    assert by_queue['cloud-io']['max_concurrent_activities'] == 16
    assert by_queue['cloud-ai']['max_concurrent_activities'] == 8
    for queue in ('desktop-render', 'control-workflows'):
        assert 'max_concurrent_activities' not in by_queue[queue]
    assert all(worker.client is client for worker in created)


def test_worker_factory_default_is_none():
    from controlplane.api.wiring.production import TemporalWorkerGroup

    assert inspect.signature(TemporalWorkerGroup.__init__).parameters['worker_factory'].default is None
