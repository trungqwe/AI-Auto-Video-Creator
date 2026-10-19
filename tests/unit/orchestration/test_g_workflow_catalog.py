"""G-12: workflow catalog, task queue và versioning (CT-WF-001, CT-WF-002, CT-WF-009; R18).

coveredIds: CT-WF-001, CT-WF-002, CT-WF-009
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from controlplane.domain.orchestration.workflow_catalog import (
    STAGE_QUEUES, WORKFLOW_CATALOG, CatalogError, CompletionInvariant, RetrySemantics, StageSpec, TaskQueue, WorkflowSpec,
    get_workflow, is_breaking_change, route_stage, validate_catalog,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'workflow_catalog.py'
SIX = ['DailyCollectionWorkflow', 'ContentEnrichmentWorkflow', 'ProductionBatchWorkflow', 'VideoProductionWorkflow', 'DebugStageWorkflow', 'MaintenanceWorkflow']
QUEUES = ['control-workflows', 'cloud-io', 'cloud-ai', 'desktop-cpu', 'desktop-gpu', 'desktop-render']
VIDEO_STAGES = ['analyze', 'script', 'plan', 'media_select', 'tts', 'align', 'process', 'render', 'qc', 'sync', 'complete']
R18_STAGES = ['script', 'plan', 'tts']
Q = TaskQueue


def _catalog(**changes):
    return tuple(dataclasses.replace(s, **changes[s.name]) if s.name in changes else s for s in WORKFLOW_CATALOG)


def _video(**changes):
    return dataclasses.replace(get_workflow('VideoProductionWorkflow'), **changes)


def _code(catalog=WORKFLOW_CATALOG, routes=STAGE_QUEUES):
    with pytest.raises(CatalogError) as info:
        validate_catalog(catalog, routes)
    return info.value.code


def test_catalog_has_exactly_the_six_ct_wf_001_workflows():
    assert [s.name for s in WORKFLOW_CATALOG] == SIX


def test_task_queue_has_exactly_the_six_ct_wf_002_values():
    assert [q.value for q in TaskQueue] == QUEUES


def test_every_workflow_has_version_and_stages():
    assert len(WORKFLOW_CATALOG) == 6
    for spec in WORKFLOW_CATALOG:
        assert isinstance(spec.workflow_version, int) and not isinstance(spec.workflow_version, bool) and spec.workflow_version >= 1
        assert isinstance(spec.stages, tuple) and spec.stages
        assert all(isinstance(stage, StageSpec) for stage in spec.stages)


def test_catalog_data_is_frozen():
    assert isinstance(WORKFLOW_CATALOG, tuple) and WORKFLOW_CATALOG
    spec = WORKFLOW_CATALOG[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.workflow_version = 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.stages[0].stage_type = 'x'
    with pytest.raises(TypeError):
        STAGE_QUEUES['script'] = Q.CLOUD_AI


def test_shipped_catalog_is_valid():
    assert validate_catalog() is None


def test_video_production_stage_order_and_dependencies():
    video = get_workflow('VideoProductionWorkflow')
    assert [stage.stage_type for stage in video.stages] == VIDEO_STAGES
    deps = {stage.stage_type: stage.depends_on for stage in video.stages}
    assert deps['analyze'] == () and deps['script'] == ('analyze',) and deps['plan'] == ('script',)
    assert deps['process'] == ('media_select', 'align') and deps['complete'] == ('sync',)


def test_get_workflow_unknown_name_is_rejected():
    with pytest.raises(CatalogError) as info:
        get_workflow('NoSuchWorkflow')
    assert info.value.code == 'UNKNOWN_WORKFLOW'


@pytest.mark.parametrize('stage_type, queue', [
    ('collect', 'cloud-io'), ('enrich_ai', 'cloud-ai'), ('analyze', 'desktop-cpu'), ('plan', 'desktop-cpu'),
    ('script', 'desktop-gpu'), ('tts', 'desktop-gpu'), ('render', 'desktop-render'), ('qc', 'desktop-render'),
    ('sync', 'cloud-io'), ('complete', 'control-workflows'),
])
def test_route_stage_maps_stage_type_to_logical_queue(stage_type, queue):
    assert route_stage(stage_type) == queue


@pytest.mark.parametrize('stage_type', R18_STAGES)
def test_r18_stages_route_to_desktop_queues(stage_type):
    assert route_stage(stage_type) in {Q.DESKTOP_CPU, Q.DESKTOP_GPU, Q.DESKTOP_RENDER}


def test_every_catalog_stage_has_a_queue_and_all_six_queues_are_used():
    assert WORKFLOW_CATALOG
    for spec in WORKFLOW_CATALOG:
        for stage in spec.stages:
            assert isinstance(route_stage(stage.stage_type), TaskQueue)
    assert set(STAGE_QUEUES.values()) == set(TaskQueue)


def test_route_stage_rejects_unknown_stage_and_non_str():
    with pytest.raises(CatalogError) as info:
        route_stage('teleport')
    assert info.value.code == 'STAGE_WITHOUT_QUEUE'
    for bad in (None, 5, b'script', ['script']):
        with pytest.raises(TypeError):
            route_stage(bad)


def test_cycle_is_rejected_including_self_dependency():
    for deps in (('complete',), ('analyze',)):
        stages = (StageSpec('analyze', deps),) + _video().stages[1:]
        assert _code(_catalog(VideoProductionWorkflow={'stages': stages})) == 'DEPENDENCY_CYCLE'
    two = (StageSpec('select_sources', ('collect',)), StageSpec('collect', ('select_sources',)))
    assert _code(_catalog(DailyCollectionWorkflow={'stages': two})) == 'DEPENDENCY_CYCLE'


def test_unknown_dependency_and_duplicate_stage_are_rejected():
    stages = _video().stages
    assert _code(_catalog(VideoProductionWorkflow={'stages': (StageSpec('analyze', ('ghost',)),) + stages[1:]})) == 'UNKNOWN_DEPENDENCY'
    assert _code(_catalog(VideoProductionWorkflow={'stages': stages + (stages[0],)})) == 'DUPLICATE_STAGE'


def test_stage_without_queue_is_rejected():
    stages = _video().stages + (StageSpec('teleport', ('complete',)),)
    assert _code(_catalog(VideoProductionWorkflow={'stages': stages})) == 'STAGE_WITHOUT_QUEUE'
    assert _code(routes={k: v for k, v in STAGE_QUEUES.items() if k != 'script'}) == 'STAGE_WITHOUT_QUEUE'
    assert _code(routes=dict(STAGE_QUEUES, script='desktop-gpu')) == 'STAGE_WITHOUT_QUEUE'


@pytest.mark.parametrize('queue', [Q.CLOUD_IO, Q.CLOUD_AI, Q.CONTROL_WORKFLOWS])
@pytest.mark.parametrize('stage_type', R18_STAGES)
def test_r18_stage_on_non_desktop_queue_is_rejected(stage_type, queue):
    assert _code(routes=dict(STAGE_QUEUES, **{stage_type: queue})) == 'R18_QUEUE_VIOLATION'


def test_incomplete_or_duplicate_catalog_is_rejected():
    assert _code(WORKFLOW_CATALOG[:-1]) == 'CATALOG_INCOMPLETE'
    assert _code(WORKFLOW_CATALOG + (WORKFLOW_CATALOG[0],)) == 'DUPLICATE_WORKFLOW'


def test_video_production_is_an_isolated_child_of_the_batch():
    assert get_workflow('VideoProductionWorkflow').isolated_child is True
    assert get_workflow('ProductionBatchWorkflow').child_workflows == ('VideoProductionWorkflow',)
    assert _code(_catalog(VideoProductionWorkflow={'isolated_child': False})) == 'CHILD_NOT_ISOLATED'
    assert _code(_catalog(ProductionBatchWorkflow={'child_workflows': ()})) == 'CHILD_NOT_ISOLATED'
    assert _code(_catalog(ProductionBatchWorkflow={'child_workflows': ('VideoProductionWorkflow', 'Ghost')})) == 'CHILD_NOT_ISOLATED'


def test_debug_stage_never_auto_advances():
    debug = get_workflow('DebugStageWorkflow')
    assert debug.auto_advance is False and len(debug.stages) == 1
    assert _code(_catalog(DebugStageWorkflow={'auto_advance': True})) == 'DEBUG_AUTO_ADVANCE'


@pytest.mark.parametrize('version', [0, -1, True, '1', None, 1.0])
def test_invalid_workflow_version_is_rejected(version):
    assert _code(_catalog(DailyCollectionWorkflow={'workflow_version': version})) == 'INVALID_VERSION'


def _swap(stages, first, second):
    items = list(stages)
    names = [stage.stage_type for stage in items]
    i, j = names.index(first), names.index(second)
    items[i], items[j] = items[j], items[i]
    return tuple(items)


def test_unchanged_workflow_and_version_bump_are_not_breaking():
    video = get_workflow('VideoProductionWorkflow')
    assert is_breaking_change(video, video) is False
    assert is_breaking_change(video, _video(workflow_version=video.workflow_version + 1)) is False


def test_dependency_listing_order_is_not_breaking():
    video = get_workflow('VideoProductionWorkflow')
    stages = tuple(StageSpec('process', ('align', 'media_select')) if s.stage_type == 'process' else s for s in video.stages)
    assert is_breaking_change(video, _video(stages=stages)) is False


def test_stage_order_change_is_breaking():
    video = get_workflow('VideoProductionWorkflow')
    assert is_breaking_change(video, _video(stages=_swap(video.stages, 'media_select', 'tts'))) is True
    assert is_breaking_change(video, _video(stages=video.stages + (StageSpec('archive', ('complete',)),))) is True
    assert is_breaking_change(video, _video(stages=video.stages[:-1])) is True
    plan_dep = tuple(StageSpec('plan', ('analyze',)) if s.stage_type == 'plan' else s for s in video.stages)
    assert is_breaking_change(video, _video(stages=plan_dep)) is True


def test_retry_semantics_or_completion_invariant_change_is_breaking():
    video = get_workflow('VideoProductionWorkflow')
    assert is_breaking_change(video, _video(retry_semantics=RetrySemantics.NO_AUTO_RETRY)) is True
    assert is_breaking_change(video, _video(completion_invariant=CompletionInvariant.SINGLE_STAGE_OBSERVED)) is True


def test_is_breaking_change_rejects_mismatched_or_bad_arguments():
    assert WORKFLOW_CATALOG
    with pytest.raises(CatalogError) as info:
        is_breaking_change(WORKFLOW_CATALOG[0], WORKFLOW_CATALOG[1])
    assert info.value.code == 'WORKFLOW_NAME_MISMATCH'
    with pytest.raises(TypeError):
        is_breaking_change(WORKFLOW_CATALOG[0], 'x')


def test_module_imports_only_stdlib_and_controlplane_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'collections', 'dataclasses', 'enum', 'types', 'controlplane'}
    assert internal == {'controlplane.domain.orchestration.job_waiting'}
