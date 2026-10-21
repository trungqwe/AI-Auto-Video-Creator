"""PostgreSQL variant registry store for caller-owned transactions."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from controlplane.application.orchestration.variant_reservation_flow import VariantReservationRecord
from controlplane.domain.orchestration import ReservationState

_REF = 'variant_reservation:'
_SELECT = (
    "SELECT v.reservation_id, v.workspace_id::text, v.job_id, v.fingerprint, "
    "v.snapshot_scope, v.validation_ref, v.variation_policy_revision, "
    "v.expected_registry_revision, v.committed_registry_revision, "
    "COALESCE(r.idempotency_key, ''), v.state "
    "FROM controlplane.cp_variant_reservations v "
    "LEFT JOIN controlplane.cp_orchestration_receipts r "
    "ON r.workspace_id = v.workspace_id AND r.aggregate_ref = 'variant_reservation:' || v.reservation_id"
)


def _record(row: Any) -> VariantReservationRecord:
    state_val = str(row[10])
    return VariantReservationRecord(
        reservation_id=str(row[0]),
        workspace_id=str(row[1]),
        job_id=str(row[2]),
        fingerprint=str(row[3]),
        snapshot_scope=str(row[4]),
        validation_ref=str(row[5]),
        variation_policy_revision=str(row[6]),
        expected_registry_revision=int(row[7]),
        committed_registry_revision=int(row[8]),
        idempotency_key=str(row[9]),
        state=ReservationState(state_val),
    )


class PostgresVariantRegistry:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def current_revision(self, workspace_id: str) -> int:
        self._connection.execute(
            "INSERT INTO controlplane.cp_variant_registry "
            "(workspace_id, current_registry_revision) VALUES (%s, 1) "
            "ON CONFLICT (workspace_id) DO NOTHING",
            (workspace_id,),
        )
        row = self._connection.execute(
            "SELECT current_registry_revision "
            "FROM controlplane.cp_variant_registry "
            "WHERE workspace_id = %s FOR UPDATE",
            (workspace_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 1

    def find_by_job(
        self, workspace_id: str, job_id: str
    ) -> VariantReservationRecord | None:
        row = self._connection.execute(
            _SELECT + " WHERE v.workspace_id = %s AND v.job_id = %s",
            (workspace_id, job_id),
        ).fetchone()
        return _record(row) if row is not None else None

    def find_active_by_fingerprint(
        self, workspace_id: str, fingerprint: str
    ) -> VariantReservationRecord | None:
        row = self._connection.execute(
            _SELECT + " WHERE v.workspace_id = %s AND v.fingerprint = %s AND v.state IN ('ACTIVE', 'CONVERTED') LIMIT 1",
            (workspace_id, fingerprint),
        ).fetchone()
        return _record(row) if row is not None else None

    def save(self, record: VariantReservationRecord) -> None:
        existing = self._connection.execute(
            "SELECT 1 FROM controlplane.cp_variant_reservations "
            "WHERE workspace_id = %s AND reservation_id = %s",
            (record.workspace_id, record.reservation_id),
        ).fetchone()
        state_val = record.state.value if isinstance(record.state, ReservationState) else str(record.state)
        if existing is not None:
            self._connection.execute(
                "UPDATE controlplane.cp_variant_reservations "
                "SET state = %s WHERE workspace_id = %s AND reservation_id = %s",
                (state_val, record.workspace_id, record.reservation_id),
            )
            return

        self._connection.execute(
            "INSERT INTO controlplane.cp_variant_reservations "
            "(reservation_id, workspace_id, job_id, fingerprint, snapshot_scope, "
            "validation_ref, variation_policy_revision, expected_registry_revision, "
            "committed_registry_revision, state) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                record.reservation_id,
                record.workspace_id,
                record.job_id,
                record.fingerprint,
                record.snapshot_scope,
                record.validation_ref,
                record.variation_policy_revision,
                record.expected_registry_revision,
                record.committed_registry_revision,
                state_val,
            ),
        )

        payload = [
            record.fingerprint,
            record.snapshot_scope,
            record.validation_ref,
            record.variation_policy_revision,
            record.expected_registry_revision,
        ]
        request_hash = hashlib.sha256(
            json.dumps(payload, separators=(',', ':')).encode()
        ).hexdigest()

        self._connection.execute(
            "INSERT INTO controlplane.cp_orchestration_receipts "
            "(workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                record.workspace_id,
                record.idempotency_key,
                request_hash,
                _REF + record.reservation_id,
                record.committed_registry_revision,
            ),
        )

    def bump_revision(self, workspace_id: str) -> int:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_variant_registry "
            "(workspace_id, current_registry_revision) VALUES (%s, 2) "
            "ON CONFLICT (workspace_id) DO UPDATE SET "
            "current_registry_revision = controlplane.cp_variant_registry.current_registry_revision + 1 "
            "RETURNING current_registry_revision",
            (workspace_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 2


__all__ = ['PostgresVariantRegistry']