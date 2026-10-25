"""Shared helpers for the read_screens services: UTC text, cursor time, keyset SQL fragments and nested payload reads.

Pure module: no database access and no environment access; stdlib and list_query only.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, ContextManager

from controlplane.application.projections.list_query import ListQuery, Page, build_page

ConnectionScope = Callable[[], ContextManager[Any]]

_RFC3339 = re.compile(r'(\d{4}-\d{2}-\d{2})[Tt](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})', re.ASCII)
_SQL_DIRECTIONS = {'asc': 'ASC', 'desc': 'DESC'}
_CURSOR_OPERATORS = {'asc': '>', 'desc': '<'}


def utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def parse_cursor_time(value: str) -> datetime:
    match = _RFC3339.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError('cursor time is not an RFC 3339 timestamp')
    day, clock, fraction, offset = match.groups()
    micros = (fraction or '0')[:6].ljust(6, '0')
    zone = '+00:00' if offset in ('Z', 'z') else offset
    try:
        return datetime.fromisoformat(f'{day}T{clock}.{micros}{zone}').astimezone(timezone.utc)
    except OverflowError:
        raise ValueError('cursor time is out of range') from None


def effective_direction(request: Any, query: ListQuery) -> str:
    return query.direction if 'direction' in request.query_params else 'desc'


def keyset(query: ListQuery, *, sort_sql: str, id_sql: str) -> tuple[str, list[Any], str]:
    if query.direction not in _SQL_DIRECTIONS:
        raise ValueError('direction must be asc or desc')
    direction = _SQL_DIRECTIONS[query.direction]
    order_sql = f'ORDER BY {sort_sql} {direction}, ({id_sql})::text {direction}'
    if query.cursor is None:
        return 'TRUE', [], order_sql
    sort_value, row_id = query.cursor
    where_sql = f'({sort_sql}, ({id_sql})::text) {_CURSOR_OPERATORS[query.direction]} (%s::timestamptz, %s)'
    return where_sql, [parse_cursor_time(sort_value), row_id], order_sql


def page_of(rows: Sequence[Mapping[str, object]], query: ListQuery, sort_field: str, id_field: str) -> Page:
    return build_page(rows, query=query, sort_field=sort_field, id_field=id_field)


def pick(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current
