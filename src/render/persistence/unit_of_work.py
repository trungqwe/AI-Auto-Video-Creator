"""PostgreSQL unit of work for render (PERSIST-F)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from controlplane.domain.interfaces.uow import IUnitOfWork
from render.persistence.outbox import OutboxContext, PostgresRenderOutboxWriter
from render.persistence.repository import PostgresRenderRepository
from render.persistence.tables import (
    PostgresAttemptIndex,
    PostgresReceiptTable,
    PostgresReportTable,
    PostgresTraceTable,
)


class UnitOfWorkNotActiveError(RuntimeError):
    """The unit of work is not active."""


class UnitOfWorkAlreadyActiveError(RuntimeError):
    """The unit of work is already active."""


class PostgresRenderUnitOfWork(IUnitOfWork):
    """Sequential reusable unit of work; each 'with' block borrows one connection."""

    def __init__(
        self,
        manager: Any,
        *,
        workspace_id: str | None = None,
        correlation_id: str | None = None,
        actor: str = 'render',
    ) -> None:
        self._manager = manager
        self._context: Any = None
        self._connection: Any = None
        write = self._active_connection
        read = self._read_connection
        self.renders = PostgresRenderRepository(write, read, workspace_id)
        self.reports = PostgresReportTable(write, read, workspace_id)
        self.receipts = PostgresReceiptTable(write, read, workspace_id)
        self.traces = PostgresTraceTable(write, read, workspace_id)
        self.attempt_index = PostgresAttemptIndex(write, read, workspace_id)
        self.outbox = PostgresRenderOutboxWriter(
            write,
            OutboxContext(workspace_id, correlation_id, actor),
        )

    @property
    def active(self) -> bool:
        return self._connection is not None

    def _active_connection(self) -> Any:
        if not self.active:
            raise UnitOfWorkNotActiveError('UOW_NOT_ACTIVE')
        return self._connection

    @contextmanager
    def _read_connection(self) -> Iterator[Any]:
        if self.active:
            yield self._connection
        else:
            with self._manager.borrow_connection() as connection:
                try:
                    yield connection
                finally:
                    connection.rollback()

    def begin(self) -> None:
        if self.active:
            raise UnitOfWorkAlreadyActiveError('UOW_ALREADY_ACTIVE')
        context = self._manager.borrow_connection()
        connection = context.__enter__()
        self._context = context
        self._connection = connection

    def commit(self) -> None:
        self._active_connection().commit()

    def rollback(self) -> None:
        self._active_connection().rollback()

    def __enter__(self) -> PostgresRenderUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self.active:
            return None
        context = self._context
        connection = self._connection
        self._context = None
        self._connection = None
        try:
            connection.rollback()
        finally:
            context.__exit__(exc_type, exc_val, exc_tb)
        return None