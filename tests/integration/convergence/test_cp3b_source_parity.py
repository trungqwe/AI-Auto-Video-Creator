"""edges of A are compared with CT-STATE-001, CT-STATE-002, CT-STATE-002A written inline; A keeps its local tables."""

import dataclasses
import datetime
import pathlib
import pytest

from controlplane.domain.statemachine import ForbiddenTransitionError
from source_ingestion.domain import collection_run as cr
from source_ingestion.domain.source import (
    SourcePolicy,
    disable_source,
    enable_source,
    register_source,
    remove_source,
    restore_source,
    update_source_metadata,
)
from source_ingestion.domain.source_candidate import (
    ALLOWED_TRANSITIONS,
    NO_MATCH,
    CandidateStatus,
    IdentityMatch,
    IdentityMatchKind,
    RegistrationPolicy,
    begin_validation,
    complete_validation,
    discover_candidate,
    register_candidate,
)

AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

CT_STATE_001_EDGES = {
    ("ACTIVE", "DISABLED"),
    ("DISABLED", "ACTIVE"),
    ("ACTIVE", "REMOVED_TOMBSTONE"),
    ("DISABLED", "REMOVED_TOMBSTONE"),
    ("REMOVED_TOMBSTONE", "ACTIVE"),
    ("REMOVED_TOMBSTONE", "DISABLED"),
}

CT_STATE_002_RUN_EDGES = {
    ("SCHEDULED", "RUNNING"),
    ("SCHEDULED", "FAILED_FINAL"),
    ("RUNNING", "WAITING_RETRY"),
    ("RUNNING", "WAITING_RECONCILIATION"),
    ("RUNNING", "COMPLETED"),
    ("RUNNING", "COMPLETED_PARTIAL"),
    ("RUNNING", "FAILED_FINAL"),
    ("WAITING_RETRY", "RUNNING"),
    ("WAITING_RETRY", "COMPLETED_PARTIAL"),
    ("WAITING_RETRY", "FAILED_FINAL"),
    ("WAITING_RECONCILIATION", "RUNNING"),
    ("WAITING_RECONCILIATION", "WAITING_RETRY"),
    ("WAITING_RECONCILIATION", "COMPLETED"),
    ("WAITING_RECONCILIATION", "COMPLETED_PARTIAL"),
    ("WAITING_RECONCILIATION", "FAILED_FINAL"),
}

CT_STATE_002A_EDGES = {
    ("DISCOVERED", "VALIDATING"),
    ("VALIDATING", "READY_FOR_REGISTRATION"),
    ("VALIDATING", "MATCHED_EXISTING"),
    ("VALIDATING", "BLOCKED_TOMBSTONE"),
    ("VALIDATING", "REJECTED"),
    ("READY_FOR_REGISTRATION", "REGISTERED"),
    ("READY_FOR_REGISTRATION", "MATCHED_EXISTING"),
    ("READY_FOR_REGISTRATION", "BLOCKED_TOMBSTONE"),
    ("READY_FOR_REGISTRATION", "REJECTED"),
}


def _assert_same_edges(name: str, observed: set[tuple[str, str]], expected: set[tuple[str, str]]) -> None:
    missing = expected - observed
    extra = observed - expected
    assert not missing and not extra, f"{name}: missing={sorted(missing)} extra={sorted(extra)}"


POLICY_OK = SourcePolicy("p1", frozenset({"rss"}), frozenset({"t1"}), frozenset())
POLICY_NARROW = SourcePolicy("p2", frozenset({"other"}), frozenset({"t1"}), frozenset())


def _source(enabled: bool):
    return register_source(
        source_id="s1",
        workspace_id="w1",
        canonical_locator="https://example.test/feed",
        name="Feed",
        source_kind="rss",
        tier="t1",
        topics=["news"],
        notes="",
        collection_enabled=enabled,
        admin_metadata={},
        actor="t",
        at=AT,
        policy=POLICY_OK,
    )


