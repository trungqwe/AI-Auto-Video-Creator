"""Workspace-scoped read-only Control API query ports."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from controlplane.application.projections.list_query import ListQuery, Page


class ControlQueryPort(Protocol):
    def operations(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def operation(self, *, workspace_id: str, operation_id: str) -> dict[str, object] | None: ...
    def batches(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def batch(self, *, workspace_id: str, batch_id: str) -> dict[str, object] | None: ...
    def jobs(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def job(self, *, workspace_id: str, job_id: str) -> dict[str, object] | None: ...
    def configs(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def sources(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def articles(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def events(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def media(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def hooks(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def stage_runs(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def sessions(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def logs(self, *, workspace_id: str, query: ListQuery) -> Page: ...
    def capabilities(self, *, workspace_id: str, query: ListQuery) -> Page: ...


class ControlApiQueryService:
    def __init__(self, repository_factory: Callable[[Any], ControlQueryPort]) -> None:
        self._repository_factory = repository_factory

    def operations(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).operations(workspace_id=workspace_id, query=query)

    def operation(self, *, connection: Any, workspace_id: str,
                  operation_id: str) -> dict[str, object]:
        item = self._repository_factory(connection).operation(
            workspace_id=workspace_id, operation_id=operation_id,
        )
        if item is None:
            raise LookupError("operation not found")
        return item

    def batches(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).batches(workspace_id=workspace_id, query=query)

    def batch(self, *, connection: Any, workspace_id: str, batch_id: str) -> dict[str, object]:
        item = self._repository_factory(connection).batch(
            workspace_id=workspace_id, batch_id=batch_id,
        )
        if item is None:
            raise LookupError("batch not found")
        return item

    def jobs(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).jobs(workspace_id=workspace_id, query=query)

    def job(self, *, connection: Any, workspace_id: str, job_id: str) -> dict[str, object]:
        item = self._repository_factory(connection).job(workspace_id=workspace_id, job_id=job_id)
        if item is None:
            raise LookupError("job not found")
        return item

    def configs(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).configs(workspace_id=workspace_id, query=query)

    def sources(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).sources(workspace_id=workspace_id, query=query)

    def articles(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).articles(workspace_id=workspace_id, query=query)

    def events(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).events(workspace_id=workspace_id, query=query)

    def media(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).media(workspace_id=workspace_id, query=query)

    def hooks(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).hooks(workspace_id=workspace_id, query=query)

    def stage_runs(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).stage_runs(workspace_id=workspace_id, query=query)

    def sessions(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).sessions(workspace_id=workspace_id, query=query)

    def logs(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).logs(workspace_id=workspace_id, query=query)

    def capabilities(self, *, connection: Any, workspace_id: str, query: ListQuery) -> Page:
        return self._repository_factory(connection).capabilities(workspace_id=workspace_id, query=query)