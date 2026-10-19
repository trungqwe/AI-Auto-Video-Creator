"""G-07: bảng case chính sách allocation (CT-ORC-002; INV-013, INV-018).

coveredIds: CT-ORC-002, INV-013, INV-018
"""
from __future__ import annotations

import inspect

import pytest

from controlplane.domain.orchestration.allocation_policy import (
    MAX_JOBS_PER_ROUND,
    AllocationCandidate,
    ReservationAction,
    can_allocate,
    plan_round,
    reservation_action,
)
from controlplane.domain.statemachine import JobState

CAN_ALLOCATE_CASES = [
    (5, 0, 0, True), (5, 2, 2, True), (5, 4, 0, True), (5, 0, 4, True), (1, 0, 0, True),
    (5, 2, 3, False), (5, 5, 0, False), (5, 0, 5, False), (1, 0, 1, False), (1, 1, 0, False),
    (3, 2, 2, False), (0, 0, 0, False),
]
INVALID_COUNTS = [(-1, 0, 0), (5, -1, 0), (5, 0, -1), (True, 0, 0), (5, True, 0), (5, 0, True), (5, 1.5, 0), ('5', 0, 0), (5, None, 0)]


@pytest.mark.parametrize(('target', 'completed', 'active', 'expected'), CAN_ALLOCATE_CASES)
def test_can_allocate_table(target, completed, active, expected):
    assert can_allocate(target, completed, active) is expected


@pytest.mark.parametrize(('target', 'completed', 'active'), INVALID_COUNTS)
def test_can_allocate_rejects_invalid_counts(target, completed, active):
    with pytest.raises(ValueError):
        can_allocate(target, completed, active)


def test_can_allocate_takes_ledger_count_not_files():
    assert list(inspect.signature(can_allocate).parameters) == ['target', 'completed_count', 'active_reservations']


def _cands(*slots):
    return [AllocationCandidate(f'cand-{i}', slot) for i, slot in enumerate(slots)]


def test_max_jobs_per_round_is_three():
    assert MAX_JOBS_PER_ROUND == 3


@pytest.mark.parametrize('count', [1, 2, 3])
def test_plan_round_grants_one_to_three_distinct_angles(count):
    candidates = _cands(*['a', 'b', 'c'][:count])
    planned = plan_round(candidates, 3)
    assert planned == tuple(candidates)
    assert len({c.angle_slot for c in planned}) == count


@pytest.mark.parametrize(('slots_left', 'granted'), [(3, 3), (2, 2), (1, 1), (0, 0)])
def test_plan_round_is_capped_by_slots_left(slots_left, granted):
    candidates = _cands('a', 'b', 'c')
    assert plan_round(candidates, slots_left) == tuple(candidates[:granted])


def test_plan_round_accepts_tuple_input():
    assert len(plan_round(tuple(_cands('a', 'b')), 5)) == 2


@pytest.mark.parametrize('slots', [(), ('a', 'b', 'c', 'd'), ('a', 'a'), ('a', 'b', 'a'), ('a', ' a ')])
def test_plan_round_rejects_bad_requests(slots):
    with pytest.raises(ValueError):
        plan_round(_cands(*slots), 3)


@pytest.mark.parametrize('slots', [('a', 'a'), ('a', 'b', 'c', 'd')])
def test_plan_round_validates_before_truncating_by_slots_left(slots):
    with pytest.raises(ValueError):
        plan_round(_cands(*slots), 1)


@pytest.mark.parametrize('slots_left', [-1, True, 1.5, None, '2'])
def test_plan_round_rejects_invalid_slots_left(slots_left):
    with pytest.raises(ValueError):
        plan_round(_cands('a'), slots_left)


@pytest.mark.parametrize('candidates', [None, 'abc', [{'angle_slot': 'a'}], _cands(''), _cands('   '), [AllocationCandidate('c', None)]])
def test_plan_round_rejects_invalid_candidates(candidates):
    with pytest.raises(ValueError):
        plan_round(candidates, 3)


R = ReservationAction
EXPECTED_ACTIONS = {
    JobState.WAITING: R.HOLD,
    JobState.FAILED_FINAL: R.RELEASE,
    JobState.COMPLETED: R.CONVERT,
    JobState.CREATED: R.NONE,
    JobState.SNAPSHOTTED: R.NONE,
    JobState.ACTIVE: R.NONE,
    JobState.READY_FOR_COMPLETION: R.NONE,
}


def test_expected_actions_cover_every_job_state():
    assert set(EXPECTED_ACTIONS) == set(JobState)


@pytest.mark.parametrize(('state', 'expected'), list(EXPECTED_ACTIONS.items()))
def test_reservation_action_table(state, expected):
    assert reservation_action(state) is expected


def test_reservation_action_accepts_plain_string():
    assert reservation_action('WAITING') is R.HOLD


def test_waiting_holds_slot_and_retry_does_not_create_reservation():
    assert reservation_action(JobState.WAITING) is R.HOLD
    assert reservation_action(JobState.ACTIVE) is R.NONE


def test_failed_final_releases_slot():
    assert reservation_action(JobState.FAILED_FINAL) is R.RELEASE


@pytest.mark.parametrize('state', ['BOGUS', '', None, 1, True])
def test_reservation_action_rejects_unknown_state(state):
    with pytest.raises(ValueError):
        reservation_action(state)