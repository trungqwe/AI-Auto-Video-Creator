"""G-10: CommitVideoCompletion chạy trong một unit of work (CT-ORC-008; INV-010, INV-017).

G chỉ điều phối: ghi ledger, job, reservation, registry, bộ đếm, outbox và cleanup eligibility qua CompletionStorePort,
và gọi MediaUsagePort.record cho C (G không ghi bảng C). Module không có cổng xóa nào.

coveredIds: CT-ORC-008, INV-010, INV-017
"""
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from controlplane.application.orchestration.event_payloads import build_g_event
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.orchestration.completion_binding import validate_commit_request, validate_ledger_entry
from controlplane.domain.orchestration.completion_gate import ALREADY_COMPLETED, INVALID_REQUEST, GateAction, ReservationBinding, check_completion
from controlplane.domain.orchestration.fencing import FencingDecision
from controlplane.domain.statemachine import JobState, transition_job

COMPLETED = 'COMPLETED'
LEDGER_INVALID = 'LEDGER_INVALID'
CLEANUP_ELIGIBLE = 'CLEANUP_ELIGIBLE'


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    state: JobState
    revision: int


@dataclass(frozen=True)
class CompletionContext:
    completion_id: str
    batch_ref: str
    session_ref: str
    cloud_location_ref: str
    preset_revision_ref: str
    output_naming_metadata: Mapping[str, Any]
    cost_usage_summary: Mapping[str, Any]
    audit_actor: str
    cleanup_policy_ref: str
    completed_at: str
    fencing: FencingDecision
    variant_conflict_confirmed: bool = False


@dataclass(frozen=True)
class CompletionResult:
    code: str
    ledger: Mapping[str, Any]


class CompletionRejectedError(Exception):
    def __init__(self, code: str, action: GateAction) -> None:
        super().__init__(code)
        self.code = code
        self.action = action


class CompletionStorePort(Protocol):
    def find_ledger(self, video_job_id: str) -> Mapping[str, Any] | None: ...
    def get_job(self, job_id: str) -> JobRecord | None: ...
    def get_variant_reservation(self, reservation_id: str) -> ReservationBinding | None: ...
    def get_registry_revision(self) -> int: ...
    def insert_ledger(self, ledger: Mapping[str, Any]) -> None: ...
    def set_job_state(self, job_id: str, state: JobState, revision: int) -> None: ...
    def convert_capacity_reservation(self, job_id: str) -> None: ...
    def convert_variant_reservation(self, reservation_id: str) -> None: ...
    def set_registry_revision(self, revision: int) -> None: ...
    def increment_batch_completed(self, batch_ref: str) -> None: ...
    def insert_outbox(self, event: Mapping[str, Any]) -> None: ...
    def insert_cleanup_eligibility(self, record: Mapping[str, Any]) -> None: ...


class MediaUsagePort(Protocol):
    def record(self, manifest: list[Any]) -> None: ...


class CompletionUnitOfWork(IUnitOfWork):
    store: CompletionStorePort


def _build_ledger(request: Mapping[str, Any], context: CompletionContext) -> dict[str, Any]:
    ledger = {
        'completion_id': context.completion_id,
        'video_job_id': request['video_job_id'],
        'batch_ref': context.batch_ref,
        'session_ref': context.session_ref,
        'output_artifact_version_id': request['output_artifact_version_id'],
        'output_sha256': request['output_sha256'],
        'cloud_location_ref': context.cloud_location_ref,
        'snapshot_ref': request['snapshot_ref'],
        'script_version_ref': request['script_version_ref'],
        'production_plan_ref': request['production_plan_ref'],
        'preset_revision_ref': context.preset_revision_ref,
        'quality_report_ref': request['quality_report_ref'],
        'variant_validation_ref': request['variant_validation_ref'],
        'media_usage_manifest': request['media_usage_manifest'],
        'completed_at': context.completed_at,
        'output_naming_metadata': context.output_naming_metadata,
        'cost_usage_summary': context.cost_usage_summary,
        'audit_actor': context.audit_actor,
        'cleanup_policy_ref': context.cleanup_policy_ref,
    }
    return copy.deepcopy(ledger)

class CommitVideoCompletion:
    def __init__(self, uow_factory: Callable[[], CompletionUnitOfWork], media_usage: MediaUsagePort) -> None:
        self._uow_factory = uow_factory
        self._media_usage = media_usage


    def execute(self, request: Mapping[str, Any], context: CompletionContext) -> CompletionResult:
        if not isinstance(context, CompletionContext):
            raise TypeError('context must be a CompletionContext')
        uow = self._uow_factory()
        uow.begin()
        try:
            result, wrote = self._complete(uow.store, request, context)
            if wrote:
                uow.commit()
            else:
                uow.rollback()
        except BaseException:
            uow.rollback()
            raise
        return result

    def _complete(self, store: CompletionStorePort, request: Mapping[str, Any], context: CompletionContext) -> tuple[CompletionResult, bool]:
        if validate_commit_request(request):
            raise CompletionRejectedError(INVALID_REQUEST, GateAction.REJECT)
        job_id = request['video_job_id']
        reservation_id = request['variant_reservation_id']
        job = store.get_job(job_id)
        registry_revision = store.get_registry_revision()
        decision = check_completion(
            job.state if job is not None else None,
            request,
            context.fencing,
            store.get_variant_reservation(reservation_id),
            registry_revision,
            store.find_ledger(job_id),
            variant_conflict_confirmed=context.variant_conflict_confirmed,
        )
        if decision.action == GateAction.RETURN_EXISTING_LEDGER:
            return CompletionResult(ALREADY_COMPLETED, decision.ledger), False
        if decision.action != GateAction.PROCEED:
            raise CompletionRejectedError(decision.code, decision.action)
        ledger = _build_ledger(request, context)
        if validate_ledger_entry(ledger):
            raise CompletionRejectedError(LEDGER_INVALID, GateAction.REJECT)
        moved = transition_job(
            current_state=job.state,
            current_revision=job.revision,
            expected_revision=job.revision,
            requested_state=JobState.COMPLETED,
        )
        new_registry_revision = registry_revision + 1
        store.insert_ledger(ledger)
        store.set_job_state(job_id, moved.state, moved.revision)
        store.convert_capacity_reservation(job_id)
        store.convert_variant_reservation(reservation_id)
        store.set_registry_revision(new_registry_revision)
        store.increment_batch_completed(context.batch_ref)
        self._media_usage.record(copy.deepcopy(request['media_usage_manifest']))
        event = build_g_event(
            'VideoCompleted', job_id, moved.revision, request['recovery_epoch'],
            {'completion_id': context.completion_id, 'video_job_id': job_id, 'variant_registry_revision': new_registry_revision},
        )
        store.insert_outbox(event)
        store.insert_cleanup_eligibility({
            'completion_id': context.completion_id,
            'video_job_id': job_id,
            'output_artifact_version_id': request['output_artifact_version_id'],
            'cleanup_policy_ref': context.cleanup_policy_ref,
            'state': CLEANUP_ELIGIBLE,
        })
        return CompletionResult(COMPLETED, ledger), True


__all__ = [
    'CLEANUP_ELIGIBLE', 'COMPLETED', 'LEDGER_INVALID', 'CommitVideoCompletion', 'CompletionContext', 'CompletionRejectedError',
    'CompletionResult', 'CompletionStorePort', 'CompletionUnitOfWork', 'JobRecord', 'MediaUsagePort',
]
