"""Structural P5B artifact-metadata contracts; behavior is intentionally absent."""
from __future__ import annotations

from dataclasses import dataclass

from controlplane.domain.statemachine import ArtifactLocationState


@dataclass(frozen=True)
class ArtifactVersion:
    workspace_id: str
    artifact_id: str
    artifact_version_id: str
    sha256_hash: str
    size_bytes: int
    mime_type: str
    artifact_kind: str
    owner_ref: str
    lineage_ref: str | None
    retention_ref: str
    sensitivity_ref: str
    created_at: str


@dataclass(frozen=True)
class ArtifactLocation:
    workspace_id: str
    location_id: str
    artifact_version_id: str
    backend_ref: str
    provider_namespace_ref: str
    provider_object_ref: str
    logical_locator: str
    observed_hash: str | None
    observed_size_bytes: int | None
    provider_metadata_revision: str | None
    verification_evidence_ref: str | None
    state: ArtifactLocationState
    revision: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CleanupAuthorization:
    workspace_id: str
    cleanup_authorization_id: str
    location_id: str
    artifact_version_id: str
    artifact_hash: str
    reason: str
    policy_revision: str
    completion_evidence_ref: str
    verification_evidence_ref: str
    issued_at: str
    expires_at: str
    recovery_epoch: int
    authorizing_owner_ref: str
    actor_ref: str
    audit_ref: str
    correlation_ref: str


__all__ = ["ArtifactLocation", "ArtifactVersion", "CleanupAuthorization"]
