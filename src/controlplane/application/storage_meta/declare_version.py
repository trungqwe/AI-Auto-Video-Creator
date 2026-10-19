"""I-02: immutable artifact version declaration service (CT-STO-001, ADR-0006)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from typing import Callable, Protocol

from controlplane.domain.storage_meta.declaration import (
    DeclareArtifactVersionRequest,
    DeclareArtifactVersionResult,
    validate_declare_request,
)


@dataclass(frozen=True)
class ArtifactVersionRef:
    artifact_id: str
    artifact_version_id: str


class ArtifactVersionCatalogPort(Protocol):
    def find_matching(self, owner_resource_ref: str, artifact_kind: str, content_sha256: str) -> ArtifactVersionRef | None: ...
    def find_artifact_id(self, owner_resource_ref: str, artifact_kind: str) -> str | None: ...
    def insert_version(self, artifact_id: str, artifact_version_id: str, request: DeclareArtifactVersionRequest) -> None: ...


class DeclareRequestInvalidError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


class DeclareArtifactVersionService:
    def __init__(self, catalog: ArtifactVersionCatalogPort, id_factory: Callable[[], str] | None = None) -> None:
        self._catalog = catalog
        self._new_id = id_factory or (lambda: str(uuid.uuid4()))

    def declare(self, payload: dict) -> DeclareArtifactVersionResult:
        errors = validate_declare_request(payload)
        if errors:
            raise DeclareRequestInvalidError(errors[0]["code"], errors[0]["field"])
        request = DeclareArtifactVersionRequest(**{f.name: payload[f.name] for f in fields(DeclareArtifactVersionRequest)})
        existing = self._catalog.find_matching(request.owner_resource_ref, request.artifact_kind, request.content_sha256)
        if existing is not None:
            return DeclareArtifactVersionResult(existing.artifact_id, existing.artifact_version_id, True, "matched_existing")
        artifact_id = self._catalog.find_artifact_id(request.owner_resource_ref, request.artifact_kind)
        if artifact_id is None:
            artifact_id = self._new_id()
        artifact_version_id = self._new_id()
        self._catalog.insert_version(artifact_id, artifact_version_id, request)
        return DeclareArtifactVersionResult(artifact_id, artifact_version_id, False, "new_version", "upload")


__all__ = [
    "ArtifactVersionCatalogPort",
    "ArtifactVersionRef",
    "DeclareArtifactVersionService",
    "DeclareRequestInvalidError",
]
