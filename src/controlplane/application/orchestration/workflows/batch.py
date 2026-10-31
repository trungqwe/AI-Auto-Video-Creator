from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.flow import STATUS_COMPLETED, STATUS_FAILED
from controlplane.application.orchestration.workflows.settings import WorkflowSettings
from controlplane.domain.orchestration.workflow_catalog import (
    CatalogError,
    WorkflowSpec,
    get_workflow,
)

BATCH_TARGET_REACHED = 'TARGET_REACHED'
BATCH_EXHAUSTED = 'EXHAUSTED'
BATCH_OUTCOMES = {BATCH_TARGET_REACHED: 'COMPLETED_TARGET', BATCH_EXHAUSTED: 'COMPLETED_EXHAUSTED'}
DEFAULT_PRODUCTION_MODE = 'single_article'
ACTIVITY_ALLOCATE_JOB = 'AllocateJob'
ACTIVITY_FINALIZE_BATCH = 'FinalizeBatch'
REF_PRODUCTION_BATCH = 'production_batch'
REF_ALLOCATION_JOB = 'allocation_job'
REF_PRODUCTION_MODE = 'production_mode'
REF_BATCH_OUTCOME = 'batch_outcome'
REF_BATCH_STOP_REASON = 'batch_stop_reason'
REF_ALLOCATED_JOB = 'allocated_job'
REF_JOB_RESERVATION = 'job_reservation'
REF_JOB_CANDIDATE = 'job_candidate'
REF_SOURCE_SET = 'source_set'
REF_NO_MORE_JOBS = 'no_more_jobs'
REF_BATCH_FINISHED = 'batch_finished'
NO_MORE_JOBS_TARGET_REACHED = 'target_reached'
NO_MORE_JOBS_CANDIDATES_EXHAUSTED = 'candidates_exhausted'


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def candidate_fingerprint(candidate_ref: str, source_set_ref: str | None) -> str:
    return _sha256_text(json.dumps([candidate_ref, source_set_ref], separators=(',', ':'), ensure_ascii=False))


class ChildHandle(Protocol):
    def done(self) -> bool:
        ...

    def result(self) -> Mapping[str, Any]:
        ...

    def cancel(self) -> Any:
        ...


