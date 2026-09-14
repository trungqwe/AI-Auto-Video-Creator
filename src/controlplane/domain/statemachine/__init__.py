"""Structural P4 state-machine seams; behavioral rules begin only after RED review."""

from dataclasses import dataclass
from enum import StrEnum


class OperationState(StrEnum):
    PREPARED = "PREPARED"
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class BatchState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_CAPABILITY = "WAITING_CAPABILITY"
    COMPLETED_TARGET = "COMPLETED_TARGET"
    COMPLETED_EXHAUSTED = "COMPLETED_EXHAUSTED"
    FAILED_SYSTEM = "FAILED_SYSTEM"


class JobState(StrEnum):
    CREATED = "CREATED"
    SNAPSHOTTED = "SNAPSHOTTED"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    READY_FOR_COMPLETION = "READY_FOR_COMPLETION"
    COMPLETED = "COMPLETED"
    FAILED_FINAL = "FAILED_FINAL"


class StageRunState(StrEnum):
    PENDING = "PENDING"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    WAITING_CAPABILITY = "WAITING_CAPABILITY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    STALE = "STALE"


class ArtifactLocationState(StrEnum):
    DECLARED = "DECLARED"
    MATERIALIZING = "MATERIALIZING"
    AVAILABLE_UNVERIFIED = "AVAILABLE_UNVERIFIED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    CORRUPT = "CORRUPT"
    MISSING = "MISSING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CLEANUP_ELIGIBLE = "CLEANUP_ELIGIBLE"
    CLEANUP_AUTHORIZED = "CLEANUP_AUTHORIZED"
    DELETED = "DELETED"


@dataclass(frozen=True)
class TransitionResult:
    state: StrEnum
    revision: int


@dataclass(frozen=True)
class ReconciliationEvidence:
    reference: str


class ForbiddenTransitionError(Exception):
    """Structural error type; safe error semantics are not implemented during RED."""


def transition_operation(
    *,
    current_state: OperationState,
    current_revision: int,
    expected_revision: int,
    requested_state: OperationState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    raise NotImplementedError


def transition_batch(
    *,
    current_state: BatchState,
    current_revision: int,
    expected_revision: int,
    requested_state: BatchState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    raise NotImplementedError


def transition_job(
    *,
    current_state: JobState,
    current_revision: int,
    expected_revision: int,
    requested_state: JobState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    raise NotImplementedError


def transition_stage_run(
    *,
    current_state: StageRunState,
    current_revision: int,
    expected_revision: int,
    requested_state: StageRunState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    raise NotImplementedError


def transition_artifact_location(
    *,
    current_state: ArtifactLocationState,
    current_revision: int,
    expected_revision: int,
    requested_state: ArtifactLocationState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    raise NotImplementedError


__all__ = [
    "ArtifactLocationState",
    "BatchState",
    "ForbiddenTransitionError",
    "JobState",
    "OperationState",
    "ReconciliationEvidence",
    "StageRunState",
    "TransitionResult",
    "transition_artifact_location",
    "transition_batch",
    "transition_job",
    "transition_operation",
    "transition_stage_run",
]
