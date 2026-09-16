"""PostgreSQL persistence for the P6 orchestration boundary."""

from __future__ import annotations

from typing import Any

from controlplane.domain.orchestration import (
    CapacityAllocation,
    CompletionLedger,
    OrchestrationContractError,
    ReservationState,
    VariantReservation,
)

_CAPACITY_COLUMNS = "workspace_id::text, batch_id, job_id, reservation_id, state"
_VARIANT_COLUMNS = (
    "reservation_id, workspace_id::text, job_id, fingerprint, snapshot_scope, "
    "validation_ref, variation_policy_revision, committed_registry_revision, state, "
    "expected_registry_revision"
)
_LEDGER_COLUMNS = (
    "ledger_id::text, workspace_id::text, job_id, batch_id, capacity_reservation_id, "
    "variant_reservation_id, output_artifact_version_id::text, output_artifact_hash, "
    "actor_ref, completed_at, audit_ref"
)


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _capacity(row: Any, target: int) -> CapacityAllocation:
    if row is None:
        raise OrchestrationContractError("NOT_FOUND")
    return CapacityAllocation(
        str(row[0]),
        str(row[1]),
        str(row[2]),
        str(row[3]),
        target,
        ReservationState(str(row[4])),
    )


def _variant(row: Any) -> VariantReservation:
    return VariantReservation(
        str(row[0]),
        str(row[1]),
        str(row[2]),
        str(row[3]),
        str(row[4]),
        str(row[5]),
        str(row[6]),
        int(row[7]),
        ReservationState(str(row[8])),
    )


def _ledger(row: Any) -> CompletionLedger:
    return CompletionLedger(
        str(row[0]),
        str(row[1]),
        str(row[2]),
        str(row[3]),
        str(row[4]),
        str(row[5]),
        str(row[6]),
        str(row[7]),
        str(row[8]),
        _iso(row[9]),
        str(row[10]),
    )


