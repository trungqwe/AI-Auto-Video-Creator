"""Fail-closed safety rules for destructive M2-P1 database operations."""
from __future__ import annotations

import re


class DestructiveOperationBlockedError(RuntimeError):
    """The requested destructive operation is outside the test boundary."""


class DestructiveRollbackGuard:
    """Allow rollback only for an exact disposable M2-P1 fixture identity."""

    _DATABASE_RE = re.compile(r"^m2_p1_test_[0-9a-f]+$")

    def assert_allowed(
        self,
        database_name: str,
        *,
        is_test_env: bool,
        expected_database_name: str | None = None,
    ) -> None:
        if (
            not is_test_env
            or expected_database_name is None
            or self._DATABASE_RE.fullmatch(database_name) is None
            or database_name != expected_database_name
            or self._DATABASE_RE.fullmatch(expected_database_name) is None
        ):
            raise DestructiveOperationBlockedError(
                "Destructive rollback requires the exact fixture database identity, a test environment, "
                "and a valid M2-P1 disposable database name."
            )
