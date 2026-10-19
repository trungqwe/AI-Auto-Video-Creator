"""Source set and timeline eligibility for ProductionSnapshot (CT-AI-001, INV-004, INV-006, D8-B-09).

Read-only: pins article revisions for module D; it never opens a transaction, stores records or emits events.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ingestion.application.evaluate_event_update import EVENT_UPDATE_KIND
from ingestion.application.ports import UnitOfWork
from ingestion.domain.article import ArticleRevision
from ingestion.domain.event_update import ACCEPTED_NEW_DEVELOPMENT

SINGLE_ARTICLE = 'single_article'
MULTI_ARTICLE_EVENT = 'multi_article_event'
FROM_THEN_TO_NOW = 'from_then_to_now'
PRODUCTION_MODES = (SINGLE_ARTICLE, MULTI_ARTICLE_EVENT, FROM_THEN_TO_NOW)
SOURCE_REF_FIELDS = ('article_id', 'article_revision_id', 'source_id', 'source_revision')
REASON_SINGLE_ELIGIBLE = 'single_article_eligible'
REASON_MULTI_ELIGIBLE = 'multi_article_event_eligible'
REASON_TIMELINE_ELIGIBLE = 'from_then_to_now_eligible'
REASON_NO_REPRESENTATIVE = 'no_representative_revision'
REASON_NOT_ENOUGH_LINKED = 'event_needs_two_linked_articles'
REASON_UPDATE_NOT_ACCEPTED = 'event_update_not_accepted'


class SourceSetRejected(Exception):
    """The subject is not eligible for the requested production mode; `reason` is the stable machine reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class SourceSet:
    production_mode: str
    source_refs: tuple[Mapping[str, object], ...]
    source_set_fingerprint: str
    eligibility_reason: str


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _load_revision(uow: UnitOfWork, article_id: str, article_revision_id: str) -> ArticleRevision:
    article = uow.articles.get(article_id)
    revisions = article.revisions if article is not None else ()
    revision = next((item for item in revisions if item.article_revision_id == article_revision_id), None)
    if revision is None:
        raise LookupError(f'unknown article revision {article_id}/{article_revision_id}')
    return revision


def _source_ref(revision: ArticleRevision) -> Mapping[str, object]:
    return MappingProxyType(
        {
            'article_id': revision.article_id,
            'article_revision_id': revision.article_revision_id,
            'source_id': revision.source_id,
            'source_revision': revision.source_revision,
        }
    )


def _sorted_refs(refs: Iterable[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    return tuple(sorted(refs, key=lambda ref: (ref['article_id'], ref['article_revision_id'])))


def fingerprint_source_refs(refs: Iterable[Mapping[str, object]]) -> str:
    """Return the SHA-256 hex of the compact JSON of the refs sorted by (article_id, article_revision_id)."""
    ordered = [{name: ref[name] for name in SOURCE_REF_FIELDS} for ref in _sorted_refs(refs)]
    payload = json.dumps(ordered, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _event(uow: UnitOfWork, event_id: str) -> Mapping[str, Any]:
    event = uow.events.get(event_id)
    if event is None:
        raise LookupError(f'unknown event {event_id}')
    return event


def _member_pairs(event: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple((ref[0], ref[1]) for ref in event['member_refs'])


def _pinned(uow: UnitOfWork, pairs: Iterable[tuple[str, str]]) -> tuple[Mapping[str, object], ...]:
    """Pin the exact stored revisions; later revisions of the same articles never enter the set."""
    return tuple(_source_ref(_load_revision(uow, article_id, revision_id)) for article_id, revision_id in sorted(set(pairs)))


def _single_article(uow: UnitOfWork, subject_id: str) -> tuple[tuple[Mapping[str, object], ...], str]:
    article = uow.articles.get(subject_id)
    if article is None:
        raise LookupError(f'unknown article {subject_id}')
    representative = article.latest_revision
    if representative is None:
        raise SourceSetRejected(REASON_NO_REPRESENTATIVE)
    return (_source_ref(representative),), REASON_SINGLE_ELIGIBLE


def _multi_article_event(uow: UnitOfWork, subject_id: str) -> tuple[tuple[Mapping[str, object], ...], str]:
    pairs = _member_pairs(_event(uow, subject_id))
    if len({article_id for article_id, _ in pairs}) < 2:
        raise SourceSetRejected(REASON_NOT_ENOUGH_LINKED)
    return _pinned(uow, pairs), REASON_MULTI_ELIGIBLE


def _from_then_to_now(uow: UnitOfWork, subject_id: str) -> tuple[tuple[Mapping[str, object], ...], str]:
    event = _event(uow, subject_id)
    accepted = tuple(
        record
        for record in uow.records.list(EVENT_UPDATE_KIND)
        if record.get('event_id') == subject_id and record.get('state') == ACCEPTED_NEW_DEVELOPMENT
    )
    if not accepted:
        raise SourceSetRejected(REASON_UPDATE_NOT_ACCEPTED)
    update_pairs = tuple((record['article_id'], record['article_revision_id']) for record in accepted)
    return _pinned(uow, (*_member_pairs(event), *update_pairs)), REASON_TIMELINE_ELIGIBLE


_BUILDERS = {
    SINGLE_ARTICLE: _single_article,
    MULTI_ARTICLE_EVENT: _multi_article_event,
    FROM_THEN_TO_NOW: _from_then_to_now,
}


def build_source_set(production_mode: str, subject_id: str, uow: UnitOfWork) -> SourceSet:
    """Return the pinned source set of one subject: article_id for single_article, event_id for the event modes.

    Raises SourceSetRejected with a stable reason when the subject is not eligible for the mode,
    LookupError for an unknown subject or stored ref, ValueError for invalid arguments.
    """
    if production_mode not in PRODUCTION_MODES:
        raise ValueError(f'production_mode must be one of {PRODUCTION_MODES!r}')
    _require_text('subject_id', subject_id)
    refs, reason = _BUILDERS[production_mode](uow, subject_id)
    return SourceSet(
        production_mode=production_mode,
        source_refs=_sorted_refs(refs),
        source_set_fingerprint=fingerprint_source_refs(refs),
        eligibility_reason=reason,
    )
