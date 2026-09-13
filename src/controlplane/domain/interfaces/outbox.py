"""Transactional Outbox contract (ADR-0004).

Pure domain abstraction for writing events atomically within the database transaction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class IOutboxWriter(ABC):
    """Interface for writing domain events to transactional outbox."""

    @abstractmethod
    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        deduplication_id: str,
    ) -> str:
        """Atomically append an event to outbox. Returns event_id."""
        raise NotImplementedError("append_event must be implemented by concrete outbox adapter.")
