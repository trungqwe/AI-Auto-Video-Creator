"""In-memory adapters for module B ports (D8-B-13).

Writes are staged inside `with uow:`; commit applies aggregates and outbox records together.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ingestion.domain.article import Article

KIND_ARTICLE = 'article'
KIND_RESOLUTION = 'collected_document_resolution'
KIND_EVENT = 'event'
RESERVED_KINDS = frozenset({KIND_ARTICLE, KIND_RESOLUTION, KIND_EVENT})


@dataclass(frozen=True)
class OutboxRecord:
    event_id: str
    event_type: str
    aggregate_id: str
    payload: Mapping[str, object]
    deduplication_id: str


class InMemoryUnitOfWork:
    def __init__(self, id_factory: Callable[[], str] | None = None) -> None:
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._committed: dict[str, dict[object, object]] = {}
        self._committed_outbox: list[OutboxRecord] = []
        self._staged: dict[str, dict[object, object]] = {}
        self._staged_outbox: list[OutboxRecord] = []
        self._active = False
        self.articles = _ArticleRepository(self)
        self.resolutions = _ResolutionRepository(self)
        self.events = _EventRepository(self)
        self.records = _RecordRepository(self)
        self.outbox = _OutboxWriter(self)

    def __enter__(self) -> InMemoryUnitOfWork:
        if self._active:
            raise RuntimeError('unit of work is already active')
        self._active = True
        self.rollback()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.rollback()
        self._active = False

    def commit(self) -> None:
        self._require_active()
        committed = {kind: dict(records) for kind, records in self._committed.items()}
        for kind, records in self._staged.items():
            committed.setdefault(kind, {}).update(records)
        outbox = [*self._committed_outbox, *self._staged_outbox]
        self._committed, self._committed_outbox = committed, outbox
        self.rollback()

    def rollback(self) -> None:
        self._staged = {}
        self._staged_outbox = []

    def committed(self, kind: str) -> tuple[object, ...]:
        return tuple(self._committed.get(kind, {}).values())

    def committed_outbox(self) -> tuple[OutboxRecord, ...]:
        return tuple(self._committed_outbox)

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError('unit of work is not active; use `with uow:`')

    def _put(self, kind: str, key: object, record: object) -> None:
        self._require_active()
        self._staged.setdefault(kind, {})[key] = record

    def _get(self, kind: str, key: object) -> object | None:
        staged = self._staged.get(kind, {})
        if key in staged:
            return staged[key]
        return self._committed.get(kind, {}).get(key)

    def _list(self, kind: str) -> tuple[object, ...]:
        merged = dict(self._committed.get(kind, {}))
        merged.update(self._staged.get(kind, {}))
        return tuple(merged.values())

    def _append_event(self, event_type: str, aggregate_id: str, payload: Mapping[str, object], deduplication_id: str) -> str:
        self._require_active()
        if not isinstance(deduplication_id, str) or not deduplication_id:
            raise ValueError('deduplication_id must be a non-empty string')
        for existing in (*self._committed_outbox, *self._staged_outbox):
            if existing.deduplication_id == deduplication_id:
                return existing.event_id
        event_id = self._id_factory()
        record = OutboxRecord(event_id, event_type, aggregate_id, MappingProxyType(dict(payload)), deduplication_id)
        self._staged_outbox.append(record)
        return event_id


class _ArticleRepository:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    def get(self, article_id: str) -> Article | None:
        return self._uow._get(KIND_ARTICLE, article_id)

    def find_by_identity_key(self, identity_key: str) -> Article | None:
        return next((a for a in self.list_all() if a.identity_key == identity_key), None)

    def find_by_exact_fingerprint(self, exact_fingerprint: str) -> Article | None:
        matches = (a for a in self.list_all() if any(r.exact_fingerprint == exact_fingerprint for r in a.revisions))
        return next(matches, None)

    def list_all(self) -> tuple[Article, ...]:
        return self._uow._list(KIND_ARTICLE)

    def save(self, article: Article) -> None:
        if not isinstance(article, Article):
            raise TypeError('article must be an Article')
        stored = self.get(article.article_id)
        if stored is not None and article.revisions[: len(stored.revisions)] != stored.revisions:
            raise ValueError(f'stored revisions of {article.article_id} are immutable')
        self._uow._put(KIND_ARTICLE, article.article_id, article)


class _ResolutionRepository:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    def get(self, collected_document_id: str, dedup_policy_revision: str) -> Mapping[str, object] | None:
        return self._uow._get(KIND_RESOLUTION, (collected_document_id, dedup_policy_revision))

    def list_all(self) -> tuple[Mapping[str, object], ...]:
        return self._uow._list(KIND_RESOLUTION)

    def save(self, resolution: Mapping[str, object]) -> None:
        key = (resolution['collected_document_id'], resolution['dedup_policy_revision'])
        self._uow._put(KIND_RESOLUTION, key, MappingProxyType(dict(resolution)))


class _EventRepository:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    def get(self, event_id: str) -> Mapping[str, object] | None:
        return self._uow._get(KIND_EVENT, event_id)

    def list_all(self) -> tuple[Mapping[str, object], ...]:
        return self._uow._list(KIND_EVENT)

    def save(self, event: Mapping[str, object]) -> None:
        self._uow._put(KIND_EVENT, event['event_id'], MappingProxyType(dict(event)))


class _RecordRepository:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    def put(self, kind: str, record_id: str, record: Mapping[str, object]) -> None:
        if kind in RESERVED_KINDS:
            raise ValueError(f'kind {kind} has a dedicated repository')
        self._uow._put(kind, record_id, MappingProxyType(dict(record)))

    def get(self, kind: str, record_id: str) -> Mapping[str, object] | None:
        return self._uow._get(kind, record_id)

    def list(self, kind: str) -> tuple[Mapping[str, object], ...]:
        return self._uow._list(kind)


class _OutboxWriter:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, object],
        deduplication_id: str,
    ) -> str:
        return self._uow._append_event(event_type, aggregate_id, payload, deduplication_id)


class InMemorySourceTierLookup:
    def __init__(self, tiers: Mapping[str, int]) -> None:
        self._tiers = dict(tiers)

    def tier_of(self, source_id: str) -> int:
        if source_id not in self._tiers:
            raise LookupError(f'unknown source_id {source_id}')
        return self._tiers[source_id]
