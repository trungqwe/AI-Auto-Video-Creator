"""Pure, revision-aware state transitions for the capability C catalog graphs (CT-STATE-005, CT-STATE-006)."""

from enum import StrEnum

from controlplane.domain.statemachine import ReconciliationEvidence, TransitionResult, _transition


class MediaDiscoveryState(StrEnum):
    DISCOVERED = "DISCOVERED"
    ACQUIRING = "ACQUIRING"
    CATALOGED = "CATALOGED"
    FAILED = "FAILED"


class RenditionState(StrEnum):
    DECLARED = "DECLARED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class AvailabilityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    CORRUPT = "CORRUPT"
    RECOVERING = "RECOVERING"
    UNAVAILABLE_SOURCE = "UNAVAILABLE_SOURCE"


class ImageSafetyState(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    ASSESSING = "ASSESSING"
    SAFE = "SAFE"
    TRANSFORM_REQUIRED = "TRANSFORM_REQUIRED"
    UNCERTAIN = "UNCERTAIN"
    DETECTION_FAILED = "DETECTION_FAILED"
    UNREADABLE = "UNREADABLE"
    TRANSFORMING = "TRANSFORMING"
    PROCESSED_READY = "PROCESSED_READY"
    TRANSFORM_FAILED = "TRANSFORM_FAILED"


_MEDIA_DISCOVERY_EDGES: frozenset[tuple[StrEnum, StrEnum]] = frozenset(
    {
        (MediaDiscoveryState.DISCOVERED, MediaDiscoveryState.ACQUIRING),
        (MediaDiscoveryState.ACQUIRING, MediaDiscoveryState.CATALOGED),
        (MediaDiscoveryState.ACQUIRING, MediaDiscoveryState.FAILED),
    }
)
_RENDITION_EDGES: frozenset[tuple[StrEnum, StrEnum]] = frozenset(
    {
        (RenditionState.DECLARED, RenditionState.PROCESSING),
        (RenditionState.PROCESSING, RenditionState.READY),
        (RenditionState.PROCESSING, RenditionState.FAILED),
        (RenditionState.PROCESSING, RenditionState.OUTCOME_UNKNOWN),
    }
)
# CT-STATE-005 lists availability values only and no edges; do not infer recovery edges (cf. CT-STATE-008).
_AVAILABILITY_EDGES: frozenset[tuple[StrEnum, StrEnum]] = frozenset()
_IMAGE_SAFETY_EDGES: frozenset[tuple[StrEnum, StrEnum]] = frozenset(
    {
        (ImageSafetyState.NOT_ASSESSED, ImageSafetyState.ASSESSING),
        (ImageSafetyState.ASSESSING, ImageSafetyState.SAFE),
        (ImageSafetyState.ASSESSING, ImageSafetyState.TRANSFORM_REQUIRED),
        (ImageSafetyState.ASSESSING, ImageSafetyState.UNCERTAIN),
        (ImageSafetyState.ASSESSING, ImageSafetyState.DETECTION_FAILED),
        (ImageSafetyState.ASSESSING, ImageSafetyState.UNREADABLE),
        (ImageSafetyState.TRANSFORM_REQUIRED, ImageSafetyState.TRANSFORMING),
        (ImageSafetyState.TRANSFORMING, ImageSafetyState.PROCESSED_READY),
        (ImageSafetyState.TRANSFORMING, ImageSafetyState.TRANSFORM_FAILED),
    }
)


def transition_media_discovery(
    *,
    current_state: MediaDiscoveryState,
    current_revision: int,
    expected_revision: int,
    requested_state: MediaDiscoveryState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="media_discovery",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_MEDIA_DISCOVERY_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_rendition(
    *,
    current_state: RenditionState,
    current_revision: int,
    expected_revision: int,
    requested_state: RenditionState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="rendition",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_RENDITION_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_availability(
    *,
    current_state: AvailabilityState,
    current_revision: int,
    expected_revision: int,
    requested_state: AvailabilityState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="availability",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_AVAILABILITY_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


def transition_image_safety(
    *,
    current_state: ImageSafetyState,
    current_revision: int,
    expected_revision: int,
    requested_state: ImageSafetyState,
    reconciliation_evidence: ReconciliationEvidence | None = None,
) -> TransitionResult:
    return _transition(
        aggregate_type="image_safety",
        current_state=current_state,
        current_revision=current_revision,
        expected_revision=expected_revision,
        requested_state=requested_state,
        allowed_edges=_IMAGE_SAFETY_EDGES,
        evidence_required_edges=frozenset(),
        reconciliation_evidence=reconciliation_evidence,
    )


__all__ = [
    "AvailabilityState",
    "ImageSafetyState",
    "MediaDiscoveryState",
    "RenditionState",
    "transition_availability",
    "transition_image_safety",
    "transition_media_discovery",
    "transition_rendition",
]
