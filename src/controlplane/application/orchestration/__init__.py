"""Importable P6 application seams; behavior intentionally remains unimplemented."""

from __future__ import annotations

from typing import Any


class ExecutionGrantService:
    def accept_result(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-001 execution grant fencing is not implemented")


class VariantReservationService:
    def reserve(self, **kwargs: Any) -> object:
        raise NotImplementedError("P6-002 variant reservation CAS is not implemented")


class BatchCapacityService:
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


class CompletionLedgerService:
    def commit(self, **kwargs: Any) -> object:
        raise NotImplementedError(
            "P6-004 completion ledger persistence is not implemented"
        )


__all__ = [
    "BatchCapacityService",
    "CompletionLedgerService",
    "ExecutionGrantService",
    "VariantReservationService",
]
