"""CP-6-WORKFLOW catalog integration tests.

coveredIds: CP-6-WORKFLOW-CATALOG
"""
from __future__ import annotations

from dataclasses import asdict, replace
import datetime
import json
import pathlib
import socket
from typing import Any

import pytest
from temporalio.workflow._definition import _Definition

from controlplane.api.wiring.workflow import (
    StoreBackedClaimsCurrency,
    build_temporal_registration,
    build_workflow_services,
)
from controlplane.application.orchestration.workflows.activities import (
    ACTIVITY_BINDINGS,
    BINDINGS_BY_NAME,
    REF_TYPE_COLLECTED_DOCUMENT,
    STAGE_ACTIVITIES_BY_WORKFLOW,
    SUBSCRIPTIONS,
    VIDEO_STAGE_ACTIVITIES,
    ActivityRejected,
    INVALID_EXECUTION_GRANT,
    MISSING_EXECUTION_GRANT,
    document_input_refs,
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
    NOT_READY,
    READY,
    schedule_state,
    settings_from_parameters,
)
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.orchestration.workflow_catalog import (
    DESKTOP_QUEUES,
    STAGE_QUEUES,
    WORKFLOW_NAMES,
    CatalogError,
    TaskQueue,
    get_workflow,
    route_stage,
    validate_catalog,
)
import creative.worker.activity_handler as creative_ah
import ingestion.application.activity_handler as ingestion_ah
import render.worker.activity_handler as render_ah
import source_ingestion.application.collect_source as source_collect
import source_ingestion.worker.activity_handler as source_ah
import voice.worker.activity_handler as voice_ah

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
NOW = datetime.datetime(2026, 10, 18, 8, 0, 0, tzinfo=datetime.timezone.utc)


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


def make_claims(stage_run_id: str = 'stage-1', allowed_operation: str = 'op-1') -> GrantClaims:
    return GrantClaims(
        grant_id='grant-1',
        stage_run_id=stage_run_id,
        execution_generation=1,
        recovery_epoch='1',
        worker_lease_id='lease-1',
        issued_at='2026-10-18T08:00:00Z',
        expires_at='2026-10-18T09:00:00Z',
        allowed_operation=allowed_operation,
        input_fingerprint='fp-1',
    )


def make_request(activity_name: str, stage_run_id: str = 'stage-1', claims: GrantClaims | None = None) -> dict[str, Any]:
    req: dict[str, Any] = {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'run-1',
        'stage_run_id': stage_run_id,
        'activity_name': activity_name,
        'activity_version': '1',
        'input_refs': [{'ref_type': 'input', 'ref_id': 'in-1'}],
        'operation_key': 'opk-1',
        'capability_requirements': {'task_queue': 'cloud-io'},
        'retry_policy_ref': 'ref-1',
    }
    if claims is not None:
        req['execution_grant'] = asdict(claims)
    return req


def test_every_stage_has_a_queue():
    validate_catalog()
    for wf_name in WORKFLOW_NAMES:
        spec = get_workflow(wf_name)
        for stage in spec.stages:
            q = route_stage(stage.stage_type)
            assert isinstance(q, TaskQueue)
            if stage.stage_type in ('script', 'plan', 'tts'):
                assert q in DESKTOP_QUEUES
                assert q not in (TaskQueue.CLOUD_IO, TaskQueue.CLOUD_AI)

    bad_routes = dict(STAGE_QUEUES)
    bad_routes['script'] = TaskQueue.CLOUD_AI
    with pytest.raises(CatalogError) as exc_info:
        validate_catalog(routes=bad_routes)
    assert exc_info.value.code == 'R18_QUEUE_VIOLATION'


def test_bindings_follow_the_catalog():
    for binding in ACTIVITY_BINDINGS:
        if binding.stage_type is not None:
            assert binding.queue == route_stage(binding.stage_type)
            if binding.stage_type in ('script', 'plan', 'tts'):
                assert binding.queue in DESKTOP_QUEUES

    owners = {b.owner for b in ACTIVITY_BINDINGS}
    assert {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'I', 'J'}.issubset(owners)

    for wf_name, stage_map in STAGE_ACTIVITIES_BY_WORKFLOW.items():
        for stage_name, activity_names in stage_map.items():
            for name in activity_names:
                assert name in BINDINGS_BY_NAME
                binding = BINDINGS_BY_NAME[name]
                if wf_name != 'DebugStageWorkflow':
                    assert binding.stage_type == stage_name

    video_spec = get_workflow('VideoProductionWorkflow')
    assert set(VIDEO_STAGE_ACTIVITIES.keys()) == {s.stage_type for s in video_spec.stages}


