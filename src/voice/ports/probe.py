"""Probe port: reads an immutable artifact and returns simulated ffprobe output; no subprocess in this slice."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from voice.domain.processing import ArtifactRef


@runtime_checkable
class ProbePort(Protocol):
    def probe(self, artifact_ref: ArtifactRef) -> dict[str, object]:
        """Return ffprobe-shaped output for the artifact; an empty dict means the probe could not read it."""
        ...


__all__ = ('ProbePort',)
