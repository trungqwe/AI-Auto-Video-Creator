"""Importable P3 DomainEvent shape without behavior during Behavioral RED."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Structural event data holder; validation and persistence are not implemented."""

    contract_name: str
    contract_version: int
    message_id: str
    workspace_id: str
    correlation_id: str
    causation_id: str | None
    trace_context: str | None
    occurred_at: str
    actor: str
    recovery_epoch: int | None
    payload: dict[str, Any]
    event_id: str
    event_name: str
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    producer: str
    schema_version: int
    sensitivity: str
