"""PP-1: LocalGpuLease, the in-process GpuLeasePort for LOCK-DESKTOP-GPU (CT-RND-004).

Slot capacity, lease lifetime and the wait limit come from the caller (profile gpu.slots, render timeout plus grace, ports gpu_lease.wait_seconds); nothing here is a constant. An expired lease is reclaimed on the next acquire so a dead render never holds a slot forever.
acquire never waits (the gpu_lease_ready probe uses it). acquire_waiting waits on a threading.Condition for at most wait_seconds and raises GpuLeaseWaitExpired when no slot came free; release wakes the waiters. waiting_port() is the one GpuLeasePort that F uses.
The adapter probes no hardware and reads no environment; one instance guards its own table with the Condition.

coveredIds: CT-RND-004
"""
from __future__ import annotations

import math
import threading
import time
import uuid
from collections.abc import Callable

from render.ports.lease import GPU_LOCK_ID, GpuLease, GpuLeasePort, GpuLeaseUnavailable, GpuLeaseWaitExpired


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _is_non_negative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _require_owner_ref(owner_ref: object) -> None:
    if not isinstance(owner_ref, str) or not owner_ref.strip():
        raise ValueError('owner_ref must be a non-empty string')


class LocalGpuLease:
    def __init__(
        self, slots: int, ttl_seconds: float, *, wait_seconds: float = 0, lock_id: str = GPU_LOCK_ID,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not _is_positive_int(slots):
            raise ValueError('slots must be a positive int')
        if not _is_positive_number(ttl_seconds):
            raise ValueError('ttl_seconds must be a positive finite number')
        if not _is_non_negative_number(wait_seconds):
            raise ValueError('wait_seconds must be a finite number >= 0')
        if lock_id != GPU_LOCK_ID:
            raise ValueError(f'lock_id must be {GPU_LOCK_ID}')
        if not callable(clock):
            raise ValueError('clock must be callable')
        self._slots = slots
        self._ttl_seconds = ttl_seconds
        self._wait_seconds = wait_seconds
        self._lock_id = lock_id
        self._clock = clock
        self._cond = threading.Condition()
        self._expires_at: dict[str, float] = {}
        self._waiting_port = _WaitingPort(self)

    def _reclaim_expired(self, now: float) -> None:
        for lease_id in [key for key, expires_at in self._expires_at.items() if expires_at <= now]:
            del self._expires_at[lease_id]

    def _grant(self, owner_ref: str, now: float) -> GpuLease:
        lease = GpuLease(lease_id=uuid.uuid4().hex, owner_ref=owner_ref, lock_id=self._lock_id)
        self._expires_at[lease.lease_id] = now + self._ttl_seconds
        return lease

    def acquire(self, owner_ref: str) -> GpuLease:
        _require_owner_ref(owner_ref)
        with self._cond:
            now = self._clock()
            self._reclaim_expired(now)
            if len(self._expires_at) >= self._slots:
                raise GpuLeaseUnavailable(f'all {self._slots} slot(s) of {self._lock_id} are in use')
            return self._grant(owner_ref, now)

    def acquire_waiting(self, owner_ref: str) -> GpuLease:
        if self._wait_seconds == 0:
            return self.acquire(owner_ref)
        _require_owner_ref(owner_ref)
        with self._cond:
            deadline = self._clock() + self._wait_seconds
            while True:
                now = self._clock()
                self._reclaim_expired(now)
                if len(self._expires_at) < self._slots:
                    return self._grant(owner_ref, now)
                remaining = deadline - now
                if remaining <= 0:
                    raise GpuLeaseWaitExpired(f'no slot of {self._lock_id} came free within {self._wait_seconds} s')
                self._cond.wait(min(remaining, min(self._expires_at.values()) - now))

    def release(self, lease: GpuLease) -> None:
        with self._cond:
            self._expires_at.pop(lease.lease_id, None)
            self._cond.notify_all()

    def waiting_port(self) -> GpuLeasePort:
        return self._waiting_port


class _WaitingPort:
    def __init__(self, lease: LocalGpuLease) -> None:
        self._lease = lease

    def acquire(self, owner_ref: str) -> GpuLease:
        return self._lease.acquire_waiting(owner_ref)

    def release(self, lease: GpuLease) -> None:
        self._lease.release(lease)


__all__ = ['LocalGpuLease']
