"""F-18: RendererPort, RendererOutcome and OutputObservationPort (CT-RND-004, CT-STATE-011); pure, no I/O, no clock, no process execution.

run(spec) executes one structured RenderCommandSpec and returns a RendererOutcome (status, output ref, sha256, metrics, error text).
RendererTimeout means the side effect may have happened (handler: OUTCOME_UNKNOWN); any other exception is a crash (handler: FAILED).
OutputObservationPort reports whether an output exists and its sha256; decodability comes from OutputProbePort of F-13. The FFmpeg adapter waits for CONV-F-02.

coveredIds: CT-RND-004, CT-STATE-011
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from render.domain.render_command import RenderCommandSpec


class RendererTimeout(Exception):
    """The renderer did not answer in time; the output may or may not exist."""


class RendererStatus(StrEnum):
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'


def _no_metrics() -> Mapping[str, int | float]:
    return MappingProxyType({})


@dataclasses.dataclass(frozen=True, kw_only=True)
class RendererMetrics:
    wall_time_ms: int | None = None
    cpu_metrics: Mapping[str, int | float] = dataclasses.field(default_factory=_no_metrics)
    gpu_metrics: Mapping[str, int | float] = dataclasses.field(default_factory=_no_metrics)
    peak_disk_bytes: int | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class RendererOutcome:
    """output_ref and sha256 are claims of the renderer; the handler verifies them. error is raw text and is redacted before it is stored."""

    status: RendererStatus
    output_ref: str | None = None
    sha256: str | None = None
    metrics: RendererMetrics = dataclasses.field(default_factory=RendererMetrics)
    error: str | None = dataclasses.field(default=None, repr=False)


@dataclasses.dataclass(frozen=True, kw_only=True)
class OutputObservation:
    exists: bool
    sha256: str | None = None


@runtime_checkable
class RendererPort(Protocol):
    def run(self, spec: RenderCommandSpec) -> RendererOutcome:
        ...


@runtime_checkable
class OutputObservationPort(Protocol):
    def observe(self, output_ref: str) -> OutputObservation:
        ...


__all__ = [
    'OutputObservation',
    'OutputObservationPort',
    'RendererMetrics',
    'RendererOutcome',
    'RendererPort',
    'RendererStatus',
    'RendererTimeout',
]
