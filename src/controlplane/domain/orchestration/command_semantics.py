"""G-11: ngữ nghĩa retry, biến thể, regenerate và debug (CT-ORC-004, CT-ORC-005, CT-ORC-006, CT-WF-008).

Pure domain: không I/O, không đồng hồ, không đổi đối số.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from controlplane.domain.orchestration.stage_run_plan import ATTEMPT_SOURCE_STATES, StageRun

USE_REGENERATE_OR_VARIANT = 'USE_REGENERATE_OR_VARIANT'
STAGE_JOB_MISMATCH = 'STAGE_JOB_MISMATCH'
RETRY_NOT_ALLOWED = 'RETRY_NOT_ALLOWED'
UNKNOWN_STAGE = 'UNKNOWN_STAGE'
DEPENDENCY_CYCLE = 'DEPENDENCY_CYCLE'
INVALID_NEW_JOB_ID = 'INVALID_NEW_JOB_ID'
DEBUG_AUTO_ADVANCE_FORBIDDEN = 'DEBUG_AUTO_ADVANCE_FORBIDDEN'


class CommandSemanticsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require_ref(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _validated_graph(graph: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(graph, Mapping):
        raise ValueError('dependency_graph must be a mapping')
    result: dict[str, tuple[str, ...]] = {}
    for node, deps in graph.items():
        _require_ref('stage_type', node)
        if isinstance(deps, (str, bytes)) or not isinstance(deps, Sequence):
            raise ValueError('dependencies must be a sequence')
        result[node] = tuple(_require_ref('dependency', d) for d in deps)
    for deps in result.values():
        for d in deps:
            if d not in result:
                raise CommandSemanticsError(UNKNOWN_STAGE)
    return result


def _topological_order(graph: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    remaining = {n: set(d) for n, d in graph.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(n for n, d in remaining.items() if not d)
        if not ready:
            raise CommandSemanticsError(DEPENDENCY_CYCLE)
        for n in ready:
            order.append(n)
            del remaining[n]
        for d in remaining.values():
            d.difference_update(ready)
    return tuple(order)


@dataclass(frozen=True)
class JobContext:
    video_job_id: str
    snapshot_ref: str
    intent: str
    input_fingerprint: str
    parent_article_ref: str
    parent_event_ref: str

    def __post_init__(self) -> None:
        for name in ('video_job_id', 'snapshot_ref', 'intent', 'input_fingerprint', 'parent_article_ref', 'parent_event_ref'):
            _require_ref(name, getattr(self, name))


@dataclass(frozen=True)
class RetryDecision:
    video_job_id: str
    snapshot_ref: str
    intent: str
    input_fingerprint: str
    stage_type: str
    attempt: int
    completed_count_delta: int
    creates_new_job: bool


@dataclass(frozen=True)
class VariantDecision:
    video_job_id: str
    parent_job_id: str
    parent_article_ref: str
    parent_event_ref: str
    prior_variant_refs: tuple[str, ...]
    counts_toward_target: bool
    difference_validation_required: bool


@dataclass(frozen=True)
class RegenerateDecision:
    video_job_id: str
    from_stage_type: str
    revision_stage_types: tuple[str, ...]
    invalidates_downstream_refs: bool
    rewrites_history: bool
    completed_count_delta: int


@dataclass(frozen=True)
class DebugDecision:
    auto_advance: bool
    auto_run_stage_types: tuple[str, ...]


def decide_retry_stage(job: JobContext, stage: StageRun, new_input_fingerprint: str) -> RetryDecision:
    if not isinstance(job, JobContext):
        raise TypeError('job must be JobContext')
    if not isinstance(stage, StageRun):
        raise TypeError('stage must be StageRun')
    _require_ref('new_input_fingerprint', new_input_fingerprint)
    if stage.job_id != job.video_job_id:
        raise CommandSemanticsError(STAGE_JOB_MISMATCH)
    if new_input_fingerprint != job.input_fingerprint:
        raise CommandSemanticsError(USE_REGENERATE_OR_VARIANT)
    if stage.state not in ATTEMPT_SOURCE_STATES:
        raise CommandSemanticsError(RETRY_NOT_ALLOWED)
    return RetryDecision(
        video_job_id=job.video_job_id,
        snapshot_ref=job.snapshot_ref,
        intent=job.intent,
        input_fingerprint=job.input_fingerprint,
        stage_type=stage.stage_type,
        attempt=stage.attempt + 1,
        completed_count_delta=0,
        creates_new_job=False,
    )


def decide_new_variant(parent_job: JobContext, prior_variant_refs: Sequence[str], new_job_id: str) -> VariantDecision:
    if not isinstance(parent_job, JobContext):
        raise TypeError('parent_job must be JobContext')
    _require_ref('new_job_id', new_job_id)
    if isinstance(prior_variant_refs, (str, bytes)) or not isinstance(prior_variant_refs, Sequence):
        raise ValueError('prior_variant_refs must be a sequence')
    refs = tuple(_require_ref('prior_variant_ref', r) for r in prior_variant_refs)
    if new_job_id == parent_job.video_job_id:
        raise CommandSemanticsError(INVALID_NEW_JOB_ID)
    return VariantDecision(
        video_job_id=new_job_id,
        parent_job_id=parent_job.video_job_id,
        parent_article_ref=parent_job.parent_article_ref,
        parent_event_ref=parent_job.parent_event_ref,
        prior_variant_refs=refs,
        counts_toward_target=False,
        difference_validation_required=True,
    )


def decide_regenerate(stage: StageRun, dependency_graph: Mapping[str, Sequence[str]]) -> RegenerateDecision:
    if not isinstance(stage, StageRun):
        raise TypeError('stage must be StageRun')
    graph = _validated_graph(dependency_graph)
    if stage.stage_type not in graph:
        raise CommandSemanticsError(UNKNOWN_STAGE)
    order = _topological_order(graph)
    affected = {stage.stage_type}
    for node in order:
        if affected.intersection(graph[node]):
            affected.add(node)
    return RegenerateDecision(
        video_job_id=stage.job_id,
        from_stage_type=stage.stage_type,
        revision_stage_types=tuple(n for n in order if n in affected),
        invalidates_downstream_refs=True,
        rewrites_history=False,
        completed_count_delta=0,
    )


def validate_debug_request(auto_advance: bool) -> DebugDecision:
    if not isinstance(auto_advance, bool):
        raise TypeError('auto_advance must be bool')
    if auto_advance:
        raise CommandSemanticsError(DEBUG_AUTO_ADVANCE_FORBIDDEN)
    return DebugDecision(auto_advance=False, auto_run_stage_types=())


__all__ = [
    'CommandSemanticsError',
    'DEBUG_AUTO_ADVANCE_FORBIDDEN',
    'DEPENDENCY_CYCLE',
    'DebugDecision',
    'INVALID_NEW_JOB_ID',
    'JobContext',
    'RETRY_NOT_ALLOWED',
    'RegenerateDecision',
    'RetryDecision',
    'STAGE_JOB_MISMATCH',
    'UNKNOWN_STAGE',
    'USE_REGENERATE_OR_VARIANT',
    'VariantDecision',
    'decide_new_variant',
    'decide_regenerate',
    'decide_retry_stage',
    'validate_debug_request',
]
