"""G-09: cổng điều kiện completion (CT-ORC-008 bước 1–2, CT-ORC-012, INV-010).

Pure domain: không I/O, không đồng hồ, không cổng ghi. Chỉ quyết định PROCEED mới cho phép G-10 mở unit of work để ghi.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration.completion_binding import validate_commit_request
from controlplane.domain.orchestration.fencing import FencingDecision
from controlplane.domain.statemachine import JobState

INVALID_REQUEST = 'INVALID_REQUEST'
ALREADY_COMPLETED = 'ALREADY_COMPLETED'
CONFLICT = 'CONFLICT'
JOB_NOT_READY = 'JOB_NOT_READY'
CLOUD_VERIFICATION_MISSING = 'CLOUD_VERIFICATION_MISSING'
RESERVATION_INVALID = 'RESERVATION_INVALID'
VARIANT_REGISTRY_STALE = 'VARIANT_REGISTRY_STALE'
VARIANT_CONFLICT_FINAL = 'VARIANT_CONFLICT_FINAL'
PROCEED = 'PROCEED'

LEDGER_COMPARED_FIELDS = (
    'video_job_id',
    'snapshot_ref',
    'script_version_ref',
    'production_plan_ref',
    'quality_report_ref',
    'output_artifact_version_id',
    'output_sha256',
    'variant_validation_ref',
    'media_usage_manifest',
)


class GateAction(StrEnum):
    PROCEED = 'PROCEED'
    REJECT = 'REJECT'
    RETURN_EXISTING_LEDGER = 'RETURN_EXISTING_LEDGER'
    KEEP_WAITING = 'KEEP_WAITING'
    FAIL_JOB_RELEASE = 'FAIL_JOB_RELEASE'


@dataclass(frozen=True)
class ReservationBinding:
    reservation_id: str
    job_id: str
    output_sha256: str
    state: ReservationState


@dataclass(frozen=True)
class GateDecision:
    code: str
    action: GateAction
    ledger: Mapping[str, object] | None = None


def _reject(code: str) -> GateDecision:
    return GateDecision(code, GateAction.REJECT)


def _is_revision(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _same_input(request: Mapping[str, object], ledger: Mapping[str, object]) -> bool:
    return all(field in ledger and ledger[field] == request[field] for field in LEDGER_COMPARED_FIELDS)


def _reservation_valid(reservation: object, request: Mapping[str, object]) -> bool:
    return (
        isinstance(reservation, ReservationBinding)
        and reservation.state == ReservationState.ACTIVE
        and reservation.job_id == request['video_job_id']
        and reservation.reservation_id == request['variant_reservation_id']
        and reservation.output_sha256 == request['output_sha256']
    )


def check_completion(
    job_state: object,
    request: Mapping[str, object],
    fencing: FencingDecision,
    reservation: ReservationBinding | None,
    current_registry_revision: int,
    existing_ledger: Mapping[str, object] | None,
    *,
    variant_conflict_confirmed: bool = False,
) -> GateDecision:
    if not isinstance(fencing, FencingDecision):
        raise TypeError('fencing must be FencingDecision')
    if existing_ledger is not None and not isinstance(existing_ledger, Mapping):
        raise TypeError('existing_ledger must be a mapping or None')
    if not isinstance(variant_conflict_confirmed, bool):
        raise TypeError('variant_conflict_confirmed must be bool')
    if validate_commit_request(request):
        return _reject(INVALID_REQUEST)
    if existing_ledger is not None:
        if _same_input(request, existing_ledger):
            return GateDecision(ALREADY_COMPLETED, GateAction.RETURN_EXISTING_LEDGER, existing_ledger)
        return _reject(CONFLICT)
    if job_state != JobState.READY_FOR_COMPLETION:
        return _reject(JOB_NOT_READY)
    if fencing.accepted is not True:
        return _reject(fencing.code)
    verification_ref = request['cloud_location_verification_ref']
    if not verification_ref.strip():
        return _reject(CLOUD_VERIFICATION_MISSING)
    if not _reservation_valid(reservation, request):
        return _reject(RESERVATION_INVALID)
    if not _is_revision(current_registry_revision) or current_registry_revision != request['expected_variant_registry_revision']:
        return GateDecision(VARIANT_REGISTRY_STALE, GateAction.KEEP_WAITING)
    if variant_conflict_confirmed:
        return GateDecision(VARIANT_CONFLICT_FINAL, GateAction.FAIL_JOB_RELEASE)
    return GateDecision(PROCEED, GateAction.PROCEED)


__all__ = [
    'ALREADY_COMPLETED', 'CLOUD_VERIFICATION_MISSING', 'CONFLICT', 'INVALID_REQUEST', 'JOB_NOT_READY', 'LEDGER_COMPARED_FIELDS',
    'PROCEED', 'RESERVATION_INVALID', 'VARIANT_CONFLICT_FINAL', 'VARIANT_REGISTRY_STALE',
    'GateAction', 'GateDecision', 'ReservationBinding', 'check_completion',
]
