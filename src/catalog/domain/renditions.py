"""Immutable media renditions and transformation-fingerprint dedupe (CT-MED-003)."""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from catalog.domain.identity import MediaKind

CLIP_SAFETY_TRANSFORM_FORBIDDEN = "CLIP_SAFETY_TRANSFORM_FORBIDDEN"
ORIGINAL_ALREADY_REGISTERED = "ORIGINAL_ALREADY_REGISTERED"
RENDITION_REF_CONFLICT = "RENDITION_REF_CONFLICT"
MEDIA_ASSET_MISMATCH = "MEDIA_ASSET_MISMATCH"


class RenditionKind(StrEnum):
    ORIGINAL = "original"
    NORMALIZED = "normalized"
    BLURRED = "blurred"
    RECOLORED = "recolored"
    THUMBNAIL = "thumbnail"
    EXTRACTED_FRAME = "extracted_frame"


_SAFETY_TRANSFORMS = frozenset({RenditionKind.BLURRED, RenditionKind.RECOLORED})
_REQUIRED_REFS = ("rendition_ref", "media_asset_id", "artifact_version_ref", "source_artifact_version_ref")


class RenditionRejected(ValueError):
    """A rendition registration refused by a catalog rule; ``code`` names the rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class Rendition:
    """One produced output artifact of a media asset; never mutated after registration."""

    rendition_ref: str
    media_asset_id: str
    kind: RenditionKind
    artifact_version_ref: str
    source_artifact_version_ref: str
    transformation_spec_revision: str
    processor_version: str
    lineage: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", RenditionKind(self.kind))
        for name in _REQUIRED_REFS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("transformation_spec_revision", "processor_version"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be a string")
        if not isinstance(self.lineage, tuple) or not all(isinstance(ref, str) for ref in self.lineage):
            raise ValueError("lineage must be a tuple of str")


def transformation_fingerprint(rendition: Rendition) -> str:
    """SHA-256 over the transformation inputs; output refs and lineage are excluded."""
    payload = {
        "source_artifact_version_ref": rendition.source_artifact_version_ref,
        "kind": rendition.kind.value,
        "transformation_spec_revision": rendition.transformation_spec_revision,
        "processor_version": rendition.processor_version,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RenditionSet:
    """Append-only renditions of one asset; ``register`` returns a new set."""

    media_asset_id: str
    renditions: tuple[Rendition, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.media_asset_id, str) or not self.media_asset_id:
            raise ValueError("media_asset_id must be a non-empty string")
        if not isinstance(self.renditions, tuple) or not all(isinstance(r, Rendition) for r in self.renditions):
            raise ValueError("renditions must be a tuple of Rendition")
        if any(r.media_asset_id != self.media_asset_id for r in self.renditions):
            raise ValueError("every rendition must belong to media_asset_id")

    def register(self, rendition: Rendition, media_kind: MediaKind) -> tuple["RenditionSet", Rendition]:
        """Register ``rendition``; an equal transformation returns the existing rendition."""
        media_kind = MediaKind(media_kind)
        if not isinstance(rendition, Rendition):
            raise ValueError("rendition must be a Rendition")
        if rendition.media_asset_id != self.media_asset_id:
            raise RenditionRejected(MEDIA_ASSET_MISMATCH, "rendition belongs to another media asset")
        if media_kind is MediaKind.CLIP and rendition.kind in _SAFETY_TRANSFORMS:
            raise RenditionRejected(CLIP_SAFETY_TRANSFORM_FORBIDDEN, f"clip media cannot take a {rendition.kind} rendition")
        if rendition.kind is RenditionKind.ORIGINAL:
            for existing in self.renditions:
                if existing.kind is RenditionKind.ORIGINAL:
                    if existing.artifact_version_ref == rendition.artifact_version_ref:
                        return self, existing
                    raise RenditionRejected(ORIGINAL_ALREADY_REGISTERED, "asset already has an original rendition")
        fingerprint = transformation_fingerprint(rendition)
        for existing in self.renditions:
            if transformation_fingerprint(existing) == fingerprint:
                return self, existing
        if any(existing.rendition_ref == rendition.rendition_ref for existing in self.renditions):
            raise RenditionRejected(RENDITION_REF_CONFLICT, "rendition_ref is already used by another transformation")
        return RenditionSet(self.media_asset_id, (*self.renditions, rendition)), rendition
