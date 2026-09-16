"""Importable P6 application seams; behavior intentionally remains unimplemented."""

from __future__ import annotations

from typing import Any, Callable, Protocol


class OrchestrationRepository(Protocol):
    """Persistence output port for future P6 behavior."""


RepositoryFactory = Callable[[object], OrchestrationRepository]


class _Service:
    def __init__(self, repository_factory: RepositoryFactory) -> None:
        self._repository_factory = repository_factory


class ExecutionGrantService(_Service):
    def accept_result(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-001 execution grant fencing is not implemented")


class VariantReservationService(_Service):
    def reserve(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-002 variant reservation CAS is not implemented")


class BatchCapacityService(_Service):
    def allocate(self, **kwargs: Any) -> object:
        raise NotImplementedError(
            "P6-003 batch capacity persistence is not implemented"
        )

    def mark_waiting(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-003 batch capacity lifecycle is not implemented")

    def release_terminal(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-003 batch capacity lifecycle is not implemented")

    def convert_completion(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-003 completion conversion is not implemented")


class CompletionLedgerService(_Service):
    def commit(self, **kwargs: Any) -> object:
        raise NotImplementedError(
            "P6-004 completion ledger persistence is not implemented"
        )


__all__ = [
    "BatchCapacityService",
    "CompletionLedgerService",
    "ExecutionGrantService",
    "OrchestrationRepository",
    "RepositoryFactory",
    "VariantReservationService",
]
