"""Read-only service behind the Dashboard articles list (module B, RS-2).

One query joins cp_articles with the cp_article_revisions row of the current revision; rows carry only the registry columns.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT a.article_id, r.payload->>'source_id', r.payload->>'title', r.payload->>'published_at', "
    "r.payload->>'raw_snapshot_ref', a.revision, a.updated_at "
    'FROM controlplane.cp_articles a '
    'JOIN controlplane.cp_article_revisions r '
    'ON r.workspace_id = a.workspace_id AND r.article_id = a.article_id AND r.revision = a.revision '
    'WHERE a.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'source_id': "r.payload->>'source_id' = %s"}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    article_id, source_id, title, published_at, fetch_evidence_ref, revision, updated_at = record
    return {
        'article_id': article_id,
        'source_id': source_id,
        'title': title,
        'published_at': published_at,
        'fetch_evidence_ref': fetch_evidence_ref,
        'revision': revision,
        'updated_at': utc_text(updated_at),
    }


class ArticleModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='a.updated_at', id_sql='a.article_id')
        clauses: list[str] = []
        params: list[Any] = [workspace_id]
        for name, value in query.filters:
            if name not in _SUPPORTED_FILTERS:
                raise ValueError(f'filter {name} is not supported')
            clauses.append(_SUPPORTED_FILTERS[name])
            params.append(value)
        conditions = ' AND '.join([*clauses, where_sql])
        params.extend(cursor_params)
        params.append(query.limit + 1)
        statement = f'{_SELECT_SQL} AND {conditions} {order_sql} LIMIT %s'
        with self._connection_scope() as connection:
            records = connection.execute(statement, params).fetchall()
        return page_of([_row(record) for record in records], query, 'updated_at', 'article_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND a.article_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