def test_binding_names_match_real_handlers():
    assert source_ah.ACTIVITY_NAME in BINDINGS_BY_NAME
    assert BINDINGS_BY_NAME[source_ah.ACTIVITY_NAME].owner == 'A'

    assert ingestion_ah.ACTIVITY_NAME in BINDINGS_BY_NAME
    assert BINDINGS_BY_NAME[ingestion_ah.ACTIVITY_NAME].owner == 'B'

    for name in creative_ah.ACTIVITY_NAMES:
        assert name in BINDINGS_BY_NAME
        assert BINDINGS_BY_NAME[name].owner == 'D'

    for name in voice_ah.ACTIVITY_NAMES:
        assert name in BINDINGS_BY_NAME
        assert BINDINGS_BY_NAME[name].owner == 'E'

    for name in render_ah.ACTIVITY_NAMES:
        assert name in BINDINGS_BY_NAME
        assert BINDINGS_BY_NAME[name].owner == 'F'


def test_every_activity_has_a_handler():
    services = build_workflow_services(
        parameters=profile_parameters(),
        handlers={},
        clock=lambda: NOW,
        timezone_approved=False,
    )
    assert services.bound_activities == frozenset()

    for binding in ACTIVITY_BINDINGS:
        claims = make_claims('stage-1', binding.name)
        req = make_request(binding.name, 'stage-1', claims=claims)
        res = services.dispatcher.dispatch(req)
        assert res['disposition'] == 'failed'
        assert res.get('problem', {}).get('code') == 'ACTIVITY_SERVICE_UNBOUND'


def test_side_effect_activity_is_rejected_without_execution_grant():
    calls = []

    def fake_handler(req: Mapping[str, Any], claims: GrantClaims | None) -> dict[str, Any]:
        calls.append(req)
        return {
            'stage_run_id': req['stage_run_id'],
            'grant_id': claims.grant_id if claims else 'none',
            'execution_generation': 1,
            'recovery_epoch': '1',
            'disposition': 'succeeded',
            'output_refs': [],
            'completed_at': '2026-10-18T08:00:00Z',
        }

    services = build_workflow_services(
        parameters=profile_parameters(),
        handlers={'CollectSource': fake_handler},
        clock=lambda: NOW,
        timezone_approved=False,
    )

    req_no_grant = make_request('CollectSource', 'stage-1', claims=None)
    with pytest.raises(ActivityRejected) as raised:
        services.dispatcher.dispatch(req_no_grant)
    assert raised.value.code == MISSING_EXECUTION_GRANT
    assert len(calls) == 0

    valid_claims = make_claims('stage-1', 'CollectSource')
    req_valid = make_request('CollectSource', 'stage-1', claims=valid_claims)
    res = services.dispatcher.dispatch(req_valid)
    assert res['disposition'] == 'succeeded'
    assert len(calls) == 1

    mismatched_claims = make_claims('different-stage', 'CollectSource')
    req_mismatched = make_request('CollectSource', 'stage-1', claims=mismatched_claims)
    with pytest.raises(ActivityRejected) as raised_mismatch:
        services.dispatcher.dispatch(req_mismatched)
    assert raised_mismatch.value.code == INVALID_EXECUTION_GRANT
    assert len(calls) == 1


def test_config_comes_from_j():
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    params = profile_parameters()
    settings = settings_from_parameters(params)

    for q in TaskQueue:
        assert settings.start_to_close_seconds[q.value] == data['workflow']['start_to_close_seconds']['value'][q.value]
    assert settings.heartbeat_seconds == data['workflow']['heartbeat_seconds']['value']
    assert settings.retry.max_attempts == data['workflow']['retry']['value']['maximum_attempts']
    assert settings.retry.initial_delay_seconds == data['workflow']['retry']['value']['initial_interval_seconds']
    assert settings.retry.multiplier == data['workflow']['retry']['value']['backoff_coefficient']
    assert settings.retry.max_delay_seconds == data['workflow']['retry']['value']['maximum_interval_seconds']
    assert settings.capability_poll_seconds == data['ai']['quota_wait_poll_seconds']['value']
    assert settings.cloud_schedule_enabled == data['workflow']['schedule']['value']['cloud_schedule_enabled']

    missing_retry = dict(params)
    missing_retry.pop('workflow.retry')
    with pytest.raises(ValueError):
        settings_from_parameters(missing_retry)

    bad_stc = dict(params)
    bad_stc_map = dict(bad_stc['workflow.start_to_close_seconds'])
    bad_stc_map.pop(TaskQueue.CONTROL_WORKFLOWS.value)
    bad_stc['workflow.start_to_close_seconds'] = bad_stc_map
    with pytest.raises(ValueError):
        settings_from_parameters(bad_stc)


