from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from controlplane.application.orchestration.workflows.flow import STATUS_COMPLETED, STATUS_FAILED
from controlplane.domain.orchestration.workflow_catalog import (
    CatalogError,
    WorkflowSpec,
    get_workflow,
)

BATCH_TARGET_REACHED = 'TARGET_REACHED'
BATCH_EXHAUSTED = 'EXHAUSTED'


class BatchGateway(Protocol):
    async def run_child(self, workflow_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class BatchParams:
    batch_id: str
    target_videos: int
    jobs: tuple[Mapping[str, Any], ...]
    settings_payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> BatchParams:
        for key in ('batch_id', 'target_videos', 'jobs', 'settings'):
            if key not in payload:
                raise ValueError(f'missing batch parameter: {key}')
        batch_id = payload['batch_id']
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError('batch_id must be a non-empty string')
        target_videos = payload['target_videos']
        if isinstance(target_videos, bool) or not isinstance(target_videos, int) or target_videos <= 0:
            raise ValueError('target_videos must be a positive int')
        jobs = payload['jobs']
        if not isinstance(jobs, (list, tuple)):
            raise ValueError('jobs must be a list or tuple')
        settings = payload['settings']
        if not isinstance(settings, Mapping):
            raise ValueError('settings must be a mapping')
        return cls(
            batch_id=batch_id,
            target_videos=target_videos,
            jobs=tuple(dict(j) for j in jobs),
            settings_payload=dict(settings),
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

    async def run(self) -> dict[str, Any]:
        queue = list(self._params.jobs)
        completed = 0
        failed = 0
        index = 0
        debug_seq = 0
        children: list[dict[str, Any]] = []

        while completed < self._params.target_videos:
            while self._variant_inbox:
                queue.append(self._variant_inbox.pop(0))

            if index >= len(queue):
                break

            job = {
                **queue[index],
                'settings': dict(self._params.settings_payload),
                'child_id': f'{self._params.batch_id}:video:{index}',
                'hold_on_failure': False,
            }
            index += 1

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
        return {
            'status': final_status,
            'completed': completed,
            'failed': failed,
            'children': children,
        }


__all__ = [
    'BATCH_EXHAUSTED',
    'BATCH_TARGET_REACHED',
    'BatchGateway',
    'BatchParams',
    'ProductionBatchFlow',
]
