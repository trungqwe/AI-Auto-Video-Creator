"""Unit of Work interface definition (ADR-0002).

Pure domain abstraction for transactional atomic execution across repositories.
Must not import technical drivers (psycopg, sqlalchemy, etc.).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IUnitOfWork(ABC):
    """Abstract interface for transactional Unit of Work."""

    @abstractmethod
    def begin(self) -> None:
        """Begin a new transaction boundary."""
        raise NotImplementedError("Unit of Work begin() must be implemented by adapter.")

    @abstractmethod
    def commit(self) -> None:
        """Commit all pending changes in the transaction."""
        raise NotImplementedError("Unit of Work commit() must be implemented by adapter.")

    @abstractmethod
    def rollback(self) -> None:
        """Roll back all uncommitted changes."""
        raise NotImplementedError("Unit of Work rollback() must be implemented by adapter.")

    @abstractmethod
    def __enter__(self) -> IUnitOfWork:
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        raise NotImplementedError
