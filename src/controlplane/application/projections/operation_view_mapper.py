"""Pure mapping from an Operation execution state to its read-model view."""

from controlplane.domain.statemachine import OperationState


def map_operation_view(*, execution_state: OperationState, wait_reason: object | None = None) -> str:
    if execution_state is OperationState.STARTED and wait_reason is not None:
        return "waiting"
    return {
        OperationState.PREPARED: "accepted",
        OperationState.STARTED: "running",
        OperationState.SUCCEEDED: "succeeded",
        OperationState.FAILED: "failed",
        OperationState.OUTCOME_UNKNOWN: "outcome_unknown",
    }[execution_state]
