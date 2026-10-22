"""Errors of the PostgreSQL adapter of E: transaction state, workspace binding and unsupported output kind."""

from __future__ import annotations


class TransactionNotActiveError(RuntimeError):
    pass


class TransactionAlreadyActiveError(RuntimeError):
    pass


class WorkspaceNotBoundError(RuntimeError):
    pass


class UnsupportedKindError(ValueError):
    pass
