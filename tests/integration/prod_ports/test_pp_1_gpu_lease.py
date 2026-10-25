"""PP-1: LocalGpuLease behaviour with an injected clock."""
from __future__ import annotations

import pathlib
import threading

import pytest

import controlplane.infrastructure.production_ports.gpu_lease as gpu_lease_module
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from render.ports.lease import GPU_LOCK_ID, GpuLease, GpuLeasePort, GpuLeaseUnavailable


class ManualClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make(slots: int = 1, ttl: float = 10.0) -> tuple[LocalGpuLease, ManualClock]:
    clock = ManualClock()
    return LocalGpuLease(slots, ttl, clock=clock), clock


def test_implements_port_and_lease_fields() -> None:
    port, _ = make()
    assert isinstance(port, GpuLeasePort)
    lease = port.acquire('job-1')
    assert isinstance(lease, GpuLease)
    assert lease.owner_ref == 'job-1' and lease.lock_id == GPU_LOCK_ID
    assert len(lease.lease_id) == 32 and int(lease.lease_id, 16) >= 0


def test_one_slot_second_acquire_raises() -> None:
    port, _ = make()
    port.acquire('a')
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('b')


def test_release_then_acquire_succeeds() -> None:
    port, _ = make()
    first = port.acquire('a')
    port.release(first)
    second = port.acquire('b')
    assert second.lease_id != first.lease_id


def test_release_twice_is_noop_and_keeps_new_lease() -> None:
    port, _ = make()
    first = port.acquire('a')
    port.release(first)
    port.release(first)
    port.acquire('b')
    port.release(first)
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('c')


def test_not_reclaimed_before_ttl_and_reclaimed_at_ttl() -> None:
    port, clock = make(ttl=10.0)
    port.acquire('a')
    clock.advance(9.5)
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('b')
    clock.advance(0.5)
    port.acquire('b')


def test_stale_release_does_not_free_new_lease() -> None:
    port, clock = make(ttl=10.0)
    old = port.acquire('a')
    clock.advance(10.0)
    new = port.acquire('b')
    port.release(old)
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('c')
    port.release(new)
    port.acquire('c')


def test_two_slots_grant_exactly_two_unique_leases() -> None:
    port, _ = make(slots=2)
    leases = [port.acquire('a'), port.acquire('b')]
    assert len({lease.lease_id for lease in leases}) == 2
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('c')


def test_slot_count_is_taken_from_constructor() -> None:
    port, _ = make(slots=3)
    for index in range(3):
        port.acquire(f'job-{index}')
    with pytest.raises(GpuLeaseUnavailable):
        port.acquire('job-3')

def test_eight_threads_one_slot_single_winner() -> None:
    port, _ = make()
    barrier = threading.Barrier(8)
    outcomes: list[str] = []

    def contend(index: int) -> None:
        barrier.wait(timeout=10)
        try:
            port.acquire(f'job-{index}')
        except GpuLeaseUnavailable:
            outcomes.append('unavailable')
        else:
            outcomes.append('won')

    threads = [threading.Thread(target=contend, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ['unavailable'] * 7 + ['won']


@pytest.mark.parametrize('slots', [0, -1, True, False, 1.5, '1', None])
def test_constructor_rejects_bad_slots(slots: object) -> None:
    with pytest.raises(ValueError):
        LocalGpuLease(slots, 10.0)  # type: ignore[arg-type]


@pytest.mark.parametrize('ttl', [0, -1, 0.0, float('nan'), float('inf'), True, '5', None])
def test_constructor_rejects_bad_ttl(ttl: object) -> None:
    with pytest.raises(ValueError):
        LocalGpuLease(1, ttl)  # type: ignore[arg-type]


def test_constructor_rejects_other_lock_id() -> None:
    with pytest.raises(ValueError):
        LocalGpuLease(1, 10.0, lock_id='LOCK-OTHER')


@pytest.mark.parametrize('owner_ref', ['', '   ', None, 7])
def test_acquire_rejects_bad_owner_ref(owner_ref: object) -> None:
    port, _ = make()
    with pytest.raises(ValueError):
        port.acquire(owner_ref)  # type: ignore[arg-type]
    port.acquire('ok')


def test_source_has_no_hardware_probe_environment_or_branches() -> None:
    text = pathlib.Path(gpu_lease_module.__file__).read_text(encoding='utf-8').lower()
    for banned in ('nvidia', 'os.environ', 'getenv', 'subprocess', 'from src.', 'mock', 'fake'):
        assert banned not in text
