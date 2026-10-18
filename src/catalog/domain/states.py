"""Read-only state axes of capability C (CT-STATE-005/006) and usability classification (D8-C-05).

Only contract values and classifiers live here; transition graphs belong to the shared
state machine (D8-C-04, CONV-C-07).
"""

from enum import StrEnum
from types import MappingProxyType

from catalog.domain.identity import MediaKind


class DiscoveryState(StrEnum):
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


class Availability(StrEnum):
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


class Usability(StrEnum):
    USABLE = "usable"
    USABLE_WITH_WARNING = "usable_with_warning"
    NOT_USABLE = "not_usable"


_IMAGE_SAFETY_USABILITY = MappingProxyType(
    {
        ImageSafetyState.NOT_ASSESSED: Usability.NOT_USABLE,
        ImageSafetyState.ASSESSING: Usability.NOT_USABLE,
        ImageSafetyState.SAFE: Usability.USABLE,
        ImageSafetyState.TRANSFORM_REQUIRED: Usability.NOT_USABLE,
        ImageSafetyState.UNCERTAIN: Usability.USABLE_WITH_WARNING,
        ImageSafetyState.DETECTION_FAILED: Usability.USABLE_WITH_WARNING,
        ImageSafetyState.UNREADABLE: Usability.NOT_USABLE,
        ImageSafetyState.TRANSFORMING: Usability.NOT_USABLE,
        ImageSafetyState.PROCESSED_READY: Usability.USABLE,
        ImageSafetyState.TRANSFORM_FAILED: Usability.USABLE_WITH_WARNING,
    }
)

_AVAILABILITY_USABILITY = MappingProxyType(
    {
        Availability.AVAILABLE: Usability.USABLE,
        Availability.UNAVAILABLE_SOURCE: Usability.USABLE,
        Availability.MISSING: Usability.NOT_USABLE,
        Availability.CORRUPT: Usability.NOT_USABLE,
        Availability.RECOVERING: Usability.NOT_USABLE,
    }
)


def classify_safety(kind: MediaKind, safety: ImageSafetyState | None) -> Usability:
    """Map image safety to usability; clip and audio carry no image safety axis."""
    kind = MediaKind(kind)
    if kind is not MediaKind.IMAGE:
        if safety is not None:
            raise ValueError(f"{kind} media has no image safety state")
        return Usability.USABLE
    if safety is None:
        raise ValueError("image media requires an image safety state")
    return _IMAGE_SAFETY_USABILITY[ImageSafetyState(safety)]


def classify_availability(availability: Availability) -> Usability:
    """Map storage availability to usability; a removed source keeps eligibility."""
    return _AVAILABILITY_USABILITY[Availability(availability)]
