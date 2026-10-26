"""Read-only service behind the Dashboard story angles list (module D, RS-7).

One query reads cp_story_angles; the snapshot of an angle is found through its angle set and the exact analysis revision that set names, and is null when either link is missing. Rows carry only the registry columns.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT g.angle_id, ana.payload->>'snapshot_id', g.payload->>'title', g.payload->>'suitability', g.created_at "
    'FROM controlplane.cp_story_angles g '
    'LEFT JOIN controlplane.cp_story_angle_sets s ON s.workspace_id = g.workspace_id AND s.set_id = g.set_id '
    'LEFT JOIN controlplane.cp_content_analyses ana ON ana.workspace_id = s.workspace_id '
    "AND ana.record_key = s.payload->>'analysis_id' AND ana.revision::text = s.payload->>'analysis_revision' "
    'WHERE g.workspace_id = %s::uuid'
)


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    angle_id, snapshot_id, title, suitability, created_at = record
    return {'angle_id': angle_id, 'snapshot_id': snapshot_id, 'title': title, 'suitability': suitability, 'created_at': utc_text(created_at)}


class StoryAngleModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'created_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        if query.filters:
            raise ValueError(f'filter {query.filters[0][0]} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='g.created_at', id_sql='g.angle_id')
        params: list[Any] = [workspace_id, *cursor_params, query.limit + 1]
        statement = f'{_SELECT_SQL} AND {where_sql} {order_sql} LIMIT %s'
        with self._connection_scope() as connection:
            records = connection.execute(statement, params).fetchall()
        return page_of([_row(record) for record in records], query, 'created_at', 'angle_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND g.angle_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
