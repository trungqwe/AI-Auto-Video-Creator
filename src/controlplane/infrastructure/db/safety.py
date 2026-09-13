"""Fail-closed safety rules for destructive M2-P1 database operations."""
from __future__ import annotations

import re


class DestructiveOperationBlockedError(RuntimeError):
    """The requested destructive operation is outside the test boundary."""


class DestructiveRollbackGuard:
    """Allow rollback only for an exact disposable M2-P1 fixture identity."""

    _DATABASE_RE = re.compile(r"^m2_p1_test_[0-9a-f]+$")

    def assert_allowed(self, database_name: str, *, is_test_env: bool) -> None:
        if not is_test_env or self._DATABASE_RE.fullmatch(database_name) is None:
            raise DestructiveOperationBlockedError(
                "Destructive rollback is allowed only for an exact M2-P1 disposable test database."
            )
