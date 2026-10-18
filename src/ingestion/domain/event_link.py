"""Deterministic event link rule of module B (CT-CNT-004, CT-STATE-004, D8-B-06).

Thresholds come from the event link policy revision passed by the caller; linking never merges or deletes an Article.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType

from ingestion.domain.article import ArticleRevision
from ingestion.domain.fingerprint import jaccard
from ingestion.domain.normalization import normalize_text

LINKED = 'linked'
KEPT_SEPARATE = 'kept_separate'
NEEDS_MORE_EVIDENCE = 'needs_more_evidence'
DISPOSITIONS = (LINKED, KEPT_SEPARATE, NEEDS_MORE_EVIDENCE)
STATE_PROPOSED = 'PROPOSED'
STATE_BY_DISPOSITION = MappingProxyType({LINKED: 'LINKED', KEPT_SEPARATE: 'KEPT_SEPARATE', NEEDS_MORE_EVIDENCE: 'NEEDS_MORE_EVIDENCE'})
RELATION_BY_DISPOSITION = MappingProxyType({LINKED: 'same_event', KEPT_SEPARATE: 'separate_event', NEEDS_MORE_EVIDENCE: 'possible_same_event'})
POLICY_REVISION = 'event_link_policy_revision'
LINK_JACCARD = 'link_jaccard'
REVIEW_JACCARD = 'review_jaccard'
MAX_TIME_GAP_HOURS = 'max_time_gap_hours'
NO_COMPARABLE_EVENT = 'no_comparable_event'
_PRIORITY = MappingProxyType({KEPT_SEPARATE: 0, NEEDS_MORE_EVIDENCE: 1, LINKED: 2})
_WORD_RE = re.compile(r'\w+')
_TOKEN_RE = re.compile(r'\S{1,256}')


@dataclass(frozen=True)
class EventLinkPolicy:
    revision: str
    link_jaccard: float
    review_jaccard: float
    max_time_gap_hours: float


@dataclass(frozen=True)
class PairAssessment:
    disposition: str
    confidence: float
    explanation: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class EventLinkResolution:
    event_link_candidate_id: str
    article_id: str
    article_revision_id: str
    event_id: str
    is_new_event: bool
    disposition: str
    state: str
    confidence: float
    explanation: tuple[str, ...]
    relation_type: str
    effective_time_range: tuple[str, str]
    event_link_policy_revision: str
    domain_event_id: str


def _number(policy: Mapping, key: str) -> float:
    value = policy.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{key} must be a number')
    return float(value)


def parse_event_link_policy(policy: Mapping) -> EventLinkPolicy:
    """Return the validated policy; raise ValueError on a missing or out-of-range value."""
    if not isinstance(policy, Mapping):
        raise ValueError('event_link_policy must be a mapping')
    revision = policy.get(POLICY_REVISION)
    if not isinstance(revision, str) or not _TOKEN_RE.fullmatch(revision):
        raise ValueError(f'{POLICY_REVISION} must be a non-empty token')
    link = _number(policy, LINK_JACCARD)
    review = _number(policy, REVIEW_JACCARD)
    hours = _number(policy, MAX_TIME_GAP_HOURS)
    if not 0 < link <= 1:
        raise ValueError(f'{LINK_JACCARD} must be in (0, 1]')
    if not 0 < review <= link:
        raise ValueError(f'{REVIEW_JACCARD} must be in (0, {LINK_JACCARD}]')
    if not (math.isfinite(hours) and hours > 0):
        raise ValueError(f'{MAX_TIME_GAP_HOURS} must be a positive finite number')
    return EventLinkPolicy(revision, link, review, hours)


def title_keywords(title: str) -> frozenset[str]:
    """Return the casefolded NFC word set of a title."""
    return frozenset(_WORD_RE.findall(normalize_text(normalize_text(title).casefold())))


def parse_rfc3339(value: object) -> datetime | None:
    """Return an aware datetime, or None when the value is absent or lacks a UTC offset."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def revision_time(revision: ArticleRevision) -> str:
    """Return published_at when it parses, else fetched_at; used for effective_time_range only."""
    return revision.published_at if parse_rfc3339(revision.published_at) is not None else revision.fetched_at


def assess_pair(subject: ArticleRevision, member: ArticleRevision, policy: EventLinkPolicy) -> PairAssessment:
    """Apply D8-B-06 to one subject/member pair; missing evidence never yields LINKED."""
    score = jaccard(title_keywords(subject.title), title_keywords(member.title))
    if subject.topic != member.topic:
        return PairAssessment(KEPT_SEPARATE, score, ('topic_mismatch',))
    reasons = ['same_topic']
    missing = []
    if subject.topic_uncertain or member.topic_uncertain:
        missing.append('topic_uncertain')
    subject_time, member_time = parse_rfc3339(subject.published_at), parse_rfc3339(member.published_at)
    if subject_time is None or member_time is None:
        missing.append('published_at_missing')
    elif abs(subject_time - member_time) > timedelta(hours=policy.max_time_gap_hours):
        return PairAssessment(KEPT_SEPARATE, score, (*reasons, 'outside_time_window'))
    else:
        reasons.append('within_time_window')
    if score < policy.review_jaccard:
        return PairAssessment(KEPT_SEPARATE, score, (*reasons, *missing, 'title_jaccard_below_review'))
    band = 'title_jaccard_at_least_link' if score >= policy.link_jaccard else 'title_jaccard_below_link'
    if score >= policy.link_jaccard and not missing:
        return PairAssessment(LINKED, score, (*reasons, band))
    return PairAssessment(NEEDS_MORE_EVIDENCE, score, (*reasons, *missing, band))


def rank(assessment: PairAssessment) -> tuple[int, float]:
    """Order assessments: LINKED over NEEDS_MORE_EVIDENCE over KEPT_SEPARATE, then by confidence."""
    return _PRIORITY[assessment.disposition], assessment.confidence