class BatchGateway(Protocol):
    async def run_child(self, workflow_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    async def start_child(self, workflow_name: str, payload: Mapping[str, Any]) -> ChildHandle:
        ...

    async def wait_first(self, handles: Sequence[ChildHandle]) -> None:
        ...

    async def issue_grant(
        self, stage_run_id: str, allowed_operation: str, input_fingerprint: str, worker_lease_id: str
    ) -> Mapping[str, Any]:
        ...

    async def execute(self, activity_name: str, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class BatchParams:
    batch_id: str
    target_videos: int
    jobs: tuple[Mapping[str, Any], ...]
    settings_payload: Mapping[str, Any]
    worker_lease_id: str = ''
    production_mode: str = DEFAULT_PRODUCTION_MODE
    workflow_run_id: str = ''
    max_concurrent_videos: int = 1

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> BatchParams:
        for key in ('batch_id', 'target_videos', 'settings'):
            if key not in payload:
                raise ValueError(f'missing batch parameter: {key}')
        batch_id = payload['batch_id']
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError('batch_id must be a non-empty string')
        target_videos = payload['target_videos']
        if isinstance(target_videos, bool) or not isinstance(target_videos, int) or target_videos <= 0:
            raise ValueError('target_videos must be a positive int')
        jobs = payload.get('jobs', ())
        if not isinstance(jobs, (list, tuple)):
            raise ValueError('jobs must be a list or tuple')
        settings = payload['settings']
        if not isinstance(settings, Mapping):
            raise ValueError('settings must be a mapping')
        lease = payload.get('worker_lease_id', '')
        if not isinstance(lease, str):
            raise ValueError('worker_lease_id must be a string')
        if not jobs and not lease.strip():
            raise ValueError('missing batch parameter: worker_lease_id')
        mode = payload.get('production_mode', DEFAULT_PRODUCTION_MODE)
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError('production_mode must be a non-empty string')
        run_id = payload.get('workflow_run_id', '')
        if not isinstance(run_id, str):
            raise ValueError('workflow_run_id must be a string')
        concurrency = payload.get('max_concurrent_videos', 1)
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency <= 0:
            raise ValueError('max_concurrent_videos must be a positive int')
        return cls(
            batch_id=batch_id,
            target_videos=target_videos,
            jobs=tuple(dict(j) for j in jobs),
            settings_payload=dict(settings),
            worker_lease_id=lease,
            production_mode=mode,
            workflow_run_id=run_id,
            max_concurrent_videos=concurrency,
        )


class ProductionBatchFlow:
    def __init__(
        self,
        spec: WorkflowSpec,
        params: BatchParams,
        gateway: BatchGateway,
        variant_inbox: list,
        debug_inbox: list,
    ) -> None:
        if (
            'VideoProductionWorkflow' not in spec.child_workflows
            or get_workflow('VideoProductionWorkflow').isolated_child is not True
        ):
            raise CatalogError('CHILD_NOT_ISOLATED')
        self._spec = spec
        self._params = params
        self._gateway = gateway
        self._variant_inbox = variant_inbox
        self._debug_inbox = debug_inbox
        self._settings = WorkflowSettings.from_payload(params.settings_payload)
        self._stop_reason: str | None = None
        self._problem: dict[str, Any] | None = None

    async def run(self) -> dict[str, Any]:
        limit = self._params.max_concurrent_videos
        if limit <= 1:
            return await self._run_sequential()
        return await self._run_concurrent(limit)

    async def _run_sequential(self) -> dict[str, Any]:
        queue = list(self._params.jobs)
        static_jobs = bool(queue)
        completed = 0
        failed = 0
        queued = 0
        allocated = 0
        video_seq = 0
        debug_seq = 0
        children: list[dict[str, Any]] = []

        while completed < self._params.target_videos:
            while self._variant_inbox:
                queue.append(self._variant_inbox.pop(0))

            if queued < len(queue):
                base = queue[queued]
                queued += 1
            elif static_jobs:
                break
            else:
                allocation = await self._allocate(allocated + 1)
                if allocation is None:
                    break
                allocated += 1
                base = allocation

            job = {
                **base,
                'settings': dict(self._params.settings_payload),
                'child_id': f'{self._params.batch_id}:video:{video_seq}',
                'hold_on_failure': False,
            }
            video_seq += 1

            try:
                out = await self._gateway.run_child('VideoProductionWorkflow', job)
                status = out.get('status')
            except Exception:
                status = STATUS_FAILED

            if status == STATUS_COMPLETED:
                completed += 1
            else:
                failed += 1
            children.append({'child_id': job['child_id'], 'status': status})

            debug_items = list(self._debug_inbox)
            self._debug_inbox.clear()
            for payload in debug_items:
                child_id = f'{self._params.batch_id}:debug:{debug_seq}'
                debug_seq += 1
                try:
                    out = await self._gateway.run_child(
                        'DebugStageWorkflow',
                        {
                            **payload,
                            'settings': dict(self._params.settings_payload),
                            'child_id': child_id,
                        },
                    )
                    d_status = out.get('status')
                except Exception:
                    d_status = STATUS_FAILED
                children.append({'child_id': child_id, 'status': d_status})

        final_status = (
            BATCH_TARGET_REACHED if completed >= self._params.target_videos else BATCH_EXHAUSTED
        )
        finalized = await self._finalize(final_status, completed, failed)
        return {
            'status': final_status,
            'completed': completed,
            'failed': failed,
            'allocated': allocated,
            'finalized': finalized,
            'problem': self._problem,
            'children': children,
        }

    async def _run_concurrent(self, limit: int) -> dict[str, Any]:
        queue = list(self._params.jobs)
        static_jobs = bool(queue)
        completed = 0
        failed = 0
        queued = 0
        allocated = 0
        video_seq = 0
        debug_seq = 0
        children: list[dict[str, Any]] = []
        running: list[tuple[str, ChildHandle]] = []
        stopped = False

        try:
            while True:
                while (
                    not stopped
                    and len(running) < limit
                    and completed + len(running) < self._params.target_videos
                ):
                    while self._variant_inbox:
                        queue.append(self._variant_inbox.pop(0))

                    if queued < len(queue):
                        base = queue[queued]
                        queued += 1
                    elif static_jobs:
                        stopped = True
                        break
                    else:
                        allocation = await self._allocate(allocated + 1)
                        if allocation is None:
                            stopped = True
                            break
                        allocated += 1
                        base = allocation

                    job = {
                        **base,
                        'settings': dict(self._params.settings_payload),
                        'child_id': f'{self._params.batch_id}:video:{video_seq}',
                        'hold_on_failure': False,
                    }
                    video_seq += 1

                    try:
                        handle = await self._gateway.start_child('VideoProductionWorkflow', job)
                    except Exception:
                        failed += 1
                        children.append({'child_id': job['child_id'], 'status': STATUS_FAILED})
                        continue
                    running.append((job['child_id'], handle))

                if not running:
                    break

                await self._gateway.wait_first([handle for _, handle in running])
                pending: list[tuple[str, ChildHandle]] = []
                for child_id, handle in running:
                    if not handle.done():
                        pending.append((child_id, handle))
                        continue
                    try:
                        status = handle.result().get('status')
                    except Exception:
                        status = STATUS_FAILED
                    if status == STATUS_COMPLETED:
                        completed += 1
                    else:
                        failed += 1
                    children.append({'child_id': child_id, 'status': status})
                running = pending

                debug_items = list(self._debug_inbox)
                self._debug_inbox.clear()
                for payload in debug_items:
                    child_id = f'{self._params.batch_id}:debug:{debug_seq}'
                    debug_seq += 1
                    try:
                        out = await self._gateway.run_child(
                            'DebugStageWorkflow',
                            {
                                **payload,
                                'settings': dict(self._params.settings_payload),
                                'child_id': child_id,
                            },
                        )
                        d_status = out.get('status')
                    except Exception:
                        d_status = STATUS_FAILED
                    children.append({'child_id': child_id, 'status': d_status})
        except BaseException:
            for _, handle in running:
                handle.cancel()
            raise

        final_status = (
            BATCH_TARGET_REACHED if completed >= self._params.target_videos else BATCH_EXHAUSTED
        )
        finalized = await self._finalize(final_status, completed, failed)
        return {
            'status': final_status,
            'completed': completed,
            'failed': failed,
            'allocated': allocated,
            'finalized': finalized,
            'problem': self._problem,
            'children': children,
        }

    def _lease(self) -> str:
        return self._params.worker_lease_id or self._params.batch_id

    async def _call(
        self, activity_name: str, stage: str, revision: int, input_refs: list[dict[str, str]]
    ) -> Mapping[str, Any] | None:
        batch_id = self._params.batch_id
        stage_run_id = f'{batch_id}:{stage}:r{revision}'
        operation_key = f'{batch_id}:{stage}:{activity_name}:{revision}'
        try:
            claims = await self._gateway.issue_grant(
                stage_run_id, activity_name, _sha256_text(operation_key), self._lease()
            )
            result = await self._gateway.execute(
                activity_name,
                {
                    'workflow_id': batch_id,
                    'workflow_run_id': self._params.workflow_run_id,
                    'stage_run_id': stage_run_id,
                    'activity_name': activity_name,
                    'activity_version': '1',
                    'input_refs': input_refs,
                    'operation_key': operation_key,
                    'capability_requirements': {'task_queue': BINDINGS_BY_NAME[activity_name].queue.value},
                    'retry_policy_ref': self._settings.retry_policy_ref,
                    'execution_grant': dict(claims),
                },
            )
        except Exception as exc:
            self._problem = {'activity': activity_name, 'disposition': 'exception', 'code': type(exc).__name__}
            return None
        if result.get('disposition') != 'succeeded':
            problem = result.get('problem')
            self._problem = {
                'activity': activity_name,
                'disposition': result.get('disposition'),
                'code': problem.get('code') if isinstance(problem, Mapping) else None,
            }
            return None
        return result

    async def _allocate(self, ordinal: int) -> dict[str, Any] | None:
        batch_id = self._params.batch_id
        job_id = f'{batch_id}:job:{ordinal}'
        result = await self._call(
            ACTIVITY_ALLOCATE_JOB,
            'allocate',
            ordinal,
            [
                {'ref_type': REF_PRODUCTION_BATCH, 'ref_id': batch_id},
                {'ref_type': REF_ALLOCATION_JOB, 'ref_id': job_id},
                {'ref_type': REF_PRODUCTION_MODE, 'ref_id': self._params.production_mode},
            ],
        )
        if result is None:
            self._stop_reason = f"allocation_failed: {(self._problem or {}).get('code')}"
            return None
        outputs: dict[str, str] = {}
        for ref in result.get('output_refs', ()):
            if isinstance(ref, Mapping):
                outputs.setdefault(str(ref.get('ref_type')), str(ref.get('ref_id')))
        if REF_NO_MORE_JOBS in outputs:
            self._stop_reason = f'no_more_jobs: {outputs[REF_NO_MORE_JOBS]}'
            return None
        candidate_ref = outputs.get(REF_JOB_CANDIDATE)
        if outputs.get(REF_ALLOCATED_JOB) != job_id or not candidate_ref:
            self._problem = {'activity': ACTIVITY_ALLOCATE_JOB, 'disposition': 'succeeded', 'code': 'ALLOCATION_RESULT_INVALID'}
            self._stop_reason = 'allocation_failed: ALLOCATION_RESULT_INVALID'
            return None
        source_set_ref = outputs.get(REF_SOURCE_SET)
        input_refs = [{'ref_type': REF_JOB_CANDIDATE, 'ref_id': candidate_ref}]
        if source_set_ref:
            input_refs.append({'ref_type': REF_SOURCE_SET, 'ref_id': source_set_ref})
        return {
            'video_job_id': job_id,
            'input_fingerprint': candidate_fingerprint(candidate_ref, source_set_ref),
            'worker_lease_id': self._lease(),
            'input_refs': input_refs,
        }

    async def _finalize(self, status: str, completed: int, failed: int) -> bool:
        reason = f'{status}: completed={completed} failed={failed}'
        if self._stop_reason:
            reason = f'{reason}; {self._stop_reason}'
        result = await self._call(
            ACTIVITY_FINALIZE_BATCH,
            'run_videos',
            1,
            [
                {'ref_type': REF_PRODUCTION_BATCH, 'ref_id': self._params.batch_id},
                {'ref_type': REF_BATCH_OUTCOME, 'ref_id': BATCH_OUTCOMES[status]},
                {'ref_type': REF_BATCH_STOP_REASON, 'ref_id': reason},
            ],
        )
        return result is not None


__all__ = [
    'ACTIVITY_ALLOCATE_JOB',
    'ACTIVITY_FINALIZE_BATCH',
    'BATCH_EXHAUSTED',
    'BATCH_OUTCOMES',
    'BATCH_TARGET_REACHED',
    'BatchGateway',
    'BatchParams',
    'ChildHandle',
    'DEFAULT_PRODUCTION_MODE',
    'NO_MORE_JOBS_CANDIDATES_EXHAUSTED',
    'NO_MORE_JOBS_TARGET_REACHED',
    'ProductionBatchFlow',
    'REF_ALLOCATED_JOB',
    'REF_ALLOCATION_JOB',
    'REF_BATCH_FINISHED',
    'REF_BATCH_OUTCOME',
    'REF_BATCH_STOP_REASON',
    'REF_JOB_CANDIDATE',
    'REF_JOB_RESERVATION',
    'REF_NO_MORE_JOBS',
    'REF_PRODUCTION_BATCH',
    'REF_PRODUCTION_MODE',
    'REF_SOURCE_SET',
    'candidate_fingerprint',
]
