"""Per-batch concurrent video limits chosen through POST /v1/batches."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

FIELD = "max_concurrent_videos"


def _is_pos_int(value: object) -> bool:
    return type(value) is int and value > 0


@dataclass(frozen=True)
class BatchConcurrency:
    default: int
    maximum: int

    def __post_init__(self) -> None:
        if not _is_pos_int(self.default) or not _is_pos_int(self.maximum) or self.default > self.maximum:
            raise ValueError("invalid batch concurrency limits")


SEQUENTIAL = BatchConcurrency(1, 1)


class BatchFieldError(ValueError):
    def __init__(self, field_errors: Mapping[str, str]) -> None:
        super().__init__("invalid batch field")
        self.field_errors = dict(field_errors)


def resolve(payload: Mapping[str, object], limits: BatchConcurrency) -> int:
    if FIELD not in payload:
        return limits.default
    value = payload[FIELD]
    if not _is_pos_int(value) or value > limits.maximum:
        raise BatchFieldError({FIELD: f"Số nguyên từ 1 tới {limits.maximum}."})
    return value


__all__ = ["BatchConcurrency", "BatchFieldError", "SEQUENTIAL", "resolve"]
