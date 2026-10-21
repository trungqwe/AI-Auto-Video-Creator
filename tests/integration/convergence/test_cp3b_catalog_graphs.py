"""Behavioral tests and edge oracle verification for CT-STATE-005 and CT-STATE-006 catalog graphs."""

import itertools
import pathlib
import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain import statemachine as sm
from controlplane.domain.statemachine import ForbiddenTransitionError, TransitionResult
from controlplane.domain.statemachine import catalog_states as cs
from catalog.domain import states as catalog_enums

REVISION = 17

GRAPHS = {
    "media_discovery": (
        cs.MediaDiscoveryState,
        cs.transition_media_discovery,
        "media_discovery",
        {
            ("DISCOVERED", "ACQUIRING"),
            ("ACQUIRING", "CATALOGED"),
            ("ACQUIRING", "FAILED"),
        },
    ),
    "rendition": (
        cs.RenditionState,
        cs.transition_rendition,
        "rendition",
        {
            ("DECLARED", "PROCESSING"),
            ("PROCESSING", "READY"),
            ("PROCESSING", "FAILED"),
            ("PROCESSING", "OUTCOME_UNKNOWN"),
        },
    ),
    "availability": (
        cs.AvailabilityState,
        cs.transition_availability,
        "availability",
        set(),
    ),
    "image_safety": (
        cs.ImageSafetyState,
        cs.transition_image_safety,
        "image_safety",
        {
            ("NOT_ASSESSED", "ASSESSING"),
            ("ASSESSING", "SAFE"),
            ("ASSESSING", "TRANSFORM_REQUIRED"),
            ("ASSESSING", "UNCERTAIN"),
            ("ASSESSING", "DETECTION_FAILED"),
            ("ASSESSING", "UNREADABLE"),
            ("TRANSFORM_REQUIRED", "TRANSFORMING"),
            ("TRANSFORMING", "PROCESSED_READY"),
            ("TRANSFORMING", "TRANSFORM_FAILED"),
        },
    ),
}


def _call(fn, enum_cls, a, b, expected_revision=REVISION):
    return fn(
        current_state=enum_cls(a),
        current_revision=REVISION,
        expected_revision=expected_revision,
        requested_state=enum_cls(b),
    )


@pytest.mark.parametrize("graph_name", list(GRAPHS.keys()))
def test_valid_edges(graph_name: str) -> None:
    enum_cls, fn, agg_type, edges = GRAPHS[graph_name]
    for a, b in sorted(edges):
        result = _call(fn, enum_cls, a, b)
        assert result == TransitionResult(state=enum_cls(b), revision=REVISION + 1)


@pytest.mark.parametrize("graph_name", list(GRAPHS.keys()))
def test_forbidden_edges(graph_name: str) -> None:
    enum_cls, fn, agg_type, edges = GRAPHS[graph_name]
    values = [member.value for member in enum_cls]
    for a, b in itertools.product(values, values):
        if (a, b) in edges:
            continue
        with pytest.raises(ForbiddenTransitionError) as exc_info:
            _call(fn, enum_cls, a, b)
        err = exc_info.value
        assert err.code == "FORBIDDEN_TRANSITION"
        assert err.aggregate_type == agg_type
        assert err.current_state == enum_cls(a)
        assert err.requested_next_state == enum_cls(b)
        assert err.current_revision == REVISION


@pytest.mark.parametrize("graph_name", list(GRAPHS.keys()))
def test_stale_revision(graph_name: str) -> None:
    enum_cls, fn, agg_type, edges = GRAPHS[graph_name]
    if not edges:
        return
    a, b = sorted(edges)[0]
    with pytest.raises(RevisionConflictError):
        _call(fn, enum_cls, a, b, expected_revision=REVISION - 1)


def test_unsafe_outcomes_never_map_to_safe() -> None:
    enum_cls, fn, agg_type, edges = GRAPHS["image_safety"]
    incoming_to_safe = [(a, b) for a, b in edges if b == "SAFE"]
    assert incoming_to_safe == [("ASSESSING", "SAFE")]
    values = [member.value for member in enum_cls]
    terminal_candidates = (
        "UNCERTAIN",
        "DETECTION_FAILED",
        "TRANSFORM_FAILED",
        "UNREADABLE",
        "SAFE",
        "PROCESSED_READY",
    )
    for src in terminal_candidates:
        for dst in values:
            with pytest.raises(ForbiddenTransitionError):
                _call(fn, enum_cls, src, dst)


def test_availability_is_separate_axis() -> None:
    avail_values = {m.value for m in cs.AvailabilityState}
    safety_values = {m.value for m in cs.ImageSafetyState}
    assert avail_values.isdisjoint(safety_values)

    with pytest.raises(ForbiddenTransitionError):
        cs.transition_image_safety(
            current_state=cs.ImageSafetyState.ASSESSING,
            current_revision=REVISION,
            expected_revision=REVISION,
            requested_state=cs.AvailabilityState.MISSING,  # type: ignore[arg-type]
        )

    with pytest.raises(ForbiddenTransitionError):
        cs.transition_availability(
            current_state=cs.AvailabilityState.AVAILABLE,
            current_revision=REVISION,
            expected_revision=REVISION,
            requested_state=cs.ImageSafetyState.SAFE,  # type: ignore[arg-type]
        )


def test_enum_values_match_catalog_axes() -> None:
    assert {m.value for m in cs.MediaDiscoveryState} == {m.value for m in catalog_enums.DiscoveryState}
    assert {m.value for m in cs.RenditionState} == {m.value for m in catalog_enums.RenditionState}
    assert {m.value for m in cs.AvailabilityState} == {m.value for m in catalog_enums.Availability}
    assert {m.value for m in cs.ImageSafetyState} == {m.value for m in catalog_enums.ImageSafetyState}


def test_existing_graphs_untouched() -> None:
    expected_sm_all = sorted(
        [
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
    )
    assert sorted(sm.__all__) == expected_sm_all
    sm_dir = pathlib.Path(sm.__file__).parent
    py_files = sorted(p.name for p in sm_dir.glob("*.py"))
    assert py_files == ["__init__.py", "catalog_states.py"]
    init_text = (sm_dir / "__init__.py").read_text(encoding="utf-8")
    assert "catalog_states" not in init_text


def test_module_surface_and_imports() -> None:
    expected_cs_all = sorted(
        [
            "AvailabilityState",
            "ImageSafetyState",
            "MediaDiscoveryState",
            "RenditionState",
            "transition_availability",
            "transition_image_safety",
            "transition_media_discovery",
            "transition_rendition",
        ]
    )
    assert sorted(cs.__all__) == expected_cs_all
    cs_path = pathlib.Path(cs.__file__)
    for line in cs_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for forbidden in (
            "from catalog",
            "import catalog",
            "from source_ingestion",
            "import source_ingestion",
        ):
            assert not stripped.startswith(forbidden), f"Forbidden import found: {line}"
