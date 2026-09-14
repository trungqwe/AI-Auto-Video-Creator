"""Structural P3 event contracts; behavioral semantics remain RED-gated."""

from .contracts import DomainEvent, ensure_safe_event_payload

__all__ = ["DomainEvent", "ensure_safe_event_payload"]
