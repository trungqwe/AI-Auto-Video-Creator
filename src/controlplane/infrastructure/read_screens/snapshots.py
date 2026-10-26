"""Read-only service behind the Dashboard snapshots list (module D, RS-6).

One query reads cp_production_snapshots and takes the newest content analysis of each snapshot through LEFT JOIN LATERAL, so a snapshot is never repeated; rows carry only the registry columns.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    "SELECT s.snapshot_id, s.payload->>'video_job_ref', ana.model, ana.prompt_ref, s.configuration_bundle_fingerprint, s.created_at "
    'FROM controlplane.cp_production_snapshots s '
    'LEFT JOIN LATERAL ('
    "SELECT a.payload->'trace'->>'model' AS model, "
    "(a.payload->'trace'->'prompt_ref'->>'ref_id') || '@' || (a.payload->'trace'->'prompt_ref'->>'revision_id') AS prompt_ref "
    'FROM controlplane.cp_content_analyses a '
    "WHERE a.workspace_id = s.workspace_id AND a.payload->>'snapshot_id' = s.snapshot_id "
    'ORDER BY a.created_at DESC, a.revision DESC, a.record_key DESC LIMIT 1'
    ') ana ON TRUE '
    'WHERE s.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {'job_id': "s.payload->>'video_job_ref' = %s"}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    snapshot_id, job_id, model, prompt_ref, config_revision_ref, created_at = record
    return {'snapshot_id': snapshot_id, 'job_id': job_id, 'model': model, 'prompt_ref': prompt_ref, 'config_revision_ref': config_revision_ref, 'created_at': utc_text(created_at)}


class SnapshotModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'created_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='s.created_at', id_sql='s.snapshot_id')
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
        return page_of([_row(record) for record in records], query, 'created_at', 'snapshot_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND s.snapshot_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
