"""Structural domain types for the M2-P6 Behavioral RED boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReservationState(str, Enum):
    ACTIVE = "ACTIVE"
    CONVERTED = "CONVERTED"
    RELEASED = "RELEASED"


class OrchestrationContractError(Exception):
    """Contract-shaped error type; behavioral production mapping is not implemented."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ExecutionGrant:
    workspace_id: str
    operation_id: str
    job_id: str
    stage_run_id: str
    execution_generation: int
    recovery_epoch: int


@dataclass(frozen=True)
class AcceptedExecutionResult:
    grant: ExecutionGrant
    result_ref: str
    accepted: bool = True


@dataclass(frozen=True)
class VariantReservation:
    reservation_id: str
    workspace_id: str
    job_id: str
    fingerprint: str
    snapshot_scope: str
    validation_ref: str
    variation_policy_revision: str
    committed_registry_revision: int
    state: ReservationState


@dataclass(frozen=True)
class CapacityAllocation:
    workspace_id: str
    batch_id: str
    job_id: str
    reservation_id: str
    target_completed_videos: int
    state: ReservationState


@dataclass(frozen=True)
class CompletionLedger:
    ledger_id: str
    workspace_id: str
    job_id: str
    batch_id: str
    capacity_reservation_id: str
    variant_reservation_id: str
    output_artifact_version_id: str
    output_artifact_hash: str
    actor_ref: str
    completed_at: str
    audit_ref: str


__all__ = [
    "AcceptedExecutionResult",
    "CapacityAllocation",
    "CompletionLedger",
    "ExecutionGrant",
    "OrchestrationContractError",
    "ReservationState",
    "VariantReservation",
]
