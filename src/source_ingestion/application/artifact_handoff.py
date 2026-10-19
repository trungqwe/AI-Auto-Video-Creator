"""Raw snapshot handoff to I through ArtifactPort (A-14; A-RULE-015).

A declares the version of the raw bytes to I (CT-STO-001) and keeps only the opaque
raw_snapshot_ref. Artifact kind, retention, sensitivity and storage class come from the policy
object supplied by the caller; A has no defaults and holds no storage path. A timeout after the
object may exist is OUTCOME_UNKNOWN: the run waits for reconciliation and the declaration is not
repeated until the run is RUNNING again.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import dataclasses
import enum
import hashlib
import uuid

from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionRun,
    RunStatus,
    record_attempt_outcome,
)
from source_ingestion.ports.partners import ArtifactPort
from source_ingestion.ports.source_adapter import FetchedDocument

_OPERATION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, 'urn:source-ingestion:raw-snapshot-operation')
_STORAGE_PATH_CHARS = frozenset({'/', ':', chr(92)})


class HandoffStatus(str, enum.Enum):
    DECLARED = 'DECLARED'
    OUTCOME_UNKNOWN = 'OUTCOME_UNKNOWN'


class HandoffError(ValueError):
    pass


class ReconciliationPendingError(HandoffError):
    pass


def _require_text(value: object, reason: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffError(reason)
    return value


@dataclasses.dataclass(frozen=True)
class RawSnapshotPolicy:
    """Values owned by policy and I; no defaults so A can never pick retention itself."""

    policy_revision: str
    artifact_kind: str
    retention_class: str
    sensitivity_class: str
    intended_storage_class: str

    def __post_init__(self) -> None:
        for field in dataclasses.fields(self):
            _require_text(getattr(self, field.name), 'INVALID_RAW_SNAPSHOT_POLICY')


@dataclasses.dataclass(frozen=True)
class RawSnapshotHandoff:
    status: HandoffStatus
    run: CollectionRun
    operation_key: str
    content_sha256: str
    policy_revision: str
    raw_snapshot_ref: str | None = None
    artifact_id: str | None = None
    matched_existing: bool | None = None


def snapshot_operation_key(collection_run_id: str, content_sha256: str) -> str:
    _require_text(collection_run_id, 'INVALID_OPERATION_KEY')
    _require_text(content_sha256, 'INVALID_OPERATION_KEY')
    return str(uuid.uuid5(_OPERATION_NAMESPACE, '|'.join((collection_run_id, content_sha256))))


def handoff_raw_snapshot(
    document: FetchedDocument,
    *,
    port: ArtifactPort,
    policy: RawSnapshotPolicy,
    run: CollectionRun,
    operation_key: str,
    lineage_refs: Sequence[str] = (),
) -> RawSnapshotHandoff:
    if run.status is RunStatus.WAITING_RECONCILIATION:
        raise ReconciliationPendingError('RECONCILIATION_PENDING')
    if run.status is not RunStatus.RUNNING:
        raise HandoffError('RUN_NOT_RUNNING')
    if not isinstance(policy, RawSnapshotPolicy):
        raise HandoffError('INVALID_RAW_SNAPSHOT_POLICY')
    _require_text(operation_key, 'INVALID_OPERATION_KEY')
    checkpoint_ref = _require_text(run.checkpoint_ref, 'RUN_CHECKPOINT_MISSING')
    media_type = _require_text(document.observation.media_type, 'INVALID_MEDIA_TYPE')
    lineage = [_require_text(ref, 'INVALID_LINEAGE_REF') for ref in lineage_refs]
    body = bytes(document.body)
    content_sha256 = hashlib.sha256(body).hexdigest()
    request = {
        'artifact_kind': policy.artifact_kind,
        'owner_resource_ref': run.run_id,
        'content_sha256': content_sha256,
        'size_bytes': len(body),
        'media_type': media_type,
        'lineage_refs': lineage,
        'retention_class': policy.retention_class,
        'sensitivity_class': policy.sensitivity_class,
        'intended_storage_class': policy.intended_storage_class,
        'producer_operation_ref': operation_key,
    }
    try:
        result = port.declare_artifact_version(request)
    except TimeoutError:
        waiting = record_attempt_outcome(
            run,
            AttemptOutcome.OUTCOME_UNKNOWN,
            source_active=True,
            deadline_passed=False,
            checkpoint_ref=checkpoint_ref,
        )
        return RawSnapshotHandoff(
            HandoffStatus.OUTCOME_UNKNOWN, waiting, operation_key, content_sha256, policy.policy_revision
        )
    if not isinstance(result, Mapping) or not isinstance(result.get('matched_existing'), bool):
        raise HandoffError('INVALID_ARTIFACT_RESULT')
    artifact_id = _require_text(result.get('artifact_id'), 'INVALID_ARTIFACT_RESULT')
    version_id = _require_text(result.get('artifact_version_id'), 'INVALID_ARTIFACT_RESULT')
    _require_text(result.get('policy_decision'), 'INVALID_ARTIFACT_RESULT')
    if any(char in _STORAGE_PATH_CHARS for char in artifact_id + version_id):
        raise HandoffError('STORAGE_PATH_REFERENCE')
    return RawSnapshotHandoff(
        HandoffStatus.DECLARED,
        run,
        operation_key,
        content_sha256,
        policy.policy_revision,
        raw_snapshot_ref=version_id,
        artifact_id=artifact_id,
        matched_existing=result['matched_existing'],
    )