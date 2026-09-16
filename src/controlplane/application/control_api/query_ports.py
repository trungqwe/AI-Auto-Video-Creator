"""Workspace-scoped read-only Control API query ports."""

from __future__ import annotations

from typing import Any, Callable, Protocol


class ControlQueryPort(Protocol):
    def operations(self, *, workspace_id: str) -> list[dict[str, object]]: ...
    def operation(self, *, workspace_id: str, operation_id: str) -> dict[str, object] | None: ...
    def jobs(self, *, workspace_id: str) -> list[dict[str, object]]: ...
    def job(self, *, workspace_id: str, job_id: str) -> dict[str, object] | None: ...
    def configs(self, *, workspace_id: str) -> list[dict[str, object]]: ...


class ControlApiQueryService:
    def __init__(self, repository_factory: Callable[[Any], ControlQueryPort]) -> None:
        self._repository_factory = repository_factory

    def operations(self, *, connection: Any, workspace_id: str) -> list[dict[str, object]]:
        return self._repository_factory(connection).operations(workspace_id=workspace_id)

    def operation(self, *, connection: Any, workspace_id: str,
                  operation_id: str) -> dict[str, object]:
        item = self._repository_factory(connection).operation(
            workspace_id=workspace_id, operation_id=operation_id,
        )
        if item is None:
            raise LookupError("operation not found")
        return item

    def jobs(self, *, connection: Any, workspace_id: str) -> list[dict[str, object]]:
        return self._repository_factory(connection).jobs(workspace_id=workspace_id)

    def job(self, *, connection: Any, workspace_id: str, job_id: str) -> dict[str, object]:
        item = self._repository_factory(connection).job(workspace_id=workspace_id, job_id=job_id)
        if item is None:
            raise LookupError("job not found")
        return item

    def configs(self, *, connection: Any, workspace_id: str) -> list[dict[str, object]]:
        return self._repository_factory(connection).configs(workspace_id=workspace_id)
