"""Read-only service behind the Dashboard events list (module B, RS-3).

One query joins cp_events with the cp_article_revisions row of the representative article (assumption RS-01: first entry of payload.member_refs); rows carry only the registry columns.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT e.event_id, r.payload->>'title', e.payload->>'status', r.payload->>'source_id', "
    "r.payload->>'raw_snapshot_ref', e.revision, e.updated_at "
    'FROM controlplane.cp_events e '
    'LEFT JOIN controlplane.cp_article_revisions r '
    'ON r.workspace_id = e.workspace_id '
    "AND r.article_id = e.payload->'member_refs'->0->>0 "
    "AND r.payload->>'article_revision_id' = e.payload->'member_refs'->0->>1 "
    'WHERE e.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'status': "e.payload->>'status' = %s"}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    event_id, title, status, source_id, fetch_evidence_ref, revision, updated_at = record
    return {
        'event_id': event_id,
        'title': title,
        'status': status,
        'source_id': source_id,
        'fetch_evidence_ref': fetch_evidence_ref,
        'revision': revision,
        'updated_at': utc_text(updated_at),
    }


class EventModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='e.updated_at', id_sql='e.event_id')
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
        return page_of([_row(record) for record in records], query, 'updated_at', 'event_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND e.event_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
