"""PW-G7: CompletionAssembler dựng CommitVideoCompletionRequest và CompletionContext từ PostgreSQL thật (CT-ORC-008, CT-ORC-012, CT-AI-008; INV-003).

Grant hiện hành, execution_generation và recovery epoch đọc qua PostgresGrantStore và PostgresRecoveryEpoch trên connection của người gọi, không qua kho trong bộ nhớ. SQL đọc bảng của D, F, I là hằng ở đầu tệp (GIẢ ĐỊNH D8: chuyển sang adapter hạ tầng ở slice sau).
"""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from controlplane.application.orchestration.commit_completion import CompletionContext
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.fencing import (
    GRANT_MISMATCH, STALE_RECOVERY_EPOCH, FencingDecision, GrantClaims, evaluate_result_fencing,
)
from controlplane.infrastructure.db.orchestration.grants import PostgresGrantStore, PostgresRecoveryEpoch

REF_PRODUCTION_SNAPSHOT = 'production_snapshot'
REF_SCRIPT_VERSION = 'script_version'
REF_PRODUCTION_PLAN = 'production_plan'
REF_OUTPUT_METADATA = 'output_metadata'
REF_RENDER_ATTEMPT = 'render_attempt'
REF_QUALITY_REPORT = 'quality_report'
REF_VARIANT_VALIDATION = 'variant_validation'
REF_OUTPUT_ARTIFACT = 'output_artifact_version'
REF_CLOUD_LOCATION = 'cloud_location'
ARTIFACT_NOT_READY = 'artifact_not_ready'
OUTPUT_MIME_TYPE = 'video/mp4'


