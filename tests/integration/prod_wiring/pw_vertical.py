"""PW-VERT vertical harness assembling real G components with test adapters for D, E, F, I."""
from __future__ import annotations

import asyncio
import hashlib
import threading
import uuid
from collections import Counter
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import datetime, timezone
import psycopg
from psycopg.types.json import Jsonb
from temporalio.worker import UnsandboxedWorkflowRunner, Worker
from catalog.application.usage import MediaUsageRecorder
from catalog.persistence.usage import media_usage_repository_factory
from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, service_handler
from controlplane.application.orchestration.batch_allocation import AllocateJobService, FinalizeBatchService
from controlplane.application.orchestration.capability_view import CapabilityReader
from controlplane.application.orchestration.grant_runtime import GrantRevokingDispatcher, build_grant_issuer
from controlplane.application.orchestration.job_lifecycle import BatchLifecycle, JobLifecycleListener
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.variant_handlers import commit_video_completion_handler, reserve_variant_handler
from controlplane.application.orchestration.workflows.activities import VIDEO_STAGE_ACTIVITIES
from controlplane.application.orchestration.workflows.batch import candidate_fingerprint
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.outbox_relay import OutboxRelay
from controlplane.infrastructure.db.orchestration.stage_runs import parse_stage_run_id
from controlplane.infrastructure.db.uow import TransactionManager

NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
CONTROL_QUEUE = 'control-workflows'
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 0.2,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
VIDEO_STAGES = ('analyze', 'script', 'plan', 'media_select', 'tts', 'align', 'process', 'render', 'qc', 'sync', 'complete')
EXPECTED_ACTIVITIES = {'analyze': 2, 'script': 2, 'plan': 4, 'media_select': 2, 'tts': 1, 'align': 1, 'process': 5, 'render': 5, 'qc': 3, 'sync': 1, 'complete': 1}
G_ACTIVITIES = ('AllocateJob', 'FinalizeBatch', 'ReserveVariant', 'CommitVideoCompletion')
VIDEO_ACTIVITIES = tuple(sorted({name for names in VIDEO_STAGE_ACTIVITIES.values() for name in names}))
FAKE_ACTIVITIES = tuple(name for name in VIDEO_ACTIVITIES if name not in G_ACTIVITIES)


def rows(database, sql, *params):
    with database.connect() as conn:
        return conn.execute(sql, (database.workspace_id, *params)).fetchall()


def scalar(database, sql, *params):
    with database.connect() as conn:
        row = conn.execute(sql, (database.workspace_id, *params)).fetchone()
        return row[0] if row else None


def count(database, table):
    return scalar(database, f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s')


def begin_session(database, session_ref, epoch):
    with database.connect() as conn:
        return PostgresAppSessions(conn, database.workspace_id).begin(session_ref, epoch)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def output_sha(job_id: str) -> str:
    return sha256_hex('mp4:' + job_id)


def artifact_uuid(job_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'pw-vert:artifact:' + job_id))


def location_uuid(job_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'pw-vert:location:' + job_id))


def stage_runs(database, job_id):
    return rows(
        database,
        'SELECT stage_name, status, attempt, recovery_epoch, wait_reason FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND job_id = %s ORDER BY stage_name',
        job_id,
    )


def grants_by_stage(database):
    result = {}
    query = 'SELECT stage_run_id, execution_generation, recovery_epoch, (revoked_at IS NOT NULL) FROM controlplane.cp_execution_grants WHERE workspace_id = %s ORDER BY stage_run_id, execution_generation'
    for stage_run_id, gen, epoch, revoked in rows(database, query):
        result.setdefault(stage_run_id, []).append((gen, epoch, revoked))
    return result


def live_grants(database):
    return scalar(database, 'SELECT count(*) FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND revoked_at IS NULL')


def job_row(database, job_id):
    with database.connect() as conn:
        row = conn.execute(
            'SELECT status, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s',
            (database.workspace_id, job_id),
        ).fetchone()
        return (row[0], row[1]) if row else None