class PostgresOrchestrationRepository:
    """SQL adapter over a caller-owned connection; never owns transactions."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def reserve_variant(
        self, reservation_id: str, values: dict[str, Any]
    ) -> VariantReservation:
        workspace_id = values["workspace_id"]
        self._connection.execute(
            "INSERT INTO controlplane.cp_variant_registry "
            "(workspace_id,current_registry_revision) VALUES (%s,1) "
            "ON CONFLICT (workspace_id) DO NOTHING",
            (workspace_id,),
        )
        registry = self._connection.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s FOR UPDATE",
            (workspace_id,),
        ).fetchone()
        if registry is None:
            raise OrchestrationContractError("NOT_FOUND")
        existing = self._connection.execute(
            f"SELECT {_VARIANT_COLUMNS} FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND job_id=%s",
            (workspace_id, values["job_id"]),
        ).fetchone()
        if existing is not None:
            same = (
                str(existing[3]) == values["fingerprint"]
                and str(existing[4]) == values["snapshot_scope"]
                and str(existing[5]) == values["validation_ref"]
                and str(existing[6]) == values["variation_policy_revision"]
                and int(existing[9]) == values["expected_registry_revision"]
            )
            if same:
                return _variant(existing)
            raise OrchestrationContractError("VARIANT_CONFLICT")
        conflict = self._connection.execute(
            "SELECT 1 FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND fingerprint=%s AND state IN ('ACTIVE','CONVERTED')",
            (workspace_id, values["fingerprint"]),
        ).fetchone()
        if conflict is not None:
            raise OrchestrationContractError("VARIANT_CONFLICT")
        current_revision = int(registry[0])
        if current_revision != values["expected_registry_revision"]:
            raise OrchestrationContractError("VARIANT_VALIDATION_STALE")
        committed_revision = current_revision + 1
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_variant_reservations (reservation_id,workspace_id,job_id,fingerprint,snapshot_scope,validation_ref,variation_policy_revision,expected_registry_revision,committed_registry_revision,state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE') RETURNING "
            + _VARIANT_COLUMNS,
            (
                reservation_id,
                workspace_id,
                values["job_id"],
                values["fingerprint"],
                values["snapshot_scope"],
                values["validation_ref"],
                values["variation_policy_revision"],
                current_revision,
                committed_revision,
            ),
        ).fetchone()
        self._connection.execute(
            "UPDATE controlplane.cp_variant_registry SET current_registry_revision=%s WHERE workspace_id=%s",
            (committed_revision, workspace_id),
        )
        return _variant(row)

    def allocate_capacity(
        self, reservation_id: str, values: dict[str, Any]
    ) -> CapacityAllocation:
        workspace_id, batch_id = values["workspace_id"], values["batch_id"]
        batch = self._connection.execute(
            "SELECT target_count FROM controlplane.cp_production_batches WHERE workspace_id=%s AND batch_id=%s FOR UPDATE",
            (workspace_id, batch_id),
        ).fetchone()
        if batch is None:
            raise OrchestrationContractError("NOT_FOUND")
        target = int(batch[0])
        existing = self._connection.execute(
            f"SELECT {_CAPACITY_COLUMNS} FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id=%s",
            (workspace_id, values["job_id"]),
        ).fetchone()
        if existing is not None:
            if str(existing[1]) != batch_id:
                raise OrchestrationContractError("VALIDATION_ERROR")
            return _capacity(existing, target)
        occupied = self._connection.execute(
            "SELECT (SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND batch_id=%s) + (SELECT count(*) FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND batch_id=%s AND state='ACTIVE')",
            (workspace_id, batch_id, workspace_id, batch_id),
        ).fetchone()[0]
        if int(occupied) >= target:
            raise OrchestrationContractError("BATCH_TARGET_REACHED")
        self._connection.execute(
            "INSERT INTO controlplane.cp_video_jobs (job_id,batch_id,workspace_id,status,snapshot_ref,revision) VALUES (%s,%s,%s,'CREATED','allocation',1)",
            (values["job_id"], batch_id, workspace_id),
        )
        if values.get("fault_hook") is not None:
            values["fault_hook"]("after_job_insert")
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id,workspace_id,batch_id,job_id,state) VALUES (%s,%s,%s,%s,'ACTIVE') RETURNING "
            + _CAPACITY_COLUMNS,
            (reservation_id, workspace_id, batch_id, values["job_id"]),
        ).fetchone()
        return _capacity(row, target)

    def get_capacity(self, workspace_id: str, job_id: str) -> CapacityAllocation:
        row = self._connection.execute(
            f"SELECT {_CAPACITY_COLUMNS} FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id=%s",
            (workspace_id, job_id),
        ).fetchone()
        return _capacity(row, self._target_for(row))

    def set_capacity_state(
        self, workspace_id: str, job_id: str, state: str
    ) -> CapacityAllocation:
        row = self._connection.execute(
            "UPDATE controlplane.cp_batch_capacity_reservations SET state=%s WHERE workspace_id=%s AND job_id=%s AND state='ACTIVE' RETURNING "
            + _CAPACITY_COLUMNS,
            (state, workspace_id, job_id),
        ).fetchone()
        if row is None:
            row = self._connection.execute(
                f"SELECT {_CAPACITY_COLUMNS} FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id=%s AND state=%s",
                (workspace_id, job_id, state),
            ).fetchone()
        return _capacity(row, self._target_for(row))

    def _target_for(self, row: Any) -> int:
        if row is None:
            raise OrchestrationContractError("NOT_FOUND")
        return int(
            self._connection.execute(
                "SELECT target_count FROM controlplane.cp_production_batches WHERE workspace_id=%s AND batch_id=%s",
                (row[0], row[1]),
            ).fetchone()[0]
        )

    def commit_completion(
        self, ledger_id: str, values: dict[str, Any]
    ) -> CompletionLedger:
        job = self._connection.execute(
            "SELECT 1 FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id=%s AND batch_id=%s FOR UPDATE",
            (values["workspace_id"], values["job_id"], values["batch_id"]),
        ).fetchone()
        if job is None:
            raise OrchestrationContractError("NOT_FOUND")
        existing = self._connection.execute(
            f"SELECT {_LEDGER_COLUMNS} FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id=%s",
            (values["workspace_id"], values["job_id"]),
        ).fetchone()
        if existing is not None:
            expected = (
                values["batch_id"],
                values["capacity_reservation_id"],
                values["variant_reservation_id"],
                values["output_artifact_version_id"],
                values["output_artifact_hash"],
                values["actor_ref"],
                values["completed_at"],
                values["audit_ref"],
            )
            actual = tuple(str(existing[index]) for index in (3, 4, 5, 6, 7, 8, 9, 10))
            if actual != tuple(str(value) for value in expected):
                raise OrchestrationContractError("FORBIDDEN_TRANSITION")
            return _ledger(existing)
        if values.get("fault_hook") is not None:
            values["fault_hook"]("before_ledger_insert")
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING "
            + _LEDGER_COLUMNS,
            (
                ledger_id,
                values["workspace_id"],
                values["job_id"],
                values["batch_id"],
                values["capacity_reservation_id"],
                values["variant_reservation_id"],
                values["output_artifact_version_id"],
                values["output_artifact_hash"],
                values["actor_ref"],
                values["completed_at"],
                values["audit_ref"],
            ),
        ).fetchone()
        return _ledger(row)


__all__ = ["PostgresOrchestrationRepository"]
