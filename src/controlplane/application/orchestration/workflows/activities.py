from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.orchestration.activity_binding import (
    validate_activity_request,
    validate_activity_result,
)
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.orchestration.workflow_catalog import TaskQueue, route_stage


@dataclass(frozen=True)
class ActivityBinding:
    name: str
    owner: str
    stage_type: str | None
    queue: TaskQueue
    side_effect: bool
    extra_stage_types: tuple[str, ...] = ()


def _b(
    name: str, owner: str, stage_type: str | None, side_effect: bool, extra_stage_types: tuple[str, ...] = (),
) -> ActivityBinding:
    queue = route_stage(stage_type) if stage_type is not None else TaskQueue.CONTROL_WORKFLOWS
    return ActivityBinding(
        name=name,
        owner=owner,
        stage_type=stage_type,
        queue=queue,
        side_effect=side_effect,
        extra_stage_types=extra_stage_types,
    )


# Names from docs/09-contracts (CT-SRC-004/005, CT-CNT-001, CT-MED-001/007, CT-STO-004/006/007, CT-AI-ROUTE-001, CT-CAP-002, CT-SEC-002) and handler constants; ReconcileStorage is a local name.
ACTIVITY_BINDINGS: tuple[ActivityBinding, ...] = (
    _b('PlanCollectionCycle', 'A', 'select_sources', False),
    _b('CollectSource', 'A', 'collect', True),
    _b('ResolveCollectedDocument', 'B', 'normalize', True),
    _b('RegisterMediaDiscovery', 'C', 'media', True),
    _b('RequestSupplementalMedia', 'C', 'media', True),
    _b('BuildProductionSnapshot', 'D', 'analyze', True),
    _b('AnalyzeContent', 'D', 'analyze', True),
    _b('GenerateStoryAngles', 'D', 'script', True),
    _b('GenerateScript', 'D', 'script', True),
    _b('BuildProductionPlan', 'D', 'plan', True),
    _b('ValidateVariant', 'D', 'plan', True, ('qc',)),
    _b('ReserveVariant', 'G', 'plan', True),
    _b('GenerateOutputMetadata', 'D', 'plan', True),
    _b('SelectCreativeAssets', 'D', 'media_select', True),
    _b('CreateVoiceTrack', 'E', 'tts', True),
    _b('CreateWordTiming', 'E', 'align', True),
    _b('ProbeMedia', 'E', 'process', True),
    _b('AssessImageSafety', 'E', 'process', True),
    _b('TransformSensitiveImage', 'E', 'process', True),
    _b('NormalizeMedia', 'E', 'process', True),
    _b('PrepareAudioBed', 'E', 'process', True),
    _b('resolve_render_package', 'F', 'render', True),
    _b('validate_render_package', 'F', 'render', True),
    _b('reconcile_render', 'F', 'render', True),
    _b('render_video', 'F', 'render', True),
    _b('inspect_output', 'F', 'qc', True),
    _b('prepare_output_ready', 'F', 'qc', True),
    _b('CommitVideoCompletion', 'G', 'complete', True),
    _b('MaterializeArtifactSet', 'I', 'render', True),
    _b('PersistVideoOutput', 'I', 'sync', True),
    _b('RequestCleanupEvaluation', 'I', 'cleanup', True),
    _b('ReconcileStorage', 'I', 'reconcile', True),
    _b('ResolveProviderRoute', 'J', None, False),
    _b('ReserveProviderCapacity', 'J', None, True),
    _b('IssueShortLivedCredential', 'J', None, True),
)

BINDINGS_BY_NAME: Mapping[str, ActivityBinding] = MappingProxyType(
    {b.name: b for b in ACTIVITY_BINDINGS}
)
INTERNAL_ACTIVITIES: Mapping[str, TaskQueue] = MappingProxyType({
    'IssueExecutionGrant': TaskQueue.CONTROL_WORKFLOWS,
    'ReadCapabilityView': TaskQueue.CONTROL_WORKFLOWS,
})

