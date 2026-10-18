"""MediaAssetView read model for the UI (CT-MED-002) with display status (D8-C-09).

Pure and I/O-free: the view only reads the catalog aggregate and the states handed in;
screens belong to the UI shell (CONV-C-04).
"""

from collections.abc import Mapping
from enum import StrEnum

from catalog.domain.identity import MediaAsset, MediaKind, ProvenanceRelation, RightsStatus
from catalog.domain.renditions import RenditionKind, RenditionSet
from catalog.domain.states import (
    Availability,
    ImageSafetyState,
    Usability,
    classify_availability,
    classify_safety,
)


class DisplayStatus(StrEnum):
    ORIGINAL = "original"
    PROCESSED = "processed"
    UNCERTAIN = "uncertain"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


_FAILED_SAFETY = frozenset({ImageSafetyState.UNREADABLE, ImageSafetyState.TRANSFORM_FAILED})
_UNCERTAIN_SAFETY = frozenset({ImageSafetyState.UNCERTAIN, ImageSafetyState.DETECTION_FAILED})
_PROCESSED_RENDITIONS = frozenset({RenditionKind.NORMALIZED, RenditionKind.BLURRED, RenditionKind.RECOLORED})
_UNCERTAIN_RIGHTS = frozenset({RightsStatus.UNKNOWN, RightsStatus.DISPUTED})


def resolve_display_status(
    kind: MediaKind,
    image_safety: ImageSafetyState | None,
    availability: Availability,
    renditions: RenditionSet,
) -> DisplayStatus:
    """Worse state wins so a failure is never hidden: unavailable > failed > uncertain > processed > original (D8-C-09)."""
    if not isinstance(renditions, RenditionSet):
        raise ValueError("renditions must be a RenditionSet")
    classify_safety(kind, image_safety)
    if classify_availability(availability) is Usability.NOT_USABLE:
        return DisplayStatus.UNAVAILABLE
    safety = None if image_safety is None else ImageSafetyState(image_safety)
    if safety in _FAILED_SAFETY:
        return DisplayStatus.FAILED
    if safety in _UNCERTAIN_SAFETY:
        return DisplayStatus.UNCERTAIN
    if safety is ImageSafetyState.PROCESSED_READY or any(r.kind in _PROCESSED_RENDITIONS for r in renditions.renditions):
        return DisplayStatus.PROCESSED
    return DisplayStatus.ORIGINAL


def build_media_asset_view(
    asset: MediaAsset,
    renditions: RenditionSet,
    image_safety: ImageSafetyState | None,
    availability: Availability,
    semantics: Mapping[str, object],
    technical: Mapping[str, object],
    usage_summary: Mapping[str, object],
) -> dict:
    """Assemble every CT-MED-002 group; uncertain rights are shown with their evidence, never hidden."""
    if not isinstance(asset, MediaAsset):
        raise ValueError("asset must be a MediaAsset")
    if not isinstance(renditions, RenditionSet):
        raise ValueError("renditions must be a RenditionSet")
    if renditions.media_asset_id != asset.media_asset_id:
        raise ValueError("renditions must belong to the asset")
    for name, value in (("semantics", semantics), ("technical", technical), ("usage_summary", usage_summary)):
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be a mapping")
    kind = MediaKind(asset.kind)
    availability = Availability(availability)
    safety = None if image_safety is None else ImageSafetyState(image_safety)
    rights_status = RightsStatus(asset.rights.status)
    return {
        "identity": {
            "media_asset_id": asset.media_asset_id,
            "kind": kind.value,
            "canonical_fingerprint": None if asset.fingerprint is None else asset.fingerprint.value,
            "index_revision": asset.index_revision,
        },
        "provenance": [
            {
                "source_ref": e.source_ref,
                "article_ref": e.article_ref,
                "event_ref": e.event_ref,
                "original_locator": e.original_locator,
                "observed_at": e.observed_at,
                "relation": ProvenanceRelation(e.relation).value,
            }
            for e in asset.provenance
        ],
        "semantics": dict(semantics),
        "technical": dict(technical),
        "safety": {
            "image_safety_state": None if safety is None else safety.value,
            "usability": classify_safety(kind, safety).value,
        },
        "rights": {
            "status": rights_status.value,
            "evidence_refs": list(asset.rights.evidence_refs),
            "uncertain": rights_status in _UNCERTAIN_RIGHTS,
        },
        "availability": {"state": availability.value, "usability": classify_availability(availability).value},
        "renditions": [
            {
                "rendition_ref": r.rendition_ref,
                "kind": r.kind.value,
                "artifact_version_ref": r.artifact_version_ref,
                "source_artifact_version_ref": r.source_artifact_version_ref,
                "transformation_spec_revision": r.transformation_spec_revision,
                "processor_version": r.processor_version,
                "lineage": list(r.lineage),
            }
            for r in renditions.renditions
        ],
        "usage": dict(usage_summary),
        "display_status": resolve_display_status(kind, safety, availability, renditions).value,
    }
