"""Pure OperationView read model for CT-API-007 (H-01)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from controlplane.application.projections.operation_view_mapper import map_operation_view
from controlplane.domain.statemachine import OperationState

OPERATION_STATUSES: tuple[str, ...] = (
    "accepted",
    "running",
    "waiting",
    "outcome_unknown",
    "succeeded",
    "failed",
)
TERMINAL_STATUSES: tuple[str, ...] = ("succeeded", "failed")
PROBLEM_STATUSES: tuple[str, ...] = ("failed", "outcome_unknown")
PROBLEM_REQUIRED_KEYS: tuple[str, ...] = ("code", "title", "status", "correlation_id")
FORBIDDEN_PROBLEM_KEYS: frozenset[str] = frozenset(
    {"stack_trace", "traceback", "secret_value", "internal_detail"}
)
TRACEBACK_MARKER: str = "Traceback (most recent call last)"


@dataclass(frozen=True)
class OperationViewModel:
    operation_id: str
    command_ref: str
    status: str
    progress: Any
    resource_refs: Any
    started_at: str | None
    updated_at: str | None
    finished_at: str | None
    wait_reason: dict[str, Any] | None
    problem: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "command_ref": self.command_ref,
            "status": self.status,
            "progress": self.progress,
            "resource_refs": self.resource_refs,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "wait_reason": self.wait_reason,
            "problem": self.problem,
        }


def _has_unsafe_content(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and key.lower() in FORBIDDEN_PROBLEM_KEYS)
            or _has_unsafe_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_unsafe_content(item) for item in value)
    if isinstance(value, str):
        return TRACEBACK_MARKER in value
    return False


def build_operation_view(
    *,
    operation_id: str,
    command_ref: str,
    execution_state: OperationState,
    resource_refs: Any,
    started_at: str | None = None,
    updated_at: str | None = None,
    finished_at: str | None = None,
    wait_reason: Any = None,
    progress: Any = None,
    problem: Any = None,
) -> OperationViewModel:
    status = map_operation_view(execution_state=execution_state, wait_reason=wait_reason)

    if status == "waiting":
        if (
            not isinstance(wait_reason, dict)
            or not isinstance(wait_reason.get("code"), str)
            or wait_reason["code"] == ""
        ):
            raise ValueError("invalid_wait_reason")
    elif wait_reason is not None:
        raise ValueError("unexpected_wait_reason")

    if status in TERMINAL_STATUSES:
        if not finished_at:
            raise ValueError("missing_finished_at")
    elif finished_at is not None:
        raise ValueError("unexpected_finished_at")

    if problem is not None:
        if status not in PROBLEM_STATUSES:
            raise ValueError("unexpected_problem")
        if _has_unsafe_content(problem):
            raise ValueError("unsafe_problem")
        if not isinstance(problem, dict) or any(k not in problem for k in PROBLEM_REQUIRED_KEYS):
            raise ValueError("invalid_problem")

    return OperationViewModel(
        operation_id=operation_id,
        command_ref=command_ref,
        status=status,
        progress=progress,
        resource_refs=resource_refs,
        started_at=started_at,
        updated_at=updated_at,
        finished_at=finished_at,
        wait_reason=wait_reason,
        problem=problem,
    )
