"""PW-G2: PostgreSQL store for StageRun rows (cp_stage_runs) on a caller-owned connection.

The caller owns the transaction; this module never opens or ends one.
"""
from __future__ import annotations

import datetime
import re
from typing import Any

from psycopg.types.json import Jsonb

from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.statemachine import ReconciliationEvidence, StageRunState, transition_stage_run

INVALID_STAGE_RUN_ID = 'INVALID_STAGE_RUN_ID'
INVALID_RECOVERY_EPOCH = 'INVALID_RECOVERY_EPOCH'
STAGE_RUN_NOT_FOUND = 'NOT_FOUND'
FINISHED_STATES = frozenset({StageRunState.SUCCEEDED, StageRunState.FAILED_RETRYABLE, StageRunState.FAILED_FINAL, StageRunState.OUTCOME_UNKNOWN, StageRunState.STALE})
_STAGE_RUN_ID = re.compile(r'(.+):([^:]+):r([0-9]+)')
_MAX_ATTEMPT = 2147483647


def parse_stage_run_id(stage_run_id: str) -> tuple[str, str, int]:
    match = _STAGE_RUN_ID.fullmatch(stage_run_id) if isinstance(stage_run_id, str) else None
    if match is None:
        raise OrchestrationContractError(INVALID_STAGE_RUN_ID)
    owner, stage, revision = match.group(1), match.group(2), int(match.group(3))
    if owner.strip() == '' or stage.strip() == '' or not 1 <= revision <= _MAX_ATTEMPT:
        raise OrchestrationContractError(INVALID_STAGE_RUN_ID)
    return owner, stage, revision


class PostgresStageRuns:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def ensure(self, stage_run_id: str, recovery_epoch: str = '0') -> bool:
        owner, stage, revision = parse_stage_run_id(stage_run_id)
        if not isinstance(recovery_epoch, str) or recovery_epoch.strip() == '':
            raise OrchestrationContractError(INVALID_RECOVERY_EPOCH)
        is_job = self._connection.execute(
            "SELECT 1 FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s",
            (self._workspace_id, owner),
        ).fetchone() is not None
        cursor = self._connection.execute(
            "INSERT INTO controlplane.cp_stage_runs "
            "(stage_run_id, workspace_id, job_id, workflow_id, stage_name, attempt, status, recovery_epoch, execution_generation) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s, 0) "
            "ON CONFLICT (workspace_id, stage_run_id) DO NOTHING",
            (stage_run_id, self._workspace_id, owner if is_job else None, None if is_job else owner, stage, revision, recovery_epoch),
        )
        return cursor.rowcount == 1

    def status_of(self, stage_run_id: str, *, lock: bool = False) -> StageRunState | None:
        row = self._connection.execute(
            "SELECT status FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND stage_run_id = %s" + (" FOR UPDATE" if lock else ""),
            (self._workspace_id, stage_run_id),
        ).fetchone()
        return StageRunState(row[0]) if row is not None else None

    def transition(self, stage_run_id: str, requested: StageRunState, now: datetime.datetime, *, execution_generation: int | None = None, wait_reason: str | None = None, problem: dict[str, Any] | None = None, evidence_ref: str | None = None) -> StageRunState:
        requested = StageRunState(requested)
        current = self.status_of(stage_run_id, lock=True)
        if current is None:
            raise OrchestrationContractError(STAGE_RUN_NOT_FOUND)
        evidence = ReconciliationEvidence(evidence_ref) if isinstance(evidence_ref, str) and evidence_ref.strip() else None
        # cp_stage_runs has no revision column, so the pure state machine runs with a fixed revision pair; edges still decide.
        transition_stage_run(current_state=current, current_revision=0, expected_revision=0, requested_state=requested, reconciliation_evidence=evidence)
        self._connection.execute(
            "UPDATE controlplane.cp_stage_runs SET status = %s, execution_generation = COALESCE(%s, execution_generation), "
            "started_at = COALESCE(%s, started_at), finished_at = COALESCE(%s, finished_at), wait_reason = %s, "
            "problem = COALESCE(%s, problem), updated_at = %s WHERE workspace_id = %s AND stage_run_id = %s",
            (requested.value, execution_generation, now if requested == StageRunState.RUNNING else None, now if requested in FINISHED_STATES else None, None if wait_reason is None else str(wait_reason), Jsonb(problem) if problem is not None else None, now, self._workspace_id, stage_run_id),
        )
        return requested

    def record_wait(self, stage_run_id: str, wait_reason: str, now: datetime.datetime) -> bool:
        cursor = self._connection.execute(
            "UPDATE controlplane.cp_stage_runs SET wait_reason = %s, updated_at = %s "
            "WHERE workspace_id = %s AND stage_run_id = %s AND status = 'RUNNING'",
            (str(wait_reason), now, self._workspace_id, stage_run_id),
        )
        return cursor.rowcount == 1


__all__ = ['FINISHED_STATES', 'INVALID_RECOVERY_EPOCH', 'INVALID_STAGE_RUN_ID', 'PostgresStageRuns', 'STAGE_RUN_NOT_FOUND', 'parse_stage_run_id']
