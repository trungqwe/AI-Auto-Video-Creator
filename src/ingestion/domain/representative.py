"""Representative selection for a duplicate cluster (CT-CNT-002, D8-B-05).

Tier 1 is the highest priority; the caller resolves tiers through the SourceTierLookup port.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

MIN_TIER = 1
MAX_TIER = 3
HIGHER_TIER = 'higher_tier'
KEEP_INCUMBENT_SAME_TIER = 'keep_incumbent_same_tier'
TIE_BREAK_SOURCE_ID = 'tie_break_source_id'
SELECTION_REASONS = (HIGHER_TIER, KEEP_INCUMBENT_SAME_TIER, TIE_BREAK_SOURCE_ID)


class RepresentativeCandidate(NamedTuple):
    source_id: str
    tier: int


class RepresentativeSelection(NamedTuple):
    representative: RepresentativeCandidate
    selection_reason: str
    changed: bool
    applies_to_future_production_only: bool


def _candidate(value: object) -> RepresentativeCandidate:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError('candidate must be a (source_id, tier) pair')
    source_id, tier = value
    if not isinstance(source_id, str) or not source_id:
        raise ValueError('source_id must be a non-empty string')
    if isinstance(tier, bool) or not isinstance(tier, int) or not MIN_TIER <= tier <= MAX_TIER:
        raise ValueError('tier must be an integer in 1..3')
    return RepresentativeCandidate(source_id, tier)


def select_representative(
    incumbent: RepresentativeCandidate | None, candidates: Iterable[RepresentativeCandidate]
) -> RepresentativeSelection:
    """Return the cluster representative; the result does not depend on candidate order.

    A strictly lower tier replaces the incumbent, otherwise the incumbent is kept; without an incumbent
    the lowest tier wins and ties break on the smallest source_id. Only replacing an existing
    representative sets applies_to_future_production_only, so started production snapshots keep theirs.
    """
    pool = {_candidate(item) for item in candidates}
    current = None if incumbent is None else _candidate(incumbent)
    tiers: dict[str, int] = {}
    for item in pool | ({current} if current is not None else set()):
        if tiers.setdefault(item.source_id, item.tier) != item.tier:
            raise ValueError(f'conflicting tiers for source_id {item.source_id!r}')
    best = min(pool, key=lambda item: (item.tier, item.source_id), default=current)
    if current is None:
        if best is None:
            raise ValueError('candidates must not be empty without an incumbent')
        peers = sum(1 for item in pool if item.tier == best.tier)
        reason = HIGHER_TIER if peers == 1 and len(pool) > 1 else TIE_BREAK_SOURCE_ID
        return RepresentativeSelection(best, reason, False, False)
    if best.tier < current.tier:
        return RepresentativeSelection(best, HIGHER_TIER, True, True)
    return RepresentativeSelection(current, KEEP_INCUMBENT_SAME_TIER, False, False)
