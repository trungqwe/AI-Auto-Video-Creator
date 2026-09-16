"""P5B application orchestration and persistence ports."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Callable, Protocol
import uuid

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ArtifactLocationState, ForbiddenTransitionError, transition_artifact_location
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion, CleanupAuthorization

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNSAFE_REFERENCE = re.compile(r"(?:^[/\\]|^[A-Za-z]:[\\/]|(?:^|[/\\])\.\.(?:[/\\]|$)|^file://|(?:^|[?&;\s])(?:signature|token|credential|access_token|secret|password)\s*=|[;&|`]|\$\(|\brm\s+-rf\b)", re.IGNORECASE)


class StorageMetaRepository(Protocol):
    def find_version(self, workspace_id: str, artifact_id: str, sha256_hash: str) -> ArtifactVersion | None: ...
    def insert_version(self, version_id: str, values: dict[str, Any]) -> ArtifactVersion | None: ...
    def get_version(self, workspace_id: str, artifact_version_id: str) -> ArtifactVersion | None: ...
    def insert_location(self, location_id: str, values: dict[str, Any]) -> ArtifactLocation | None: ...
    def get_location(self, workspace_id: str, location_id: str) -> ArtifactLocation | None: ...
    def update_location(self, location: ArtifactLocation, expected_revision: int, requested_state: ArtifactLocationState, evidence: str | None) -> ArtifactLocation | None: ...
    def insert_authorization(self, authorization_id: str, values: dict[str, Any]) -> CleanupAuthorization: ...
    def authorize_location(self, location: ArtifactLocation, expected_revision: int) -> bool: ...


RepositoryFactory = Callable[[object], StorageMetaRepository]


def _repository(factory: RepositoryFactory, values: dict[str, Any]) -> StorageMetaRepository:
    connection = values.pop("connection", None)
    if connection is None:
        raise TypeError("connection is required")
    return factory(connection)


class ArtifactVersionStore:
    def __init__(self, repository_factory: RepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def register(self, **kwargs: Any) -> ArtifactVersion:
        repository = _repository(self._repository_factory, kwargs)
        if not _SHA256.fullmatch(str(kwargs.get("sha256_hash", ""))):
            raise ValueError("VALIDATION_ERROR: invalid SHA-256")
        if not isinstance(kwargs.get("size_bytes"), int) or kwargs["size_bytes"] <= 0:
            raise ValueError("VALIDATION_ERROR: size_bytes must be positive")
        if not str(kwargs.get("mime_type", "")).strip():
            raise ValueError("VALIDATION_ERROR: mime_type is required")
        kwargs["mime_type"] = kwargs["mime_type"].strip()
        result = repository.find_version(kwargs["workspace_id"], kwargs["artifact_id"], kwargs["sha256_hash"])
        result = result or repository.insert_version(str(uuid.uuid4()), kwargs)
        if result is None:
            result = repository.find_version(kwargs["workspace_id"], kwargs["artifact_id"], kwargs["sha256_hash"])
        if result is None:
            raise RuntimeError("artifact version insert returned no row")
        return result

    def get_scoped(self, **kwargs: Any) -> ArtifactVersion | None:
        repository = _repository(self._repository_factory, kwargs)
        return repository.get_version(kwargs["workspace_id"], kwargs["artifact_version_id"])


class ArtifactLocationStore:
    def __init__(self, repository_factory: RepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def declare(self, **kwargs: Any) -> ArtifactLocation:
        repository = _repository(self._repository_factory, kwargs)
        for field in ("backend_ref", "provider_namespace_ref", "provider_object_ref", "logical_locator"):
            value = str(kwargs.get(field, ""))
            if not value or _UNSAFE_REFERENCE.search(value):
                raise ValueError(f"VALIDATION_ERROR: unsafe {field}")
        result = repository.insert_location(str(uuid.uuid4()), kwargs)
        if result is None:
            raise RuntimeError("artifact location insert returned no row")
        return result

    def get_scoped(self, **kwargs: Any) -> ArtifactLocation | None:
        repository = _repository(self._repository_factory, kwargs)
        return repository.get_location(kwargs["workspace_id"], kwargs["location_id"])

    def transition(self, **kwargs: Any) -> ArtifactLocation:
        repository = _repository(self._repository_factory, kwargs)
        current = repository.get_location(kwargs["workspace_id"], kwargs["location_id"])
        if current is None:
            raise PermissionError("artifact location not found in workspace")
        requested = ArtifactLocationState(kwargs["requested_state"])
        self.validate_transition(current_state=current.state, current_revision=current.revision, expected_revision=kwargs["expected_revision"], requested_state=requested)
        result = repository.update_location(current, kwargs["expected_revision"], requested, kwargs.get("verification_evidence_ref"))
        if result is None:
            latest = repository.get_location(current.workspace_id, current.location_id)
            raise RevisionConflictError(latest.revision if latest else current.revision)
        return result

    def validate_transition(self, **kwargs: Any) -> object:
        if ArtifactLocationState(kwargs["requested_state"]) is ArtifactLocationState.DELETED:
            raise ForbiddenTransitionError(aggregate_type="artifact_location", current_state=kwargs["current_state"], requested_next_state=kwargs["requested_state"], current_revision=kwargs["current_revision"])
        return transition_artifact_location(**kwargs)


class CleanupAuthorizationStore:
    def __init__(self, repository_factory: RepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def authorize(self, **kwargs: Any) -> CleanupAuthorization:
        repository = _repository(self._repository_factory, kwargs)
        location = repository.get_location(kwargs["workspace_id"], kwargs["location_id"])
        if location is None or location.state is not ArtifactLocationState.CLEANUP_ELIGIBLE:
            raise ValueError("POLICY_VIOLATION: location is not cleanup eligible")
        if kwargs["recovery_epoch"] != kwargs["current_recovery_epoch"]:
            raise ValueError("REVISION_CONFLICT: stale recovery epoch")
        if location.revision != kwargs["expected_revision"]:
            raise RevisionConflictError(location.revision)
        if location.verification_evidence_ref is None or kwargs["verification_evidence_ref"] != location.verification_evidence_ref:
            raise ValueError("POLICY_VIOLATION: verification evidence mismatch")
        version = repository.get_version(kwargs["workspace_id"], kwargs["artifact_version_id"])
        if version is None or version.artifact_version_id != location.artifact_version_id or version.sha256_hash != kwargs["artifact_hash"]:
            raise ValueError("POLICY_VIOLATION: artifact binding mismatch")
        transition_artifact_location(current_state=location.state, current_revision=location.revision, expected_revision=kwargs["expected_revision"], requested_state=ArtifactLocationState.CLEANUP_AUTHORIZED)
        authorization = repository.insert_authorization(str(uuid.uuid4()), kwargs)
        if not repository.authorize_location(location, kwargs["expected_revision"]):
            latest = repository.get_location(location.workspace_id, location.location_id)
            raise RevisionConflictError(latest.revision if latest else location.revision)
        return authorization

    def is_expired(self, **kwargs: Any) -> bool:
        expires = kwargs["authorization"].expires_at
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        return kwargs["evaluated_at"] >= expires


__all__ = ["ArtifactLocationStore", "ArtifactVersionStore", "CleanupAuthorizationStore", "StorageMetaRepository"]
