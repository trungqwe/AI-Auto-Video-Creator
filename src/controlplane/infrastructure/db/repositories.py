"""PostgreSQL repositories that only use the connection owned by a UoW."""
from __future__ import annotations

import uuid
from typing import Any

from psycopg import Connection

from controlplane.domain.identity.models import Actor, AuthSession, Workspace
from controlplane.domain.identity.ports import IActorRepository, IAuthSessionRepository, IWorkspaceRepository


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(str(value))


class WorkspaceRepository(IWorkspaceRepository):
    def __init__(self, connection: Connection[Any]) -> None:
        self._connection = connection

    def create(self, workspace_id: str, name: str, status: str) -> Workspace:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) "
            "VALUES (%s, %s, %s) RETURNING workspace_id::text, name, status, created_at, updated_at",
            (_uuid(workspace_id), name, status),
        ).fetchone()
        assert row is not None
        return Workspace(*row)

    def get(self, workspace_id: str, target_workspace_id: str) -> Workspace | None:
        row = self._connection.execute(
            "SELECT workspace_id::text, name, status, created_at, updated_at "
            "FROM controlplane.cp_workspaces WHERE workspace_id = %s AND workspace_id = %s",
            (_uuid(workspace_id), _uuid(target_workspace_id)),
        ).fetchone()
        return Workspace(*row) if row is not None else None

    def list(self, workspace_id: str) -> list[Workspace]:
        rows = self._connection.execute(
            "SELECT workspace_id::text, name, status, created_at, updated_at "
            "FROM controlplane.cp_workspaces WHERE workspace_id = %s ORDER BY workspace_id",
            (_uuid(workspace_id),),
        ).fetchall()
        return [Workspace(*row) for row in rows]

    def update_status(self, workspace_id: str, target_workspace_id: str, status: str) -> Workspace | None:
        row = self._connection.execute(
            "UPDATE controlplane.cp_workspaces SET status = %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE workspace_id = %s AND workspace_id = %s "
            "RETURNING workspace_id::text, name, status, created_at, updated_at",
            (status, _uuid(workspace_id), _uuid(target_workspace_id)),
        ).fetchone()
        return Workspace(*row) if row is not None else None


class ActorRepository(IActorRepository):
    def __init__(self, connection: Connection[Any]) -> None:
        self._connection = connection

    def create(self, workspace_id: str, actor_id: str, actor_type: str, display_name: str, status: str) -> Actor:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_actors "
            "(actor_id, workspace_id, actor_type, display_name, status) "
            "VALUES (%s, %s, %s, %s, %s) "
            "RETURNING actor_id::text, workspace_id::text, actor_type, display_name, status, created_at",
            (_uuid(actor_id), _uuid(workspace_id), actor_type, display_name, status),
        ).fetchone()
        assert row is not None
        return Actor(*row)

    def get(self, workspace_id: str, actor_id: str) -> Actor | None:
        row = self._connection.execute(
            "SELECT actor_id::text, workspace_id::text, actor_type, display_name, status, created_at "
            "FROM controlplane.cp_actors WHERE workspace_id = %s AND actor_id = %s",
            (_uuid(workspace_id), _uuid(actor_id)),
        ).fetchone()
        return Actor(*row) if row is not None else None

    def list(self, workspace_id: str) -> list[Actor]:
        rows = self._connection.execute(
            "SELECT actor_id::text, workspace_id::text, actor_type, display_name, status, created_at "
            "FROM controlplane.cp_actors WHERE workspace_id = %s ORDER BY actor_id",
            (_uuid(workspace_id),),
        ).fetchall()
        return [Actor(*row) for row in rows]

    def update_status(self, workspace_id: str, actor_id: str, status: str) -> Actor | None:
        row = self._connection.execute(
            "UPDATE controlplane.cp_actors SET status = %s "
            "WHERE workspace_id = %s AND actor_id = %s "
            "RETURNING actor_id::text, workspace_id::text, actor_type, display_name, status, created_at",
            (status, _uuid(workspace_id), _uuid(actor_id),),
        ).fetchone()
        return Actor(*row) if row is not None else None


class AuthSessionRepository(IAuthSessionRepository):
    def __init__(self, connection: Connection[Any]) -> None:
        self._connection = connection

    def create(
        self,
        workspace_id: str,
        actor_id: str,
        session_id: str,
        status: str,
        expires_at: Any = None,
    ) -> AuthSession:
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_auth_sessions "
            "(session_id, workspace_id, actor_id, status, expires_at) VALUES (%s, %s, %s, %s, %s) "
            "RETURNING session_id::text, workspace_id::text, actor_id::text, status, created_at, expires_at",
            (_uuid(session_id), _uuid(workspace_id), _uuid(actor_id), status, expires_at),
        ).fetchone()
        assert row is not None
        return AuthSession(*row)

    def get(self, workspace_id: str, session_id: str) -> AuthSession | None:
        row = self._connection.execute(
            "SELECT session_id::text, workspace_id::text, actor_id::text, status, created_at, expires_at "
            "FROM controlplane.cp_auth_sessions WHERE workspace_id = %s AND session_id = %s",
            (_uuid(workspace_id), _uuid(session_id)),
        ).fetchone()
        return AuthSession(*row) if row is not None else None

    def list(self, workspace_id: str) -> list[AuthSession]:
        rows = self._connection.execute(
            "SELECT session_id::text, workspace_id::text, actor_id::text, status, created_at, expires_at "
            "FROM controlplane.cp_auth_sessions WHERE workspace_id = %s ORDER BY session_id",
            (_uuid(workspace_id),),
        ).fetchall()
        return [AuthSession(*row) for row in rows]

    def update_status(self, workspace_id: str, session_id: str, status: str) -> AuthSession | None:
        row = self._connection.execute(
            "UPDATE controlplane.cp_auth_sessions SET status = %s "
            "WHERE workspace_id = %s AND session_id = %s "
            "RETURNING session_id::text, workspace_id::text, actor_id::text, status, created_at, expires_at",
            (status, _uuid(workspace_id), _uuid(session_id)),
        ).fetchone()
        return AuthSession(*row) if row is not None else None
