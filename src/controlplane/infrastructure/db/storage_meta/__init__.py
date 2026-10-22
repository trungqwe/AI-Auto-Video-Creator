"""PostgreSQL persistence adapter for P5B storage metadata."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from psycopg.types.json import Jsonb

from controlplane.application.storage_meta.cloud_persist import UploadReceipt, UploadReceiptState
from controlplane.application.storage_meta.materialization import WorkingSetPolicy
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion, CleanupAuthorization
from controlplane.infrastructure.db.storage_meta.records import ArtifactLocationFields, ArtifactVersionExtension, MaterializationLease, RevisionPlacement

_VERSION_COLUMNS = "workspace_id::text, artifact_id, artifact_version_id::text, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref, created_at"
_LOCATION_COLUMNS = "workspace_id::text, location_id::text, artifact_version_id::text, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, observed_hash, observed_size_bytes, provider_metadata_revision, verification_evidence_ref, state, revision, created_at, updated_at"
_LEASE_COLUMNS = "lease_ref, operation_key, device_ref, staging_root_ref, expected_total_bytes, state, expires_at, revision"
_PLACEMENT_COLUMNS = "placement_id, artifact_version_id::text, revision_ref, storage_class, location_id::text"
_REVISION = re.compile(r"[1-9][0-9]*")
_LEASE_SETTLED_STATES = ("RELEASED", "EXPIRED")
_RECEIPT_STATE_TO_DB = {UploadReceiptState.PREPARED: "PREPARED", UploadReceiptState.VERIFIED: "VERIFIED", UploadReceiptState.OUTCOME_UNKNOWN: "OUTCOME_UNKNOWN", UploadReceiptState.CORRUPT: "FAILED", UploadReceiptState.MISSING: "FAILED"}
_RECEIPT_STATE_FROM_DB = {"PREPARED": UploadReceiptState.PREPARED, "UPLOADING": UploadReceiptState.PREPARED, "UPLOADED_UNVERIFIED": UploadReceiptState.PREPARED, "VERIFIED": UploadReceiptState.VERIFIED, "OUTCOME_UNKNOWN": UploadReceiptState.OUTCOME_UNKNOWN, "FAILED": UploadReceiptState.CORRUPT}


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _version(row: Any) -> ArtifactVersion | None:
    return None if row is None else ArtifactVersion(str(row[0]), str(row[1]), str(row[2]), str(row[3]), int(row[4]), str(row[5]), str(row[6]), str(row[7]), row[8], str(row[9]), str(row[10]), _iso(row[11]))


def _location(row: Any) -> ArtifactLocation | None:
    return None if row is None else ArtifactLocation(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), row[7], row[8], row[9], row[10], ArtifactLocationState(str(row[11])), int(row[12]), _iso(row[13]), _iso(row[14]))


def _lease(row: Any) -> MaterializationLease | None:
    return None if row is None else MaterializationLease(str(row[0]), str(row[1]), str(row[2]), str(row[3]), int(row[4]), str(row[5]), _iso(row[6]), int(row[7]))


def _placement(row: Any) -> RevisionPlacement | None:
    return None if row is None else RevisionPlacement(str(row[0]), str(row[1]), str(row[2]), str(row[3]), None if row[4] is None else str(row[4]))


class PostgresStorageMetaRepository:
    """SQL adapter over a caller-owned connection; never commits or rolls back."""

    def __init__(self, connection: Any, workspace_id: str | None = None, upload_backend_ref: str = "cloud") -> None:
        self._connection = connection
        self._workspace_id = workspace_id
        self._upload_backend_ref = upload_backend_ref

    def _scope(self) -> str:
        if self._workspace_id is None:
            raise ValueError("workspace_id is required for this operation")
        return self._workspace_id

    def find_version(self, workspace_id: str, artifact_id: str, sha256_hash: str) -> ArtifactVersion | None:
        return _version(self._connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_id=%s AND sha256_hash=%s", (workspace_id, artifact_id, sha256_hash)).fetchone())

    def insert_version(self, version_id: str, values: dict[str, Any]) -> ArtifactVersion | None:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref, intended_storage_class, producer_operation_ref, lineage_refs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, artifact_id, sha256_hash) DO NOTHING RETURNING " + _VERSION_COLUMNS,
            (version_id, values["workspace_id"], values["artifact_id"], values["sha256_hash"], values["size_bytes"], values["mime_type"], values["artifact_kind"], values["owner_ref"], values.get("lineage_ref"), values["retention_ref"], values["sensitivity_ref"], values.get("intended_storage_class"), values.get("producer_operation_ref"), Jsonb(list(values.get("lineage_refs") or []))),
        ).fetchone()
        return _version(row)

    def get_version(self, workspace_id: str, artifact_version_id: str) -> ArtifactVersion | None:
        return _version(self._connection.execute(f"SELECT {_VERSION_COLUMNS} FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_version_id=%s", (workspace_id, artifact_version_id)).fetchone())

    def get_version_extension(self, workspace_id: str, artifact_version_id: str) -> ArtifactVersionExtension | None:
        row = self._connection.execute("SELECT artifact_version_id::text, intended_storage_class, producer_operation_ref, lineage_refs FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_version_id=%s", (workspace_id, artifact_version_id)).fetchone()
        return None if row is None else ArtifactVersionExtension(str(row[0]), row[1], row[2], tuple(row[3]))

    def insert_location(self, location_id: str, values: dict[str, Any]) -> ArtifactLocation | None:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_artifact_locations (location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, state, revision, device_ref, logical_category, last_verified_at, lease_ref, retention_state, cleanup_state) VALUES (%s,%s,%s,%s,%s,%s,%s,'DECLARED',1,%s,%s,%s,%s,%s,%s) RETURNING " + _LOCATION_COLUMNS,
            (location_id, values["workspace_id"], values["artifact_version_id"], values["backend_ref"], values["provider_namespace_ref"], values["provider_object_ref"], values["logical_locator"], values.get("device_ref"), values.get("logical_category"), values.get("last_verified_at"), values.get("lease_ref"), values.get("retention_state"), values.get("cleanup_state")),
        ).fetchone()
        return _location(row)

    def get_location(self, workspace_id: str, location_id: str) -> ArtifactLocation | None:
        return _location(self._connection.execute(f"SELECT {_LOCATION_COLUMNS} FROM controlplane.cp_artifact_locations WHERE workspace_id=%s AND location_id=%s", (workspace_id, location_id)).fetchone())

    def get_location_fields(self, workspace_id: str, location_id: str) -> ArtifactLocationFields | None:
        row = self._connection.execute("SELECT location_id::text, device_ref, logical_category, last_verified_at, lease_ref, retention_state, cleanup_state FROM controlplane.cp_artifact_locations WHERE workspace_id=%s AND location_id=%s", (workspace_id, location_id)).fetchone()
        return None if row is None else ArtifactLocationFields(str(row[0]), row[1], row[2], None if row[3] is None else _iso(row[3]), row[4], row[5], row[6])

    def update_location(self, location: ArtifactLocation, expected_revision: int, requested_state: ArtifactLocationState, evidence: str | None) -> ArtifactLocation | None:
        row = self._connection.execute("UPDATE controlplane.cp_artifact_locations SET state=%s, revision=revision+1, last_verified_at=CASE WHEN %s::text = 'VERIFIED' THEN CURRENT_TIMESTAMP ELSE last_verified_at END, verification_evidence_ref=COALESCE(%s, verification_evidence_ref), updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state=%s RETURNING " + _LOCATION_COLUMNS, (requested_state.value, requested_state.value, evidence, location.workspace_id, location.location_id, expected_revision, location.state.value)).fetchone()
        return _location(row)

    def insert_authorization(self, authorization_id: str, values: dict[str, Any]) -> CleanupAuthorization:
        row = self._connection.execute("INSERT INTO controlplane.cp_cleanup_authorizations (cleanup_authorization_id, workspace_id, location_id, artifact_version_id, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING workspace_id::text, cleanup_authorization_id::text, location_id::text, artifact_version_id::text, artifact_hash, reason, policy_revision, completion_evidence_ref, verification_evidence_ref, issued_at, expires_at, recovery_epoch, authorizing_owner_ref, actor_ref, audit_ref, correlation_ref", (authorization_id, values["workspace_id"], values["location_id"], values["artifact_version_id"], values["artifact_hash"], values["reason"], values["policy_revision"], values["completion_evidence_ref"], values["verification_evidence_ref"], values["issued_at"], values["expires_at"], str(values["recovery_epoch"]), values["authorizing_owner_ref"], values["actor_ref"], values["audit_ref"], values["correlation_ref"])).fetchone()
        return CleanupAuthorization(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]), _iso(row[9]), _iso(row[10]), str(row[11]), str(row[12]), str(row[13]), str(row[14]), str(row[15]))

    def authorize_location(self, location: ArtifactLocation, expected_revision: int) -> bool:
        return self._connection.execute("UPDATE controlplane.cp_artifact_locations SET state='CLEANUP_AUTHORIZED', revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND location_id=%s AND revision=%s AND state='CLEANUP_ELIGIBLE'", (location.workspace_id, location.location_id, expected_revision)).rowcount == 1

    def get(self, operation_key: str) -> UploadReceipt | None:
        workspace_id = self._scope()
        row = self._connection.execute("SELECT r.operation_key, r.artifact_version_id::text, v.sha256_hash, v.size_bytes, r.provider_object_ref, r.state, r.verification_evidence_ref FROM controlplane.cp_upload_receipts r JOIN controlplane.cp_artifact_versions v ON v.workspace_id = r.workspace_id AND v.artifact_version_id = r.artifact_version_id WHERE r.workspace_id=%s AND r.operation_key=%s", (workspace_id, operation_key)).fetchone()
        if row is None:
            return None
        if row[4] is None:
            raise ValueError("upload receipt has no provider object")
        return UploadReceipt(str(row[0]), str(row[1]), str(row[2]), int(row[3]), str(row[4]), _RECEIPT_STATE_FROM_DB[str(row[5])], row[6])

    def save(self, receipt: UploadReceipt) -> None:
        workspace_id = self._scope()
        version = self._connection.execute("SELECT sha256_hash, size_bytes FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND artifact_version_id=%s", (workspace_id, receipt.artifact_version_id)).fetchone()
        if version is None:
            raise LookupError("artifact version not found in workspace")
        if (str(version[0]), int(version[1])) != (receipt.content_sha256, receipt.size_bytes):
            raise ValueError("upload receipt content does not match artifact version")
        row = self._connection.execute("INSERT INTO controlplane.cp_upload_receipts (workspace_id, operation_key, artifact_version_id, target_backend_ref, provider_object_ref, state, verification_evidence_ref, revision) VALUES (%s,%s,%s,%s,%s,%s,%s,1) ON CONFLICT (workspace_id, operation_key) DO UPDATE SET state=EXCLUDED.state, verification_evidence_ref=EXCLUDED.verification_evidence_ref, revision=cp_upload_receipts.revision+1, updated_at=CURRENT_TIMESTAMP WHERE cp_upload_receipts.artifact_version_id=EXCLUDED.artifact_version_id AND cp_upload_receipts.provider_object_ref IS NOT DISTINCT FROM EXCLUDED.provider_object_ref RETURNING revision", (workspace_id, receipt.operation_key, receipt.artifact_version_id, self._upload_backend_ref, receipt.object_id, _RECEIPT_STATE_TO_DB[receipt.state], receipt.verification_evidence_ref)).fetchone()
        if row is None:
            raise ValueError("operation_key was already used with different content")

    def insert_lease(self, lease_ref: str, operation_key: str, device_ref: str, staging_root_ref: str, expected_total_bytes: int, expires_at: datetime) -> MaterializationLease | None:
        workspace_id = self._scope()
        row = self._connection.execute("INSERT INTO controlplane.cp_materialization_leases (workspace_id, lease_ref, operation_key, device_ref, staging_root_ref, expected_total_bytes, state, expires_at, revision) VALUES (%s,%s,%s,%s,%s,%s,'ACTIVE',%s,1) ON CONFLICT (workspace_id, operation_key) DO NOTHING RETURNING " + _LEASE_COLUMNS, (workspace_id, lease_ref, operation_key, device_ref, staging_root_ref, expected_total_bytes, expires_at)).fetchone()
        if row is None:
            row = self._connection.execute(f"SELECT {_LEASE_COLUMNS} FROM controlplane.cp_materialization_leases WHERE workspace_id=%s AND operation_key=%s", (workspace_id, operation_key)).fetchone()
        return _lease(row)

    def get_lease(self, lease_ref: str) -> MaterializationLease | None:
        return _lease(self._connection.execute(f"SELECT {_LEASE_COLUMNS} FROM controlplane.cp_materialization_leases WHERE workspace_id=%s AND lease_ref=%s", (self._scope(), lease_ref)).fetchone())

    def settle_lease(self, lease_ref: str, expected_revision: int, new_state: str) -> MaterializationLease | None:
        if new_state not in _LEASE_SETTLED_STATES:
            raise ValueError("new_state must be RELEASED or EXPIRED")
        row = self._connection.execute("UPDATE controlplane.cp_materialization_leases SET state=%s, revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=%s AND lease_ref=%s AND revision=%s AND state='ACTIVE' RETURNING " + _LEASE_COLUMNS, (new_state, self._scope(), lease_ref, expected_revision)).fetchone()
        return _lease(row)

    def insert_revision_placement(self, placement_id: str, artifact_version_id: str, revision_ref: str, storage_class: str, location_id: str | None = None) -> RevisionPlacement | None:
        workspace_id = self._scope()
        row = self._connection.execute("INSERT INTO controlplane.cp_revision_placements (workspace_id, placement_id, artifact_version_id, revision_ref, storage_class, location_id) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, artifact_version_id, revision_ref) DO NOTHING RETURNING " + _PLACEMENT_COLUMNS, (workspace_id, placement_id, artifact_version_id, revision_ref, storage_class, location_id)).fetchone()
        if row is None:
            row = self._connection.execute(f"SELECT {_PLACEMENT_COLUMNS} FROM controlplane.cp_revision_placements WHERE workspace_id=%s AND artifact_version_id=%s AND revision_ref=%s", (workspace_id, artifact_version_id, revision_ref)).fetchone()
        return _placement(row)

    def get_revision_placement(self, placement_id: str) -> RevisionPlacement | None:
        return _placement(self._connection.execute(f"SELECT {_PLACEMENT_COLUMNS} FROM controlplane.cp_revision_placements WHERE workspace_id=%s AND placement_id=%s", (self._scope(), placement_id)).fetchone())

    def list_revision_placements(self, artifact_version_id: str) -> list[RevisionPlacement]:
        rows = self._connection.execute(f"SELECT {_PLACEMENT_COLUMNS} FROM controlplane.cp_revision_placements WHERE workspace_id=%s AND artifact_version_id=%s ORDER BY created_at, placement_id", (self._scope(), artifact_version_id)).fetchall()
        return [_placement(row) for row in rows]

    def insert_working_set_policy(self, policy_ref: str, policy: WorkingSetPolicy) -> bool:
        workspace_id = self._scope()
        if not _REVISION.fullmatch(policy.policy_revision):
            raise ValueError("policy_revision must be a positive integer string")
        return self._connection.execute("INSERT INTO controlplane.cp_working_set_policies (workspace_id, policy_ref, policy_revision, max_videos_per_render, max_working_set_bytes) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, policy_ref, policy_revision) DO NOTHING", (workspace_id, policy_ref, int(policy.policy_revision), policy.max_video_sets, policy.max_bytes)).rowcount == 1

    def get_working_set_policy(self, policy_ref: str, policy_revision: str | None = None) -> WorkingSetPolicy | None:
        workspace_id = self._scope()
        select = "SELECT policy_revision, max_videos_per_render, max_working_set_bytes FROM controlplane.cp_working_set_policies WHERE workspace_id=%s AND policy_ref=%s"
        if policy_revision is None:
            row = self._connection.execute(select + " ORDER BY policy_revision DESC LIMIT 1", (workspace_id, policy_ref)).fetchone()
        else:
            if not _REVISION.fullmatch(policy_revision):
                raise ValueError("policy_revision must be a positive integer string")
            row = self._connection.execute(select + " AND policy_revision=%s", (workspace_id, policy_ref, int(policy_revision))).fetchone()
        if row is None:
            return None
        if row[2] is None:
            raise ValueError("working set policy has no byte limit")
        return WorkingSetPolicy(int(row[2]), str(row[0]), int(row[1]))


__all__ = ["PostgresStorageMetaRepository"]
