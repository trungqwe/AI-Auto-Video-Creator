"""Article / ArticleRevision aggregate of module B (CT-CNT-003).

A stored ArticleRevision is immutable; Article.with_revision returns a new Article.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType


@dataclass(frozen=True, kw_only=True)
class ArticleRevision:
    article_revision_id: str
    article_id: str
    revision_number: int
    title: str
    normalized_text: str
    source_id: str
    source_revision: int
    collection_run_id: str
    collected_document_id: str
    requested_url: str
    final_url: str
    provenance_chain: tuple[Mapping[str, object], ...]
    raw_snapshot_ref: str | None
    published_at: str | None
    published_at_confidence: str
    fetched_at: str
    topic: str
    topic_uncertain: bool
    exact_fingerprint: str
    media_discovery_refs: tuple[str, ...]
    extractor_version: str
    normalizer_version: str
    is_complete: bool
    uncertain_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'provenance_chain', tuple(MappingProxyType(dict(step)) for step in self.provenance_chain))
        object.__setattr__(self, 'media_discovery_refs', tuple(self.media_discovery_refs))
        object.__setattr__(self, 'uncertain_fields', tuple(self.uncertain_fields))


@dataclass(frozen=True, kw_only=True)
class Article:
    article_id: str
    identity_key: str
    representative_source_id: str
    revisions: tuple[ArticleRevision, ...] = ()

    def __post_init__(self) -> None:
        revisions = tuple(self.revisions)
        seen: set[str] = set()
        for expected, revision in enumerate(revisions, start=1):
            if revision.article_id != self.article_id:
                raise ValueError(f'revision {revision.article_revision_id} belongs to another article')
            if isinstance(revision.revision_number, bool) or revision.revision_number != expected:
                raise ValueError(f'revision_number must be {expected}, got {revision.revision_number!r}')
            if revision.article_revision_id in seen:
                raise ValueError(f'duplicate article_revision_id {revision.article_revision_id}')
            seen.add(revision.article_revision_id)
        object.__setattr__(self, 'revisions', revisions)

    @property
    def latest_revision(self) -> ArticleRevision | None:
        return self.revisions[-1] if self.revisions else None

    @property
    def next_revision_number(self) -> int:
        return len(self.revisions) + 1

    def with_revision(self, revision: ArticleRevision) -> Article:
        return replace(self, revisions=(*self.revisions, revision))
