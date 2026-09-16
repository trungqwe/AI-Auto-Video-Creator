"""PostgreSQL technical-detail persistence on a caller-owned connection."""

from __future__ import annotations

from typing import Any
import uuid

from psycopg.types.json import Jsonb


class PostgresTechnicalDetailRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def record(self, *, workspace_id: str, correlation_id: str, error_type: str,
               stack_trace: str, sanitized_context: dict[str, object]) -> str:
        detail_ref = str(uuid.uuid4())
        self._connection.execute(
            "INSERT INTO controlplane.cp_technical_details "
            "(detail_ref,workspace_id,correlation_id,error_type,stack_trace,sanitized_context) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (detail_ref, workspace_id, correlation_id, error_type, stack_trace, Jsonb(sanitized_context)),
        )
        return detail_ref

    def retrieve(self, *, detail_ref: str, workspace_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT detail_ref::text,workspace_id::text,correlation_id,error_type,stack_trace,"
            "sanitized_context,created_at FROM controlplane.cp_technical_details "
            "WHERE detail_ref=%s AND workspace_id=%s",
            (detail_ref, workspace_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "detail_ref": row[0], "workspace_id": row[1], "correlation_id": row[2],
            "error_type": row[3], "stack_trace": row[4],
            "sanitized_context": row[5], "created_at": row[6],
        }

    def audit_access(self, *, detail_ref: str, workspace_id: str, actor_id: str,
                     session_id: str, correlation_id: str) -> None:
        self._connection.execute(
            "INSERT INTO controlplane.cp_technical_detail_access_audit "
            "(access_id,workspace_id,detail_ref,actor_id,session_id,correlation_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), workspace_id, detail_ref, actor_id, session_id, correlation_id),
        )
