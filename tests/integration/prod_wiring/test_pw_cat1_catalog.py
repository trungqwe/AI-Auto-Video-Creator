"""PW-CAT1: thứ tự stage v2, binding ReserveVariant và pha ValidateVariant."""
from __future__ import annotations

import dataclasses

import pytest

from controlplane.application.orchestration.workflows import activities
from controlplane.application.orchestration.workflows.activities import (
    ACTIVITY_BINDINGS, BINDINGS_BY_NAME, STAGE_ACTIVITIES_BY_WORKFLOW, VIDEO_STAGE_ACTIVITIES, ActivityBinding,
)
from controlplane.domain.orchestration.workflow_catalog import (
    WORKFLOW_CATALOG, StageSpec, TaskQueue, get_workflow, is_breaking_change, route_stage, validate_catalog,
)

V2_STAGES = ['analyze', 'script', 'media_select', 'plan', 'tts', 'align', 'process', 'render', 'qc', 'sync', 'complete']
V2_DEPS = {
    'analyze': (), 'script': ('analyze',), 'media_select': ('script',), 'plan': ('media_select',), 'tts': ('script',),
    'align': ('tts',), 'process': ('plan', 'align'), 'render': ('process',), 'qc': ('render',), 'sync': ('qc',), 'complete': ('sync',),
}
V1_STAGES = (
    StageSpec('analyze'), StageSpec('script', ('analyze',)), StageSpec('plan', ('script',)), StageSpec('media_select', ('plan',)),
    StageSpec('tts', ('script',)), StageSpec('align', ('tts',)), StageSpec('process', ('media_select', 'align')),
    StageSpec('render', ('process',)), StageSpec('qc', ('render',)), StageSpec('sync', ('qc',)), StageSpec('complete', ('sync',)),
)


def binding_mismatches(stage_map):
    bad = []
    for wf_name, stages in stage_map.items():
        if wf_name == 'DebugStageWorkflow':
            continue
        for stage, names in stages.items():
            for name in names:
                binding = BINDINGS_BY_NAME[name]
                if stage not in (binding.stage_type, *binding.extra_stage_types):
                    bad.append((wf_name, stage, name))
    return bad


def test_video_workflow_v2_order_dependencies_and_version():
    video = get_workflow('VideoProductionWorkflow')
    assert video.workflow_version == 2
    assert [s.stage_type for s in video.stages] == V2_STAGES
    assert {s.stage_type: s.depends_on for s in video.stages} == V2_DEPS
    assert validate_catalog() is None


def test_v1_to_v2_is_a_breaking_change():
    video = get_workflow('VideoProductionWorkflow')
    old = dataclasses.replace(video, workflow_version=1, stages=V1_STAGES)
    assert is_breaking_change(old, video) is True


def test_plan_runs_after_media_select_and_reserve_variant_before_render():
    order = [s.stage_type for s in get_workflow('VideoProductionWorkflow').stages]
    assert order.index('media_select') < order.index('plan') < order.index('render')
    reserve_stages = [st for st, names in VIDEO_STAGE_ACTIVITIES.items() if 'ReserveVariant' in names]
    assert reserve_stages == ['plan']
    assert order.index(reserve_stages[0]) < order.index('render')


def test_video_stage_activities_follow_the_v2_plan():
    assert VIDEO_STAGE_ACTIVITIES['plan'] == ('BuildProductionPlan', 'ValidateVariant', 'ReserveVariant', 'GenerateOutputMetadata')
    assert VIDEO_STAGE_ACTIVITIES['render'] == (
        'MaterializeArtifactSet', 'resolve_render_package', 'validate_render_package', 'reconcile_render', 'render_video',
    )
    assert VIDEO_STAGE_ACTIVITIES['qc'] == ('inspect_output', 'ValidateVariant', 'prepare_output_ready')
    assert VIDEO_STAGE_ACTIVITIES['process'] == ('ProbeMedia', 'AssessImageSafety', 'TransformSensitiveImage', 'NormalizeMedia', 'PrepareAudioBed')


def test_new_and_moved_bindings():
    expected = {
        'ReserveVariant': ('G', 'plan'), 'reconcile_render': ('F', 'render'), 'prepare_output_ready': ('F', 'qc'),
        'GenerateOutputMetadata': ('D', 'plan'), 'ValidateVariant': ('D', 'plan'),
    }
    for name, (owner, stage) in expected.items():
        binding = BINDINGS_BY_NAME[name]
        assert (binding.owner, binding.stage_type, binding.side_effect) == (owner, stage, True), name


def test_every_stage_activity_matches_its_binding():
    assert binding_mismatches(STAGE_ACTIVITIES_BY_WORKFLOW) == []


def test_binding_check_is_red_for_an_activity_outside_its_stage():
    for stage, name in (('qc', 'GenerateOutputMetadata'), ('render', 'ReserveVariant'), ('qc', 'BuildProductionPlan')):
        video = dict(VIDEO_STAGE_ACTIVITIES, **{stage: (*VIDEO_STAGE_ACTIVITIES[stage], name)})
        assert binding_mismatches({'VideoProductionWorkflow': video}) == [('VideoProductionWorkflow', stage, name)]


def test_only_validate_variant_has_extra_stage_types():
    assert {b.name for b in ACTIVITY_BINDINGS if b.extra_stage_types} == {'ValidateVariant'}
    assert BINDINGS_BY_NAME['ValidateVariant'].extra_stage_types == ('qc',)
    assert [st for st, names in VIDEO_STAGE_ACTIVITIES.items() if 'ValidateVariant' in names] == ['plan', 'qc']
    fields = dataclasses.fields(ActivityBinding)
    assert [f.name for f in fields][-2:] == ['side_effect', 'extra_stage_types']
    assert fields[-1].default == ()


def test_validate_variant_queue_is_the_plan_queue_and_stage_queues_are_unchanged():
    assert BINDINGS_BY_NAME['ValidateVariant'].queue == route_stage('plan') == TaskQueue.DESKTOP_CPU
    assert route_stage('qc') == TaskQueue.DESKTOP_RENDER


def test_fan_out_table_lists_exactly_the_four_activities():
    assert dict(activities.FAN_OUT_FROM_OUTPUT) == {
        'AssessImageSafety': ('media_select', 'selected_media'), 'ProbeMedia': ('media_select', 'selected_media'),
        'NormalizeMedia': ('media_select', 'selected_media'), 'CollectSource': ('select_sources', 'collection_source'),
    }
    with pytest.raises(TypeError):
        activities.FAN_OUT_FROM_OUTPUT['x'] = ('a', 'b')


def test_fan_out_previous_stage_precedes_the_activity_stage_in_its_workflow():
    for name, (previous, ref_type) in activities.FAN_OUT_FROM_OUTPUT.items():
        assert ref_type
        stage = BINDINGS_BY_NAME[name].stage_type
        orders = [[s.stage_type for s in spec.stages] for spec in WORKFLOW_CATALOG]
        hosts = [order for order in orders if stage in order]
        assert hosts and all(previous in order and order.index(previous) < order.index(stage) for order in hosts), name
