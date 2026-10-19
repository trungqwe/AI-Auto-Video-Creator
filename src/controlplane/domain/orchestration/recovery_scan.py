"""G-14: kế hoạch resume sau restart (CT-WF-004, CT-WF-006, CT-STO-009; INV-016; TST-WF-INV-016, TST-E2E-008).

Pure domain: không I/O, không đồng hồ; now do người gọi truyền.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from controlplane.domain.orchestration.job_waiting import Proceed, evaluate_wait
from controlplane.domain.orchestration.stage_run_plan import StageRun, dependencies_ready
from controlplane.domain.statemachine import StageRunState


class ResumeKind(StrEnum):
    RESUME_STAGE = 'RESUME_STAGE'
    CREATE_NEW_ATTEMPT = 'CREATE_NEW_ATTEMPT'
    RECONCILE_OUTCOME_UNKNOWN = 'RECONCILE_OUTCOME_UNKNOWN'
    QUARANTINE_OLD_EPOCH_RESULT = 'QUARANTINE_OLD_EPOCH_RESULT'
    REISSUE_GRANT_NEW_EPOCH = 'REISSUE_GRANT_NEW_EPOCH'
    KEEP_WAITING = 'KEEP_WAITING'


@dataclass(frozen=True)
class ResumeAction:
    kind: ResumeKind
    stage_run_id: str
    job_id: str | None = None
    result_id: str | None = None


@dataclass(frozen=True)
class GrantView:
    stage_run_id: str
    execution_generation: int
    recovery_epoch: str | int
    expires_at: str


@dataclass(frozen=True)
class PendingResult:
    result_id: str
    stage_run_id: str
    execution_generation: int
    recovery_epoch: str | int


@dataclass(frozen=True)
class ResumeSnapshot:
    runs: tuple[StageRun, ...]
    grants: tuple[GrantView, ...]
    pending_results: tuple[PendingResult, ...]
    current_recovery_epoch: str | int
    now: datetime
    capability_view: Mapping[str, object] | None = None
    allocation_cursor: int = 0  # con trỏ cấp phát, chỉ được kiểm tra, không có action nào quay về candidate đầu


def _epoch_text(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    s = str(value)
    if not s.strip():
        return None
    return s


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _can_run(run: StageRun, runs: tuple[StageRun, ...], view: Mapping[str, object] | None) -> bool:
    return dependencies_ready(run, runs) and isinstance(evaluate_wait(run.stage_type, view), Proceed)


def plan_resume(snapshot: ResumeSnapshot) -> tuple[ResumeAction, ...]:
    """Lập kế hoạch resume sau restart xác định, thuần túy và fail-closed."""
    if not isinstance(snapshot, ResumeSnapshot):
        raise TypeError('snapshot must be ResumeSnapshot')
    if (
        not isinstance(snapshot.runs, tuple)
        or not isinstance(snapshot.grants, tuple)
        or not isinstance(snapshot.pending_results, tuple)
    ):
        raise TypeError('runs, grants, and pending_results must be tuples')

    current = _epoch_text(snapshot.current_recovery_epoch)
    if current is None:
        raise ValueError('current_recovery_epoch must be a valid non-empty str or int')

    if (
        not isinstance(snapshot.now, datetime)
        or snapshot.now.tzinfo is None
        or snapshot.now.utcoffset() is None
    ):
        raise ValueError('now must be an aware datetime')

    if not _is_int(snapshot.allocation_cursor) or snapshot.allocation_cursor < 0:
        raise ValueError('allocation_cursor must be a non-negative integer')

    actions: list[ResumeAction] = []

    # Phần 1: Quarantine old epoch results (INV-016)
    for result in snapshot.pending_results:
        if _epoch_text(result.recovery_epoch) != current:
            actions.append(
                ResumeAction(
                    kind=ResumeKind.QUARANTINE_OLD_EPOCH_RESULT,
                    stage_run_id=result.stage_run_id,
                    result_id=result.result_id,
                )
            )

    # Tìm các run bị supersede
    superseded_ids: set[str] = set()
    for run in snapshot.runs:
        for other in snapshot.runs:
            if (
                other.job_id == run.job_id
                and other.stage_type == run.stage_type
                and other.attempt > run.attempt
            ):
                superseded_ids.add(run.stage_run_id)
                break

    # Phần 2: Lên kế hoạch cho từng stage run
    for run in snapshot.runs:
        if run.stage_run_id in superseded_ids:
            continue

        if run.state in (StageRunState.SUCCEEDED, StageRunState.FAILED_FINAL):
            continue
        elif run.state == StageRunState.OUTCOME_UNKNOWN:
            actions.append(
                ResumeAction(
                    kind=ResumeKind.RECONCILE_OUTCOME_UNKNOWN,
                    stage_run_id=run.stage_run_id,
                    job_id=run.job_id,
                )
            )
        elif run.state in (
            StageRunState.PENDING,
            StageRunState.WAITING_DEPENDENCY,
            StageRunState.WAITING_CAPABILITY,
        ):
            kind = (
                ResumeKind.RESUME_STAGE
                if _can_run(run, snapshot.runs, snapshot.capability_view)
                else ResumeKind.KEEP_WAITING
            )
            actions.append(
                ResumeAction(
                    kind=kind,
                    stage_run_id=run.stage_run_id,
                    job_id=run.job_id,
                )
            )
        elif run.state in (StageRunState.FAILED_RETRYABLE, StageRunState.STALE):
            kind = (
                ResumeKind.CREATE_NEW_ATTEMPT
                if _can_run(run, snapshot.runs, snapshot.capability_view)
                else ResumeKind.KEEP_WAITING
            )
            actions.append(
                ResumeAction(
                    kind=kind,
                    stage_run_id=run.stage_run_id,
                    job_id=run.job_id,
                )
            )
        elif run.state == StageRunState.RUNNING:
            matching_grants = [
                g
                for g in snapshot.grants
                if g.stage_run_id == run.stage_run_id and _is_int(g.execution_generation)
            ]
            if not matching_grants:
                kind = ResumeKind.RECONCILE_OUTCOME_UNKNOWN
            else:
                best_grant = max(matching_grants, key=lambda g: g.execution_generation)
                if _epoch_text(best_grant.recovery_epoch) != current:
                    kind = ResumeKind.REISSUE_GRANT_NEW_EPOCH
                else:
                    expiry = _parse_aware(best_grant.expires_at)
                    if expiry is None or snapshot.now >= expiry:
                        kind = ResumeKind.RECONCILE_OUTCOME_UNKNOWN
                    else:
                        kind = ResumeKind.KEEP_WAITING

            actions.append(
                ResumeAction(
                    kind=kind,
                    stage_run_id=run.stage_run_id,
                    job_id=run.job_id,
                )
            )
        else:
            actions.append(
                ResumeAction(
                    kind=ResumeKind.KEEP_WAITING,
                    stage_run_id=run.stage_run_id,
                    job_id=run.job_id,
                )
            )

    return tuple(actions)


__all__ = [
    'GrantView',
    'PendingResult',
    'ResumeAction',
    'ResumeKind',
    'ResumeSnapshot',
    'plan_resume',
]
