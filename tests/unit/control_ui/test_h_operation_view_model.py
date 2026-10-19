"""Kiểm thử mô hình OperationView đầy đủ cho CT-API-007 và luật D8-H-04.

coveredIds: CT-API-007, QR-UX-003, TST-SEC-INV-012
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
import re
from typing import Any

import pytest

from controlplane.application.projections.operation_view_model import (
    OPERATION_STATUSES,
    TERMINAL_STATUSES,
    OperationViewModel,
    build_operation_view,
)
from controlplane.domain.statemachine import OperationState

WAIT: dict[str, Any] = {"code": "capability_unavailable"}
PROBLEM: dict[str, Any] = {
    "code": "RENDER_FAILED",
    "title": "Render thất bại",
    "status": 500,
    "correlation_id": "corr-1",
    "technical_detail_ref": "tdr-1",
}
FINISHED: str = "2026-10-20T10:00:00Z"
EXPECTED_FIELDS: tuple[str, ...] = (
    "operation_id",
    "command_ref",
    "status",
    "progress",
    "resource_refs",
    "started_at",
    "updated_at",
    "finished_at",
    "wait_reason",
    "problem",
)


def _build(state: OperationState, **overrides: Any) -> OperationViewModel:
    return build_operation_view(
        operation_id="op-1",
        command_ref="StartProductionBatch",
        execution_state=state,
        resource_refs={"batch_id": "b-1"},
        **overrides,
    )


def _finished(state: OperationState) -> dict[str, str]:
    if state in (OperationState.SUCCEEDED, OperationState.FAILED):
        return {"finished_at": FINISHED}
    return {}


# 1. test_status_constants
def test_status_constants() -> None:
    assert OPERATION_STATUSES == (
        "accepted",
        "running",
        "waiting",
        "outcome_unknown",
        "succeeded",
        "failed",
    )
    assert TERMINAL_STATUSES == ("succeeded", "failed")
    assert "outcome_unknown" not in TERMINAL_STATUSES


# 2. test_status_matrix
@pytest.mark.parametrize(
    ("state", "wait_reason", "expected_status"),
    [
        (OperationState.PREPARED, None, "accepted"),
        (OperationState.STARTED, None, "running"),
        (OperationState.STARTED, WAIT, "waiting"),
        (OperationState.SUCCEEDED, None, "succeeded"),
        (OperationState.FAILED, None, "failed"),
        (OperationState.OUTCOME_UNKNOWN, None, "outcome_unknown"),
    ],
)
def test_status_matrix(
    state: OperationState,
    wait_reason: dict[str, Any] | None,
    expected_status: str,
) -> None:
    view = _build(state, wait_reason=wait_reason, **_finished(state))
    assert isinstance(view, OperationViewModel)
    assert view.status == expected_status


@pytest.mark.parametrize(
    "state",
    [
        OperationState.PREPARED,
        OperationState.SUCCEEDED,
        OperationState.FAILED,
        OperationState.OUTCOME_UNKNOWN,
    ],
)
def test_status_matrix_unexpected_wait_reason(state: OperationState) -> None:
    with pytest.raises(ValueError, match="^unexpected_wait_reason$"):
        _build(state, wait_reason=WAIT, **_finished(state))


# 3. test_matrix_reaches_all_six_statuses
def test_matrix_reaches_all_six_statuses() -> None:
    combinations = [
        (OperationState.PREPARED, None),
        (OperationState.STARTED, None),
        (OperationState.STARTED, WAIT),
        (OperationState.SUCCEEDED, None),
        (OperationState.FAILED, None),
        (OperationState.OUTCOME_UNKNOWN, None),
    ]
    statuses = {
        _build(state, wait_reason=wr, **_finished(state)).status
        for state, wr in combinations
    }
    assert statuses == set(OPERATION_STATUSES)


# 4. test_waiting_is_not_running and test_outcome_unknown_is_not_failed
def test_waiting_is_not_running() -> None:
    view = _build(OperationState.STARTED, wait_reason=WAIT)
    assert view.status == "waiting"
    assert view.status != "running"


def test_outcome_unknown_is_not_failed() -> None:
    view = _build(OperationState.OUTCOME_UNKNOWN)
    assert view.status == "outcome_unknown"
    assert view.status != "failed"
    assert view.finished_at is None


# 5. test_invalid_wait_reason
@pytest.mark.parametrize(
    "invalid_reason",
    [{}, [], "stalled", {"code": ""}, {"code": 5}, {"reason": "x"}],
)
def test_invalid_wait_reason(invalid_reason: Any) -> None:
    with pytest.raises(ValueError, match="^invalid_wait_reason$"):
        _build(OperationState.STARTED, wait_reason=invalid_reason)


# 6. test_missing_finished_at
@pytest.mark.parametrize("state", [OperationState.SUCCEEDED, OperationState.FAILED])
@pytest.mark.parametrize("missing_val", [None, ""])
def test_missing_finished_at(state: OperationState, missing_val: Any) -> None:
    kwargs: dict[str, Any] = {}
    if missing_val is not None:
        kwargs["finished_at"] = missing_val
    with pytest.raises(ValueError, match="^missing_finished_at$"):
        _build(state, **kwargs)


# 7. test_unexpected_finished_at
@pytest.mark.parametrize(
    ("state", "wait_reason"),
    [
        (OperationState.PREPARED, None),
        (OperationState.STARTED, None),
        (OperationState.STARTED, WAIT),
        (OperationState.OUTCOME_UNKNOWN, None),
    ],
)
def test_unexpected_finished_at(state: OperationState, wait_reason: Any) -> None:
    with pytest.raises(ValueError, match="^unexpected_finished_at$"):
        _build(state, wait_reason=wait_reason, finished_at=FINISHED)


# 8. test_terminal_with_finished_at_is_accepted
@pytest.mark.parametrize("state", [OperationState.SUCCEEDED, OperationState.FAILED])
def test_terminal_with_finished_at_is_accepted(state: OperationState) -> None:
    view = _build(state, finished_at=FINISHED)
    assert view.finished_at == FINISHED


# 9. test_problem_valid_on_failed_and_outcome_unknown
def test_problem_valid_on_failed_and_outcome_unknown() -> None:
    view_failed = _build(OperationState.FAILED, finished_at=FINISHED, problem=PROBLEM)
    assert view_failed.problem == PROBLEM
    assert view_failed.to_dict()["problem"]["technical_detail_ref"] == "tdr-1"

    view_unknown = _build(OperationState.OUTCOME_UNKNOWN, problem=PROBLEM)
    assert view_unknown.problem == PROBLEM
    assert view_unknown.to_dict()["problem"]["technical_detail_ref"] == "tdr-1"


# 10. test_problem_rejected_when_not_failed_or_unknown
@pytest.mark.parametrize(
    ("state", "wait_reason"),
    [
        (OperationState.PREPARED, None),
        (OperationState.STARTED, None),
        (OperationState.STARTED, WAIT),
        (OperationState.SUCCEEDED, None),
    ],
)
def test_problem_rejected_when_not_failed_or_unknown(
    state: OperationState, wait_reason: Any
) -> None:
    with pytest.raises(ValueError, match="^unexpected_problem$"):
        _build(state, wait_reason=wait_reason, problem=PROBLEM, **_finished(state))

    if state is OperationState.STARTED and wait_reason is None:
        with pytest.raises(ValueError, match="^unexpected_problem$"):
            _build(state, problem={})


# 11. test_problem_missing_required_key
@pytest.mark.parametrize("missing_key", ["code", "title", "status", "correlation_id"])
def test_problem_missing_required_key(missing_key: str) -> None:
    bad_problem = {k: v for k, v in PROBLEM.items() if k != missing_key}
    with pytest.raises(ValueError, match="^invalid_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad_problem)

    with pytest.raises(ValueError, match="^invalid_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem="plain text")


# 12. test_problem_forbidden_key_top_level
@pytest.mark.parametrize(
    "forbidden_key",
    [
        "stack_trace",
        "traceback",
        "secret_value",
        "internal_detail",
        "Stack_Trace",
        "TRACEBACK",
        "Secret_Value",
        "INTERNAL_DETAIL",
    ],
)
def test_problem_forbidden_key_top_level(forbidden_key: str) -> None:
    bad_problem = {**PROBLEM, forbidden_key: "x"}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad_problem)


# 13. test_problem_forbidden_key_nested
def test_problem_forbidden_key_nested() -> None:
    bad1 = {**PROBLEM, "detail": {"frames": [{"stack_trace": "x"}]}}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad1)

    bad2 = {**PROBLEM, "items": [[{"Internal_Detail": "x"}]]}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad2)


# 14. test_problem_traceback_string
def test_problem_traceback_string() -> None:
    bad1 = {**PROBLEM, "title": "Traceback (most recent call last): boom"}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad1)

    bad2 = {
        **PROBLEM,
        "notes": ["a", {"note": "Traceback (most recent call last)"}],
    }
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad2)


# 15. test_unsafe_error_does_not_leak_value
def test_unsafe_error_does_not_leak_value() -> None:
    canary = "CANARY-SECRET-1"
    bad_problem = {**PROBLEM, "secret_value": canary}
    with pytest.raises(ValueError) as excinfo:
        _build(OperationState.FAILED, finished_at=FINISHED, problem=bad_problem)
    assert str(excinfo.value) == "unsafe_problem"
    assert canary not in str(excinfo.value)


# 16. test_view_is_frozen_with_ten_fields
def test_view_is_frozen_with_ten_fields() -> None:
    view = _build(OperationState.PREPARED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.status = "changed"  # type: ignore[misc]

    field_names = tuple(f.name for f in dataclasses.fields(OperationViewModel))
    assert field_names == EXPECTED_FIELDS


# 17. test_to_dict_returns_ten_keys_in_order
def test_to_dict_returns_ten_keys_in_order() -> None:
    view = _build(
        OperationState.FAILED,
        progress={"stage": "render"},
        started_at="2026-10-20T09:00:00Z",
        updated_at="2026-10-20T09:30:00Z",
        finished_at=FINISHED,
        problem=PROBLEM,
    )
    result = view.to_dict()
    assert tuple(result.keys()) == EXPECTED_FIELDS
    assert result["operation_id"] == "op-1"
    assert result["command_ref"] == "StartProductionBatch"
    assert result["status"] == "failed"
    assert result["progress"] == {"stage": "render"}
    assert result["resource_refs"] == {"batch_id": "b-1"}
    assert result["started_at"] == "2026-10-20T09:00:00Z"
    assert result["updated_at"] == "2026-10-20T09:30:00Z"
    assert result["finished_at"] == FINISHED
    assert result["wait_reason"] is None
    assert result["problem"] == PROBLEM


# 18. Contract
def _contract_rows() -> list[tuple[list[str], list[str]]]:
    doc_path = (
        Path(__file__).resolve().parents[3]
        / "docs/09-contracts/01-control-api-and-stream.md"
    )
    content = doc_path.read_text(encoding="utf-8")
    section = content.split("### CT-API-007")[1].split("\n## ")[0]
    rows: list[tuple[list[str], list[str]]] = []
    pattern = "`([a-z_]+)`"
    for line in section.strip().splitlines():
        if line.startswith("|"):
            cells = line.strip().strip("|").split("|")
            col0_names = re.findall(pattern, cells[0])
            col1_names = re.findall(pattern, cells[1]) if len(cells) > 1 else []
            if col0_names:
                rows.append((col0_names, col1_names))
    return rows


def test_to_dict_keys_match_contract_table() -> None:
    rows = _contract_rows()
    col0_flat: list[str] = [name for row in rows for name in row[0]]
    assert len(col0_flat) == 10
    view = _build(
        OperationState.FAILED,
        progress={"stage": "render"},
        started_at="2026-10-20T09:00:00Z",
        updated_at="2026-10-20T09:30:00Z",
        finished_at=FINISHED,
        problem=PROBLEM,
    )
    assert set(col0_flat) == set(view.to_dict().keys()) == set(EXPECTED_FIELDS)


def test_status_values_match_contract_table() -> None:
    rows = _contract_rows()
    status_row = next(row for row in rows if row[0] == ["status"])
    assert status_row[1] == list(OPERATION_STATUSES)


# 19. test_module_has_no_clock_or_io_imports
def test_module_has_no_clock_or_io_imports() -> None:
    src_path = (
        Path(__file__).resolve().parents[3]
        / "src/controlplane/application/projections/operation_view_model.py"
    )
    source = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(src_path))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])
    allowed_roots = {"__future__", "dataclasses", "typing", "controlplane"}
    assert imported_roots.issubset(allowed_roots)
