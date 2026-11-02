"""IMGGEN-PIPE: Temporal versioning of GenerateIllustrations (patch video-ai-illustrations). A new VideoProductionWorkflow records
the marker before its first command and runs GenerateIllustrations before SelectCreativeAssets; a history recorded without the
marker (a run started before the change) replays with the new code on the legacy map and never generates, and the same history
fails to replay when the patch is ignored. Time-skipping test server and scripted handlers; no database.

coveredIds: OI-CP7-11-Q2, CT-WF-009
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack
from datetime import datetime, timezone

import pytest
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services
from controlplane.application.orchestration.workflows import definitions
from controlplane.application.orchestration.workflows.activities import (
    BINDINGS_BY_NAME, LEGACY_VIDEO_STAGE_ACTIVITIES, VIDEO_STAGE_ACTIVITIES, video_stage_activities)
from controlplane.application.orchestration.workflows.definitions import ILLUSTRATIONS_PATCH_ID, VideoProductionWorkflow
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.orchestration.fencing import GrantClaims

NOW = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)
CONTROL_QUEUE = 'control-workflows'


def scripted_handlers(log):
    def make(name):
        def handler(request, claims):
            log.append(name)
            ref_type = 'ai_illustration' if name == 'GenerateIllustrations' else name + '_out'
            return {'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id, 'execution_generation': claims.execution_generation,
                    'recovery_epoch': claims.recovery_epoch, 'completed_at': '2026-11-02T08:00:00Z', 'disposition': 'succeeded',
                    'output_refs': [{'ref_type': ref_type, 'ref_id': request['operation_key']}]}
        return handler
    return {name: make(name) for name in BINDINGS_BY_NAME}


def scripted_grants():
    issued = []

    def issue(stage_run_id, allowed_operation, input_fingerprint, worker_lease_id):
        issued.append(stage_run_id)
        return GrantClaims(f'grant-{len(issued)}', stage_run_id, 1, '1', worker_lease_id, '2026-11-02T08:00:00Z', '2026-11-02T09:00:00Z',
                           allowed_operation, input_fingerprint)
    return issue


async def run_video(client):
    log = []
    services = build_workflow_services(parameters=PARAMETERS, handlers=scripted_handlers(log), clock=lambda: NOW, timezone_approved=False)
    registration = build_temporal_registration(services, grant_issuer=scripted_grants(),
                                               capability_reader=lambda: {'desktop_production': {'status': 'available'}})
    payload = {'settings': SETTINGS.to_payload(), 'input_fingerprint': 'fp-1', 'worker_lease_id': 'lease-1', 'video_job_id': 'job-imggen-1'}
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows)} if queue == CONTROL_QUEUE else {}
            await stack.enter_async_context(Worker(client, task_queue=queue, activities=list(functions),
                                                   workflow_runner=UnsandboxedWorkflowRunner(), **extra))
        handle = await client.start_workflow('VideoProductionWorkflow', payload, id='imggen-' + uuid.uuid4().hex[:8], task_queue=CONTROL_QUEUE)
        snapshot = await asyncio.wait_for(handle.result(), timeout=300)
        history = await handle.fetch_history()
    return snapshot, history, log


def scheduled(history):
    return [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events
            if e.HasField('activity_task_scheduled_event_attributes')]


def marker_indexes(history):
    return [i for i, e in enumerate(history.events)
            if e.HasField('marker_recorded_event_attributes') and ILLUSTRATIONS_PATCH_ID in str(e.marker_recorded_event_attributes)]


def first_activity_index(history):
    return next(i for i, e in enumerate(history.events) if e.HasField('activity_task_scheduled_event_attributes'))


def replayer():
    return Replayer(workflows=[VideoProductionWorkflow], workflow_runner=UnsandboxedWorkflowRunner())


def test_the_patch_chooses_the_stage_map_and_only_media_select_differs():
    assert ILLUSTRATIONS_PATCH_ID == 'video-ai-illustrations'
    assert video_stage_activities(True) is VIDEO_STAGE_ACTIVITIES and video_stage_activities(False) is LEGACY_VIDEO_STAGE_ACTIVITIES
    assert {k for k in VIDEO_STAGE_ACTIVITIES if VIDEO_STAGE_ACTIVITIES[k] != LEGACY_VIDEO_STAGE_ACTIVITIES[k]} == {'media_select'}
    assert VIDEO_STAGE_ACTIVITIES['media_select'] == ('GenerateIllustrations', 'SelectCreativeAssets')
    assert LEGACY_VIDEO_STAGE_ACTIVITIES['media_select'] == ('SelectCreativeAssets',)


@pytest.mark.asyncio
async def test_a_new_run_records_the_marker_first_and_generates_before_selection(pw_temporal):
    snapshot, history, log = await run_video(pw_temporal)
    assert snapshot['status'] == 'COMPLETED' and snapshot['attempts']['media_select'] == 2
    names = scheduled(history)
    assert names.index('GenerateIllustrations') < names.index('SelectCreativeAssets') < names.index('BuildProductionPlan')
    markers = marker_indexes(history)
    assert len(markers) == 1 and markers[0] < first_activity_index(history)
    assert log.count('GenerateIllustrations') == 1
    assert [ref['ref_type'] for ref in snapshot['output_refs']['media_select']] == ['ai_illustration', 'SelectCreativeAssets_out']
    await replayer().replay_workflow(history)


@pytest.mark.asyncio
async def test_a_history_without_the_marker_replays_on_the_legacy_map_and_fails_when_the_patch_is_ignored(pw_temporal, monkeypatch):
    original = definitions.workflow.patched
    # The code before IMGGEN-PIPE never asked for this patch: recording a run that answers False without a marker reproduces its history.
    monkeypatch.setattr(definitions.workflow, 'patched', lambda patch_id: False if patch_id == ILLUSTRATIONS_PATCH_ID else original(patch_id))
    snapshot, legacy, log = await run_video(pw_temporal)
    monkeypatch.undo()
    assert snapshot['status'] == 'COMPLETED' and snapshot['attempts']['media_select'] == 1
    assert 'GenerateIllustrations' not in scheduled(legacy) and 'GenerateIllustrations' not in log and marker_indexes(legacy) == []
    await replayer().replay_workflow(legacy)
    monkeypatch.setattr(definitions, 'video_stage_activities', lambda illustrated: VIDEO_STAGE_ACTIVITIES)
    with pytest.raises(Exception) as caught:
        await replayer().replay_workflow(legacy)
    assert 'nondetermin' in repr(caught.value).lower() or 'GenerateIllustrations' in repr(caught.value)
