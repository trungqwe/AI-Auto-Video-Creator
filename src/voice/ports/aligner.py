"""AlignerPort: E-local port that aligns one exact voice with its script text word by word (CT-SUB-001).

Pure declarations: no I/O, no clock. The aligner tool is not chosen (TECH-POC-005, CP7-E-02); only this port and a fake exist.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class AlignerError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f'{code}: {message}')


@dataclass(frozen=True, kw_only=True)
class AlignmentRequest:
    voice_artifact_ref: str
    voice_hash: str
    voice_duration_ms: int
    script_version_id: str
    script_text: str
    expected_language: str


@dataclass(frozen=True, kw_only=True)
class AlignmentResult:
    words: tuple[Mapping[str, object], ...]
    segment_boundaries: tuple[Mapping[str, object], ...]
    voice_locale_reported: str | None
    aligner_revision: str


@runtime_checkable
class AlignerPort(Protocol):
    def align(self, request: AlignmentRequest) -> AlignmentResult:
        """Return word timings (start_ms, end_ms, text, normalized_text, confidence), segment boundaries and the locale the aligner reported; errors are AlignerError."""
        ...


__all__ = ('AlignerError', 'AlignerPort', 'AlignmentRequest', 'AlignmentResult')
