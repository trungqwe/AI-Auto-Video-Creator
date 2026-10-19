"""OutputProbePort and OutputMeasurements (CT-QC-001): what a probe reports about a rendered output file.

Every measurement defaults to None (not measured); gates treat a missing measurement as a failure, never as a pass.
duration_ms is milliseconds; audio_level is in the unit of the policy min_voice_level (GIẢ ĐỊNH, caller defined).
severe_audio_errors is None (unknown) or a tuple of error codes. Adapters implement probe; this module does no I/O.

coveredIds: CT-QC-001
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, kw_only=True)
class OutputMeasurements:
    """Frozen probe result; unmeasured fields stay None; a list of audio errors is stored as a tuple."""

    decodable: bool | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    container: str | None = None
    has_audio_stream: bool | None = None
    audio_level: float | None = None
    severe_audio_errors: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.severe_audio_errors, list):
            object.__setattr__(self, 'severe_audio_errors', tuple(self.severe_audio_errors))


@runtime_checkable
class OutputProbePort(Protocol):
    """Probe a rendered output by reference; implementations read metadata only and never modify the output."""

    def probe(self, output_ref: str) -> OutputMeasurements:
        ...
