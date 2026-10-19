"""G-08: luồng VariantReservation và registry revision (CT-ORC-012; TST-WF-VAR-001, 003, 004)."""
from __future__ import annotations

from dataclasses import dataclass, replace
import threading
from typing import Protocol
import uuid

from controlplane.domain.orchestration import OrchestrationContractError, ReservationState
from controlplane.domain.statemachine import JobState


@dataclass(frozen=True)
class ReserveVariantRequest:
    workspace_id: str
    job_id: str
    fingerprint: str
    snapshot_scope: str
    validation_ref: str
    variation_policy_revision: str
    expected_registry_revision: int
    idempotency_key: str


@dataclass(frozen=True)
class VariantReservationRecord:
    reservation_id: str
    workspace_id: str
    job_id: str
    fingerprint: str
    snapshot_scope: str
    validation_ref: str
    variation_policy_revision: str
    expected_registry_revision: int
    committed_registry_revision: int
    idempotency_key: str
    state: ReservationState


@dataclass(frozen=True)
class VariantReceipt:
    reservation_id: str
    workspace_id: str
    job_id: str
    state: ReservationState
    committed_registry_revision: int
    idempotency_key: str


class VariantRegistryPort(Protocol):
    def current_revision(self, workspace_id: str) -> int: ...
    def find_by_job(self, workspace_id: str, job_id: str) -> VariantReservationRecord | None: ...
    def find_active_by_fingerprint(self, workspace_id: str, fingerprint: str) -> VariantReservationRecord | None: ...
    def save(self, record: VariantReservationRecord) -> None: ...
    def bump_revision(self, workspace_id: str) -> int: ...


_FLOW_LOCK = threading.Lock()
_TEXT_FIELDS = ('workspace_id', 'job_id', 'fingerprint', 'snapshot_scope', 'validation_ref', 'variation_policy_revision', 'idempotency_key')
_INPUT_FIELDS = ('fingerprint', 'snapshot_scope', 'validation_ref', 'variation_policy_revision', 'expected_registry_revision', 'idempotency_key')


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')


def _validate(request: object) -> None:
    if not isinstance(request, ReserveVariantRequest):
        raise TypeError('request must be a ReserveVariantRequest')
    for name in _TEXT_FIELDS:
        _require_text(name, getattr(request, name))
    revision = request.expected_registry_revision
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError('expected_registry_revision must be a positive int')


def _receipt(record: VariantReservationRecord) -> VariantReceipt:
    return VariantReceipt(
        record.reservation_id, record.workspace_id, record.job_id,
        record.state, record.committed_registry_revision, record.idempotency_key,
    )


def _same_input(record: VariantReservationRecord, request: ReserveVariantRequest) -> bool:
    return all(getattr(record, name) == getattr(request, name) for name in _INPUT_FIELDS)


class VariantReservationFlow:
    def __init__(self, registry: VariantRegistryPort) -> None:
        self._registry = registry

    def reserve(self, request: ReserveVariantRequest) -> VariantReceipt:
        _validate(request)
        with _FLOW_LOCK:
            existing = self._registry.find_by_job(request.workspace_id, request.job_id)
            if existing is not None:
                if _same_input(existing, request):
                    return _receipt(existing)
                raise OrchestrationContractError('VARIANT_CONFLICT')
            current = self._registry.current_revision(request.workspace_id)
            if current != request.expected_registry_revision:
                raise OrchestrationContractError('VARIANT_VALIDATION_STALE')
            rival = self._registry.find_active_by_fingerprint(request.workspace_id, request.fingerprint)
            if (
                rival is not None
                and rival.job_id != request.job_id
                and rival.state in (ReservationState.ACTIVE, ReservationState.CONVERTED)
            ):
                raise OrchestrationContractError('VARIANT_CONFLICT')
            record = VariantReservationRecord(
                reservation_id=str(uuid.uuid4()),
                workspace_id=request.workspace_id,
                job_id=request.job_id,
                fingerprint=request.fingerprint,
                snapshot_scope=request.snapshot_scope,
                validation_ref=request.validation_ref,
                variation_policy_revision=request.variation_policy_revision,
                expected_registry_revision=request.expected_registry_revision,
                committed_registry_revision=current + 1,
                idempotency_key=request.idempotency_key,
                state=ReservationState.ACTIVE,
            )
            self._registry.save(record)
            self._registry.bump_revision(request.workspace_id)
            return _receipt(record)

    def _settle(
        self, workspace_id: str, job_id: str, job_state: JobState, required: JobState, target: ReservationState
    ) -> VariantReceipt:
        _require_text('workspace_id', workspace_id)
        _require_text('job_id', job_id)
        if job_state != required:
            raise OrchestrationContractError('FORBIDDEN_TRANSITION')
        with _FLOW_LOCK:
            record = self._registry.find_by_job(workspace_id, job_id)
            if record is None:
                raise OrchestrationContractError('NOT_FOUND')
            if record.state == target:
                return _receipt(record)
            if record.state != ReservationState.ACTIVE:
                raise OrchestrationContractError('FORBIDDEN_TRANSITION')
            settled = replace(record, state=target)
            self._registry.save(settled)
            self._registry.bump_revision(workspace_id)
            return _receipt(settled)

    def release(self, workspace_id: str, job_id: str, job_state: JobState) -> VariantReceipt:
        return self._settle(workspace_id, job_id, job_state, JobState.FAILED_FINAL, ReservationState.RELEASED)

    def convert(self, workspace_id: str, job_id: str, job_state: JobState) -> VariantReceipt:
        return self._settle(workspace_id, job_id, job_state, JobState.COMPLETED, ReservationState.CONVERTED)

    def _unchanged(self, workspace_id: str, job_id: str) -> VariantReceipt | None:
        _require_text('workspace_id', workspace_id)
        _require_text('job_id', job_id)
        record = self._registry.find_by_job(workspace_id, job_id)
        return None if record is None else _receipt(record)

    def on_wait(self, workspace_id: str, job_id: str) -> VariantReceipt | None:
        return self._unchanged(workspace_id, job_id)

    def on_desktop_offline(self, workspace_id: str, job_id: str) -> VariantReceipt | None:
        return self._unchanged(workspace_id, job_id)

    def on_lease_expired(self, workspace_id: str, job_id: str) -> VariantReceipt | None:
        return self._unchanged(workspace_id, job_id)


__all__ = ['OrchestrationContractError', 'ReserveVariantRequest', 'VariantReceipt', 'VariantRegistryPort', 'VariantReservationFlow', 'VariantReservationRecord']