VIDEO_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'analyze': ('BuildProductionSnapshot', 'AnalyzeContent'),
    'script': ('GenerateStoryAngles', 'GenerateScript'),
    'plan': ('BuildProductionPlan', 'ValidateVariant', 'ReserveVariant', 'GenerateOutputMetadata'),
    'media_select': ('SelectCreativeAssets',),
    'tts': ('CreateVoiceTrack',),
    'align': ('CreateWordTiming',),
    'process': ('ProbeMedia', 'AssessImageSafety', 'TransformSensitiveImage', 'NormalizeMedia', 'PrepareAudioBed'),
    'render': ('MaterializeArtifactSet', 'resolve_render_package', 'validate_render_package', 'reconcile_render', 'render_video'),
    'qc': ('inspect_output', 'ValidateVariant', 'prepare_output_ready'),
    'sync': ('PersistVideoOutput',),
    'complete': ('CommitVideoCompletion',),
})

DAILY_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'select_sources': ('PlanCollectionCycle',),
    'collect': ('CollectSource',),
})

ENRICHMENT_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'normalize': ('ResolveCollectedDocument',),
    'dedup': (),
    'enrich_ai': (),
    'media': (),
    'index': (),
})

BATCH_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'allocate': (),
    'run_videos': (),
})

MAINTENANCE_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'reconcile': ('ReconcileStorage',),
    'cleanup': ('RequestCleanupEvaluation',),
    'backup_check': (),
})

DEBUG_STAGE_ACTIVITIES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    'debug_observe': (),
})

STAGE_ACTIVITIES_BY_WORKFLOW: Mapping[str, Mapping[str, tuple[str, ...]]] = MappingProxyType({
    'DailyCollectionWorkflow': DAILY_STAGE_ACTIVITIES,
    'ContentEnrichmentWorkflow': ENRICHMENT_STAGE_ACTIVITIES,
    'ProductionBatchWorkflow': BATCH_STAGE_ACTIVITIES,
    'VideoProductionWorkflow': VIDEO_STAGE_ACTIVITIES,
    'DebugStageWorkflow': DEBUG_STAGE_ACTIVITIES,
    'MaintenanceWorkflow': MAINTENANCE_STAGE_ACTIVITIES,
})

# activity -> (stage trước, ref_type) cho activity chạy một lần trên mỗi phần tử đầu ra của stage trước.
FAN_OUT_FROM_OUTPUT: Mapping[str, tuple[str, str]] = MappingProxyType({
    'AssessImageSafety': ('media_select', 'selected_media'),
    'ProbeMedia': ('media_select', 'selected_media'),
    'NormalizeMedia': ('media_select', 'selected_media'),
    'CollectSource': ('select_sources', 'collection_source'),
})

SUBSCRIPTIONS: Mapping[str, str] = MappingProxyType({
    'CollectedDocumentAvailable': 'ResolveCollectedDocument',
})
REF_TYPE_COLLECTED_DOCUMENT = 'collected_document'


def document_input_refs(
    collected_document_ids: Sequence[str],
) -> tuple[tuple[dict[str, str], ...], ...]:
    results = []
    for doc_id in collected_document_ids:
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError('collected_document_id must be a non-empty string')
        results.append(({'ref_type': REF_TYPE_COLLECTED_DOCUMENT, 'ref_id': doc_id},))
    return tuple(results)


UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
MISSING_EXECUTION_GRANT = 'MISSING_EXECUTION_GRANT'
INVALID_EXECUTION_GRANT = 'INVALID_EXECUTION_GRANT'
INVALID_ACTIVITY_REQUEST = 'INVALID_ACTIVITY_REQUEST'
INVALID_ACTIVITY_RESULT = 'INVALID_ACTIVITY_RESULT'
ACTIVITY_SERVICE_UNBOUND = 'ACTIVITY_SERVICE_UNBOUND'


class ActivityRejected(Exception):
    def __init__(self, code: str, issues: Sequence[Any] | tuple[Any, ...] | list[Any] = ()) -> None:
        self.code = code
        self.issues = tuple(issues)
        super().__init__(code)


