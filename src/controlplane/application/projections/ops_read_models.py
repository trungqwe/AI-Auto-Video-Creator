"""Pure operations read models for CT-API-002 and CT-STATE-009 (H-05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

LOG_SEVERITIES: tuple[str, ...] = ("debug", "info", "warning", "error")
FORBIDDEN_STAGE_PROBLEM_KEYS: frozenset[str] = frozenset({"stack_trace", "traceback", "internal_detail"})
UNSAFE_SUMMARY_MARKERS: tuple[str, ...] = ("traceback (most recent call last)", "stack trace")
DEFAULT_SUMMARY_MAX_LEN: int = 300


@dataclass(frozen=True)
class StageRunView:
    stage_run_id: str
    job_id: str
    module: str
    status: str
    attempt: int
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    problem: dict[str, Any] | None


@dataclass(frozen=True)
class SessionView:
    session_id: str
    started_at: str
    ended_at: str | None
    output_folder_label: str
    status: str


@dataclass(frozen=True)
class LogEntryView:
    log_id: str
    severity: str
    occurred_at: str
    summary: str
    correlation_id: str
    technical_detail_ref: str | None


@dataclass(frozen=True)
class CapabilityHealthView:
    capability_kind: str
    name: str
    availability: str
    checked_at: str


@dataclass(frozen=True)
class JobMilestonesView:
    render_succeeded: bool
    qc_passed: bool
    upload_verified: bool
    completed: bool


def _validate_detail_ref(ref: Any) -> str | None:
    if ref is None:
        return None
    if not isinstance(ref, str):
        raise ValueError("invalid_technical_detail_ref")
    try:
        parsed = uuid.UUID(ref)
    except ValueError as exc:
        raise ValueError("invalid_technical_detail_ref") from exc
    if str(parsed) != ref.lower():
        raise ValueError("invalid_technical_detail_ref")
    return str(parsed)


def safe_summary(text: str, max_len: int = DEFAULT_SUMMARY_MAX_LEN) -> str:
    if not isinstance(text, str):
        raise ValueError("invalid_summary")
    if isinstance(max_len, bool) or not isinstance(max_len, int) or max_len < 1:
        raise ValueError("invalid_max_len")
    flattened = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    lowered = flattened.lower()
    if any(marker in lowered for marker in UNSAFE_SUMMARY_MARKERS):
        raise ValueError("unsafe_summary")
    return flattened[:max_len]


def build_log_entry(
    *,
    log_id: str,
    severity: str,
    occurred_at: str,
    summary: str,
    correlation_id: str,
    technical_detail_ref: str | None = None,
) -> LogEntryView:
    if severity not in LOG_SEVERITIES:
        raise ValueError("invalid_severity")
    return LogEntryView(
        log_id=log_id,
        severity=severity,
        occurred_at=occurred_at,
        summary=safe_summary(summary),
        correlation_id=correlation_id,
        technical_detail_ref=_validate_detail_ref(technical_detail_ref),
    )


def _has_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and key.lower() in FORBIDDEN_STAGE_PROBLEM_KEYS)
            or _has_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden_key(item) for item in value)
    return False


def _as_ref_tuple(refs: Any) -> tuple[str, ...]:
    if not isinstance(refs, (list, tuple)) or not all(isinstance(ref, str) for ref in refs):
        raise ValueError("invalid_refs")
    return tuple(refs)


def build_stage_run_view(
    *,
    stage_run_id: str,
    job_id: str,
    module: str,
    status: str,
    attempt: int,
    input_refs: Any = (),
    output_refs: Any = (),
    problem: Any = None,
) -> StageRunView:
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("invalid_attempt")
    if problem is not None:
        if not isinstance(problem, dict):
            raise ValueError("invalid_problem")
        if _has_forbidden_key(problem):
            raise ValueError("unsafe_problem")
    return StageRunView(
        stage_run_id=stage_run_id,
        job_id=job_id,
        module=module,
        status=status,
        attempt=attempt,
        input_refs=_as_ref_tuple(input_refs),
        output_refs=_as_ref_tuple(output_refs),
        problem=problem,
    )


def build_job_milestones(
    *,
    render_succeeded: bool,
    qc_passed: bool,
    upload_verified: bool,
    completed: bool,
) -> JobMilestonesView:
    flags = (render_succeeded, qc_passed, upload_verified, completed)
    if not all(isinstance(flag, bool) for flag in flags):
        raise ValueError("invalid_milestone")
    if completed and not upload_verified:
        raise ValueError("completed_without_upload_verified")
    return JobMilestonesView(
        render_succeeded=render_succeeded,
        qc_passed=qc_passed,
        upload_verified=upload_verified,
        completed=completed,
    )
