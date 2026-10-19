"""F-18: FakeRenderer and FakeOutputStorage; test and fixture use only, no I/O (CT-RND-004).

FakeOutputStorage never deletes, truncates or overwrites: a second write to a stored ref raises OutputAlreadyExists and every operation is logged in `operations`.
FakeRenderer injects a fault before, during or after the side effect (the write of the output); fail_text, write_partial and claimed_sha256 shape the other outcomes.
The FFmpeg adapter waits for CONV-F-02.

coveredIds: CT-RND-004, CT-STATE-011
"""
from __future__ import annotations

import dataclasses
import hashlib

from render.domain.render_command import RenderCommandSpec
from render.ports.output_probe import OutputMeasurements
from render.ports.renderer import OutputObservation, RendererMetrics, RendererOutcome, RendererStatus

BEFORE_SIDE_EFFECT = 'before'
DURING_SIDE_EFFECT = 'during'
AFTER_SIDE_EFFECT = 'after'
FAULT_POINTS = (BEFORE_SIDE_EFFECT, DURING_SIDE_EFFECT, AFTER_SIDE_EFFECT)
DEFAULT_CONTENT = b'fake-video-bytes'


class OutputAlreadyExists(Exception):
    """A write targeted an output ref that is already stored; the stored output is unchanged."""


@dataclasses.dataclass(frozen=True)
class FakeFile:
    data: bytes
    complete: bool


class FakeOutputStorage:
    """In-memory outputs by ref; implements OutputObservationPort and OutputProbePort over the same files. Public methods are only write, observe and probe."""

    def __init__(self) -> None:
        self.files: dict[str, FakeFile] = {}
        self.operations: list[tuple[str, str]] = []

    def write(self, output_ref: str, data: bytes, *, complete: bool) -> None:
        if output_ref in self.files:
            self.operations.append(('write_refused', output_ref))
            raise OutputAlreadyExists(output_ref)
        self.files[output_ref] = FakeFile(data=data, complete=complete)
        self.operations.append(('write', output_ref))

    def observe(self, output_ref: str) -> OutputObservation:
        stored = self.files.get(output_ref)
        if stored is None:
            return OutputObservation(exists=False)
        return OutputObservation(exists=True, sha256=hashlib.sha256(stored.data).hexdigest())

    def probe(self, output_ref: str) -> OutputMeasurements:
        stored = self.files.get(output_ref)
        return OutputMeasurements() if stored is None else OutputMeasurements(decodable=stored.complete)


class FakeRenderer:
    """RendererPort fake: writes its output into the storage; `fault` is (point, exception) set by inject()."""

    def __init__(self, storage: FakeOutputStorage, *, output_ref: str, content: bytes = DEFAULT_CONTENT) -> None:
        self.storage = storage
        self.output_ref = output_ref
        self.content = content
        self.calls = 0
        self.fault: tuple[str, Exception] | None = None
        self.fail_text: str | None = None
        self.write_partial = False
        self.claimed_sha256: str | None = None
        self.metrics = RendererMetrics(
            wall_time_ms=1200, cpu_metrics={'cpu_percent': 50.0}, gpu_metrics={'gpu_percent': 80.0}, peak_disk_bytes=4096,
        )

    def inject(self, point: str, error: Exception) -> None:
        if point not in FAULT_POINTS:
            raise ValueError(f'unknown fault point: {point}')
        self.fault = (point, error)

    def _fire(self, point: str) -> None:
        if self.fault is not None and self.fault[0] == point:
            raise self.fault[1]

    def run(self, spec: RenderCommandSpec) -> RendererOutcome:
        if not isinstance(spec, RenderCommandSpec):
            raise TypeError('spec must be a RenderCommandSpec')
        self.calls += 1
        self._fire(BEFORE_SIDE_EFFECT)
        if self.fail_text is not None:
            return RendererOutcome(status=RendererStatus.FAILED, error=self.fail_text)
        half = self.content[: len(self.content) // 2]
        if self.fault is not None and self.fault[0] == DURING_SIDE_EFFECT:
            self.storage.write(self.output_ref, half, complete=False)
            raise self.fault[1]
        written = half if self.write_partial else self.content
        self.storage.write(self.output_ref, written, complete=not self.write_partial)
        self._fire(AFTER_SIDE_EFFECT)
        sha256 = self.claimed_sha256 or hashlib.sha256(written).hexdigest()
        return RendererOutcome(status=RendererStatus.SUCCEEDED, output_ref=self.output_ref, sha256=sha256, metrics=self.metrics)


__all__ = [
    'AFTER_SIDE_EFFECT',
    'BEFORE_SIDE_EFFECT',
    'DEFAULT_CONTENT',
    'DURING_SIDE_EFFECT',
    'FAULT_POINTS',
    'FakeFile',
    'FakeOutputStorage',
    'FakeRenderer',
    'OutputAlreadyExists',
]
