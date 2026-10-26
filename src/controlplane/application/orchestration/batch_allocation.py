"""PW-G5: AllocateJob và FinalizeBatch (G) cho vòng lô của ProductionBatchWorkflow.

Hai dịch vụ đồng bộ chạy trong luồng riêng của activity, trả kết quả dạng outcome cho service_handler của composition root; tệp này không nối handler nào.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from controlplane.application.orchestration.job_allocation import BatchTargetReachedError, JobAllocationService
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle
from controlplane.application.orchestration.workflows.activities import INVALID_ACTIVITY_REQUEST, ActivityRejected
from controlplane.application.orchestration.workflows.batch import (
    NO_MORE_JOBS_CANDIDATES_EXHAUSTED, NO_MORE_JOBS_TARGET_REACHED, REF_ALLOCATED_JOB, REF_ALLOCATION_JOB,
    REF_BATCH_FINISHED, REF_BATCH_OUTCOME, REF_BATCH_STOP_REASON, REF_JOB_CANDIDATE, REF_JOB_RESERVATION,
    REF_NO_MORE_JOBS, REF_PRODUCTION_BATCH, REF_PRODUCTION_MODE, REF_SOURCE_SET,
)
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.domain.statemachine import ForbiddenTransitionError
from controlplane.infrastructure.db.orchestration.allocation import PostgresAllocationStore


class CandidateSelectorPort(Protocol):
    def next_candidate(self, batch_id: str, production_mode: str) -> AllocationCandidate | None: ...


def _single_ref(request: Mapping[str, Any], ref_type: str) -> str:
    refs = request.get('input_refs')
    if not isinstance(refs, (list, tuple)):
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    values = [
        ref['ref_id'] for ref in refs
        if isinstance(ref, Mapping) and ref.get('ref_type') == ref_type
        and isinstance(ref.get('ref_id'), str) and ref['ref_id'].strip()
    ]
    if len(values) != 1:
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    return values[0]


def _failed(code: str, message: str) -> dict[str, Any]:
    return {'disposition': 'failed', 'output_refs': [], 'problem': {'code': code, 'retryable': False, 'message': message}}


def _no_more_jobs(reason: str) -> dict[str, Any]:
    return {'disposition': 'succeeded', 'output_refs': [{'ref_type': REF_NO_MORE_JOBS, 'ref_id': reason}]}

   


class AllocateJobService:
    def __init__(
        self, connection_factory: Callable[[], Any], selector: CandidateSelectorPort, *, workspace_id: str
    ) -> None:
        self._connection_factory = connection_factory
        self._selector = selector
        self._workspace_id = workspace_id

    def __call__(self, request: Mapping[str, Any], claims: Any = None) -> dict[str, Any]:
        batch_id = _single_ref(request, REF_PRODUCTION_BATCH)
        job_id = _single_ref(request, REF_ALLOCATION_JOB)
        mode = _single_ref(request, REF_PRODUCTION_MODE)
        with self._connection_factory() as connection:
            with connection.transaction():
                return self._allocate(PostgresAllocationStore(connection, self._workspace_id), batch_id, job_id, mode)

    def _allocate(self, store: PostgresAllocationStore, batch_id: str, job_id: str, mode: str) -> dict[str, Any]:
        reservation = store.find_reservation(job_id)
        if reservation is None:
            candidate = self._selector.next_candidate(batch_id, mode)
            if candidate is None:
                return _no_more_jobs(NO_MORE_JOBS_CANDIDATES_EXHAUSTED)
            try:
                reservation = JobAllocationService(store).allocate(batch_id, job_id, candidate)
            except BatchTargetReachedError:
                return _no_more_jobs(NO_MORE_JOBS_TARGET_REACHED)
        elif reservation.batch_id != batch_id:
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
        stored = store.find_candidate(job_id)
        if stored is None:
            return _failed('CANDIDATE_NOT_RECORDED', 'the job has no row in cp_job_candidates')
        refs = [
            {'ref_type': REF_ALLOCATED_JOB, 'ref_id': job_id},
            {'ref_type': REF_JOB_RESERVATION, 'ref_id': reservation.reservation_id},
            {'ref_type': REF_JOB_CANDIDATE, 'ref_id': stored.candidate_ref},
        ]
        if stored.source_set_ref is not None:
            refs.append({'ref_type': REF_SOURCE_SET, 'ref_id': stored.source_set_ref})
        return {'disposition': 'succeeded', 'output_refs': refs}


class FinalizeBatchService:
    def __init__(self, lifecycle: BatchLifecycle) -> None:
        self._lifecycle = lifecycle

    def __call__(self, request: Mapping[str, Any], claims: Any = None) -> dict[str, Any]:
        batch_id = _single_ref(request, REF_PRODUCTION_BATCH)
        outcome = _single_ref(request, REF_BATCH_OUTCOME)
        reason = _single_ref(request, REF_BATCH_STOP_REASON)
        try:
            changed = self._lifecycle.finish(batch_id, outcome, reason)
        except OrchestrationContractError as exc:
            return _failed(exc.code, 'the batch stop was rejected')
        except ForbiddenTransitionError:
            return _failed('FORBIDDEN_TRANSITION', 'the batch stop is not an allowed transition')
        return {
            'disposition': 'succeeded',
            'output_refs': [{'ref_type': REF_BATCH_FINISHED, 'ref_id': batch_id}],
            'metrics': {'changed': changed},
        }


__all__ = ['AllocateJobService', 'CandidateSelectorPort', 'FinalizeBatchService']

   