class CompletionAssemblyError(Exception):
    """A completion input is missing or unusable; waiting=True means the job waits instead of failing."""

    def __init__(self, code: str, message: str, *, waiting: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.waiting = waiting


_JOB_SQL = 'SELECT batch_id FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s'
_ARTIFACT_SQL = 'SELECT sha256_hash, mime_type FROM controlplane.cp_artifact_versions WHERE workspace_id = %s AND artifact_version_id = %s'
_LOCATION_SQL = (
    'SELECT artifact_version_id::text, state, observed_hash, verification_evidence_ref '
    'FROM controlplane.cp_artifact_locations WHERE workspace_id = %s AND location_id = %s'
)
_RESERVATION_SQL = 'SELECT reservation_id, state FROM controlplane.cp_variant_reservations WHERE workspace_id = %s AND job_id = %s'
_LEDGER_SQL = 'SELECT 1 FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s'
_VALIDATION_SQL = (
    'SELECT record_key, revision, payload FROM controlplane.cp_variant_validations '
    "WHERE workspace_id = %s AND record_key = ANY(%s) AND payload->>'phase' = 'output' AND payload->>'output_hash' = %s "
    'ORDER BY revision DESC LIMIT 1'
)
_QUALITY_SQL = (
    'SELECT payload FROM controlplane.cp_quality_reports '
    "WHERE workspace_id = %s AND record_key = %s AND payload->>'report_id' = %s ORDER BY revision DESC LIMIT 1"
)
_METADATA_SQL = 'SELECT max(revision) FROM controlplane.cp_output_metadata WHERE workspace_id = %s AND record_key = %s'
_SELECTION_SQL = (
    'SELECT payload FROM controlplane.cp_creative_selections WHERE workspace_id = %s AND job_id = %s '
    'ORDER BY selection_revision DESC LIMIT 1'
)
_SESSION_SQL = (
    'SELECT session_ref FROM controlplane.cp_app_sessions '
    "WHERE workspace_id = %s AND status = 'ACTIVE' ORDER BY started_at DESC, session_ref DESC LIMIT 1"
)


def input_ref_ids(request: Mapping[str, Any], ref_type: str) -> list[str]:
    refs = request.get('input_refs')
    found: list[str] = []
    for ref in refs if isinstance(refs, (list, tuple)) else ():
        ref_id = ref.get('ref_id') if isinstance(ref, Mapping) else None
        if isinstance(ref, Mapping) and ref.get('ref_type') == ref_type and isinstance(ref_id, str) and ref_id.strip() and ref_id not in found:
            found.append(ref_id)
    return found


def _one(request: Mapping[str, Any], ref_type: str) -> str:
    found = input_ref_ids(request, ref_type)
    if len(found) != 1:
        code = 'COMPLETION_INPUT_MISSING' if not found else 'COMPLETION_INPUT_AMBIGUOUS'
        raise CompletionAssemblyError(code, f'input_refs needs exactly one {ref_type}')
    return found[0]


def _uuid_text(value: str, ref_type: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise CompletionAssemblyError('COMPLETION_INPUT_INVALID', f'{ref_type} is not a UUID') from None


def _utc_text(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _manifest(selection: Mapping[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(asset: Any, role: str, **optional: Any) -> None:
        if isinstance(asset, str) and asset and (asset, role) not in seen:
            seen.add((asset, role))
            items.append({'media_asset_id': asset, 'role': role, **{k: v for k, v in optional.items() if isinstance(v, str) and v}})

    for item in selection.get('assignments') or ():
        if isinstance(item, Mapping):
            add(item.get('media_asset_id'), 'scene_media', rendition_ref=item.get('rendition_ref'), artifact_version_ref=item.get('artifact_version_ref'))
    for key in ('visual_hook', 'audio_hook', 'thumbnail'):
        ref = selection.get(key)
        if isinstance(ref, Mapping):
            add(ref.get('ref_id'), key)
    return items


class CompletionAssembler:
    def __init__(self, workspace_id: str, clock: Callable[[], datetime.datetime], *, audit_actor: str = 'system:orchestration', cleanup_policy_ref: str = 'cleanup-policy:default') -> None:
        self._workspace_id = workspace_id
        self._clock = clock
        self._audit_actor = audit_actor
        self._cleanup_policy_ref = cleanup_policy_ref

    def _row(self, connection: Any, sql: str, *params: Any) -> Any:
        return connection.execute(sql, (self._workspace_id, *params)).fetchone()

    def assemble(self, connection: Any, request: Mapping[str, Any], claims: GrantClaims) -> tuple[dict[str, Any], CompletionContext]:
        if not isinstance(claims, GrantClaims):
            raise TypeError('claims must be GrantClaims')
        job_id = request.get('video_job_id')
        if not isinstance(job_id, str) or not job_id.strip():
            raise CompletionAssemblyError('COMPLETION_INPUT_MISSING', 'video_job_id is required')
        job = self._row(connection, _JOB_SQL, job_id)
        if job is None:
            raise CompletionAssemblyError('JOB_NOT_FOUND', 'the video job does not exist')
        artifact_id = _uuid_text(_one(request, REF_OUTPUT_ARTIFACT), REF_OUTPUT_ARTIFACT)
        sha = self._artifact_hash(connection, artifact_id)
        location_id = _uuid_text(_one(request, REF_CLOUD_LOCATION), REF_CLOUD_LOCATION)
        evidence = self._verified_evidence(connection, location_id, artifact_id, sha)
        reservation_id = self._reservation(connection, job_id)
        validation_ref, expected_revision, conflict = self._output_validation(connection, request, sha)
        attempt_id = _one(request, REF_RENDER_ATTEMPT)
        report_id = self._quality(connection, attempt_id, _one(request, REF_QUALITY_REPORT))
        metadata_ref = _one(request, REF_OUTPUT_METADATA)
        metadata_revision = self._metadata_revision(connection, metadata_ref)
        preset, manifest = self._selection(connection, job_id)
        commit_request = {
            'video_job_id': job_id,
            'snapshot_ref': _one(request, REF_PRODUCTION_SNAPSHOT),
            'script_version_ref': _one(request, REF_SCRIPT_VERSION),
            'production_plan_ref': _one(request, REF_PRODUCTION_PLAN),
            'render_attempt_ref': attempt_id,
            'quality_report_ref': report_id,
            'output_artifact_version_id': artifact_id,
            'output_sha256': sha,
            'cloud_location_verification_ref': evidence,
            'output_metadata_revision': metadata_revision,
            'variant_validation_ref': validation_ref,
            'variant_reservation_id': reservation_id,
            'expected_variant_registry_revision': expected_revision,
            'media_usage_manifest': manifest,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
        }
        session = self._row(connection, _SESSION_SQL)
        context = CompletionContext(
            completion_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f'completion:{self._workspace_id}:{job_id}')),
            batch_ref=str(job[0]),
            session_ref=str(session[0]) if session is not None else claims.worker_lease_id,
            cloud_location_ref=location_id,
            preset_revision_ref=preset,
            output_naming_metadata={'output_metadata_ref': metadata_ref, 'output_metadata_revision': metadata_revision},
            cost_usage_summary={},
            audit_actor=self._audit_actor,
            cleanup_policy_ref=self._cleanup_policy_ref,
            completed_at=_utc_text(self._clock()),
            fencing=self._fencing(connection, claims),
            variant_conflict_confirmed=conflict,
        )
        return commit_request, context

    def _artifact_hash(self, connection: Any, artifact_id: str) -> str:
        row = self._row(connection, _ARTIFACT_SQL, artifact_id)
        if row is None:
            raise CompletionAssemblyError('OUTPUT_ARTIFACT_MISSING', 'the output artifact version does not exist')
        if row[1] != OUTPUT_MIME_TYPE:
            raise CompletionAssemblyError('OUTPUT_ARTIFACT_INVALID', 'the output artifact is not an mp4')
        return str(row[0])

    def _verified_evidence(self, connection: Any, location_id: str, artifact_id: str, sha: str) -> str:
        row = self._row(connection, _LOCATION_SQL, location_id)
        if row is None or row[0] != artifact_id:
            raise CompletionAssemblyError('LOCATION_MISMATCH', 'the location does not belong to the output artifact')
        if row[1] != 'VERIFIED':
            raise CompletionAssemblyError(ARTIFACT_NOT_READY, 'the cloud location is not VERIFIED yet', waiting=True)
        if row[2] != sha:
            raise CompletionAssemblyError('LOCATION_HASH_MISMATCH', 'the observed hash differs from the artifact hash')
        if not isinstance(row[3], str) or not row[3].strip():
            raise CompletionAssemblyError(ARTIFACT_NOT_READY, 'the cloud location has no verification evidence', waiting=True)
        return row[3]

    def _reservation(self, connection: Any, job_id: str) -> str:
        row = self._row(connection, _RESERVATION_SQL, job_id)
        if row is None:
            raise CompletionAssemblyError('RESERVATION_MISSING', 'the job has no variant reservation')
        if row[1] == 'ACTIVE' or (row[1] == 'CONVERTED' and self._row(connection, _LEDGER_SQL, job_id) is not None):
            return str(row[0])
        raise CompletionAssemblyError('RESERVATION_NOT_ACTIVE', 'the variant reservation is not ACTIVE')

    def _output_validation(self, connection: Any, request: Mapping[str, Any], sha: str) -> tuple[str, int, bool]:
        keys = input_ref_ids(request, REF_VARIANT_VALIDATION)
        if not keys:
            raise CompletionAssemblyError('COMPLETION_INPUT_MISSING', 'input_refs needs a variant_validation')
        row = self._row(connection, _VALIDATION_SQL, keys, sha)
        if row is None:
            raise CompletionAssemblyError('VARIANT_VALIDATION_UNAVAILABLE', 'no output-phase validation matches the exact output hash', waiting=True)
        revision = row[2].get('registry_revision')
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise CompletionAssemblyError('VARIANT_VALIDATION_INVALID_RECORD', 'the validation has no registry_revision')
        return f'{row[0]}:r{row[1]}', revision, row[2].get('valid') is False

    def _quality(self, connection: Any, attempt_id: str, report_id: str) -> str:
        row = self._row(connection, _QUALITY_SQL, attempt_id, report_id)
        if row is None:
            raise CompletionAssemblyError('QUALITY_REPORT_MISSING', 'the quality report does not belong to the render attempt')
        if row[0].get('passed') is not True:
            raise CompletionAssemblyError('QUALITY_REPORT_NOT_PASSED', 'the quality report did not pass')
        return report_id

    def _metadata_revision(self, connection: Any, metadata_ref: str) -> str:
        row = self._row(connection, _METADATA_SQL, metadata_ref)
        if row is None or row[0] is None:
            raise CompletionAssemblyError('OUTPUT_METADATA_MISSING', 'the output metadata has no stored revision')
        return str(row[0])

    def _selection(self, connection: Any, job_id: str) -> tuple[str, list[dict[str, str]]]:
        row = self._row(connection, _SELECTION_SQL, job_id)
        if row is None:
            raise CompletionAssemblyError('SELECTION_MISSING', 'the job has no stored creative selection')
        preset = row[0].get('preset_registry_revision')
        manifest = _manifest(row[0])
        if not isinstance(preset, str) or not preset.strip() or not manifest:
            raise CompletionAssemblyError('SELECTION_INVALID', 'the selection has no preset revision or no media usage')
        return preset, manifest

    def _fencing(self, connection: Any, claims: GrantClaims) -> FencingDecision:
        now = self._clock()
        grants = PostgresGrantStore(connection, self._workspace_id)
        try:
            epoch = PostgresRecoveryEpoch(connection, self._workspace_id).current()
        except OrchestrationContractError:
            return FencingDecision(False, STALE_RECOVERY_EPOCH)
        claimed = {
            'recovery_epoch': claims.recovery_epoch,
            'execution_generation': claims.execution_generation,
            'grant_id': claims.grant_id,
            'stage_run_id': claims.stage_run_id,
        }
        decision = evaluate_result_fencing(
            claims, grants.latest_generation(claims.stage_run_id), epoch, claimed, claims.input_fingerprint, now, False,
        )
        if decision.accepted and grants.active_grant(claims.stage_run_id, now) != claims:
            return FencingDecision(False, GRANT_MISMATCH)
        return decision


__all__ = [
    'ARTIFACT_NOT_READY', 'CompletionAssembler', 'CompletionAssemblyError', 'REF_CLOUD_LOCATION', 'REF_OUTPUT_ARTIFACT',
    'REF_OUTPUT_METADATA', 'REF_PRODUCTION_PLAN', 'REF_PRODUCTION_SNAPSHOT', 'REF_QUALITY_REPORT', 'REF_RENDER_ATTEMPT',
    'REF_SCRIPT_VERSION', 'REF_VARIANT_VALIDATION', 'input_ref_ids',
]
