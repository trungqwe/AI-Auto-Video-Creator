"""PW-G7: handler ReserveVariant và CommitVideoCompletion (G); mỗi hàm trả dịch vụ (request, claims) -> outcome cho service_handler của composition root.

reserve_variant_handler bọc VariantReservationFlow; commit_video_completion_handler bọc CommitVideoCompletion qua PostgresCompletionUnitOfWork. Mỗi handler tự mượn connection từ TransactionManager; thông điệp lỗi là chuỗi cố định, không chứa văn bản ngoại lệ.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from controlplane.application.orchestration.commit_completion import CommitVideoCompletion, CompletionRejectedError
from controlplane.application.orchestration.completion_assembler import (
    REF_PRODUCTION_SNAPSHOT, REF_VARIANT_VALIDATION, CompletionAssembler, CompletionAssemblyError, input_ref_ids,
)
from controlplane.application.orchestration.variant_reservation_flow import ReserveVariantRequest, VariantReservationFlow
from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST, MISSING_EXECUTION_GRANT, ActivityRejected,
)
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.completion_gate import ALREADY_COMPLETED, GateAction
from controlplane.domain.orchestration.fencing import (
    GRANT_EXPIRED, GRANT_MISMATCH, INPUT_FINGERPRINT_MISMATCH, INVALID_EXPIRY, OPERATION_CONFLICT,
    STALE_EXECUTION_GENERATION, STALE_RECOVERY_EPOCH, GrantClaims,
)
from controlplane.domain.statemachine import JobState
from controlplane.infrastructure.db.orchestration.job_states import PostgresJobStates
from controlplane.infrastructure.db.orchestration.postgres_completion import (
    CompletionStoreError, PostgresCompletionUnitOfWork, PostgresMediaUsagePort,
)
from controlplane.infrastructure.db.orchestration.stage_runs import parse_stage_run_id
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry

REF_VARIANT_RESERVATION = 'variant_reservation'
REF_VIDEO_COMPLETION = 'video_completion'
RESERVE_STAGE = 'plan'
LATER_STAGES = ['render', 'qc', 'sync', 'complete']
STALE_CODES = frozenset({
    STALE_RECOVERY_EPOCH, STALE_EXECUTION_GENERATION, GRANT_MISMATCH, GRANT_EXPIRED, INVALID_EXPIRY,
    INPUT_FINGERPRINT_MISMATCH, OPERATION_CONFLICT,
})
Service = Callable[[Mapping[str, Any], GrantClaims | None], dict[str, Any]]

_JOB_EXISTS_SQL = 'SELECT 1 FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s'
_LATER_STAGE_SQL = 'SELECT 1 FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND job_id = %s AND stage_name = ANY(%s) LIMIT 1'
_PLAN_VALIDATION_SQL = (
    'SELECT record_key, revision, payload FROM controlplane.cp_variant_validations '
    "WHERE workspace_id = %s AND record_key = ANY(%s) AND payload->>'phase' = 'plan' ORDER BY revision DESC LIMIT 1"
)
_RELEASE_CAPACITY_SQL = (
    "UPDATE controlplane.cp_batch_capacity_reservations SET state = 'RELEASED' "
    "WHERE workspace_id = %s AND job_id = %s AND state = 'ACTIVE'"
)


def _outcome(disposition: str, code: str, message: str, retryable: bool) -> dict[str, Any]:
    return {'disposition': disposition, 'output_refs': [], 'problem': {'code': code, 'retryable': retryable, 'message': message}}


def _failed(code: str, message: str) -> dict[str, Any]:
    return _outcome('failed', code, message, False)


def _waiting(code: str, message: str) -> dict[str, Any]:
    return _outcome('waiting', code, message, True)


def _stale(code: str, message: str) -> dict[str, Any]:
    return _outcome('stale', code, message, True)


def _job_id(request: Mapping[str, Any]) -> str:
    job_id = request.get('video_job_id')
    if not isinstance(job_id, str) or not job_id.strip():
        raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
    return job_id


def _reserve(connection: Any, workspace_id: str, request: Mapping[str, Any], job_id: str) -> dict[str, Any]:
    if connection.execute(_JOB_EXISTS_SQL, (workspace_id, job_id)).fetchone() is None:
        return _failed('JOB_NOT_FOUND', 'the video job does not exist')
    if connection.execute(_LATER_STAGE_SQL, (workspace_id, job_id, LATER_STAGES)).fetchone() is not None:
        return _failed('RESERVE_AFTER_RENDER', 'ReserveVariant must run before render')
    keys = input_ref_ids(request, REF_VARIANT_VALIDATION)
    snapshots = input_ref_ids(request, REF_PRODUCTION_SNAPSHOT)
    if not keys or len(snapshots) != 1:
        return _failed('RESERVE_INPUT_MISSING', 'ReserveVariant needs a variant_validation and one production_snapshot')
    row = connection.execute(_PLAN_VALIDATION_SQL, (workspace_id, keys)).fetchone()
    if row is None:
        return _failed('RESERVE_INPUT_MISSING', 'no plan-phase validation was found')
    payload = row[2]
    if payload.get('valid') is not True:
        return _failed('VARIANT_VALIDATION_INVALID', 'the plan-phase validation is not valid')
    hashes = payload.get('input_hashes')
    reserve_request = ReserveVariantRequest(
        workspace_id=workspace_id,
        job_id=job_id,
        fingerprint=hashes.get('candidate') if isinstance(hashes, Mapping) else None,
        snapshot_scope=snapshots[0],
        validation_ref=f'{row[0]}:r{row[1]}',
        variation_policy_revision=payload.get('variation_policy_revision'),
        expected_registry_revision=payload.get('registry_revision'),
        idempotency_key=request.get('operation_key'),
    )
    try:
        receipt = VariantReservationFlow(PostgresVariantRegistry(connection)).reserve(reserve_request)
    except (TypeError, ValueError):
        return _failed('RESERVE_INPUT_INVALID', 'the reservation input is not valid')
    return {
        'disposition': 'succeeded',
        'output_refs': [{
            'ref_type': REF_VARIANT_RESERVATION,
            'ref_id': receipt.reservation_id,
            'revision_id': str(receipt.committed_registry_revision),
        }],
        'metrics': {'registry_revision': receipt.committed_registry_revision},
    }


def reserve_variant_handler(transactions: Any, *, workspace_id: str) -> Service:
    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        job_id = _job_id(request)
        try:
            _owner, stage, _revision = parse_stage_run_id(request.get('stage_run_id'))
        except OrchestrationContractError:
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST) from None
        if stage != RESERVE_STAGE:
            return _failed('RESERVE_OUT_OF_ORDER', 'ReserveVariant runs only in the plan stage')
        try:
            with transactions.borrow_connection() as connection:
                return _reserve(connection, workspace_id, request, job_id)
        except OrchestrationContractError as exc:
            if exc.code == 'VARIANT_CONFLICT':
                return _failed(exc.code, 'the job or fingerprint already has a different variant reservation')
            if exc.code == 'VARIANT_VALIDATION_STALE':
                return _waiting(exc.code, 'the variant registry changed; validate the plan again')
            raise

    return service


def _fail_and_release(transactions: Any, workspace_id: str, job_id: str) -> None:
    with transactions.borrow_connection() as connection:
        states = PostgresJobStates(connection, workspace_id)
        if states.state_of(job_id, lock=True) == JobState.READY_FOR_COMPLETION:
            states.transition(job_id, JobState.FAILED_FINAL)
        VariantReservationFlow(PostgresVariantRegistry(connection)).release(workspace_id, job_id, JobState.FAILED_FINAL)
        connection.execute(_RELEASE_CAPACITY_SQL, (workspace_id, job_id))


def commit_video_completion_handler(
    transactions: Any, *, workspace_id: str, clock: Callable[[], Any], usage_recorder: Any, assembler: Any = None,
) -> Service:
    built = assembler if assembler is not None else CompletionAssembler(workspace_id, clock)

    def service(request: Mapping[str, Any], claims: GrantClaims | None = None) -> dict[str, Any]:
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        job_id = _job_id(request)
        try:
            with transactions.borrow_connection() as connection:
                commit_request, context = built.assemble(connection, request, claims)
        except CompletionAssemblyError as exc:
            return (_waiting if exc.waiting else _failed)(exc.code, exc.message)
        uow = PostgresCompletionUnitOfWork(transactions, workspace_id, commit_request)
        usage = PostgresMediaUsagePort(uow, usage_recorder)
        try:
            result = CommitVideoCompletion(lambda: uow, usage).execute(commit_request, context)
        except CompletionRejectedError as exc:
            if exc.action == GateAction.FAIL_JOB_RELEASE:
                _fail_and_release(transactions, workspace_id, job_id)
                return _failed('VARIANT_CONFLICT', 'a confirmed duplicate variant ended the job and released its reservations')
            if exc.action == GateAction.KEEP_WAITING:
                return _waiting(exc.code, 'the variant registry changed; validate the output again')
            if exc.code in STALE_CODES:
                return _stale(exc.code, 'the execution grant is no longer current')
            return _failed(exc.code, 'the completion request was rejected')
        except CompletionStoreError as exc:
            return _failed(str(exc), 'the completion store rejected the write; nothing was committed')
        return {
            'disposition': 'succeeded',
            'output_refs': [{'ref_type': REF_VIDEO_COMPLETION, 'ref_id': str(result.ledger['completion_id'])}],
            'metrics': {'replayed': result.code == ALREADY_COMPLETED},
        }

    return service


__all__ = ['REF_VARIANT_RESERVATION', 'REF_VIDEO_COMPLETION', 'commit_video_completion_handler', 'reserve_variant_handler']
