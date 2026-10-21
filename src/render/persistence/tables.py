"""PostgreSQL tables for reports, receipts, traces, and attempt index (PERSIST-F)."""
from __future__ import annotations

import datetime
import json
from typing import Any

import psycopg.errors

from controlplane.domain.concurrency import RevisionConflictError
from render.application.package_pipeline import CommandReceipt, CommandTrace
from render.domain.validate_package import PackageValidationReport
from render.persistence import _codec
from render.persistence._sql import (
    ConnectionProvider,
    ReadProvider,
    dumps,
    resolve_workspace,
    savepoint,
    uuid_text,
)
from render.ports.repositories import DuplicateRecordError

TRACE_PREFIX = 'render-trace:'


class PostgresReportTable:
    """Append-only table for package validation reports keyed by package_fingerprint."""

    def __init__(
        self,
        connection: ConnectionProvider,
        reader: ReadProvider,
        workspace_id: str | None,
    ) -> None:
        self._connection = connection
        self._reader = reader
        self._workspace_id = workspace_id

    def _workspace(self) -> str:
        return resolve_workspace(self._workspace_id)

    def append(self, report: Any) -> int:
        if not isinstance(report, PackageValidationReport):
            raise TypeError('report must be a PackageValidationReport')
        conn = self._connection()
        ws = self._workspace()
        key = report.package_fingerprint

        row = conn.execute(
            'SELECT revision, payload->>\'report_id\' FROM controlplane.cp_package_validation_reports '
            'WHERE workspace_id = %s AND record_key = %s ORDER BY revision DESC LIMIT 1',
            (ws, key),
        ).fetchone()

        if row is not None:
            prev_rev, prev_report_id = row[0], row[1]
            if prev_report_id == report.report_id:
                return prev_rev
            next_rev = prev_rev + 1
        else:
            prev_rev = 0
            next_rev = 1

        payload_json = dumps(_codec.validation_payload(report))
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_package_validation_reports '
                    '(workspace_id, record_key, revision, payload) '
                    'VALUES (%s, %s, %s, %s::jsonb)',
                    (ws, key, next_rev, payload_json),
                )
        except psycopg.errors.UniqueViolation:
            raise RevisionConflictError(prev_rev) from None

        return next_rev

    def latest(self, package_fingerprint: str) -> PackageValidationReport | None:
        ws = self._workspace()
        with self._reader() as conn:
            row = conn.execute(
                'SELECT payload FROM controlplane.cp_package_validation_reports '
                'WHERE workspace_id = %s AND record_key = %s ORDER BY revision DESC LIMIT 1',
                (ws, package_fingerprint),
            ).fetchone()
        return _codec.validation_from_payload(row[0]) if row is not None else None

    def revisions(self, package_fingerprint: str) -> tuple[PackageValidationReport, ...]:
        ws = self._workspace()
        with self._reader() as conn:
            rows = conn.execute(
                'SELECT payload FROM controlplane.cp_package_validation_reports '
                'WHERE workspace_id = %s AND record_key = %s ORDER BY revision ASC',
                (ws, package_fingerprint),
            ).fetchall()
        return tuple(_codec.validation_from_payload(r[0]) for r in rows)

    def by_id(self, package_fingerprint: str, report_id: str) -> PackageValidationReport | None:
        ws = self._workspace()
        with self._reader() as conn:
            row = conn.execute(
                'SELECT payload FROM controlplane.cp_package_validation_reports '
                'WHERE workspace_id = %s AND record_key = %s AND payload->>\'report_id\' = %s '
                'ORDER BY revision LIMIT 1',
                (ws, package_fingerprint, report_id),
            ).fetchone()
        return _codec.validation_from_payload(row[0]) if row is not None else None


