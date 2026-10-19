"""G-07: JobAllocationService cấp suất job nguyên tử qua AllocationStorePort (CT-ORC-002; INV-018).

coveredIds: CT-ORC-002, INV-018
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from controlplane.domain.orchestration.allocation_policy import AllocationCandidate, can_allocate


class BatchTargetReachedError(Exception):
    def __init__(self, batch_id: str) -> None:
        super().__init__(f'BATCH_TARGET_REACHED: {batch_id}')
        self.batch_id = batch_id


@dataclass(frozen=True)
class JobReservation:
    batch_id: str
    job_id: str
    reservation_id: str
    angle_slot: str


class AllocationStorePort(Protocol):
    def lock_batch(self, batch_id: str) -> AbstractContextManager[int]: ...  # yield target_completed_videos; thoát bình thường = commit, có exception = rollback toàn khối
    def count_ledger(self, batch_id: str) -> int: ...
    def count_active(self, batch_id: str) -> int: ...
    def find_reservation(self, job_id: str) -> JobReservation | None: ...
    def create_job_and_reservation(self, batch_id: str, job_id: str, candidate: AllocationCandidate) -> JobReservation: ...


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


class JobAllocationService:
    def __init__(self, store: AllocationStorePort) -> None:
        self._store = store

    def allocate(self, batch_id: str, job_id: str, candidate: AllocationCandidate) -> JobReservation:
        _require_text('batch_id', batch_id)
        _require_text('job_id', job_id)
        if not isinstance(candidate, AllocationCandidate):
            raise ValueError('candidate must be an AllocationCandidate')
        with self._store.lock_batch(batch_id) as target:
            existing = self._store.find_reservation(job_id)
            if existing is not None:
                if existing.batch_id != batch_id:
                    raise ValueError(f'job_id {job_id} already belongs to another batch')
                return existing
            completed = self._store.count_ledger(batch_id)
            active = self._store.count_active(batch_id)
            if not can_allocate(target, completed, active):
                raise BatchTargetReachedError(batch_id)
            return self._store.create_job_and_reservation(batch_id, job_id, candidate)


__all__ = ['AllocationStorePort', 'BatchTargetReachedError', 'JobAllocationService', 'JobReservation']