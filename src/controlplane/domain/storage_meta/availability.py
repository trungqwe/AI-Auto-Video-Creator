"""Availability classification of artifact locations for read models (EG-M4-I-4, D8-I-11)."""
from __future__ import annotations

from controlplane.domain.statemachine import ArtifactLocationState

AVAILABLE = "available"
UNCERTAIN = "uncertain"
FAILED = "failed"
UNAVAILABLE = "unavailable"
_PRIORITY = (AVAILABLE, UNCERTAIN, FAILED, UNAVAILABLE)
_LOCATION_AVAILABILITY = {
    ArtifactLocationState.VERIFIED: AVAILABLE,
    ArtifactLocationState.DECLARED: UNCERTAIN,
    ArtifactLocationState.MATERIALIZING: UNCERTAIN,
    ArtifactLocationState.AVAILABLE_UNVERIFIED: UNCERTAIN,
    ArtifactLocationState.VERIFYING: UNCERTAIN,
    ArtifactLocationState.OUTCOME_UNKNOWN: UNCERTAIN,
    ArtifactLocationState.CORRUPT: FAILED,
    ArtifactLocationState.MISSING: UNAVAILABLE,
    ArtifactLocationState.CLEANUP_ELIGIBLE: UNAVAILABLE,
    ArtifactLocationState.CLEANUP_AUTHORIZED: UNAVAILABLE,
    ArtifactLocationState.DELETED: UNAVAILABLE,
}


def classify_location(state: ArtifactLocationState) -> str:
    # ArtifactLocationState(...) raises ValueError for any unknown value.
    return _LOCATION_AVAILABILITY[ArtifactLocationState(state)]


def classify_artifact(states: list[ArtifactLocationState]) -> str:
    classes = {classify_location(state) for state in states}
    return next((c for c in _PRIORITY if c in classes), UNAVAILABLE)


__all__ = ["classify_artifact", "classify_location"]
