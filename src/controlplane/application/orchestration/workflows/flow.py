from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.application.orchestration.workflows.settings import WorkflowSettings
from controlplane.domain.orchestration.job_waiting import (
    Wait,
    evaluate_wait,
    stage_requires_desktop,
)
from controlplane.domain.orchestration.retry_policy import next_delay, should_retry
from controlplane.domain.orchestration.workflow_catalog import WorkflowSpec

STATUS_RUNNING = 'RUNNING'
STATUS_COMPLETED = 'COMPLETED'
STATUS_WAITING_CAPABILITY = 'WAITING_CAPABILITY'
STATUS_FAILED = 'FAILED'
STATUS_STAGE_OBSERVED = 'STAGE_OBSERVED'
SIGNAL_RETRY = 'retry_stage'
SIGNAL_REGENERATE = 'regenerate_from_stage'
DEBUG_STAGE_NOT_ALLOWED = 'DEBUG_STAGE_NOT_ALLOWED'


class FlowGateway(Protocol):
    async def issue_grant(
        self, stage_run_id: str, allowed_operation: str, input_fingerprint: str, worker_lease_id: str
    ) -> Mapping[str, Any]:
        ...

    async def read_capability_view(self) -> Mapping[str, Any]:
        ...

    async def execute(self, activity_name: str, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    async def sleep(self, seconds: float) -> None:
        ...


@dataclass(frozen=True)
class FlowParams:
    workflow_id: str
    workflow_run_id: str
    input_fingerprint: str
    worker_lease_id: str
    video_job_id: str | None = None
    input_refs: tuple[Mapping[str, str], ...] = ()
    item_refs: Mapping[str, Sequence[Sequence[Mapping[str, str]]]] = field(default_factory=dict)
    target_stage: str | None = None
    hold_on_failure: bool = False

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any], *, workflow_id: str, workflow_run_id: str
    ) -> FlowParams:
        for key in ('input_fingerprint', 'worker_lease_id'):
            if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError(f'missing flow parameter: {key}')
        video_job_id = payload.get('video_job_id')
        input_refs = tuple(dict(r) for r in payload.get('input_refs', ()))
        item_refs = payload.get('item_refs') or {}
        target_stage = payload.get('target_stage')
        hold_on_failure = bool(payload.get('hold_on_failure', False))
        return cls(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_fingerprint=payload['input_fingerprint'],
            worker_lease_id=payload['worker_lease_id'],
            video_job_id=video_job_id,
            input_refs=input_refs,
            item_refs=item_refs,
            target_stage=target_stage,
            hold_on_failure=hold_on_failure,
        )


