"""Kiểm thử read model vận hành H-05 (stage run, session, log, capability, mốc job).

coveredIds: CT-API-002, CT-STATE-009, QR-UX-003, TST-E2E-INV-009"""

from __future__ import annotations

import ast
import dataclasses
import itertools
from pathlib import Path
from typing import Any
import uuid

import pytest

from controlplane.application.projections.ops_read_models import (
    LOG_SEVERITIES,
    CapabilityHealthView,
    JobMilestonesView,
    LogEntryView,
    SessionView,
    StageRunView,
    build_job_milestones,
    build_log_entry,
    build_stage_run_view,
    safe_summary,
)

UUID_OK = "00000000-0000-0000-0000-000000000999"


def _log(**overrides: Any) -> LogEntryView:
    payload: dict[str, Any] = {
        "log_id": "log-1",
        "severity": "info",
        "occurred_at": "2026-10-20T10:00:00Z",
        "summary": "Render bắt đầu",
        "correlation_id": "corr-1",
        "technical_detail_ref": None,
    }
    payload.update(overrides)
    return build_log_entry(**payload)


@pytest.mark.parametrize(
    "marker_text",
    [
        "Traceback (most recent call last): boom",
        "TRACEBACK (MOST RECENT CALL LAST)",
        "boom\nTraceback (most recent call last)",
        "Stack Trace: x",
        "STACK TRACE",
        "x" * 400 + " stack trace",
    ],
)
def test_safe_summary_rejects_markers(marker_text: str) -> None:
    with pytest.raises(ValueError, match="^unsafe_summary$"):
        safe_summary(marker_text)


def test_safe_summary_truncates_and_flattens() -> None:
    text = "line\n" * 200
    res = safe_summary(text)
    assert len(res) == 300
    assert "\n" not in res
    assert "\t" not in res

    flattened = safe_summary("a\tb\r\nc")
    assert "\t" not in flattened
    assert "\r" not in flattened
    assert "\n" not in flattened
    assert flattened.startswith("a b")

    assert safe_summary("x" * 1000, max_len=10) == "x" * 10
    assert safe_summary("ngắn") == "ngắn"


def test_safe_summary_invalid_arguments() -> None:
    with pytest.raises(ValueError, match="^invalid_summary$"):
        safe_summary(123)  # type: ignore[arg-type]

    for invalid_max in (0, -1, True, "5"):
        with pytest.raises(ValueError, match="^invalid_max_len$"):
            safe_summary("ok", max_len=invalid_max)  # type: ignore[arg-type]


def test_log_rejects_traceback_summary() -> None:
    with pytest.raises(ValueError, match="^unsafe_summary$"):
        _log(summary="Traceback (most recent call last): x")


def test_log_summary_is_sanitized() -> None:
    entry = _log(summary="y" * 1000 + "\n")
    assert len(entry.summary) == 300
    assert "\n" not in entry.summary


def test_log_severity() -> None:
    assert LOG_SEVERITIES == ("debug", "info", "warning", "error")
    for sev in LOG_SEVERITIES:
        entry = _log(severity=sev)
        assert entry.severity == sev

    for invalid_sev in ("fatal", "INFO", "", None):
        with pytest.raises(ValueError, match="^invalid_severity$"):
            _log(severity=invalid_sev)  # type: ignore[arg-type]


def test_log_technical_detail_ref() -> None:
    entry_none = _log(technical_detail_ref=None)
    assert entry_none.technical_detail_ref is None

    entry_uuid = _log(technical_detail_ref=UUID_OK)
    assert entry_uuid.technical_detail_ref == UUID_OK

    entry_upper = _log(technical_detail_ref="ABCDEF00-0000-0000-0000-000000000999")
    assert entry_upper.technical_detail_ref == "abcdef00-0000-0000-0000-000000000999"

    for invalid_ref in (
        "abc",
        "",
        "00000000000000000000000000000999",
        "{00000000-0000-0000-0000-000000000999}",
        123,
    ):
        with pytest.raises(ValueError, match="^invalid_technical_detail_ref$"):
            _log(technical_detail_ref=invalid_ref)  # type: ignore[arg-type]


