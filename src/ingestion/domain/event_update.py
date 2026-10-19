"""Event update rule of module B (CT-CNT-005, CT-STATE-004, D8-B-07).

Repost threshold and shingle size come from the event update policy revision passed by the caller; claims are opaque refs from a ClaimCandidateProvider.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ingestion.domain.article import ArticleRevision
from ingestion.domain.fingerprint import jaccard, shingles

ACCEPTED_NEW_DEVELOPMENT = 'ACCEPTED_NEW_DEVELOPMENT'
REJECTED_REPOST = 'REJECTED_REPOST'
REJECTED_NO_NEW_FACT = 'REJECTED_NO_NEW_FACT'
UNCERTAIN = 'UNCERTAIN'
STATES = (ACCEPTED_NEW_DEVELOPMENT, REJECTED_REPOST, REJECTED_NO_NEW_FACT, UNCERTAIN)
STATE_PROPOSED = 'PROPOSED'
POLICY_REVISION = 'event_update_policy_revision'
REPOST_JACCARD = 'repost_jaccard'
SHINGLE_SIZE = 'shingle_size'
REASON_NEW_CLAIM = 'new_claim_found'
REASON_REPOST = 'repost_of_event_member'
REASON_ALL_CLAIMS_KNOWN = 'all_claims_known'
REASON_NO_CLAIM_CANDIDATE = 'no_claim_candidate'
REASON_NO_BASELINE = 'no_baseline_revision'
_TOKEN_RE = re.compile(r'\S{1,256}')


@dataclass(frozen=True)
class EventUpdatePolicy:
    revision: str
    repost_jaccard: float
    shingle_size: int


@dataclass(frozen=True)
class ClaimCandidate:
    claim_ref: str
    evidence_article_revision_id: str

    def __post_init__(self) -> None:
        for name, value in (('claim_ref', self.claim_ref), ('evidence_article_revision_id', self.evidence_article_revision_id)):
            if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
                raise ValueError(f'invalid {name}')


@dataclass(frozen=True)
class EventUpdateDecision:
    state: str
    new_claim_refs: tuple[str, ...]
    confidence: float
    reason: str


@dataclass(frozen=True, kw_only=True)
class EventUpdateEvaluation:
    event_update_candidate_id: str
    event_id: str
    article_id: str
    article_revision_id: str
    state: str
    is_new_development: bool
    new_claim_refs: tuple[str, ...]
    source_revision_refs: tuple[str, ...]
    confidence: float
    reason: str
    event_update_id: str | None
    event_update_revision: int | None
    event_update_policy_revision: str
    domain_event_id: str | None


def parse_event_update_policy(policy: Mapping) -> EventUpdatePolicy:
    """Return the validated policy; raise ValueError on a missing or out-of-range value."""
    if not isinstance(policy, Mapping):
        raise ValueError('event_update_policy must be a mapping')
    revision = policy.get(POLICY_REVISION)
    if not isinstance(revision, str) or not _TOKEN_RE.fullmatch(revision):
        raise ValueError(f'{POLICY_REVISION} must be a non-empty token')
    threshold = policy.get(REPOST_JACCARD)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError(f'{REPOST_JACCARD} must be a number in (0, 1]')
    size = policy.get(SHINGLE_SIZE)
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError(f'{SHINGLE_SIZE} must be a positive integer')
    return EventUpdatePolicy(revision, float(threshold), size)


def repost_score(subject: ArticleRevision, member: ArticleRevision, policy: EventUpdatePolicy) -> float:
    """Return 1.0 for an equal exact fingerprint, else the shingle Jaccard of the normalized texts."""
    if subject.exact_fingerprint == member.exact_fingerprint:
        return 1.0
    return jaccard(shingles(subject.normalized_text, policy.shingle_size), shingles(member.normalized_text, policy.shingle_size))


def decide(
    subject: ArticleRevision,
    baseline: Sequence[ArticleRevision],
    candidates: Sequence[ClaimCandidate],
    known_claim_refs: Iterable[str],
    policy: EventUpdatePolicy,
) -> EventUpdateDecision:
    """Apply D8-B-07; missing baseline or claim evidence never yields ACCEPTED_NEW_DEVELOPMENT."""
    if not baseline:
        return EventUpdateDecision(UNCERTAIN, (), 0.0, REASON_NO_BASELINE)
    best = max(repost_score(subject, member, policy) for member in baseline)
    if best >= policy.repost_jaccard:
        return EventUpdateDecision(REJECTED_REPOST, (), best, REASON_REPOST)
    refs = tuple(sorted({c.claim_ref for c in candidates if c.evidence_article_revision_id == subject.article_revision_id}))
    if not refs:
        return EventUpdateDecision(UNCERTAIN, (), 0.0, REASON_NO_CLAIM_CANDIDATE)
    known = frozenset(known_claim_refs)
    new = tuple(ref for ref in refs if ref not in known)
    if not new:
        return EventUpdateDecision(REJECTED_NO_NEW_FACT, (), 0.0, REASON_ALL_CLAIMS_KNOWN)
    return EventUpdateDecision(ACCEPTED_NEW_DEVELOPMENT, new, len(new) / len(refs), REASON_NEW_CLAIM)
