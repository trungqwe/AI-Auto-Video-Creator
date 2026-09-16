"""Importable P6 application seams; behavior intentionally remains unimplemented."""

from __future__ import annotations

from typing import Any, Callable, Protocol
import uuid

from controlplane.domain.orchestration import (
    AcceptedExecutionResult,
    CapacityAllocation,
    CompletionLedger,
    ExecutionGrant,
    OrchestrationContractError,
    VariantReservation,
)


class OrchestrationRepository(Protocol):
    def reserve_variant(
        self, reservation_id: str, values: dict[str, Any]
    ) -> VariantReservation: ...
    def allocate_capacity(
        self, reservation_id: str, values: dict[str, Any]
    ) -> CapacityAllocation: ...
    def get_capacity(self, workspace_id: str, job_id: str) -> CapacityAllocation: ...
    def set_capacity_state(
        self, workspace_id: str, job_id: str, state: str
    ) -> CapacityAllocation: ...
    def commit_completion(
        self, ledger_id: str, values: dict[str, Any]
    ) -> CompletionLedger: ...


RepositoryFactory = Callable[[object], OrchestrationRepository]


class _Service:
    def __init__(self, repository_factory: RepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def _repository(self, values: dict[str, Any]) -> OrchestrationRepository:
        connection = values.pop("connection", None)
        if connection is None:
            raise TypeError("connection is required")
        return self._repository_factory(connection)


class ExecutionGrantService(_Service):
    def accept_result(self, **kwargs: Any) -> AcceptedExecutionResult:
        self._repository(kwargs)
        grant = kwargs["grant"]
        if not isinstance(grant, ExecutionGrant):
            raise TypeError("grant must be an ExecutionGrant")
        if kwargs["submitted_recovery_epoch"] != grant.recovery_epoch:
            raise OrchestrationContractError("STALE_RECOVERY_EPOCH")
        if kwargs["submitted_generation"] != grant.execution_generation:
            raise OrchestrationContractError("STALE_EXECUTION_GENERATION")
        return AcceptedExecutionResult(grant, str(kwargs["result_ref"]))


class VariantReservationService(_Service):
    def reserve(self, **kwargs: Any) -> VariantReservation:
        repository = self._repository(kwargs)
        return repository.reserve_variant(str(uuid.uuid4()), kwargs)


class BatchCapacityService(_Service):
    def allocate(self, **kwargs: Any) -> CapacityAllocation:
        repository = self._repository(kwargs)
        return repository.allocate_capacity(str(uuid.uuid4()), kwargs)

    def mark_waiting(self, **kwargs: Any) -> CapacityAllocation:
        repository = self._repository(kwargs)
        return repository.get_capacity(kwargs["workspace_id"], kwargs["job_id"])

    def release_terminal(self, **kwargs: Any) -> CapacityAllocation:
        repository = self._repository(kwargs)
        if kwargs["terminal_status"] != "FAILED_FINAL":
            raise OrchestrationContractError("FORBIDDEN_TRANSITION")
        return repository.set_capacity_state(
            kwargs["workspace_id"], kwargs["job_id"], "RELEASED"
        )

    def convert_completion(self, **kwargs: Any) -> CapacityAllocation:
        repository = self._repository(kwargs)
        return repository.set_capacity_state(
            kwargs["workspace_id"], kwargs["job_id"], "CONVERTED"
        )


class CompletionLedgerService(_Service):
    def commit(self, **kwargs: Any) -> CompletionLedger:
        repository = self._repository(kwargs)
        return repository.commit_completion(str(uuid.uuid4()), kwargs)


__all__ = [
    "BatchCapacityService",
    "CompletionLedgerService",
    "ExecutionGrantService",
    "OrchestrationRepository",
    "RepositoryFactory",
    "VariantReservationService",
]
