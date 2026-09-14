"""P2 revision port contract; no PostgreSQL CAS exists during RED."""

from typing import Protocol

from controlplane.domain.concurrency import RevisionConflictError


class RevisionedMutationPort(Protocol):
    def mutate(self, **_: object) -> object:
        """Atomically mutate a revisioned resource through an injected UoW."""
