"""Pure speed-fit planning for a one-shot voice re-read (no I/O, no clock, no adapters)."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


@dataclass(frozen=True, kw_only=True)
class SpeedFitPolicy:
    """Clamp range of the speed multiplier and measured duration sensitivity to speed."""

    min_scale: float
    max_scale: float
    duration_slope: float

    def __post_init__(self) -> None:
        min_scale = _finite('min_scale', self.min_scale)
        max_scale = _finite('max_scale', self.max_scale)
        duration_slope = _finite('duration_slope', self.duration_slope)
        if not 0 < min_scale <= 1:
            raise ValueError('min_scale must satisfy 0 < min_scale <= 1')
        if max_scale < 1:
            raise ValueError('max_scale must be >= 1')
        if not 0 < duration_slope <= 2:
            raise ValueError('duration_slope must satisfy 0 < duration_slope <= 2')


def plan_speed_fit(actual_duration_ms: float, policy_range: tuple[float, float], policy: SpeedFitPolicy) -> float:
    """Return the speed multiplier that moves actual_duration_ms to the range centre, clamped by policy."""
    if not isinstance(policy, SpeedFitPolicy):
        raise TypeError('policy must be a SpeedFitPolicy')
    low, high = policy_range
    if (
        isinstance(actual_duration_ms, bool)
        or not isinstance(actual_duration_ms, (int, float))
        or not math.isfinite(actual_duration_ms)
        or actual_duration_ms <= 0
    ):
        raise ValueError('actual_duration_ms must be a positive number')
    target = (low + high) / 2
    raw = 1 + (1 - target / actual_duration_ms) / policy.duration_slope
    return round(min(policy.max_scale, max(policy.min_scale, raw)), 3)


__all__ = ('SpeedFitPolicy', 'plan_speed_fit')
