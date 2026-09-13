"""State Machine contract for Control Plane operations and workflows (INV-001..005).

Pure domain abstraction for state transitions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Sequence, TypeVar


StateT = TypeVar("StateT")
EventT = TypeVar("EventT")


class IStateMachine(ABC, Generic[StateT, EventT]):
    """Pure domain state machine interface."""

    @property
    @abstractmethod
    def current_state(self) -> StateT:
        """Return the current active state."""
        raise NotImplementedError

    @abstractmethod
    def allowed_transitions(self) -> Sequence[EventT]:
        """Return list of allowed events from the current state."""
        raise NotImplementedError

    @abstractmethod
    def transition(self, event: EventT) -> StateT:
        """Execute a state transition triggered by event, or raise domain transition error."""
        raise NotImplementedError
