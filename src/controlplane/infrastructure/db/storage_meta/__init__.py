"""PostgreSQL persistence adapter for P5B storage metadata."""
from __future__ import annotations

from typing import Any

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion, CleanupAuthorization

_VERSION_COLUMNS = "workspace_id::text, artifact_id, artifact_version_id::text, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref, created_at"
_LOCATION_COLUMNS = "workspace_id::text, location_id::text, artifact_version_id::text, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, observed_hash, observed_size_bytes, provider_metadata_revision, verification_evidence_ref, state, revision, created_at, updated_at"


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _version(row: Any) -> ArtifactVersion | None:
    return None if row is None else ArtifactVersion(str(row[0]), str(row[1]), str(row[2]), str(row[3]), int(row[4]), str(row[5]), str(row[6]), str(row[7]), row[8], str(row[9]), str(row[10]), _iso(row[11]))


def _location(row: Any) -> ArtifactLocation | None:
    return None if row is None else ArtifactLocation(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), row[7], row[8], row[9], row[10], ArtifactLocationState(str(row[11])), int(row[12]), _iso(row[13]), _iso(row[14]))


class PostgresStorageMetaRepository:
    """SQL adapter over a caller-owned connection; never commits or rolls back."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def find_version(self, workspace_id: str, artifact_id: str, sha256_hash: str) -> ArtifactVersion | None:
        return _version(self._connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_id=%s AND sha256_hash=%s", (workspace_id, artifact_id, sha256_hash)).fetchone())

    def insert_version(self, version_id: str, values: dict[str, Any]) -> ArtifactVersion | None:
        row = self._connection.execute("INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, artifact_id, sha256_hash) DO NOTHING RETURNING " + _VERSION_COLUMNS, (version_id, values["workspace_id"], values["artifact_id"], values["sha256_hash"], values["size_bytes"], values["mime_type"], values["artifact_kind"], values["owner_ref"], values.get("lineage_ref"), values["retention_ref"], values["sensitivity_ref"])).fetchone()
        return _version(row)

    def get_version(self, workspace_id: str, artifact_version_id: str) -> ArtifactVersion | None:
        return _version(self._connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_version_id=%s", (workspace_id, artifact_version_id)).fetchone())

    def insert_location(self, location_id: str, values: dict[str, Any]) -> ArtifactLocation | None:
        row = self._connection.execute("INSERT INTO controlplane.cp_artifact_locations (location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, state, revision) VALUES (%s,%s,%s,%s,%s,%s,%s,'DECLARED',1) RETURNING " + _LOCATION_COLUMNS, (location_id, values["workspace_id"], values["artifact_version_id"], values["backend_ref"], values["provider_namespace_ref"], values["provider_object_ref"], values["logical_locator"])).fetchone()
        return _location(row)

    def get_location(self, workspace_id: str, location_id: str) -> ArtifactLocation | None:
        return _location(self._connection.execute(f"SELECT {_LOCATION_COLUMNS} FROM controlplane.cp_artifact_locations WHERE workspace_id=%s AND location_id=%s", (workspace_id, location_id)).fetchone())

    def update_location(self, location: ArtifactLocation, expected_revision: int, requested_state: ArtifactLocationState, evidence: str | None) -> ArtifactLocation | None:
        row = self._connection.execute("UPDATE controlplane.cp_artifact_locations SET state=%s, revision=revision+1, verification_evidence_ref=COALESCE(%s, verification_evidence_ref), updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state=%s RETURNING " + _LOCATION_COLUMNS, (requested_state.value, evidence, location.workspace_id, location.location_id, expected_revision, location.state.value)).fetchone()
        return _location(row)

    def insert_authorization(self, authorization_id: str, values: dict[str, Any]) -> CleanupAuthorization:
        row = self._connection.execute("INSERT INTO controlplane.cp_cleanup_authorizations (cleanup_authorization_id, workspace_id, location_id, artifact_version_id, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING workspace_id::text, cleanup_authorization_id::text, location_id::text, artifact_version_id::text, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref", (authorization_id, values["workspace_id"], values["location_id"], values["artifact_version_id"], values["artifact_hash"], values["reason"], values["policy_revision"], values["completion_evidence_ref"], values["verification_evidence_ref"], values["issued_at"], values["expires_at"], values["recovery_epoch"], values["authorizing_owner_ref"], values["actor_ref"], values["audit_ref"], values["correlation_ref"])).fetchone()
        return CleanupAuthorization(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]), _iso(row[9]), _iso(row[10]), int(row[11]), str(row[12]), str(row[13]), str(row[14]), str(row[15]))

    def authorize_location(self, location: ArtifactLocation, expected_revision: int) -> bool:
        return self._connection.execute("UPDATE controlplane.cp_artifact_locations SET state='CLEANUP_AUTHORIZED', revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state='CLEANUP_ELIGIBLE'", (location.workspace_id, location.location_id, expected_revision)).rowcount == 1


__all__ = ["PostgresStorageMetaRepository"]
