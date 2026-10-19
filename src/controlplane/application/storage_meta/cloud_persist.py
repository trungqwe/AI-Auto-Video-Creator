"""I-04: upload idempotent lên cloud và reconcile OUTCOME_UNKNOWN (CT-STO-003 bước 1-3, ADR-0006)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta.verification import IntegrityObservation, evaluate_integrity


class ObjectAlreadyExistsError(Exception):
    '''Cloud trả 409: object_id đã tồn tại.'''


class UploadReceiptState(StrEnum):
    PREPARED = 'PREPARED'
    VERIFIED = 'VERIFIED'
    CORRUPT = 'CORRUPT'
    MISSING = 'MISSING'
    OUTCOME_UNKNOWN = 'OUTCOME_UNKNOWN'


@dataclass(frozen=True)
class UploadReceipt:
    operation_key: str
    artifact_version_id: str
    content_sha256: str
    size_bytes: int
    object_id: str
    state: UploadReceiptState = UploadReceiptState.PREPARED
    verification_evidence_ref: str | None = None


@dataclass(frozen=True)
class PersistResult:
    operation_key: str
    object_id: str
    state: ArtifactLocationState
    verification_evidence_ref: str | None


class CloudObjectPort(Protocol):
    def reserve_object_id(self, namespace_ref: str) -> str: ...
    def upload(self, object_id: str, artifact_version_id: str, content_sha256: str, size_bytes: int) -> None: ...
    def lookup(self, object_id: str) -> IntegrityObservation: ...


class UploadReceiptPort(Protocol):
    def get(self, operation_key: str) -> UploadReceipt | None: ...
    def save(self, receipt: UploadReceipt) -> None: ...


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


class PersistArtifactToCloud:
    def __init__(self, cloud: CloudObjectPort, receipts: UploadReceiptPort) -> None:
        self._cloud = cloud
        self._receipts = receipts

    def execute(
        self,
        artifact_version_id: str,
        content_sha256: str,
        size_bytes: int,
        source_verified: bool,
        namespace_ref: str,
        operation_key: str,
        grant_ref: str,
    ) -> PersistResult:
        if source_verified is not True:
            raise PermissionError('source location must be verified before cloud persist')
        if not isinstance(grant_ref, str) or not grant_ref.strip():
            raise PermissionError('execution grant is required')
        _require_text(artifact_version_id, 'artifact_version_id')
        _require_text(namespace_ref, 'namespace_ref')
        _require_text(operation_key, 'operation_key')
        # Chỉ kiểm định dạng sha256/size: evaluate_integrity raise ValueError khi sai.
        evaluate_integrity(content_sha256, size_bytes, IntegrityObservation(None, None, None, None))
        receipt = self._receipts.get(operation_key)
        if receipt is None:
            object_id = _require_text(self._cloud.reserve_object_id(namespace_ref), 'object_id')
            receipt = UploadReceipt(operation_key, artifact_version_id, content_sha256, size_bytes, object_id)
            self._receipts.save(receipt)
        elif (receipt.artifact_version_id, receipt.content_sha256, receipt.size_bytes) != (artifact_version_id, content_sha256, size_bytes):
            raise ValueError('operation_key was already used with different content')
        elif receipt.state is UploadReceiptState.VERIFIED:
            return self._result(receipt)
        try:
            self._cloud.upload(receipt.object_id, artifact_version_id, content_sha256, size_bytes)
        except TimeoutError:
            return self._record(receipt, ArtifactLocationState.OUTCOME_UNKNOWN, None)
        except ObjectAlreadyExistsError:
            pass
        return self._verify(receipt)

    def reconcile(self, operation_key: str) -> PersistResult:
        receipt = self._receipts.get(operation_key)
        if receipt is None:
            raise LookupError('upload receipt not found')
        return self._verify(receipt)

    def _verify(self, receipt: UploadReceipt) -> PersistResult:
        try:
            observation = self._cloud.lookup(receipt.object_id)
        except TimeoutError:
            return self._record(receipt, ArtifactLocationState.OUTCOME_UNKNOWN, None)
        outcome = evaluate_integrity(receipt.content_sha256, receipt.size_bytes, observation)
        evidence = observation.evidence_ref if outcome is ArtifactLocationState.VERIFIED else None
        return self._record(receipt, outcome, evidence)

    def _record(self, receipt: UploadReceipt, outcome: ArtifactLocationState, evidence: str | None) -> PersistResult:
        updated = replace(receipt, state=UploadReceiptState(outcome.value), verification_evidence_ref=evidence)
        self._receipts.save(updated)
        return self._result(updated)

    @staticmethod
    def _result(receipt: UploadReceipt) -> PersistResult:
        outcome = ArtifactLocationState(receipt.state.value)
        evidence = receipt.verification_evidence_ref if outcome is ArtifactLocationState.VERIFIED else None
        return PersistResult(receipt.operation_key, receipt.object_id, outcome, evidence)


__all__ = [
    'CloudObjectPort',
    'ObjectAlreadyExistsError',
    'PersistArtifactToCloud',
    'PersistResult',
    'UploadReceipt',
    'UploadReceiptPort',
    'UploadReceiptState',
]