def _observed_source_edges() -> set[tuple[str, str]]:
    starting_points = [
        _source(True),
        _source(False),
        remove_source(_source(True), expected_revision=1, actor="t", at=AT),
        remove_source(_source(False), expected_revision=1, actor="t", at=AT),
    ]
    operations = [
        lambda s: enable_source(s, expected_revision=s.revision, actor="t", at=AT),
        lambda s: disable_source(s, expected_revision=s.revision, actor="t", at=AT),
        lambda s: remove_source(s, expected_revision=s.revision, actor="t", at=AT),
        lambda s: restore_source(s, expected_revision=s.revision, actor="t", at=AT, policy=POLICY_OK),
        lambda s: restore_source(s, expected_revision=s.revision, actor="t", at=AT, policy=POLICY_NARROW),
        lambda s: update_source_metadata(s, expected_revision=s.revision, actor="t", at=AT, policy=POLICY_OK, collection_enabled=True),
        lambda s: update_source_metadata(s, expected_revision=s.revision, actor="t", at=AT, policy=POLICY_OK, collection_enabled=False),
    ]
    observed: set[tuple[str, str]] = set()
    for s in starting_points:
        for op in operations:
            try:
                res = op(s)
                observed.add((s.status.value, res.status.value))
            except (ForbiddenTransitionError, ValueError):
                pass
    return observed


def test_source_edges_match_ct_state_001() -> None:
    _assert_same_edges("CT-STATE-001 source", _observed_source_edges(), CT_STATE_001_EDGES)

def test_candidate_table_matches_ct_state_002a() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(CandidateStatus)
    observed = {(a.value, b.value) for a, targets in ALLOWED_TRANSITIONS.items() for b in targets}
    _assert_same_edges("CT-STATE-002A table", observed, CT_STATE_002A_EDGES)


def _observed_candidate_behavior_edges() -> set[tuple[str, str]]:
    observed: set[tuple[str, str]] = set()

    c = discover_candidate(
        candidate_id="c1",
        workspace_id="w1",
        observed_locator="https://example.test/a",
        canonical_locator="https://example.test/a",
        discovery_method="rss",
        discovery_evidence="ev",
        actor="t",
        at=AT,
    )
    d1 = begin_validation(c, expected_revision=c.revision, actor="t", at=AT)
    if d1.candidate.status != c.status:
        observed.add((c.status.value, d1.candidate.status.value))
    v = d1.candidate

    tomb_match = IdentityMatch(IdentityMatchKind.TOMBSTONE, "tomb-1")
    exist_match = IdentityMatch(IdentityMatchKind.EXISTING_SOURCE, "src-1")

    validation_combos = [
        (NO_MATCH, True, None),
        (tomb_match, True, None),
        (exist_match, True, None),
        (NO_MATCH, False, "invalid"),
    ]
    ready_candidate = None
    for identity, passed, reason in validation_combos:
        d = complete_validation(
            v,
            expected_revision=v.revision,
            identity=identity,
            validation_passed=passed,
            reason=reason,
            actor="t",
            at=AT,
        )
        if d.candidate.status != v.status:
            observed.add((v.status.value, d.candidate.status.value))
        if identity == NO_MATCH and passed is True:
            ready_candidate = d.candidate

    assert ready_candidate is not None
    ready = ready_candidate

    full_policy = RegistrationPolicy(
        revision="p1",
        auto_registration_enabled=True,
        permitted=True,
        source_kind="rss",
        topics=("news",),
        tier="t1",
    )
    forbid_policy = RegistrationPolicy(
        revision="p1",
        auto_registration_enabled=True,
        permitted=False,
        reason="no",
    )

    registration_combos = [
        (NO_MATCH, full_policy),
        (tomb_match, full_policy),
        (exist_match, full_policy),
        (NO_MATCH, forbid_policy),
        (NO_MATCH, None),
    ]
    for identity, policy in registration_combos:
        d = register_candidate(
            ready,
            expected_revision=ready.revision,
            identity=identity,
            policy=policy,
            new_source_ref="src-new",
            actor="t",
            at=AT,
        )
        if d.candidate.status != ready.status:
            observed.add((ready.status.value, d.candidate.status.value))

    return observed


def test_candidate_behavior_matches_ct_state_002a() -> None:
    _assert_same_edges("CT-STATE-002A behavior", _observed_candidate_behavior_edges(), CT_STATE_002A_EDGES)

