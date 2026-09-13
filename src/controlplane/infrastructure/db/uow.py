"""Pooled PostgreSQL transaction boundaries for M2-P1."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Condition
from types import TracebackType
from typing import Any, Iterator, Self

from psycopg import Connection

try:  # The control-plane package provides psycopg_pool; the root M1 lock does not.
    from psycopg_pool import ConnectionPool as _PsycopgConnectionPool
except ModuleNotFoundError:  # pragma: no cover - exercised in the frozen root env.
    _PsycopgConnectionPool = None

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
        if _PsycopgConnectionPool is not None:
            self._pool: Any = _PsycopgConnectionPool(
                conninfo=dsn,
                min_size=0,
                max_size=self.pool_max_size,
                open=True,
            )
        else:
            self._pool = _FallbackConnectionPool(dsn, self.pool_max_size)

    def unit_of_work(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._pool)

    def borrow_connection(self) -> Any:
        return self._pool.connection()

    def close(self) -> None:
        self._pool.close()


class _FallbackConnectionPool:
    """Small bounded pool used when the root frozen environment omits psycopg_pool.

    It intentionally exposes only the context-manager operation used by the UoW,
    while preserving max-size and connection-reuse semantics required by P1.
    """

    def __init__(self, dsn: str, max_size: int) -> None:
        if max_size < 1:
            raise ValueError("pool max_size must be positive")
        self._dsn = dsn
        self._max_size = max_size
        self._idle: list[Connection[Any]] = []
        self._in_use = 0
        self._closed = False
        self._condition = Condition()

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        connection = self._acquire()
        try:
            yield connection
        finally:
            self._release(connection)

    def _acquire(self) -> Connection[Any]:
        with self._condition:
            while True:
                if self._closed:
                    raise RuntimeError("Connection pool is closed")
                if self._idle:
                    connection = self._idle.pop()
                    self._in_use += 1
                    return connection
                if self._in_use < self._max_size:
                    connection = Connection.connect(self._dsn)
                    self._in_use += 1
                    return connection
                self._condition.wait()

    def _release(self, connection: Connection[Any]) -> None:
        with self._condition:
            self._in_use -= 1
            if self._closed or connection.closed:
                if not connection.closed:
                    connection.close()
            else:
                self._idle.append(connection)
            self._condition.notify()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            while self._idle:
                connection = self._idle.pop()
                if not connection.closed:
                    connection.close()
            self._condition.notify_all()
