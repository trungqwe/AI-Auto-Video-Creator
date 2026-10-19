"""J-15: ExternalAccountTester with operation receipt (CT-ACC-002).

Application service: no I/O of its own, no route catalog, no account mutation.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import redact_value


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    latency_ms: int | None = None
    error_class: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class AccountTestReceipt:
    receipt_id: str
    operation_key: str
    external_account_id: str
    ok: bool
    latency_ms: int | None
    error_class: str | None
    redacted_detail: str | None
    tested_at: str


class AccountProbePort(Protocol):
    def probe(self, account_ref: str, minimal: bool) -> ProbeResult: ...


class ReceiptStorePort(Protocol):
    def get(self, operation_key: str) -> AccountTestReceipt | None: ...
    def save(self, receipt: AccountTestReceipt) -> None: ...


def _receipt_id(external_account_id: str, operation_key: str) -> str:
    digest = hashlib.sha256(f'{external_account_id}|{operation_key}'.encode('utf-8')).hexdigest()
    return f'acctest-{digest[:24]}'


class ExternalAccountTester:
    """Probe an external account once per operation_key and return a redacted receipt (CT-ACC-002).

    Idempotent: a stored receipt is returned without probing again. The probe is always the minimal request. A REVOKED account is never
    probed. A raising probe becomes an ok=False receipt whose error_class is the exception class name. The account is never modified and
    there is no enable, disable or routing method.
    """

    def __init__(self, probe: AccountProbePort, receipts: ReceiptStorePort, clock: Callable[[], str]) -> None:
        self._probe, self._receipts, self._clock = probe, receipts, clock

    def run(self, account: ExternalAccount, operation_key: str) -> AccountTestReceipt:
        if not isinstance(operation_key, str) or not operation_key:
            raise ValueError('operation_key must be a non-empty string')
        existing = self._receipts.get(operation_key)
        if existing is not None:
            return existing
        ok, latency_ms, error_class, detail = self._outcome(account)
        receipt = AccountTestReceipt(
            receipt_id=_receipt_id(account.external_account_id, operation_key), operation_key=operation_key,
            external_account_id=account.external_account_id, ok=ok, latency_ms=latency_ms, error_class=redact_value(error_class),
            redacted_detail=redact_value(detail), tested_at=self._clock(),
        )
        self._receipts.save(receipt)
        return receipt

    def _outcome(self, account: ExternalAccount) -> tuple[bool, int | None, str | None, str | None]:
        if account.status is ExternalAccountStatus.REVOKED:
            return False, None, 'REVOKED', None
        try:
            result = self._probe.probe(account_ref=account.external_account_id, minimal=True)
            return bool(result.ok), result.latency_ms, result.error_class, result.detail
        except Exception as exc:
            return False, None, type(exc).__name__, redact_value(exc)
