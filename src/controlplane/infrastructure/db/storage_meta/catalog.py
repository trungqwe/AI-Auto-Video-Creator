"""PostgreSQL adapter of ArtifactVersionCatalogPort (CT-STO-001) on cp_artifact_versions."""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from controlplane.application.storage_meta.declare_version import ArtifactVersionRef
from controlplane.domain.storage_meta.declaration import DeclareArtifactVersionRequest


class PostgresArtifactVersionCatalog:
    """Workspace-scoped catalog over a caller-owned connection; never commits or rolls back."""

    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def find_matching(self, owner_resource_ref: str, artifact_kind: str, content_sha256: str) -> ArtifactVersionRef | None:
        row = self._connection.execute("SELECT artifact_id, artifact_version_id::text FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND owner_ref=%s AND artifact_kind=%s AND sha256_hash=%s ORDER BY created_at, artifact_version_id LIMIT 1", (self._workspace_id, owner_resource_ref, artifact_kind, content_sha256)).fetchone()
        return None if row is None else ArtifactVersionRef(str(row[0]), str(row[1]))

    def find_artifact_id(self, owner_resource_ref: str, artifact_kind: str) -> str | None:
        row = self._connection.execute("SELECT artifact_id FROM controlplane.cp_artifact_versions WHERE workspace_id=%s AND owner_ref=%s AND artifact_kind=%s ORDER BY created_at, artifact_version_id LIMIT 1", (self._workspace_id, owner_resource_ref, artifact_kind)).fetchone()
        return None if row is None else str(row[0])

    def insert_version(self, artifact_id: str, artifact_version_id: str, request: DeclareArtifactVersionRequest) -> None:
        self._connection.execute("INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, retention_ref, sensitivity_ref, intended_storage_class, producer_operation_ref, lineage_refs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (artifact_version_id, self._workspace_id, artifact_id, request.content_sha256, request.size_bytes, request.media_type, request.artifact_kind, request.owner_resource_ref, request.retention_class, request.sensitivity_class, request.intended_storage_class, request.producer_operation_ref, Jsonb(list(request.lineage_refs))))


__all__ = ["PostgresArtifactVersionCatalog"]
