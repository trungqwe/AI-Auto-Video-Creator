"""I-07: admission materialize, working set và release input cho render (CT-STO-004, INV-008)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation

REASON_MAX_VIDEO_SETS = "MAX_VIDEO_SETS_REACHED"
REASON_MAX_BYTES = "MAX_BYTES_EXCEEDED"


def _is_int(value: object, minimum: int) -> bool:
    return type(value) is int and value >= minimum


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class WorkingSetPolicy:
    max_bytes: int
    policy_revision: str
    max_video_sets: int = 5

    def __post_init__(self) -> None:
        if not _is_int(self.max_bytes, 1):
            raise ValueError("max_bytes must be a positive int")
        if not isinstance(self.policy_revision, str) or not self.policy_revision.strip():
            raise ValueError("policy_revision must be a non-empty string")
        if not _is_int(self.max_video_sets, 1):
            raise ValueError("max_video_sets must be a positive int")


@dataclass(frozen=True)
class ActiveVideoSet:
    video_set_id: str
    expected_bytes: int
    inputs_materialized: bool = True
    unsynced_output_bytes: int = 0

    def __post_init__(self) -> None:
        if not _is_int(self.expected_bytes, 0) or not _is_int(self.unsynced_output_bytes, 0):
            raise ValueError("expected_bytes and unsynced_output_bytes must be non-negative ints")

    @property
    def occupies_slot(self) -> bool:
        return self.inputs_materialized or self.unsynced_output_bytes > 0

    @property
    def held_bytes(self) -> int:
        return (self.expected_bytes if self.inputs_materialized else 0) + self.unsynced_output_bytes


@dataclass(frozen=True)
class MaterializationRequest:
    video_set_id: str
    expected_bytes: int
    is_prefetch: bool = False

    def __post_init__(self) -> None:
        if not _is_int(self.expected_bytes, 0):
            raise ValueError("expected_bytes must be a non-negative int")


@dataclass(frozen=True)
class AdmissionDecision:
    status: AdmissionStatus
    reason: str | None


class RenderInputNotVerifiedError(Exception):
    def __init__(self, artifact_version_id: str, reason: str) -> None:
        self.artifact_version_id = artifact_version_id
        self.reason = reason
        super().__init__(f"render input not verified: {artifact_version_id}: {reason}")


def admit_materialization(policy: WorkingSetPolicy, active_sets: list[ActiveVideoSet], request: MaterializationRequest) -> AdmissionDecision:
    held = [active for active in active_sets if active.occupies_slot]
    if len(held) >= policy.max_video_sets:
        return AdmissionDecision(AdmissionStatus.DEFERRED, REASON_MAX_VIDEO_SETS)
    if sum(active.held_bytes for active in held) + request.expected_bytes > policy.max_bytes:
        return AdmissionDecision(AdmissionStatus.DEFERRED, REASON_MAX_BYTES)
    return AdmissionDecision(AdmissionStatus.ADMITTED, None)


def release_for_render(input_artifacts: list[dict[str, Any]], local_locations: dict[str, ArtifactLocation]) -> list[ArtifactLocation]:
    released: list[ArtifactLocation] = []
    for item in input_artifacts:
        version_id = item.get("artifact_version_id") if isinstance(item, dict) else None
        if not isinstance(version_id, str) or not version_id:
            raise RenderInputNotVerifiedError(str(version_id), "INPUT_MALFORMED")
        sha256 = item.get("sha256")
        size_bytes = item.get("size_bytes")
        if not isinstance(sha256, str) or not sha256 or not _is_int(size_bytes, 0):
            raise RenderInputNotVerifiedError(version_id, "INPUT_MALFORMED")
        location = local_locations.get(version_id)
        if location is None:
            raise RenderInputNotVerifiedError(version_id, "LOCATION_MISSING")
        if location.artifact_version_id != version_id:
            raise RenderInputNotVerifiedError(version_id, "LOCATION_BINDING_MISMATCH")
        if location.state is not ArtifactLocationState.VERIFIED:
            raise RenderInputNotVerifiedError(version_id, "NOT_VERIFIED")
        if location.observed_hash != sha256 or not _is_int(location.observed_size_bytes, 0) or location.observed_size_bytes != size_bytes:
            raise RenderInputNotVerifiedError(version_id, "OBSERVATION_MISMATCH")
        released.append(location)
    return released


__all__ = [
    "ActiveVideoSet",
    "AdmissionDecision",
    "AdmissionStatus",
    "MaterializationRequest",
    "REASON_MAX_BYTES",
    "REASON_MAX_VIDEO_SETS",
    "RenderInputNotVerifiedError",
    "WorkingSetPolicy",
    "admit_materialization",
    "release_for_render",
]