def _run(status: cr.RunStatus, *, max_attempts: int, committed: int) -> cr.CollectionRun:
    base = cr.schedule_run(
        run_id="r1",
        workspace_id="w1",
        source_id="s1",
        business_date=datetime.date(2026, 1, 1),
        purpose=cr.CollectionPurpose.PERIODIC,
        retry_policy=cr.RetryPolicy("r1", max_attempts),
    )
    if status == cr.RunStatus.WAITING_RETRY:
        attempts = (cr.CollectionAttempt(1, cr.AttemptOutcome.FAILED_RETRYABLE),)
    elif status == cr.RunStatus.WAITING_RECONCILIATION:
        attempts = (cr.CollectionAttempt(1, cr.AttemptOutcome.OUTCOME_UNKNOWN),)
    else:
        attempts = ()
    return dataclasses.replace(
        base,
        status=status,
        committed_package_count=committed,
        attempts=attempts,
    )


def _observed_run_edges() -> set[tuple[str, str]]:
    observed: set[tuple[str, str]] = set()
    # record_committed_packages and flag_reconciliation_overdue are excluded because they never change status.
    for status in cr.RunStatus:
        for max_attempts in (1, 3):
            for committed in (0, 1):
                r = _run(status, max_attempts=max_attempts, committed=committed)
                for a in (True, False):
                    for d in (True, False):
                        try:
                            res = cr.start_run(r, source_active=a, checkpoint_ref="cp")
                            observed.add((r.status.value, res.status.value))
                        except cr.InvalidTransitionError:
                            pass

                        for o in cr.AttemptOutcome:
                            try:
                                res = cr.record_attempt_outcome(
                                    r, o, source_active=a, deadline_passed=d, checkpoint_ref="cp"
                                )
                                observed.add((r.status.value, res.status.value))
                            except cr.InvalidTransitionError:
                                pass

                        try:
                            res = cr.resume_retry(r, source_active=a, deadline_passed=d, checkpoint_ref="cp")
                            observed.add((r.status.value, res.status.value))
                        except cr.InvalidTransitionError:
                            pass

                        try:
                            res = cr.deactivate_source(r, checkpoint_ref="cp")
                            observed.add((r.status.value, res.status.value))
                        except cr.InvalidTransitionError:
                            pass

                        for res_enum in cr.ReconciliationResult:
                            try:
                                res = cr.reconcile(
                                    r,
                                    res_enum,
                                    evidence_ref="ev",
                                    source_active=a,
                                    deadline_passed=d,
                                    checkpoint_ref="cp",
                                )
                                observed.add((r.status.value, res.status.value))
                            except cr.InvalidTransitionError:
                                pass
    return observed


def test_run_edges_match_ct_state_002() -> None:
    _assert_same_edges("CT-STATE-002 run", _observed_run_edges(), CT_STATE_002_RUN_EDGES)


def test_a_has_no_cycle_state_machine_to_compare() -> None:
    source_dir = pathlib.Path(__file__).parents[3] / "src" / "source_ingestion"
    for py_file in source_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "PLANNED" not in content, f"Found PLANNED in {py_file}: cycle state machine introduced"


def test_oracle_sensitivity_ct_state_001() -> None:
    first_edge = sorted(CT_STATE_001_EDGES)[0]
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-001 sensitivity missing", CT_STATE_001_EDGES - {first_edge}, CT_STATE_001_EDGES)
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-001 sensitivity extra", CT_STATE_001_EDGES | {("X", "Y")}, CT_STATE_001_EDGES)


def test_oracle_sensitivity_ct_state_002_run() -> None:
    first_edge = sorted(CT_STATE_002_RUN_EDGES)[0]
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-002 run sensitivity missing", CT_STATE_002_RUN_EDGES - {first_edge}, CT_STATE_002_RUN_EDGES)
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-002 run sensitivity extra", CT_STATE_002_RUN_EDGES | {("X", "Y")}, CT_STATE_002_RUN_EDGES)


def test_oracle_sensitivity_ct_state_002a() -> None:
    first_edge = sorted(CT_STATE_002A_EDGES)[0]
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-002A sensitivity missing", CT_STATE_002A_EDGES - {first_edge}, CT_STATE_002A_EDGES)
    with pytest.raises(AssertionError):
        _assert_same_edges("CT-STATE-002A sensitivity extra", CT_STATE_002A_EDGES | {("X", "Y")}, CT_STATE_002A_EDGES)
