"""Importable P5B application seams with no persistence implementation."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
import uuid

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ArtifactLocationState, ForbiddenTransitionError, transition_artifact_location
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion, CleanupAuthorization


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNSAFE_LOCATOR = re.compile(r"(?:^[/\\]|^[A-Za-z]:[\\/]|(?:^|[/\\])\.\.(?:[/\\]|$)|^file://|[?&](?:signature|token|credential)=|[;&|`])", re.IGNORECASE)


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _version(row: Any) -> ArtifactVersion | None:
    if row is None: return None
    return ArtifactVersion(str(row[0]), str(row[1]), str(row[2]), str(row[3]), int(row[4]), str(row[5]), str(row[6]), str(row[7]), row[8], str(row[9]), str(row[10]), _iso(row[11]))


def _location(row: Any) -> ArtifactLocation | None:
    if row is None: return None
    return ArtifactLocation(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), row[7], row[8], row[9], row[10], ArtifactLocationState(str(row[11])), int(row[12]), _iso(row[13]), _iso(row[14]))


_VERSION_COLUMNS = "workspace_id::text, artifact_id, artifact_version_id::text, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref, created_at"
_LOCATION_COLUMNS = "workspace_id::text, location_id::text, artifact_version_id::text, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, observed_hash, observed_size_bytes, provider_metadata_revision, verification_evidence_ref, state, revision, created_at, updated_at"


class ArtifactVersionStore:
    def register(self, **kwargs: Any) -> ArtifactVersion:
        connection = kwargs.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        if not _SHA256.fullmatch(str(kwargs.get("sha256_hash", ""))): raise ValueError("VALIDATION_ERROR: invalid SHA-256")
        if not isinstance(kwargs.get("size_bytes"), int) or kwargs["size_bytes"] <= 0: raise ValueError("VALIDATION_ERROR: size_bytes must be positive")
        if not str(kwargs.get("mime_type", "")).strip(): raise ValueError("VALIDATION_ERROR: mime_type is required")
        existing = _version(connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_id=%s AND sha256_hash=%s", (kwargs["workspace_id"], kwargs["artifact_id"], kwargs["sha256_hash"])).fetchone())
        if existing is not None: return existing
        version_id = str(uuid.uuid4())
        row = connection.execute("INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, artifact_id, sha256_hash) DO NOTHING RETURNING " + _VERSION_COLUMNS, (version_id, kwargs["workspace_id"], kwargs["artifact_id"], kwargs["sha256_hash"], kwargs["size_bytes"], kwargs["mime_type"].strip(), kwargs["artifact_kind"], kwargs["owner_ref"], kwargs.get("lineage_ref"), kwargs["retention_ref"], kwargs["sensitivity_ref"])).fetchone()
        if row is None:
            row = connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_id=%s AND sha256_hash=%s", (kwargs["workspace_id"], kwargs["artifact_id"], kwargs["sha256_hash"])).fetchone()
        result = _version(row)
        if result is None: raise RuntimeError("artifact version insert returned no row")
        return result

    def get_scoped(self, **kwargs: Any) -> ArtifactVersion | None:
        connection = kwargs.get("connection")
        if connection is None: raise TypeError("connection is required")
        return _version(connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_version_id=%s", (kwargs["workspace_id"], kwargs["artifact_version_id"])).fetchone())


class ArtifactLocationStore:
    def declare(self, **kwargs: Any) -> ArtifactLocation:
        connection = kwargs.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        locator = str(kwargs.get("logical_locator", ""))
        if not locator or _UNSAFE_LOCATOR.search(locator): raise ValueError("VALIDATION_ERROR: unsafe logical locator")
        location_id = str(uuid.uuid4())
        row = connection.execute("INSERT INTO controlplane.cp_artifact_locations (location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, state, revision) VALUES (%s,%s,%s,%s,%s,%s,%s,'DECLARED',1) RETURNING " + _LOCATION_COLUMNS, (location_id, kwargs["workspace_id"], kwargs["artifact_version_id"], kwargs["backend_ref"], kwargs["provider_namespace_ref"], kwargs["provider_object_ref"], locator)).fetchone()
        result = _location(row)
        if result is None: raise RuntimeError("artifact location insert returned no row")
        return result

    def get_scoped(self, **kwargs: Any) -> ArtifactLocation | None:
        connection = kwargs.get("connection")
        if connection is None: raise TypeError("connection is required")
        return _location(connection.execute(f"SELECT {_LOCATION_COLUMNS} FROM controlplane.cp_artifact_locations WHERE workspace_id=%s AND location_id=%s", (kwargs["workspace_id"], kwargs["location_id"])).fetchone())

    def transition(self, **kwargs: Any) -> ArtifactLocation:
        connection = kwargs.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        current = self.get_scoped(connection=connection, workspace_id=kwargs["workspace_id"], location_id=kwargs["location_id"])
        if current is None: raise PermissionError("artifact location not found in workspace")
        requested = ArtifactLocationState(kwargs["requested_state"])
        if requested is ArtifactLocationState.DELETED: raise ForbiddenTransitionError(aggregate_type="artifact_location", current_state=current.state, requested_next_state=requested, current_revision=current.revision)
        self.validate_transition(current_state=current.state, current_revision=current.revision, expected_revision=kwargs["expected_revision"], requested_state=requested)
        evidence = kwargs.get("verification_evidence_ref")
        row = connection.execute("UPDATE controlplane.cp_artifact_locations SET state=%s, revision=revision+1, verification_evidence_ref=COALESCE(%s, verification_evidence_ref), updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state=%s RETURNING " + _LOCATION_COLUMNS, (requested.value, evidence, current.workspace_id, current.location_id, kwargs["expected_revision"], current.state.value)).fetchone()
        result = _location(row)
        if result is None:
            latest = self.get_scoped(connection=connection, workspace_id=current.workspace_id, location_id=current.location_id)
            raise RevisionConflictError(latest.revision if latest is not None else current.revision)
        return result

    def validate_transition(self, **kwargs: Any) -> object:
        if ArtifactLocationState(kwargs["requested_state"]) is ArtifactLocationState.DELETED: raise ForbiddenTransitionError(aggregate_type="artifact_location", current_state=kwargs["current_state"], requested_next_state=kwargs["requested_state"], current_revision=kwargs["current_revision"])
        return transition_artifact_location(**kwargs)


class CleanupAuthorizationStore:
    def authorize(self, **kwargs: Any) -> CleanupAuthorization:
        connection = kwargs.pop("connection", None)
        if connection is None: raise TypeError("connection is required")
        location = ArtifactLocationStore().get_scoped(connection=connection, workspace_id=kwargs["workspace_id"], location_id=kwargs["location_id"])
        if location is None or location.state is not ArtifactLocationState.CLEANUP_ELIGIBLE: raise ValueError("POLICY_VIOLATION: location is not cleanup eligible")
        if kwargs["recovery_epoch"] != kwargs["current_recovery_epoch"]: raise ValueError("REVISION_CONFLICT: stale recovery epoch")
        if location.revision != kwargs["expected_revision"]: raise RevisionConflictError(location.revision)
        version = ArtifactVersionStore().get_scoped(connection=connection, workspace_id=kwargs["workspace_id"], artifact_version_id=kwargs["artifact_version_id"])
        if version is None or version.artifact_version_id != location.artifact_version_id or version.sha256_hash != kwargs["artifact_hash"]: raise ValueError("POLICY_VIOLATION: artifact binding mismatch")
        transition_artifact_location(current_state=location.state, current_revision=location.revision, expected_revision=kwargs["expected_revision"], requested_state=ArtifactLocationState.CLEANUP_AUTHORIZED)
        auth_id = str(uuid.uuid4())
        row = connection.execute("INSERT INTO controlplane.cp_cleanup_authorizations (cleanup_authorization_id, workspace_id, location_id, artifact_version_id, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING workspace_id::text, cleanup_authorization_id::text, location_id::text, artifact_version_id::text, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref", (auth_id, kwargs["workspace_id"], kwargs["location_id"], kwargs["artifact_version_id"], kwargs["artifact_hash"], kwargs["reason"], kwargs["policy_revision"], kwargs["completion_evidence_ref"], kwargs["verification_evidence_ref"], kwargs["issued_at"], kwargs["expires_at"], kwargs["recovery_epoch"], kwargs["authorizing_owner_ref"], kwargs["actor_ref"], kwargs["audit_ref"], kwargs["correlation_ref"])).fetchone()
        updated = connection.execute("UPDATE controlplane.cp_artifact_locations SET state='CLEANUP_AUTHORIZED', revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state='CLEANUP_ELIGIBLE'", (kwargs["workspace_id"], kwargs["location_id"], kwargs["expected_revision"])).rowcount
        if updated != 1: raise RevisionConflictError(ArtifactLocationStore().get_scoped(connection=connection, workspace_id=kwargs["workspace_id"], location_id=kwargs["location_id"]).revision)
        return CleanupAuthorization(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]), _iso(row[9]), _iso(row[10]), int(row[11]), str(row[12]), str(row[13]), str(row[14]), str(row[15]))

    def is_expired(self, **kwargs: Any) -> bool:
        expires = kwargs["authorization"].expires_at
        if isinstance(expires, str): expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        return kwargs["evaluated_at"] >= expires


__all__ = ["ArtifactLocationStore", "ArtifactVersionStore", "CleanupAuthorizationStore"]
