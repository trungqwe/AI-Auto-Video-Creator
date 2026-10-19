"""J-16: adapter capability health từ ProviderCapacitySnapshot (CT-CAP-003, CT-CAP-001).

Pure application adapter: không I/O, không đọc đồng hồ (now do caller truyền, phải có múi giờ), không mutation snapshot.
Heartbeat chỉ là bằng chứng sức khỏe; module chỉ dựng observation và CapabilityView, không tạo quyền thực thi.
Phân loại trạng thái do controlplane.config.capability_view quyết định (import chỉ đọc).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from controlplane.config.capability_view import CapabilityView, project_latest_capability_views
from controlplane.domain.config_security.capacity_snapshot import CONFIDENCE_UNKNOWN, ProviderCapacitySnapshot, effective_confidence


def _aware(value: object) -> datetime | None:
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(('Z', 'z')):
            text = text[:-1] + '+00:00'
        try:
            value = datetime.fromisoformat(text)
        except ValueError:
            return None
    if isinstance(value, datetime) and value.utcoffset() is not None:
        return value
    return None


def _time_text(value: datetime | str | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def _backoff_active(snapshot: ProviderCapacitySnapshot, now: datetime) -> bool:
    """Backoff còn hiệu lực khi backoff_until sau now; giá trị naive hoặc không parse được coi là còn hiệu lực (fail-closed)."""
    if snapshot.backoff_until is None:
        return False
    until = _aware(snapshot.backoff_until)
    return until is None or until > now


def snapshot_to_observation(snapshot: ProviderCapacitySnapshot, now: datetime, location: str = 'cloud') -> dict[str, object]:
    if not isinstance(snapshot, ProviderCapacitySnapshot):
        raise TypeError('snapshot must be a ProviderCapacitySnapshot')
    confidence = effective_confidence(snapshot, now)
    observation: dict[str, object] = {
        'provider': snapshot.provider,
        'capability_type': snapshot.capability,
        'account_scope': f'{snapshot.account}:{snapshot.project}',
        'used': snapshot.used_requests,
        'health': snapshot.health,
        'confidence': confidence,
        'observed_at': _time_text(snapshot.observed_at),
        'expires_at': _time_text(snapshot.expires_at),
        'reset_at': _time_text(snapshot.reset_at),
        'backoff_active': _backoff_active(snapshot, now),
        'location': location,
    }
    if snapshot.limit_requests is not None:
        observation['limit'] = snapshot.limit_requests
    if confidence == CONFIDENCE_UNKNOWN:
        observation['is_quota_uncertain'] = True
    return observation


def project_capability_health(snapshots: Iterable[ProviderCapacitySnapshot], now: datetime, location: str = 'cloud') -> list[CapabilityView]:
    return project_latest_capability_views([snapshot_to_observation(snap, now, location) for snap in snapshots])