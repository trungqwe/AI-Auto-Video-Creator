"""Resolve whether a rendition's artifact version may be rendered (phần C của TST-INT-INV-008, TST-E2E-011).

Location state belongs to I (CT-STO-002, CT-STATE-012); this module only reads it and never writes it.
"""

from dataclasses import dataclass
from types import MappingProxyType

from catalog.domain.identity import MediaKind
from catalog.domain.renditions import Rendition
from catalog.domain.states import Availability, ImageSafetyState, Usability, classify_availability, classify_safety
from controlplane.domain.statemachine import ArtifactLocationState

ARTIFACT_MISSING = "ARTIFACT_MISSING"
ARTIFACT_CORRUPT = "ARTIFACT_CORRUPT"
ARTIFACT_NOT_VERIFIED = "ARTIFACT_NOT_VERIFIED"
HASH_MISMATCH = "HASH_MISMATCH"

_LOCATION_REASONS = MappingProxyType(
    {
        ArtifactLocationState.MISSING: ARTIFACT_MISSING,
        ArtifactLocationState.CORRUPT: ARTIFACT_CORRUPT,
    }
)
_SEVERITY = MappingProxyType({Usability.USABLE: 0, Usability.USABLE_WITH_WARNING: 1, Usability.NOT_USABLE: 2})


@dataclass(frozen=True, slots=True)
class ArtifactVersionView:
    """Read-only view of one artifact version supplied by I; C never changes ``location_state``."""

    artifact_version_ref: str
    content_sha256: str
    size_bytes: int
    media_type: str
    location_state: ArtifactLocationState
    is_local: bool

    def __post_init__(self) -> None:
        if not isinstance(self.location_state, ArtifactLocationState):
            raise ValueError("location_state must be an ArtifactLocationState")
        if not isinstance(self.is_local, bool):
            raise ValueError("is_local must be a bool")


@dataclass(frozen=True, slots=True)
class RenderableResolution:
    """Render eligibility of one artifact version; ``reason_codes`` explains every downgrade."""

    artifact_version_ref: str
    location_state: ArtifactLocationState
    content_sha256: str
    size_bytes: int
    media_type: str
    materialization_required: bool
    safety_state: ImageSafetyState | None
    usability: Usability
    reason_codes: tuple[str, ...]


def resolve_renderable_version(
    rendition: Rendition,
    artifact: ArtifactVersionView,
    expected_sha256: str,
    media_kind: MediaKind,
    image_safety: ImageSafetyState | None,
    availability: Availability,
) -> RenderableResolution:
    """Combine location, hash, availability and image safety; the worst usability wins."""
    if not isinstance(rendition, Rendition) or not isinstance(artifact, ArtifactVersionView):
        raise ValueError("rendition and artifact must be a Rendition and an ArtifactVersionView")
    if rendition.artifact_version_ref != artifact.artifact_version_ref:
        raise ValueError("artifact does not belong to the rendition")
    findings: list[tuple[Usability, str]] = []
    if artifact.location_state is not ArtifactLocationState.VERIFIED:
        findings.append((Usability.NOT_USABLE, _LOCATION_REASONS.get(artifact.location_state, ARTIFACT_NOT_VERIFIED)))
    if artifact.content_sha256 != expected_sha256:
        findings.append((Usability.NOT_USABLE, HASH_MISMATCH))
    availability = Availability(availability)
    availability_usability = classify_availability(availability)
    if availability_usability is not Usability.USABLE:
        findings.append((availability_usability, f"AVAILABILITY_{availability.value}"))
    safety = None if image_safety is None else ImageSafetyState(image_safety)
    safety_usability = classify_safety(media_kind, safety)
    if safety_usability is not Usability.USABLE:
        findings.append((safety_usability, f"IMAGE_SAFETY_{safety.value}"))
    usability = max((level for level, _ in findings), key=_SEVERITY.__getitem__, default=Usability.USABLE)
    return RenderableResolution(
        artifact_version_ref=artifact.artifact_version_ref,
        location_state=artifact.location_state,
        content_sha256=artifact.content_sha256,
        size_bytes=artifact.size_bytes,
        media_type=artifact.media_type,
        materialization_required=not artifact.is_local,
        safety_state=safety,
        usability=usability,
        reason_codes=tuple(code for _, code in findings),
    )
