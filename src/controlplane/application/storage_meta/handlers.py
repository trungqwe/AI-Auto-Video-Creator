"""PW-I1: handler MaterializeArtifactSet, ReconcileStorage và RequestCleanupEvaluation (I); mỗi hàm trả dịch vụ (request, claims) -> outcome cho service_handler của composition root.

materialize_artifact_set_handler đăng ký version, đặt bản local phẳng <staging>/<artifact_version_id> rồi ghi location DECLARED -> VERIFIED với hash và size đo thật từ tệp. reconcile_storage_handler bọc reconcile(); request_cleanup_evaluation_handler bọc evaluate_cleanup() và không bao giờ cấp authorization. Mỗi handler tự mượn connection qua PostgresStorageMetaRepository.in_transaction; thông điệp lỗi là chuỗi cố định, không chứa văn bản ngoại lệ hay đường dẫn.

GIẢ ĐỊNH (D8): input_refs của MaterializeArtifactSet gồm artifact_source (ref_id là đường dẫn tương đối dưới staging root, ví dụ voice/line.wav) và artifact_version (UUID đã đăng ký, chỉ kiểm lại); version mới có retention_ref per_video và sensitivity_ref internal; khi request không có artifact_source và artifact_version thì dẫn xuất mỗi ref voice_artifact thành artifact_source voice/<ref_id> và mỗi revision_id của ref selected_media thành artifact_version; register_staged_artifact đăng ký tệp staging với retention_ref do bên gọi chọn (ảnh dùng durable) và verified_version_for_sha tìm version media/<sha256>.<ext> có location local VERIFIED (mặc định thử hậu tố ảnh STAGED_IMAGE_EXTENSIONS; hook video hoặc âm thanh truyền extensions=STAGED_HOOK_EXTENSIONS); tệp .ass do F ghi và đưa vào manifest riêng (with_ass_entry) nên handler này không đăng ký; location VERIFIED không bao giờ bị ghi lại, nên tệp bị sửa sau khi đăng ký luôn bị từ chối.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from controlplane.application.orchestration.completion_assembler import ARTIFACT_NOT_READY, input_ref_ids
from controlplane.application.orchestration.workflows.activities import INVALID_ACTIVITY_REQUEST, MISSING_EXECUTION_GRANT, ActivityRejected
from controlplane.application.storage_meta.cleanup_evaluation import CleanupEvaluationRequest, evaluate_cleanup
from controlplane.application.storage_meta.reconciliation import CloudLocationRecord, CloudObjectObservation, ReconcileSnapshot, VersionRecord, reconcile
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.statemachine import ArtifactLocationState, transition_artifact_location
from controlplane.domain.storage_meta import ArtifactLocation, ArtifactVersion
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository


REF_ARTIFACT_SOURCE = 'artifact_source'
REF_ARTIFACT_VERSION = 'artifact_version'
REF_ARTIFACT_SET = 'artifact_set'
REF_ARTIFACT_LOCATION = 'artifact_location'
REF_VIDEO_COMPLETION = 'video_completion'
REF_SUPERSEDED_STAGE = 'superseded_stage'
REF_RECONCILE_REPORT = 'storage_reconcile_report'
REF_CLEANUP_EVALUATION = 'cleanup_evaluation'
LOCAL_BACKEND = 'local-staging'
LOCAL_NAMESPACE = 'staging'
CLOUD_BACKEND = 'cloud'
LOCAL_STORAGE_CLASS = 'local_staging'
TRANSIENT_RETENTION = 'per_video'
DEFAULT_SENSITIVITY = 'internal'
_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
_MIME_BY_SUFFIX = {'.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
_KIND_BY_ROOT = {'voice': 'voice_track', 'media': 'render_input_media'}
_DEFAULT_KIND = 'render_input'
VOICE_ROOT = 'voice'
VOICE_WAV_MIME = 'audio/wav'
REF_VOICE_ARTIFACT = 'voice_artifact'
REF_SELECTED_MEDIA = 'selected_media'
STAGED_IMAGE_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp')
STAGED_HOOK_EXTENSIONS = ('mp4', 'mov', 'webm', 'wav', 'mp3', 'm4a')
_SHA256 = re.compile(r'[0-9a-f]{64}')
Service = Callable[[Mapping[str, Any], GrantClaims | None], dict[str, Any]]


def _outcome(disposition: str, code: str, message: str, retryable: bool) -> dict[str, Any]:
    return {'disposition': disposition, 'output_refs': [], 'problem': {'code': code, 'retryable': retryable, 'message': message}}


def _failed(code: str, message: str) -> dict[str, Any]:
    return _outcome('failed', code, message, False)


def _waiting(code: str, message: str) -> dict[str, Any]:
    return _outcome('waiting', code, message, True)


def _job_id(request: Mapping[str, Any]) -> str:
    job_id = request.get('video_job_id')
    if not isinstance(job_id, str) or not job_id.strip():
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    return job_id


def _uuid_text(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST) from None


def _claims_epoch(claims: GrantClaims | None) -> str:
    if claims is None:
        raise ActivityRejected(MISSING_EXECUTION_GRANT)
    return str(claims.recovery_epoch)


class _NotReady(Exception):
    def __init__(self, ref: str, reason: str) -> None:
        super().__init__(reason)
        self.ref = ref
        self.reason = reason


def _measure(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _source_file(root: Path, ref_id: str) -> Path | None:
    parts = ref_id.split('/')
    if not all(_NAME.fullmatch(part) for part in parts):
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    candidate = (root / Path(*parts)).resolve()
    if root.resolve() not in candidate.parents:
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    return candidate if candidate.is_file() else None


def _advance(repository: PostgresStorageMetaRepository, location: ArtifactLocation, target: ArtifactLocationState, evidence: str | None = None, observed: tuple[str, int] | None = None) -> ArtifactLocation:
    transition_artifact_location(current_state=location.state, current_revision=location.revision, expected_revision=location.revision, requested_state=target)
    observed_hash, observed_size = observed if observed is not None else (None, None)
    updated = repository.update_location(location, location.revision, target, evidence, observed_hash, observed_size)
    if updated is None:
        raise RuntimeError('LOCATION_REVISION_CONFLICT')
    return updated


def _entry(version: ArtifactVersion) -> dict[str, Any]:
    return {'artifact_version_id': version.artifact_version_id, 'local_ref': version.artifact_version_id, 'sha256': version.sha256_hash, 'size_bytes': version.size_bytes}


def _local_location(repository: PostgresStorageMetaRepository, workspace_id: str, version: ArtifactVersion) -> ArtifactLocation:
    version_id = version.artifact_version_id
    location = repository.find_location(workspace_id, LOCAL_BACKEND, LOCAL_NAMESPACE, version_id)
    if location is None:
        location = repository.insert_location(str(uuid.uuid4()), {'workspace_id': workspace_id, 'artifact_version_id': version_id, 'backend_ref': LOCAL_BACKEND, 'provider_namespace_ref': LOCAL_NAMESPACE, 'provider_object_ref': version_id, 'logical_locator': version_id, 'logical_category': 'render_input'}) or repository.find_location(workspace_id, LOCAL_BACKEND, LOCAL_NAMESPACE, version_id)
    if location is None:
        raise RuntimeError('LOCATION_INSERT_FAILED')
    return location


def _place_and_verify(repository: PostgresStorageMetaRepository, root: Path, workspace_id: str, version: ArtifactVersion, source: Path | None) -> dict[str, Any]:
    version_id = version.artifact_version_id
    dest = root / version_id
    location = _local_location(repository, workspace_id, version)
    expected = (version.sha256_hash, version.size_bytes)
    if location.state is ArtifactLocationState.VERIFIED:
        if not dest.is_file() or _measure(dest) != expected or (location.observed_hash, location.observed_size_bytes) != expected:
            raise _NotReady(version_id, 'LOCAL_COPY_MISMATCH')
        return _entry(version)
    if location.state not in (ArtifactLocationState.DECLARED, ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING):
        raise _NotReady(version_id, 'LOCATION_STATE_' + location.state.value)
    if source is None:
        raise _NotReady(version_id, 'SOURCE_MISSING')
    temp = root / f'.{version_id}.{uuid.uuid4().hex}.part'
    shutil.copyfile(source, temp)
    temp.replace(dest)
    following = {ArtifactLocationState.DECLARED: ArtifactLocationState.MATERIALIZING, ArtifactLocationState.MATERIALIZING: ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.AVAILABLE_UNVERIFIED: ArtifactLocationState.VERIFYING}
    while location.state is not ArtifactLocationState.VERIFYING:
        location = _advance(repository, location, following[location.state])
    measured = _measure(dest)
    if measured != expected:
        _advance(repository, location, ArtifactLocationState.CORRUPT, 'local-measure-mismatch')
        raise _NotReady(version_id, 'LOCAL_COPY_MISMATCH')
    _advance(repository, location, ArtifactLocationState.VERIFIED, 'local-measure/' + version_id, measured)
    return _entry(version)


def _register(repository: PostgresStorageMetaRepository, workspace_id: str, job_id: str, ref_id: str, source: Path, retention_ref: str = TRANSIENT_RETENTION) -> ArtifactVersion:
    root_name = ref_id.split('/')[0] if '/' in ref_id else ''
    mime_type = _MIME_BY_SUFFIX.get(source.suffix.lower())
    if mime_type is None and root_name == VOICE_ROOT and source.suffix == '':
        mime_type = VOICE_WAV_MIME
    if mime_type is None:
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    sha256, size = _measure(source)
    if size == 0:
        raise _NotReady(ref_id, 'SOURCE_EMPTY')
    version = repository.find_version(workspace_id, ref_id, sha256)
    if version is None:
        values = {'workspace_id': workspace_id, 'artifact_id': ref_id, 'sha256_hash': sha256, 'size_bytes': size, 'mime_type': mime_type, 'artifact_kind': _KIND_BY_ROOT.get(root_name, _DEFAULT_KIND), 'owner_ref': job_id, 'retention_ref': retention_ref, 'sensitivity_ref': DEFAULT_SENSITIVITY}
        version = repository.insert_version(str(uuid.uuid4()), values) or repository.find_version(workspace_id, ref_id, sha256)
    if version is None:
        raise RuntimeError('VERSION_INSERT_FAILED')
    return version


def _derived_inputs(request: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    sources = [f'{VOICE_ROOT}/{ref_id}' for ref_id in input_ref_ids(request, REF_VOICE_ARTIFACT)]
    registered: list[str] = []
    refs = request.get('input_refs')
    for ref in refs if isinstance(refs, (list, tuple)) else ():
        if not isinstance(ref, Mapping) or ref.get('ref_type') != REF_SELECTED_MEDIA:
            continue
        revision_id = ref.get('revision_id')
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
        version_id = _uuid_text(revision_id)
        if version_id not in registered:
            registered.append(version_id)
    return sources, registered


def _materialize(repository: PostgresStorageMetaRepository, root: Path, workspace_id: str, request: Mapping[str, Any], job_id: str) -> dict[str, Any]:
    sources = input_ref_ids(request, REF_ARTIFACT_SOURCE)
    registered = input_ref_ids(request, REF_ARTIFACT_VERSION)
    if not sources and not registered:
        sources, registered = _derived_inputs(request)
    if not sources and not registered:
        return _failed('MATERIALIZE_INPUT_MISSING', 'MaterializeArtifactSet needs artifact_source or artifact_version input refs')
    manifest: list[dict[str, Any]] = []
    pending: list[str] = []
    artifact_ids: dict[str, str] = {}
    for ref_id in [*sources, *registered]:
        try:
            if ref_id in sources:
                source = _source_file(root, ref_id)
                if source is None:
                    raise _NotReady(ref_id, 'SOURCE_MISSING')
                version = _register(repository, workspace_id, job_id, ref_id, source)
                entry = _place_and_verify(repository, root, workspace_id, version, source)
            else:
                version = repository.get_version(workspace_id, _uuid_text(ref_id))
                if version is None:
                    raise _NotReady(ref_id, 'VERSION_UNKNOWN')
                entry = _place_and_verify(repository, root, workspace_id, version, None)
        except _NotReady as exc:
            pending.append(f'{exc.ref}={exc.reason}')
            continue
        if entry not in manifest:
            manifest.append(entry)
            artifact_ids[entry['artifact_version_id']] = version.artifact_id
    if pending:
        return {**_waiting(ARTIFACT_NOT_READY, 'some artifacts are missing or do not match their registered hash and size'), 'metrics': {'pending': pending}}
    return {'disposition': 'succeeded', 'output_refs': [{'ref_type': REF_ARTIFACT_SET, 'ref_id': request.get('operation_key')}, *({'ref_type': REF_ARTIFACT_VERSION, 'ref_id': item['artifact_version_id'], 'source_ref_id': artifact_ids[item['artifact_version_id']]} for item in manifest)], 'metrics': {'materialization_manifest': manifest, 'artifact_count': len(manifest), 'total_bytes': sum(item['size_bytes'] for item in manifest)}}


def register_staged_artifact(transactions: Any, *, workspace_id: str, staging_root: Path, owner_ref: str, relative_ref: str, retention_ref: str) -> ArtifactVersion:
    root = Path(staging_root)
    if not root.is_absolute():
        raise ValueError('staging_root must be an absolute Path')
    suffix = Path(relative_ref).suffix
    if suffix != suffix.lower():
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    pending: str | None = None
    with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
        try:
            source = _source_file(root, relative_ref)
            if source is None:
                raise _NotReady(relative_ref, 'SOURCE_MISSING')
            version = _register(repository, workspace_id, owner_ref, relative_ref, source, retention_ref)
            _place_and_verify(repository, root, workspace_id, version, source)
        except _NotReady as exc:
            pending = exc.reason
    if pending is not None:
        raise RuntimeError('STAGED_ARTIFACT_NOT_READY:' + pending)
    return version


def verified_version_for_sha(transactions: Any, *, workspace_id: str, sha256: str, extensions: tuple[str, ...] = STAGED_IMAGE_EXTENSIONS) -> ArtifactVersion | None:
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        return None
    with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
        for extension in extensions:
            version = repository.find_version(workspace_id, f'media/{sha256}.{extension}', sha256)
            if version is None:
                continue
            for location in repository.list_version_locations(workspace_id, version.artifact_version_id):
                if location.backend_ref == LOCAL_BACKEND and location.provider_namespace_ref == LOCAL_NAMESPACE and location.state is ArtifactLocationState.VERIFIED and location.observed_hash == sha256:
                    return version
    return None


def materialize_artifact_set_handler(transactions: Any, *, workspace_id: str, staging_root: Path) -> Service:
    root = Path(staging_root)
    if not root.is_absolute():
        raise ValueError('staging_root must be an absolute Path')

    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        job_id = _job_id(request)
        root.mkdir(parents=True, exist_ok=True)
        with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
            return _materialize(repository, root, workspace_id, request, job_id)

    return service


def reconcile_storage_handler(transactions: Any, *, workspace_id: str, observe: Callable[[str], CloudObjectObservation | None], backend_ref: str = CLOUD_BACKEND) -> Service:
    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        epoch = _claims_epoch(claims)
        with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
            locations = [item for item in repository.list_backend_locations(workspace_id, backend_ref) if item.state is not ArtifactLocationState.DELETED]
            versions = repository.list_versions(workspace_id, sorted({item.artifact_version_id for item in locations}))
        observations = [found for found in (observe(item.provider_object_ref) for item in locations) if found is not None]
        snapshot = ReconcileSnapshot(
            current_recovery_epoch=epoch,
            versions=tuple(VersionRecord(item.artifact_version_id, item.sha256_hash, item.size_bytes) for item in versions),
            cloud_locations=tuple(CloudLocationRecord(item.location_id, item.artifact_version_id, item.provider_object_ref) for item in locations),
            cloud_objects=tuple(observations),
        )
        report = [{'code': finding.code.value, 'ref': finding.ref} for finding in reconcile(snapshot)]
        outcome: dict[str, Any] = {'disposition': 'succeeded', 'output_refs': [{'ref_type': REF_RECONCILE_REPORT, 'ref_id': request.get('operation_key')}], 'metrics': {'checked_locations': len(locations), 'finding_count': len(report), 'findings': report}}
        if report:
            outcome['warnings'] = [f"{item['code']}:{item['ref']}" for item in report]
        return outcome

    return service


def request_cleanup_evaluation_handler(transactions: Any, *, workspace_id: str) -> Service:
    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        request_epoch = _claims_epoch(claims)
        locations = input_ref_ids(request, REF_ARTIFACT_LOCATION)
        if len(locations) != 1:
            return _failed('CLEANUP_INPUT_INVALID', 'RequestCleanupEvaluation needs exactly one artifact_location input ref')
        location_id = _uuid_text(locations[0])
        completions = input_ref_ids(request, REF_VIDEO_COMPLETION)
        superseded = input_ref_ids(request, REF_SUPERSEDED_STAGE)
        with PostgresStorageMetaRepository.in_transaction(transactions, workspace_id) as repository:
            location = repository.get_location(workspace_id, location_id)
            if location is None:
                return _failed('LOCATION_NOT_FOUND', 'the artifact location does not exist in this workspace')
            version = repository.get_version(workspace_id, location.artifact_version_id)
            current_epoch = repository.current_recovery_epoch(workspace_id)
            if version is None or current_epoch is None:
                return _failed('CLEANUP_CONTEXT_UNAVAILABLE', 'the artifact version or the active recovery epoch is missing')
            fields = repository.get_location_fields(workspace_id, location_id)
            lease = repository.get_lease(fields.lease_ref) if fields is not None and fields.lease_ref else None
            siblings = repository.list_version_locations(workspace_id, location.artifact_version_id)
        cloud_verified = any(item.backend_ref == CLOUD_BACKEND and item.state is ArtifactLocationState.VERIFIED and item.verification_evidence_ref is not None and item.observed_hash in (None, version.sha256_hash) for item in siblings)
        evaluation = evaluate_cleanup(CleanupEvaluationRequest(
            storage_class=LOCAL_STORAGE_CLASS if location.backend_ref == LOCAL_BACKEND else location.backend_ref,
            location_state=location.state,
            retention_class=version.retention_ref,
            cloud_copy_verified=cloud_verified,
            active_lease=lease is not None and lease.state == 'ACTIVE',
            completion_ref=completions[0] if completions else None,
            superseded_ref=superseded[0] if superseded else None,
            request_recovery_epoch=request_epoch,
            current_recovery_epoch=current_epoch,
        ))
        return {'disposition': 'succeeded', 'output_refs': [{'ref_type': REF_CLEANUP_EVALUATION, 'ref_id': location_id}], 'metrics': {'decision': evaluation.decision, 'reason_codes': list(evaluation.reason_codes), 'authorization_issued': False}}

    return service


__all__ = ['materialize_artifact_set_handler', 'reconcile_storage_handler', 'register_staged_artifact', 'request_cleanup_evaluation_handler', 'verified_version_for_sha']
