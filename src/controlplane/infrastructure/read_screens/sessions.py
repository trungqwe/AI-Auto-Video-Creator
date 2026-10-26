"""Read-only service behind the Dashboard sessions list (module G, RS-9).

One query reads cp_app_sessions; rows carry only the registry columns. The recovery marker stays in the table and is never selected, and the authentication session table is never touched.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    'SELECT s.session_ref, s.status, s.started_at, s.ended_at '
    'FROM controlplane.cp_app_sessions s '
    'WHERE s.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'status': 's.status = %s'}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    session_ref, status, started_at, ended_at = record
    return {
        'session_id': session_ref,
        'status': status,
        'started_at': utc_text(started_at),
        'finished_at': None if ended_at is None else utc_text(ended_at),
    }


class SessionModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'started_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='s.started_at', id_sql='s.session_ref')
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
        return page_of([_row(record) for record in records], query, 'started_at', 'session_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND s.session_ref = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
