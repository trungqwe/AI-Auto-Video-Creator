"""CP-6-WORKFLOW in-process video production flow integration tests.

coveredIds: CP-6-WORKFLOW-FLOW
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass
import datetime
import json
import pathlib
import socket
from typing import Any, Mapping

import pytest

from controlplane.application.orchestration.commit_completion import (
    CommitVideoCompletion,
    CompletionContext,
    CompletionRejectedError,
    JobRecord,
)
from controlplane.application.orchestration.grant_issuance import GrantIssuer
from controlplane.application.orchestration.workflows.activities import (
    ACTIVITY_BINDINGS,
    BINDINGS_BY_NAME,
    ActivityDispatcher,
    claims_to_payload,
    document_input_refs,
)
from controlplane.application.orchestration.workflows.batch import (
    BATCH_EXHAUSTED,
    BATCH_TARGET_REACHED,
    BatchParams,
    ProductionBatchFlow,
)
from controlplane.application.orchestration.workflows.definitions import get_workflow
from controlplane.application.orchestration.workflows.flow import (
    DEBUG_STAGE_NOT_ALLOWED,
    FlowParams,
    StageGraphFlow,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_STAGE_OBSERVED,
    STATUS_WAITING_CAPABILITY,
    build_debug_flow,
)
from controlplane.application.orchestration.workflows.settings import (
    settings_from_parameters,
)
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration.completion_gate import ReservationBinding
from controlplane.domain.orchestration.fencing import (
    GrantClaims,
    evaluate_result_fencing,
)
from controlplane.domain.orchestration.retry_policy import next_delay
from controlplane.domain.orchestration.workflow_catalog import (
    DESKTOP_QUEUES,
    TaskQueue,
)
from controlplane.domain.statemachine import JobState

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = json.loads(
    (ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json').read_text(
        encoding='utf-8'
    )
)
REQUEST = FIXTURE['entities']['CommitVideoCompletionRequest']['valid'][0]
LEDGER = FIXTURE['entities']['CompletionLedgerEntry']['valid'][0]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
NOW = datetime.datetime(2026, 10, 18, 8, 0, 0, tzinfo=datetime.timezone.utc)

JOB_ID = REQUEST['video_job_id']
RES_ID = REQUEST['variant_reservation_id']
SHA = REQUEST['output_sha256']
REV = REQUEST['expected_variant_registry_revision']
BATCH = LEDGER['batch_ref']
JOB_REVISION = 3
CONTEXT_KEYS = (
    'completion_id',
    'batch_ref',
    'session_ref',
    'cloud_location_ref',
    'preset_revision_ref',
    'output_naming_metadata',
    'cost_usage_summary',
    'audit_actor',
    'cleanup_policy_ref',
    'completed_at',
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('real DNS/network call in integration test')

    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


def profile_parameters() -> dict[str, Any]:
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    return {
        'workflow.start_to_close_seconds': data['workflow']['start_to_close_seconds']['value'],
        'workflow.heartbeat_seconds': data['workflow']['heartbeat_seconds']['value'],
        'workflow.retry': data['workflow']['retry']['value'],
        'workflow.schedule': data['workflow']['schedule']['value'],
        'ai.quota_wait_poll_seconds': data['ai']['quota_wait_poll_seconds']['value'],
        'meta.revision': data['meta']['revision']['value'],
    }


class World:
    def __init__(self) -> None:
        self.ledgers: dict[str, Any] = {}
        self.jobs = {JOB_ID: JobRecord(JOB_ID, JobState.READY_FOR_COMPLETION, JOB_REVISION)}
        self.variant = {RES_ID: ReservationBinding(RES_ID, JOB_ID, SHA, ReservationState.ACTIVE)}
        self.capacity = {JOB_ID: 'ACTIVE'}
        self.registry_revision = REV
        self.batch_counts = {BATCH: 0}
        self.usage: list[Any] = []
        self.outbox: list[Any] = []
        self.cleanup: list[Any] = []

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.__dict__)

    def restore(self, snapshot: dict[str, Any]) -> None:
        self.__dict__.clear()
        self.__dict__.update(copy.deepcopy(snapshot))


class FakeStore:
    def __init__(self, world: World) -> None:
        self.world = world

    def find_ledger(self, video_job_id: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.world.ledgers.get(video_job_id))

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.world.jobs.get(job_id)

    def get_variant_reservation(self, reservation_id: str) -> ReservationBinding | None:
        return self.world.variant.get(reservation_id)

    def get_registry_revision(self) -> int:
        return self.world.registry_revision

    def insert_ledger(self, ledger: Mapping[str, Any]) -> None:
        assert ledger['video_job_id'] not in self.world.ledgers
        self.world.ledgers[ledger['video_job_id']] = copy.deepcopy(dict(ledger))

    def set_job_state(self, job_id: str, state: Any, revision: int) -> None:
        self.world.jobs[job_id] = JobRecord(job_id, state, revision)

    def convert_capacity_reservation(self, job_id: str) -> None:
        self.world.capacity[job_id] = 'CONVERTED'

    def convert_variant_reservation(self, reservation_id: str) -> None:
        self.world.variant[reservation_id] = copy.deepcopy(
            ReservationBinding(reservation_id, JOB_ID, SHA, ReservationState.CONVERTED)
        )

    def set_registry_revision(self, revision: int) -> None:
        self.world.registry_revision = revision

    def increment_batch_completed(self, batch_ref: str) -> None:
        self.world.batch_counts[batch_ref] += 1

    def insert_outbox(self, event: Mapping[str, Any]) -> None:
        self.world.outbox.append(copy.deepcopy(dict(event)))

    def insert_cleanup_eligibility(self, record: Mapping[str, Any]) -> None:
        self.world.cleanup.append(copy.deepcopy(dict(record)))


class FakeMediaUsage:
    def __init__(self, world: World) -> None:
        self.world = world

    def record(self, manifest: Any) -> None:
        self.world.usage.append(copy.deepcopy(manifest))


class FakeUow(IUnitOfWork):
    def __init__(self, world: World) -> None:
        self.world = world
        self.store = FakeStore(world)
        self.snapshot: dict[str, Any] | None = None
        self.committed = False
        self.rolled_back = False

    def begin(self) -> None:
        self.snapshot = self.world.snapshot()

    def commit(self) -> None:
        self.snapshot = None
        self.committed = True

    def rollback(self) -> None:
        if self.snapshot is not None:
            self.world.restore(self.snapshot)
            self.snapshot = None
        self.rolled_back = True

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        return None


class InMemoryGrantStore:
    def __init__(self) -> None:
        self.generations: dict[str, int] = {}
        self.grants: dict[str, GrantClaims] = {}

    def latest_generation(self, stage_run_id: str) -> int:
        return self.generations.get(stage_run_id, 0)

    def active_grant(self, stage_run_id: str, now: datetime.datetime) -> GrantClaims | None:
        return None

    def insert(self, claims: GrantClaims) -> None:
        self.generations[claims.stage_run_id] = claims.execution_generation
        self.grants[claims.grant_id] = claims

    def revoke(self, grant_id: str) -> None:
        self.grants.pop(grant_id, None)


class FakeRecoveryEpochPort:
    def current(self) -> str:
        return '1'


def make_handlers(log: list[str], behaviors: dict[str, list[Any]]) -> dict[str, Any]:
    handlers = {}
    for binding in ACTIVITY_BINDINGS:
        if binding.name == 'CommitVideoCompletion':
            continue

        def _make_handler(name: str):
            def handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
                assert claims is not None
                log.append(name)
                beh_list = behaviors.get(name)
                item = beh_list.pop(0) if beh_list else 'succeeded'
                if isinstance(item, dict):
                    disposition = item.get('disposition', 'failed')
                    retryable = item.get('retryable', True)
                    code = item.get('code', 'FAILED')
                    message = item.get('message', 'operation failed')
                elif item == 'failed':
                    disposition = 'failed'
                    retryable = True
                    code = 'STAGE_FAILED'
                    message = 'stage failed'
                elif item == 'outcome_unknown':
                    disposition = 'outcome_unknown'
                    retryable = False
                    code = 'OUTCOME_UNKNOWN'
                    message = 'outcome unknown'
                else:
                    disposition = item
                    retryable = False
                    code = 'OTHER'
                    message = 'other problem'

                res: dict[str, Any] = {
                    'stage_run_id': claims.stage_run_id,
                    'grant_id': claims.grant_id,
                    'execution_generation': claims.execution_generation,
                    'recovery_epoch': claims.recovery_epoch,
                    'disposition': disposition,
                    'output_refs': [
                        {'ref_type': name + '_out', 'ref_id': name + ':' + request['operation_key']}
                    ],
                    'completed_at': '2026-10-18T08:00:00Z',
                }
                if disposition != 'succeeded':
                    res['problem'] = {'code': code, 'retryable': retryable, 'message': message}
                return res

            return handler

        handlers[binding.name] = _make_handler(binding.name)
    return handlers


class InProcessGateway:
    def __init__(self, dispatcher: ActivityDispatcher, grant_issuer: GrantIssuer) -> None:
        self.dispatcher = dispatcher
        self.grant_issuer = grant_issuer
        self.capability_view: dict[str, Any] = {'desktop_production': {'status': 'available'}}
        self.calls: list[tuple[str, TaskQueue]] = []
        self.requests: list[dict[str, Any]] = []
        self.sleeps: list[float] = []

    async def issue_grant(
        self, stage_run_id: str, allowed_operation: str, input_fingerprint: str, worker_lease_id: str
    ) -> dict[str, Any]:
        claims = self.grant_issuer.issue(
            stage_run_id, allowed_operation, input_fingerprint, worker_lease_id, ttl_seconds=3600, now=NOW
        )
        return claims_to_payload(claims)

    async def read_capability_view(self) -> dict[str, Any]:
        return self.capability_view

    async def execute(self, activity_name: str, request: Mapping[str, Any]) -> dict[str, Any]:
        binding = BINDINGS_BY_NAME[activity_name]
        self.calls.append((binding.name, binding.queue))
        self.requests.append(dict(request))
        return self.dispatcher.dispatch(request)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def setup_video_environment(behaviors: dict[str, list[Any]] | None = None):
    world = World()
    media_usage = FakeMediaUsage(world)
    service = CommitVideoCompletion(lambda: FakeUow(world), media_usage)
    behaviors_map = behaviors if behaviors is not None else {}
    log: list[str] = []
    handlers = make_handlers(log, behaviors_map)

    def commit_handler(request: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        assert claims is not None
        fencing = evaluate_result_fencing(
            claims,
            claims.execution_generation,
            claims.recovery_epoch,
            {
                'recovery_epoch': claims.recovery_epoch,
                'execution_generation': claims.execution_generation,
                'grant_id': claims.grant_id,
                'stage_run_id': claims.stage_run_id,
            },
            claims.input_fingerprint,
            NOW,
            False,
        )
        fields = {key: copy.deepcopy(LEDGER[key]) for key in CONTEXT_KEYS}
        fields['fencing'] = fencing
        context = CompletionContext(**fields)
        try:
            out = service.execute(copy.deepcopy(REQUEST), context)
        except CompletionRejectedError as exc:
            return {
                'stage_run_id': claims.stage_run_id,
                'grant_id': claims.grant_id,
                'execution_generation': claims.execution_generation,
                'recovery_epoch': claims.recovery_epoch,
                'disposition': 'failed',
                'output_refs': [],
                'completed_at': '2026-10-18T08:00:00Z',
                'problem': {'code': exc.code, 'retryable': False, 'message': 'completion rejected'},
            }
        ledger = out.ledger
        return {
            'stage_run_id': claims.stage_run_id,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
            'disposition': 'succeeded',
            'output_refs': [{'ref_type': 'completion_ledger', 'ref_id': ledger['completion_id']}],
            'completed_at': '2026-10-18T08:00:00Z',
        }

    dispatcher = ActivityDispatcher({**handlers, 'CommitVideoCompletion': commit_handler})
    grant_issuer = GrantIssuer(InMemoryGrantStore(), FakeRecoveryEpochPort())
    gateway = InProcessGateway(dispatcher, grant_issuer)
    settings = settings_from_parameters(profile_parameters())
    params = FlowParams(
        workflow_id='wf-video-1',
        workflow_run_id='run-1',
        video_job_id=REQUEST['video_job_id'],
        input_fingerprint='fp-1',
        worker_lease_id='lease-1',
    )
    return world, gateway, settings, params, log


def test_happy_path():
    world, gateway, settings, params, log = setup_video_environment()
    video_spec = get_workflow('VideoProductionWorkflow')
    flow = StageGraphFlow(
        video_spec,
        get_workflow('VideoProductionWorkflow').name and {s.stage_type: tuple(b for b in get_stage_activities(s.stage_type)) for s in video_spec.stages},
        params,
        settings,
        gateway,
        [],
        chain_outputs=True,
    )

    status = asyncio.run(flow.advance())
    assert status == STATUS_COMPLETED
    assert flow.unbound == []
    assert REQUEST['video_job_id'] in world.ledgers
    assert world.jobs[JOB_ID].state == JobState.COMPLETED
    assert world.batch_counts[BATCH] == 1
    assert len(world.usage) == 1
    assert any(e.get('event_name') == 'VideoCompleted' for e in world.outbox)
    assert gateway.sleeps == []

    # Check stage ordering: analyze before script, script before plan, tts before align, render before qc, qc before sync, sync before complete
    call_names = [call[0] for call in gateway.calls]
    assert call_names.index('AnalyzeContent') < call_names.index('GenerateStoryAngles')
    assert call_names.index('GenerateScript') < call_names.index('BuildProductionPlan')
    assert call_names.index('CreateVoiceTrack') < call_names.index('CreateWordTiming')
    assert call_names.index('render_video') < call_names.index('inspect_output')
    assert call_names.index('GenerateOutputMetadata') < call_names.index('PersistVideoOutput')
    assert call_names.index('PersistVideoOutput') < call_names.index('CommitVideoCompletion')

    # Script, plan, tts must run in DESKTOP_QUEUES
    for name, q in gateway.calls:
        if name in ('GenerateStoryAngles', 'GenerateScript', 'BuildProductionPlan', 'CreateVoiceTrack'):
            assert q in DESKTOP_QUEUES


def get_stage_activities(stage_type: str) -> tuple[str, ...]:
    from controlplane.application.orchestration.workflows.activities import VIDEO_STAGE_ACTIVITIES
    return VIDEO_STAGE_ACTIVITIES[stage_type]


def test_waiting_capability():
    world, gateway, settings, params, log = setup_video_environment()
    gateway.capability_view = {'desktop_production': {'status': 'unavailable'}}
    video_spec = get_workflow('VideoProductionWorkflow')
    stage_acts = {s.stage_type: get_stage_activities(s.stage_type) for s in video_spec.stages}
    flow = StageGraphFlow(video_spec, stage_acts, params, settings, gateway, [], chain_outputs=True)

    status = asyncio.run(flow.advance())
    assert status == STATUS_WAITING_CAPABILITY
    assert flow.waiting_stage == 'script'
    assert flow.wait_reason == 'desktop_offline'

    call_names = [c[0] for c in gateway.calls]
    assert 'AnalyzeContent' in call_names
    assert 'GenerateStoryAngles' not in call_names
    assert 'GenerateScript' not in call_names

    gateway.capability_view = {'desktop_production': {'status': 'available'}}
    status2 = asyncio.run(flow.advance())
    assert status2 == STATUS_COMPLETED
    call_names2 = [c[0] for c in gateway.calls]
    assert 'GenerateStoryAngles' in call_names2


def test_debug_stage():
    world, gateway, settings, params, log = setup_video_environment()
    debug_spec = get_workflow('DebugStageWorkflow')
    assert debug_spec.auto_advance is False

    from controlplane.application.orchestration.workflows.activities import VIDEO_STAGE_ACTIVITIES
    plan_params = FlowParams(
        workflow_id='wf-dbg',
        workflow_run_id='run-dbg',
        input_fingerprint='fp-1',
        worker_lease_id='lease-1',
        target_stage='plan',
    )
    flow = build_debug_flow(debug_spec, VIDEO_STAGE_ACTIVITIES, plan_params, settings, gateway, [])

    status = asyncio.run(flow.advance())
    assert status == STATUS_STAGE_OBSERVED
    call_names = [c[0] for c in gateway.calls]
    assert call_names == ['BuildProductionPlan']

    status2 = asyncio.run(flow.advance())
    assert status2 == STATUS_STAGE_OBSERVED
    assert len(gateway.calls) == 1

    bad_params1 = FlowParams(
        workflow_id='wf-dbg', workflow_run_id='run-dbg', input_fingerprint='fp-1', worker_lease_id='lease-1',
        target_stage='complete',
    )
    with pytest.raises(ValueError, match=DEBUG_STAGE_NOT_ALLOWED):
        build_debug_flow(debug_spec, VIDEO_STAGE_ACTIVITIES, bad_params1, settings, gateway, [])

    bad_params2 = FlowParams(
        workflow_id='wf-dbg', workflow_run_id='run-dbg', input_fingerprint='fp-1', worker_lease_id='lease-1',
        target_stage='unknown_stage',
    )
    with pytest.raises(ValueError, match=DEBUG_STAGE_NOT_ALLOWED):
        build_debug_flow(debug_spec, VIDEO_STAGE_ACTIVITIES, bad_params2, settings, gateway, [])

    gateway.capability_view = {'desktop_production': {'status': 'unavailable'}}
    script_params = FlowParams(
        workflow_id='wf-dbg', workflow_run_id='run-dbg', input_fingerprint='fp-1', worker_lease_id='lease-1',
        target_stage='script',
    )
    script_flow = build_debug_flow(debug_spec, VIDEO_STAGE_ACTIVITIES, script_params, settings, gateway, [])
    assert asyncio.run(script_flow.advance()) == STATUS_WAITING_CAPABILITY


def test_retry():
    behaviors = {'render_video': ['failed']}
    world, gateway, settings, params, log = setup_video_environment(behaviors)
    video_spec = get_workflow('VideoProductionWorkflow')
    stage_acts = {s.stage_type: get_stage_activities(s.stage_type) for s in video_spec.stages}
    flow = StageGraphFlow(video_spec, stage_acts, params, settings, gateway, [], chain_outputs=True)

    status = asyncio.run(flow.advance())
    assert status == STATUS_COMPLETED
    assert gateway.sleeps == [next_delay(1, settings.retry)]
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    assert gateway.sleeps[0] == data['workflow']['retry']['value']['initial_interval_seconds']

    # Outcome unknown fail-closed check
    behaviors_unknown = {'render_video': ['outcome_unknown']}
    world2, gateway2, settings2, params2, log2 = setup_video_environment(behaviors_unknown)
    flow2 = StageGraphFlow(video_spec, stage_acts, params2, settings2, gateway2, [], chain_outputs=True)
    status2 = asyncio.run(flow2.advance())
    assert status2 == STATUS_FAILED
    assert flow2.last_problem is not None
    assert flow2.last_problem['disposition'] == 'outcome_unknown'
    assert gateway2.sleeps == []


def test_non_retryable_failure_then_retry_stage_signal():
    behaviors = {'render_video': [{'disposition': 'failed', 'retryable': False, 'code': 'RENDER_ERR'}]}
    world, gateway, settings, params, log = setup_video_environment(behaviors)
    video_spec = get_workflow('VideoProductionWorkflow')
    stage_acts = {s.stage_type: get_stage_activities(s.stage_type) for s in video_spec.stages}
    inbox = []
    flow = StageGraphFlow(video_spec, stage_acts, params, settings, gateway, inbox, chain_outputs=True)

    status = asyncio.run(flow.advance())
    assert status == STATUS_FAILED
    assert flow.failed_stage == 'render'

    render_calls_1 = [c for c in gateway.calls if c[0] == 'render_video']
    assert len(render_calls_1) == 1

    # Signal RetryStage for stage not failed is rejected while failed at render
    flow.signal_retry_stage('analyze')
    asyncio.run(flow.advance())
    rejected = [s for s in flow.rejected_signals if s.get('code') == 'RETRY_NOT_APPLICABLE']
    assert len(rejected) >= 1

    flow.signal_retry_stage('render')
    status2 = asyncio.run(flow.advance())
    assert status2 == STATUS_COMPLETED

    render_calls_2 = [c for c in gateway.calls if c[0] == 'render_video']
    assert len(render_calls_2) == 2

    render_reqs = [r for r in gateway.requests if r['activity_name'] == 'render_video']
    assert len(render_reqs) == 2
    assert render_reqs[0]['operation_key'] == render_reqs[1]['operation_key']
    assert render_reqs[1]['execution_grant']['execution_generation'] > render_reqs[0]['execution_grant']['execution_generation']


def test_regenerate():
    world, gateway, settings, params, log = setup_video_environment()
    gateway.capability_view = {'desktop_production': {'status': 'unavailable'}}
    video_spec = get_workflow('VideoProductionWorkflow')
    stage_acts = {s.stage_type: get_stage_activities(s.stage_type) for s in video_spec.stages}
    inbox = []
    flow = StageGraphFlow(video_spec, stage_acts, params, settings, gateway, inbox, chain_outputs=True)

    status = asyncio.run(flow.advance())
    assert status == STATUS_WAITING_CAPABILITY
    assert flow.waiting_stage == 'script'
    assert flow.revision == 1

    # Regenerate stage whose dependency is not completed is rejected
    flow.signal_regenerate_from_stage('plan')
    asyncio.run(flow.advance())
    assert any(s.get('code') == 'DEPENDENCY_NOT_COMPLETED' for s in flow.rejected_signals)

    # Regenerate from analyze
    flow.signal_regenerate_from_stage('analyze')
    status2 = asyncio.run(flow.advance())
    assert status2 == STATUS_WAITING_CAPABILITY
    assert flow.revision == 2


def test_batch_isolation():
    class FakeBatchGateway:
        def __init__(self):
            self.calls = []

        async def run_child(self, workflow_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
            self.calls.append((workflow_name, payload))
            child_id = payload['child_id']
            if ':video:0' in child_id:
                raise RuntimeError('first child failed')
            if ':video:' in child_id:
                return {'status': STATUS_COMPLETED}
            return {'status': STATUS_STAGE_OBSERVED}

    settings = settings_from_parameters(profile_parameters())
    params = BatchParams(
        batch_id='batch-1',
        target_videos=1,
        jobs=({'job': '1'}, {'job': '2'}),
        settings_payload=settings.to_payload(),
    )
    spec = get_workflow('ProductionBatchWorkflow')
    variant_inbox = []
    debug_inbox = []
    gateway = FakeBatchGateway()
    batch_flow = ProductionBatchFlow(spec, params, gateway, variant_inbox, debug_inbox)

    res = asyncio.run(batch_flow.run())
    assert res['status'] == BATCH_TARGET_REACHED
    assert res['completed'] == 1
    assert res['failed'] == 1

    # Test exhausted when jobs run out
    params_exhaust = BatchParams(
        batch_id='batch-2',
        target_videos=5,
        jobs=({'job': '1'},),
        settings_payload=settings.to_payload(),
    )
    gateway2 = FakeBatchGateway()
    batch_flow2 = ProductionBatchFlow(spec, params_exhaust, gateway2, variant_inbox, debug_inbox)
    res2 = asyncio.run(batch_flow2.run())
    assert res2['status'] == BATCH_EXHAUSTED

    # Test CreateNewVariant and RunDebugStage
    gateway3 = FakeBatchGateway()
    variant_inbox3 = [{'job': 'extra'}]
    debug_inbox3 = [{'target_stage': 'plan'}]
    batch_flow3 = ProductionBatchFlow(spec, params, gateway3, variant_inbox3, debug_inbox3)
    res3 = asyncio.run(batch_flow3.run())
    assert any('DebugStageWorkflow' == c[0] for c in gateway3.calls)


def test_enrichment_subscription():
    world, gateway, settings, params, log = setup_video_environment()
    spec = get_workflow('ContentEnrichmentWorkflow')
    from controlplane.application.orchestration.workflows.activities import ENRICHMENT_STAGE_ACTIVITIES

    doc_refs = document_input_refs(['d1', 'd2', 'd3'])
    enrich_params = FlowParams(
        workflow_id='wf-enrich-1',
        workflow_run_id='run-enrich-1',
        input_fingerprint='fp-enrich',
        worker_lease_id='lease-enrich',
        item_refs={'ResolveCollectedDocument': doc_refs},
    )
    flow = StageGraphFlow(
        spec,
        ENRICHMENT_STAGE_ACTIVITIES,
        enrich_params,
        settings,
        gateway,
        [],
        chain_outputs=False,
    )
    status = asyncio.run(flow.advance())
    assert status == STATUS_COMPLETED
    assert [c[0] for c in gateway.calls if c[0] == 'ResolveCollectedDocument'] == [
        'ResolveCollectedDocument', 'ResolveCollectedDocument', 'ResolveCollectedDocument'
    ]
    assert flow.unbound == ['dedup', 'enrich_ai', 'media', 'index']
