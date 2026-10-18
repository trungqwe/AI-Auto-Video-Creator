"""SourceCandidate lifecycle for auto-discovered sources (CT-SRC-003A, CT-STATE-002A).

Pure domain rules only: no I/O, persistence or event publishing. Canonicalization,
identity lookup and policy loading are supplied by the caller.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _require_aware(at: object) -> None:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError('at must be a timezone-aware datetime')


class CandidateStatus(str, Enum):
    DISCOVERED = 'DISCOVERED'
    VALIDATING = 'VALIDATING'
    READY_FOR_REGISTRATION = 'READY_FOR_REGISTRATION'
    MATCHED_EXISTING = 'MATCHED_EXISTING'
    BLOCKED_TOMBSTONE = 'BLOCKED_TOMBSTONE'
    REJECTED = 'REJECTED'
    REGISTERED = 'REGISTERED'


TERMINAL_STATUSES = frozenset({
    CandidateStatus.MATCHED_EXISTING,
    CandidateStatus.BLOCKED_TOMBSTONE,
    CandidateStatus.REJECTED,
    CandidateStatus.REGISTERED,
})
_RESOLVED = frozenset({CandidateStatus.MATCHED_EXISTING, CandidateStatus.BLOCKED_TOMBSTONE, CandidateStatus.REJECTED})
ALLOWED_TRANSITIONS: Mapping[CandidateStatus, frozenset[CandidateStatus]] = MappingProxyType({
    CandidateStatus.DISCOVERED: frozenset({CandidateStatus.VALIDATING}),
    CandidateStatus.VALIDATING: _RESOLVED | {CandidateStatus.READY_FOR_REGISTRATION},
    CandidateStatus.READY_FOR_REGISTRATION: _RESOLVED | {CandidateStatus.REGISTERED},
    **{status: frozenset() for status in TERMINAL_STATUSES},
})
WAITING_POLICY = 'WAITING_POLICY'
REVISION_CONFLICT = 'REVISION_CONFLICT'


class CandidateTransitionError(ValueError):
    """Transition not allowed by CT-STATE-002A; terminal candidates are never reopened."""


class IdentityMatchKind(str, Enum):
    NONE = 'NONE'
    EXISTING_SOURCE = 'EXISTING_SOURCE'
    TOMBSTONE = 'TOMBSTONE'


@dataclass(frozen=True)
class IdentityMatch:
    """Result of the source/tombstone identity lookup for a canonical locator."""

    kind: IdentityMatchKind
    ref: str | None = None

    def __post_init__(self) -> None:
        if self.kind is IdentityMatchKind.NONE:
            if self.ref is not None:
                raise ValueError('ref must be None when there is no identity match')
        else:
            _require_text('ref', self.ref)


NO_MATCH = IdentityMatch(IdentityMatchKind.NONE)


@dataclass(frozen=True)
class RegistrationPolicy:
    """Approved Tier/discovery policy decision; classification is never defaulted."""

    revision: str
    auto_registration_enabled: bool
    permitted: bool
    source_kind: str | None = None
    topics: tuple[str, ...] = ()
    tier: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SourceCandidate:
    """Candidate observation (CT-SRC-003A); classification fields stay empty until REGISTERED."""

    candidate_id: str
    workspace_id: str
    observed_locator: str
    canonical_locator: str
    discovery_method: str
    discovery_evidence: str
    source_kind_candidates: tuple[str, ...]
    topic_candidates: tuple[str, ...]
    status: CandidateStatus
    revision: int
    updated_by: str
    updated_at: datetime
    matched_source_ref: str | None = None
    matched_tombstone_ref: str | None = None
    registered_source_ref: str | None = None
    source_kind: str | None = None
    topics: tuple[str, ...] = ()
    tier: str | None = None
    policy_revision: str | None = None
    reason: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass(frozen=True)
class CandidateDecision:
    """Outcome of one command; WAITING_POLICY and REVISION_CONFLICT return the candidate unchanged."""

    candidate: SourceCandidate
    code: str
    current_revision: int
    reason: str | None = None


def discover_candidate(
    *,
    candidate_id: str,
    workspace_id: str,
    observed_locator: str,
    canonical_locator: str,
    discovery_method: str,
    discovery_evidence: str,
    source_kind_candidates: Iterable[str] = (),
    topic_candidates: Iterable[str] = (),
    actor: str,
    at: datetime,
) -> SourceCandidate:
    for name, value in (
        ('candidate_id', candidate_id), ('workspace_id', workspace_id), ('observed_locator', observed_locator),
        ('canonical_locator', canonical_locator), ('discovery_method', discovery_method),
        ('discovery_evidence', discovery_evidence), ('actor', actor),
    ):
        _require_text(name, value)
    _require_aware(at)
    return SourceCandidate(
        candidate_id=candidate_id, workspace_id=workspace_id, observed_locator=observed_locator,
        canonical_locator=canonical_locator, discovery_method=discovery_method,
        discovery_evidence=discovery_evidence, source_kind_candidates=tuple(source_kind_candidates),
        topic_candidates=tuple(topic_candidates), status=CandidateStatus.DISCOVERED, revision=1,
        updated_by=actor, updated_at=at,
    )


def _conflict(candidate: SourceCandidate, expected_revision: int) -> CandidateDecision | None:
    if expected_revision != candidate.revision:
        return CandidateDecision(candidate, REVISION_CONFLICT, candidate.revision, 'expected revision is stale')
    return None


def _require_status(candidate: SourceCandidate, expected: CandidateStatus) -> None:
    if candidate.status is not expected:
        raise CandidateTransitionError(
            f'expected {expected.value}, got {candidate.status.value}; terminal candidates are not reopened'
        )


def _advance(
    candidate: SourceCandidate, target: CandidateStatus, *, actor: str, at: datetime, **changes: object,
) -> CandidateDecision:
    if target not in ALLOWED_TRANSITIONS[candidate.status]:
        raise CandidateTransitionError(f'{candidate.status.value} -> {target.value} is not allowed')
    _require_text('actor', actor)
    _require_aware(at)
    updated = replace(
        candidate, status=target, revision=candidate.revision + 1, updated_by=actor, updated_at=at, **changes,
    )
    return CandidateDecision(updated, target.value, updated.revision, updated.reason)


def _identity_outcome(
    candidate: SourceCandidate, identity: IdentityMatch, *, actor: str, at: datetime,
) -> CandidateDecision | None:
    if identity.kind is IdentityMatchKind.TOMBSTONE:
        return _advance(
            candidate, CandidateStatus.BLOCKED_TOMBSTONE, actor=actor, at=at,
            matched_tombstone_ref=identity.ref, reason='identity matches a removed source tombstone',
        )
    if identity.kind is IdentityMatchKind.EXISTING_SOURCE:
        return _advance(
            candidate, CandidateStatus.MATCHED_EXISTING, actor=actor, at=at,
            matched_source_ref=identity.ref, reason='identity matches an existing source',
        )
    return None


def begin_validation(
    candidate: SourceCandidate, *, expected_revision: int, actor: str, at: datetime,
) -> CandidateDecision:
    conflict = _conflict(candidate, expected_revision)
    if conflict is not None:
        return conflict
    _require_status(candidate, CandidateStatus.DISCOVERED)
    return _advance(candidate, CandidateStatus.VALIDATING, actor=actor, at=at)


def complete_validation(
    candidate: SourceCandidate, *, expected_revision: int, identity: IdentityMatch, validation_passed: bool,
    reason: str | None = None, actor: str, at: datetime,
) -> CandidateDecision:
    conflict = _conflict(candidate, expected_revision)
    if conflict is not None:
        return conflict
    _require_status(candidate, CandidateStatus.VALIDATING)
    resolved = _identity_outcome(candidate, identity, actor=actor, at=at)
    if resolved is not None:
        return resolved
    if not validation_passed:
        _require_text('reason', reason)
        return _advance(candidate, CandidateStatus.REJECTED, actor=actor, at=at, reason=reason)
    return _advance(candidate, CandidateStatus.READY_FOR_REGISTRATION, actor=actor, at=at, reason=reason)


def register_candidate(
    candidate: SourceCandidate, *, expected_revision: int, identity: IdentityMatch,
    policy: RegistrationPolicy | None, new_source_ref: str, actor: str, at: datetime,
) -> CandidateDecision:
    conflict = _conflict(candidate, expected_revision)
    if conflict is not None:
        return conflict
    _require_status(candidate, CandidateStatus.READY_FOR_REGISTRATION)
    resolved = _identity_outcome(candidate, identity, actor=actor, at=at)
    if resolved is not None:
        return resolved
    if policy is None or not policy.auto_registration_enabled:
        return CandidateDecision(
            candidate, WAITING_POLICY, candidate.revision,
            'registration policy is missing or auto-registration is disabled',
        )
    _require_text('policy.revision', policy.revision)
    if not policy.permitted:
        return _advance(
            candidate, CandidateStatus.REJECTED, actor=actor, at=at, policy_revision=policy.revision,
            reason=policy.reason or 'registration policy forbids this candidate',
        )
    if policy.source_kind is None or not policy.topics or policy.tier is None:
        return CandidateDecision(
            candidate, WAITING_POLICY, candidate.revision,
            'policy has not determined source kind, topic and Tier',
        )
    _require_text('new_source_ref', new_source_ref)
    return _advance(
        candidate, CandidateStatus.REGISTERED, actor=actor, at=at, registered_source_ref=new_source_ref,
        source_kind=policy.source_kind, topics=tuple(policy.topics), tier=policy.tier,
        policy_revision=policy.revision, reason=policy.reason,
    )


def resolve_identity(
    canonical_locator: str, *, tombstoned_refs: Mapping[str, str], source_refs: Mapping[str, str],
) -> IdentityMatch:
    if canonical_locator in tombstoned_refs:
        return IdentityMatch(IdentityMatchKind.TOMBSTONE, tombstoned_refs[canonical_locator])
    if canonical_locator in source_refs:
        return IdentityMatch(IdentityMatchKind.EXISTING_SOURCE, source_refs[canonical_locator])
    return NO_MATCH
