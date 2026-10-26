"""Read-only service behind the Dashboard media list (module C, RS-4); apply_update stays unavailable so PATCH answers 503."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT m.media_asset_id, m.payload->>'kind', m.payload->'rights'->>'status', m.status, m.revision, m.updated_at "
    'FROM controlplane.cp_media_assets m '
    'WHERE m.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'kind': "m.payload->>'kind' = %s", 'status': 'm.status = %s'}
_NAME_OPERATORS = {'asc': '>', 'desc': '<'}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    media_id, kind, rights_status, status, revision, updated_at = record
    return {
        'media_id': media_id,
        'kind': kind,
        'rights_status': rights_status,
        'status': status,
        'revision': revision,
        'updated_at': utc_text(updated_at),
    }


def _name_keyset(query: ListQuery) -> tuple[str, list[Any], str]:
    if query.direction not in _NAME_OPERATORS:
        raise ValueError('direction must be asc or desc')
    order_sql = f'ORDER BY m.media_asset_id {query.direction.upper()}'
    if query.cursor is None:
        return 'TRUE', [], order_sql
    sort_value, row_id = query.cursor
    if sort_value != row_id:
        raise ValueError('cursor does not belong to the name sort')
    return f'm.media_asset_id {_NAME_OPERATORS[query.direction]} %s', [row_id], order_sql


class MediaModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        query = replace(query, direction=effective_direction(request, query))
        if query.sort_key == 'updated_at':
            where_sql, cursor_params, order_sql = keyset(query, sort_sql='m.updated_at', id_sql='m.media_asset_id')
            sort_field = 'updated_at'
        elif query.sort_key == 'name':
            where_sql, cursor_params, order_sql = _name_keyset(query)
            sort_field = 'media_id'
        else:
            raise ValueError(f'sort {query.sort_key} is not supported')
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
        return page_of([_row(record) for record in records], query, sort_field, 'media_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND m.media_asset_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)

    def apply_update(self, *, request: Any, item_id: str, expected_revision: int, changes: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        raise CapabilityUnavailableError('media')