class PostgresReceiptTable:
    """Idempotent store for command operation receipts in cp_render_operation_receipts."""

    def __init__(
        self,
        connection: ConnectionProvider,
        reader: ReadProvider,
        workspace_id: str | None,
    ) -> None:
        self._connection = connection
        self._reader = reader
        self._workspace_id = workspace_id

    def _workspace(self) -> str:
        return resolve_workspace(self._workspace_id)

    def add(self, receipt: CommandReceipt) -> None:
        conn = self._connection()
        ws = uuid_text(receipt.workspace_id)
        idempotency_key = _codec.receipt_key(receipt.command, receipt.operation_key)
        ref_json = _codec.receipt_ref_json(receipt)
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_render_operation_receipts '
                    '(workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (ws, idempotency_key, receipt.request_hash, ref_json, receipt.revision),
                )
        except psycopg.errors.UniqueViolation:
            raise DuplicateRecordError('receipt already stored for this operation_key') from None

    def get(self, workspace_id: str, command: str, operation_key: str) -> CommandReceipt | None:
        ws_text = uuid_text(workspace_id)
        key = _codec.receipt_key(command, operation_key)
        with self._reader() as conn:
            row = conn.execute(
                'SELECT idempotency_key, request_hash, aggregate_ref, aggregate_revision '
                'FROM controlplane.cp_render_operation_receipts '
                'WHERE workspace_id = %s AND idempotency_key = %s',
                (ws_text, key),
            ).fetchone()
        if row is None:
            return None
        return _codec.receipt_from_row(ws_text, row[0], row[1], row[2], row[3])

    def records(self) -> tuple[CommandReceipt, ...]:
        ws_text = self._workspace()
        with self._reader() as conn:
            rows = conn.execute(
                'SELECT idempotency_key, request_hash, aggregate_ref, aggregate_revision '
                'FROM controlplane.cp_render_operation_receipts '
                'WHERE workspace_id = %s ORDER BY created_at, idempotency_key',
                (ws_text,),
            ).fetchall()
        return tuple(_codec.receipt_from_row(ws_text, r[0], r[1], r[2], r[3]) for r in rows)


class PostgresTraceTable:
    """Sequential audit trace storage in controlplane.cp_audit_records."""

    def __init__(
        self,
        connection: ConnectionProvider,
        reader: ReadProvider,
        workspace_id: str | None,
    ) -> None:
        self._connection = connection
        self._reader = reader
        self._workspace_id = workspace_id

    def _workspace(self) -> str:
        return resolve_workspace(self._workspace_id)

    def append(self, trace: CommandTrace) -> None:
        conn = self._connection()
        ws = self._workspace()
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (TRACE_PREFIX + ws,))
        row = conn.execute(
            'SELECT count(*) FROM controlplane.cp_audit_records '
            'WHERE workspace_id = %s AND starts_with(audit_id, %s)',
            (ws, TRACE_PREFIX),
        ).fetchone()
        n = (row[0] if row is not None else 0) + 1
        audit_id = f'{TRACE_PREFIX}{n:012d}'
        dt = datetime.datetime.fromisoformat(trace.occurred_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        conn.execute(
            'INSERT INTO controlplane.cp_audit_records '
            '(audit_id, workspace_id, actor_ref, action, resource_ref, revision_before, revision_after, occurred_at, correlation_id, outcome, redacted_reason) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (
                audit_id,
                ws,
                trace.actor,
                trace.command,
                trace.subject_ref,
                None,
                None,
                dt,
                trace.correlation_id,
                _codec.audit_outcome(trace.outcome),
                dumps(_codec.trace_payload(trace)),
            ),
        )

    def records(self) -> tuple[CommandTrace, ...]:
        ws = self._workspace()
        with self._reader() as conn:
            rows = conn.execute(
                'SELECT audit_id, redacted_reason FROM controlplane.cp_audit_records '
                'WHERE workspace_id = %s AND starts_with(audit_id, %s) ORDER BY audit_id',
                (ws, TRACE_PREFIX),
            ).fetchall()
        traces = []
        for audit_id, redacted_reason in rows:
            sequence = int(audit_id[len(TRACE_PREFIX):])
            data = redacted_reason if isinstance(redacted_reason, dict) else json.loads(redacted_reason)
            traces.append(_codec.trace_from_payload(sequence, data))
        return tuple(traces)


class PostgresAttemptIndex:
    """Index of attempt ids by package_fingerprint, derived from cp_render_attempts."""

    def __init__(
        self,
        connection: ConnectionProvider,
        reader: ReadProvider,
        workspace_id: str | None,
    ) -> None:
        self._connection = connection
        self._reader = reader
        self._workspace_id = workspace_id

    def _workspace(self) -> str:
        return resolve_workspace(self._workspace_id)

    def add(self, package_fingerprint: str, attempt_id: str) -> None:
        # Require UoW to be active; the attempt record already holds package_fingerprint
        self._connection()

    def ids(self, package_fingerprint: str) -> tuple[str, ...]:
        ws = self._workspace()
        with self._reader() as conn:
            rows = conn.execute(
                'SELECT record_key FROM controlplane.cp_render_attempts '
                'WHERE workspace_id = %s AND revision = 1 AND payload->>\'package_fingerprint\' = %s '
                'ORDER BY created_at, record_key',
                (ws, package_fingerprint),
            ).fetchall()
        return tuple(r[0] for r in rows)