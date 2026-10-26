"""Article context adapter of D (PW-D2): normalized article text for the data block of a model call.

Reads the article revisions pinned by a snapshot from cp_articles and cp_article_revisions through an injected connection factory; it imports no driver and writes nothing.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

REF_TYPE_ARTICLE_REVISION = 'article_revision'
_FIELDS = ('title', 'normalized_text', 'source_id', 'published_at', 'topic')
_QUERY = (
    'SELECT r.payload FROM controlplane.cp_article_revisions r '
    'JOIN controlplane.cp_articles a ON a.workspace_id = r.workspace_id AND a.article_id = r.article_id '
    "WHERE r.workspace_id = %s AND r.article_id = %s AND r.payload->>'article_revision_id' = %s"
)


class PostgresArticleContext:
    """ArticleContextPort over PostgreSQL: one item per article_revision ref in ref order; a revision that is not stored is left out, so the caller sees the gap."""

    def __init__(self, connect: Callable[[], Any]) -> None:
        if not callable(connect):
            raise TypeError('connect must be callable')
        self._connect = connect

    def articles(self, workspace_id: str, source_refs: Sequence[Mapping[str, str]]) -> tuple[dict[str, Any], ...]:
        items: list[dict[str, Any]] = []
        with self._connect() as connection:
            for ref in source_refs:
                if ref.get('ref_type') != REF_TYPE_ARTICLE_REVISION:
                    continue
                row = connection.execute(_QUERY, (workspace_id, ref['ref_id'], ref['revision_id'])).fetchone()
                if row is None:
                    continue
                payload = row[0] if isinstance(row[0], Mapping) else json.loads(row[0])
                items.append({'article_id': ref['ref_id'], 'article_revision_id': ref['revision_id'], **{name: payload.get(name) for name in _FIELDS}})
        return tuple(items)


__all__ = ['PostgresArticleContext']
