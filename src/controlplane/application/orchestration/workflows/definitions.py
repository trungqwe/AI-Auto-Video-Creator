from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy as TemporalRetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from controlplane.application.orchestration.workflows.activities import (
        BINDINGS_BY_NAME,
        INTERNAL_ACTIVITIES,
        STAGE_ACTIVITIES_BY_WORKFLOW,
        VIDEO_STAGE_ACTIVITIES,
    )
    from controlplane.application.orchestration.workflows.batch import (
        BatchParams,
        ProductionBatchFlow,
    )
    from controlplane.application.orchestration.workflows.flow import (
        SIGNAL_REGENERATE,
        SIGNAL_RETRY,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_STAGE_OBSERVED,
        FlowParams,
        StageGraphFlow,
        build_debug_flow,
    )
    from controlplane.application.orchestration.workflows.settings import (
        WorkflowSettings,
        start_to_close_for,
    )
    from controlplane.domain.orchestration.workflow_catalog import TaskQueue, get_workflow

JOB_TERMINAL_PATCH_ID = 'job-terminal-on-failure'
BATCH_CONCURRENCY_PATCH_ID = 'batch-concurrent-videos'


class TemporalGateway:
    def __init__(self, settings: WorkflowSettings) -> None:
        self._settings = settings
        self._retry = TemporalRetryPolicy(
            initial_interval=timedelta(seconds=settings.retry.initial_delay_seconds),
            backoff_coefficient=settings.retry.multiplier,
            maximum_interval=timedelta(seconds=settings.retry.max_delay_seconds),
            maximum_attempts=settings.retry.max_attempts,
        )

    async def _call(self, name: str, queue: TaskQueue, argument: Any) -> Any:
        return await workflow.execute_activity(
            name,
            argument,
            task_queue=queue.value,
            start_to_close_timeout=timedelta(
                seconds=start_to_close_for(self._settings, queue)
            ),
            retry_policy=self._retry,
        )

    async def issue_grant(
        self,
        stage_run_id: str,
        allowed_operation: str,
        input_fingerprint: str,
        worker_lease_id: str,
    ) -> Any:
        return await self._call(
            'IssueExecutionGrant',
            INTERNAL_ACTIVITIES['IssueExecutionGrant'],
            {
                'stage_run_id': stage_run_id,
                'allowed_operation': allowed_operation,
                'input_fingerprint': input_fingerprint,
                'worker_lease_id': worker_lease_id,
            },
        )

    async def read_capability_view(self) -> Any:
        return await self._call(
            'ReadCapabilityView',
            INTERNAL_ACTIVITIES['ReadCapabilityView'],
            {},
        )

    async def fail_video_job(self, request: Any) -> Any:
        return await self._call(
            'FailVideoJob',
            INTERNAL_ACTIVITIES['FailVideoJob'],
            dict(request),
        )

    async def execute(self, name: str, request: Any) -> Any:
        return await self._call(name, BINDINGS_BY_NAME[name].queue, dict(request))

    async def sleep(self, seconds: float) -> None:
        await workflow.sleep(timedelta(seconds=seconds))

    def patched(self, patch_id: str) -> bool:
        return workflow.patched(patch_id)

    async def run_child(self, workflow_name: str, payload: Any) -> Any:
        return await workflow.execute_child_workflow(
            workflow_name,
            payload,
            id=payload['child_id'],
            task_queue=TaskQueue.CONTROL_WORKFLOWS.value,
        )

    async def start_child(self, workflow_name: str, payload: Any) -> Any:
        return await workflow.start_child_workflow(
            workflow_name,
            payload,
            id=payload['child_id'],
            task_queue=TaskQueue.CONTROL_WORKFLOWS.value,
        )

    async def wait_first(self, handles: Any) -> None:
        await workflow.wait(list(handles), return_when='FIRST_COMPLETED')


async def _drive(
    flow: StageGraphFlow,
    inbox: list,
    params: FlowParams,
    settings: WorkflowSettings,
    gateway: TemporalGateway,
) -> dict[str, Any]:
    while True:
        status = await flow.advance()
        if status in (STATUS_COMPLETED, STATUS_STAGE_OBSERVED):
            break
        if status == STATUS_FAILED:
            if not params.hold_on_failure:
                break
            await workflow.wait_condition(lambda: bool(inbox))
        else:
            try:
                await workflow.wait_condition(
                    lambda: bool(inbox),
                    timeout=timedelta(seconds=settings.capability_poll_seconds),
                )
            except TimeoutError:
                pass
    return flow.snapshot()