class StageGraphFlow:
    def __init__(
        self,
        spec: WorkflowSpec,
        stage_activities: Mapping[str, tuple[str, ...]],
        params: FlowParams,
        settings: WorkflowSettings,
        gateway: FlowGateway,
        inbox: list,
        *,
        chain_outputs: bool,
    ) -> None:
        expected_stages = {s.stage_type for s in spec.stages}
        if set(stage_activities.keys()) != expected_stages:
            raise ValueError('stage_activities keys must match spec stages')
        for names in stage_activities.values():
            for name in names:
                if name not in BINDINGS_BY_NAME:
                    raise ValueError(f'unknown activity: {name}')

        self._spec = spec
        self._stage_activities = stage_activities
        self._params = params
        self._settings = settings
        self._gateway = gateway
        self._inbox = inbox
        self._chain_outputs = chain_outputs

        self._stage_names = frozenset(expected_stages)
        self._stages_by_name = {s.stage_type: s for s in spec.stages}
        self._gate_types: dict[str, str] = {}
        for s in spec.stages:
            if spec.auto_advance is False and params.target_stage is not None:
                self._gate_types[s.stage_type] = params.target_stage
            else:
                self._gate_types[s.stage_type] = s.stage_type

        self.status: str = STATUS_RUNNING
        self.revision: int = 1
        self.completed: list[str] = []
        self.failed_stage: str | None = None
        self.waiting_stage: str | None = None
        self.wait_reason: str | None = None
        self.unbound: list[str] = []
        self.attempts: dict[str, int] = {}
        self.output_refs: dict[str, list[dict[str, str]]] = {}
        self.last_problem: dict[str, Any] | None = None
        self.rejected_signals: list[dict[str, Any]] = []

    def signal_retry_stage(self, stage_type: str) -> None:
        self._inbox.append((SIGNAL_RETRY, stage_type))

    def signal_regenerate_from_stage(self, stage_type: str) -> None:
        self._inbox.append((SIGNAL_REGENERATE, stage_type))

    def _downstream(self, stage: str) -> set[str]:
        affected = {stage}
        changed = True
        while changed:
            changed = False
            for s in self._spec.stages:
                if s.stage_type not in affected and any(dep in affected for dep in s.depends_on):
                    affected.add(s.stage_type)
                    changed = True
        return affected

    def _next_stage(self) -> str | None:
        for stage in self._spec.stages:
            if stage.stage_type not in self.completed:
                if all(dep in self.completed for dep in stage.depends_on):
                    return stage.stage_type
        return None

    def _prior_refs(self) -> list[dict[str, str]]:
        if not self._chain_outputs:
            return []
        seen = set()
        merged: list[dict[str, str]] = []
        for refs in self.output_refs.values():
            for ref in refs:
                key = (ref.get('ref_type'), ref.get('ref_id'))
                if key not in seen:
                    seen.add(key)
                    merged.append(dict(ref))
        return merged

    def snapshot(self) -> dict[str, Any]:
        return {
            'workflow_name': self._spec.name,
            'status': self.status,
            'revision': self.revision,
            'completed': list(self.completed),
            'failed_stage': self.failed_stage,
            'waiting_stage': self.waiting_stage,
            'wait_reason': self.wait_reason,
            'unbound': list(self.unbound),
            'attempts': dict(self.attempts),
            'output_refs': {k: [dict(r) for r in v] for k, v in self.output_refs.items()},
            'last_problem': dict(self.last_problem) if self.last_problem is not None else None,
            'rejected_signals': list(self.rejected_signals),
        }

    def _apply_inbox(self) -> None:
        pending = list(self._inbox)
        self._inbox.clear()
        for kind, stage in pending:
            if self.status in (STATUS_COMPLETED, STATUS_STAGE_OBSERVED) or stage not in self._stage_names:
                self.rejected_signals.append({'signal': kind, 'stage': stage, 'code': 'SIGNAL_REJECTED'})
                continue
            if kind == SIGNAL_RETRY:
                if self.failed_stage != stage:
                    self.rejected_signals.append(
                        {'signal': kind, 'stage': stage, 'code': 'RETRY_NOT_APPLICABLE'}
                    )
                    continue
                self.failed_stage = None
                self.status = STATUS_RUNNING
            elif kind == SIGNAL_REGENERATE:
                spec_stage = self._stages_by_name.get(stage)
                if spec_stage and any(dep not in self.completed for dep in spec_stage.depends_on):
                    self.rejected_signals.append(
                        {'signal': kind, 'stage': stage, 'code': 'DEPENDENCY_NOT_COMPLETED'}
                    )
                    continue
                stale = self._downstream(stage)
                self.completed = [s for s in self.completed if s not in stale]
                for s in stale:
                    self.output_refs.pop(s, None)
                self.revision += 1
                self.failed_stage = None
                self.status = STATUS_RUNNING

    async def advance(self) -> str:
        self._apply_inbox()
        while True:
            if self.status in (STATUS_COMPLETED, STATUS_STAGE_OBSERVED, STATUS_FAILED):
                return self.status
            stage = self._next_stage()
            if stage is None:
                self.status = STATUS_COMPLETED
                return self.status
            gate_type = self._gate_types[stage]
            if stage_requires_desktop(gate_type):
                decision = evaluate_wait(gate_type, await self._gateway.read_capability_view())
                if isinstance(decision, Wait):
                    self.status = STATUS_WAITING_CAPABILITY
                    self.waiting_stage = stage
                    self.wait_reason = decision.reason.value
                    return self.status
                self.status = STATUS_RUNNING
                self.waiting_stage = None
                self.wait_reason = None
            if not await self._run_stage(stage):
                self.failed_stage = stage
                self.status = STATUS_FAILED
                return self.status
            self.completed.append(stage)
            if not self._spec.auto_advance:
                self.status = STATUS_STAGE_OBSERVED
                return self.status

    async def _run_stage(self, stage: str) -> bool:
        names = self._stage_activities[stage]
        if not names:
            if stage not in self.unbound:
                self.unbound.append(stage)
            return True
        for name in names:
            item_runs = self._params.item_refs.get(name) or ((),)
            for index, refs in enumerate(item_runs):
                ok = await self._run_activity(stage, BINDINGS_BY_NAME[name], index, refs)
                if not ok:
                    return False
        return True

    async def _run_activity(
        self,
        stage: str,
        binding: Any,
        index: int,
        refs: Sequence[Mapping[str, str]],
    ) -> bool:
        owner = self._params.video_job_id or self._params.workflow_id
        stage_run_id = f'{owner}:{stage}:r{self.revision}'
        operation_key = f'{self._params.workflow_id}:{stage}:{binding.name}:{index}:r{self.revision}'
        input_refs = [dict(r) for r in (*self._params.input_refs, *refs)] + self._prior_refs()
        attempt = 1
        while True:
            self.attempts[stage] = self.attempts.get(stage, 0) + 1
            request: dict[str, Any] = {
                'workflow_id': self._params.workflow_id,
                'workflow_run_id': self._params.workflow_run_id,
                'stage_run_id': stage_run_id,
                'activity_name': binding.name,
                'activity_version': '1',
                'input_refs': input_refs,
                'operation_key': operation_key,
                'capability_requirements': {'task_queue': binding.queue.value},
                'retry_policy_ref': self._settings.retry_policy_ref,
            }
            if self._params.video_job_id is not None:
                request['video_job_id'] = self._params.video_job_id

            try:
                claims = await self._gateway.issue_grant(
                    stage_run_id, binding.name, self._params.input_fingerprint, self._params.worker_lease_id
                )
                request['execution_grant'] = dict(claims)
                result = await self._gateway.execute(binding.name, request)
            except Exception as exc:
                self.last_problem = {
                    'activity': binding.name,
                    'disposition': 'exception',
                    'code': type(exc).__name__,
                }
                return False

            disposition = result.get('disposition')
            if disposition == 'succeeded':
                self.output_refs.setdefault(stage, []).extend(
                    dict(r) for r in result.get('output_refs', ())
                )
                self.last_problem = None
                return True

            problem = result.get('problem') or {}
            self.last_problem = {
                'activity': binding.name,
                'disposition': disposition,
                'code': problem.get('code'),
            }
            retryable = disposition == 'stale' or problem.get('retryable') is True
            if disposition == 'outcome_unknown' or not retryable or not should_retry(attempt, True, self._settings.retry):
                return False
            if disposition != 'stale':
                await self._gateway.sleep(next_delay(attempt, self._settings.retry))
            attempt += 1


def build_debug_flow(
    spec: WorkflowSpec,
    video_stage_activities: Mapping[str, tuple[str, ...]],
    params: FlowParams,
    settings: WorkflowSettings,
    gateway: FlowGateway,
    inbox: list,
) -> StageGraphFlow:
    if params.target_stage not in video_stage_activities or params.target_stage == 'complete':
        raise ValueError(DEBUG_STAGE_NOT_ALLOWED)
    return StageGraphFlow(
        spec,
        {'debug_observe': video_stage_activities[params.target_stage]},
        params,
        settings,
        gateway,
        inbox,
        chain_outputs=False,
    )


__all__ = [
    'DEBUG_STAGE_NOT_ALLOWED',
    'FlowGateway',
    'FlowParams',
    'SIGNAL_REGENERATE',
    'SIGNAL_RETRY',
    'STATUS_COMPLETED',
    'STATUS_FAILED',
    'STATUS_RUNNING',
    'STATUS_STAGE_OBSERVED',
    'STATUS_WAITING_CAPABILITY',
    'StageGraphFlow',
    'build_debug_flow',
]
