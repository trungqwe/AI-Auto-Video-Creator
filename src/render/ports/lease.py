"""F-18: GpuLeasePort, the F-side view of LOCK-DESKTOP-GPU (CT-RND-004); pure, no I/O, no clock.

LeaseManager and G own the slots and their capacity (configuration, never a constant here). F only acquires one slot through this port and returns it when the work is done or has failed.
F waits for a slot only inside the adapter, within a bounded limit (gpu_lease.wait_seconds); the port itself never sleeps. The LeaseManager adapter waits for CONV-F-02; tests use a fake.

coveredIds: CT-RND-004
"""
from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable

GPU_LOCK_ID = 'LOCK-DESKTOP-GPU'


class GpuLeaseUnavailable(Exception):
    """No slot is free: nothing was rendered. F waits only inside the adapter, within its bounded wait limit."""


class GpuLeaseWaitExpired(GpuLeaseUnavailable):
    """No slot became free within the wait limit of the adapter: nothing was rendered."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class GpuLease:
    lease_id: str
    owner_ref: str
    lock_id: str = GPU_LOCK_ID


@runtime_checkable
class GpuLeasePort(Protocol):
    def acquire(self, owner_ref: str) -> GpuLease:
        """Take one LOCK-DESKTOP-GPU slot for owner_ref; raise GpuLeaseUnavailable when none is free (GpuLeaseWaitExpired when the adapter waited its whole limit)."""
        ...

    def release(self, lease: GpuLease) -> None:
        """Return the slot; releasing a lease twice is a no-op."""
        ...


__all__ = ['GPU_LOCK_ID', 'GpuLease', 'GpuLeasePort', 'GpuLeaseUnavailable', 'GpuLeaseWaitExpired']
