"""F-14: OutputInspectorPort and frozen evidence DTOs (CT-QC-001, CT-QC-002).

The port only observes a rendered output and returns evidence; thresholds and verdicts live in render.domain.content_gates.
DTO shapes are F-local (CONV-F-07, CONV-F-14). Real measurement belongs to CP7-F-01 and CP7-F-02; tests use fakes.
No I/O in this module.

coveredIds: CT-QC-001, CT-QC-002
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from render.domain.package_contract import RenderPackageRecord


@dataclass(frozen=True, kw_only=True)
class VisualHookEvidence:
    evidence_ref: str
    start_ms: int
    end_ms: int
    similarity: float


@dataclass(frozen=True, kw_only=True)
class AudioHookEvidence:
    evidence_ref: str
    start_ms: int
    end_ms: int
    level_db: float


@dataclass(frozen=True, kw_only=True)
class ThumbnailEvidence:
    evidence_ref: str
    time_ms: int
    asset_ref: str


@dataclass(frozen=True, kw_only=True)
class SubtitleEvidence:
    evidence_ref: str
    frames_with_text: int


@dataclass(frozen=True, kw_only=True)
class KaraokeWordObservation:
    word_index: int
    highlight_ms: int


@dataclass(frozen=True, kw_only=True)
class KaraokeEvidence:
    evidence_ref: str
    observations: tuple[KaraokeWordObservation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'observations', tuple(self.observations))


@dataclass(frozen=True, kw_only=True)
class LanguageEvidence:
    evidence_ref: str
    script_fingerprint: str | None = None
    voice_hash: str | None = None
    subtitle_text_hash: str | None = None
    output_metadata_revision: str | None = None
    script_locale: str | None = None
    voice_locale: str | None = None
    subtitle_locale: str | None = None
    title_locale: str | None = None
    hashtag_locale: str | None = None
    declared_language: str | None = None


@dataclass(frozen=True, kw_only=True)
class DisclosureObservation:
    segment_id: str
    visible: bool


@dataclass(frozen=True, kw_only=True)
class DisclosureEvidence:
    evidence_ref: str
    observations: tuple[DisclosureObservation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'observations', tuple(self.observations))


@dataclass(frozen=True, kw_only=True)
class OutputEvidence:
    visual_hook: VisualHookEvidence | None = None
    audio_hook: AudioHookEvidence | None = None
    thumbnail: ThumbnailEvidence | None = None
    subtitle: SubtitleEvidence | None = None
    karaoke: KaraokeEvidence | None = None
    language: LanguageEvidence | None = None
    disclosure: DisclosureEvidence | None = None


class OutputInspectorPort(Protocol):
    def inspect(self, output_ref: str, package: RenderPackageRecord) -> OutputEvidence:
        """Observe the rendered output and return frozen evidence; a field is None when the inspector observed nothing for it."""
        ...
