"""Workspace-scoped SSE cursor policy and bounded replay coordination."""

from __future__ import annotations

import re
from typing import Protocol, TypeVar


MAX_CURSOR = 9223372036854775807
_CANONICAL_CURSOR = re.compile(r"[1-9][0-9]*\Z", re.ASCII)
RowT = TypeVar("RowT")


class SseReaderPort(Protocol[RowT]):
    def workspace_high_water(self, *, workspace_id: str) -> int: ...
    def retention_watermark(self, *, workspace_id: str) -> int | None: ...
    def cursor_exists(self, *, workspace_id: str, cursor: int) -> bool: ...
    def fetch_workspace_page(self, *, workspace_id: str, after_cursor: int,
                             limit: int = 100) -> list[RowT]: ...


def parse_cursor(value: str) -> int:
    if not _CANONICAL_CURSOR.fullmatch(value) or len(value) > 19:
        raise ValueError("INVALID_CURSOR")
    cursor = int(value)
    if cursor > MAX_CURSOR:
        raise ValueError("INVALID_CURSOR")
    return cursor


class SseStreamService:
    def __init__(self, reader: SseReaderPort[RowT]) -> None:
        self._reader = reader

    def initial_baseline(self, *, workspace_id: str) -> int:
        return self._reader.workspace_high_water(workspace_id=workspace_id)

    def replay_after(self, *, workspace_id: str, cursor: int) -> list[RowT]:
        return self._reader.fetch_workspace_page(
            workspace_id=workspace_id, after_cursor=cursor, limit=100,
        )

    def classify_cursor(self, *, workspace_id: str, cursor: int) -> str:
        if not 1 <= cursor <= MAX_CURSOR:
            return "invalid"
        watermark = self._reader.retention_watermark(workspace_id=workspace_id)
        if watermark is not None:
            if cursor < watermark:
                return "resync_required"
            if cursor == watermark:
                return "valid"
        if cursor > self._reader.workspace_high_water(workspace_id=workspace_id):
            return "ahead"
        if not self._reader.cursor_exists(workspace_id=workspace_id, cursor=cursor):
            return "unknown"
        return "valid"
