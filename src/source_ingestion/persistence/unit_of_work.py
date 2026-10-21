"""PostgreSQL unit of work for source ingestion."""
from __future__ import annotations

from typing import Any

from controlplane.domain.interfaces.uow import IUnitOfWork
from source_ingestion.persistence.outbox import OutboxContext, PostgresSourceOutboxWriter
from source_ingestion.persistence.repositories import (
    PostgresCheckpointRepository,
    PostgresCollectionRunRepository,
    PostgresPackageRepository,
    PostgresReceiptStore,
    PostgresSourceCandidateRepository,
    PostgresSourceRepository,
)


class UnitOfWorkNotActiveError(RuntimeError):
    """The unit of work is not active."""


class UnitOfWorkAlreadyActiveError(RuntimeError):
    """The unit of work is already active."""


class PostgresSourceIngestionUnitOfWork(IUnitOfWork):
    """Sequential reusable unit of work; each 'with' block borrows one connection."""

    def __init__(
        self,
        manager: Any,
        *,
        workspace_id: str | None = None,
        correlation_id: str | None = None,
        actor: str = 'source_ingestion',
    ) -> None:
        self._manager = manager
        self._context: Any = None
        self._connection: Any = None
        provider = self._active_connection
        self.sources = PostgresSourceRepository(provider)
        self.candidates = PostgresSourceCandidateRepository(provider)
        self.runs = PostgresCollectionRunRepository(provider)
        self.packages = PostgresPackageRepository(provider)
        self.checkpoints = PostgresCheckpointRepository(provider)
        self.receipts = PostgresReceiptStore(provider)
        self.outbox = PostgresSourceOutboxWriter(
            provider,
            OutboxContext(workspace_id, correlation_id, actor),
        )

    @property
    def active(self) -> bool:
        return self._connection is not None

    def _active_connection(self) -> Any:
        if not self.active:
            raise UnitOfWorkNotActiveError('UOW_NOT_ACTIVE')
        return self._connection

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

    def __enter__(self) -> PostgresSourceIngestionUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self.active:
            return None
        context = self._context
        connection = self._connection
        self._context = None
        self._connection = None
        # connection.rollback() must run before context.__exit__ because the
        # pool context commits if the transaction is left open.
        try:
            connection.rollback()
        finally:
            context.__exit__(exc_type, exc_val, exc_tb)
        return None