PROBLEM: dict[str, Any] = {
    "code": "RENDER_FAILED",
    "title": "Render thất bại",
    "status": 500,
    "correlation_id": "corr-1",
    "technical_detail_ref": UUID_OK,
}


def _stage(**overrides: Any) -> StageRunView:
    payload: dict[str, Any] = {
        "stage_run_id": "sr-1",
        "job_id": "job-1",
        "module": "render",
        "status": "running",
        "attempt": 1,
        "input_refs": ("in-1",),
        "output_refs": (),
        "problem": None,
    }
    payload.update(overrides)
    return build_stage_run_view(**payload)


def _milestones(**kw: Any) -> JobMilestonesView:
    payload: dict[str, Any] = {
        "render_succeeded": True,
        "qc_passed": False,
        "upload_verified": False,
        "completed": False,
    }
    payload.update(kw)
    return build_job_milestones(**payload)


def test_stage_attempt() -> None:
    v1 = _stage(attempt=1)
    assert v1.attempt == 1
    v2 = _stage(attempt=2)
    assert v2.attempt == 2

    for invalid_attempt in (0, -1, True, "1", 1.0):
        with pytest.raises(ValueError, match="^invalid_attempt$"):
            _stage(attempt=invalid_attempt)  # type: ignore[arg-type]


def test_stage_problem_valid_and_none() -> None:
    view_none = _stage(problem=None)
    assert view_none.problem is None

    view_prob = _stage(problem=PROBLEM)
    assert view_prob.problem == PROBLEM


@pytest.mark.parametrize(
    "key",
    [
        "stack_trace",
        "traceback",
        "internal_detail",
        "Stack_Trace",
        "TRACEBACK",
        "Internal_Detail",
    ],
)
def test_stage_problem_forbidden_key_top_level(key: str) -> None:
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _stage(problem={**PROBLEM, key: "x"})


def test_stage_problem_forbidden_key_nested() -> None:
    nested1 = {**PROBLEM, "detail": {"frames": [{"internal_detail": "x"}]}}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _stage(problem=nested1)

    nested2 = {**PROBLEM, "items": [[{"Traceback": "x"}]]}
    with pytest.raises(ValueError, match="^unsafe_problem$"):
        _stage(problem=nested2)


def test_stage_problem_error_does_not_leak() -> None:
    with pytest.raises(ValueError) as excinfo:
        _stage(problem={**PROBLEM, "internal_detail": "CANARY-1"})
    assert str(excinfo.value) == "unsafe_problem"


def test_stage_problem_must_be_dict() -> None:
    for invalid_prob in ("text", [], 5):
        with pytest.raises(ValueError, match="^invalid_problem$"):
            _stage(problem=invalid_prob)  # type: ignore[arg-type]


def test_stage_refs() -> None:
    view = _stage(input_refs=["a", "b"])
    assert view.input_refs == ("a", "b")

    default_view = build_stage_run_view(
        stage_run_id="sr-2",
        job_id="job-2",
        module="source",
        status="running",
        attempt=1,
    )
    assert default_view.input_refs == ()
    assert default_view.output_refs == ()

    for invalid_ref in ("abc", [1]):
        with pytest.raises(ValueError, match="^invalid_refs$"):
            _stage(input_refs=invalid_ref)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="^invalid_refs$"):
            _stage(output_refs=invalid_ref)  # type: ignore[arg-type]


def test_session_and_capability_views() -> None:
    sess = SessionView("s-1", "2026-10-20T09:00:00Z", None, "Lượt sáng", "running")
    assert sess.session_id == "s-1"
    assert sess.started_at == "2026-10-20T09:00:00Z"
    assert sess.ended_at is None
    assert sess.output_folder_label == "Lượt sáng"
    assert sess.status == "running"

    cap = CapabilityHealthView("gpu", "local-gpu", "available", "2026-10-20T10:00:00Z")
    assert cap.capability_kind == "gpu"
    assert cap.name == "local-gpu"
    assert cap.availability == "available"
    assert cap.checked_at == "2026-10-20T10:00:00Z"


