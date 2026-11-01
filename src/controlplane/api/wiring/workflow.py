"""CP-6-WORKFLOW: wires workflow activities into the composition root; BL-CV-10 and BL-CV-06 stay PENDING (src/main.py does not call this module yet)."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
import datetime
import hashlib
import json
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from catalog.application.media_discovery_handler import MediaDiscoveryDeps, register_media_discovery_handler
from catalog.persistence.assets import PostgresMediaAssetRepository
from controlplane.api.wiring.collection import collection_activity_handlers, seed_collection_sources
from controlplane.api.wiring.completion import completion_activity_services
from controlplane.api.wiring.ingestion import build_ingestion_services, ingestion_activity_handlers, ingestion_candidate_selector
from controlplane.api.wiring.production_profile import PROFILE_PRODUCTION, WiringConfig
from controlplane.api.wiring.storage import storage_activity_services
from controlplane.application.orchestration.grant_runtime import ExecutionGrantCurrency, GrantRevokingDispatcher
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle, JobLifecycleListener
from controlplane.application.orchestration.job_terminal import FailJobRequest, JobTerminator
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
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
from controlplane.application.storage_meta.handlers import register_staged_artifact
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.statemachine import ForbiddenTransitionError
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.orchestration.stage_runs import parse_stage_run_id
from creative.worker.activity_handler import handle_activity as handle_creative_activity
from creative.application.prompts import seed_default_prompts
from ingestion.application.activity_handler import handle_resolve_activity
from render.worker.activity_handler import handle_activity as handle_render_activity
from render.adapters.activity_inputs import ActivityInputError as RenderInputError
from render.ports.lease import GpuLeaseUnavailable
from source_ingestion.worker.activity_handler import handle_collect_source_activity
from voice.worker.activity_handler import handle_activity as handle_voice_activity
from voice.adapters.activity_inputs import ActivityInputError as VoiceInputError, ProductionActivityInputs
from voice.persistence.unit_of_work import PostgresVoiceUnitOfWork


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
    job_terminator: Any = None
    batch_lifecycle: Any = None


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

    @activity.defn(name='FailVideoJob')
    async def _fail_video_job_activity(request: dict) -> dict:
        terminator = services.job_terminator
        if terminator is None:
            raise ApplicationError('JOB_TERMINATOR_UNBOUND', non_retryable=True)
        try:
            fail_request = FailJobRequest(
                video_job_id=request['video_job_id'],
                stage_run_id=request['stage_run_id'],
                problem=request.get('problem') or {},
            )
        except KeyError:
            raise ApplicationError('INVALID_ACTIVITY_REQUEST', non_retryable=True) from None
        result = await asyncio.to_thread(terminator.fail, fail_request)
        return {'code': result.code, 'job_state': result.job_state}

    @activity.defn(name='StartBatch')
    async def _start_batch_activity(request: dict) -> dict:
        lifecycle = services.batch_lifecycle
        if lifecycle is None:
            raise ApplicationError('BATCH_LIFECYCLE_UNBOUND', non_retryable=True)
        batch_id = request.get('batch_id') if isinstance(request, Mapping) else None
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ApplicationError('INVALID_ACTIVITY_REQUEST', non_retryable=True)
        try:
            changed = await asyncio.to_thread(lifecycle.start, batch_id)
        except (OrchestrationContractError, ForbiddenTransitionError) as exc:
            raise ApplicationError(exc.code, non_retryable=True) from exc
        return {'batch_id': batch_id, 'changed': changed}

    control_queue = INTERNAL_ACTIVITIES['IssueExecutionGrant'].value
    activities_map.setdefault(control_queue, []).extend(
        [_issue_grant_activity, _read_capability_view_activity, _fail_video_job_activity, _start_batch_activity]
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


class ExecutionClaimsCurrency:
    """ClaimsCurrencyPort for A: turns GrantClaims into an ExecutionGrant and asks the PW-G3 ExecutionGrantCurrency."""

    def __init__(self, currency: Any, workspace_id: str) -> None:
        self._currency = currency
        self._workspace_id = workspace_id

    def is_grant_current(self, grant: GrantClaims) -> bool:
        try:
            job_id = parse_stage_run_id(grant.stage_run_id)[0]
            execution_grant = to_execution_grant(grant, workspace_id=self._workspace_id, job_id=job_id)
        except (ActivityRejected, OrchestrationContractError):
            return False
        return self._currency.is_grant_current(execution_grant)


def media_assets_opener(manager: Any) -> Callable[[str], Any]:
    @contextmanager
    def open_assets(workspace_id: str) -> Any:
        with manager.borrow_connection() as connection:
            yield PostgresMediaAssetRepository(connection, workspace_id)

    return open_assets


DURABLE_RETENTION = 'durable'


def staged_artifact_registrar(manager: Any, workspace_id: str, staging_root: Path) -> Callable[[Path, str], str]:
    def register(staged_path: Path, article_ref: str) -> str:
        relative_ref = Path(staged_path).relative_to(staging_root).as_posix()
        version = register_staged_artifact(
            manager, workspace_id=workspace_id, staging_root=staging_root,
            owner_ref=article_ref, relative_ref=relative_ref, retention_ref=DURABLE_RETENTION,
        )
        return version.artifact_version_id

    return register


RENDER_IMAGE_TOOL_VERSION = 'render-image-sources'
REF_TYPE_SELECTED_MEDIA = 'selected_media'


@dataclass(frozen=True)
class RenderImage:
    """Ảnh render lấy cho một media đã chọn: version mà NormalizeMedia của E dùng, hoặc None khi E loại và hết seed."""

    media_asset_id: str
    artifact_version_id: str | None
    reason: str


def render_image_sources(
    manager: Any,
    *,
    workspace_id: str,
    profile: Any,
    staging_root: Path,
    clock: Callable[[], datetime.datetime],
) -> Callable[[Sequence[Mapping[str, Any]]], dict[str, RenderImage]]:
    from controlplane.api.wiring.voice import ArtifactRows, SelectionSeedFallback, locate_media_file

    root = Path(staging_root)
    inputs = ProductionActivityInputs(
        parameters=profile.parameters,
        tool_version=RENDER_IMAGE_TOOL_VERSION,
        scripts=None,
        outputs=PostgresVoiceUnitOfWork(manager, workspace_id=workspace_id).outputs,
        media=ArtifactRows(manager, workspace_id),
        plans=None,
        selections=SelectionSeedFallback(manager, workspace_id),
        vision=None,
        read_image=None,
        verify_output=None,
        settings=None,
        clock=clock,
    )
    locate = locate_media_file(manager, workspace_id, root)

    def version_id_of(ref: str) -> str | None:
        try:
            return str(uuid.UUID(ref))
        except ValueError:
            return None

    def blurred_version(media_asset_id: str, artifact: Any) -> str:
        path = locate(artifact.ref)
        if path is None:
            raise RenderInputError('INPUT_NOT_READY', f'image_processed_missing:{media_asset_id}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.content_sha256:
            raise RenderInputError('INPUT_NOT_READY', f'image_processed_sha256_mismatch:{media_asset_id}')
        try:
            version = register_staged_artifact(
                manager,
                workspace_id=workspace_id,
                staging_root=root,
                owner_ref=media_asset_id,
                relative_ref=path.resolve().relative_to(root.resolve()).as_posix(),
                retention_ref=DURABLE_RETENTION,
            )
        except RuntimeError as error:
            raise RenderInputError('INPUT_NOT_READY', f'image_processed_not_registered:{media_asset_id}') from error
        return version.artifact_version_id

    def decide(refs: Sequence[Mapping[str, Any]]) -> dict[str, RenderImage]:
        decisions: dict[str, RenderImage] = {}
        for item in refs:
            media_id = item.get('ref_id')
            if (
                item.get('ref_type') != REF_TYPE_SELECTED_MEDIA
                or not isinstance(media_id, str)
                or not media_id
                or media_id in decisions
            ):
                continue
            ordered = [
                dict(item),
                *(dict(ref) for ref in refs if (ref.get('ref_type'), ref.get('ref_id')) != (REF_TYPE_SELECTED_MEDIA, media_id)),
            ]
            try:
                source = inputs.normalize_source(workspace_id, ordered)
            except VoiceInputError as error:
                raise RenderInputError(error.code, error.reason) from error
            artifact = source.artifact
            if artifact is None:
                decisions[media_id] = RenderImage(media_id, None, source.reason)
                continue
            version_id = version_id_of(artifact.ref) or blurred_version(media_id, artifact)
            decisions[media_id] = RenderImage(media_id, version_id, source.reason)
        return decisions

    return decide


def assemble_activity_handlers(
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    collection: Any,
    storage: Any,
    connection_factory: Callable[[], Any],
    clock: Callable[[], datetime.datetime],
) -> dict[str, ActivityHandler]:
    config = WiringConfig(mode=PROFILE_PRODUCTION, workspace_id=workspace_id, profile=profile, runtime=runtime)
    ingestion = build_ingestion_services(manager, config)
    grants = ExecutionClaimsCurrency(ExecutionGrantCurrency(connection_factory, workspace_id, clock), workspace_id)
    handlers: dict[str, ActivityHandler] = {}
    handlers.update(collection_activity_handlers(
        collection, grants=grants, tier_order=tuple(profile.parameters['collection.tiers']), clock=clock,
    ))
    handlers.update(ingestion_activity_handlers(ingestion, clock))
    handlers['RegisterMediaDiscovery'] = register_media_discovery_handler(
        MediaDiscoveryDeps(
            workspace_id, ingestion.resolve_factory.package_loader(), collection.media_fetcher, media_assets_opener(manager),
            staged_artifact_registrar(manager, workspace_id, runtime.staging_root),
        ),
        clock,
    )
    selector = ingestion_candidate_selector(ingestion, connection_factory=connection_factory, clock=clock)
    services: dict[str, Callable[..., Any]] = {}
    services.update(completion_activity_services(
        manager, connection_factory=connection_factory, workspace_id=workspace_id, selector=selector, clock=clock,
    ))
    services.update(storage_activity_services(
        storage, transactions=manager, workspace_id=workspace_id, staging_root=runtime.staging_root,
    ))
    for name, service in services.items():
        handlers[name] = service_handler(service, clock)
    return handlers


APP_SESSION_ACTIVE_SQL = "SELECT 1 FROM controlplane.cp_app_sessions WHERE workspace_id = %s AND status = 'ACTIVE' LIMIT 1"
GPU_PROBE_OWNER = 'capability-probe'


def wrap_dispatcher(
    services: WorkflowServices,
    *,
    connection_factory: Callable[[], Any],
    workspace_id: str,
    clock: Callable[[], datetime.datetime],
) -> WorkflowServices:
    listener = JobLifecycleListener(connection_factory, workspace_id=workspace_id)
    recording = ResultRecordingDispatcher(services.dispatcher, connection_factory, clock, [listener], workspace_id=workspace_id)
    return replace(
        services,
        dispatcher=GrantRevokingDispatcher(recording, connection_factory, workspace_id),
        job_terminator=JobTerminator(connection_factory, clock, workspace_id=workspace_id),
        batch_lifecycle=BatchLifecycle(connection_factory, clock, workspace_id=workspace_id),
    )


def build_capability_probes(
    *,
    connection_factory: Callable[[], Any],
    workspace_id: str,
    ffmpeg_path: Path,
    runtime_lock_path: Path,
    gpu_lease: Any,
) -> dict[str, Callable[[], bool]]:
    measured: dict[str, Any] = {}

    def app_session_active() -> bool:
        with connection_factory() as connection:
            return connection.execute(APP_SESSION_ACTIVE_SQL, (workspace_id,)).fetchone() is not None

    def ffmpeg_pinned() -> bool:
        pin = json.loads(Path(runtime_lock_path).read_text(encoding='utf-8'))['pins']['ffmpeg']
        if pin.get('status') != 'PINNED':
            return False
        try:
            stat = Path(ffmpeg_path).stat()
        except OSError:
            return False
        key = (stat.st_mtime_ns, stat.st_size)
        if measured.get('key') != key:
            digest = hashlib.sha256()
            with Path(ffmpeg_path).open('rb') as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b''):
                    digest.update(chunk)
            measured['key'] = key
            measured['sha256'] = digest.hexdigest()
        return measured['sha256'] == pin.get('sha256')

    def gpu_lease_ready() -> bool:
        try:
            lease = gpu_lease.acquire(GPU_PROBE_OWNER)
        except GpuLeaseUnavailable:
            return False
        gpu_lease.release(lease)
        return True

    return {'app_session_active': app_session_active, 'ffmpeg_pinned': ffmpeg_pinned, 'gpu_lease_ready': gpu_lease_ready}


def seed_production_defaults(
    manager: Any,
    *,
    workspace_id: str,
    actor_id: str,
    profile: Any,
    sources_path: Path,
    recovery_epoch: str,
    resolver: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    sources = seed_collection_sources(
        manager, workspace_id=workspace_id, profile=profile, sources_path=sources_path,
        recovery_epoch=recovery_epoch, resolver=resolver,
    )
    prompts = seed_default_prompts(compose_command_service(manager.unit_of_work), workspace_id=workspace_id, actor_id=actor_id)
    return {'sources': sources, 'prompts': prompts}


__all__ = [
    'ExecutionClaimsCurrency',
    'ExecutionGrantCurrency',
    'RenderImage',
    'StoreBackedClaimsCurrency',
    'TemporalRegistration',
    'WorkflowServices',
    'assemble_activity_handlers',
    'build_capability_probes',
    'build_temporal_registration',
    'build_workflow_services',
    'collect_source_handler',
    'creative_handler',
    'media_assets_opener',
    'render_handler',
    'render_image_sources',
    'resolve_document_handler',
    'seed_production_defaults',
    'service_handler',
    'unbound_handler',
    'voice_handler',
    'wrap_dispatcher',
]
