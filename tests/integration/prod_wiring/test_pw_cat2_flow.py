"""PW-CAT2: flow.py xử lý waiting, RetryStage và fan-out.

coveredIds: PW-CAT2-01, CT-WF-006, CT-WF-007, CT-ORC-007
"""
from __future__ import annotations

import asyncio
import inspect
import uuid
from collections import Counter
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from temporalio.api.enums.v1 import EventType
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services
from controlplane.application.orchestration.grant_runtime import GrantRevokingDispatcher, build_grant_issuer
from controlplane.application.orchestration.workflows import definitions
from controlplane.application.orchestration.workflows.activities import (
    BINDINGS_BY_NAME,
    DAILY_STAGE_ACTIVITIES,
    FAN_OUT_FROM_OUTPUT,
    VIDEO_STAGE_ACTIVITIES,
)
from controlplane.application.orchestration.workflows.flow import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_WAITING_CAPABILITY,
    FlowParams,
    StageGraphFlow,
)
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.job_waiting import WaitReason
from controlplane.domain.orchestration.workflow_catalog import get_workflow
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions

ROOT = Path(__file__).resolve().parents[3]
FLOW_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'workflows' / 'flow.py'
NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
WORKFLOW_ID = 'wf-pw-cat2'
PARAMETERS = {
    'workflow.start_to_close_seconds': {
        'control-workflows': 60,
        'cloud-io': 900,
        'cloud-ai': 240,
        'desktop-cpu': 600,
        'desktop-gpu': 900,
        'desktop-render': 1200,
    },
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {
        'initial_interval_seconds': 5,
        'backoff_coefficient': 2.0,
        'maximum_interval_seconds': 120,
        'maximum_attempts': 3,
    },
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
FAN_OUT_ACTIVITIES = ('ProbeMedia', 'AssessImageSafety', 'NormalizeMedia')
RENDER_TWO = {**VIDEO_STAGE_ACTIVITIES, 'render': ('reconcile_render', 'render_video')}


def media(count):
    return [{'ref_type': 'selected_media', 'ref_id': 'img-' + str(i)} for i in range(count)]


DEFAULT_OUTPUTS = {'SelectCreativeAssets': media(2)}


class ScriptedGateway:
    def __init__(self, script=None):
        self.script = {name: list(steps) for name, steps in (script or {}).items()}
        self.requests = []
        self.sleeps = []
        self._grants = 0
        self._identities = {}

    async def issue_grant(self, stage_run_id, allowed_operation, input_fingerprint, worker_lease_id):
        self._grants += 1
        return {'grant_id': 'grant-' + str(self._grants), 'stage_run_id': stage_run_id}

    async def read_capability_view(self):
        return {'desktop_production': {'status': 'available'}}

    async def sleep(self, seconds):
        self.sleeps.append(seconds)

    async def execute(self, activity_name, request):
        self.requests.append(dict(request))
        identity = (activity_name, tuple((r['ref_type'], r['ref_id']) for r in request['input_refs']))
        if self._identities.setdefault(request['operation_key'], identity) != identity:
            return {
                'disposition': 'failed',
                'output_refs': [],
                'problem': {'code': 'OPERATION_KEY_CONFLICT', 'retryable': False, 'message': 'operation_key reused'},
            }
        steps = self.script.get(activity_name)
        step = steps.pop(0) if steps else 'succeeded'
        spec = {'disposition': step} if isinstance(step, str) else dict(step)
        disposition = spec.get('disposition', 'succeeded')
        if disposition == 'succeeded':
            outputs = spec.get('outputs')
            if outputs is None:
                outputs = DEFAULT_OUTPUTS.get(activity_name) or [
                    {'ref_type': activity_name + '_out', 'ref_id': request['operation_key']}
                ]
            return {'disposition': 'succeeded', 'output_refs': [dict(o) for o in outputs]}
        return {
            'disposition': disposition,
            'output_refs': [],
            'problem': {'code': spec.get('code', 'STAGE_FAILED'), 'retryable': False, 'message': 'scripted'},
        }


def make_params(**changes):
    values = {
        'workflow_id': WORKFLOW_ID,
        'workflow_run_id': 'run-1',
        'input_fingerprint': 'fp-1',
        'worker_lease_id': 'lease-1',
        'video_job_id': 'job-1',
    }
    values.update(changes)
    return FlowParams(**values)


def make_video_flow(script=None, *, stage_activities=None, params=None, inbox=None):
    gateway = ScriptedGateway(script)
    flow = StageGraphFlow(
        get_workflow('VideoProductionWorkflow'),
        stage_activities or VIDEO_STAGE_ACTIVITIES,
        params or make_params(),
        SETTINGS,
        gateway,
        [] if inbox is None else inbox,
        chain_outputs=True,
    )
    return flow, gateway


def requests_of(gateway, name):
    return [r for r in gateway.requests if r['activity_name'] == name]


def expected_calls(waited=None):
    expected = Counter()
    for names in VIDEO_STAGE_ACTIVITIES.values():
        for name in names:
            expected[name] += 2 if name in FAN_OUT_FROM_OUTPUT else 1
    if waited is not None:
        expected[waited] += 1
    return expected


def test_wait_reason_enum_lists_the_seven_codes_and_dependency_wait():
    assert {reason.value for reason in WaitReason} == {
        'credential_unavailable', 'quota_wait', 'artifact_not_ready', 'insufficient_disk',
        'provider_unavailable', 'local_ai_unavailable', 'desktop_offline', 'dependency_wait',
    }


@pytest.mark.parametrize(
    'code, expected',
    [(reason.value, reason.value) for reason in WaitReason] + [('SOMETHING_ELSE', 'dependency_wait'), (None, 'dependency_wait')],
)
def test_waiting_sets_the_wait_reason_from_the_problem_code(code, expected):
    flow, gateway = make_video_flow({'SelectCreativeAssets': [{'disposition': 'waiting', 'code': code}]})
    assert asyncio.run(flow.advance()) == STATUS_WAITING_CAPABILITY
    assert flow.status == STATUS_WAITING_CAPABILITY
    assert flow.waiting_stage == 'media_select'
    assert flow.wait_reason == expected
    assert flow.failed_stage is None
    assert 'media_select' not in flow.completed
    assert gateway.sleeps == []
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    assert (flow.waiting_stage, flow.wait_reason) == (None, None)


@pytest.mark.parametrize('stage', list(VIDEO_STAGE_ACTIVITIES))
def test_waiting_applies_to_every_stage_and_resumes_at_the_same_stage(stage):
    waited = VIDEO_STAGE_ACTIVITIES[stage][0]
    flow, gateway = make_video_flow({waited: [{'disposition': 'waiting', 'code': 'quota_wait'}]})
    assert asyncio.run(flow.advance()) == STATUS_WAITING_CAPABILITY
    assert (flow.waiting_stage, flow.wait_reason, flow.failed_stage) == (stage, 'quota_wait', None)
    assert stage not in flow.completed
    done = list(flow.completed)
    attempts_before = dict(flow.attempts)
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    assert Counter(r['activity_name'] for r in gateway.requests) == expected_calls(waited)
    assert {name: flow.attempts[name] for name in done} == {name: attempts_before[name] for name in done}
    assert (flow.waiting_stage, flow.wait_reason) == (None, None)
    assert gateway.sleeps == []


def test_retry_stage_reruns_only_the_failed_activity_and_keeps_received_output():
    flow, gateway = make_video_flow(
        {'render_video': [{'disposition': 'failed', 'code': 'RENDER_ERR'}]}, stage_activities=RENDER_TWO
    )
    assert asyncio.run(flow.advance()) == STATUS_FAILED
    assert flow.failed_stage == 'render'
    received = [dict(ref) for ref in flow.output_refs['render']]
    assert [ref['ref_type'] for ref in received] == ['reconcile_render_out']
    flow.signal_retry_stage('render')
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    reconcile = requests_of(gateway, 'reconcile_render')
    render = requests_of(gateway, 'render_video')
    assert len(reconcile) == 1
    assert len(render) == 2
    assert render[0]['operation_key'] == render[1]['operation_key']
    assert render[0]['input_refs'] == render[1]['input_refs']
    counts = Counter(r['operation_key'] for r in gateway.requests)
    assert [key for key, count in counts.items() if count > 1] == [render[0]['operation_key']]
    assert flow.output_refs['render'][0] == received[0]
    assert [ref['ref_type'] for ref in flow.output_refs['render']] == ['reconcile_render_out', 'render_video_out']
    assert flow.last_problem is None


def test_fan_out_runs_once_per_selected_image_with_its_own_index():
    images = media(3)
    other = {'ref_type': 'selected_audio', 'ref_id': 'bed-1'}
    flow, gateway = make_video_flow({'SelectCreativeAssets': [{'outputs': images + [other]}]})
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    for name in FAN_OUT_ACTIVITIES:
        runs = requests_of(gateway, name)
        assert [r['operation_key'] for r in runs] == [f'{WORKFLOW_ID}:process:{name}:{i}:r1' for i in range(3)]
        assert [r['input_refs'][0] for r in runs] == images
    assert len(requests_of(gateway, 'TransformSensitiveImage')) == 1


def test_payload_item_refs_are_kept_over_fan_out():
    fixed = ({'ref_type': 'selected_media', 'ref_id': 'fixed-1'},)
    flow, gateway = make_video_flow(params=make_params(item_refs={'ProbeMedia': (fixed,)}))
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    probe = requests_of(gateway, 'ProbeMedia')
    assert len(probe) == 1
    assert probe[0]['input_refs'][0]['ref_id'] == 'fixed-1'
    assert len(requests_of(gateway, 'AssessImageSafety')) == 2


def test_fan_out_without_matching_output_runs_zero_times():
    other = {'ref_type': 'selected_audio', 'ref_id': 'bed-1'}
    flow, gateway = make_video_flow({'SelectCreativeAssets': [{'outputs': [other]}]})
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    for name in FAN_OUT_ACTIVITIES:
        assert requests_of(gateway, name) == []
    assert len(requests_of(gateway, 'TransformSensitiveImage')) == 1


def test_fan_out_item_waiting_reruns_only_that_item():
    script = {'ProbeMedia': ['succeeded', {'disposition': 'waiting', 'code': 'artifact_not_ready'}]}
    flow, gateway = make_video_flow(script)
    assert asyncio.run(flow.advance()) == STATUS_WAITING_CAPABILITY
    assert (flow.waiting_stage, flow.wait_reason) == ('process', 'artifact_not_ready')
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    probe = requests_of(gateway, 'ProbeMedia')
    assert [r['operation_key'].split(':')[-2] for r in probe] == ['0', '1', '1']


def test_daily_collection_fans_out_from_collection_sources():
    sources = [{'ref_type': 'collection_source', 'ref_id': 'src-' + str(i)} for i in range(2)]
    gateway = ScriptedGateway({'PlanCollectionCycle': [{'outputs': sources}]})
    flow = StageGraphFlow(
        get_workflow('DailyCollectionWorkflow'),
        DAILY_STAGE_ACTIVITIES,
        make_params(video_job_id=None),
        SETTINGS,
        gateway,
        [],
        chain_outputs=False,
    )
    assert asyncio.run(flow.advance()) == STATUS_COMPLETED
    collect = requests_of(gateway, 'CollectSource')
    assert [r['operation_key'] for r in collect] == [f'{WORKFLOW_ID}:collect:CollectSource:{i}:r1' for i in range(2)]
    assert [r['input_refs'][0] for r in collect] == sources


def test_flow_source_is_deterministic_and_drive_waits_on_condition_with_timeout():
    text = FLOW_PATH.read_text(encoding='utf-8')
    assert 'waiting' in text
    for forbidden in ('time.sleep', 'datetime.now', 'time.time', 'asyncio.sleep', 'import random', 'import uuid'):
        assert forbidden not in text
    body = inspect.getsource(definitions._drive)
    assert 'workflow.wait_condition' in body
    assert 'timeout=' in body
    assert 'capability_poll_seconds' in body
    assert 'gateway.sleep' not in body


def temporal_handlers(log, script):
    def make(name):
        def handler(request, claims):
            log.append(name)
            steps = script.get(name)
            step = steps.pop(0) if steps else 'succeeded'
            result = {
                'stage_run_id': claims.stage_run_id,
                'grant_id': claims.grant_id,
                'execution_generation': claims.execution_generation,
                'recovery_epoch': claims.recovery_epoch,
                'completed_at': '2026-10-26T01:02:03Z',
            }
            if step == 'waiting':
                result.update(
                    disposition='waiting',
                    output_refs=[],
                    problem={'code': 'artifact_not_ready', 'retryable': False, 'message': 'artifact is not ready'},
                )
            else:
                result.update(
                    disposition='succeeded',
                    output_refs=[{'ref_type': name + '_out', 'ref_id': request['operation_key']}],
                )
            return result

        return handler

    return {name: make(name) for name in BINDINGS_BY_NAME}


@pytest.mark.asyncio
async def test_waiting_waits_on_the_temporal_timer_and_resumes_at_the_same_stage(pw_database, pw_temporal):
    with pw_database.connect() as connection:
        PostgresAppSessions(connection, pw_database.workspace_id).begin('ses-1', '5')
    log = []
    handlers = temporal_handlers(log, {'SelectCreativeAssets': ['waiting']})
    services = build_workflow_services(
        parameters=PARAMETERS, handlers=handlers, clock=lambda: NOW, timezone_approved=False
    )
    services = replace(
        services,
        dispatcher=GrantRevokingDispatcher(services.dispatcher, pw_database.connect, pw_database.workspace_id),
    )
    registration = build_temporal_registration(
        services,
        grant_issuer=build_grant_issuer(pw_database.connect, pw_database.workspace_id, None, lambda: NOW),
        capability_reader=lambda: {'desktop_production': {'status': 'available'}},
    )
    workflow_queue = 'control-workflows'
    payload = {
        'settings': SETTINGS.to_payload(),
        'input_fingerprint': 'fp-1',
        'worker_lease_id': 'lease-1',
        'video_job_id': 'job-pw-cat2-1',
    }
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows)} if queue == workflow_queue else {}
            await stack.enter_async_context(
                Worker(
                    pw_temporal,
                    task_queue=queue,
                    activities=list(functions),
                    workflow_runner=UnsandboxedWorkflowRunner(),
                    **extra,
                )
            )
        handle = await pw_temporal.start_workflow(
            'VideoProductionWorkflow',
            payload,
            id='pw-cat2-' + uuid.uuid4().hex[:8],
            task_queue=workflow_queue,
        )
        snapshot = await asyncio.wait_for(handle.result(), timeout=300)
        history = await handle.fetch_history()
    assert snapshot['status'] == 'COMPLETED'
    assert snapshot['waiting_stage'] is None
    assert snapshot['wait_reason'] is None
    counts = Counter(log)
    assert counts['SelectCreativeAssets'] == 2
    assert counts['GenerateIllustrations'] == 1  # IMGGEN-PIPE: done before the wait, not run again
    assert counts['AnalyzeContent'] == 1
    assert counts['GenerateScript'] == 1
    assert counts['BuildProductionPlan'] == 1
    assert snapshot['attempts']['analyze'] == 2
    assert snapshot['attempts']['script'] == 2
    assert snapshot['attempts']['media_select'] == 3
    timers = [e for e in history.events if e.event_type == EventType.EVENT_TYPE_TIMER_STARTED]
    assert len(timers) == 1
    assert timers[0].timer_started_event_attributes.start_to_fire_timeout.seconds == 60
