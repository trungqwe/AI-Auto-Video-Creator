"""PW-CAT2-FIX1: StageGraphFlow đối chiếu lại ValidateVariant khi registry biến thể đổi.

coveredIds: PW-CAT2-FIX1-01
"""
from __future__ import annotations

import asyncio

import pytest

from controlplane.application.orchestration.workflows.activities import VIDEO_STAGE_ACTIVITIES
from controlplane.application.orchestration.workflows.flow import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_WAITING_CAPABILITY,
    FlowParams,
    StageGraphFlow,
)
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.workflow_catalog import get_workflow

WORKFLOW_ID = 'wf-revalidate'
JOB_ID = 'job-1'
VALIDATION_KEY = 'variant:job-1'
PATCH_ID = 'variant-stale-revalidate'
FOREVER = float('inf')
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


def make_flow(gateway):
    return StageGraphFlow(
        get_workflow('VideoProductionWorkflow'),
        VIDEO_STAGE_ACTIVITIES,
        FlowParams(
            workflow_id=WORKFLOW_ID,
            workflow_run_id='run-1',
            input_fingerprint='fp-1',
            worker_lease_id='lease-1',
            video_job_id=JOB_ID,
        ),
        SETTINGS,
        gateway,
        [],
        chain_outputs=True,
    )


def run(flow):
    return asyncio.run(flow.advance())


def requests_of(gateway, name, stage=None):
    return [
        request
        for request in gateway.requests
        if request['activity_name'] == name
        and (stage is None or request['stage_run_id'].split(':')[1] == stage)
    ]


def validation_refs(flow, stage):
    return [r for r in flow.output_refs[stage] if r['ref_type'] == 'variant_validation']


class RegistryGateway:
    def __init__(self, *, reserve_stale=0, commit_stale=0, waits=None, patched=True):
        self.reserve_stale = reserve_stale
        self.commit_stale = commit_stale
        self.waits = {name: list(codes) for name, codes in (waits or {}).items()}
        self.patch_enabled = patched
        self.patched_calls = []
        self.requests = []
        self.sleeps = []
        self._validation_keys = set()
        self._validation_count = {}
        self._grants = 0

    def patched(self, patch_id):
        self.patched_calls.append(patch_id)
        return self.patch_enabled

    async def issue_grant(self, stage_run_id, allowed_operation, input_fingerprint, worker_lease_id):
        self._grants += 1
        return {'grant_id': 'grant-' + str(self._grants), 'stage_run_id': stage_run_id}

    async def read_capability_view(self):
        return {'desktop_production': {'status': 'available'}}

    async def sleep(self, seconds):
        self.sleeps.append(seconds)

    async def execute(self, activity_name, request):
        self.requests.append(dict(request))
        stage = request['stage_run_id'].split(':')[1]
        key = request['operation_key']
        if activity_name == 'ValidateVariant':
            if key in self._validation_keys:
                return {
                    'disposition': 'failed',
                    'output_refs': [],
                    'problem': {'code': 'IDEMPOTENCY_CONFLICT', 'retryable': False, 'message': 'operation_key reused'},
                }
            self._validation_keys.add(key)
            count = self._validation_count.get(stage, 0) + 1
            self._validation_count[stage] = count
            return {
                'disposition': 'succeeded',
                'output_refs': [
                    {'ref_type': 'variant_validation', 'ref_id': VALIDATION_KEY, 'revision_id': f'{stage}-{count}'}
                ],
            }
        code = None
        if activity_name == 'ReserveVariant' and self.reserve_stale > 0:
            self.reserve_stale -= 1
            code = 'VARIANT_VALIDATION_STALE'
        elif activity_name == 'CommitVideoCompletion' and self.commit_stale > 0:
            self.commit_stale -= 1
            code = 'VARIANT_REGISTRY_STALE'
        elif self.waits.get(activity_name):
            code = self.waits[activity_name].pop(0)
        if code is not None:
            return {
                'disposition': 'waiting',
                'output_refs': [],
                'problem': {'code': code, 'retryable': True, 'message': 'scripted'},
            }
        if activity_name == 'SelectCreativeAssets':
            outputs = [{'ref_type': 'selected_media', 'ref_id': 'img-0'}]
        else:
            outputs = [{'ref_type': activity_name + '_out', 'ref_id': key}]
        return {'disposition': 'succeeded', 'output_refs': outputs}


BASE_PLAN = f'{WORKFLOW_ID}:plan:ValidateVariant:0:r1'
BASE_QC = f'{WORKFLOW_ID}:qc:ValidateVariant:0:r1'


