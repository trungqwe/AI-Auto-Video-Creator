"""Pooled PostgreSQL transaction boundaries for M2-P1."""
from __future__ import annotations

from types import TracebackType
from typing import Any, Self

from psycopg import Connection
from psycopg_pool import ConnectionPool

from .repositories import ActorRepository, AuthSessionRepository, WorkspaceRepository


class SqlUnitOfWork:
    """Own exactly one pooled connection for one transaction scope."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._connection_context: Any = None
        self._connection: Connection[Any] | None = None
        self._workspaces: WorkspaceRepository | None = None
        self._actors: ActorRepository | None = None
        self._auth_sessions: AuthSessionRepository | None = None

    def __enter__(self) -> Self:
        self._connection_context = self._pool.connection()
        self._connection = self._connection_context.__enter__()
        self._workspaces = WorkspaceRepository(self._connection)
        self._actors = ActorRepository(self._connection)
        self._auth_sessions = AuthSessionRepository(self._connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        connection = self._connection
        context = self._connection_context
        try:
            if connection is not None:
                if exc_type is not None:
                    connection.rollback()
                elif connection.info.transaction_status.name != "IDLE":
                    connection.commit()
        finally:
            self._connection = None
            self._connection_context = None
            if context is not None:
                context.__exit__(exc_type, exc_value, traceback)

    @property
    def connection(self) -> Connection[Any]:
        if self._connection is None:
            raise RuntimeError("Unit of Work is not active")
        return self._connection

    @property
    def workspaces(self) -> WorkspaceRepository:
        if self._workspaces is None:
            raise RuntimeError("Unit of Work is not active")
        return self._workspaces

    @property
    def actors(self) -> ActorRepository:
        if self._actors is None:
            raise RuntimeError("Unit of Work is not active")
        return self._actors

    @property
    def auth_sessions(self) -> AuthSessionRepository:
        if self._auth_sessions is None:
            raise RuntimeError("Unit of Work is not active")
        return self._auth_sessions

    def commit(self) -> None:
        self.connection.commit()


class TransactionManager:
    """Factory/coordinator for UoWs; repositories never acquire the pool."""

    def __init__(self, dsn: str, *, pool_max_size: int | None = None) -> None:
        self.dsn = dsn
        self.pool_max_size = pool_max_size or 4
        self._pool: Any = ConnectionPool(
            conninfo=dsn,
            min_size=0,
            max_size=self.pool_max_size,
            open=True,
        )

    def unit_of_work(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._pool)

    def borrow_connection(self) -> Any:
        return self._pool.connection()

    def close(self) -> None:
        self._pool.close()
