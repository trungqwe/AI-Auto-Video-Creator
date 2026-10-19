"""Integrity verification policy for artifact locations (CT-STO-003 bước 4-5, CT-STATE-012)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from controlplane.domain.statemachine import (
    ArtifactLocationState,
    TransitionResult,
    transition_artifact_location,
)

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_INTEGRITY_OUTCOMES = frozenset(
    {
        ArtifactLocationState.VERIFIED,
        ArtifactLocationState.CORRUPT,
        ArtifactLocationState.MISSING,
        ArtifactLocationState.OUTCOME_UNKNOWN,
    }
)


@dataclass(frozen=True)
class IntegrityObservation:
    object_present: bool | None
    observed_sha256: str | None
    observed_size_bytes: int | None
    evidence_ref: str | None


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None


def _is_size(value: object) -> bool:
    return type(value) is int and value >= 0


def evaluate_integrity(
    expected_sha256: str,
    expected_size_bytes: int,
    observation: IntegrityObservation,
) -> ArtifactLocationState:
    if not _is_sha256(expected_sha256):
        raise ValueError("expected_sha256 must be 64 lowercase hex characters")
    if not _is_size(expected_size_bytes):
        raise ValueError("expected_size_bytes must be a non-negative int")
    if observation.object_present is False:
        return ArtifactLocationState.MISSING
    if observation.object_present is not True:
        return ArtifactLocationState.OUTCOME_UNKNOWN
    evidence_ref = observation.evidence_ref
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        return ArtifactLocationState.OUTCOME_UNKNOWN
    if not _is_sha256(observation.observed_sha256) or not _is_size(observation.observed_size_bytes):
        return ArtifactLocationState.OUTCOME_UNKNOWN
    if (
        observation.observed_sha256 != expected_sha256
        or observation.observed_size_bytes != expected_size_bytes
    ):
        return ArtifactLocationState.CORRUPT
    return ArtifactLocationState.VERIFIED


def apply_integrity_outcome(
    current_state: ArtifactLocationState,
    current_revision: int,
    outcome: ArtifactLocationState,
) -> TransitionResult:
    if outcome not in _INTEGRITY_OUTCOMES:
        raise ValueError("outcome must be VERIFIED, CORRUPT, MISSING or OUTCOME_UNKNOWN")
    return transition_artifact_location(
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=current_revision,
        requested_state=outcome,
    )


__all__ = ["IntegrityObservation", "apply_integrity_outcome", "evaluate_integrity"]
