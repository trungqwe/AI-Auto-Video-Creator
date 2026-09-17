"""Read-only, workspace-scoped SSE queries on a caller-owned connection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class StreamRow:
    stream_event_id: int
    resource_type: str
    resource_id: str
    resource_revision: int
    event_kind: str
    occurred_at: datetime
    recorded_at: datetime
    summary: str
    correlation_id: str


class PostgresSseReader:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def _query(self, sql: str, params: tuple[object, ...]) -> Any:
        # Borrowed P1 connections use a transaction; LOCAL expires on pool return.
        self._connection.execute("SET LOCAL statement_timeout = 5000")
        return self._connection.execute(sql, params)

    def workspace_high_water(self, *, workspace_id: str) -> int:
        return self._query(
            "SELECT COALESCE(MAX(stream_event_id), 0) "
            "FROM controlplane.cp_operation_stream WHERE workspace_id=%s",
            (workspace_id,),
        ).fetchone()[0]

    def retention_watermark(self, *, workspace_id: str) -> int | None:
        row = self._query(
            "SELECT minimum_available_cursor "
            "FROM controlplane.cp_operation_stream_retention_watermarks "
            "WHERE workspace_id=%s", (workspace_id,),
        ).fetchone()
        return None if row is None else row[0]

    def cursor_exists(self, *, workspace_id: str, cursor: int) -> bool:
        return self._query(
            "SELECT EXISTS (SELECT 1 FROM controlplane.cp_operation_stream "
            "WHERE workspace_id=%s AND stream_event_id=%s)",
            (workspace_id, cursor),
        ).fetchone()[0]

    def fetch_workspace_page(self, *, workspace_id: str, after_cursor: int,
                             limit: int = 100) -> list[StreamRow]:
        if not 1 <= limit <= 100 or after_cursor < 0:
            raise ValueError("invalid SSE page bound")
        rows = self._query(
            "SELECT stream_event_id, resource_type, resource_id, resource_revision, "
            "event_kind, occurred_at, recorded_at, summary, correlation_id "
            "FROM controlplane.cp_operation_stream "
            "WHERE workspace_id=%s AND stream_event_id>%s "
            "ORDER BY stream_event_id ASC LIMIT %s",
            (workspace_id, after_cursor, limit),
        ).fetchall()
        return [StreamRow(*row) for row in rows]
