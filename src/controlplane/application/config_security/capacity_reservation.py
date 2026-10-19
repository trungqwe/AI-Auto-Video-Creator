"""J-12: Reservation capacity theo quota domain (CT-CAP-002, RM-RISK-007; ADR-0008, D8-J-07, D8-J-13).

Reservation in-memory tính theo quota domain (provider/project/model), không theo account. Không đọc đồng hồ, không sleep, không retry; thời gian do caller truyền và phải có múi giờ. Reservation chỉ là hint nội bộ, không phải cam kết của provider.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from controlplane.domain.config_security.capacity_snapshot import DomainCapacity

NO_CAPACITY = 'NO_CAPACITY'
CONFIDENCE_KNOWN = 'KNOWN'
CONFIDENCE_UNCERTAIN = 'UNCERTAIN'


class ReservationConflictError(Exception):
    """operation_key đã dùng với units hoặc domain_key khác."""


class CapacityUnavailableError(Exception):
    """Tổng đang giữ cộng units vượt remaining_requests của quota domain."""

    code = NO_CAPACITY

    def __init__(self, domain_key: str, retry_after: datetime | None) -> None:
        super().__init__(f'{NO_CAPACITY}: {domain_key}')
        self.domain_key = domain_key
        self.retry_after = retry_after


@dataclass(frozen=True)
class Reservation:
    reservation_ref: str
    domain_key: str
    units: int
    expires_at: datetime
    operation_key: str
    confidence_flag: str


class ReservationStorePort(Protocol):
    def get_by_operation(self, operation_key: str) -> Reservation | None: ...
    def list_by_domain(self, domain_key: str) -> tuple[Reservation, ...]: ...
    def list_all(self) -> tuple[Reservation, ...]: ...
    def add(self, reservation: Reservation) -> None: ...
    def remove(self, reservation_ref: str) -> Reservation | None: ...


class InMemoryReservationStore:
    def __init__(self) -> None:
        self._by_ref: dict[str, Reservation] = {}

    def get_by_operation(self, operation_key: str) -> Reservation | None:
        return next((item for item in self._by_ref.values() if item.operation_key == operation_key), None)

    def list_by_domain(self, domain_key: str) -> tuple[Reservation, ...]:
        return tuple(item for item in self._by_ref.values() if item.domain_key == domain_key)

    def list_all(self) -> tuple[Reservation, ...]:
        return tuple(self._by_ref.values())

    def add(self, reservation: Reservation) -> None:
        self._by_ref[reservation.reservation_ref] = reservation

    def remove(self, reservation_ref: str) -> Reservation | None:
        return self._by_ref.pop(reservation_ref, None)


def _new_reference() -> str:
    return f'res-{uuid.uuid4().hex}'


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _require_positive_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'{name} must be a positive integer')


def _require_aware_now(now: object) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be a timezone-aware datetime')


def _retry_after(domain_capacity: DomainCapacity, now: datetime) -> datetime | None:
    value = domain_capacity.reset_at
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(('Z', 'z')):
            text = text[:-1] + '+00:00'
        try:
            value = datetime.fromisoformat(text)
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value if value > now else None


class CapacityReservationBook:
    def __init__(self, store: ReservationStorePort | None = None, ref_factory: Callable[[], str] | None = None) -> None:
        self._store = store if store is not None else InMemoryReservationStore()
        self._ref_factory = ref_factory if ref_factory is not None else _new_reference

    def reserve(self, domain_key: str, units: int, ttl_seconds: int, operation_key: str, now: datetime, domain_capacity: DomainCapacity | None) -> Reservation:
        _require_text('domain_key', domain_key)
        _require_text('operation_key', operation_key)
        _require_positive_int('units', units)
        _require_positive_int('ttl_seconds', ttl_seconds)
        _require_aware_now(now)
        if domain_capacity is not None:
            if not isinstance(domain_capacity, DomainCapacity):
                raise ValueError('domain_capacity must be a DomainCapacity or None')
            if domain_capacity.domain_key != domain_key:
                raise ValueError('domain_capacity.domain_key must equal domain_key')
        try:
            expires_at = now + timedelta(seconds=ttl_seconds)
        except OverflowError as exc:
            raise ValueError('ttl_seconds is too large') from exc
        self.expire(now)
        existing = self._store.get_by_operation(operation_key)
        if existing is not None:
            if existing.units != units or existing.domain_key != domain_key:
                raise ReservationConflictError(operation_key)
            return existing
        remaining = None if domain_capacity is None else domain_capacity.remaining_requests
        if remaining is None:
            confidence_flag = CONFIDENCE_UNCERTAIN
        else:
            held = sum(item.units for item in self._store.list_by_domain(domain_key))
            if held + units > remaining:
                raise CapacityUnavailableError(domain_key, _retry_after(domain_capacity, now))
            confidence_flag = CONFIDENCE_KNOWN
        reservation = Reservation(
            reservation_ref=self._ref_factory(), domain_key=domain_key, units=units, expires_at=expires_at,
            operation_key=operation_key, confidence_flag=confidence_flag,
        )
        self._store.add(reservation)
        return reservation

    def release(self, reservation_ref: str) -> bool:
        _require_text('reservation_ref', reservation_ref)
        return self._store.remove(reservation_ref) is not None

    def expire(self, now: datetime) -> tuple[str, ...]:
        _require_aware_now(now)
        expired = tuple(item.reservation_ref for item in self._store.list_all() if now >= item.expires_at)
        for reservation_ref in expired:
            self._store.remove(reservation_ref)
        return expired
