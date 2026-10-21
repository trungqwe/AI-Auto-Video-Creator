"""PostgreSQL unit of work of E: outputs and outbox share one pooled connection and one transaction (VoiceUnitOfWork and MediaUnitOfWork)."""

from __future__ import annotations

import contextlib
import datetime
from collections.abc import Callable, Iterator
from typing import Any, Self

from controlplane.domain.interfaces.uow import IUnitOfWork
from voice.persistence.errors import TransactionAlreadyActiveError, TransactionNotActiveError, WorkspaceNotBoundError
from voice.persistence.outbox import PostgresVoiceOutboxWriter
from voice.persistence.output_repository import PostgresOutputRepository


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class PostgresVoiceUnitOfWork(IUnitOfWork):
    """Leaving the context without commit() rolls back outputs and outbox; workspace, actor and correlation come from the keyword arguments or bind() because the ports carry no workspace_id."""

    def __init__(self, manager: Any, *, workspace_id: str | None = None, correlation_id: str = 'voice', actor: str = 'system:voice', recovery_epoch: str | None = None, clock: Callable[[], datetime.datetime] | None = None) -> None:
        self._manager = manager
        self._connection_context: Any = None
        self._connection: Any = None
        self._clock = clock or _utc_now
        self.workspace_id = workspace_id
        self.correlation_id = correlation_id
        self.actor = actor
        self.recovery_epoch = recovery_epoch
        self.outputs = PostgresOutputRepository(self)
        self.outbox = PostgresVoiceOutboxWriter(self)

    @property
    def active(self) -> bool:
        return self._connection is not None

    @property
    def connection(self) -> Any:
        if self._connection is None:
            raise TransactionNotActiveError('UOW_NOT_ACTIVE')
        return self._connection

    def now(self) -> datetime.datetime:
        return self._clock()

    def require_workspace(self) -> str:
        if not self.workspace_id:
            raise WorkspaceNotBoundError('UOW_WORKSPACE_NOT_BOUND')
        return self.workspace_id

    def bind(self, *, workspace_id: str, correlation_id: str | None = None, actor: str | None = None, recovery_epoch: str | None = None) -> Self:
        if self.active:
            raise TransactionAlreadyActiveError('UOW_ALREADY_ACTIVE')
        self.workspace_id = workspace_id
        if correlation_id is not None:
            self.correlation_id = correlation_id
        if actor is not None:
            self.actor = actor
        self.recovery_epoch = recovery_epoch
        return self

    @contextlib.contextmanager
    def reading(self) -> Iterator[Any]:
        """Connection for reads: the transaction connection when active, otherwise one short-lived pooled connection."""
        if self._connection is not None:
            yield self._connection
            return
        with self._manager.borrow_connection() as connection:
            yield connection

    def begin(self) -> None:
        if self._connection is not None:
            raise TransactionAlreadyActiveError('UOW_ALREADY_ACTIVE')
        self.require_workspace()
        context = self._manager.borrow_connection()
        connection = context.__enter__()
        try:
            connection.execute('SELECT 1')  # opens the transaction so nested transaction() blocks are savepoints
        except BaseException as exc:
            context.__exit__(type(exc), exc, exc.__traceback__)
            raise
        self._connection_context, self._connection = context, connection

    def _release(self) -> None:
        context, self._connection_context, self._connection = self._connection_context, None, None
        if context is not None:
            context.__exit__(None, None, None)

    def commit(self) -> None:
        connection = self.connection
        try:
            connection.commit()
        except BaseException:
            self.rollback()
            raise
        self._release()

    def rollback(self) -> None:
        connection = self.connection
        try:
            connection.rollback()
        finally:
            self._release()

    def __enter__(self) -> Self:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._connection is not None:
            self.rollback()
