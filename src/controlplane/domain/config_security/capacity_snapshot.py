"""J-07: ProviderCapacitySnapshot và quota domain (CT-CAP-001, RM-RISK-007; ADR-0008, D8-J-13).

Pure domain: không I/O, không đọc đồng hồ, không mutation; thời gian do caller truyền và phải có múi giờ.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

CONFIDENCE_OBSERVED = 'observed'
CONFIDENCE_ESTIMATED = 'estimated'
CONFIDENCE_UNKNOWN = 'unknown'
CONFIDENCE_VALUES = (CONFIDENCE_OBSERVED, CONFIDENCE_ESTIMATED, CONFIDENCE_UNKNOWN)
QUOTA_KINDS = ('requests', 'tokens', 'storage_bytes')
_OLDEST = datetime(1, 1, 2, tzinfo=timezone.utc)


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _require_count(name: str, value: object, *, optional: bool) -> None:
    if optional and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a non-negative integer')


def _require_measure(name: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be a non-negative finite number or None')


def _require_str(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')


def _require_time_value(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, (str, datetime)):
        raise ValueError(f'{name} must be a datetime, an ISO 8601 string or None')


@dataclass(frozen=True)
class ProviderCapacitySnapshot:
    snapshot_id: str
    provider: str
    model: str
    project: str
    account: str
    capability: str
    limit_requests: int | None = None
    used_requests: int = 0
    limit_tokens: int | None = None
    used_tokens: int = 0
    limit_storage_bytes: int | None = None
    used_storage_bytes: int = 0
    reset_at: datetime | str | None = None
    backoff_until: datetime | str | None = None
    health: str = 'unknown'
    latency_ms: float | None = None
    error_rate: float | None = None
    confidence: str = 'unknown'
    source: str = ''
    observed_at: datetime | str | None = None
    expires_at: datetime | str | None = None

    def __post_init__(self) -> None:
        for name in ('snapshot_id', 'provider', 'model', 'project', 'account', 'capability'):
            _require_text(name, getattr(self, name))
        for name in ('limit_requests', 'limit_tokens', 'limit_storage_bytes'):
            _require_count(name, getattr(self, name), optional=True)
        for name in ('used_requests', 'used_tokens', 'used_storage_bytes'):
            _require_count(name, getattr(self, name), optional=False)
        for name in ('latency_ms', 'error_rate'):
            _require_measure(name, getattr(self, name))
        if not isinstance(self.confidence, str) or self.confidence not in CONFIDENCE_VALUES:
            raise ValueError(f'confidence must be one of {CONFIDENCE_VALUES}')
        for name in ('health', 'source'):
            _require_str(name, getattr(self, name))
        for name in ('reset_at', 'backoff_until', 'observed_at', 'expires_at'):
            _require_time_value(name, getattr(self, name))


@dataclass(frozen=True)
class DomainCapacity:
    domain_key: str
    limit_requests: int | None
    used_requests: int
    remaining_requests: int | None
    health: str
    confidence: str
    reset_at: datetime | str | None
    observed_at: datetime | str | None


def quota_domain_key(provider: str, project: str, model: str) -> str:
    """Quota domain is provider/project/model without account."""
    for part in (provider, project, model):
        _require_text('domain key part', part)
    return '/'.join(quote(part, safe='') for part in (provider, project, model))


def _parse_aware(value: object) -> datetime | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(('Z', 'z')):
            text = text[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value
    return None


def _require_aware_now(now: object) -> None:
    if not isinstance(now, datetime) or _parse_aware(now) is None:
        raise ValueError('now must be a timezone-aware datetime')


def is_expired(snapshot: ProviderCapacitySnapshot, now: datetime) -> bool:
    _require_aware_now(now)
    if snapshot.expires_at is None:
        return False
    expires_at = _parse_aware(snapshot.expires_at)
    return expires_at is None or now >= expires_at


def effective_confidence(snapshot: ProviderCapacitySnapshot, now: datetime) -> str:
    if is_expired(snapshot, now):
        return CONFIDENCE_UNKNOWN
    return snapshot.confidence


def remaining(snapshot: ProviderCapacitySnapshot, kind: str, now: datetime) -> int | None:
    if kind not in QUOTA_KINDS:
        raise ValueError(f'kind must be one of {QUOTA_KINDS}')
    if effective_confidence(snapshot, now) == CONFIDENCE_UNKNOWN:
        return None
    limit = getattr(snapshot, f'limit_{kind}')
    if limit is None:
        return None
    return max(limit - getattr(snapshot, f'used_{kind}'), 0)


def merge_quota_domain(snapshots: Iterable[ProviderCapacitySnapshot], now: datetime) -> dict[str, DomainCapacity]:
    """Merge snapshots by quota domain taking the newest snapshot per observed_at."""
    _require_aware_now(now)
    order: list[str] = []
    latest: dict[str, tuple[tuple[datetime, int], ProviderCapacitySnapshot]] = {}
    for index, snap in enumerate(snapshots):
        key = quota_domain_key(snap.provider, snap.project, snap.model)
        rank = (_parse_aware(snap.observed_at) or _OLDEST, index)
        if key not in latest:
            order.append(key)
            latest[key] = (rank, snap)
        elif rank >= latest[key][0]:
            latest[key] = (rank, snap)

    result: dict[str, DomainCapacity] = {}
    for key in order:
        _, snap = latest[key]
        result[key] = DomainCapacity(
            domain_key=key,
            limit_requests=snap.limit_requests,
            used_requests=snap.used_requests,
            remaining_requests=remaining(snap, 'requests', now),
            health=snap.health,
            confidence=effective_confidence(snap, now),
            reset_at=snap.reset_at,
            observed_at=snap.observed_at,
        )
    return result
