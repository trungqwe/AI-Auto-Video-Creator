"""Structural public use-case ports for M2-P1 identity persistence.

There is deliberately no generic Workspace or Actor delete port.  Lifecycle
changes are limited to status mutation, AuthSession revoke, and AuthSession
expire when the implementation phase is separately authorized.
"""
from __future__ import annotations

from typing import Any


class WorkspaceUseCases:
    """Importable workspace use-case port; behavior is intentionally absent in RED."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def get(self, workspace_id: str, target_workspace_id: str) -> Any:
        raise NotImplementedError("M2-P1 RED: WorkspaceUseCases.get is not implemented.")

    def list(self, workspace_id: str) -> list[Any]:
        raise NotImplementedError("M2-P1 RED: WorkspaceUseCases.list is not implemented.")

    def update_status(self, workspace_id: str, target_workspace_id: str, status: str) -> Any:
        raise NotImplementedError("M2-P1 RED: WorkspaceUseCases.update_status is not implemented.")


class ActorUseCases:
    """Importable actor use-case port; behavior is intentionally absent in RED."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def get(self, workspace_id: str, actor_id: str) -> Any:
        raise NotImplementedError("M2-P1 RED: ActorUseCases.get is not implemented.")

    def list(self, workspace_id: str) -> list[Any]:
        raise NotImplementedError("M2-P1 RED: ActorUseCases.list is not implemented.")

    def update_status(self, workspace_id: str, actor_id: str, status: str) -> Any:
        raise NotImplementedError("M2-P1 RED: ActorUseCases.update_status is not implemented.")


class AuthSessionUseCases:
    """Importable session use-case port; behavior is intentionally absent in RED."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def revoke(self, workspace_id: str, session_id: str) -> Any:
        raise NotImplementedError("M2-P1 RED: AuthSessionUseCases.revoke is not implemented.")

    def expire(self, workspace_id: str, session_id: str) -> Any:
        raise NotImplementedError("M2-P1 RED: AuthSessionUseCases.expire is not implemented.")
