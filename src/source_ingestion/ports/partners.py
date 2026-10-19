"""Partner ports for source ingestion (A-08): I artifact version, B content handoff, A-local config, G grant.

Payload field tables mirror docs/parallel-delivery/bindings/i-artifact-version.json 1.0.0.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from controlplane.domain.config_security import SecretHandle
from controlplane.domain.orchestration import ExecutionGrant

ARTIFACT_BINDING_VERSION = '1.0.0'
DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ('artifact_kind', 'string', True),
    ('owner_resource_ref', 'string', True),
    ('content_sha256', 'sha256', True),
    ('size_bytes', 'integer', True),
    ('media_type', 'string', True),
    ('lineage_refs', 'array', True),
    ('retention_class', 'string', True),
    ('sensitivity_class', 'string', True),
    ('intended_storage_class', 'string', True),
    ('producer_operation_ref', 'string', True),
)
DECLARE_ARTIFACT_VERSION_RESULT_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ('artifact_id', 'string', True),
    ('artifact_version_id', 'string', True),
    ('matched_existing', 'boolean', True),
    ('policy_decision', 'string', True),
    ('required_operation', 'string', False),
)


@dataclass(frozen=True)
class PolicyRevisionRef:
    workspace_id: str
    policy_kind: str
    revision: str

    def __post_init__(self) -> None:
        for name, value in (
            ('workspace_id', self.workspace_id),
            ('policy_kind', self.policy_kind),
            ('revision', self.revision),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')


@runtime_checkable
class ArtifactPort(Protocol):
    """CT-STO-001 seam to I; A declares artifact versions and never writes I tables."""

    def declare_artifact_version(self, request: Mapping[str, object]) -> Mapping[str, object]:
        ...


@runtime_checkable
class ContentHandoffPort(Protocol):
    """CT-CNT-001 seam to B; B decides and returns a CollectedDocumentResolution."""

    def resolve_collected_document(self, package: Mapping[str, object]) -> Mapping[str, object]:
        ...


@runtime_checkable
class ConfigPort(Protocol):
    """A-local until CONV-A-07 opens J->A CT-CFG-002; returns revision refs and SecretHandle, never raw secrets."""

    def get_policy_revision(self, workspace_id: str, policy_kind: str) -> PolicyRevisionRef | None:
        ...

    def get_credential_handle(self, workspace_id: str, source_id: str) -> SecretHandle | None:
        ...


@runtime_checkable
class ActivityGrantPort(Protocol):
    """G owns ExecutionGrant; A asks whether a grant is still current before accepting work."""

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        ...


__all__ = [
    'ARTIFACT_BINDING_VERSION',
    'ActivityGrantPort',
    'ArtifactPort',
    'ConfigPort',
    'ContentHandoffPort',
    'DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS',
    'DECLARE_ARTIFACT_VERSION_RESULT_FIELDS',
    'PolicyRevisionRef',
]