def test_stale_reserve_once_revalidates_plan_and_reserves():
    gateway = RegistryGateway(reserve_stale=1)
    flow = make_flow(gateway)
    assert run(flow) == STATUS_COMPLETED
    plan_v = requests_of(gateway, 'ValidateVariant', 'plan')
    assert [r['operation_key'] for r in plan_v] == [BASE_PLAN, BASE_PLAN + ':v1']
    assert {r['stage_run_id'] for r in plan_v} == {f'{JOB_ID}:plan:r1'}
    assert plan_v[1]['input_refs'] == plan_v[0]['input_refs']
    assert len(requests_of(gateway, 'ReserveVariant')) == 2
    assert len(requests_of(gateway, 'BuildProductionPlan')) == 1
    assert len(requests_of(gateway, 'GenerateOutputMetadata')) == 1
    assert validation_refs(flow, 'plan') == [
        {'ref_type': 'variant_validation', 'ref_id': VALIDATION_KEY, 'revision_id': 'plan-2'}
    ]
    assert gateway.patched_calls == [PATCH_ID]
    assert gateway.sleeps == []


def test_stale_reserve_forever_fails_after_max_attempts():
    assert SETTINGS.retry.max_attempts == 3
    gateway = RegistryGateway(reserve_stale=FOREVER)
    flow = make_flow(gateway)
    assert run(flow) == STATUS_FAILED
    snap = flow.snapshot()
    assert snap['failed_stage'] == 'plan'
    assert snap['last_problem']['code'] == 'VARIANT_VALIDATION_STALE'
    assert snap['last_problem']['activity'] == 'ReserveVariant'
    assert len(requests_of(gateway, 'ReserveVariant')) == 3
    keys = [r['operation_key'] for r in requests_of(gateway, 'ValidateVariant', 'plan')]
    assert keys == [BASE_PLAN, BASE_PLAN + ':v1', BASE_PLAN + ':v2']
    assert requests_of(gateway, 'GenerateOutputMetadata') == []
    assert gateway.sleeps == []


def test_stale_commit_once_revalidates_qc_and_commits():
    gateway = RegistryGateway(commit_stale=1)
    flow = make_flow(gateway)
    assert run(flow) == STATUS_COMPLETED
    qc_v = requests_of(gateway, 'ValidateVariant', 'qc')
    assert [r['operation_key'] for r in qc_v] == [BASE_QC, BASE_QC + ':v1']
    assert {r['stage_run_id'] for r in qc_v} == {f'{JOB_ID}:qc:r1'}
    assert len(requests_of(gateway, 'CommitVideoCompletion')) == 2
    assert len(requests_of(gateway, 'PersistVideoOutput')) == 1
    assert len(requests_of(gateway, 'inspect_output')) == 1
    assert len(requests_of(gateway, 'ValidateVariant', 'plan')) == 1
    assert validation_refs(flow, 'qc') == [
        {'ref_type': 'variant_validation', 'ref_id': VALIDATION_KEY, 'revision_id': 'qc-2'}
    ]


def test_stale_commit_forever_fails_after_max_attempts():
    gateway = RegistryGateway(commit_stale=FOREVER)
    flow = make_flow(gateway)
    assert run(flow) == STATUS_FAILED
    snap = flow.snapshot()
    assert snap['failed_stage'] == 'complete'
    assert snap['last_problem']['code'] == 'VARIANT_REGISTRY_STALE'
    assert len(requests_of(gateway, 'CommitVideoCompletion')) == 3


def test_patch_inactive_keeps_the_waiting_behavior():
    gateway = RegistryGateway(reserve_stale=1, patched=False)
    flow = make_flow(gateway)
    assert run(flow) == STATUS_WAITING_CAPABILITY
    assert flow.waiting_stage == 'plan'
    assert flow.wait_reason == 'dependency_wait'
    assert len(requests_of(gateway, 'ValidateVariant', 'plan')) == 1
    assert len(requests_of(gateway, 'ReserveVariant')) == 1
    assert gateway.patched_calls == [PATCH_ID]
    assert run(flow) == STATUS_COMPLETED
    assert len(requests_of(gateway, 'ValidateVariant', 'plan')) == 1
    assert len(requests_of(gateway, 'ReserveVariant')) == 2


@pytest.mark.parametrize(
    'activity, code, stage, reason',
    [
        ('GenerateScript', 'quota_wait', 'script', 'quota_wait'),
        ('ReserveVariant', 'quota_wait', 'plan', 'quota_wait'),
        ('CommitVideoCompletion', 'VARIANT_VALIDATION_STALE', 'complete', 'dependency_wait'),
        ('ReserveVariant', 'VARIANT_REGISTRY_STALE', 'plan', 'dependency_wait'),
    ],
)
def test_other_waiting_codes_never_ask_for_the_patch(activity, code, stage, reason):
    gateway = RegistryGateway(waits={activity: [code]})
    flow = make_flow(gateway)
    assert run(flow) == STATUS_WAITING_CAPABILITY
    assert flow.waiting_stage == stage
    assert flow.wait_reason == reason
    assert gateway.patched_calls == []