async def _fail_video_job(gateway: TemporalGateway, params: FlowParams, snapshot: dict[str, Any]) -> None:
    request = {
        'video_job_id': params.video_job_id,
        'stage_run_id': f"{params.video_job_id}:{snapshot['failed_stage']}:r{snapshot['revision']}",
        'problem': dict(snapshot['last_problem'] or {}),
    }
    try:
        await gateway.fail_video_job(request)
    except ActivityError as exc:
        workflow.logger.warning('FailVideoJob did not finish for %s: %s', params.video_job_id, exc)


async def _run_stage_graph(name: str, payload: dict[str, Any], inbox: list) -> dict[str, Any]:
    info = workflow.info()
    settings = WorkflowSettings.from_payload(payload['settings'])
    params = FlowParams.from_payload(
        payload, workflow_id=info.workflow_id, workflow_run_id=info.run_id
    )
    spec = get_workflow(name)
    gateway = TemporalGateway(settings)
    if name == 'DebugStageWorkflow':
        flow = build_debug_flow(spec, VIDEO_STAGE_ACTIVITIES, params, settings, gateway, inbox)
    else:
        flow = StageGraphFlow(
            spec,
            STAGE_ACTIVITIES_BY_WORKFLOW[name],
            params,
            settings,
            gateway,
            inbox,
            chain_outputs=(name == 'VideoProductionWorkflow'),
        )
    snapshot = await _drive(flow, inbox, params, settings, gateway)
    if (
        name == 'VideoProductionWorkflow'
        and params.video_job_id is not None
        and snapshot['status'] == STATUS_FAILED
        and snapshot['failed_stage'] is not None
        and not params.hold_on_failure
        and workflow.patched(JOB_TERMINAL_PATCH_ID)
    ):
        await _fail_video_job(gateway, params, snapshot)
    return snapshot


@workflow.defn(name='DailyCollectionWorkflow')
class DailyCollectionWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await _run_stage_graph('DailyCollectionWorkflow', payload, self._inbox)


@workflow.defn(name='ContentEnrichmentWorkflow')
class ContentEnrichmentWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await _run_stage_graph('ContentEnrichmentWorkflow', payload, self._inbox)


@workflow.defn(name='MaintenanceWorkflow')
class MaintenanceWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await _run_stage_graph('MaintenanceWorkflow', payload, self._inbox)


@workflow.defn(name='VideoProductionWorkflow')
class VideoProductionWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []

    @workflow.signal(name='RetryStage')
    def retry_stage(self, stage_type: str) -> None:
        self._inbox.append((SIGNAL_RETRY, stage_type))

    @workflow.signal(name='RegenerateFromStage')
    def regenerate_from_stage(self, stage_type: str) -> None:
        self._inbox.append((SIGNAL_REGENERATE, stage_type))

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await _run_stage_graph('VideoProductionWorkflow', payload, self._inbox)


@workflow.defn(name='DebugStageWorkflow')
class DebugStageWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await _run_stage_graph('DebugStageWorkflow', payload, self._inbox)


@workflow.defn(name='ProductionBatchWorkflow')
class ProductionBatchWorkflow:
    def __init__(self) -> None:
        self._inbox: list = []
        self._variants: list = []
        self._debug: list = []

    @workflow.signal(name='CreateNewVariant')
    def create_new_variant(self, job_payload: dict) -> None:
        self._variants.append(dict(job_payload))

    @workflow.signal(name='RunDebugStage')
    def run_debug_stage(self, debug_payload: dict) -> None:
        self._debug.append(dict(debug_payload))

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = WorkflowSettings.from_payload(payload['settings'])
        info = workflow.info()
        params = BatchParams.from_payload(
            {**payload, 'batch_id': info.workflow_id, 'workflow_run_id': info.run_id}
        )
        if params.max_concurrent_videos > 1 and not workflow.patched(BATCH_CONCURRENCY_PATCH_ID):
            params = replace(params, max_concurrent_videos=1)
        flow = ProductionBatchFlow(
            get_workflow('ProductionBatchWorkflow'),
            params,
            TemporalGateway(settings),
            self._variants,
            self._debug,
        )
        return await flow.run()


__all__ = [
    'ContentEnrichmentWorkflow',
    'DailyCollectionWorkflow',
    'DebugStageWorkflow',
    'MaintenanceWorkflow',
    'ProductionBatchWorkflow',
    'TemporalGateway',
    'VideoProductionWorkflow',
]
