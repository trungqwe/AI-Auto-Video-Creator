"""Structural PostgreSQL adapter seam for M2-P6 Behavioral RED."""

from __future__ import annotations

from typing import Any


class PostgresOrchestrationRepository:
    """Future P6 adapter over a caller-owned connection; behavior is absent."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection


__all__ = ["PostgresOrchestrationRepository"]
