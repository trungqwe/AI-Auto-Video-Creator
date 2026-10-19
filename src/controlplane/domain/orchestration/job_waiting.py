"""G-06: job waiting và cổng R18 (CT-ORC-007, CT-WF-007, CT-STATE-009, CT-CAP-003).

Pure domain: không I/O, không đồng hồ. Capability unavailable/unknown không đủ để chạy stage cần desktop (fail-closed); không bao giờ dẫn tới FAILED_FINAL hay tự thêm provider trả phí.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from controlplane.domain.orchestration.stage_run_plan import StageRun
from controlplane.domain.statemachine import ForbiddenTransitionError, JobState, StageRunState, TransitionResult, transition_job


class WaitReason(StrEnum):
    DESKTOP_OFFLINE = 'desktop_offline'
    LOCAL_AI_UNAVAILABLE = 'local_ai_unavailable'
    PROVIDER_UNAVAILABLE = 'provider_unavailable'
    QUOTA_WAIT = 'quota_wait'
    ARTIFACT_NOT_READY = 'artifact_not_ready'
    INSUFFICIENT_DISK = 'insufficient_disk'
    DEPENDENCY_WAIT = 'dependency_wait'
    CREDENTIAL_UNAVAILABLE = 'credential_unavailable'


DESKTOP_STAGE_TYPES = frozenset({'script', 'plan', 'tts'})
DESKTOP_CAPABILITY_KEY = 'desktop_production'
RUNNABLE_STATUSES = frozenset({'available', 'degraded'})


@dataclass(frozen=True)
class Proceed:
    pass


@dataclass(frozen=True)
class Wait:
    reason: WaitReason


def stage_requires_desktop(stage_type: str) -> bool:
    if not isinstance(stage_type, str):
        raise TypeError('stage_type must be str')
    return stage_type in DESKTOP_STAGE_TYPES


def evaluate_wait(stage_type: str, capability_view: Mapping[str, object] | None) -> Proceed | Wait:
    if not stage_requires_desktop(stage_type):
        return Proceed()
    entry = capability_view.get(DESKTOP_CAPABILITY_KEY) if isinstance(capability_view, Mapping) else None
    status = entry.get('status') if isinstance(entry, Mapping) else None
    if isinstance(status, str) and status in RUNNABLE_STATUSES:
        return Proceed()
    return Wait(WaitReason.DESKTOP_OFFLINE)


def plan_job_transition(*, current_state: JobState, current_revision: int, expected_revision: int, decision: Proceed | Wait) -> TransitionResult | None:
    if not isinstance(decision, (Proceed, Wait)):
        raise TypeError('decision must be Proceed or Wait')
    requested = JobState.WAITING if isinstance(decision, Wait) else JobState.ACTIVE
    if current_state not in (JobState.ACTIVE, JobState.WAITING):
        raise ForbiddenTransitionError(aggregate_type='job', current_state=current_state, requested_next_state=requested, current_revision=current_revision)
    if current_state == requested:
        return None
    return transition_job(current_state=current_state, current_revision=current_revision, expected_revision=expected_revision, requested_state=requested)


def on_capability_restored(runs: Sequence[StageRun], capability_view: Mapping[str, object] | None) -> tuple[str, ...]:
    restored: list[str] = []
    for run in runs:
        if run.state != StageRunState.WAITING_CAPABILITY:
            continue
        superseded = any(other.job_id == run.job_id and other.stage_type == run.stage_type and other.attempt > run.attempt for other in runs)
        if superseded:
            continue
        if isinstance(evaluate_wait(run.stage_type, capability_view), Proceed):
            restored.append(run.stage_run_id)
    return tuple(restored)


__all__ = ['DESKTOP_CAPABILITY_KEY', 'DESKTOP_STAGE_TYPES', 'RUNNABLE_STATUSES', 'Proceed', 'Wait', 'WaitReason', 'evaluate_wait', 'on_capability_restored', 'plan_job_transition', 'stage_requires_desktop']
