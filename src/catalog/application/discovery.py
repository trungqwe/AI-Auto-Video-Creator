"""Media discovery registration and provenance merge (CT-MED-001, capability C)."""

from dataclasses import dataclass
from enum import StrEnum

from catalog.domain.identity import (
    CanonicalFingerprint,
    MediaAsset,
    MediaKind,
    ProvenanceEntry,
    RightsAssessment,
    RightsStatus,
)
from catalog.ports.repositories import MediaAssetRepository


class Disposition(StrEnum):
    NEW_ASSET = "new_asset"
    NEW_PROVENANCE = "new_provenance"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DiscoveryObservation:
    discovery_id: str
    kind: MediaKind
    provenance: ProvenanceEntry
    fingerprint: CanonicalFingerprint | None
    locator_validated: bool

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_id, str) or not self.discovery_id:
            raise ValueError("discovery_id must be a non-empty string")
        if not isinstance(self.kind, MediaKind):
            raise ValueError("kind must be a MediaKind")
        if not isinstance(self.provenance, ProvenanceEntry):
            raise ValueError("provenance must be a ProvenanceEntry")
        if self.fingerprint is not None and not isinstance(self.fingerprint, CanonicalFingerprint):
            raise ValueError("fingerprint must be a CanonicalFingerprint or None")
        if not isinstance(self.locator_validated, bool):
            raise ValueError("locator_validated must be a bool")


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    media_asset_id: str | None
    disposition: Disposition
    acquisition_required: bool


def register_discovery(
    repo: MediaAssetRepository, observation: DiscoveryObservation, new_asset_id: str
) -> DiscoveryResult:
    """Merge one discovery into the catalog; byte identity is the fingerprint, provenance is append-only."""
    if not observation.locator_validated:
        return DiscoveryResult(media_asset_id=None, disposition=Disposition.REJECTED, acquisition_required=False)
    seen = repo.find_by_discovery_id(observation.discovery_id)
    if seen is not None:
        return DiscoveryResult(seen.media_asset_id, Disposition.DUPLICATE_OBSERVATION, seen.fingerprint is None)
    if observation.fingerprint is not None:
        existing = repo.find_by_fingerprint(observation.fingerprint)
        if existing is not None:
            if observation.provenance in existing.provenance:
                return DiscoveryResult(existing.media_asset_id, Disposition.DUPLICATE_OBSERVATION, False)
            repo.save(existing.with_provenance(observation.provenance), discovery_id=observation.discovery_id)
            return DiscoveryResult(existing.media_asset_id, Disposition.NEW_PROVENANCE, False)
    asset = MediaAsset(
        media_asset_id=new_asset_id,
        kind=observation.kind,
        fingerprint=observation.fingerprint,
        provenance=(observation.provenance,),
        rights=RightsAssessment(status=RightsStatus.UNKNOWN, evidence_refs=()),
        index_revision=1,
    )
    repo.save(asset, discovery_id=observation.discovery_id)
    return DiscoveryResult(new_asset_id, Disposition.NEW_ASSET, observation.fingerprint is None)