def test_schedule_not_ready_until_timezone_approved():
    settings = settings_from_parameters(profile_parameters())
    assert schedule_state(settings, timezone_approved=False) == NOT_READY

    settings_enabled = replace(settings, cloud_schedule_enabled=True)
    assert schedule_state(settings_enabled, timezone_approved=False) == NOT_READY

    settings_disabled = replace(settings, cloud_schedule_enabled=False)
    assert schedule_state(settings_disabled, timezone_approved=True) == NOT_READY

    assert schedule_state(settings_enabled, timezone_approved=True) == READY

    with pytest.raises(TypeError):
        schedule_state(settings, timezone_approved='yes')  # type: ignore[arg-type]


def test_workflows_and_signals_are_registered():
    workflow_classes = (
        DailyCollectionWorkflow,
        ContentEnrichmentWorkflow,
        ProductionBatchWorkflow,
        VideoProductionWorkflow,
        DebugStageWorkflow,
        MaintenanceWorkflow,
    )
    names = set()
    all_signals = set()
    for cls in workflow_classes:
        defn = _Definition.must_from_class(cls)
        names.add(defn.name)
        all_signals.update(defn.signals.keys())

    assert names == WORKFLOW_NAMES
    expected_signals = {'RunDebugStage', 'RetryStage', 'CreateNewVariant', 'RegenerateFromStage'}
    assert expected_signals.issubset(all_signals)


def test_subscription_collected_document_available_goes_to_b():
    assert SUBSCRIPTIONS['CollectedDocumentAvailable'] == 'ResolveCollectedDocument'
    assert source_collect.EVENT_DOCUMENT_AVAILABLE == 'CollectedDocumentAvailable'

    refs = document_input_refs(['d1', 'd2'])
    assert len(refs) == 2
    assert refs[0] == ({'ref_type': REF_TYPE_COLLECTED_DOCUMENT, 'ref_id': 'd1'},)
    assert refs[1] == ({'ref_type': REF_TYPE_COLLECTED_DOCUMENT, 'ref_id': 'd2'},)

    with pytest.raises(ValueError):
        document_input_refs(['d1', ''])


def test_temporal_registration_maps_every_activity_to_its_queue():
    services = build_workflow_services(
        parameters=profile_parameters(),
        handlers={},
        clock=lambda: NOW,
        timezone_approved=False,
    )
    reg = build_temporal_registration(
        services,
        grant_issuer=lambda *args: make_claims(),
        capability_reader=lambda: {'desktop_production': {'status': 'available'}},
    )

    assert len(reg.workflows) == 6
    registered_names = set()
    for queue_str, fns in reg.activities_by_queue.items():
        for fn in fns:
            act_name = getattr(fn, '__temporal_activity_definition', None)
            act_name_str = act_name.name if act_name else fn.__name__
            assert act_name_str not in registered_names
            registered_names.add(act_name_str)

            if act_name_str in BINDINGS_BY_NAME:
                assert queue_str == BINDINGS_BY_NAME[act_name_str].queue.value

    control_q = TaskQueue.CONTROL_WORKFLOWS.value
    assert 'IssueExecutionGrant' in [
        getattr(f, '__temporal_activity_definition', None).name
        for f in reg.activities_by_queue[control_q]
    ]
    assert 'ReadCapabilityView' in [
        getattr(f, '__temporal_activity_definition', None).name
        for f in reg.activities_by_queue[control_q]
    ]


def test_store_backed_claims_currency():
    claims = make_claims('stage-1', 'CollectSource')

    class FakeGrantStore:
        def __init__(self, current: GrantClaims | None):
            self.current = current

        def active_grant(self, stage_run_id: str, now: datetime.datetime) -> GrantClaims | None:
            return self.current

    store_ok = FakeGrantStore(claims)
    currency_ok = StoreBackedClaimsCurrency(store_ok, lambda: NOW)
    assert currency_ok.is_grant_current(claims) is True

    store_none = FakeGrantStore(None)
    currency_none = StoreBackedClaimsCurrency(store_none, lambda: NOW)
    assert currency_none.is_grant_current(claims) is False

    store_other = FakeGrantStore(replace(claims, execution_generation=2))
    currency_other = StoreBackedClaimsCurrency(store_other, lambda: NOW)
    assert currency_other.is_grant_current(claims) is False
