"""Read models of the 0010 storage metadata extension tables (infrastructure-only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactVersionExtension:
    artifact_version_id: str
    intended_storage_class: str | None
    producer_operation_ref: str | None
    lineage_refs: tuple[Any, ...]


@dataclass(frozen=True)
class ArtifactLocationFields:
    location_id: str
    device_ref: str | None
    logical_category: str | None
    last_verified_at: str | None
    lease_ref: str | None
    retention_state: str | None
    cleanup_state: str | None


@dataclass(frozen=True)
class MaterializationLease:
    lease_ref: str
    operation_key: str
    device_ref: str
    staging_root_ref: str
    expected_total_bytes: int
    state: str
    expires_at: str
    revision: int


@dataclass(frozen=True)
class RevisionPlacement:
    placement_id: str
    artifact_version_id: str
    revision_ref: str
    storage_class: str
    location_id: str | None


__all__ = ["ArtifactLocationFields", "ArtifactVersionExtension", "MaterializationLease", "RevisionPlacement"]
