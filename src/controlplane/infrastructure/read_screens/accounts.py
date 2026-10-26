"""Read-only service behind the Dashboard accounts list (module J, RS-10).

One query reads cp_external_accounts; rows carry only the registry columns.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import (
    ConnectionScope,
    effective_direction,
    keyset,
    page_of,
    utc_text,
)

_SELECT_SQL = (
    'SELECT a.external_account_id, a.provider, a.account_label, a.status, a.updated_at '
    'FROM controlplane.cp_external_accounts a '
    'WHERE a.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {
    'provider': 'a.provider = %s',
    'status': 'a.status = %s',
}


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    external_account_id, provider, account_label, status, updated_at = record
    return {
        'account_ref': external_account_id,
        'provider': provider,
        'account_label': account_label,
        'status': status,
        'updated_at': utc_text(updated_at),
    }


class AccountModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'updated_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='a.updated_at', id_sql='a.external_account_id')
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
        return page_of([_row(r) for r in records], query, 'updated_at', 'account_ref')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(
                f'{_SELECT_SQL} AND a.external_account_id = %s',
                (workspace_id, item_id),
            ).fetchone()
        return None if record is None else _row(record)