def test_milestones_independent() -> None:
    m = build_job_milestones(
        render_succeeded=True,
        qc_passed=False,
        upload_verified=False,
        completed=False,
    )
    assert (
        m.render_succeeded,
        m.qc_passed,
        m.upload_verified,
        m.completed,
    ) == (True, False, False, False)


def test_milestones_all_sixteen_combinations() -> None:
    for render_s, qc, upload_v, comp in itertools.product([False, True], repeat=4):
        if comp and not upload_v:
            with pytest.raises(ValueError, match="^completed_without_upload_verified$"):
                build_job_milestones(
                    render_succeeded=render_s,
                    qc_passed=qc,
                    upload_verified=upload_v,
                    completed=comp,
                )
        else:
            m = build_job_milestones(
                render_succeeded=render_s,
                qc_passed=qc,
                upload_verified=upload_v,
                completed=comp,
            )
            assert (
                m.render_succeeded,
                m.qc_passed,
                m.upload_verified,
                m.completed,
            ) == (render_s, qc, upload_v, comp)


def test_milestones_require_real_bool() -> None:
    for invalid_val in (1, None):
        with pytest.raises(ValueError, match="^invalid_milestone$"):
            _milestones(render_succeeded=invalid_val)
        with pytest.raises(ValueError, match="^invalid_milestone$"):
            _milestones(qc_passed=invalid_val)
        with pytest.raises(ValueError, match="^invalid_milestone$"):
            _milestones(upload_verified=invalid_val)
        with pytest.raises(ValueError, match="^invalid_milestone$"):
            _milestones(completed=invalid_val)


def test_milestones_are_four_separate_fields() -> None:
    fields = dataclasses.fields(JobMilestonesView)
    assert tuple(f.name for f in fields) == (
        "render_succeeded",
        "qc_passed",
        "upload_verified",
        "completed",
    )
    for f in fields:
        assert f.type == "bool"


def test_views_are_frozen_with_expected_fields() -> None:
    instances = [
        _stage(),
        _log(),
        SessionView("s-1", "2026-10-20T09:00:00Z", None, "label", "running"),
        CapabilityHealthView("gpu", "local-gpu", "available", "2026-10-20T10:00:00Z"),
        _milestones(),
    ]
    for inst in instances:
        first_field = dataclasses.fields(inst)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(inst, first_field, "modified")

    assert tuple(f.name for f in dataclasses.fields(StageRunView)) == (
        "stage_run_id",
        "job_id",
        "module",
        "status",
        "attempt",
        "input_refs",
        "output_refs",
        "problem",
    )
    assert tuple(f.name for f in dataclasses.fields(SessionView)) == (
        "session_id",
        "started_at",
        "ended_at",
        "output_folder_label",
        "status",
    )
    assert tuple(f.name for f in dataclasses.fields(LogEntryView)) == (
        "log_id",
        "severity",
        "occurred_at",
        "summary",
        "correlation_id",
        "technical_detail_ref",
    )
    assert tuple(f.name for f in dataclasses.fields(CapabilityHealthView)) == (
        "capability_kind",
        "name",
        "availability",
        "checked_at",
    )
    assert tuple(f.name for f in dataclasses.fields(JobMilestonesView)) == (
        "render_succeeded",
        "qc_passed",
        "upload_verified",
        "completed",
    )


def test_module_has_only_pure_imports() -> None:
    module_path = (
        Path(__file__).resolve().parents[3]
        / "src/controlplane/application/projections/ops_read_models.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imported_roots.add(node.module.split(".")[0])
    assert imported_roots.issubset({"__future__", "dataclasses", "typing", "uuid"})
