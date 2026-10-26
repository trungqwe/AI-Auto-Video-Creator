"""G-12: workflow catalog, task queue logic và versioning (CT-WF-001, CT-WF-002, CT-WF-009; R18).

Pure domain: dữ liệu khai báo frozen, không I/O, không đồng hồ. Tên queue là queue logic; tên queue vật lý là cấu hình (CT-WF-002).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from controlplane.domain.orchestration.job_waiting import DESKTOP_STAGE_TYPES


class TaskQueue(StrEnum):
    CONTROL_WORKFLOWS = 'control-workflows'
    CLOUD_IO = 'cloud-io'
    CLOUD_AI = 'cloud-ai'
    DESKTOP_CPU = 'desktop-cpu'
    DESKTOP_GPU = 'desktop-gpu'
    DESKTOP_RENDER = 'desktop-render'


DESKTOP_QUEUES = frozenset({TaskQueue.DESKTOP_CPU, TaskQueue.DESKTOP_GPU, TaskQueue.DESKTOP_RENDER})


class RetrySemantics(StrEnum):
    TECHNICAL_ATTEMPT = 'technical_attempt'
    NO_AUTO_RETRY = 'no_auto_retry'


class CompletionInvariant(StrEnum):
    SOURCES_COLLECTED = 'sources_collected'
    ITEMS_ENRICHED = 'items_enriched'
    TARGET_REACHED_OR_EXHAUSTED = 'target_reached_or_exhausted'
    ALL_STAGES_OWNER_COMMITTED = 'all_stages_owner_committed'
    SINGLE_STAGE_OBSERVED = 'single_stage_observed'
    CHECKS_RECONCILED = 'checks_reconciled'


class CatalogError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StageSpec:
    stage_type: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    workflow_version: int
    stages: tuple[StageSpec, ...]
    retry_semantics: RetrySemantics
    completion_invariant: CompletionInvariant
    child_workflows: tuple[str, ...] = ()
    isolated_child: bool = False
    auto_advance: bool = True


WORKFLOW_NAMES = frozenset({
    'DailyCollectionWorkflow', 'ContentEnrichmentWorkflow', 'ProductionBatchWorkflow',
    'VideoProductionWorkflow', 'DebugStageWorkflow', 'MaintenanceWorkflow',
})
_Q = TaskQueue
STAGE_QUEUES: Mapping[str, TaskQueue] = MappingProxyType({
    'select_sources': _Q.CONTROL_WORKFLOWS, 'collect': _Q.CLOUD_IO,
    'normalize': _Q.CLOUD_IO, 'dedup': _Q.CLOUD_IO, 'enrich_ai': _Q.CLOUD_AI, 'media': _Q.CLOUD_IO, 'index': _Q.CLOUD_IO,
    'allocate': _Q.CONTROL_WORKFLOWS, 'run_videos': _Q.CONTROL_WORKFLOWS,
    'analyze': _Q.DESKTOP_CPU, 'script': _Q.DESKTOP_GPU, 'plan': _Q.DESKTOP_CPU, 'media_select': _Q.DESKTOP_CPU,
    'tts': _Q.DESKTOP_GPU, 'align': _Q.DESKTOP_CPU, 'process': _Q.DESKTOP_CPU,
    'render': _Q.DESKTOP_RENDER, 'qc': _Q.DESKTOP_RENDER, 'sync': _Q.CLOUD_IO, 'complete': _Q.CONTROL_WORKFLOWS,
    'debug_observe': _Q.CONTROL_WORKFLOWS, 'reconcile': _Q.CLOUD_IO, 'cleanup': _Q.CLOUD_IO, 'backup_check': _Q.CLOUD_IO,
})


def _stage(stage_type: str, *depends_on: str) -> StageSpec:
    return StageSpec(stage_type, tuple(depends_on))


_RETRY = RetrySemantics.TECHNICAL_ATTEMPT
_CI = CompletionInvariant
WORKFLOW_CATALOG: tuple[WorkflowSpec, ...] = (
    WorkflowSpec('DailyCollectionWorkflow', 1, (_stage('select_sources'), _stage('collect', 'select_sources')), _RETRY, _CI.SOURCES_COLLECTED),
    WorkflowSpec(
        'ContentEnrichmentWorkflow', 1,
        (_stage('normalize'), _stage('dedup', 'normalize'), _stage('enrich_ai', 'dedup'), _stage('media', 'dedup'), _stage('index', 'enrich_ai', 'media')),
        _RETRY, _CI.ITEMS_ENRICHED,
    ),
    WorkflowSpec(
        'ProductionBatchWorkflow', 1, (_stage('allocate'), _stage('run_videos', 'allocate')), _RETRY, _CI.TARGET_REACHED_OR_EXHAUSTED,
        child_workflows=('VideoProductionWorkflow',),
    ),
    WorkflowSpec(
        'VideoProductionWorkflow', 2,
        (
            _stage('analyze'), _stage('script', 'analyze'), _stage('media_select', 'script'), _stage('plan', 'media_select'),
            _stage('tts', 'script'), _stage('align', 'tts'), _stage('process', 'plan', 'align'),
            _stage('render', 'process'), _stage('qc', 'render'), _stage('sync', 'qc'), _stage('complete', 'sync'),
        ),
        _RETRY, _CI.ALL_STAGES_OWNER_COMMITTED, isolated_child=True,
    ),
    WorkflowSpec('DebugStageWorkflow', 1, (_stage('debug_observe'),), RetrySemantics.NO_AUTO_RETRY, _CI.SINGLE_STAGE_OBSERVED, auto_advance=False),
    WorkflowSpec(
        'MaintenanceWorkflow', 1, (_stage('reconcile'), _stage('cleanup', 'reconcile'), _stage('backup_check', 'reconcile')),
        _RETRY, _CI.CHECKS_RECONCILED,
    ),
)


def _lookup(routes: Mapping[str, TaskQueue], stage_type: str) -> TaskQueue:
    if not isinstance(stage_type, str):
        raise TypeError('stage_type must be str')
    queue = routes.get(stage_type)
    if not isinstance(queue, TaskQueue):
        raise CatalogError('STAGE_WITHOUT_QUEUE')
    return queue


def route_stage(stage_type: str) -> TaskQueue:
    return _lookup(STAGE_QUEUES, stage_type)


def get_workflow(name: str) -> WorkflowSpec:
    for spec in WORKFLOW_CATALOG:
        if spec.name == name:
            return spec
    raise CatalogError('UNKNOWN_WORKFLOW')


def _check_stage_graph(spec: WorkflowSpec) -> None:
    names = [stage.stage_type for stage in spec.stages]
    if len(set(names)) != len(names):
        raise CatalogError('DUPLICATE_STAGE')
    for stage in spec.stages:
        if any(dep not in names for dep in stage.depends_on):
            raise CatalogError('UNKNOWN_DEPENDENCY')
    pending = {stage.stage_type: set(stage.depends_on) for stage in spec.stages}
    while pending:
        ready = [name for name, deps in pending.items() if not deps]
        if not ready:
            raise CatalogError('DEPENDENCY_CYCLE')
        for name in ready:
            del pending[name]
        for deps in pending.values():
            deps.difference_update(ready)


def _check_policy(spec: WorkflowSpec, by_name: Mapping[str, WorkflowSpec]) -> None:
    version = spec.workflow_version
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CatalogError('INVALID_VERSION')
    for child in spec.child_workflows:
        target = by_name.get(child)
        if target is None or not target.isolated_child:
            raise CatalogError('CHILD_NOT_ISOLATED')
    if spec.name == 'VideoProductionWorkflow' and not spec.isolated_child:
        raise CatalogError('CHILD_NOT_ISOLATED')
    if spec.name == 'ProductionBatchWorkflow' and 'VideoProductionWorkflow' not in spec.child_workflows:
        raise CatalogError('CHILD_NOT_ISOLATED')
    if spec.name == 'DebugStageWorkflow' and spec.auto_advance is not False:
        raise CatalogError('DEBUG_AUTO_ADVANCE')


def validate_catalog(catalog: Sequence[WorkflowSpec] = WORKFLOW_CATALOG, routes: Mapping[str, TaskQueue] = STAGE_QUEUES) -> None:
    names = [spec.name for spec in catalog]
    if len(set(names)) != len(names):
        raise CatalogError('DUPLICATE_WORKFLOW')
    if set(names) != WORKFLOW_NAMES:
        raise CatalogError('CATALOG_INCOMPLETE')
    by_name = {spec.name: spec for spec in catalog}
    for spec in catalog:
        _check_stage_graph(spec)
        for stage in spec.stages:
            _lookup(routes, stage.stage_type)
        _check_policy(spec, by_name)
    for stage_type in sorted(DESKTOP_STAGE_TYPES):
        if _lookup(routes, stage_type) not in DESKTOP_QUEUES:
            raise CatalogError('R18_QUEUE_VIOLATION')


def _order_signature(spec: WorkflowSpec) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((stage.stage_type, tuple(sorted(stage.depends_on))) for stage in spec.stages)


def is_breaking_change(old: WorkflowSpec, new: WorkflowSpec) -> bool:
    if not isinstance(old, WorkflowSpec) or not isinstance(new, WorkflowSpec):
        raise TypeError('old and new must be WorkflowSpec')
    if old.name != new.name:
        raise CatalogError('WORKFLOW_NAME_MISMATCH')
    return (
        _order_signature(old) != _order_signature(new)
        or old.retry_semantics != new.retry_semantics
        or old.completion_invariant != new.completion_invariant
    )


__all__ = [
    'DESKTOP_QUEUES', 'STAGE_QUEUES', 'WORKFLOW_CATALOG', 'WORKFLOW_NAMES', 'CatalogError', 'CompletionInvariant',
    'RetrySemantics', 'StageSpec', 'TaskQueue', 'WorkflowSpec', 'get_workflow', 'is_breaking_change', 'route_stage', 'validate_catalog',
]
