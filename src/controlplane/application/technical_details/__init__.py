"""Application ports and workspace-scoped technical-detail operations."""

from __future__ import annotations

from typing import Any, Callable, Protocol


class TechnicalDetailRepository(Protocol):
    def record(self, *, workspace_id: str, correlation_id: str, error_type: str,
               stack_trace: str, sanitized_context: dict[str, object]) -> str: ...

    def retrieve(self, *, detail_ref: str, workspace_id: str) -> dict[str, object] | None: ...

    def audit_access(self, *, detail_ref: str, workspace_id: str, actor_id: str,
                     session_id: str, correlation_id: str) -> None: ...


class TechnicalDetailService:
    def __init__(self, repository_factory: Callable[[Any], TechnicalDetailRepository]) -> None:
        self._repository_factory = repository_factory

    def record(self, *, connection: Any, workspace_id: str, correlation_id: str,
               error_type: str, redacted_detail: str) -> str:
        return self._repository_factory(connection).record(
            workspace_id=workspace_id, correlation_id=correlation_id,
            error_type=error_type, stack_trace=redacted_detail, sanitized_context={},
        )

    def retrieve(self, *, connection: Any, detail_ref: str, workspace_id: str,
                 actor_id: str | None = None, session_id: str | None = None,
                 correlation_id: str | None = None) -> dict[str, object]:
        repository = self._repository_factory(connection)
        detail = repository.retrieve(detail_ref=detail_ref, workspace_id=workspace_id)
        if detail is None:
            raise LookupError("technical detail not found")
        if actor_id is not None or session_id is not None:
            if not actor_id or not session_id or not correlation_id:
                raise ValueError("complete audit identity is required")
            repository.audit_access(
                detail_ref=detail_ref, workspace_id=workspace_id,
                actor_id=actor_id, session_id=session_id, correlation_id=correlation_id,
            )
        return detail
