"""Pure, revision-aware state transitions for the foundational P4 aggregates."""

from dataclasses import dataclass
from enum import StrEnum

from controlplane.domain.concurrency import RevisionConflictError


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
    """A safe domain error for a transition that is not admitted by its state graph."""

    code = "FORBIDDEN_TRANSITION"

    def __init__(
        self,
        *,
        aggregate_type: str,
        current_state: StrEnum,
        requested_next_state: StrEnum,
        current_revision: int,
    ) -> None:
        super().__init__(f"Forbidden transition for {aggregate_type}.")
        self.aggregate_type = aggregate_type
        self.current_state = current_state
        self.requested_next_state = requested_next_state
        self.current_revision = current_revision


def _transition(
    *,
    aggregate_type: str,
    current_state: StrEnum,
    current_revision: int,
    expected_revision: int,
    requested_state: StrEnum,
    allowed_edges: frozenset[tuple[StrEnum, StrEnum]],
    evidence_required_edges: frozenset[tuple[StrEnum, StrEnum]],
    reconciliation_evidence: ReconciliationEvidence | None,
) -> TransitionResult:
    """Validate one pure transition without mutating aggregate or persistence state."""
    if expected_revision != current_revision:
        raise RevisionConflictError(current_revision)

    edge = (current_state, requested_state)
    if edge not in allowed_edges or (
        edge in evidence_required_edges and reconciliation_evidence is None
    ):
        raise ForbiddenTransitionError(
            aggregate_type=aggregate_type,
            current_state=current_state,
            requested_next_state=requested_state,
            current_revision=current_revision,
        )
    return TransitionResult(state=requested_state, revision=current_revision + 1)


_OPERATION_EDGES = frozenset(
    {
        (OperationState.PREPARED, OperationState.STARTED),
        (OperationState.STARTED, OperationState.SUCCEEDED),
        (OperationState.STARTED, OperationState.FAILED),
        (OperationState.STARTED, OperationState.OUTCOME_UNKNOWN),
        (OperationState.OUTCOME_UNKNOWN, OperationState.SUCCEEDED),
        (OperationState.OUTCOME_UNKNOWN, OperationState.FAILED),
    }
)
_OPERATION_EVIDENCE_EDGES = frozenset(
    {
        (OperationState.OUTCOME_UNKNOWN, OperationState.SUCCEEDED),
        (OperationState.OUTCOME_UNKNOWN, OperationState.FAILED),
    }
)

_BATCH_EDGES = frozenset(
    {
        (BatchState.CREATED, BatchState.RUNNING),
        (BatchState.RUNNING, BatchState.WAITING_CAPABILITY),
        (BatchState.WAITING_CAPABILITY, BatchState.RUNNING),
        *(
            (state, terminal)
            for state in (BatchState.RUNNING, BatchState.WAITING_CAPABILITY)
            for terminal in (
                BatchState.COMPLETED_TARGET,
                BatchState.COMPLETED_EXHAUSTED,
                BatchState.FAILED_SYSTEM,
            )
        ),
    }
)

_JOB_EDGES = frozenset(
    {
        (JobState.CREATED, JobState.SNAPSHOTTED),
        (JobState.SNAPSHOTTED, JobState.ACTIVE),
        (JobState.ACTIVE, JobState.WAITING),
        (JobState.WAITING, JobState.ACTIVE),
        (JobState.ACTIVE, JobState.READY_FOR_COMPLETION),
        (JobState.WAITING, JobState.READY_FOR_COMPLETION),
        (JobState.READY_FOR_COMPLETION, JobState.COMPLETED),
        (JobState.ACTIVE, JobState.FAILED_FINAL),
        (JobState.WAITING, JobState.FAILED_FINAL),
        (JobState.READY_FOR_COMPLETION, JobState.FAILED_FINAL),
    }
)

_STAGE_RUN_EDGES = frozenset(
    {
        (StageRunState.PENDING, StageRunState.WAITING_DEPENDENCY),
        (StageRunState.PENDING, StageRunState.WAITING_CAPABILITY),
        (StageRunState.PENDING, StageRunState.RUNNING),
        *(
            (StageRunState.RUNNING, state)
            for state in (
                StageRunState.SUCCEEDED,
                StageRunState.FAILED_RETRYABLE,
                StageRunState.FAILED_FINAL,
                StageRunState.OUTCOME_UNKNOWN,
                StageRunState.STALE,
            )
        ),
        *(
            (StageRunState.OUTCOME_UNKNOWN, state)
            for state in (
                StageRunState.SUCCEEDED,
                StageRunState.FAILED_RETRYABLE,
                StageRunState.FAILED_FINAL,
            )
        ),
    }
)
_STAGE_RUN_EVIDENCE_EDGES = frozenset(
    {
        (StageRunState.OUTCOME_UNKNOWN, StageRunState.SUCCEEDED),
        (StageRunState.OUTCOME_UNKNOWN, StageRunState.FAILED_RETRYABLE),
        (StageRunState.OUTCOME_UNKNOWN, StageRunState.FAILED_FINAL),
    }
)

_ARTIFACT_LOCATION_EDGES = frozenset(
    {
        (ArtifactLocationState.DECLARED, ArtifactLocationState.MATERIALIZING),
        (ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED),
        (ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING),
        (ArtifactLocationState.VERIFYING, ArtifactLocationState.VERIFIED),
        (ArtifactLocationState.VERIFYING, ArtifactLocationState.CORRUPT),
        (ArtifactLocationState.VERIFYING, ArtifactLocationState.MISSING),
        (ArtifactLocationState.VERIFYING, ArtifactLocationState.OUTCOME_UNKNOWN),
        (ArtifactLocationState.VERIFIED, ArtifactLocationState.CLEANUP_ELIGIBLE),
        (ArtifactLocationState.VERIFIED, ArtifactLocationState.MISSING),
        (ArtifactLocationState.CLEANUP_ELIGIBLE, ArtifactLocationState.CLEANUP_AUTHORIZED),
        (ArtifactLocationState.CLEANUP_AUTHORIZED, ArtifactLocationState.DELETED),
    }
)


def transition_operation(
    *,
    current_state: OperationState,
    current_revision: int,
    expected_revision: int,
    requested_state: OperationState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="operation",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_OPERATION_EDGES,
        evidence_required_edges=_OPERATION_EVIDENCE_EDGES,
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_batch(
    *,
    current_state: BatchState,
    current_revision: int,
    expected_revision: int,
    requested_state: BatchState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="batch",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_BATCH_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_job(
    *,
    current_state: JobState,
    current_revision: int,
    expected_revision: int,
    requested_state: JobState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="job",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_JOB_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_stage_run(
    *,
    current_state: StageRunState,
    current_revision: int,
    expected_revision: int,
    requested_state: StageRunState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="stage_run",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_STAGE_RUN_EDGES,
        evidence_required_edges=_STAGE_RUN_EVIDENCE_EDGES,
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_artifact_location(
    *,
    current_state: ArtifactLocationState,
    current_revision: int,
    expected_revision: int,
    requested_state: ArtifactLocationState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="artifact_location",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_ARTIFACT_LOCATION_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


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
