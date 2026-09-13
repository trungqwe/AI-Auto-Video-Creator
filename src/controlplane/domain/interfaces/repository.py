"""Generic Repository interface definition.

Pure domain abstraction for entity persistence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar


T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T, ID]):
    """Generic repository contract for pure domain entities."""

    @abstractmethod
    def get_by_id(self, entity_id: ID) -> Optional[T]:
        """Fetch entity by its unique identifier."""
        raise NotImplementedError("get_by_id must be implemented by concrete repository.")

    @abstractmethod
    def save(self, entity: T) -> None:
        """Persist entity to underlying storage."""
        raise NotImplementedError("save must be implemented by concrete repository.")

    @abstractmethod
    def delete(self, entity_id: ID) -> None:
        """Delete entity by identifier."""
        raise NotImplementedError("delete must be implemented by concrete repository.")
