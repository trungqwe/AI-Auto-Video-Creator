"""J-08: IncrementalCostRecord và dự báo ngân sách 80% (CT-COST-001, QR-COST-001).

Pure domain: no I/O, no clock; caller passes window_start, window_end and now as timezone-aware datetimes (D8-J-06).
Money is Decimal only. Budget warning is a forecast; hard_stop is off by default and never blocks without a configured limit (D8-J-05).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

ALLOWED_COST_CATEGORIES = frozenset({'api_paid', 'background_service', 'extra_storage', 'other_direct'})
EXCLUDED_COST_CATEGORIES = frozenset({'existing_plan', 'electricity', 'internet', 'hardware'})
REASON_FORECAST_80 = 'FORECAST_80'
REASON_SPENT_80 = 'SPENT_80'
REASON_LIMIT_REACHED = 'LIMIT_REACHED'
_MICROSECOND = timedelta(microseconds=1)


class NotIncrementalCostError(ValueError):
    """Category is not a project incremental cost."""


class InvalidAmountError(ValueError):
    """Amount is not a finite non-negative Decimal."""


class CurrencyMismatchError(ValueError):
    """A record inside the window uses a currency different from the policy."""


def _require_amount(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise InvalidAmountError(f'{name} must be a finite non-negative Decimal')
    return value


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _parse_aware(name: str, value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty ISO-8601 string')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{name} must be an ISO-8601 datetime') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{name} must carry a timezone offset')
    return parsed


def _require_aware(name: str, value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f'{name} must be a timezone-aware datetime')
    return value


class BudgetLevel(Enum):
    NO_LIMIT = 'NO_LIMIT'
    OK = 'OK'
    WARN_80 = 'WARN_80'
    EXCEEDED = 'EXCEEDED'


@dataclass(frozen=True)
class IncrementalCostRecord:
    record_id: str
    provider: str
    service: str
    operation_ref: str
    job_ref: str | None
    batch_ref: str | None
    quantity: Decimal
    unit: str
    estimated_cost: Decimal
    actual_cost: Decimal | None
    currency: str
    source: str
    occurred_at: str
    cost_category: str

    def __post_init__(self) -> None:
        for name in ('record_id', 'provider', 'service', 'operation_ref', 'unit', 'currency', 'source'):
            _require_text(name, getattr(self, name))
        for name in ('job_ref', 'batch_ref'):
            if getattr(self, name) is not None:
                _require_text(name, getattr(self, name))
        _require_amount('quantity', self.quantity)
        _require_amount('estimated_cost', self.estimated_cost)
        if self.actual_cost is not None:
            _require_amount('actual_cost', self.actual_cost)
        _parse_aware('occurred_at', self.occurred_at)
        if not isinstance(self.cost_category, str) or self.cost_category not in ALLOWED_COST_CATEGORIES:
            raise NotIncrementalCostError('cost_category is not an incremental project cost')


@dataclass(frozen=True)
class BudgetPolicy:
    monthly_limit: Decimal | None
    warn_ratio: Decimal = Decimal('0.8')
    hard_stop: bool = False
    currency: str = 'USD'

    def __post_init__(self) -> None:
        if self.monthly_limit is not None:
            _require_amount('monthly_limit', self.monthly_limit)
            if self.monthly_limit == 0:
                raise InvalidAmountError('monthly_limit must be greater than zero')
        _require_amount('warn_ratio', self.warn_ratio)
        if self.warn_ratio == 0 or self.warn_ratio > 1:
            raise InvalidAmountError('warn_ratio must be in (0, 1]')
        if not isinstance(self.hard_stop, bool):
            raise ValueError('hard_stop must be a bool')
        _require_text('currency', self.currency)


@dataclass(frozen=True)
class BudgetStatus:
    spent: Decimal
    forecast: Decimal | None
    level: BudgetLevel
    reason_codes: tuple[str, ...]


def _forecast(spent: Decimal, start: datetime, end: datetime, now: datetime) -> Decimal | None:
    elapsed = min(now, end) - start
    if elapsed <= timedelta(0):
        return None
    return spent * Decimal((end - start) // _MICROSECOND) / Decimal(elapsed // _MICROSECOND)


def _classify(spent: Decimal, forecast: Decimal | None, policy: BudgetPolicy) -> tuple[BudgetLevel, tuple[str, ...]]:
    limit = policy.monthly_limit
    if limit is None:
        return BudgetLevel.NO_LIMIT, ()
    if spent >= limit:
        return BudgetLevel.EXCEEDED, (REASON_LIMIT_REACHED,)
    threshold = limit * policy.warn_ratio
    reasons = []
    if spent >= threshold:
        reasons.append(REASON_SPENT_80)
    if forecast is not None and forecast >= threshold:
        reasons.append(REASON_FORECAST_80)
    if reasons:
        return BudgetLevel.WARN_80, tuple(reasons)
    return BudgetLevel.OK, ()


def evaluate_budget(
    records: Iterable[IncrementalCostRecord], policy: BudgetPolicy, window_start: datetime, window_end: datetime, now: datetime,
) -> BudgetStatus:
    start = _require_aware('window_start', window_start)
    end = _require_aware('window_end', window_end)
    current = _require_aware('now', now)
    if end <= start:
        raise ValueError('window_end must be after window_start')
    spent = Decimal('0')
    for record in records:
        if not isinstance(record, IncrementalCostRecord):
            raise TypeError('records must contain IncrementalCostRecord items')
        occurred = _parse_aware('occurred_at', record.occurred_at)
        if not start <= occurred < end:
            continue
        if record.currency != policy.currency:
            raise CurrencyMismatchError('record currency differs from policy currency')
        spent += record.actual_cost if record.actual_cost is not None else record.estimated_cost
    forecast = _forecast(spent, start, end, current)
    level, reasons = _classify(spent, forecast, policy)
    return BudgetStatus(spent=spent, forecast=forecast, level=level, reason_codes=reasons)


def should_block(status: BudgetStatus, policy: BudgetPolicy, additional_estimated: Decimal) -> bool:
    additional = _require_amount('additional_estimated', additional_estimated)
    if policy.hard_stop is not True or policy.monthly_limit is None:
        return False
    return status.spent + additional > policy.monthly_limit