def batch_row(database, batch_id):
    with database.connect() as conn:
        row = conn.execute(
            'SELECT status, stop_reason, stopped_at FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s',
            (database.workspace_id, batch_id),
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None


async def wait_until(predicate, *, timeout=30.0, interval=0.05, what='condition'):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        val = predicate()
        if val:
            return val
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('timed out waiting for ' + what)
        await asyncio.sleep(interval)


class CapabilitySwitch:
    def __init__(self) -> None:
        self.ffmpeg_pinned = True
        self.gpu_lease_ready = True
        self.reads = 0

    def ffmpeg_probe(self) -> bool:
        self.reads += 1
        return self.ffmpeg_pinned

    def gpu_probe(self) -> bool:
        return self.gpu_lease_ready


class ScriptedCandidateSelector:
    def __init__(self, *candidates: AllocationCandidate) -> None:
        self.pending = list(candidates)
        self.calls: list[tuple[str, str]] = []

    def next_candidate(self, batch_id: str, production_mode: str) -> AllocationCandidate | None:
        self.calls.append((batch_id, production_mode))
        if self.pending:
            return self.pending.pop(0)
        return None


class RecordingStartClient:
    def __init__(self, client) -> None:
        self._client = client
        self.calls: list[tuple[tuple, dict]] = []

    async def start_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return await self._client.start_workflow(*args, **kwargs)


class JobStatusTrace:
    def __init__(self, inner, database) -> None:
        self._inner = inner
        self._database = database
        self.history: dict[str, list[str]] = {}

    def on_result(self, request, result) -> None:
        self._inner.on_result(request, result)
        try:
            job_id = parse_stage_run_id(request['stage_run_id'])[0]
        except Exception:
            return
        row = job_row(self._database, job_id)
        if row is None:
            return
        status = row[0]
        current = self.history.setdefault(job_id, [])
        if not current or current[-1] != status:
            current.append(status)


REFS = {
    'BuildProductionSnapshot': ('production_snapshot', 'snapshot'),
    'AnalyzeContent': ('content_analysis', 'analysis'),
    'GenerateStoryAngles': ('story_angle_set', 'angles'),
    'GenerateScript': ('script_version', 'script'),
    'GenerateIllustrations': ('ai_illustration', 'illustration'),
    'BuildProductionPlan': ('production_plan', 'plan'),
    'CreateVoiceTrack': ('voice_track', 'voice'),
    'CreateWordTiming': ('word_timing', 'timing'),
    'ProbeMedia': ('media_probe', 'probe'),
    'AssessImageSafety': ('image_safety', 'safety'),
    'TransformSensitiveImage': ('transformed_media', 'transformed'),
    'NormalizeMedia': ('normalized_media', 'normalized'),
    'PrepareAudioBed': ('audio_bed', 'bed'),
    'MaterializeArtifactSet': ('artifact_set', 'artifacts'),
    'resolve_render_package': ('render_package', 'package'),
    'validate_render_package': ('render_package_validation', 'package-ok'),
    'reconcile_render': ('render_reconcile', 'reconcile'),
    'prepare_output_ready': ('output_ready', 'ready'),
}


class DesktopAdapters:
    def __init__(
        self,
        database,
        *,
        switch: CapabilitySwitch,
        fail_plan_validation: int = 0,
        drop_capability_on: str | None = None,
    ) -> None:
        self._database = database
        self.switch = switch
        self._fail_plan_validation = fail_plan_validation
        self._drop_capability_on = drop_capability_on
        self.calls: Counter[str] = Counter()
        self.stage_calls: Counter[tuple[str, str]] = Counter()
        self._lock = threading.Lock()

    def handlers(self) -> dict:
        return {name: service_handler(self._service(name), lambda: NOW) for name in FAKE_ACTIVITIES}

    def _service(self, name: str):
        def service(request: dict, claims: dict | None) -> dict:
            job_id = request['video_job_id']
            stage = parse_stage_run_id(request['stage_run_id'])[1]
            with self._lock:
                self.calls[name] += 1
                self.stage_calls[(stage, name)] += 1
                if name == 'ValidateVariant' and stage == 'plan' and self._fail_plan_validation > 0:
                    self._fail_plan_validation -= 1
                    return {
                        'disposition': 'failed',
                        'output_refs': [],
                        'problem': {
                            'code': 'VALIDATOR_BUSY',
                            'retryable': True,
                            'message': 'test adapter busy',
                        },
                    }
                if self._drop_capability_on == name:
                    self._drop_capability_on = None
                    self.switch.ffmpeg_pinned = False
                    return {
                        'disposition': 'waiting',
                        'output_refs': [],
                        'problem': {
                            'code': 'desktop_offline',
                            'retryable': True,
                            'message': 'desktop went offline during the activity',
                        },
                    }
            writers = {
                'ValidateVariant': self._validate_variant,
                'GenerateOutputMetadata': self._output_metadata,
                'SelectCreativeAssets': self._creative_selection,
                'render_video': self._render_video,
                'inspect_output': self._inspect_output,
                'PersistVideoOutput': self._persist_output,
            }
            writer = writers.get(name)
            if writer is not None:
                refs = writer(job_id, stage)
            else:
                ref_type, prefix = REFS[name]
                refs = [{'ref_type': ref_type, 'ref_id': f'{prefix}:{job_id}'}]
            return {'disposition': 'succeeded', 'output_refs': refs}

        return service

    def _validate_variant(self, job_id: str, stage: str) -> list[dict]:
        phase = 'plan' if stage == 'plan' else 'output'
        revision = 1 if phase == 'plan' else 2
        registry_revision = scalar(
            self._database,
            'SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id = %s',
        )
        if registry_revision is None:
            registry_revision = 1
        payload = {
            'valid': True,
            'phase': phase,
            'registry_revision': registry_revision,
            'variation_policy_revision': 'policy-r1',
            'input_hashes': {'candidate': sha256_hex('candidate:' + job_id)},
            'output_hash': output_sha(job_id) if phase == 'output' else None,
            'own_reservation_id': None,
            'exact_duplicate': False,
            'reason_codes': ['valid'],
        }
        with self._database.connect() as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_variant_validations (workspace_id, record_key, revision, payload) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                (self._database.workspace_id, f'variant:{job_id}', revision, Jsonb(payload)),
            )
        return [{'ref_type': 'variant_validation', 'ref_id': f'variant:{job_id}'}]

    def _output_metadata(self, job_id: str, stage: str) -> list[dict]:
        with self._database.connect() as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_output_metadata (workspace_id, record_key, revision, payload) VALUES (%s, %s, 1, %s) ON CONFLICT DO NOTHING',
                (self._database.workspace_id, f'meta:{job_id}', Jsonb({'title': 'title-' + job_id})),
            )
        return [{'ref_type': 'output_metadata', 'ref_id': f'meta:{job_id}'}]

    def _creative_selection(self, job_id: str, stage: str) -> list[dict]:
        payload = {
            'preset_registry_revision': 'preset-r1',
            'assignments': [
                {
                    'media_asset_id': f'asset:{job_id}',
                    'rendition_ref': 'rend-1',
                    'artifact_version_ref': 'av-1',
                }
            ],
            'visual_hook': {'ref_id': 'vh-01'},
            'audio_hook': {'ref_id': 'ah-01'},
            'thumbnail': {'ref_id': f'asset:{job_id}'},
        }
        with self._database.connect() as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_creative_selections (workspace_id, selection_id, job_id, selection_revision, content_sha256, payload) VALUES (%s, %s, %s, 1, %s, %s) ON CONFLICT DO NOTHING',
                (
                    self._database.workspace_id,
                    f'sel:{job_id}',
                    job_id,
                    sha256_hex('sel:' + job_id),
                    Jsonb(payload),
                ),
            )
        return [
            {'ref_type': 'creative_selection', 'ref_id': f'sel:{job_id}'},
            {'ref_type': 'selected_media', 'ref_id': f'asset:{job_id}'},
        ]

    def _render_video(self, job_id: str, stage: str) -> list[dict]:
        with self._database.connect() as conn:
            conn.execute(
                "INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) VALUES (%s, %s, %s, %s, 128, 'video/mp4', 'rendered_video', 'owner-g', 'lineage-g', 'retention-g', 'internal') ON CONFLICT DO NOTHING",
                (
                    artifact_uuid(job_id),
                    self._database.workspace_id,
                    f'artifact:{job_id}',
                    output_sha(job_id),
                ),
            )
        return [
            {'ref_type': 'render_attempt', 'ref_id': f'attempt:{job_id}:1'},
            {'ref_type': 'output_artifact_version', 'ref_id': artifact_uuid(job_id)},
        ]

    def _inspect_output(self, job_id: str, stage: str) -> list[dict]:
        with self._database.connect() as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_quality_reports (workspace_id, record_key, revision, payload) VALUES (%s, %s, 1, %s) ON CONFLICT DO NOTHING',
                (self._database.workspace_id, f'attempt:{job_id}:1', Jsonb({'report_id': f'qr:{job_id}', 'passed': True})),
            )
        return [{'ref_type': 'quality_report', 'ref_id': f'qr:{job_id}'}]

    def _persist_output(self, job_id: str, stage: str) -> list[dict]:
        with self._database.connect() as conn:
            conn.execute(
                "INSERT INTO controlplane.cp_artifact_locations (location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, observed_hash, observed_size_bytes, verification_evidence_ref, state) VALUES (%s, %s, %s, 'drive', 'ns', %s, %s, %s, 128, %s, 'VERIFIED') ON CONFLICT DO NOTHING",
                (
                    location_uuid(job_id),
                    self._database.workspace_id,
                    artifact_uuid(job_id),
                    f'obj:{job_id}',
                    f'loc:{job_id}',
                    output_sha(job_id),
                    f'evidence:{job_id}',
                ),
            )
        return [{'ref_type': 'cloud_location', 'ref_id': location_uuid(job_id)}]


