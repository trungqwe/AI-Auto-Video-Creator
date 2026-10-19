"""G-14: lý do dừng batch (CT-ORC-010; TST-E2E-006, TST-E2E-007).

Pure domain: không I/O, không đồng hồ.
"""
from __future__ import annotations

from enum import StrEnum

from controlplane.domain.statemachine import BatchState, ForbiddenTransitionError, TransitionResult, transition_batch


class BatchOutcome(StrEnum):
    COMPLETED_TARGET = 'COMPLETED_TARGET'
    COMPLETED_EXHAUSTED = 'COMPLETED_EXHAUSTED'
    WAITING_CAPABILITY = 'WAITING_CAPABILITY'
    FAILED_SYSTEM = 'FAILED_SYSTEM'
    CONTINUE = 'CONTINUE'


def _require_count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a non-negative integer')
    return value


def decide_batch_outcome(
    ledger_count: int,
    target: int,
    active_reservations: int,
    eligible_remaining: int,
    capability_blocked_work: int,
    system_fault: bool,
) -> BatchOutcome:
    """Ledger là nguồn đếm; reservation ACTIVE (kể cả job WAITING giữ suất) chặn EXHAUSTED; job FAILED_FINAL riêng lẻ không phải đầu vào nên không bao giờ gây FAILED_SYSTEM."""
    _require_count('ledger_count', ledger_count)
    _require_count('target', target)
    _require_count('active_reservations', active_reservations)
    _require_count('eligible_remaining', eligible_remaining)
    _require_count('capability_blocked_work', capability_blocked_work)
    if not isinstance(system_fault, bool):
        raise TypeError('system_fault must be bool')

    if system_fault:
        return BatchOutcome.FAILED_SYSTEM
    if ledger_count >= target:
        return BatchOutcome.COMPLETED_TARGET
    if capability_blocked_work > 0:
        return BatchOutcome.CONTINUE if eligible_remaining > 0 else BatchOutcome.WAITING_CAPABILITY
    if eligible_remaining > 0 or active_reservations > 0:
        return BatchOutcome.CONTINUE
    return BatchOutcome.COMPLETED_EXHAUSTED


def plan_batch_transition(
    *,
    current_state: BatchState,
    current_revision: int,
    expected_revision: int,
    outcome: BatchOutcome,
) -> TransitionResult | None:
    if not isinstance(outcome, BatchOutcome):
        raise TypeError('outcome must be BatchOutcome')

    if outcome == BatchOutcome.CONTINUE:
        requested = BatchState.RUNNING
    elif outcome == BatchOutcome.COMPLETED_TARGET:
        requested = BatchState.COMPLETED_TARGET
    elif outcome == BatchOutcome.COMPLETED_EXHAUSTED:
        requested = BatchState.COMPLETED_EXHAUSTED
    elif outcome == BatchOutcome.WAITING_CAPABILITY:
        requested = BatchState.WAITING_CAPABILITY
    elif outcome == BatchOutcome.FAILED_SYSTEM:
        requested = BatchState.FAILED_SYSTEM
    else:
        raise TypeError(f'Unknown outcome: {outcome}')

    if current_state not in (BatchState.RUNNING, BatchState.WAITING_CAPABILITY):
        raise ForbiddenTransitionError(
            aggregate_type='batch',
            current_state=current_state,
            requested_next_state=requested,
            current_revision=current_revision,
        )

    if current_state == requested:
        return None

    return transition_batch(
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested,
    )


__all__ = ['BatchOutcome', 'decide_batch_outcome', 'plan_batch_transition']
