"""PW-A1: nạp bảy nguồn seed của tools/launcher/prod/sources.json qua SourceCommandHandler.register_source (FR-COL-001).

Idempotent: mỗi nguồn dùng khoá idempotency cố định theo `code`, chạy lại chỉ phát lại receipt cũ và không tạo nguồn đôi.
Toàn bộ tệp được kiểm trước khi ghi nguồn nào. Nguồn đã đăng ký bằng khoá khác được đếm là existing; nguồn đã bị xoá (tombstone) không bị đăng ký lại.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from source_ingestion.application.source_commands import SourceAlreadyRegisteredError, TombstoneConflictError

ACTOR = 'pw-a1-seed'
CORRELATION_ID = 'pw-a1-seed'
IDEMPOTENCY_PREFIX = 'pw-a1:seed-source:'
SEED_TOPICS = ('news',)
_REQUIRED_TEXT = ('code', 'url', 'source_kind', 'tier')


class SeedSourcesError(ValueError):
    pass


@dataclass(frozen=True)
class SeedSourcesReport:
    registered: int
    replayed: int
    existing: int
    tombstoned: int


def _load_sources(path: str | Path) -> list[dict[str, Any]]:
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    sources = document.get('sources') if isinstance(document, dict) else None
    if not isinstance(sources, list) or not sources:
        raise SeedSourcesError('sources must be a non-empty list')
    codes: set[str] = set()
    for item in sources:
        if not isinstance(item, dict):
            raise SeedSourcesError('each source must be an object')
        for field in _REQUIRED_TEXT:
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SeedSourcesError('source field ' + field + ' must be a non-empty string')
        if not item['url'].startswith('https://'):
            raise SeedSourcesError('source ' + item['code'] + ' must use https')
        if not isinstance(item.get('enabled', True), bool):
            raise SeedSourcesError('source ' + item['code'] + ' enabled must be a bool')
        if item['code'] in codes:
            raise SeedSourcesError('duplicate source code ' + item['code'])
        codes.add(item['code'])
    return sources


def seed_sources(
    handler: Any, path: str | Path, *, workspace_id: str, topics: tuple[str, ...] = SEED_TOPICS
) -> SeedSourcesReport:
    registered = replayed = existing = tombstoned = 0
    for item in _load_sources(path):
        try:
            result = handler.register_source(
                workspace_id=workspace_id,
                idempotency_key=IDEMPOTENCY_PREFIX + item['code'],
                actor=ACTOR,
                correlation_id=CORRELATION_ID,
                locator=item['url'],
                name=item['code'],
                source_kind=item['source_kind'],
                tier=item['tier'],
                topics=topics,
                collection_enabled=item.get('enabled', True),
            )
        except SourceAlreadyRegisteredError:
            existing += 1
        except TombstoneConflictError:
            tombstoned += 1
        else:
            if result.replayed:
                replayed += 1
            else:
                registered += 1
    return SeedSourcesReport(registered, replayed, existing, tombstoned)


__all__ = ['SeedSourcesError', 'SeedSourcesReport', 'seed_sources']
