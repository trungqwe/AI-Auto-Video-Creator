"""I-13: availability classification of artifact locations for read models (EG-M4-I-4, D8-I-11)."""
import itertools

import pytest

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import availability
from controlplane.domain.storage_meta.availability import classify_artifact, classify_location

State = ArtifactLocationState
EXPECTED = {
    State.VERIFIED: "available",
    State.DECLARED: "uncertain",
    State.MATERIALIZING: "uncertain",
    State.AVAILABLE_UNVERIFIED: "uncertain",
    State.VERIFYING: "uncertain",
    State.OUTCOME_UNKNOWN: "uncertain",
    State.CORRUPT: "failed",
    State.MISSING: "unavailable",
    State.CLEANUP_ELIGIBLE: "unavailable",
    State.CLEANUP_AUTHORIZED: "unavailable",
    State.DELETED: "unavailable",
}
MIXED = [State.VERIFIED, State.OUTCOME_UNKNOWN, State.CORRUPT, State.MISSING]
ARTIFACT_CASES = [
    pytest.param(MIXED, "available", id="available wins over all"),
    pytest.param([State.VERIFIED, State.CLEANUP_ELIGIBLE], "available", id="available with cleanup eligible"),
    pytest.param(MIXED[1:], "uncertain", id="uncertain wins over failed and unavailable"),
    pytest.param([State.CORRUPT, State.MISSING, State.DELETED], "failed", id="failed wins over unavailable"),
    pytest.param([State.CORRUPT, State.CLEANUP_AUTHORIZED], "failed", id="failed with cleanup authorized"),
    pytest.param([State.MISSING, State.CLEANUP_ELIGIBLE], "unavailable", id="only unavailable"),
    pytest.param([], "unavailable", id="empty is unavailable"),
]


def test_expected_table_covers_every_enum_member():
    assert set(EXPECTED) == set(State)


@pytest.mark.parametrize("state", list(State), ids=lambda s: s.value)
def test_classify_location_maps_every_member(state):
    assert classify_location(state) == EXPECTED[state]


@pytest.mark.parametrize("bad", ["UNKNOWN", "verified", "", None, 42], ids=repr)
def test_classify_location_rejects_unknown_value(bad):
    with pytest.raises(ValueError):
        classify_location(bad)


def test_output_values_are_the_four_read_model_strings():
    values = {classify_location(s) for s in State}
    assert values == {"available", "uncertain", "failed", "unavailable"}
    assert all(type(v) is str for v in values)


def test_outcome_unknown_is_never_available_and_corrupt_is_not_unavailable():
    assert classify_location(State.OUTCOME_UNKNOWN) == "uncertain"
    assert classify_location(State.CORRUPT) == "failed"
    assert classify_artifact([State.CORRUPT]) == "failed"


@pytest.mark.parametrize(("states", "expected"), ARTIFACT_CASES)
def test_classify_artifact_priority(states, expected):
    assert classify_artifact(states) == expected


@pytest.mark.parametrize("state", list(State), ids=lambda s: s.value)
def test_classify_artifact_single_state_matches_location(state):
    assert classify_artifact([state]) == EXPECTED[state]


def test_classify_artifact_is_order_independent():
    results = {classify_artifact(list(p)) for p in itertools.permutations(MIXED)}
    assert results == {"available"}


def test_classify_artifact_does_not_mutate_input():
    states = list(MIXED)
    classify_artifact(states)
    assert states == MIXED


def test_classify_artifact_rejects_unknown_member():
    with pytest.raises(ValueError):
        classify_artifact([State.VERIFIED, "UNKNOWN"])


def test_artifact_location_state_is_imported_read_only():
    assert availability.ArtifactLocationState is State
    assert len(State) == 11
