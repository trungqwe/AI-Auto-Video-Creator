"""Workspace, actor and AuthSession application services."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypeVar


class UnitOfWorkFactory(Protocol):
    """Application-facing factory boundary; it owns no raw DSN or connection."""

    def unit_of_work(self) -> Any:
        """Create a Unit of Work whose repositories share its owned connection."""
        ...


T = TypeVar("T")


def _run(factory: UnitOfWorkFactory, operation: Any) -> T:
    with factory.unit_of_work() as unit_of_work:
        return operation(unit_of_work)


class WorkspaceUseCases:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def create(self, workspace_id: str, name: str, status: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.workspaces.create(workspace_id, name, status),
        )

    def get(self, workspace_id: str, target_workspace_id: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.workspaces.get(workspace_id, target_workspace_id),
        )

    def list(self, workspace_id: str) -> list[Any]:
        return _run(self._unit_of_work_factory, lambda uow: uow.workspaces.list(workspace_id))

    def update_status(self, workspace_id: str, target_workspace_id: str, status: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.workspaces.update_status(workspace_id, target_workspace_id, status),
        )


class ActorUseCases:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def create(
        self,
        workspace_id: str,
        actor_id: str,
        actor_type: str,
        display_name: str,
        status: str,
    ) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.actors.create(
                workspace_id, actor_id, actor_type, display_name, status
            ),
        )

    def get(self, workspace_id: str, actor_id: str) -> Any:
        return _run(self._unit_of_work_factory, lambda uow: uow.actors.get(workspace_id, actor_id))

    def list(self, workspace_id: str) -> list[Any]:
        return _run(self._unit_of_work_factory, lambda uow: uow.actors.list(workspace_id))

    def update_status(self, workspace_id: str, actor_id: str, status: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.actors.update_status(workspace_id, actor_id, status),
        )


class AuthSessionUseCases:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def create(
        self,
        workspace_id: str,
        actor_id: str,
        session_id: str,
        status: str,
        expires_at: datetime | None = None,
    ) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.auth_sessions.create(workspace_id, actor_id, session_id, status, expires_at),
        )

    def get(self, workspace_id: str, session_id: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.auth_sessions.get(workspace_id, session_id),
        )

    def list(self, workspace_id: str) -> list[Any]:
        return _run(self._unit_of_work_factory, lambda uow: uow.auth_sessions.list(workspace_id))

    def revoke(self, workspace_id: str, session_id: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.auth_sessions.update_status(workspace_id, session_id, "revoked"),
        )

    def expire(self, workspace_id: str, session_id: str) -> Any:
        return _run(
            self._unit_of_work_factory,
            lambda uow: uow.auth_sessions.update_status(workspace_id, session_id, "expired"),
        )
