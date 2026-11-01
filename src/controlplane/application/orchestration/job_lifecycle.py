"""PW-G4: JobLifecycleListener (a PW-G2 ResultListener) and BatchLifecycle move job and batch rows through the state machine.

Synchronous: runs inside the existing to_thread of _activity_fn. Every call is its own committed transaction.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable, Mapping
from typing import Any

from controlplane.application.orchestration.result_recorder import DEFAULT_WAIT_REASON
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.batch_outcome import BatchOutcome
from controlplane.domain.orchestration.job_waiting import Proceed, Wait, WaitReason
from controlplane.domain.statemachine import JobState
from controlplane.infrastructure.db.orchestration.job_states import INVALID_BATCH_STATUS, PostgresBatchStates, PostgresJobStates
from controlplane.infrastructure.db.orchestration.stage_runs import parse_stage_run_id

SNAPSHOT_ACTIVITY = 'BuildProductionSnapshot'
OUTPUT_ACTIVITY = 'PersistVideoOutput'
_SETTLED = frozenset({JobState.COMPLETED, JobState.FAILED_FINAL})


def _job_id(request: Any) -> str | None:
    if not isinstance(request, Mapping):
        return None
    try:
        return parse_stage_run_id(request.get('stage_run_id'))[0]
    except OrchestrationContractError:
        return None


def _wait_reason(problem: Any) -> WaitReason:
    code = problem.get('code') if isinstance(problem, Mapping) else None
    try:
        return WaitReason(code) if isinstance(code, str) else DEFAULT_WAIT_REASON
    except ValueError:
        return DEFAULT_WAIT_REASON


def _kind(request: Mapping[str, Any], result: Mapping[str, Any]) -> tuple[str, WaitReason | None]:
    disposition, problem = result.get('disposition'), result.get('problem')
    if disposition == 'waiting':
        return 'wait', _wait_reason(problem)
    if disposition == 'failed':
        retryable = isinstance(problem, Mapping) and problem.get('retryable') is True
        return ('proceed', None) if retryable else ('failed_final', None)
    if disposition == 'succeeded' and request.get('activity_name') == SNAPSHOT_ACTIVITY:
        return 'snapshot', None
    if disposition == 'succeeded' and request.get('activity_name') == OUTPUT_ACTIVITY:
        return 'ready', None
    return 'proceed', None


def _advance(states: PostgresJobStates, job_id: str, kind: str, reason: WaitReason | None) -> None:
    current = states.state_of(job_id, lock=True)
    if current is None or current in _SETTLED:
        return
    if kind == 'snapshot':
        if current == JobState.CREATED:
            states.transition(job_id, JobState.SNAPSHOTTED)
        return
    if current == JobState.CREATED:
        return
    if current == JobState.READY_FOR_COMPLETION and kind != 'failed_final':
        return
    if current == JobState.SNAPSHOTTED:
        states.transition(job_id, JobState.ACTIVE)
    if kind == 'failed_final':
        states.transition(job_id, JobState.FAILED_FINAL)
    elif kind == 'ready':
        states.transition(job_id, JobState.READY_FOR_COMPLETION)
    elif kind == 'wait':
        states.apply_decision(job_id, Wait(reason if reason is not None else DEFAULT_WAIT_REASON))
    else:
        states.apply_decision(job_id, Proceed())


class JobLifecycleListener:
    def __init__(self, connection_factory: Callable[[], Any], *, workspace_id: str) -> None:
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id

    def on_result(self, request: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        job_id = _job_id(request)
        if job_id is None or not isinstance(result, Mapping):
            return
        kind, reason = _kind(request, result)
        with self._connection_factory() as connection:
            with connection.transaction():
                _advance(PostgresJobStates(connection, self._workspace_id), job_id, kind, reason)


class BatchLifecycle:
    def __init__(self, connection_factory: Callable[[], Any], clock: Callable[[], datetime.datetime], *, workspace_id: str) -> None:
        self._connection_factory = connection_factory
        self._clock = clock
        self._workspace_id = workspace_id

    def finish(self, batch_id: str, status: BatchOutcome | str, reason: str) -> bool:
        try:
            outcome = BatchOutcome(status)
        except ValueError:
            raise OrchestrationContractError(INVALID_BATCH_STATUS) from None
        with self._connection_factory() as connection:
            with connection.transaction():
                return PostgresBatchStates(connection, self._workspace_id).finish(batch_id, outcome, reason, self._clock())

    def start(self, batch_id: str) -> bool:
        with self._connection_factory() as connection:
            with connection.transaction():
                return PostgresBatchStates(connection, self._workspace_id).start(batch_id)


__all__ = ['BatchLifecycle', 'JobLifecycleListener', 'OUTPUT_ACTIVITY', 'SNAPSHOT_ACTIVITY']
