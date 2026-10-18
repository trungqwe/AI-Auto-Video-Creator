"""Repository ports owned by capability C; PostgreSQL adapters arrive with CONV-C-01."""

from typing import Protocol

from catalog.domain.identity import CanonicalFingerprint, MediaAsset


class MediaAssetRepository(Protocol):
    def get(self, media_asset_id: str) -> MediaAsset | None: ...

    def find_by_fingerprint(self, fingerprint: CanonicalFingerprint) -> MediaAsset | None: ...

    def find_by_discovery_id(self, discovery_id: str) -> MediaAsset | None: ...

    def save(self, asset: MediaAsset, discovery_id: str | None = None) -> None: ...
