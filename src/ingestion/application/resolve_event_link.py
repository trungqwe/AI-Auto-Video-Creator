"""ResolveEventLink use case of module B (CT-CNT-004, CT-STATE-004, D8-B-06).

Each article revision ref is resolved in its own transaction; Articles are only read, never merged or deleted.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone

from ingestion.application.ports import UnitOfWork
from ingestion.domain.article import ArticleRevision
from ingestion.domain.event_link import (
    KEPT_SEPARATE,
    LINKED,
    NO_COMPARABLE_EVENT,
    RELATION_BY_DISPOSITION,
    STATE_BY_DISPOSITION,
    STATE_PROPOSED,
    EventLinkPolicy,
    EventLinkResolution,
    PairAssessment,
    assess_pair,
    parse_event_link_policy,
    parse_rfc3339,
    rank,
    revision_time,
)
from ingestion.domain.events import build_event

EVENT_LINK_CANDIDATE_KIND = 'event_link_candidate'
EVENT_LINK_RESOLVED = 'EventLinkResolved'
EVENT_AGGREGATE_TYPE = 'Event'
EVENT_STATUS_CANDIDATE = 'candidate'
_TOKEN_RE = re.compile(r'\S{1,256}')
_EARLIEST = datetime.min.replace(tzinfo=timezone.utc)


def _token(name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f'invalid {name}')
    return value


def _refs(article_revision_refs: object) -> tuple[tuple[str, str], ...]:
    if isinstance(article_revision_refs, (str, bytes, Mapping)) or not isinstance(article_revision_refs, Sequence):
        raise ValueError('article_revision_refs must be a sequence of refs')
    if not article_revision_refs:
        raise ValueError('article_revision_refs must not be empty')
    refs = []
    for ref in article_revision_refs:
        if not isinstance(ref, Mapping):
            raise ValueError('article revision ref must be a mapping')
        refs.append((_token('article_id', ref.get('article_id')), _token('article_revision_id', ref.get('article_revision_id'))))
    return tuple(refs)


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


def _time_range(times: Sequence[str]) -> tuple[str, str]:
    ordered = sorted(times, key=lambda value: (parse_rfc3339(value) or _EARLIEST, value))
    return ordered[0], ordered[-1]


def _stored_resolution(uow: UnitOfWork, article_revision_id: str, policy_revision: str) -> EventLinkResolution | None:
    for record in uow.records.list(EVENT_LINK_CANDIDATE_KIND):
        if record['article_revision_id'] == article_revision_id and record['event_link_policy_revision'] == policy_revision:
            return EventLinkResolution(**{name: record[name] for name in EventLinkResolution.__dataclass_fields__})
    return None


def _best_match(uow: UnitOfWork, subject: ArticleRevision, policy: EventLinkPolicy) -> tuple[Mapping, PairAssessment] | None:
    best = None
    for event in sorted(uow.events.list_all(), key=lambda item: item['event_id']):
        for member_article_id, member_revision_id in event['member_refs']:
            if member_revision_id == subject.article_revision_id:
                continue
            assessment = assess_pair(subject, _load_revision(uow, member_article_id, member_revision_id), policy)
            if best is None or rank(assessment) > rank(best[1]):
                best = (event, assessment)
    return best


def _resolve_one(
    uow: UnitOfWork,
    subject: ArticleRevision,
    policy: EventLinkPolicy,
    now: str,
    id_factory: Callable[[], str],
    recovery_epoch: str,
) -> EventLinkResolution:
    best = _best_match(uow, subject, policy)
    subject_ref = (subject.article_id, subject.article_revision_id)
    subject_time = revision_time(subject)
    if best is None or best[1].disposition == KEPT_SEPARATE:
        assessment = best[1] if best is not None else PairAssessment(KEPT_SEPARATE, 0.0, (NO_COMPARABLE_EVENT,))
        event = {
            'event_id': _token('event_id', id_factory()),
            'status': EVENT_STATUS_CANDIDATE,
            'revision': 1,
            'topic': subject.topic,
            'member_refs': (subject_ref,),
            'effective_time_range': (subject_time, subject_time),
            'event_link_policy_revision': policy.revision,
            'created_at': now,
            'updated_at': now,
        }
        uow.events.save(event)
        is_new_event = True
    else:
        event, assessment, is_new_event = dict(best[0]), best[1], False
        if assessment.disposition == LINKED:
            members = tuple(event['member_refs'])
            event.update(
                member_refs=members if subject_ref in members else (*members, subject_ref),
                effective_time_range=_time_range((*event['effective_time_range'], subject_time)),
                revision=event['revision'] + 1,
                updated_at=now,
            )
            uow.events.save(event)
    candidate_id = _token('event_link_candidate_id', id_factory())
    domain_event_id = _token('domain_event_id', id_factory())
    disposition = assessment.disposition
    resolution = EventLinkResolution(
        event_link_candidate_id=candidate_id,
        article_id=subject.article_id,
        article_revision_id=subject.article_revision_id,
        event_id=event['event_id'],
        is_new_event=is_new_event,
        disposition=disposition,
        state=STATE_BY_DISPOSITION[disposition],
        confidence=assessment.confidence,
        explanation=assessment.explanation,
        relation_type=RELATION_BY_DISPOSITION[disposition],
        effective_time_range=tuple(event['effective_time_range']),
        event_link_policy_revision=policy.revision,
        domain_event_id=domain_event_id,
    )
    record = {name: getattr(resolution, name) for name in EventLinkResolution.__dataclass_fields__}
    record.update(state_history=(STATE_PROPOSED, resolution.state), resolved_at=now)
    uow.records.put(EVENT_LINK_CANDIDATE_KIND, candidate_id, record)
    payload = {
        'event_link_candidate_id': candidate_id,
        'event_id': resolution.event_id,
        'article_id': subject.article_id,
        'article_revision_id': subject.article_revision_id,
        'event_link_policy_revision': policy.revision,
    }
    envelope = build_event(
        EVENT_LINK_RESOLVED, EVENT_AGGREGATE_TYPE, resolution.event_id, event['revision'], payload, recovery_epoch, domain_event_id,
    )
    uow.outbox.append_event(EVENT_LINK_RESOLVED, resolution.event_id, envelope, f'{EVENT_LINK_RESOLVED}:{candidate_id}')
    return resolution


def resolve_event_link(
    article_revision_refs: Sequence[Mapping[str, str]],
    event_link_policy: Mapping,
    uow: UnitOfWork,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
    *,
    recovery_epoch: str,
) -> tuple[EventLinkResolution, ...]:
    """Resolve each ref against stored events by D8-B-06 and emit EventLinkResolved.

    A replay of the same article revision under the same policy revision returns the stored result without writing.
    """
    policy = parse_event_link_policy(event_link_policy)
    refs = _refs(article_revision_refs)
    _token('recovery_epoch', recovery_epoch)
    results = []
    for article_id, article_revision_id in refs:
        with uow:
            resolution = _stored_resolution(uow, article_revision_id, policy.revision)
            if resolution is None:
                subject = _load_revision(uow, article_id, article_revision_id)
                resolution = _resolve_one(uow, subject, policy, _now(clock), id_factory, recovery_epoch)
                uow.commit()
        results.append(resolution)
    return tuple(results)
