"""G-07: chính sách allocation theo target, 1–3 job mỗi lượt và reservation (CT-ORC-002; INV-013, INV-018).

coveredIds: CT-ORC-002, INV-013, INV-018
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from controlplane.domain.statemachine import JobState

MAX_JOBS_PER_ROUND = 3


class ReservationAction(StrEnum):
    HOLD = 'HOLD'
    RELEASE = 'RELEASE'
    CONVERT = 'CONVERT'
    NONE = 'NONE'


@dataclass(frozen=True)
class AllocationCandidate:
    candidate_ref: str
    angle_slot: str


def _require_count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a non-negative integer')
    return value


def can_allocate(target: int, completed_count: int, active_reservations: int) -> bool:
    t = _require_count('target', target)
    c = _require_count('completed_count', completed_count)
    a = _require_count('active_reservations', active_reservations)
    return c + a < t


def plan_round(candidates: Sequence[AllocationCandidate], slots_left: int) -> tuple[AllocationCandidate, ...]:
    slots = _require_count('slots_left', slots_left)
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        raise ValueError('candidates must be a sequence')
    if not 1 <= len(candidates) <= MAX_JOBS_PER_ROUND:
        raise ValueError('a round must request 1-3 jobs')
    seen: set[str] = set()
    for c in candidates:
        if not isinstance(c, AllocationCandidate) or not isinstance(c.angle_slot, str) or not c.angle_slot.strip():
            raise ValueError('invalid candidate')
        key = c.angle_slot.strip()
        if key in seen:
            raise ValueError('duplicate angle_slot')
        seen.add(key)
    return tuple(candidates[:slots])


def reservation_action(job_state: JobState | str) -> ReservationAction:
    if isinstance(job_state, bool) or not isinstance(job_state, str):
        raise ValueError('job_state must be a string')
    try:
        state = JobState(job_state)
    except ValueError as exc:
        raise ValueError(f'unknown job state: {job_state!r}') from exc
    if state is JobState.WAITING:
        return ReservationAction.HOLD
    if state is JobState.FAILED_FINAL:
        return ReservationAction.RELEASE
    if state is JobState.COMPLETED:
        return ReservationAction.CONVERT
    return ReservationAction.NONE


__all__ = [
    'MAX_JOBS_PER_ROUND', 'AllocationCandidate', 'ReservationAction',
    'can_allocate', 'plan_round', 'reservation_action',
]