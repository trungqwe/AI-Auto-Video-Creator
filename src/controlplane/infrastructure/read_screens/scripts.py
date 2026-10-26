"""Read-only service behind the Dashboard scripts list (module D, RS-8).

One query reads cp_script_versions; rows carry only the registry columns. The narration, hook, thumbnail transition and pronunciation hints stay in the stored payload and are never selected.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT v.script_version_id, v.payload->>'language', (v.payload->>'estimated_duration_seconds')::double precision, "
    'v.revision, v.created_at '
    'FROM controlplane.cp_script_versions v '
    'WHERE v.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'language': "v.payload->>'language' = %s"}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    script_id, language, estimated_duration_seconds, revision, created_at = record
    return {
        'script_id': script_id,
        'language': language,
        'estimated_duration_seconds': estimated_duration_seconds,
        'revision': revision,
        'created_at': utc_text(created_at),
    }


class ScriptModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'created_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='v.created_at', id_sql='v.script_version_id')
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
        return page_of([_row(record) for record in records], query, 'created_at', 'script_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND v.script_version_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
