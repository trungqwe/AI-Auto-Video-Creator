"""Ports of module B (D8-B-13); in-memory adapters in ingestion.infrastructure.memory, PostgreSQL in REQ-B-CONV-02."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ingestion.domain.article import Article


@runtime_checkable
class ArticleRepository(Protocol):
    def get(self, article_id: str) -> Article | None: ...

    def find_by_identity_key(self, identity_key: str) -> Article | None: ...

    def find_by_exact_fingerprint(self, exact_fingerprint: str) -> Article | None: ...

    def list_all(self) -> tuple[Article, ...]: ...

    def save(self, article: Article) -> None: ...


@runtime_checkable
class ResolutionRepository(Protocol):
    """CollectedDocumentResolution keyed by (collected_document_id, dedup_policy_revision)."""

    def get(self, collected_document_id: str, dedup_policy_revision: str) -> Mapping[str, Any] | None: ...

    def list_all(self) -> tuple[Mapping[str, Any], ...]: ...

    def save(self, resolution: Mapping[str, Any]) -> None: ...


@runtime_checkable
class EventRepository(Protocol):
    def get(self, event_id: str) -> Mapping[str, Any] | None: ...

    def list_all(self) -> tuple[Mapping[str, Any], ...]: ...

    def save(self, event: Mapping[str, Any]) -> None: ...


@runtime_checkable
class RecordRepository(Protocol):
    """Supplementary records by kind: dedup_evidence, event_link_candidate, event_update, event_update_candidate."""

    def put(self, kind: str, record_id: str, record: Mapping[str, Any]) -> None: ...

    def get(self, kind: str, record_id: str) -> Mapping[str, Any] | None: ...

    def list(self, kind: str) -> tuple[Mapping[str, Any], ...]: ...


@runtime_checkable
class SourceTierLookup(Protocol):
    def tier_of(self, source_id: str) -> int: ...


@runtime_checkable
class OutboxWriter(Protocol):
    """Same signature as controlplane.domain.interfaces.outbox.IOutboxWriter.append_event."""

    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        deduplication_id: str,
    ) -> str: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """One transaction per collected document (D8-B-11); commit writes aggregates and outbox together."""

    articles: ArticleRepository
    resolutions: ResolutionRepository
    events: EventRepository
    records: RecordRepository
    outbox: OutboxWriter

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
