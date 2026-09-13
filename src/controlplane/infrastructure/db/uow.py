"""Structural M2-P1 Unit-of-Work ports; no transaction behavior exists in RED."""
from __future__ import annotations

from typing import Any


class SqlUnitOfWork:
    """Importable UoW port only; methods intentionally fail until implementation."""

    def __enter__(self) -> SqlUnitOfWork:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.__enter__ is not implemented.")

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.__exit__ is not implemented.")

    @property
    def connection(self) -> Any:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.connection is not implemented.")

    @property
    def workspaces(self) -> Any:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.workspaces is not implemented.")

    @property
    def actors(self) -> Any:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.actors is not implemented.")

    @property
    def auth_sessions(self) -> Any:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.auth_sessions is not implemented.")

    def commit(self) -> None:
        raise NotImplementedError("M2-P1 RED: SqlUnitOfWork.commit is not implemented.")


class TransactionManager:
    """Importable coordinator port only; it owns no connection or transaction in RED."""

    def __init__(self, dsn: str, *, pool_max_size: int | None = None) -> None:
        self.dsn = dsn
        self.pool_max_size = pool_max_size

    def unit_of_work(self) -> SqlUnitOfWork:
        raise NotImplementedError("M2-P1 RED: TransactionManager.unit_of_work is not implemented.")

    def borrow_connection(self) -> Any:
        raise NotImplementedError("M2-P1 RED: TransactionManager.borrow_connection is not implemented.")
