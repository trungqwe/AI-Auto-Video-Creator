"""PW-G2: ResultRecordingDispatcher records cp_stage_runs around ActivityDispatcher.dispatch.

Synchronous: runs inside the existing to_thread of _activity_fn. Every write is its own committed transaction.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from controlplane.application.orchestration.workflows.activities import ActivityRejected
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.job_waiting import WaitReason
from controlplane.domain.statemachine import StageRunState
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns, parse_stage_run_id

DEFAULT_WAIT_REASON = WaitReason.PROVIDER_UNAVAILABLE
_STATE_BY_DISPOSITION = {'succeeded': StageRunState.SUCCEEDED, 'outcome_unknown': StageRunState.OUTCOME_UNKNOWN, 'stale': StageRunState.STALE}
_WAIT_REASONS = frozenset(reason.value for reason in WaitReason)


class ResultListener(Protocol):
    def on_result(self, request: Mapping[str, Any], result: Mapping[str, Any]) -> None: ...


def _problem(result: Mapping[str, Any]) -> dict[str, Any] | None:
    problem = result.get('problem')
    return dict(problem) if isinstance(problem, Mapping) else None


def _state_for(disposition: str, problem: Mapping[str, Any] | None) -> StageRunState | None:
    """None means waiting: CT-STATE-008 has no RUNNING to WAITING_CAPABILITY edge, so only wait_reason is written."""
    if disposition == 'waiting':
        return None
    if disposition == 'failed':
        retryable = problem is not None and problem.get('retryable') is True
        return StageRunState.FAILED_RETRYABLE if retryable else StageRunState.FAILED_FINAL
    return _STATE_BY_DISPOSITION[disposition]


def _wait_reason(problem: Mapping[str, Any] | None) -> str:
    code = problem.get('code') if problem is not None else None
    return code if isinstance(code, str) and code in _WAIT_REASONS else DEFAULT_WAIT_REASON.value


def _grant_fields(request: Mapping[str, Any]) -> tuple[str, int | None]:
    grant = request.get('execution_grant')
    if not isinstance(grant, Mapping):
        return '0', None
    epoch, generation = grant.get('recovery_epoch'), grant.get('execution_generation')
    valid_generation = isinstance(generation, int) and not isinstance(generation, bool) and generation >= 0
    return (epoch if isinstance(epoch, str) and epoch.strip() else '0'), (generation if valid_generation else None)


def _recordable_id(request: Any) -> str | None:
    if not isinstance(request, Mapping):
        return None
    stage_run_id = request.get('stage_run_id')
    try:
        parse_stage_run_id(stage_run_id)
    except OrchestrationContractError:
        return None
    return stage_run_id


class ResultRecordingDispatcher:
    def __init__(self, inner: Any, connection_factory: Callable[[], Any], clock: Callable[[], datetime.datetime], listeners: Sequence[ResultListener] = (), *, workspace_id: str) -> None:
        self._inner = inner
        self._connection_factory = connection_factory
        self._clock = clock
        self._listeners = tuple(listeners)
        self._workspace_id = workspace_id

    def dispatch(self, request: Mapping[str, Any]) -> dict[str, Any]:
        stage_run_id = _recordable_id(request)
        if stage_run_id is not None:
            self._begin(stage_run_id, request)
        try:
            result = self._inner.dispatch(request)
        except ActivityRejected as exc:
            if stage_run_id is not None:
                self._finish(stage_run_id, StageRunState.FAILED_FINAL, {'code': exc.code, 'retryable': False}, None)
            raise
        if stage_run_id is not None:
            problem = _problem(result)
            self._finish(stage_run_id, _state_for(result['disposition'], problem), problem, result.get('execution_generation'), _wait_reason(problem))
        for listener in self._listeners:
            listener.on_result(request, result)
        return result

    def _begin(self, stage_run_id: str, request: Mapping[str, Any]) -> None:
        epoch, generation = _grant_fields(request)
        with self._connection_factory() as connection:
            with connection.transaction():
                store = PostgresStageRuns(connection, self._workspace_id)
                store.ensure(stage_run_id, epoch)
                if store.status_of(stage_run_id, lock=True) == StageRunState.PENDING:
                    store.transition(stage_run_id, StageRunState.RUNNING, self._clock(), execution_generation=generation)

    def _finish(self, stage_run_id: str, state: StageRunState | None, problem: dict[str, Any] | None, generation: int | None, wait_reason: str = '') -> None:
        with self._connection_factory() as connection:
            with connection.transaction():
                store = PostgresStageRuns(connection, self._workspace_id)
                if store.status_of(stage_run_id, lock=True) != StageRunState.RUNNING:
                    return
                now = self._clock()
                if state is None:
                    store.record_wait(stage_run_id, wait_reason, now)
                else:
                    store.transition(stage_run_id, state, now, execution_generation=generation, problem=problem)


__all__ = ['DEFAULT_WAIT_REASON', 'ResultListener', 'ResultRecordingDispatcher']
