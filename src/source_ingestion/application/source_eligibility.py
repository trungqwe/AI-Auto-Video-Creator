"""Deterministic Tier-ordered source eligibility and Tier-expansion stop decision.

A-side of CT-SRC-004 (A-RULE-004, A-RULE-006, A-RULE-007). Pure functions only: no I/O,
no CollectionRun creation and no CollectionDecision write. G owns the cycle and records
SKIPPED_SUFFICIENT from the returned TierExpansionDecision.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
import dataclasses
import datetime
import enum

from source_ingestion.domain.collection_run import CollectionPurpose, CollectionRun
from source_ingestion.domain.source import Source, SourceStatus


class EligibilityReason(str, enum.Enum):
    SELECTED = 'SELECTED'
    SOURCE_NOT_ACTIVE = 'SOURCE_NOT_ACTIVE'
    WORKSPACE_OUT_OF_SCOPE = 'WORKSPACE_OUT_OF_SCOPE'
    TOPIC_OUT_OF_SCOPE = 'TOPIC_OUT_OF_SCOPE'
    TIER_NOT_RANKED = 'TIER_NOT_RANKED'
    PERIODIC_RUN_EXISTS = 'PERIODIC_RUN_EXISTS'


class TierExpansionAction(str, enum.Enum):
    OPEN_NEXT_TIER = 'OPEN_NEXT_TIER'
    STOP_SUFFICIENT = 'STOP_SUFFICIENT'
    NO_MORE_TIERS = 'NO_MORE_TIERS'


@dataclasses.dataclass(frozen=True)
class SourceEligibility:
    source_id: str
    tier: str
    selected: bool
    reason: EligibilityReason


@dataclasses.dataclass(frozen=True)
class EligibilityPlan:
    workspace_id: str
    topic: str
    business_date: datetime.date
    tier_order: tuple[str, ...]
    selected: tuple[SourceEligibility, ...]
    skipped: tuple[SourceEligibility, ...]


@dataclasses.dataclass(frozen=True)
class UniqueArticleCount:
    """Unique representative article counter supplied by G/B for one topic and business_date."""

    topic: str
    business_date: datetime.date
    unique_article_count: int

    def __post_init__(self) -> None:
        _require_text(self.topic, 'topic')
        _require_date(self.business_date)
        _require_count(self.unique_article_count, 'unique_article_count', minimum=0)


@dataclasses.dataclass(frozen=True)
class TierExpansionDecision:
    topic: str
    business_date: datetime.date
    completed_tier: str
    action: TierExpansionAction
    next_tier: str | None
    unopened_tiers: tuple[str, ...]
    unscanned_source_ids: tuple[str, ...]
    unique_article_count: int
    fresh_unique_article_target: int


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')
    return value


def _require_date(value: object) -> datetime.date:
    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError('business_date must be a datetime.date')
    return value


def _require_count(value: object, field: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{field} must be an integer >= {minimum}')
    return value


def _require_tier_order(tier_order: object) -> tuple[str, ...]:
    if isinstance(tier_order, str) or not isinstance(tier_order, Sequence):
        raise ValueError('tier_order must be an ordered sequence of Tiers')
    order = tuple(_require_text(tier, 'tier') for tier in tier_order)
    if not order or len(set(order)) != len(order):
        raise ValueError('tier_order must be non-empty with unique Tiers')
    return order


def _eligibility_reason(
    source: Source,
    *,
    workspace_id: str,
    topic: str,
    business_date: datetime.date,
    tier_rank: dict[str, int],
    periodic_keys: set[tuple[str, str, datetime.date, CollectionPurpose]],
) -> EligibilityReason:
    if source.status is not SourceStatus.ACTIVE:
        return EligibilityReason.SOURCE_NOT_ACTIVE
    if source.workspace_id != workspace_id:
        return EligibilityReason.WORKSPACE_OUT_OF_SCOPE
    if topic not in source.topics:
        return EligibilityReason.TOPIC_OUT_OF_SCOPE
    if source.tier not in tier_rank:
        return EligibilityReason.TIER_NOT_RANKED
    if (workspace_id, source.source_id, business_date, CollectionPurpose.PERIODIC) in periodic_keys:
        return EligibilityReason.PERIODIC_RUN_EXISTS
    return EligibilityReason.SELECTED


def rank_eligible_sources(
    *,
    sources: Iterable[Source],
    existing_runs: Iterable[CollectionRun],
    workspace_id: str,
    topic: str,
    business_date: datetime.date,
    tier_order: Sequence[str],
) -> EligibilityPlan:
    workspace_id = _require_text(workspace_id, 'workspace_id')
    topic = _require_text(topic, 'topic')
    business_date = _require_date(business_date)
    order = _require_tier_order(tier_order)
    tier_rank = {tier: index for index, tier in enumerate(order)}
    periodic_keys: set[tuple[str, str, datetime.date, CollectionPurpose]] = set()
    for run in existing_runs:
        if not isinstance(run, CollectionRun):
            raise TypeError('existing_runs must contain CollectionRun records')
        if run.unique_key is not None:
            periodic_keys.add(run.unique_key)
    seen: set[str] = set()
    selected: list[SourceEligibility] = []
    skipped: list[SourceEligibility] = []
    for source in sources:
        if not isinstance(source, Source):
            raise TypeError('sources must contain Source records')
        if source.source_id in seen:
            raise ValueError(f'duplicate source_id {source.source_id!r} in snapshot')
        seen.add(source.source_id)
        reason = _eligibility_reason(
            source,
            workspace_id=workspace_id,
            topic=topic,
            business_date=business_date,
            tier_rank=tier_rank,
            periodic_keys=periodic_keys,
        )
        entry = SourceEligibility(source.source_id, source.tier, reason is EligibilityReason.SELECTED, reason)
        (selected if entry.selected else skipped).append(entry)
    return EligibilityPlan(
        workspace_id=workspace_id,
        topic=topic,
        business_date=business_date,
        tier_order=order,
        selected=tuple(sorted(selected, key=lambda entry: (tier_rank[entry.tier], entry.source_id))),
        skipped=tuple(sorted(skipped, key=lambda entry: entry.source_id)),
    )


def decide_tier_expansion(
    *,
    plan: EligibilityPlan,
    completed_tier: str,
    counter: UniqueArticleCount,
    fresh_unique_article_target: int,
) -> TierExpansionDecision:
    if not isinstance(plan, EligibilityPlan):
        raise TypeError('plan must be an EligibilityPlan')
    if not isinstance(counter, UniqueArticleCount):
        raise TypeError('counter must be a UniqueArticleCount from G/B; URL or item counts are not accepted')
    if counter.topic != plan.topic or counter.business_date != plan.business_date:
        raise ValueError('counter must match the plan topic and business_date')
    if completed_tier not in plan.tier_order:
        raise ValueError('completed_tier must be a Tier of the plan')
    target = _require_count(fresh_unique_article_target, 'fresh_unique_article_target', minimum=1)
    later = plan.tier_order[plan.tier_order.index(completed_tier) + 1:]
    next_tier: str | None = None
    unscanned: tuple[str, ...] = ()
    if counter.unique_article_count >= target:
        action, unopened = TierExpansionAction.STOP_SUFFICIENT, later
        unscanned = tuple(entry.source_id for entry in plan.selected if entry.tier in later)
    elif later:
        action, next_tier, unopened = TierExpansionAction.OPEN_NEXT_TIER, later[0], later[1:]
    else:
        action, unopened = TierExpansionAction.NO_MORE_TIERS, ()
    return TierExpansionDecision(
        topic=plan.topic,
        business_date=plan.business_date,
        completed_tier=completed_tier,
        action=action,
        next_tier=next_tier,
        unopened_tiers=unopened,
        unscanned_source_ids=unscanned,
        unique_article_count=counter.unique_article_count,
        fresh_unique_article_target=target,
    )


__all__ = [
    'EligibilityPlan',
    'EligibilityReason',
    'SourceEligibility',
    'TierExpansionAction',
    'TierExpansionDecision',
    'UniqueArticleCount',
    'decide_tier_expansion',
    'rank_eligible_sources',
]