ActivityHandler = Callable[[Mapping[str, Any], GrantClaims | None], Mapping[str, Any]]


def claims_to_payload(claims: GrantClaims) -> dict[str, Any]:
    return asdict(claims)


def claims_from_request(request: Mapping[str, Any]) -> GrantClaims | None:
    raw = request.get('execution_grant')
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ActivityRejected(INVALID_EXECUTION_GRANT)
    try:
        claims = GrantClaims(**raw)
    except TypeError as exc:
        raise ActivityRejected(INVALID_EXECUTION_GRANT) from exc
    if claims.stage_run_id != request.get('stage_run_id'):
        raise ActivityRejected(INVALID_EXECUTION_GRANT)
    return claims


def to_execution_grant(claims: GrantClaims, *, workspace_id: str, job_id: str) -> ExecutionGrant:
    try:
        epoch = int(claims.recovery_epoch)
    except ValueError as exc:
        raise ActivityRejected(INVALID_EXECUTION_GRANT) from exc
    return ExecutionGrant(
        workspace_id=workspace_id,
        operation_id=claims.grant_id,
        job_id=job_id,
        stage_run_id=claims.stage_run_id,
        execution_generation=claims.execution_generation,
        recovery_epoch=epoch,
    )


class ActivityDispatcher:
    def __init__(self, handlers: Mapping[str, ActivityHandler]) -> None:
        for name in handlers:
            if name not in BINDINGS_BY_NAME:
                raise ValueError(f'unknown activity in handlers: {name}')
        self._handlers: Mapping[str, ActivityHandler] = MappingProxyType(dict(handlers))

    def dispatch(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ActivityRejected(UNKNOWN_ACTIVITY)
        name = request.get('activity_name')
        if not isinstance(name, str):
            raise ActivityRejected(UNKNOWN_ACTIVITY)
        binding = BINDINGS_BY_NAME.get(name)
        if binding is None:
            raise ActivityRejected(UNKNOWN_ACTIVITY)

        issues = validate_activity_request(dict(request), binding.side_effect)
        if issues:
            if binding.side_effect and any(
                isinstance(issue, Mapping) and issue.get('field') == 'execution_grant'
                for issue in issues
            ):
                raise ActivityRejected(MISSING_EXECUTION_GRANT, issues)
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST, issues)

        claims = claims_from_request(request)

        handler = self._handlers.get(name)
        if handler is None:
            raise ActivityRejected(ACTIVITY_SERVICE_UNBOUND)

        result = handler(request, claims)
        issues = validate_activity_result(dict(result))
        if issues:
            raise ActivityRejected(INVALID_ACTIVITY_RESULT, issues)
        return dict(result)


__all__ = [
    'ACTIVITY_BINDINGS',
    'ACTIVITY_SERVICE_UNBOUND',
    'ActivityBinding',
    'ActivityDispatcher',
    'ActivityHandler',
    'ActivityRejected',
    'BATCH_STAGE_ACTIVITIES',
    'BINDINGS_BY_NAME',
    'DAILY_STAGE_ACTIVITIES',
    'DEBUG_STAGE_ACTIVITIES',
    'ENRICHMENT_STAGE_ACTIVITIES',
    'FAN_OUT_FROM_OUTPUT',
    'INTERNAL_ACTIVITIES',
    'INVALID_ACTIVITY_REQUEST',
    'INVALID_ACTIVITY_RESULT',
    'INVALID_EXECUTION_GRANT',
    'MAINTENANCE_STAGE_ACTIVITIES',
    'MISSING_EXECUTION_GRANT',
    'REF_TYPE_COLLECTED_DOCUMENT',
    'STAGE_ACTIVITIES_BY_WORKFLOW',
    'SUBSCRIPTIONS',
    'UNKNOWN_ACTIVITY',
    'VIDEO_STAGE_ACTIVITIES',
    'claims_from_request',
    'claims_to_payload',
    'document_input_refs',
    'to_execution_grant',
]
