"""Read-only PostgreSQL projections for P7A Control API routes."""

from __future__ import annotations

from typing import Any

from controlplane.application.projections.operation_view_mapper import map_operation_view
from controlplane.domain.statemachine import OperationState


class PostgresControlQueries:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def operations(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT r.operation_id::text, r.command_id, r.receipt_id::text, r.disposition,
                      r.resource_ref, r.accepted_at, p.event_kind, p.summary, b.status AS batch_status
               FROM controlplane.cp_command_receipts r
               LEFT JOIN LATERAL (
                   SELECT event_kind, summary
                   FROM controlplane.cp_operation_stream
                   WHERE workspace_id = r.workspace_id AND operation_id = r.operation_id
                   ORDER BY stream_event_id DESC
                   LIMIT 1
               ) p ON true
               LEFT JOIN controlplane.cp_production_batches b
                   ON b.workspace_id = r.workspace_id
                   AND r.resource_ref->>'kind' = 'production_batch'
                   AND b.batch_id = r.resource_ref->>'batch_id'
               WHERE r.workspace_id = %s AND r.operation_id IS NOT NULL
               ORDER BY r.accepted_at DESC, r.receipt_id DESC
               LIMIT 100""",
            (workspace_id,),
        ).fetchall()
        return [self._operation_row(row) for row in rows]

    def operation(self, *, workspace_id: str, operation_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """SELECT r.operation_id::text, r.command_id, r.receipt_id::text, r.disposition,
                      r.resource_ref, r.accepted_at, p.event_kind, p.summary, b.status AS batch_status
               FROM controlplane.cp_command_receipts r
               LEFT JOIN LATERAL (
                   SELECT event_kind, summary
                   FROM controlplane.cp_operation_stream
                   WHERE workspace_id = r.workspace_id AND operation_id = r.operation_id
                   ORDER BY stream_event_id DESC
                   LIMIT 1
               ) p ON true
               LEFT JOIN controlplane.cp_production_batches b
                   ON b.workspace_id = r.workspace_id
                   AND r.resource_ref->>'kind' = 'production_batch'
                   AND b.batch_id = r.resource_ref->>'batch_id'
               WHERE r.workspace_id = %s AND r.operation_id = %s""",
            (workspace_id, operation_id),
        ).fetchone()
        return self._operation_row(row) if row is not None else None

    @staticmethod
    def _operation_row(row: Any) -> dict[str, object]:
        batch_status = row[8] if len(row) > 8 else None
        if batch_status:
            status_map = {
                "CREATED": OperationState.PREPARED,
                "RUNNING": OperationState.STARTED,
                "WAITING_CAPABILITY": OperationState.STARTED,
                "COMPLETED_TARGET": OperationState.SUCCEEDED,
                "COMPLETED_EXHAUSTED": OperationState.SUCCEEDED,
                "FAILED_SYSTEM": OperationState.FAILED,
            }
            op_state = status_map.get(batch_status, OperationState.PREPARED)
            wait_reason = {"code": "WAITING_CAPABILITY"} if batch_status == "WAITING_CAPABILITY" else None
            status = map_operation_view(execution_state=op_state, wait_reason=wait_reason)
        else:
            status = "accepted"

        return {
            "operation_id": row[0],
            "command_ref": row[1],
            "receipt_id": row[2],
            "status": status,
            "resource_refs": [row[4]] if row[4] else [],
            "accepted_at": row[5].isoformat() if hasattr(row[5], "isoformat") else row[5],
            "latest_event_kind": row[6],
            "latest_safe_summary": row[7],
        }

    def batches(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT batch_id, status, target_count, created_at "
            "FROM controlplane.cp_production_batches WHERE workspace_id = %s "
            "ORDER BY created_at DESC, batch_id DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
        return [self._batch_row(row) for row in rows]

    def batch(self, *, workspace_id: str, batch_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT batch_id, status, target_count, created_at "
            "FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s",
            (workspace_id, batch_id),
        ).fetchone()
        return self._batch_row(row) if row is not None else None

    @staticmethod
    def _batch_row(row: Any) -> dict[str, object]:
        return {
            "batch_id": row[0],
            "status": row[1],
            "target_count": row[2],
            "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else row[3],
        }

    def jobs(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT job_id, batch_id, status, snapshot_ref, revision, created_at "
            "FROM controlplane.cp_video_jobs WHERE workspace_id = %s "
            "ORDER BY created_at DESC, job_id DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
        return [self._job_row(row) for row in rows]

    def job(self, *, workspace_id: str, job_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT job_id, batch_id, status, snapshot_ref, revision, created_at "
            "FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s",
            (workspace_id, job_id),
        ).fetchone()
        return self._job_row(row) if row is not None else None

    @staticmethod
    def _job_row(row: Any) -> dict[str, object]:
        return {
            "job_id": row[0],
            "batch_id": row[1],
            "status": row[2],
            "snapshot_ref": row[3],
            "revision": row[4],
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else row[5],
        }

    def configs(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT config_revision_id::text, scope_kind, scope_key, config_revision_number, "
            "       revision, content_hash, status, created_at "
            "FROM controlplane.cp_config_revisions WHERE workspace_id = %s "
            "ORDER BY created_at DESC, config_revision_id DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
        return [
            {
                "config_revision_id": row[0],
                "scope_kind": row[1],
                "scope_key": row[2],
                "config_revision_number": row[3],
                "revision": row[4],
                "content_hash": row[5],
                "status": row[6],
                "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else row[7],
            }
            for row in rows
        ]