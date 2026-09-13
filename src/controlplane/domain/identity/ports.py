"""Persistence-neutral repository contracts for the M2-P1 identity foundation."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import Actor, AuthSession, Workspace


class IWorkspaceRepository(Protocol):
    def create(self, workspace_id: str, name: str, status: str) -> Workspace: ...

    def get(self, workspace_id: str, target_workspace_id: str) -> Workspace | None: ...

    def list(self, workspace_id: str) -> list[Workspace]: ...

    def update_status(self, workspace_id: str, target_workspace_id: str, status: str) -> Workspace | None: ...


class IActorRepository(Protocol):
    def create(
        self,
        workspace_id: str,
        actor_id: str,
        actor_type: str,
        display_name: str,
        status: str,
    ) -> Actor: ...

    def get(self, workspace_id: str, actor_id: str) -> Actor | None: ...

    def list(self, workspace_id: str) -> list[Actor]: ...

    def update_status(self, workspace_id: str, actor_id: str, status: str) -> Actor | None: ...


class IAuthSessionRepository(Protocol):
    def create(
        self,
        workspace_id: str,
        actor_id: str,
        session_id: str,
        status: str,
        expires_at: datetime | None = None,
    ) -> AuthSession: ...

    def get(self, workspace_id: str, session_id: str) -> AuthSession | None: ...

    def list(self, workspace_id: str) -> list[AuthSession]: ...

    def update_status(self, workspace_id: str, session_id: str, status: str) -> AuthSession | None: ...

