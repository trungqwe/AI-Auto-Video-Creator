"""Pure P3 domain-event contract and payload safety boundary."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Immutable, persistence-safe event envelope."""

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

    def __post_init__(self) -> None:
        ensure_safe_event_payload(self.payload)


def ensure_safe_event_payload(payload: Any) -> None:
    """Reject the narrow set of unsafe event materials before persistence."""
    def reject() -> None:
        raise ValueError("unsafe domain event payload")

    def walk(value: Any) -> None:
        if isinstance(value, (bytes, bytearray, memoryview)):
            reject()
        if isinstance(value, str):
            if re.search(r"(?:password|secret|token)\s*[:=]", value, re.IGNORECASE) or re.search(r"traceback|stack trace", value, re.IGNORECASE):
                reject()
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if re.search(r"password|secret|token", str(key), re.IGNORECASE):
                    reject()
                walk(child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(payload)
