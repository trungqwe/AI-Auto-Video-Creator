"""Read-only queries of module B: source trace (CT-CNT-006), search/filter and NEW_ARTICLE count (D8-B-10).

Queries only read the UnitOfWork repositories; they never open a transaction, store records or emit events.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone

from ingestion.application.ports import UnitOfWork
from ingestion.domain.article import ArticleRevision
from ingestion.domain.event_link import parse_rfc3339
from ingestion.domain.normalization import normalize_text

TRACE_FIELDS = (
    'source_id',
    'source_revision',
    'collection_run_id',
    'collected_document_id',
    'requested_url',
    'final_url',
    'fetched_at',
    'raw_snapshot_ref',
    'provenance_chain',
)
SEARCH_FILTERS = ('topic', 'source_id', 'event_id', 'article_revision_id', 'title_contains')
NEW_ARTICLE = 'NEW_ARTICLE'
_FIELD_FILTERS = ('topic', 'source_id', 'article_revision_id')
_BUSINESS_DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _fold(text: str) -> str:
    return normalize_text(normalize_text(text).casefold())


def _is_missing(name: str, value: object) -> bool:
    if name == 'source_revision':
        return isinstance(value, bool) or not isinstance(value, int)
    if name == 'fetched_at':
        return parse_rfc3339(value) is None
    if name == 'provenance_chain':
        return not value
    return not isinstance(value, str) or not value.strip()


def _business_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError('business_date_utc must be a date, not a datetime')
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _BUSINESS_DATE_RE.fullmatch(value):
        return date.fromisoformat(value)
    raise ValueError('business_date_utc must be a date or a YYYY-MM-DD string')


class IngestionQueries:
    """Read-only queries over the module B repositories of one UnitOfWork."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow


    def _revisions(self) -> tuple[ArticleRevision, ...]:
        revisions = (revision for article in self._uow.articles.list_all() for revision in article.revisions)
        return tuple(sorted(revisions, key=lambda revision: (revision.article_id, revision.revision_number)))

    def _event_ids(self) -> dict[tuple[str, str], tuple[str, ...]]:
        members: dict[tuple[str, str], set[str]] = {}
        for event in self._uow.events.list_all():
            for article_id, article_revision_id in event['member_refs']:
                members.setdefault((article_id, article_revision_id), set()).add(event['event_id'])
        return {ref: tuple(sorted(ids)) for ref, ids in members.items()}

    def trace_revision(self, article_revision_id: str) -> dict[str, object]:
        """Return the provenance of one revision; missing or uncertain fields are listed, never hidden (CT-CNT-006)."""
        _require_text('article_revision_id', article_revision_id)
        revision = next((item for item in self._revisions() if item.article_revision_id == article_revision_id), None)
        if revision is None:
            raise LookupError(f'unknown article revision {article_revision_id}')
        trace = {name: getattr(revision, name) for name in TRACE_FIELDS}
        trace['provenance_chain'] = tuple(copy.deepcopy(dict(step)) for step in revision.provenance_chain)
        missing = [name for name in TRACE_FIELDS if _is_missing(name, trace[name])]
        uncertain = (*missing, *(name for name in revision.uncertain_fields if name not in missing))
        return {
            'article_id': revision.article_id,
            'article_revision_id': revision.article_revision_id,
            'revision_number': revision.revision_number,
            **trace,
            'uncertain_fields': uncertain,
            'is_fully_traced': not any(name in TRACE_FIELDS for name in uncertain),
        }

    def search(self, filters: Mapping[str, str]) -> tuple[dict[str, object], ...]:
        """Return revisions matching every filter, ordered by (article_id, revision_number)."""
        if not isinstance(filters, Mapping):
            raise ValueError('filters must be a mapping')
        unknown = [name for name in filters if name not in SEARCH_FILTERS]
        if unknown:
            raise ValueError(f'unknown search filters {unknown!r}')
        wanted = {name: _require_text(name, value) for name, value in filters.items()}
        needle = _fold(wanted['title_contains']) if 'title_contains' in wanted else None
        if needle == '':
            raise ValueError('title_contains must contain text')
        event_ids = self._event_ids()
        results = []
        for revision in self._revisions():
            events = event_ids.get((revision.article_id, revision.article_revision_id), ())
            if any(name in wanted and wanted[name] != getattr(revision, name) for name in _FIELD_FILTERS):
                continue
            if 'event_id' in wanted and wanted['event_id'] not in events:
                continue
            if needle is not None and needle not in _fold(revision.title):
                continue
            results.append(
                {
                    'article_id': revision.article_id,
                    'article_revision_id': revision.article_revision_id,
                    'revision_number': revision.revision_number,
                    'title': revision.title,
                    'topic': revision.topic,
                    'source_id': revision.source_id,
                    'fetched_at': revision.fetched_at,
                    'event_ids': events,
                }
            )
        return tuple(results)

    def count_new_articles(self, topic: str, business_date_utc: date | str) -> int:
        """Count distinct Articles resolved NEW_ARTICLE in topic whose fetched_at falls on the UTC business date (D8-B-10)."""
        _require_text('topic', topic)
        day = _business_date(business_date_utc)
        revisions = {revision.article_revision_id: revision for revision in self._revisions()}
        counted: set[str] = set()
        for resolution in self._uow.resolutions.list_all():
            if resolution.get('disposition') != NEW_ARTICLE:
                continue
            revision = revisions.get(resolution.get('article_revision_id'))
            if revision is None or revision.article_id != resolution.get('article_id'):
                raise LookupError(f"NEW_ARTICLE resolution {resolution.get('collected_document_id')} has no stored revision")
            fetched = parse_rfc3339(revision.fetched_at)
            if fetched is None:
                raise ValueError(f'fetched_at of {revision.article_revision_id} is not RFC3339')
            if revision.topic == topic and fetched.astimezone(timezone.utc).date() == day:
                counted.add(revision.article_id)
        return len(counted)
