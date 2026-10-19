"""J-10: UpdateSecret write-only and SecretStorePort (CT-SEC-001; INV-012)."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from controlplane.domain.config_security.audit_record import AuditSinkPort, build_audit_record
from controlplane.infrastructure.security.secret_redaction import REDACTED, SecretValue, redact_exception

VALIDATION_STATES = ('unvalidated', 'valid', 'invalid')
_FORBIDDEN_REF_MARKERS = ('://', 'token=', 'secret=')
Clock = Callable[[], datetime]


class SecretStorePort(Protocol):
    def put(self, secret_ref: str, value: SecretValue) -> int: ...
    def revoke(self, secret_ref: str, version: int) -> None: ...
    def current_version(self, secret_ref: str) -> int | None: ...


class SecretUpdateError(Exception):
    """Secret store or audit sink failed; the message is redacted and never holds the secret value."""


@dataclass(frozen=True)
class SecretUpdateReceipt:
    secret_ref: str
    account_ref: str
    alias_ref: str
    version: int
    fingerprint: str
    last_updated_at: str
    validation_state: str
    actor_ref: str


def _non_empty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _component(name: str, value: object) -> str:
    text = _non_empty(name, value)
    lowered = text.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_REF_MARKERS):
        raise ValueError(f'{name} must not contain a URL or credential marker')
    return text


def _scrub(text: str, value: SecretValue) -> str:
    raw = value.reveal()
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode('utf-8', errors='replace')
    if isinstance(raw, str) and raw:
        text = text.replace(raw, REDACTED)
    return text


class UpdateSecretService:
    """Write-only secret update; there is no get, read or reveal API (INV-012)."""

    def __init__(self, store: SecretStorePort, audit_sink: AuditSinkPort, clock: Clock) -> None:
        self._store = store
        self._audit_sink = audit_sink
        self._clock = clock

    def update(self, workspace_id: Any, account_ref: Any, alias_ref: Any, value: Any, actor_ref: Any, correlation_id: Any, validator: Callable[[SecretValue], Any] | None = None) -> SecretUpdateReceipt:
        if not isinstance(value, SecretValue):
            raise TypeError('value must be a SecretValue')
        workspace = _component('workspace_id', workspace_id)
        account = _component('account_ref', account_ref)
        alias = _component('alias_ref', alias_ref)
        actor = _non_empty('actor_ref', actor_ref)
        correlation = _non_empty('correlation_id', correlation_id)
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError('clock must return an aware datetime')
        secret_ref = f'{workspace}/{account}/{alias}'
        before: Any = None
        version: Any = None
        failure: str | None = None
        try:
            before = self._store.current_version(secret_ref)
            version = self._store.put(secret_ref, value)
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise ValueError('secret store returned an invalid version')
        except Exception as exc:
            failure = _scrub(redact_exception(exc), value)
        if failure is not None:
            self._append(workspace, secret_ref, actor, correlation, now, 'failed', before, None, failure, value)
            raise SecretUpdateError(f'secret_store_failed: {failure}')
        state, note = 'unvalidated', ''
        if validator is not None:
            try:
                state = 'valid' if validator(value) is True else 'invalid'
            except Exception as exc:
                state, note = 'invalid', _scrub(redact_exception(exc), value)
        reason = f'validation_state={state}' + (f'; validator_error={note}' if note else '')
        self._append(workspace, secret_ref, actor, correlation, now, 'succeeded', before, version, reason, value)
        return SecretUpdateReceipt(
            secret_ref=secret_ref, account_ref=account, alias_ref=alias, version=version, fingerprint=f'v{version}',
            last_updated_at=now.isoformat(), validation_state=state, actor_ref=actor,
        )

    def _append(self, workspace_id: str, secret_ref: str, actor_ref: str, correlation_id: str, now: datetime, outcome: str, before: Any, after: Any, reason: str, value: SecretValue) -> None:
        record = build_audit_record(
            audit_id=str(uuid.uuid4()), workspace_id=workspace_id, actor_ref=actor_ref, action='secret_update', resource_ref=secret_ref,
            revision_before=before, revision_after=after, occurred_at=now, correlation_id=correlation_id, outcome=outcome, reason=reason,
        )
        failure: str | None = None
        try:
            self._audit_sink.append(record)
        except Exception as exc:
            failure = _scrub(redact_exception(exc), value)
        if failure is not None:
            raise SecretUpdateError(f'audit_sink_failed: {failure}')
