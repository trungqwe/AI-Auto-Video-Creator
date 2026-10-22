"""PostgreSQL adapters of the J ports (reservation, cost ledger, audit sink, account test receipt) on migration 0009 tables."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from controlplane.application.config_security.account_test import AccountTestReceipt
from controlplane.application.config_security.capacity_reservation import Reservation
from controlplane.domain.config_security.audit_record import AuditRecord
from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord

RECEIPT_ACTION = 'account_test'
RECEIPT_ACTOR = 'system:account-test'
RECEIPT_ID_PREFIX = 'acctest-'

_RESERVATION_COLUMNS = 'reservation_ref, domain_key, units, expires_at, operation_key, confidence_flag'


def _reservation(row: tuple[Any, ...]) -> Reservation:
    return Reservation(str(row[0]), str(row[1]), int(row[2]), row[3], str(row[4]), str(row[5]))


class PostgresReservationStore:
    """ReservationStorePort on cp_capacity_reservations, bound to the caller-owned connection and one workspace."""
    def __init__(self, connection: Any, workspace_id: str) -> None: self._connection, self._workspace_id = connection, workspace_id

    def get_by_operation(self, operation_key: str) -> Reservation | None:
        row = self._connection.execute(f'SELECT {_RESERVATION_COLUMNS} FROM controlplane.cp_capacity_reservations WHERE workspace_id=%s AND operation_key=%s', (self._workspace_id, operation_key)).fetchone()
        return None if row is None else _reservation(row)

    def list_by_domain(self, domain_key: str) -> tuple[Reservation, ...]:
        rows = self._connection.execute(f'SELECT {_RESERVATION_COLUMNS} FROM controlplane.cp_capacity_reservations WHERE workspace_id=%s AND domain_key=%s ORDER BY created_at, reservation_ref', (self._workspace_id, domain_key)).fetchall()
        return tuple(_reservation(row) for row in rows)

    def list_all(self) -> tuple[Reservation, ...]:
        rows = self._connection.execute(f'SELECT {_RESERVATION_COLUMNS} FROM controlplane.cp_capacity_reservations WHERE workspace_id=%s ORDER BY created_at, reservation_ref', (self._workspace_id,)).fetchall()
        return tuple(_reservation(row) for row in rows)

    def add(self, reservation: Reservation) -> None:
        self._connection.execute(
            'INSERT INTO controlplane.cp_capacity_reservations (reservation_ref, workspace_id, domain_key, units, expires_at, operation_key, confidence_flag) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (workspace_id, reservation_ref) DO UPDATE SET domain_key=EXCLUDED.domain_key, units=EXCLUDED.units, expires_at=EXCLUDED.expires_at, operation_key=EXCLUDED.operation_key, confidence_flag=EXCLUDED.confidence_flag, updated_at=CURRENT_TIMESTAMP',
            (reservation.reservation_ref, self._workspace_id, reservation.domain_key, reservation.units, reservation.expires_at, reservation.operation_key, reservation.confidence_flag),
        )

    def remove(self, reservation_ref: str) -> Reservation | None:
        row = self._connection.execute(f'DELETE FROM controlplane.cp_capacity_reservations WHERE workspace_id=%s AND reservation_ref=%s RETURNING {_RESERVATION_COLUMNS}', (self._workspace_id, reservation_ref)).fetchone()
        return None if row is None else _reservation(row)


_COST_COLUMNS = 'record_id, provider, service, operation_ref, job_ref, batch_ref, quantity, unit, estimated_cost, actual_cost, currency, source, occurred_at, cost_category'


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(value)


def _cost_record(row: tuple[Any, ...]) -> IncrementalCostRecord:
    return IncrementalCostRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]), _optional_text(row[4]), _optional_text(row[5]), Decimal(row[6]), str(row[7]), Decimal(row[8]), _optional_decimal(row[9]), str(row[10]), str(row[11]), row[12].astimezone(timezone.utc).isoformat(), str(row[13]))


class PostgresCostLedger:
    """CostLedgerPort on cp_cost_records; append is idempotent per (workspace_id, record_id)."""
    def __init__(self, connection: Any) -> None: self._connection = connection

    def records(self, workspace_id: str, window_start: datetime, window_end: datetime) -> tuple[IncrementalCostRecord, ...]:
        rows = self._connection.execute(f'SELECT {_COST_COLUMNS} FROM controlplane.cp_cost_records WHERE workspace_id=%s AND occurred_at >= %s AND occurred_at < %s ORDER BY occurred_at, record_id', (workspace_id, window_start, window_end)).fetchall()
        return tuple(_cost_record(row) for row in rows)

    def append(self, workspace_id: str, record: IncrementalCostRecord) -> None:
        self._connection.execute(
            'INSERT INTO controlplane.cp_cost_records (record_id, workspace_id, provider, service, operation_ref, job_ref, batch_ref, quantity, unit, estimated_cost, actual_cost, currency, source, occurred_at, cost_category) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s) ON CONFLICT (workspace_id, record_id) DO NOTHING',
            (record.record_id, workspace_id, record.provider, record.service, record.operation_ref, record.job_ref, record.batch_ref, record.quantity, record.unit, record.estimated_cost, record.actual_cost, record.currency, record.source, record.occurred_at, record.cost_category),
        )


def _revision_number(name: str, value: str | None) -> int | None:
    if value is None: return None
    if not (value.isascii() and value.isdigit()): raise ValueError(f'{name} must be a numeric revision to be stored in PostgreSQL')
    return int(value)


class PostgresAuditSink:
    """AuditSinkPort on cp_audit_records (append-only by trigger); this class never updates or deletes."""
    def __init__(self, connection: Any) -> None: self._connection = connection

    def append(self, record: AuditRecord) -> None:
        before = _revision_number('revision_before', record.revision_before)
        after = _revision_number('revision_after', record.revision_after)
        self._connection.execute(
            'INSERT INTO controlplane.cp_audit_records (audit_id, workspace_id, actor_ref, action, resource_ref, revision_before, revision_after, occurred_at, correlation_id, outcome, redacted_reason) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s)',
            (record.audit_id, record.workspace_id, record.actor_ref, record.action, record.resource_ref, before, after, record.occurred_at, record.correlation_id, record.outcome, record.redacted_reason),
        )


class PostgresAccountTestReceiptStore:
    """ReceiptStorePort stored as cp_audit_records rows (GIAI DINH: 0009 has no receipt table and adding a migration is out of scope).

    audit_id is the receipt_id (prefix acctest-), correlation_id is the operation_key, resource_ref is the external_account_id,
    redacted_reason holds the receipt JSON. Only already-redacted receipt fields are stored.
    """
    def __init__(self, connection: Any, workspace_id: str) -> None: self._connection, self._workspace_id = connection, workspace_id

    def get(self, operation_key: str) -> AccountTestReceipt | None:
        row = self._connection.execute('SELECT audit_id, resource_ref, correlation_id, redacted_reason FROM controlplane.cp_audit_records WHERE workspace_id=%s AND action=%s AND correlation_id=%s AND starts_with(audit_id, %s) ORDER BY created_at, audit_id LIMIT 1', (self._workspace_id, RECEIPT_ACTION, operation_key, RECEIPT_ID_PREFIX)).fetchone()
        if row is None: return None
        body = json.loads(row[3])
        return AccountTestReceipt(str(row[0]), str(row[2]), str(row[1]), bool(body['ok']), body['latency_ms'], body['error_class'], body['redacted_detail'], str(body['tested_at']))

    def save(self, receipt: AccountTestReceipt) -> None:
        if not receipt.receipt_id.startswith(RECEIPT_ID_PREFIX): raise ValueError('receipt_id must start with ' + RECEIPT_ID_PREFIX)
        tested_at = datetime.fromisoformat(receipt.tested_at)
        if tested_at.utcoffset() is None: raise ValueError('tested_at must include a timezone offset')
        body = json.dumps({'ok': receipt.ok, 'latency_ms': receipt.latency_ms, 'error_class': receipt.error_class, 'redacted_detail': receipt.redacted_detail, 'tested_at': receipt.tested_at}, sort_keys=True, ensure_ascii=False)
        self._connection.execute(
            'INSERT INTO controlplane.cp_audit_records (audit_id, workspace_id, actor_ref, action, resource_ref, occurred_at, correlation_id, outcome, redacted_reason) VALUES (%s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s) ON CONFLICT (workspace_id, audit_id) DO NOTHING',
            (receipt.receipt_id, self._workspace_id, RECEIPT_ACTOR, RECEIPT_ACTION, receipt.external_account_id, receipt.tested_at, receipt.operation_key, 'succeeded' if receipt.ok else 'failed', body),
        )


__all__ = ["PostgresAccountTestReceiptStore", "PostgresAuditSink", "PostgresCostLedger", "PostgresReservationStore"]
