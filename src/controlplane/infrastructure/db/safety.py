"""Structural migration-safety port; no destructive behavior exists in RED."""
from __future__ import annotations


class DestructiveOperationBlockedError(RuntimeError):
    """Expected GREEN error for a non-fixture destructive rollback attempt."""


class DestructiveRollbackGuard:
    """Importable guard port only; validation is implemented after valid RED."""

    def assert_allowed(self, database_name: str, *, is_test_env: bool) -> None:
        raise NotImplementedError(
            "M2-P1 RED: DestructiveRollbackGuard.assert_allowed is not implemented."
        )
