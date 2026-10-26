"""Read-only service behind the Dashboard cost list (module J, RS-11).

One query reads cp_cost_records; rows carry only the registry columns. The amount is the exact decimal text of the actual cost when present, otherwise of the estimated cost, and amount_basis says which one was used.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page
from controlplane.infrastructure.read_screens.common import ConnectionScope, effective_direction, keyset, page_of, utc_text

_SELECT_SQL = (
    'SELECT c.record_id, c.job_ref, c.provider, c.estimated_cost, c.actual_cost, c.currency, c.occurred_at '
    'FROM controlplane.cp_cost_records c '
    'WHERE c.workspace_id = %s::uuid'
)
_SUPPORTED_FILTERS = {
    'provider': 'c.provider = %s',
    'job_id': 'c.job_ref = %s',
}


def _amount(actual: Decimal | None, estimated: Decimal) -> tuple[str, str]:
    if actual is not None:
        return format(actual, 'f'), 'actual'
    return format(estimated, 'f'), 'estimated'


def _row(record: tuple[Any, ...]) -> dict[str, object]:
    record_id, job_ref, provider, estimated_cost, actual_cost, currency, occurred_at = record
    amount, amount_basis = _amount(actual_cost, estimated_cost)
    return {
        'cost_id': record_id,
        'job_id': job_ref,
        'provider': provider,
        'amount': amount,
        'currency': currency,
        'amount_basis': amount_basis,
        'recorded_at': utc_text(occurred_at),
    }


class CostModuleService:
    def __init__(self, connection_scope: ConnectionScope) -> None:
        self._connection_scope = connection_scope

    def fetch_page(self, request: Any, workspace_id: str, query: ListQuery) -> Page:
        if query.sort_key != 'recorded_at':
            raise ValueError(f'sort {query.sort_key} is not supported')
        query = replace(query, direction=effective_direction(request, query))
        where_sql, cursor_params, order_sql = keyset(query, sort_sql='c.occurred_at', id_sql='c.record_id')
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
        return page_of([_row(r) for r in records], query, 'recorded_at', 'cost_id')

    def fetch_one(self, request: Any, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._connection_scope() as connection:
            record = connection.execute(f'{_SELECT_SQL} AND c.record_id = %s', (workspace_id, item_id)).fetchone()
        return None if record is None else _row(record)
