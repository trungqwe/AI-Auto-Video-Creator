"""J-15b: AccountRecoveryService (PUC-J-03, CT-STATE-013, CT-ACC-002).

Application service: no probe, no secret access, no I/O. It only applies a receipt already produced by ExternalAccountTester.
"""
from __future__ import annotations

from controlplane.application.config_security.account_test import AccountTestReceipt
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security.external_account import ExternalAccount, recover_after_passing_test
from controlplane.domain.config_security.status_graph import ExternalAccountStatus

_RECOVERABLE = frozenset({ExternalAccountStatus.DEGRADED, ExternalAccountStatus.INVALID})


class AccountRecoveryService:
    """Recover a DEGRADED or INVALID account to ENABLED only when its own passing test receipt is supplied.

    A stale expected_revision raises RevisionConflictError. A failed receipt, a receipt of another account or any other status returns the
    same account unchanged.
    """

    def recover(self, account: ExternalAccount, receipt: AccountTestReceipt, expected_revision: int) -> ExternalAccount:
        if expected_revision != account.revision:
            raise RevisionConflictError(account.revision)
        if receipt.ok is not True or receipt.external_account_id != account.external_account_id:
            return account
        if account.status not in _RECOVERABLE:
            return account
        return recover_after_passing_test(account)
