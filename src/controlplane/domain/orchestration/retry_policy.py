"""G-11: chính sách retry/backoff (CT-WF-007; D8-G-07).

Pure domain: không I/O, không đồng hồ, không jitter. Mọi tham số bắt buộc, không có giá trị mặc định cứng; nguồn là cấu hình J.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math


class TimeoutKind(StrEnum):
    SCHEDULE_TO_START = 'schedule_to_start'
    START_TO_CLOSE = 'start_to_close'
    HEARTBEAT = 'heartbeat'


def _require_int(name: str, value: object, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f'{name} must be int')
    if value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    return value


def _require_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{name} must be a number')
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return float(value)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    initial_delay_seconds: float
    multiplier: float
    max_delay_seconds: float

    def __post_init__(self) -> None:
        _require_int('max_attempts', self.max_attempts, 1)
        initial = _require_number('initial_delay_seconds', self.initial_delay_seconds)
        multiplier = _require_number('multiplier', self.multiplier)
        cap = _require_number('max_delay_seconds', self.max_delay_seconds)
        if initial <= 0:
            raise ValueError('initial_delay_seconds must be > 0')
        if multiplier < 1:
            raise ValueError('multiplier must be >= 1')
        if cap < initial:
            raise ValueError('max_delay_seconds must be >= initial_delay_seconds')


def next_delay(attempt: int, policy: RetryPolicy) -> float:
    if not isinstance(policy, RetryPolicy):
        raise TypeError('policy must be RetryPolicy')
    _require_int('attempt', attempt, 1)
    cap = float(policy.max_delay_seconds)
    try:
        raw = float(policy.initial_delay_seconds) * float(policy.multiplier) ** (attempt - 1)
    except OverflowError:
        return cap
    return min(raw, cap)


def should_retry(attempt: int, problem_retryable: bool, policy: RetryPolicy) -> bool:
    if not isinstance(policy, RetryPolicy):
        raise TypeError('policy must be RetryPolicy')
    _require_int('attempt', attempt, 1)
    if not isinstance(problem_retryable, bool):
        raise TypeError('problem_retryable must be bool')
    return problem_retryable and attempt < policy.max_attempts


def consumes_attempt(timeout_kind: TimeoutKind | str) -> bool:
    try:
        kind = TimeoutKind(timeout_kind)
    except ValueError as exc:
        raise ValueError(f'unknown timeout kind: {timeout_kind!r}') from exc
    return kind is not TimeoutKind.SCHEDULE_TO_START


def attempts_after_timeout(consumed_attempts: int, timeout_kind: TimeoutKind | str) -> int:
    _require_int('consumed_attempts', consumed_attempts, 0)
    return consumed_attempts + 1 if consumes_attempt(timeout_kind) else consumed_attempts


__all__ = ['RetryPolicy', 'TimeoutKind', 'attempts_after_timeout', 'consumes_attempt', 'next_delay', 'should_retry']
