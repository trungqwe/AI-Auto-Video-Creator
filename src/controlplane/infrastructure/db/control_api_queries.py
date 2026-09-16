"""Read-only PostgreSQL projections for P7A Control API routes."""

from __future__ import annotations

from typing import Any


class PostgresControlQueries:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def operations(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT r.operation_id::text,r.command_id,r.receipt_id::text,r.disposition,"
            "r.resource_ref,r.accepted_at,p.event_kind,p.summary "
            "FROM controlplane.cp_command_receipts r "
            "LEFT JOIN LATERAL (SELECT event_kind,summary FROM controlplane.cp_operation_stream "
            "WHERE workspace_id=r.workspace_id AND operation_id=r.operation_id "
            "ORDER BY stream_event_id DESC LIMIT 1) p ON true "
            "WHERE r.workspace_id=%s AND r.operation_id IS NOT NULL "
            "ORDER BY r.accepted_at DESC,r.receipt_id DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
        return [self._operation_row(row) for row in rows]

    def operation(self, *, workspace_id: str, operation_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT r.operation_id::text,r.command_id,r.receipt_id::text,r.disposition,"
            "r.resource_ref,r.accepted_at,p.event_kind,p.summary "
            "FROM controlplane.cp_command_receipts r "
            "LEFT JOIN LATERAL (SELECT event_kind,summary FROM controlplane.cp_operation_stream "
            "WHERE workspace_id=r.workspace_id AND operation_id=r.operation_id "
            "ORDER BY stream_event_id DESC LIMIT 1) p ON true "
            "WHERE r.workspace_id=%s AND r.operation_id=%s",
            (workspace_id, operation_id),
        ).fetchone()
        return self._operation_row(row) if row is not None else None

    @staticmethod
    def _operation_row(row: Any) -> dict[str, object]:
        # A stream event is not automatically an execution-state fact.
        return {
            "operation_id": row[0], "command_ref": row[1], "receipt_id": row[2],
            "status": "accepted", "resource_refs": [row[4]] if row[4] else [],
            "accepted_at": row[5], "latest_event_kind": row[6],
            "latest_safe_summary": row[7],
        }

    def jobs(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT job_id,batch_id,status,snapshot_ref,revision,created_at "
            "FROM controlplane.cp_video_jobs WHERE workspace_id=%s "
            "ORDER BY created_at DESC,job_id DESC LIMIT 100", (workspace_id,),
        ).fetchall()
        return [self._job_row(row) for row in rows]

    def job(self, *, workspace_id: str, job_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT job_id,batch_id,status,snapshot_ref,revision,created_at "
            "FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id=%s",
            (workspace_id, job_id),
        ).fetchone()
        return self._job_row(row) if row is not None else None

    @staticmethod
    def _job_row(row: Any) -> dict[str, object]:
        return {"job_id": row[0], "batch_id": row[1], "status": row[2],
                "snapshot_ref": row[3], "revision": row[4], "created_at": row[5]}

    def configs(self, *, workspace_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            "SELECT config_revision_id::text,scope_kind,scope_key,config_revision_number,"
            "revision,content_hash,status,created_at "
            "FROM controlplane.cp_config_revisions WHERE workspace_id=%s "
            "ORDER BY created_at DESC,config_revision_id DESC LIMIT 100",
            (workspace_id,),
        ).fetchall()
        return [{
            "config_revision_id": row[0], "scope_kind": row[1], "scope_key": row[2],
            "config_revision_number": row[3], "revision": row[4],
            "content_hash": row[5], "status": row[6], "created_at": row[7],
        } for row in rows]
