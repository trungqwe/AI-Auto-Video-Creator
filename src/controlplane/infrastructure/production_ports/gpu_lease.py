"""PP-1: LocalGpuLease, the in-process GpuLeasePort for LOCK-DESKTOP-GPU (CT-RND-004).

Slot capacity and lease lifetime come from the caller (profile gpu.slots, render timeout plus grace); nothing here is a constant. An expired lease is reclaimed on the next acquire so a dead render never holds a slot forever.
The adapter probes no hardware and reads no environment; one instance guards its own table with a threading.Lock.

coveredIds: CT-RND-004
"""
from __future__ import annotations

import math
import threading
import time
import uuid
from collections.abc import Callable

from render.ports.lease import GPU_LOCK_ID, GpuLease, GpuLeaseUnavailable


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


class LocalGpuLease:
    def __init__(
        self, slots: int, ttl_seconds: float, *, lock_id: str = GPU_LOCK_ID, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not _is_positive_int(slots):
            raise ValueError('slots must be a positive int')
        if not _is_positive_number(ttl_seconds):
            raise ValueError('ttl_seconds must be a positive finite number')
        if lock_id != GPU_LOCK_ID:
            raise ValueError(f'lock_id must be {GPU_LOCK_ID}')
        if not callable(clock):
            raise ValueError('clock must be callable')
        self._slots = slots
        self._ttl_seconds = ttl_seconds
        self._lock_id = lock_id
        self._clock = clock
        self._guard = threading.Lock()
        self._expires_at: dict[str, float] = {}

    def acquire(self, owner_ref: str) -> GpuLease:
        if not isinstance(owner_ref, str) or not owner_ref.strip():
            raise ValueError('owner_ref must be a non-empty string')
        with self._guard:
            now = self._clock()
            for lease_id in [key for key, expires_at in self._expires_at.items() if expires_at <= now]:
                del self._expires_at[lease_id]
            if len(self._expires_at) >= self._slots:
                raise GpuLeaseUnavailable(f'all {self._slots} slot(s) of {self._lock_id} are in use')
            lease = GpuLease(lease_id=uuid.uuid4().hex, owner_ref=owner_ref, lock_id=self._lock_id)
            self._expires_at[lease.lease_id] = now + self._ttl_seconds
            return lease

    def release(self, lease: GpuLease) -> None:
        with self._guard:
            self._expires_at.pop(lease.lease_id, None)


__all__ = ['LocalGpuLease']
