"""The fixed nine M2-P4 behavioral RED oracles for pure state-machine semantics."""
from __future__ import annotations

from collections.abc import Callable

import pytest

from controlplane.application.concurrency import RevisionConflictError
from controlplane.application.projections.operation_view_mapper import map_operation_view
from controlplane.domain.statemachine import (
    ArtifactLocationState,
    BatchState,
    ForbiddenTransitionError,
    JobState,
    OperationState,
    ReconciliationEvidence,
    StageRunState,
    TransitionResult,
    transition_artifact_location,
    transition_batch,
    transition_job,
    transition_operation,
    transition_stage_run,
)


Transition = Callable[..., TransitionResult]
REVISION = 41
RECONCILIATION = ReconciliationEvidence(reference="reconcile-evidence-001")


def _assert_valid(
    transition: Transition,
    current_state: object,
    requested_state: object,
    *,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> None:
    original_state = current_state
    result = transition(
        current_state=current_state,
        current_revision=REVISION,
        expected_revision=REVISION,
        requested_state=requested_state,
        reconciliation_evidence=reconciliation_evidence,
    )
    assert result == TransitionResult(state=requested_state, revision=REVISION + 1)
    assert current_state is original_state


def _assert_forbidden(
    transition: Transition,
    current_state: object,
    requested_state: object,
    *,
    aggregate_type: str,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> None:
    original_state = current_state
    original_revision = REVISION
    with pytest.raises(ForbiddenTransitionError) as raised:
        transition(
            current_state=current_state,
            current_revision=REVISION,
            expected_revision=REVISION,
            requested_state=requested_state,
            reconciliation_evidence=reconciliation_evidence,
        )
    error = raised.value
    assert error.code == "FORBIDDEN_TRANSITION"
    assert error.aggregate_type == aggregate_type
    assert error.current_state == current_state
    assert error.requested_next_state == requested_state
    assert error.current_revision == original_revision
    assert current_state is original_state
    assert REVISION == original_revision


def _assert_no_outgoing_edges(transition: Transition, current_state: object, *, aggregate_type: str) -> None:
    for requested_state in type(current_state):
        _assert_forbidden(transition, current_state, requested_state, aggregate_type=aggregate_type)


def test_tst_m2_p4_001_valid_lifecycle_transitions() -> None:
    """Every CT-STATE-011 edge succeeds only with its required explicit evidence."""
    for current_state, requested_state, evidence in (
        (OperationState.PREPARED, OperationState.STARTED, None),
        (OperationState.STARTED, OperationState.SUCCEEDED, None),
        (OperationState.STARTED, OperationState.FAILED, None),
        (OperationState.STARTED, OperationState.OUTCOME_UNKNOWN, None),
        (OperationState.OUTCOME_UNKNOWN, OperationState.SUCCEEDED, RECONCILIATION),
        (OperationState.OUTCOME_UNKNOWN, OperationState.FAILED, RECONCILIATION),
    ):
        _assert_valid(transition_operation, current_state, requested_state, reconciliation_evidence=evidence)


def test_tst_m2_p4_002_forbidden_transition_completed_to_running_rejected() -> None:
    """Completed Job and terminal Batch states cannot regress to active/running work."""
    _assert_forbidden(transition_job, JobState.COMPLETED, JobState.ACTIVE, aggregate_type="job")
    for terminal_state in (
        BatchState.COMPLETED_TARGET,
        BatchState.COMPLETED_EXHAUSTED,
        BatchState.FAILED_SYSTEM,
    ):
        _assert_forbidden(transition_batch, terminal_state, BatchState.RUNNING, aggregate_type="batch")


def test_tst_m2_p4_003_operation_execution_to_projection_mapping() -> None:
    """Only STARTED with an explicit structured wait reason maps to waiting."""
    wait_reason = {"code": "CAPABILITY_UNAVAILABLE"}
    assert map_operation_view(execution_state=OperationState.PREPARED) == "accepted"
    assert map_operation_view(execution_state=OperationState.STARTED) == "running"
    assert map_operation_view(execution_state=OperationState.STARTED, wait_reason=wait_reason) == "waiting"
    assert map_operation_view(execution_state=OperationState.SUCCEEDED) == "succeeded"
    assert map_operation_view(execution_state=OperationState.FAILED) == "failed"
    assert map_operation_view(execution_state=OperationState.OUTCOME_UNKNOWN) == "outcome_unknown"
    for state in (OperationState.PREPARED, OperationState.SUCCEEDED, OperationState.FAILED, OperationState.OUTCOME_UNKNOWN):
        assert map_operation_view(execution_state=state, wait_reason=wait_reason) != "waiting"


def test_tst_m2_p4_004_artifact_cleanup_strict_transition_order() -> None:
    """CT-STATE-012 verification and cleanup chains permit no unsafe cleanup shortcut."""
    for current_state, requested_state in (
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
    ):
        _assert_valid(transition_artifact_location, current_state, requested_state)
    for source_state in (
        ArtifactLocationState.DECLARED,
        ArtifactLocationState.MATERIALIZING,
        ArtifactLocationState.AVAILABLE_UNVERIFIED,
        ArtifactLocationState.VERIFYING,
        ArtifactLocationState.CORRUPT,
        ArtifactLocationState.MISSING,
        ArtifactLocationState.OUTCOME_UNKNOWN,
    ):
        for cleanup_target in (
            ArtifactLocationState.CLEANUP_ELIGIBLE,
            ArtifactLocationState.CLEANUP_AUTHORIZED,
            ArtifactLocationState.DELETED,
        ):
            _assert_forbidden(
                transition_artifact_location,
                source_state,
                cleanup_target,
                aggregate_type="artifact_location",
            )
    for source_state in (ArtifactLocationState.CORRUPT, ArtifactLocationState.MISSING, ArtifactLocationState.OUTCOME_UNKNOWN):
        _assert_no_outgoing_edges(transition_artifact_location, source_state, aggregate_type="artifact_location")


def test_tst_m2_p4_005_batch_waiting_resume_and_terminal_transitions() -> None:
    """Batch permits its explicit wait loop and direct terminal paths only."""
    _assert_valid(transition_batch, BatchState.CREATED, BatchState.RUNNING)
    _assert_valid(transition_batch, BatchState.RUNNING, BatchState.WAITING_CAPABILITY)
    _assert_valid(transition_batch, BatchState.WAITING_CAPABILITY, BatchState.RUNNING)
    terminals = (BatchState.COMPLETED_TARGET, BatchState.COMPLETED_EXHAUSTED, BatchState.FAILED_SYSTEM)
    for source_state in (BatchState.RUNNING, BatchState.WAITING_CAPABILITY):
        for terminal_state in terminals:
            _assert_valid(transition_batch, source_state, terminal_state)
    for terminal_state in terminals:
        _assert_no_outgoing_edges(transition_batch, terminal_state, aggregate_type="batch")


def test_tst_m2_p4_006_job_waiting_resume_and_completion_admission() -> None:
    """Job completion is admitted from ACTIVE or WAITING, with explicit final failure branches."""
    for current_state, requested_state in (
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
    ):
        _assert_valid(transition_job, current_state, requested_state)
    for terminal_state in (JobState.COMPLETED, JobState.FAILED_FINAL):
        _assert_no_outgoing_edges(transition_job, terminal_state, aggregate_type="job")


def test_tst_m2_p4_007_stage_run_reconcile_and_terminal_transitions() -> None:
    """Stage Run exposes only CT-STATE-008 edges, including evidence-gated reconciliation."""
    for requested_state in (StageRunState.WAITING_DEPENDENCY, StageRunState.WAITING_CAPABILITY, StageRunState.RUNNING):
        _assert_valid(transition_stage_run, StageRunState.PENDING, requested_state)
    for requested_state in (
        StageRunState.SUCCEEDED,
        StageRunState.FAILED_RETRYABLE,
        StageRunState.FAILED_FINAL,
        StageRunState.OUTCOME_UNKNOWN,
        StageRunState.STALE,
    ):
        _assert_valid(transition_stage_run, StageRunState.RUNNING, requested_state)
    for requested_state in (StageRunState.SUCCEEDED, StageRunState.FAILED_RETRYABLE, StageRunState.FAILED_FINAL):
        _assert_valid(transition_stage_run, StageRunState.OUTCOME_UNKNOWN, requested_state, reconciliation_evidence=RECONCILIATION)
        _assert_forbidden(
            transition_stage_run,
            StageRunState.OUTCOME_UNKNOWN,
            requested_state,
            aggregate_type="stage_run",
        )
    for source_state in (StageRunState.WAITING_DEPENDENCY, StageRunState.WAITING_CAPABILITY, StageRunState.FAILED_RETRYABLE):
        _assert_no_outgoing_edges(transition_stage_run, source_state, aggregate_type="stage_run")
    _assert_forbidden(
        transition_stage_run,
        StageRunState.OUTCOME_UNKNOWN,
        StageRunState.RUNNING,
        aggregate_type="stage_run",
        reconciliation_evidence=RECONCILIATION,
    )
    for terminal_state in (StageRunState.SUCCEEDED, StageRunState.FAILED_FINAL, StageRunState.STALE):
        _assert_no_outgoing_edges(transition_stage_run, terminal_state, aggregate_type="stage_run")


def test_tst_m2_p4_008_operation_forbidden_transition_classes_rejected() -> None:
    """Forbidden Operation classes have exact safe errors and never materialize a result."""
    for current_state, requested_state in (
        (OperationState.PREPARED, OperationState.SUCCEEDED),
        (OperationState.PREPARED, OperationState.FAILED),
        (OperationState.PREPARED, OperationState.OUTCOME_UNKNOWN),
        (OperationState.STARTED, OperationState.PREPARED),
        (OperationState.OUTCOME_UNKNOWN, OperationState.STARTED),
        (OperationState.OUTCOME_UNKNOWN, OperationState.SUCCEEDED),
        (OperationState.OUTCOME_UNKNOWN, OperationState.FAILED),
        (OperationState.SUCCEEDED, OperationState.STARTED),
        (OperationState.FAILED, OperationState.STARTED),
        (OperationState.SUCCEEDED, OperationState.SUCCEEDED),
        (OperationState.FAILED, OperationState.FAILED),
    ):
        _assert_forbidden(transition_operation, current_state, requested_state, aggregate_type="operation")
    _assert_forbidden(
        transition_operation,
        OperationState.OUTCOME_UNKNOWN,
        OperationState.STARTED,
        aggregate_type="operation",
        reconciliation_evidence=RECONCILIATION,
    )
    for terminal_state in (OperationState.SUCCEEDED, OperationState.FAILED):
        _assert_no_outgoing_edges(transition_operation, terminal_state, aggregate_type="operation")


def test_tst_m2_p4_009_stale_expected_revision_rejected_without_mutation() -> None:
    """A sequential stale expected revision is rejected without claiming real concurrency."""
    initial_state = OperationState.PREPARED
    first = transition_operation(
        current_state=initial_state,
        current_revision=REVISION,
        expected_revision=REVISION,
        requested_state=OperationState.STARTED,
    )
    assert first == TransitionResult(state=OperationState.STARTED, revision=REVISION + 1)
    with pytest.raises(RevisionConflictError) as raised:
        transition_operation(
            current_state=first.state,
            current_revision=first.revision,
            expected_revision=REVISION,
            requested_state=OperationState.SUCCEEDED,
        )
    assert raised.value.current_revision == REVISION + 1
    assert first == TransitionResult(state=OperationState.STARTED, revision=REVISION + 1)
