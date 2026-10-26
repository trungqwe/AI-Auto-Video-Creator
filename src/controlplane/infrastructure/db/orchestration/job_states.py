"""PW-G4: PostgreSQL stores for the state columns of cp_video_jobs and cp_production_batches on a caller-owned connection.

The caller owns the transaction; this module never opens or ends one. Every edge is decided by the pure state machine.
"""
from __future__ import annotations

import datetime
from typing import Any

from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.batch_outcome import BatchOutcome, plan_batch_transition
from controlplane.domain.orchestration.job_waiting import Proceed, Wait, plan_job_transition
from controlplane.domain.statemachine import BatchState, JobState, TransitionResult, transition_job

JOB_NOT_FOUND = 'JOB_NOT_FOUND'
JOB_REVISION_CONFLICT = 'JOB_REVISION_CONFLICT'
BATCH_NOT_FOUND = 'BATCH_NOT_FOUND'
INVALID_BATCH_STATUS = 'INVALID_BATCH_STATUS'
INVALID_STOP_REASON = 'INVALID_STOP_REASON'


class PostgresJobStates:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def state_of(self, job_id: str, *, lock: bool = False) -> JobState | None:
        row = self._connection.execute(
            'SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s' + (' FOR UPDATE' if lock else ''),
            (self._workspace_id, job_id),
        ).fetchone()
        return JobState(row[0]) if row is not None else None

    def transition(self, job_id: str, requested: JobState) -> JobState:
        current, revision = self._lock(job_id)
        result = transition_job(current_state=current, current_revision=revision, expected_revision=revision, requested_state=JobState(requested))
        return self._write(job_id, result, None)

    def apply_decision(self, job_id: str, decision: Proceed | Wait) -> JobState | None:
        current, revision = self._lock(job_id)
        plan = plan_job_transition(current_state=current, current_revision=revision, expected_revision=revision, decision=decision)
        if plan is None:
            return None
        return self._write(job_id, plan, decision.reason.value if isinstance(decision, Wait) else None)

    def _lock(self, job_id: str) -> tuple[JobState, int]:
        row = self._connection.execute(
            'SELECT status, revision FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s FOR UPDATE',
            (self._workspace_id, job_id),
        ).fetchone()
        if row is None:
            raise OrchestrationContractError(JOB_NOT_FOUND)
        return JobState(row[0]), int(row[1])

    def _write(self, job_id: str, result: TransitionResult, wait_reason: str | None) -> JobState:
        cursor = self._connection.execute(
            'UPDATE controlplane.cp_video_jobs SET status = %s, revision = %s, wait_reason = %s WHERE workspace_id = %s AND job_id = %s AND revision = %s',
            (JobState(result.state).value, result.revision, wait_reason, self._workspace_id, job_id, result.revision - 1),
        )
        if cursor.rowcount != 1:
            raise OrchestrationContractError(JOB_REVISION_CONFLICT)
        return JobState(result.state)


class PostgresBatchStates:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def finish(self, batch_id: str, outcome: BatchOutcome, reason: str, now: datetime.datetime) -> bool:
        if not isinstance(outcome, BatchOutcome) or outcome == BatchOutcome.CONTINUE:
            raise OrchestrationContractError(INVALID_BATCH_STATUS)
        if not isinstance(reason, str) or reason.strip() == '':
            raise OrchestrationContractError(INVALID_STOP_REASON)
        row = self._connection.execute(
            'SELECT status FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s FOR UPDATE',
            (self._workspace_id, batch_id),
        ).fetchone()
        if row is None:
            raise OrchestrationContractError(BATCH_NOT_FOUND)
        current = BatchState(row[0])
        if current.value == outcome.value:
            return False
        # cp_production_batches has no revision column, so the pure state machine runs with a fixed revision pair; edges still decide.
        plan = plan_batch_transition(current_state=current, current_revision=0, expected_revision=0, outcome=outcome)
        if plan is None:
            return False
        self._connection.execute(
            'UPDATE controlplane.cp_production_batches SET status = %s, stop_reason = %s, stopped_at = %s WHERE workspace_id = %s AND batch_id = %s',
            (BatchState(plan.state).value, reason, now, self._workspace_id, batch_id),
        )
        return True


__all__ = ['BATCH_NOT_FOUND', 'INVALID_BATCH_STATUS', 'INVALID_STOP_REASON', 'JOB_NOT_FOUND', 'JOB_REVISION_CONFLICT', 'PostgresBatchStates', 'PostgresJobStates']