class Vertical:
    def __init__(
        self,
        database,
        client,
        *,
        adapters=None,
        switch=None,
        selector=None,
        session=None,
        revoke_grants=True,
        max_cached_workflows=1000,
    ) -> None:
        self.database = database
        self.client = client
        self._session = session
        self._revoke_grants = revoke_grants
        self._max_cached_workflows = max_cached_workflows
        self._stack = None
        self._closed = False
        self.switch = switch if switch is not None else CapabilitySwitch()
        self.adapters = adapters if adapters is not None else DesktopAdapters(database, switch=self.switch)
        self.selector = selector if selector is not None else ScriptedCandidateSelector(AllocationCandidate('cand-1', 'angle-1', 'set-1'))
        self.start_client = RecordingStartClient(client)

        ws = database.workspace_id
        clock = lambda: NOW
        self.manager = TransactionManager(database.dsn, pool_max_size=4)
        recorder = MediaUsageRecorder(media_usage_repository_factory(ws))

        self._allocate_service = AllocateJobService(database.connect, self.selector, workspace_id=ws)
        handlers = self.adapters.handlers()
        handlers['AllocateJob'] = service_handler(self._allocate_service, clock)
        handlers['FinalizeBatch'] = service_handler(
            FinalizeBatchService(BatchLifecycle(database.connect, clock, workspace_id=ws)), clock
        )
        handlers['ReserveVariant'] = service_handler(reserve_variant_handler(self.manager, workspace_id=ws), clock)
        handlers['CommitVideoCompletion'] = service_handler(
            commit_video_completion_handler(self.manager, workspace_id=ws, clock=clock, usage_recorder=recorder),
            clock,
        )

        services = build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=clock, timezone_approved=False)
        self.job_trace = JobStatusTrace(JobLifecycleListener(database.connect, workspace_id=ws), database)
        dispatcher = ResultRecordingDispatcher(services.dispatcher, database.connect, clock, [self.job_trace], workspace_id=ws)
        if self._revoke_grants:
            dispatcher = GrantRevokingDispatcher(dispatcher, database.connect, ws)
        self.services = replace(services, dispatcher=dispatcher, batch_lifecycle=BatchLifecycle(database.connect, clock, workspace_id=ws))

        reader = CapabilityReader({
            'app_session_active': self._app_session_active,
            'ffmpeg_pinned': self.switch.ffmpeg_probe,
            'gpu_lease_ready': self.switch.gpu_probe,
        })
        self.registration = build_temporal_registration(
            self.services,
            grant_issuer=build_grant_issuer(database.connect, ws, None, clock),
            capability_reader=reader,
        )

    def _app_session_active(self) -> bool:
        return scalar(self.database, "SELECT 1 FROM controlplane.cp_app_sessions WHERE workspace_id = %s AND status = 'ACTIVE'") is not None

    async def start(self):
        if self._session:
            begin_session(self.database, *self._session)
        self._stack = AsyncExitStack()
        for queue, functions in self.registration.activities_by_queue.items():
            extra = {'workflows': list(self.registration.workflows)} if queue == CONTROL_QUEUE else {}
            await self._stack.enter_async_context(
                Worker(
                    self.client,
                    task_queue=queue,
                    activities=list(functions),
                    workflow_runner=UnsandboxedWorkflowRunner(),
                    max_cached_workflows=self._max_cached_workflows,
                    **extra,
                )
            )

    async def stop(self):
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        if not self._closed:
            self.manager.close()
            self._closed = True

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def start_batch(self, target: int = 1) -> str:
        service = compose_command_service(self.manager.unit_of_work)
        receipt = service.start_batch(
            workspace_id=self.database.workspace_id,
            actor_id=self.database.actor_id,
            correlation_id='pw-vert',
            idempotency_key=str(uuid.uuid4()),
            payload={'target_completed_videos': target},
        )
        batch_id = receipt['resource_ref']['batch_id']
        return batch_id

    def relay(self) -> OutboxRelay:
        return OutboxRelay(
            lambda: psycopg.connect(self.database.dsn),
            self.start_client,
            self.database.workspace_id,
            SETTINGS,
            lambda: NOW,
        )

    async def start_video(self, batch_id: str, *, hold_on_failure: bool = True):
        job_id = f'{batch_id}:job:1'
        result = self._allocate_service(
            {
                'input_refs': [
                    {'ref_type': 'production_batch', 'ref_id': batch_id},
                    {'ref_type': 'allocation_job', 'ref_id': job_id},
                    {'ref_type': 'production_mode', 'ref_id': 'single_article'},
                ]
            },
            None,
        )
        outputs = {ref['ref_type']: ref['ref_id'] for ref in result['output_refs']}
        assert outputs['allocated_job'] == job_id
        lease = scalar(
            self.database,
            "SELECT session_ref FROM controlplane.cp_app_sessions WHERE workspace_id = %s AND status = 'ACTIVE' ORDER BY started_at DESC LIMIT 1",
        )
        payload = {
            'video_job_id': job_id,
            'input_fingerprint': candidate_fingerprint(outputs['job_candidate'], outputs['source_set']),
            'worker_lease_id': lease,
            'input_refs': [
                {'ref_type': 'job_candidate', 'ref_id': outputs['job_candidate']},
                {'ref_type': 'source_set', 'ref_id': outputs['source_set']},
            ],
            'settings': SETTINGS.to_payload(),
            'child_id': f'{batch_id}:video:0',
            'hold_on_failure': hold_on_failure,
        }
        handle = await self.client.start_workflow(
            'VideoProductionWorkflow',
            payload,
            id=f'{batch_id}:video:0',
            task_queue=CONTROL_QUEUE,
        )
        return (handle, job_id)