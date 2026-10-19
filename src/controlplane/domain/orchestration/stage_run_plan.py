"""G-06: StageRun theo attempt và áp kết quả activity (CT-ORC-003, CT-STATE-008, CT-WF-006; D8-G-01, D8-G-02).

Pure domain: không I/O, không đồng hồ, không đổi đối số. Mỗi attempt là một hàng StageRun mới; state machine không thêm cạnh.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.orchestration.activity_binding import DISPOSITIONS
from controlplane.domain.statemachine import ReconciliationEvidence, StageRunState, transition_stage_run

STAGE_NOT_COMMITTED = 'STAGE_NOT_COMMITTED'
FENCING_REJECTED = 'FENCING_REJECTED'
UNKNOWN_DISPOSITION = 'UNKNOWN_DISPOSITION'
STAGE_NOT_RUNNING = 'STAGE_NOT_RUNNING'
ATTEMPT_NOT_ALLOWED = 'ATTEMPT_NOT_ALLOWED'
INVALID_STAGE_RUN_ID = 'INVALID_STAGE_RUN_ID'
ATTEMPT_SOURCE_STATES = frozenset({StageRunState.WAITING_DEPENDENCY, StageRunState.WAITING_CAPABILITY, StageRunState.FAILED_RETRYABLE, StageRunState.STALE})


class StageRunPlanError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StageRun:
    stage_run_id: str
    job_id: str
    stage_type: str
    input_refs: tuple[str, ...]
    state: StageRunState
    attempt: int
    dependency_refs: tuple[str, ...] = ()
    revision: int = 0


@dataclass(frozen=True)
class StageResultPlan:
    state: StageRunState
    revision: int
    changed: bool
    job_waiting: bool


def plan_attempt(previous: StageRun, new_stage_run_id: str) -> StageRun:
    if not isinstance(new_stage_run_id, str) or not new_stage_run_id.strip() or new_stage_run_id == previous.stage_run_id:
        raise StageRunPlanError(INVALID_STAGE_RUN_ID)
    if previous.state not in ATTEMPT_SOURCE_STATES:
        raise StageRunPlanError(ATTEMPT_NOT_ALLOWED)
    return StageRun(
        stage_run_id=new_stage_run_id,
        job_id=previous.job_id,
        stage_type=previous.stage_type,
        input_refs=previous.input_refs,
        state=StageRunState.PENDING,
        attempt=previous.attempt + 1,
        dependency_refs=previous.dependency_refs,
        revision=0,
    )


def dependencies_ready(stage: StageRun, runs: Sequence[StageRun]) -> bool:
    for dependency in stage.dependency_refs:
        rows = [run for run in runs if run.job_id == stage.job_id and run.stage_type == dependency]
        if not rows:
            return False
        latest = max(run.attempt for run in rows)
        if any(run.state != StageRunState.SUCCEEDED for run in rows if run.attempt == latest):
            return False
    return True


def apply_activity_result(*, current_state: StageRunState, current_revision: int, expected_revision: int, disposition: str, fencing_accepted: bool, owner_commit_confirmed: bool, retryable: bool = False, evidence_ref: str | None = None) -> StageResultPlan:
    if disposition not in DISPOSITIONS:
        raise StageRunPlanError(UNKNOWN_DISPOSITION)
    if not all(isinstance(flag, bool) for flag in (fencing_accepted, owner_commit_confirmed, retryable)):
        raise TypeError('fencing_accepted, owner_commit_confirmed and retryable must be bool')
    if disposition == 'succeeded' and not (fencing_accepted and owner_commit_confirmed):
        raise StageRunPlanError(STAGE_NOT_COMMITTED)
    if disposition not in ('succeeded', 'stale') and not fencing_accepted:
        raise StageRunPlanError(FENCING_REJECTED)
    if disposition == 'waiting':
        if current_state != StageRunState.RUNNING:
            raise StageRunPlanError(STAGE_NOT_RUNNING)
        if expected_revision != current_revision:
            raise RevisionConflictError(current_revision)
        return StageResultPlan(state=current_state, revision=current_revision, changed=False, job_waiting=True)
    requested = {
        'succeeded': StageRunState.SUCCEEDED,
        'failed': StageRunState.FAILED_RETRYABLE if retryable else StageRunState.FAILED_FINAL,
        'outcome_unknown': StageRunState.OUTCOME_UNKNOWN,
        'stale': StageRunState.STALE,
    }[disposition]
    evidence = ReconciliationEvidence(evidence_ref) if isinstance(evidence_ref, str) and evidence_ref.strip() else None
    result = transition_stage_run(
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested,
        reconciliation_evidence=evidence,
    )
    return StageResultPlan(state=result.state, revision=result.revision, changed=True, job_waiting=False)


__all__ = ['ATTEMPT_NOT_ALLOWED', 'ATTEMPT_SOURCE_STATES', 'FENCING_REJECTED', 'INVALID_STAGE_RUN_ID', 'STAGE_NOT_COMMITTED', 'STAGE_NOT_RUNNING', 'UNKNOWN_DISPOSITION', 'StageResultPlan', 'StageRun', 'StageRunPlanError', 'apply_activity_result', 'dependencies_ready', 'plan_attempt']
