"""P2 revision port contract; no PostgreSQL CAS exists during RED."""

from typing import Protocol


class RevisionConflictError(Exception):
    def __init__(self, current_revision: int) -> None:
        super().__init__(f"Revision conflict; current revision is {current_revision}.")
        self.current_revision = current_revision


class RevisionedMutationPort(Protocol):
    def mutate(self, **_: object) -> object:
        """Atomically mutate a revisioned resource through an injected UoW."""
