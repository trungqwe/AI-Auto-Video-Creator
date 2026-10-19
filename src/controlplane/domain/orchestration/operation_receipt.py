"""G-05: chính sách retry theo operation receipt (CT-WF-005, CT-STATE-011)."""
from __future__ import annotations

from enum import StrEnum

from controlplane.domain.statemachine import (
    ForbiddenTransitionError,
    OperationState,
    ReconciliationEvidence,
    TransitionResult,
    transition_operation,
)


class RetryDecision(StrEnum):
    EXECUTE = 'EXECUTE'
    NEW_OPERATION_KEY_REQUIRED = 'NEW_OPERATION_KEY_REQUIRED'
    RETURN_PREVIOUS_OUTPUT = 'RETURN_PREVIOUS_OUTPUT'
    RECONCILE_FIRST = 'RECONCILE_FIRST'
    NEW_ATTEMPT_SAME_KEY = 'NEW_ATTEMPT_SAME_KEY'
    FAIL_FINAL = 'FAIL_FINAL'
    WAIT_IN_FLIGHT = 'WAIT_IN_FLIGHT'


def decide_retry(receipt_state: OperationState | None, receipt_fingerprint: str | None, new_fingerprint: str, retryable: bool) -> RetryDecision:
    """Xác định quyết định retry theo CT-WF-005."""
    if receipt_state is None:
        return RetryDecision.EXECUTE
    state = OperationState(receipt_state)
    if receipt_fingerprint != new_fingerprint:
        return RetryDecision.NEW_OPERATION_KEY_REQUIRED
    if state is OperationState.SUCCEEDED:
        return RetryDecision.RETURN_PREVIOUS_OUTPUT
    if state is OperationState.OUTCOME_UNKNOWN:
        return RetryDecision.RECONCILE_FIRST
    if state is OperationState.FAILED:
        return RetryDecision.NEW_ATTEMPT_SAME_KEY if retryable else RetryDecision.FAIL_FINAL
    return RetryDecision.WAIT_IN_FLIGHT


def apply_reconcile(state: OperationState, revision: int, evidence_ref: str | None, outcome: OperationState) -> TransitionResult:
    """Áp dụng đối soát trạng thái theo CT-STATE-011."""
    state = OperationState(state)
    outcome = OperationState(outcome)
    if state is not OperationState.OUTCOME_UNKNOWN or not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise ForbiddenTransitionError(
            aggregate_type='operation',
            current_state=state,
            requested_next_state=outcome,
            current_revision=revision,
        )
    return transition_operation(
        current_state=state,
        current_revision=revision,
        expected_revision=revision,
        requested_state=outcome,
        reconciliation_evidence=ReconciliationEvidence(evidence_ref),
    )


__all__ = ['RetryDecision', 'apply_reconcile', 'decide_retry']
