"""J-09: AuditRecord append-only (CT-SEC-004; INV-012)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Protocol

# ARCH-RULE-003: the domain layer must not statically import the infrastructure layer.
# The J-02 redactor is resolved at module load instead, so the name stays the same object.
redact_value = import_module('controlplane.infrastructure.security.secret_redaction').redact_value

AUDIT_REQUIRED_ACTIONS: frozenset[str] = frozenset({
    'config_change', 'prompt_change', 'policy_change', 'preset_change',
    'source_add', 'source_disable', 'source_remove', 'source_restore',
    'hook_metadata_edit',
    'account_update', 'account_test', 'account_enable', 'account_disable', 'secret_update',
    'debug_run', 'retry', 'variant_create',
    'cleanup', 'restore', 'recovery',
    'technical_detail_view', 'sensitive_operation',
})
AUDIT_OUTCOMES = ('succeeded', 'failed', 'denied')


class UnknownAuditActionError(ValueError):
    """Action ngoài AUDIT_REQUIRED_ACTIONS (fail-closed)."""


@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    workspace_id: str
    actor_ref: str
    action: str
    resource_ref: str
    revision_before: str | None
    revision_after: str | None
    occurred_at: str
    correlation_id: str
    outcome: str
    redacted_reason: str


class AuditSinkPort(Protocol):
    def append(self, record: AuditRecord) -> None: ...


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _revision(name: str, value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError(f'{name} must be a ref string, a revision number or None')
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f'{name} must be a non-negative revision number')
        return str(value)
    return _text(name, value)


def _occurred_at(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(('Z', 'z')):
            text = text[:-1] + '+00:00'
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError('occurred_at must be an ISO 8601 timestamp') from exc
    else:
        raise TypeError('occurred_at must be an ISO 8601 string or a datetime')
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('occurred_at must include a timezone offset')
    return parsed.isoformat()


def _reason(value: object) -> str:
    if value is None:
        return ''
    if not isinstance(value, str):
        raise TypeError('reason must be a string or None')
    return redact_value(value)


def build_audit_record(
    *,
    audit_id: Any,
    workspace_id: Any,
    actor_ref: Any,
    action: Any,
    resource_ref: Any,
    revision_before: Any,
    revision_after: Any,
    occurred_at: Any,
    correlation_id: Any,
    outcome: Any,
    reason: Any = None,
) -> AuditRecord:
    if not isinstance(action, str) or action not in AUDIT_REQUIRED_ACTIONS:
        raise UnknownAuditActionError('action is not in AUDIT_REQUIRED_ACTIONS')
    if not isinstance(outcome, str) or outcome not in AUDIT_OUTCOMES:
        raise ValueError(f'outcome must be one of {AUDIT_OUTCOMES}')
    return AuditRecord(
        audit_id=_text('audit_id', audit_id),
        workspace_id=_text('workspace_id', workspace_id),
        actor_ref=_text('actor_ref', actor_ref),
        action=action,
        resource_ref=_text('resource_ref', resource_ref),
        revision_before=_revision('revision_before', revision_before),
        revision_after=_revision('revision_after', revision_after),
        occurred_at=_occurred_at(occurred_at),
        correlation_id=_text('correlation_id', correlation_id),
        outcome=outcome,
        redacted_reason=_reason(reason),
    )
