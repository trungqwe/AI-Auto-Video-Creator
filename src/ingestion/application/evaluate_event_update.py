"""EvaluateEventUpdate use case of module B (CT-CNT-005, CT-STATE-004, D8-B-07).

Every outcome keeps an event_update_candidate record; only ACCEPTED_NEW_DEVELOPMENT writes an EventUpdate and emits EventUpdateAccepted.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from ingestion.application.ports import UnitOfWork
from ingestion.domain.article import ArticleRevision
from ingestion.domain.event_update import (
    ACCEPTED_NEW_DEVELOPMENT,
    STATE_PROPOSED,
    ClaimCandidate,
    EventUpdateEvaluation,
    EventUpdatePolicy,
    decide,
    parse_event_update_policy,
)
from ingestion.domain.events import build_event

EVENT_UPDATE_CANDIDATE_KIND = 'event_update_candidate'
EVENT_UPDATE_KIND = 'event_update'
EVENT_UPDATE_ACCEPTED = 'EventUpdateAccepted'
EVENT_UPDATE_AGGREGATE_TYPE = 'EventUpdate'
_TOKEN_RE = re.compile(r'\S{1,256}')


@runtime_checkable
class ClaimCandidateProvider(Protocol):
    """Claim extraction port (D8-B-07); the real AI extractor belongs to D/CP7."""

    def claim_candidates(self, revision: ArticleRevision) -> Sequence[ClaimCandidate]: ...


def _token(name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f'invalid {name}')
    return value


def _revision_ref(article_revision_ref: object) -> tuple[str, str]:
    if not isinstance(article_revision_ref, Mapping):
        raise ValueError('article_revision_ref must be a mapping')
    return (
        _token('article_id', article_revision_ref.get('article_id')),
        _token('article_revision_id', article_revision_ref.get('article_revision_id')),
    )


def _now(clock: Callable[[], datetime]) -> str:
    moment = clock()
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError('clock must return an aware datetime')
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _load_revision(uow: UnitOfWork, article_id: str, article_revision_id: str) -> ArticleRevision:
    article = uow.articles.get(article_id)
    revisions = article.revisions if article is not None else ()
    revision = next((item for item in revisions if item.article_revision_id == article_revision_id), None)
    if revision is None:
        raise LookupError(f'unknown article revision {article_id}/{article_revision_id}')
    return revision


def _claims(provider: ClaimCandidateProvider, revision: ArticleRevision) -> tuple[ClaimCandidate, ...]:
    result = provider.claim_candidates(revision)
    if isinstance(result, (str, bytes, Mapping)) or not isinstance(result, Sequence):
        raise ValueError('claim provider must return a sequence of ClaimCandidate')
    if not all(isinstance(item, ClaimCandidate) for item in result):
        raise ValueError('claim provider must return ClaimCandidate items')
    return tuple(result)


def _stored_evaluation(
    uow: UnitOfWork,
    event_id: str,
    article_revision_id: str,
    policy_revision: str,
) -> EventUpdateEvaluation | None:
    for record in uow.records.list(EVENT_UPDATE_CANDIDATE_KIND):
        if (
            record['event_id'],
            record['article_revision_id'],
            record['event_update_policy_revision'],
        ) == (event_id, article_revision_id, policy_revision):
            return EventUpdateEvaluation(**{name: record[name] for name in EventUpdateEvaluation.__dataclass_fields__})
    return None


def _baseline(uow: UnitOfWork, event: Mapping, subject: ArticleRevision) -> tuple[ArticleRevision, ...]:
    """Members joined before the subject, or every member when the subject is not a member."""
    members = tuple((ref[0], ref[1]) for ref in event['member_refs'])
    subject_ref = (subject.article_id, subject.article_revision_id)
    if subject_ref in members:
        members = members[: members.index(subject_ref)]
    return tuple(_load_revision(uow, a, r) for a, r in members if r != subject.article_revision_id)


def _event_updates(uow: UnitOfWork, event_id: str) -> tuple[dict, ...]:
    return tuple(record for record in uow.records.list(EVENT_UPDATE_KIND) if record['event_id'] == event_id)


def _accept(uow: UnitOfWork, evaluation: EventUpdateEvaluation, now: str, recovery_epoch: str) -> None:
    uow.records.put(
        EVENT_UPDATE_KIND,
        evaluation.event_update_id,
        {
            'event_update_id': evaluation.event_update_id,
            'event_id': evaluation.event_id,
            'event_update_revision': evaluation.event_update_revision,
            'event_update_candidate_id': evaluation.event_update_candidate_id,
            'article_id': evaluation.article_id,
            'article_revision_id': evaluation.article_revision_id,
            'new_claim_refs': evaluation.new_claim_refs,
            'source_revision_refs': evaluation.source_revision_refs,
            'confidence': evaluation.confidence,
            'state': evaluation.state,
            'event_update_policy_revision': evaluation.event_update_policy_revision,
            'accepted_at': now,
        },
    )
    payload = {
        'event_update_id': evaluation.event_update_id,
        'event_id': evaluation.event_id,
        'event_update_revision': evaluation.event_update_revision,
        'article_revision_id': evaluation.article_revision_id,
        'new_claim_refs': evaluation.new_claim_refs,
        'source_revision_refs': evaluation.source_revision_refs,
        'event_update_policy_revision': evaluation.event_update_policy_revision,
    }
    envelope = build_event(
        EVENT_UPDATE_ACCEPTED,
        EVENT_UPDATE_AGGREGATE_TYPE,
        evaluation.event_update_id,
        1,
        payload,
        recovery_epoch,
        evaluation.domain_event_id,
    )
    uow.outbox.append_event(
        EVENT_UPDATE_ACCEPTED,
        evaluation.event_update_id,
        envelope,
        f'{EVENT_UPDATE_ACCEPTED}:{evaluation.event_update_candidate_id}',
    )


def _evaluate_one(
    uow: UnitOfWork,
    event: Mapping,
    subject: ArticleRevision,
    provider: ClaimCandidateProvider,
    policy: EventUpdatePolicy,
    now: str,
    id_factory: Callable[[], str],
    recovery_epoch: str,
) -> EventUpdateEvaluation:
    event_id = event['event_id']
    baseline = _baseline(uow, event, subject)
    updates = _event_updates(uow, event_id)
    known = {c.claim_ref for member in baseline for c in _claims(provider, member)}
    known.update(ref for record in updates for ref in record['new_claim_refs'])
    decision = decide(subject, baseline, _claims(provider, subject), known, policy)
    accepted = decision.state == ACCEPTED_NEW_DEVELOPMENT
    candidate_id = _token('event_update_candidate_id', id_factory())
    event_update_id = _token('event_update_id', id_factory()) if accepted else None
    domain_event_id = _token('domain_event_id', id_factory()) if accepted else None
    evaluation = EventUpdateEvaluation(
        event_update_candidate_id=candidate_id,
        event_id=event_id,
        article_id=subject.article_id,
        article_revision_id=subject.article_revision_id,
        state=decision.state,
        is_new_development=accepted,
        new_claim_refs=decision.new_claim_refs,
        source_revision_refs=(subject.article_revision_id, *(m.article_revision_id for m in baseline)),
        confidence=decision.confidence,
        reason=decision.reason,
        event_update_id=event_update_id,
        event_update_revision=len(updates) + 1 if accepted else None,
        event_update_policy_revision=policy.revision,
        domain_event_id=domain_event_id,
    )
    record = {name: getattr(evaluation, name) for name in EventUpdateEvaluation.__dataclass_fields__}
    record.update(state_history=(STATE_PROPOSED, evaluation.state), evaluated_at=now)
    uow.records.put(EVENT_UPDATE_CANDIDATE_KIND, candidate_id, record)
    if accepted:
        _accept(uow, evaluation, now, recovery_epoch)
    return evaluation


def evaluate_event_update(
    event_id: str,
    article_revision_ref: Mapping[str, str],
    claim_provider: ClaimCandidateProvider,
    policy: Mapping,
    uow: UnitOfWork,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
    *,
    recovery_epoch: str,
) -> EventUpdateEvaluation:
    """Evaluate one article revision against one event by D8-B-07 in its own transaction.

    A replay of the same event, article revision and policy revision returns the stored result without writing.
    """
    parsed = parse_event_update_policy(policy)
    _token('event_id', event_id)
    article_id, article_revision_id = _revision_ref(article_revision_ref)
    _token('recovery_epoch', recovery_epoch)
    if not isinstance(claim_provider, ClaimCandidateProvider):
        raise ValueError('claim_provider must implement ClaimCandidateProvider')
    with uow:
        evaluation = _stored_evaluation(uow, event_id, article_revision_id, parsed.revision)
        if evaluation is None:
            event = uow.events.get(event_id)
            if event is None:
                raise LookupError(f'unknown event {event_id}')
            subject = _load_revision(uow, article_id, article_revision_id)
            evaluation = _evaluate_one(
                uow, event, subject, claim_provider, parsed, _now(clock), id_factory, recovery_epoch
            )
            uow.commit()
    return evaluation
