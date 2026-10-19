"""J-03: ConfigRevision publish plan, lineage and rollback (CT-CFG-001, D8-J-11).

Pure application function: no I/O, no clock, no DB write and no mutation of its inputs. Only revisions of the same (workspace_id, scope_kind, scope_key) are considered.
config_revision_number (business version) is never mixed with ConfigRevision.revision (concurrency revision).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from controlplane.application.idempotency import request_hash
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus

SCOPE_KINDS = frozenset({'workspace', 'module', 'provider', 'preset', 'policy', 'prompt'})
SENSITIVE_KEY_NAMES = ('password', 'secret', 'token', 'api_key', 'private_key', 'credential')
ROLLBACK_PREFIX = 'ROLLBACK_OF:'
_COMPACT_SENSITIVE = tuple(name.replace('_', '') for name in SENSITIVE_KEY_NAMES)


class StaleBaseRevisionError(Exception):
    """base_config_revision_number is not the highest number of the scope."""


class SecretInConfigError(Exception):
    """The payload contains a sensitive key at some depth."""


class RollbackTargetInvalidError(Exception):
    """The rollback target is missing, invalidated, not published or its hash differs from the payload."""


@dataclass(frozen=True)
class PublishRequest:
    workspace_id: str
    scope_kind: str
    scope_key: str
    base_config_revision_number: int | None
    payload: dict[str, Any]
    effective_at: str | None
    actor_ref: str
    change_reason: str
    rollback_of_number: int | None = None


@dataclass(frozen=True)
class PublishPlan:
    config_revision_number: int
    superseded_config_revision_id: str | None
    content_hash: str
    validation: tuple[str, ...]
    effective_at: str | None


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    compact = ''.join(ch for ch in key.casefold() if ch.isalnum())
    return compact.endswith(_COMPACT_SENSITIVE)


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_is_sensitive_key(key) or _contains_sensitive_key(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(child) for child in value)
    return False


def _check_rollback_target(scope: Sequence[ConfigRevision], number: int, content_hash: str) -> None:
    target = next((revision for revision in scope if revision.config_revision_number == number), None)
    if target is None:
        raise RollbackTargetInvalidError('rollback_target_missing')
    if target.status is ConfigRevisionStatus.INVALIDATED:
        raise RollbackTargetInvalidError('rollback_target_invalidated')
    if target.status is ConfigRevisionStatus.DRAFT:
        raise RollbackTargetInvalidError('rollback_target_not_published')
    if target.content_hash != content_hash:
        raise RollbackTargetInvalidError('rollback_payload_mismatch')


def plan_publish(existing: Sequence[ConfigRevision], request: PublishRequest) -> PublishPlan:
    """Plan the next immutable ConfigRevision of a scope (CT-CFG-001); never touches `existing` or `request`.

    Check order: scope_kind (ValueError 'invalid_scope_kind'), sensitive keys (SecretInConfigError), base number (StaleBaseRevisionError),
    rollback target (RollbackTargetInvalidError). Sensitive keys match case-insensitively on the key with separators removed, as a suffix
    (apiKey, x-api-key, client_secret); max_tokens and secret_handle_ref are not sensitive. Rollback publishes a new revision with the
    target payload hash and the ROLLBACK_OF:<number> marker; it never edits the old revision.
    """
    if request.scope_kind not in SCOPE_KINDS:
        raise ValueError('invalid_scope_kind')
    if _contains_sensitive_key(request.payload):
        raise SecretInConfigError('secret_in_config')
    identity = (request.workspace_id, request.scope_kind, request.scope_key)
    scope = [revision for revision in existing if (revision.workspace_id, revision.scope_kind, revision.scope_key) == identity]
    latest = max((revision.config_revision_number for revision in scope), default=None)
    if request.base_config_revision_number != latest:
        raise StaleBaseRevisionError('stale_base_revision')
    published = [revision for revision in scope if revision.status is ConfigRevisionStatus.PUBLISHED]
    superseded = max(published, key=lambda revision: revision.config_revision_number).config_revision_id if published else None
    content_hash = request_hash(request.payload)
    validation: tuple[str, ...] = ()
    if request.rollback_of_number is not None:
        _check_rollback_target(scope, request.rollback_of_number, content_hash)
        validation = (f'{ROLLBACK_PREFIX}{request.rollback_of_number}',)
    return PublishPlan(
        config_revision_number=(latest or 0) + 1, superseded_config_revision_id=superseded, content_hash=content_hash,
        validation=validation, effective_at=request.effective_at,
    )
