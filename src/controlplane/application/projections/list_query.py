"""Keyset pagination and whitelisted filter/sort parsing for list endpoints (H-02).

Pure module: no database access, no clock, stdlib only.
"""

from __future__ import annotations

import base64
import json
import string
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

MAX_CURSOR_LENGTH = 512
FORBIDDEN_FILTERS = frozenset({"workspace_id", "actor_id"})

_CONTROL_PARAMS = frozenset({"limit", "cursor", "sort", "direction"})
_DIRECTIONS = ("asc", "desc")
_DEFAULT_DIRECTION = "asc"
_LIMIT_DIGITS = frozenset("0123456789")
_MAX_LIMIT_CHARS = 18
_CURSOR_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")


class ListQueryError(Exception):
    """Rejected list parameter; code is limit_invalid, sort_not_allowed, filter_not_allowed or cursor_invalid."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


@dataclass(frozen=True)
class ListQuery:
    limit: int
    cursor: tuple[str, str] | None
    sort_key: str
    direction: str
    filters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Page:
    items: tuple[Mapping[str, object], ...]
    next_cursor: str | None


def encode_cursor(sort_value: str, row_id: str) -> str:
    if not isinstance(sort_value, str) or not isinstance(row_id, str):
        raise ValueError("cursor values must be strings")
    payload = json.dumps([sort_value, row_id], separators=(",", ":")).encode("ascii")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(token) > MAX_CURSOR_LENGTH:
        raise ValueError("cursor exceeds MAX_CURSOR_LENGTH")
    return token


def _invalid_cursor() -> ListQueryError:
    return ListQueryError("cursor_invalid", "cursor")


def decode_cursor(cursor: str) -> tuple[str, str]:
    if (
        not isinstance(cursor, str)
        or not cursor
        or len(cursor) > MAX_CURSOR_LENGTH
        or not set(cursor) <= _CURSOR_ALPHABET
        or len(cursor) % 4 == 1
    ):
        raise _invalid_cursor()
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        raise _invalid_cursor() from None
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, str) for item in value):
        raise _invalid_cursor()
    return value[0], value[1]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_list_query(
    params: Mapping[str, object],
    *,
    allowed_sorts: Sequence[str],
    allowed_filters: Collection[str],
    default_limit: int,
    max_limit: int,
) -> ListQuery:
    if not _is_int(default_limit) or not _is_int(max_limit) or not 1 <= default_limit <= max_limit:
        raise ValueError("require 1 <= default_limit <= max_limit")
    if isinstance(allowed_sorts, str) or not allowed_sorts:
        raise ValueError("allowed_sorts must be a non-empty sequence of names")
    if isinstance(allowed_filters, str):
        raise ValueError("allowed_filters must be a collection of names")

    filters: list[tuple[str, str]] = []
    for name in sorted(params):
        if name in _CONTROL_PARAMS:
            continue
        value = params[name]
        if name in FORBIDDEN_FILTERS or name not in allowed_filters or not isinstance(value, str):
            raise ListQueryError("filter_not_allowed", name)
        filters.append((name, value))

    limit = default_limit
    if "limit" in params:
        raw_limit = params["limit"]
        if (
            not isinstance(raw_limit, str)
            or not raw_limit
            or len(raw_limit) > _MAX_LIMIT_CHARS
            or not set(raw_limit) <= _LIMIT_DIGITS
        ):
            raise ListQueryError("limit_invalid", "limit")
        limit = int(raw_limit)
        if not 1 <= limit <= max_limit:
            raise ListQueryError("limit_invalid", "limit")

    sort_key = allowed_sorts[0]
    if "sort" in params:
        sort_key = params["sort"]
        if not isinstance(sort_key, str) or sort_key not in allowed_sorts:
            raise ListQueryError("sort_not_allowed", "sort")

    direction = _DEFAULT_DIRECTION
    if "direction" in params:
        direction = params["direction"]
        if not isinstance(direction, str) or direction not in _DIRECTIONS:
            raise ListQueryError("sort_not_allowed", "direction")

    cursor = decode_cursor(params["cursor"]) if "cursor" in params else None
    return ListQuery(
        limit=limit,
        cursor=cursor,
        sort_key=sort_key,
        direction=direction,
        filters=tuple(filters),
    )


def build_page(
    rows: Sequence[Mapping[str, object]],
    *,
    query: ListQuery,
    sort_field: str,
    id_field: str,
) -> Page:
    items = tuple(rows[: query.limit])
    if len(rows) <= query.limit:
        return Page(items=items, next_cursor=None)
    last = items[-1]
    return Page(items=items, next_cursor=encode_cursor(last[sort_field], last[id_field]))
