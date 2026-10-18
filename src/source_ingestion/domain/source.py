"""Source aggregate and lifecycle transitions (CT-STATE-001, CT-SRC-001..003)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ForbiddenTransitionError

RESTORE_POLICY_DISALLOWED = "RESTORE_POLICY_DISALLOWED"


class SourceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    REMOVED_TOMBSTONE = "REMOVED_TOMBSTONE"


@dataclass(frozen=True)
class SourcePolicy:
    """Policy-supplied value sets; this module hard-codes no source kind, Tier or metadata key."""

    policy_revision: str
    source_kinds: frozenset[str]
    tiers: frozenset[str]
    admin_metadata_keys: frozenset[str]


@dataclass(frozen=True)
class Source:
    source_id: str
    workspace_id: str
    canonical_locator: str
    name: str
    source_kind: str
    tier: str
    topics: frozenset[str]
    notes: str
    admin_metadata: tuple[tuple[str, str], ...]
    status: SourceStatus
    status_reason: str | None
    previous_status: SourceStatus | None
    policy_revision: str
    revision: int
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value


def _require_time(at: object) -> datetime:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("at must be a timezone-aware datetime.")
    return at


def _require_policy(policy: object) -> SourcePolicy:
    if not isinstance(policy, SourcePolicy) or not policy.source_kinds or not policy.tiers:
        raise ValueError("policy must supply source kinds and Tiers.")
    _require_text(policy.policy_revision, "policy_revision")
    return policy


def _require_member(value: object, allowed: frozenset[str], field: str) -> str:
    text = _require_text(value, field)
    if text not in allowed:
        raise ValueError(f"{field} is not allowed by the supplied policy.")
    return text


def _normalize_topics(topics: Iterable[str]) -> frozenset[str]:
    if isinstance(topics, str):
        raise ValueError("topics must be a collection of strings.")
    normalized = frozenset(_require_text(topic, "topic") for topic in topics)
    if not normalized:
        raise ValueError("topics must not be empty.")
    return normalized


def _normalize_admin_metadata(admin_metadata: Mapping[str, str], policy: SourcePolicy) -> tuple[tuple[str, str], ...]:
    for key, value in admin_metadata.items():
        if _require_text(key, "admin_metadata key") not in policy.admin_metadata_keys:
            raise ValueError("admin_metadata key is not published by the supplied policy.")
        if not isinstance(value, str):
            raise ValueError("admin_metadata values must be strings.")
    return tuple(sorted(admin_metadata.items()))


def _require_notes(notes: object) -> str:
    if not isinstance(notes, str):
        raise ValueError("notes must be a string.")
    return notes


def _require_flag(collection_enabled: object) -> bool:
    if not isinstance(collection_enabled, bool):
        raise ValueError("collection_enabled must be a bool.")
    return collection_enabled


def _check_revision(source: Source, expected_revision: int) -> None:
    if expected_revision != source.revision:
        raise RevisionConflictError(source.revision)


def _forbid(source: Source, requested: SourceStatus) -> ForbiddenTransitionError:
    return ForbiddenTransitionError(
        aggregate_type="source",
        current_state=source.status,
        requested_next_state=requested,
        current_revision=source.revision,
    )


def _mutate(source: Source, *, actor: str, at: datetime, **changes: object) -> Source:
    return replace(
        source,
        revision=source.revision + 1,
        updated_by=_require_text(actor, "actor"),
        updated_at=_require_time(at),
        **changes,
    )


def register_source(
    *,
    source_id: str,
    workspace_id: str,
    canonical_locator: str,
    name: str,
    source_kind: str,
    tier: str,
    topics: Iterable[str],
    notes: str,
    collection_enabled: bool,
    admin_metadata: Mapping[str, str],
    actor: str,
    at: datetime,
    policy: SourcePolicy,
) -> Source:
    policy = _require_policy(policy)
    return Source(
        source_id=_require_text(source_id, "source_id"),
        workspace_id=_require_text(workspace_id, "workspace_id"),
        canonical_locator=_require_text(canonical_locator, "canonical_locator"),
        name=_require_text(name, "name"),
        source_kind=_require_member(source_kind, policy.source_kinds, "source_kind"),
        tier=_require_member(tier, policy.tiers, "tier"),
        topics=_normalize_topics(topics),
        notes=_require_notes(notes),
        admin_metadata=_normalize_admin_metadata(admin_metadata, policy),
        status=SourceStatus.ACTIVE if _require_flag(collection_enabled) else SourceStatus.DISABLED,
        status_reason=None,
        previous_status=None,
        policy_revision=policy.policy_revision,
        revision=1,
        created_by=_require_text(actor, "actor"),
        created_at=_require_time(at),
        updated_by=actor,
        updated_at=at,
    )


def update_source_metadata(
    source: Source,
    *,
    expected_revision: int,
    actor: str,
    at: datetime,
    policy: SourcePolicy,
    tier: str | None = None,
    topics: Iterable[str] | None = None,
    notes: str | None = None,
    collection_enabled: bool | None = None,
    admin_metadata: Mapping[str, str] | None = None,
) -> Source:
    _check_revision(source, expected_revision)
    if source.status is SourceStatus.REMOVED_TOMBSTONE:
        raise _forbid(source, SourceStatus.REMOVED_TOMBSTONE)
    policy = _require_policy(policy)
    changes: dict[str, object] = {}
    if tier is not None:
        changes["tier"] = _require_member(tier, policy.tiers, "tier")
    if topics is not None:
        changes["topics"] = _normalize_topics(topics)
    if notes is not None:
        changes["notes"] = _require_notes(notes)
    if admin_metadata is not None:
        changes["admin_metadata"] = _normalize_admin_metadata(admin_metadata, policy)
    if collection_enabled is not None:
        status = SourceStatus.ACTIVE if _require_flag(collection_enabled) else SourceStatus.DISABLED
        if status is not source.status:
            changes.update(status=status, status_reason=None)
    if not changes:
        raise ValueError("update requires at least one metadata change.")
    return _mutate(source, actor=actor, at=at, policy_revision=policy.policy_revision, **changes)


def enable_source(source: Source, *, expected_revision: int, actor: str, at: datetime) -> Source:
    _check_revision(source, expected_revision)
    if source.status is not SourceStatus.DISABLED:
        raise _forbid(source, SourceStatus.ACTIVE)
    return _mutate(source, actor=actor, at=at, status=SourceStatus.ACTIVE, status_reason=None)


def disable_source(
    source: Source, *, expected_revision: int, actor: str, at: datetime, reason: str | None = None
) -> Source:
    _check_revision(source, expected_revision)
    if source.status is not SourceStatus.ACTIVE:
        raise _forbid(source, SourceStatus.DISABLED)
    if reason is not None:
        _require_text(reason, "reason")
    return _mutate(source, actor=actor, at=at, status=SourceStatus.DISABLED, status_reason=reason)


def remove_source(
    source: Source, *, expected_revision: int, actor: str, at: datetime, reason: str | None = None
) -> Source:
    _check_revision(source, expected_revision)
    if source.status is SourceStatus.REMOVED_TOMBSTONE:
        raise _forbid(source, SourceStatus.REMOVED_TOMBSTONE)
    if reason is not None:
        _require_text(reason, "reason")
    return _mutate(
        source,
        actor=actor,
        at=at,
        status=SourceStatus.REMOVED_TOMBSTONE,
        status_reason=reason,
        previous_status=source.status,
    )


def restore_source(
    source: Source, *, expected_revision: int, actor: str, at: datetime, policy: SourcePolicy
) -> Source:
    _check_revision(source, expected_revision)
    if source.status is not SourceStatus.REMOVED_TOMBSTONE or source.previous_status is None:
        raise _forbid(source, SourceStatus.ACTIVE)
    policy = _require_policy(policy)
    allowed = source.source_kind in policy.source_kinds and source.tier in policy.tiers
    return _mutate(
        source,
        actor=actor,
        at=at,
        status=source.previous_status if allowed else SourceStatus.DISABLED,
        status_reason=None if allowed else RESTORE_POLICY_DISALLOWED,
        previous_status=None,
        policy_revision=policy.policy_revision,
    )


__all__ = [
    "RESTORE_POLICY_DISALLOWED",
    "Source",
    "SourcePolicy",
    "SourceStatus",
    "disable_source",
    "enable_source",
    "register_source",
    "remove_source",
    "restore_source",
    "update_source_metadata",
]
