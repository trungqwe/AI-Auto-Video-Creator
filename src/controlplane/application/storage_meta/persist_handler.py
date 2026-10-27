"""PW-I2: handler PersistVideoOutput (I) bọc PersistArtifactToCloud; receipt bền được commit trước khi upload, lỗi credential thành waiting credential_unavailable.

Assumptions (D8):
- input_refs has exactly one render_output (ref_id is relative path under staging root, e.g. render/out.mp4).
- new version has artifact_kind video_output, retention_ref durable, sensitivity_ref internal.
- receipt key is persist-output:<artifact_version_id> so replaying after worker crash always finds the same receipt.
- content verification uses sha256 and size reported by Drive (DriveObjectStore) instead of md5.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from controlplane.application.orchestration.completion_assembler import ARTIFACT_NOT_READY, REF_CLOUD_LOCATION, REF_OUTPUT_ARTIFACT, input_ref_ids
from controlplane.application.orchestration.workflows.activities import INVALID_ACTIVITY_REQUEST, MISSING_EXECUTION_GRANT, ActivityRejected
from controlplane.application.storage_meta.cloud_persist import CloudObjectPort, PersistArtifactToCloud, PersistResult, UploadReceipt, UploadReceiptState
from controlplane.application.storage_meta.handlers import CLOUD_BACKEND, DEFAULT_SENSITIVITY, Service, _NotReady, _advance, _failed, _job_id, _measure, _place_and_verify, _source_file, _waiting
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.storage.drive_object_store import DRIVE_CREDENTIAL_INVALID, DriveObjectStoreError

REF_RENDER_OUTPUT = 'render_output'
CREDENTIAL_UNAVAILABLE = 'credential_unavailable'
PROVIDER_UNAVAILABLE = 'provider_unavailable'
OUTPUT_KIND = 'video_output'
OUTPUT_MIME_TYPE = 'video/mp4'
OUTPUT_RETENTION = 'durable'
RECEIPT_KEY_PREFIX = 'persist-output:'
_NEXT_STATE = {ArtifactLocationState.DECLARED: ArtifactLocationState.MATERIALIZING, ArtifactLocationState.MATERIALIZING: ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.AVAILABLE_UNVERIFIED: ArtifactLocationState.VERIFYING}


class _CommittedReceipts:
    """Each get/save borrows a dedicated connection and the pool commits upon exit,
    ensuring the receipt is durable before upload starts; no transaction is held open during upload."""

    def __init__(self, transactions: Any, workspace_id: str) -> None:
        self._transactions = transactions
        self._workspace_id = workspace_id

    def get(self, operation_key: str) -> UploadReceipt | None:
        with PostgresStorageMetaRepository.in_transaction(self._transactions, self._workspace_id) as repository:
            return repository.get(operation_key)

    def save(self, receipt: UploadReceipt) -> None:
        with PostgresStorageMetaRepository.in_transaction(self._transactions, self._workspace_id) as repository:
            repository.save(receipt)


def _grant_ref(claims: GrantClaims | None) -> str:
    if claims is None:
        raise ActivityRejected(MISSING_EXECUTION_GRANT)
    return str(claims.grant_id)


def _register_output(repository: PostgresStorageMetaRepository, workspace_id: str, job_id: str, ref_id: str, source: Path) -> ArtifactVersion:
    if source.suffix.lower() != '.mp4':
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    sha256, size = _measure(source)
    if size == 0:
        raise _NotReady(ref_id, 'SOURCE_EMPTY')
    version = repository.find_version(workspace_id, ref_id, sha256)
    if version is None:
        values = {'workspace_id': workspace_id, 'artifact_id': ref_id, 'sha256_hash': sha256, 'size_bytes': size, 'mime_type': OUTPUT_MIME_TYPE, 'artifact_kind': OUTPUT_KIND, 'owner_ref': job_id, 'retention_ref': OUTPUT_RETENTION, 'sensitivity_ref': DEFAULT_SENSITIVITY}
        version = repository.insert_version(str(uuid.uuid4()), values) or repository.find_version(workspace_id, ref_id, sha256)
    if version is None:
        raise RuntimeError('VERSION_INSERT_FAILED')
    return version


def _stage_output(transactions: Any, root: Path, workspace_id: str, job_id: str, ref_id: str) -> ArtifactVersion | dict[str, Any]:
    with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
        try:
            source = _source_file(root, ref_id)
            if source is None:
                raise _NotReady(ref_id, 'SOURCE_MISSING')
            version = _register_output(repository, workspace_id, job_id, ref_id, source)
            _place_and_verify(repository, root, workspace_id, version, source)
        except _NotReady as exc:
            return {**_waiting(ARTIFACT_NOT_READY, 'the rendered video is missing or does not match its registered hash and size'), 'metrics': {'pending': [f'{exc.ref}={exc.reason}']}}
    return version


def _settle_cloud_location(transactions: Any, workspace_id: str, version: ArtifactVersion, namespace_ref: str, result: PersistResult, target: ArtifactLocationState) -> ArtifactLocation:
    with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
        location = repository.find_location(workspace_id, CLOUD_BACKEND, namespace_ref, result.object_id)
        if location is None:
            location = repository.insert_location(str(uuid.uuid4()), {'workspace_id': workspace_id, 'artifact_version_id': version.artifact_version_id, 'backend_ref': CLOUD_BACKEND, 'provider_namespace_ref': namespace_ref, 'provider_object_ref': result.object_id, 'logical_locator': result.object_id, 'logical_category': OUTPUT_KIND})
        if location is None:
            raise RuntimeError('LOCATION_INSERT_FAILED')
        if location.state is target:
            return location
        while location.state is not ArtifactLocationState.VERIFYING:
            following = _NEXT_STATE.get(location.state)
            if following is None:
                raise RuntimeError('LOCATION_STATE_' + location.state.value)
            location = _advance(repository, location, following)
        observed = (version.sha256_hash, version.size_bytes) if target is ArtifactLocationState.VERIFIED else None
        return _advance(repository, location, target, result.verification_evidence_ref, observed)


def _persist_to_cloud(persist: PersistArtifactToCloud, receipts: _CommittedReceipts, version: ArtifactVersion, namespace_ref: str, grant_ref: str) -> PersistResult:
    key = RECEIPT_KEY_PREFIX + version.artifact_version_id
    existing = receipts.get(key)
    if existing is not None and existing.state is not UploadReceiptState.VERIFIED:
        checked = persist.reconcile(key)
        if checked.state is not ArtifactLocationState.MISSING:
            return checked
    return persist.execute(version.artifact_version_id, version.sha256_hash, version.size_bytes, True, namespace_ref, key, grant_ref)


def _conclude(transactions: Any, workspace_id: str, version: ArtifactVersion, namespace_ref: str, result: PersistResult) -> dict[str, Any]:
    if result.state is ArtifactLocationState.VERIFIED:
        location = _settle_cloud_location(transactions, workspace_id, version, namespace_ref, result, ArtifactLocationState.VERIFIED)
        metrics = {'output_artifact_version_id': version.artifact_version_id, 'output_sha256': version.sha256_hash, 'cloud_location_id': location.location_id, 'cloud_location_verification_ref': location.verification_evidence_ref, 'upload_receipt_ref': result.operation_key, 'provider_namespace_ref': namespace_ref}
        return {'disposition': 'succeeded', 'output_refs': [{'ref_type': REF_OUTPUT_ARTIFACT, 'ref_id': version.artifact_version_id}, {'ref_type': REF_CLOUD_LOCATION, 'ref_id': location.location_id}], 'metrics': metrics}
    if result.state is ArtifactLocationState.CORRUPT:
        _settle_cloud_location(transactions, workspace_id, version, namespace_ref, result, ArtifactLocationState.CORRUPT)
        return _failed('CLOUD_OBJECT_CORRUPT', 'the cloud object does not match the registered hash and size')
    if result.state is ArtifactLocationState.OUTCOME_UNKNOWN:
        return _waiting(PROVIDER_UNAVAILABLE, 'the cloud object could not be verified yet')
    return _waiting(ARTIFACT_NOT_READY, 'the cloud object is not present yet')


def persist_video_output_handler(transactions: Any, *, workspace_id: str, staging_root: Path, cloud: CloudObjectPort, namespace_ref: str) -> Service:
    root = Path(staging_root)
    if not root.is_absolute():
        raise ValueError('staging_root must be an absolute Path')
    if not isinstance(namespace_ref, str) or not namespace_ref.strip():
        raise ValueError('namespace_ref must be a non-empty string')
    receipts = _CommittedReceipts(transactions, workspace_id)
    persist = PersistArtifactToCloud(cloud, receipts)

    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        job_id = _job_id(request)
        grant_ref = _grant_ref(claims)
        outputs = input_ref_ids(request, REF_RENDER_OUTPUT)
        if len(outputs) != 1:
            return _failed('PERSIST_INPUT_INVALID', 'PersistVideoOutput needs exactly one render_output input ref')
        root.mkdir(parents=True, exist_ok=True)
        staged = _stage_output(transactions, root, workspace_id, job_id, outputs[0])
        if isinstance(staged, dict):
            return staged
        try:
            result = _persist_to_cloud(persist, receipts, staged, namespace_ref, grant_ref)
        except DriveObjectStoreError as exc:
            if exc.code != DRIVE_CREDENTIAL_INVALID:
                raise
            return _waiting(CREDENTIAL_UNAVAILABLE, 'the cloud credential is not valid; the job waits until a valid credential is available')
        return _conclude(transactions, workspace_id, staged, namespace_ref, result)

    return service


__all__ = ['persist_video_output_handler']
