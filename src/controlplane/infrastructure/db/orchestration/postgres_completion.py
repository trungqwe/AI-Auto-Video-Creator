"""CP-5-COMPLETION: completion unit of work trên PostgreSQL (CT-ORC-008; INV-010, INV-017)."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
import uuid

from psycopg.types.json import Jsonb

from controlplane.application.orchestration.commit_completion import (
    CompletionUnitOfWork,
    JobRecord,
)
from controlplane.domain.events import DomainEvent
from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration.completion_gate import ReservationBinding
from controlplane.domain.statemachine import JobState
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository


class CompletionStoreError(RuntimeError):
    pass


_LEDGER_KEYS = (
    'completion_id',
    'video_job_id',
    'batch_ref',
    'session_ref',
    'output_artifact_version_id',
    'output_sha256',
    'cloud_location_ref',
    'snapshot_ref',
    'script_version_ref',
    'production_plan_ref',
    'preset_revision_ref',
    'quality_report_ref',
    'variant_validation_ref',
    'media_usage_manifest',
    'completed_at',
    'output_naming_metadata',
    'cost_usage_summary',
    'audit_actor',
    'cleanup_policy_ref',
)

_LEDGER_SELECT = (
    'SELECT completion_id, job_id, batch_id, session_ref, output_artifact_version_id::text, '
    'output_artifact_hash, cloud_location_ref, snapshot_ref, script_version_ref, '
    'production_plan_ref, preset_revision_ref, quality_report_ref, variant_validation_ref, '
    'media_usage_manifest, completed_at, output_naming_metadata, cost_usage_summary, '
    'actor_ref, cleanup_policy_ref '
    'FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s'
)

_JOB_SELECT = (
    'SELECT status, revision FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s FOR UPDATE'
)

_RESERVATION_SELECT = (
    'SELECT r.reservation_id, r.job_id, r.state, a.sha256_hash '
    'FROM controlplane.cp_variant_reservations r '
    'LEFT JOIN controlplane.cp_artifact_versions a ON a.workspace_id = r.workspace_id AND a.artifact_version_id = %s '
    'WHERE r.workspace_id = %s AND r.reservation_id = %s'
)

_LEDGER_COLUMNS = (
    'ledger_id',
    'workspace_id',
    'job_id',
    'batch_id',
    'capacity_reservation_id',
    'variant_reservation_id',
    'output_artifact_version_id',
    'output_artifact_hash',
    'actor_ref',
    'completed_at',
    'audit_ref',
    'completion_id',
    'session_ref',
    'cloud_location_ref',
    'cloud_location_verification_ref',
    'snapshot_ref',
    'script_version_ref',
    'production_plan_ref',
    'preset_revision_ref',
    'quality_report_ref',
    'variant_validation_ref',
    'media_usage_manifest',
    'output_naming_metadata',
    'cost_usage_summary',
    'cleanup_policy_ref',
)

_LEDGER_INSERT = (
    'INSERT INTO controlplane.cp_completion_ledger ('
    + ', '.join(_LEDGER_COLUMNS)
    + ') VALUES ('
    + ', '.join(['%s'] * len(_LEDGER_COLUMNS))
    + ')'
)


class PostgresCompletionUnitOfWork(CompletionUnitOfWork):
    def __init__(self, transactions: Any, workspace_id: str, request: Mapping[str, Any]) -> None:
        self._transactions = transactions
        self._workspace_id = workspace_id
        self._request = request
        self._context = None
        self._connection = None
        self._ledger = None
        self.store = self

    def begin(self) -> None:
        if self._connection is not None:
            raise RuntimeError('completion unit of work already active')
        self._context = self._transactions.borrow_connection()
        self._connection = self._context.__enter__()
        self._ledger = None

    def commit(self) -> None:
        connection = self.connection
        try:
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            self._release()

    def rollback(self) -> None:
        connection = self._connection
        if connection is None:
            return
        try:
            connection.rollback()
        finally:
            self._release()

    def _release(self) -> None:
        context, self._context, self._connection = self._context, None, None
        if context is not None:
            context.__exit__(None, None, None)

    def __enter__(self) -> PostgresCompletionUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.rollback()
        return None

    @property
    def connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError('completion unit of work is not active')
        return self._connection

    @property
    def current_ledger(self) -> Mapping[str, Any]:
        if self._ledger is None:
            raise RuntimeError('ledger has not been inserted')
        return self._ledger

    def _update_one(self, query: str, params: tuple[Any, ...], code: str) -> None:
        if self.connection.execute(query, params).rowcount != 1:
            raise CompletionStoreError(code)

    def find_ledger(self, video_job_id: str) -> Mapping[str, Any] | None:
        row = self.connection.execute(_LEDGER_SELECT, (self._workspace_id, video_job_id)).fetchone()
        if row is None:
            return None
        d = dict(zip(_LEDGER_KEYS, row))
        completed_at = d.get('completed_at')
        if completed_at is not None:
            if isinstance(completed_at, datetime):
                d['completed_at'] = completed_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
            else:
                d['completed_at'] = str(completed_at)
        return d

    def get_job(self, job_id: str) -> JobRecord | None:
        row = self.connection.execute(_JOB_SELECT, (self._workspace_id, job_id)).fetchone()
        if row is None:
            return None
        return JobRecord(job_id, JobState(row[0]), int(row[1]))

    def get_variant_reservation(self, reservation_id: str) -> ReservationBinding | None:
        artifact_id = None
        try:
            artifact_id = str(uuid.UUID(str(self._request.get('output_artifact_version_id'))))
        except (ValueError, AttributeError):
            artifact_id = None
        # cp_variant_reservations chưa có cột hash đầu ra nên hash đối chiếu lấy từ cp_artifact_versions của output_artifact_version_id (GIẢ ĐỊNH, ghi vào báo cáo).
        row = self.connection.execute(_RESERVATION_SELECT, (artifact_id, self._workspace_id, reservation_id)).fetchone()
        if row is None:
            return None
        return ReservationBinding(str(row[0]), str(row[1]), str(row[3] or ''), ReservationState(row[2]))

    def get_registry_revision(self) -> int:
        return PostgresVariantRegistry(self.connection).current_revision(self._workspace_id)

    def insert_ledger(self, ledger: Mapping[str, Any]) -> None:
        cap_row = self.connection.execute(
            "SELECT reservation_id FROM controlplane.cp_batch_capacity_reservations "
            "WHERE workspace_id = %s AND job_id = %s",
            (self._workspace_id, ledger['video_job_id']),
        ).fetchone()
        if cap_row is None:
            raise CompletionStoreError('CAPACITY_RESERVATION_MISSING')
        capacity_id = cap_row[0]

        self.connection.execute(
            _LEDGER_INSERT,
            (
                uuid.uuid4(),
                self._workspace_id,
                ledger['video_job_id'],
                ledger['batch_ref'],
                capacity_id,
                self._request['variant_reservation_id'],
                ledger['output_artifact_version_id'],
                ledger['output_sha256'],
                ledger['audit_actor'],
                ledger['completed_at'],
                ledger['completion_id'],
                ledger['completion_id'],
                ledger['session_ref'],
                ledger['cloud_location_ref'],
                self._request['cloud_location_verification_ref'],
                ledger['snapshot_ref'],
                ledger['script_version_ref'],
                ledger['production_plan_ref'],
                ledger['preset_revision_ref'],
                ledger['quality_report_ref'],
                ledger['variant_validation_ref'],
                Jsonb(ledger['media_usage_manifest']),
                Jsonb(ledger['output_naming_metadata']),
                Jsonb(ledger['cost_usage_summary']),
                ledger['cleanup_policy_ref'],
            ),
        )
        self._ledger = dict(ledger)

    def set_job_state(self, job_id: str, state: Any, revision: int) -> None:
        self._update_one(
            "UPDATE controlplane.cp_video_jobs SET status = %s, revision = %s "
            "WHERE workspace_id = %s AND job_id = %s AND revision = %s",
            (JobState(state).value, revision, self._workspace_id, job_id, revision - 1),
            'JOB_REVISION_CONFLICT',
        )

    def convert_capacity_reservation(self, job_id: str) -> None:
        self._update_one(
            "UPDATE controlplane.cp_batch_capacity_reservations SET state = 'CONVERTED' "
            "WHERE workspace_id = %s AND job_id = %s AND state = 'ACTIVE'",
            (self._workspace_id, job_id),
            'CAPACITY_RESERVATION_NOT_ACTIVE',
        )

    def convert_variant_reservation(self, reservation_id: str) -> None:
        self._update_one(
            "UPDATE controlplane.cp_variant_reservations SET state = 'CONVERTED' "
            "WHERE workspace_id = %s AND reservation_id = %s AND state = 'ACTIVE'",
            (self._workspace_id, reservation_id),
            'VARIANT_RESERVATION_NOT_ACTIVE',
        )

    def set_registry_revision(self, revision: int) -> None:
        self._update_one(
            "UPDATE controlplane.cp_variant_registry SET current_registry_revision = %s "
            "WHERE workspace_id = %s AND current_registry_revision = %s",
            (revision, self._workspace_id, revision - 1),
            'REGISTRY_REVISION_CONFLICT',
        )

    def increment_batch_completed(self, batch_ref: str) -> None:
        target_row = self.connection.execute(
            "SELECT target_count FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s FOR UPDATE",
            (self._workspace_id, batch_ref),
        ).fetchone()
        if target_row is None:
            raise CompletionStoreError('BATCH_MISSING')
        target_count = int(target_row[0])
        count_row = self.connection.execute(
            "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND batch_id = %s",
            (self._workspace_id, batch_ref),
        ).fetchone()
        count = int(count_row[0]) if count_row is not None else 0
        if count > target_count:
            raise CompletionStoreError('BATCH_TARGET_EXCEEDED')

    def insert_outbox(self, event: Mapping[str, Any]) -> None:
        payload = dict(event['payload'])
        epoch = str(event['recovery_epoch'])
        recovery = (
            int(epoch)
            if epoch.isascii() and epoch.isdecimal() and len(epoch) <= 18 and str(int(epoch)) == epoch
            else None
        )
        domain_event = DomainEvent(
            contract_name='orchestration.video.completed',
            contract_version=1,
            message_id=event['event_id'],
            workspace_id=self._workspace_id,
            correlation_id=payload['completion_id'],
            causation_id=None,
            trace_context=None,
            occurred_at=self.current_ledger['completed_at'],
            actor=self.current_ledger['audit_actor'],
            recovery_epoch=recovery,
            payload=payload,
            event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'controlplane:' + event['event_id'])),
            event_name=event['event_name'],
            aggregate_type=event['aggregate_type'],
            aggregate_id=event['aggregate_id'],
            aggregate_revision=event['aggregate_revision'],
            producer=event['producer'],
            schema_version=int(event['schema_version']),
            sensitivity=event['sensitivity'],
        )
        PostgresOutboxRepository(self.connection).enqueue(domain_event)

    def insert_cleanup_eligibility(self, record: Mapping[str, Any]) -> None:
        if record.get('state') != 'CLEANUP_ELIGIBLE':
            raise CompletionStoreError('CLEANUP_STATE_INVALID')
        self.connection.execute(
            "INSERT INTO controlplane.cp_cleanup_eligibility "
            "(workspace_id, cleanup_eligibility_id, video_job_id, artifact_version_id, cleanup_policy_ref, eligible_at, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'ELIGIBLE')",
            (
                self._workspace_id,
                record['completion_id'],
                record['video_job_id'],
                record['output_artifact_version_id'],
                record['cleanup_policy_ref'],
                self.current_ledger['completed_at'],
            ),
        )


class PostgresMediaUsagePort:
    def __init__(self, uow: Any, recorder: Any) -> None:
        self._uow = uow
        self._recorder = recorder

    def record(self, manifest: list[Any]) -> None:
        ledger = self._uow.current_ledger
        self._recorder.record_production_usage(self._uow,
            ledger['completion_id'],
            {'video_job_id': ledger['video_job_id'], 'media_usage_manifest': manifest},
        )


__all__ = ['CompletionStoreError', 'PostgresCompletionUnitOfWork', 'PostgresMediaUsagePort']
