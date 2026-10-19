"""Parameterized keyset SQL builder for list endpoints (H-04).

Pure module: identifiers come only from a frozen ListSpec whitelist and every user value
travels in params. The caller owns the connection; no database driver is imported here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from controlplane.application.projections.list_query import ListQuery, Page, build_page

_IDENTIFIER = re.compile(r"[a-z_.]+")
_ORDER_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}
_KEYSET_OPERATORS = {"asc": ">", "desc": "<"}


def _require_identifier(name: object) -> None:
    if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None:
        raise ValueError("invalid_identifier")


@dataclass(frozen=True)
class ListSpec:
    table: str
    id_column: str
    sort_columns: tuple[str, ...]
    filter_columns: tuple[str, ...]
    select_columns: tuple[str, ...]

    def __post_init__(self) -> None:
        groups = (self.sort_columns, self.filter_columns, self.select_columns)
        if not all(isinstance(group, tuple) for group in groups):
            raise ValueError("invalid_spec")
        names = (self.table, self.id_column, *self.sort_columns, *self.filter_columns, *self.select_columns)
        for name in names:
            _require_identifier(name)
        if (
            not self.sort_columns
            or self.id_column not in self.select_columns
            or not set(self.sort_columns) <= set(self.select_columns)
        ):
            raise ValueError("invalid_spec")


BATCHES_SPEC = ListSpec(
    table="controlplane.cp_production_batches",
    id_column="batch_id",
    sort_columns=("created_at",),
    filter_columns=("status",),
    select_columns=("batch_id", "status", "target_count", "created_at"),
)

JOBS_SPEC = ListSpec(
    table="controlplane.cp_video_jobs",
    id_column="job_id",
    sort_columns=("created_at",),
    filter_columns=("batch_id", "status"),
    select_columns=("job_id", "batch_id", "status", "snapshot_ref", "revision", "created_at"),
)


def build_list_sql(spec: ListSpec, query: ListQuery, *, workspace_id: str) -> tuple[str, tuple[object, ...]]:
    if query.sort_key not in spec.sort_columns:
        raise ValueError("column_not_allowed")
    if any(name not in spec.filter_columns for name, _ in query.filters):
        raise ValueError("column_not_allowed")
    if query.direction not in _ORDER_DIRECTIONS:
        raise ValueError("direction_invalid")
    if type(query.limit) is not int or query.limit < 1:
        raise ValueError("limit_invalid")

    conditions = ["workspace_id = %s"]
    params: list[object] = [workspace_id]
    for name, value in query.filters:
        conditions.append(f"{name} = %s")
        params.append(value)
    if query.cursor is not None:
        sort_value, row_id = query.cursor
        operator = _KEYSET_OPERATORS[query.direction]
        conditions.append(f"({query.sort_key}, {spec.id_column}) {operator} (%s, %s)")
        params.extend((sort_value, row_id))

    direction = _ORDER_DIRECTIONS[query.direction]
    sql = (
        f"SELECT {', '.join(spec.select_columns)} FROM {spec.table} "
        f"WHERE {' AND '.join(conditions)} "
        f"ORDER BY {query.sort_key} {direction}, {spec.id_column} {direction} LIMIT %s"
    )
    params.append(query.limit + 1)
    return sql, tuple(params)


def _plain_value(value: object) -> object:
    return value.isoformat() if hasattr(value, "isoformat") else value


def fetch_page(connection: Any, spec: ListSpec, query: ListQuery, *, workspace_id: str) -> Page:
    sql, params = build_list_sql(spec, query, workspace_id=workspace_id)
    rows = connection.execute(sql, params).fetchall()
    items = [
        {name: _plain_value(value) for name, value in zip(spec.select_columns, row, strict=True)}
        for row in rows
    ]
    return build_page(items, query=query, sort_field=query.sort_key, id_field=spec.id_column)
