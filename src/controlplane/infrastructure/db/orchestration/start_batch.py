"""P7A batch creation adapter for the accepted P6 table."""

from __future__ import annotations

from typing import Any


class PostgresStartBatchRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def insert(self, *, workspace_id: str, batch_id: str, target_count: int) -> None:
        self._connection.execute(
            "INSERT INTO controlplane.cp_production_batches "
            "(workspace_id,batch_id,status,target_count) VALUES (%s,%s,'CREATED',%s)",
            (workspace_id, batch_id, target_count),
        )

    def stop(self, *, workspace_id: str, batch_id: str, reason: str) -> bool:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('reason must be a non-empty string')
        cursor = self._connection.execute(
            "UPDATE controlplane.cp_production_batches "
            "SET stop_reason=%s, stopped_at=CURRENT_TIMESTAMP "
            "WHERE workspace_id=%s AND batch_id=%s AND stop_reason IS NULL",
            (reason, workspace_id, batch_id),
        )
        return cursor.rowcount == 1