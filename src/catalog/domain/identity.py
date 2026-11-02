"""Media identity value objects and the MediaAsset aggregate root (capability C)."""

import dataclasses
import re
from dataclasses import dataclass
from enum import StrEnum

_FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")


class MediaKind(StrEnum):
    IMAGE = "image"
    CLIP = "clip"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class CanonicalFingerprint:
    """Lowercase hex SHA-256 of canonical bytes, as declared by I (CT-STO-001)."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _FINGERPRINT_PATTERN.fullmatch(self.value) is None:
            raise ValueError("canonical fingerprint must be 64 lowercase hex characters")


class RightsStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"


@dataclass(frozen=True, slots=True)
class RightsAssessment:
    """Rights as observed; unknown or disputed never blocks the asset (D8-C-06)."""

    status: RightsStatus
    evidence_refs: tuple[str, ...]


class ProvenanceRelation(StrEnum):
    HERO_IMAGE = "hero_image"
    INLINE_IMAGE = "inline_image"
    EMBEDDED_CLIP = "embedded_clip"
    OFFICIAL_SOCIAL_CLIP = "official_social_clip"
    USER_IMPORTED = "user_imported"
    AI_GENERATED = "ai_generated"


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    source_ref: str | None
    article_ref: str | None
    event_ref: str | None
    original_locator: str
    observed_at: str
    relation: ProvenanceRelation


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """Logical media: fingerprint is set at most once, provenance is append-only."""

    media_asset_id: str
    kind: MediaKind
    fingerprint: CanonicalFingerprint | None
    provenance: tuple[ProvenanceEntry, ...]
    rights: RightsAssessment
    index_revision: int

    def __post_init__(self) -> None:
        if self.fingerprint is not None and not isinstance(self.fingerprint, CanonicalFingerprint):
            raise ValueError("fingerprint must be a CanonicalFingerprint or None")
        if not isinstance(self.provenance, tuple) or not all(isinstance(e, ProvenanceEntry) for e in self.provenance):
            raise ValueError("provenance must be a tuple of ProvenanceEntry")

    def with_provenance(self, entry: ProvenanceEntry) -> "MediaAsset":
        """Return a copy with ``entry`` appended; an entry already present is skipped."""
        if not isinstance(entry, ProvenanceEntry):
            raise ValueError("entry must be a ProvenanceEntry")
        if entry in self.provenance:
            return self
        return dataclasses.replace(self, provenance=(*self.provenance, entry))

    def with_fingerprint(self, fingerprint: CanonicalFingerprint) -> "MediaAsset":
        """Return a copy with the fingerprint set; a set fingerprint is never replaced."""
        if self.fingerprint is not None:
            raise ValueError("fingerprint is already set and immutable")
        if not isinstance(fingerprint, CanonicalFingerprint):
            raise ValueError("fingerprint must be a CanonicalFingerprint")
        return dataclasses.replace(self, fingerprint=fingerprint)
