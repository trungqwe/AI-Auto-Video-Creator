"""PostgreSQL session binding adapter on a caller-owned connection."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class PostgresSessionRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def create(self, *, session_id: str, workspace_id: str, actor_id: str,
               token_hash: bytes, expires_at: datetime) -> None:
        self._connection.execute(
            "INSERT INTO controlplane.cp_auth_sessions "
            "(session_id,workspace_id,actor_id,status,token_hash,expires_at) "
            "VALUES (%s,%s,%s,'ACTIVE',%s,%s)",
            (session_id, workspace_id, actor_id, token_hash, expires_at),
        )

    def resolve(self, *, token_hash: bytes) -> dict[str, str] | None:
        row = self._connection.execute(
            "SELECT s.session_id::text,s.workspace_id::text,s.actor_id::text "
            "FROM controlplane.cp_auth_sessions s "
            "JOIN controlplane.cp_workspaces w ON w.workspace_id=s.workspace_id "
            "JOIN controlplane.cp_actors a ON a.workspace_id=s.workspace_id AND a.actor_id=s.actor_id "
            "WHERE s.token_hash=%s AND s.status='ACTIVE' AND s.expires_at>CURRENT_TIMESTAMP "
            "AND w.status='ACTIVE' AND a.status='ACTIVE'",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        return {"session_id": row[0], "workspace_id": row[1], "actor_id": row[2]}
