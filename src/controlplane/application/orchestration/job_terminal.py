"""PW-G4-FIX1: JobTerminator đưa job video tới FAILED_FINAL, trả suất variant và capacity, đóng dòng stage RUNNING (CT-CMN-010, CT-ORC-002, CT-ORC-012). Đồng bộ; mỗi lời gọi là một giao dịch."""
from __future__ import annotations

import datetime
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.allocation_policy import ReservationAction, reservation_action
from controlplane.domain.statemachine import JobState, StageRunState
from controlplane.application.orchestration.variant_reservation_flow import VariantReservationFlow
from controlplane.infrastructure.db.orchestration.job_states import JOB_NOT_FOUND, PostgresJobStates
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns, parse_stage_run_id
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry

STAGE_OWNER_MISMATCH = 'STAGE_OWNER_MISMATCH'
JOB_NOT_FAILABLE = 'JOB_NOT_FAILABLE'
RETRY_EXHAUSTED = 'RETRY_EXHAUSTED'
_VARIANT_NOT_FOUND = 'NOT_FOUND'
_RELEASE_CAPACITY_SQL = (
    "UPDATE controlplane.cp_batch_capacity_reservations SET state = 'RELEASED' "
    "WHERE workspace_id = %s AND job_id = %s AND state = 'ACTIVE'"
)
_FAILABLE = frozenset({JobState.ACTIVE, JobState.WAITING, JobState.READY_FOR_COMPLETION})


@dataclass(frozen=True)
class FailJobRequest:
    video_job_id: str
    stage_run_id: str
    problem: Mapping[str, Any]


@dataclass(frozen=True)
class FailJobResult:
    code: str | None
    job_state: str | None


class JobTerminator:
    def __init__(self, connection_factory: Callable[[], Any], clock: Callable[[], datetime.datetime], *, workspace_id: str) -> None:
        self._connection_factory = connection_factory
        self._clock = clock
        self._workspace_id = workspace_id

    def fail(self, request: FailJobRequest) -> FailJobResult:
        try:
            owner = parse_stage_run_id(request.stage_run_id)[0]
        except OrchestrationContractError:
            owner = None
        if owner != request.video_job_id:
            return FailJobResult(STAGE_OWNER_MISMATCH, None)
        with self._connection_factory() as connection:
            with connection.transaction():
                return self._fail(connection, request)

    def _fail(self, connection: Any, request: FailJobRequest) -> FailJobResult:
        ws = self._workspace_id
        job_id = request.video_job_id
        states = PostgresJobStates(connection, ws)
        state = states.state_of(job_id, lock=True)
        if state is None:
            return FailJobResult(JOB_NOT_FOUND, None)
        if state is JobState.COMPLETED:
            return FailJobResult(None, state.value)
        if state not in _FAILABLE and state not in (JobState.SNAPSHOTTED, JobState.FAILED_FINAL):
            return FailJobResult(JOB_NOT_FAILABLE, state.value)
        if state is JobState.SNAPSHOTTED:
            states.transition(job_id, JobState.ACTIVE)
            state = JobState.ACTIVE
        if state is not JobState.FAILED_FINAL:
            states.transition(job_id, JobState.FAILED_FINAL)
        if reservation_action(JobState.FAILED_FINAL) is ReservationAction.RELEASE:
            try:
                VariantReservationFlow(PostgresVariantRegistry(connection)).release(ws, job_id, JobState.FAILED_FINAL)
            except OrchestrationContractError as exc:
                if exc.code != _VARIANT_NOT_FOUND:
                    raise
            connection.execute(_RELEASE_CAPACITY_SQL, (ws, job_id))
        runs = PostgresStageRuns(connection, ws)
        if runs.status_of(request.stage_run_id, lock=True) == StageRunState.RUNNING:
            problem = request.problem if isinstance(request.problem, Mapping) else {}
            code = problem.get('code')
            runs.transition(
                request.stage_run_id,
                StageRunState.FAILED_FINAL,
                self._clock(),
                problem={
                    'code': code if isinstance(code, str) and code.strip() else RETRY_EXHAUSTED,
                    'activity': problem.get('activity'),
                    'disposition': problem.get('disposition'),
                    'retryable': False,
                },
            )
        return FailJobResult(None, JobState.FAILED_FINAL.value)


__all__ = ['FailJobRequest', 'FailJobResult', 'JOB_NOT_FAILABLE', 'JobTerminator', 'RETRY_EXHAUSTED', 'STAGE_OWNER_MISMATCH']
