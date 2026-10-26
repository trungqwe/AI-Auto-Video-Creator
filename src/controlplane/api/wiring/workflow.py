"""CP-6-WORKFLOW: wires workflow activities into the composition root; BL-CV-10 and BL-CV-06 stay PENDING (src/main.py does not call this module yet)."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import datetime
from types import MappingProxyType
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from controlplane.application.orchestration.grant_runtime import ExecutionGrantCurrency
from controlplane.application.orchestration.workflows.activities import (
    ACTIVITY_BINDINGS,
    ACTIVITY_SERVICE_UNBOUND,
    INTERNAL_ACTIVITIES,
    ActivityDispatcher,
    ActivityHandler,
    ActivityRejected,
    claims_to_payload,
    to_execution_grant,
    MISSING_EXECUTION_GRANT,
)
from controlplane.application.orchestration.workflows.definitions import (
    ContentEnrichmentWorkflow,
    DailyCollectionWorkflow,
    DebugStageWorkflow,
    MaintenanceWorkflow,
    ProductionBatchWorkflow,
    VideoProductionWorkflow,
)
from controlplane.application.orchestration.workflows.settings import (
    WorkflowSettings,
    schedule_state,
    settings_from_parameters,
)
from controlplane.domain.orchestration.fencing import GrantClaims
from creative.worker.activity_handler import handle_activity as handle_creative_activity
from ingestion.application.activity_handler import handle_resolve_activity
from render.worker.activity_handler import handle_activity as handle_render_activity
from source_ingestion.worker.activity_handler import handle_collect_source_activity
from voice.worker.activity_handler import handle_activity as handle_voice_activity


def collect_source_handler(deps: Any, clock: Callable[[], datetime.datetime]) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        return handle_collect_source_activity(request, claims, deps, clock)

    return handler


def resolve_document_handler(
    deps: Any,
    package_loader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    clock: Callable[[], datetime.datetime],
) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        return handle_resolve_activity(request, package_loader, deps, clock)

    return handler


def creative_handler(deps: Any, *, workspace_id: str) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        job_id = request.get('video_job_id')
        if not isinstance(job_id, str) or not job_id.strip():
            raise ActivityRejected('INVALID_ACTIVITY_REQUEST')
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        grant = to_execution_grant(claims, workspace_id=workspace_id, job_id=job_id)
        return handle_creative_activity(request, grant, deps)

    return handler


def voice_handler(deps: Any, *, workspace_id: str) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        job_id = request.get('video_job_id')
        if not isinstance(job_id, str) or not job_id.strip():
            raise ActivityRejected('INVALID_ACTIVITY_REQUEST')
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        grant = to_execution_grant(claims, workspace_id=workspace_id, job_id=job_id)
        return handle_voice_activity(request, grant, deps)

    return handler


def render_handler(deps: Any, *, workspace_id: str) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        job_id = request.get('video_job_id')
        if not isinstance(job_id, str) or not job_id.strip():
            raise ActivityRejected('INVALID_ACTIVITY_REQUEST')
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        grant = to_execution_grant(claims, workspace_id=workspace_id, job_id=job_id)
        return handle_render_activity(request, grant, deps)

    return handler


def service_handler(
    service: Callable[[Mapping[str, Any], GrantClaims], Mapping[str, Any]],
    clock: Callable[[], datetime.datetime],
) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        outcome = service(request, claims)
        now_utc = clock().astimezone(datetime.timezone.utc).replace(microsecond=0)
        completed_at = now_utc.isoformat().replace('+00:00', 'Z')
        result: dict[str, Any] = {
            'stage_run_id': claims.stage_run_id,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
            'disposition': outcome['disposition'],
            'output_refs': list(outcome.get('output_refs', ())),
            'completed_at': completed_at,
        }
        if 'metrics' in outcome:
            result['metrics'] = outcome['metrics']
        if 'warnings' in outcome:
            result['warnings'] = outcome['warnings']
        if 'problem' in outcome:
            result['problem'] = outcome['problem']
        return result

    return handler


def unbound_handler(clock: Callable[[], datetime.datetime]) -> ActivityHandler:
    def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        now_utc = clock().astimezone(datetime.timezone.utc).replace(microsecond=0)
        completed_at = now_utc.isoformat().replace('+00:00', 'Z')
        return {
            'stage_run_id': claims.stage_run_id,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
            'disposition': 'failed',
            'output_refs': [],
            'completed_at': completed_at,
            'problem': {
                'code': ACTIVITY_SERVICE_UNBOUND,
                'retryable': False,
                'message': 'the service for this activity is not bound in this composition',
            },
        }

    return handler


# Compares GrantClaims only; production wiring uses ExecutionGrantCurrency (grant_runtime), which compares an ExecutionGrant with the stored grant.
class StoreBackedClaimsCurrency:
    def __init__(self, store: Any, clock: Callable[[], datetime.datetime]) -> None:
        self._store = store
        self._clock = clock

    def is_grant_current(self, grant: GrantClaims) -> bool:
        active = self._store.active_grant(grant.stage_run_id, self._clock())
        return active == grant


@dataclass(frozen=True)
class WorkflowServices:
    settings: WorkflowSettings
    dispatcher: ActivityDispatcher
    bound_activities: frozenset[str]
    schedule_state: str


def build_workflow_services(
    *,
    parameters: Mapping[str, Any],
    handlers: Mapping[str, ActivityHandler | None],
    clock: Callable[[], datetime.datetime],
    timezone_approved: bool,
) -> WorkflowServices:
    settings = settings_from_parameters(parameters)
    table: dict[str, ActivityHandler] = {
        b.name: handlers.get(b.name) or unbound_handler(clock) for b in ACTIVITY_BINDINGS
    }
    for name, h in handlers.items():
        if name not in table:
            table[name] = h or unbound_handler(clock)
    dispatcher = ActivityDispatcher(table)
    bound_activities = frozenset(n for n, h in handlers.items() if h is not None)
    state = schedule_state(settings, timezone_approved=timezone_approved)
    return WorkflowServices(
        settings=settings,
        dispatcher=dispatcher,
        bound_activities=bound_activities,
        schedule_state=state,
    )


@dataclass(frozen=True)
class TemporalRegistration:
    workflows: tuple[type, ...]
    activities_by_queue: Mapping[str, tuple[Callable, ...]]


def build_temporal_registration(
    services: WorkflowServices,
    *,
    grant_issuer: Callable,
    capability_reader: Callable,
) -> TemporalRegistration:
    activities_map: dict[str, list[Callable]] = {}

    def _make_activity(name: str) -> Callable:
        @activity.defn(name=name)
        async def _activity_fn(request: dict) -> dict:
            task = asyncio.ensure_future(
                asyncio.to_thread(services.dispatcher.dispatch, request)
            )
            try:
                while True:
                    done, _ = await asyncio.wait(
                        {task}, timeout=services.settings.heartbeat_seconds
                    )
                    if done:
                        return task.result()
                    activity.heartbeat()
            except ActivityRejected as exc:
                raise ApplicationError(exc.code, non_retryable=True) from exc

        return _activity_fn

    for binding in ACTIVITY_BINDINGS:
        fn = _make_activity(binding.name)
        activities_map.setdefault(binding.queue.value, []).append(fn)

    @activity.defn(name='IssueExecutionGrant')
    async def _issue_grant_activity(request: dict) -> dict:
        claims = await asyncio.to_thread(
            grant_issuer,
            request['stage_run_id'],
            request['allowed_operation'],
            request['input_fingerprint'],
            request['worker_lease_id'],
        )
        return claims_to_payload(claims)

    @activity.defn(name='ReadCapabilityView')
    async def _read_capability_view_activity(request: dict) -> dict:
        view = await asyncio.to_thread(capability_reader)
        return dict(view)

    control_queue = INTERNAL_ACTIVITIES['IssueExecutionGrant'].value
    activities_map.setdefault(control_queue, []).extend(
        [_issue_grant_activity, _read_capability_view_activity]
    )

    activities_by_queue = {
        queue: tuple(fns) for queue, fns in activities_map.items()
    }
    workflows = (
        DailyCollectionWorkflow,
        ContentEnrichmentWorkflow,
        ProductionBatchWorkflow,
        VideoProductionWorkflow,
        DebugStageWorkflow,
        MaintenanceWorkflow,
    )
    return TemporalRegistration(
        workflows=workflows,
        activities_by_queue=MappingProxyType(activities_by_queue),
    )


__all__ = [
    'ExecutionGrantCurrency',
    'StoreBackedClaimsCurrency',
    'TemporalRegistration',
    'WorkflowServices',
    'build_temporal_registration',
    'build_workflow_services',
    'collect_source_handler',
    'creative_handler',
    'render_handler',
    'resolve_document_handler',
    'service_handler',
    'unbound_handler',
    'voice_handler',
]
