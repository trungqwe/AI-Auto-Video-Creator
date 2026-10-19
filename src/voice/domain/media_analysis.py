"""Versioned media analysis result and append-only history (CT-PROC-004)."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import enum
import math

from voice.domain.processing import (
    CONSTRAINT_VIOLATION,
    ENUM_VIOLATION,
    MISSING_REQUIRED,
    WRONG_TYPE,
    ArtifactRef,
    ProcessingContractError,
)

ANALYSIS_FIELDS = (
    'analysis_id',
    'input_ref',
    'analysis_kind',
    'model',
    'model_version',
    'spec_revision',
    'confidence',
    'coverage',
    'failure_flags',
)


class AnalysisKind(enum.StrEnum):
    KEYFRAMES_SHOTS = 'keyframes_shots'
    TRANSCRIPT_OCR = 'transcript_ocr'
    ENTITIES_FACES_OBJECTS = 'entities_faces_objects'
    MOTION_SCENE_AUDIO_ENERGY = 'motion_scene_audio_energy'
    SEMANTIC_TAGS = 'semantic_tags'


def _check_text(value: object, field: str) -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    if not value.strip():
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return value


def _check_unit_interval(value: object, field: str) -> float:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProcessingContractError(WRONG_TYPE, field)
    try:
        number = float(value)
    except OverflowError:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field) from None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return number


def _as_kind(value: object) -> AnalysisKind:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'analysis_kind')
    if isinstance(value, AnalysisKind):
        return value
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, 'analysis_kind')
    try:
        return AnalysisKind(value)
    except ValueError:
        raise ProcessingContractError(ENUM_VIOLATION, 'analysis_kind') from None


def _as_input_ref(value: object) -> ArtifactRef:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'input_ref')
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, Mapping):
        for key in ('ref', 'content_sha256'):
            if key not in value:
                raise ProcessingContractError(MISSING_REQUIRED, key)
        return ArtifactRef(value['ref'], value['content_sha256'])
    raise ProcessingContractError(WRONG_TYPE, 'input_ref')


def _as_failure_flags(value: object) -> tuple[str, ...]:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'failure_flags')
    if isinstance(value, (str, bytes, Mapping)):
        raise ProcessingContractError(WRONG_TYPE, 'failure_flags')
    try:
        items = tuple(value)
    except TypeError:
        raise ProcessingContractError(WRONG_TYPE, 'failure_flags') from None
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ProcessingContractError(WRONG_TYPE, 'failure_flags')
    return items


def _series_key(result: AnalysisResult) -> tuple:
    return (result.input_ref.ref, result.input_ref.content_sha256, result.analysis_kind)


def _version_key(result: AnalysisResult) -> tuple:
    return _series_key(result) + (result.model, result.model_version, result.spec_revision)


@dataclasses.dataclass(frozen=True)
class AnalysisResult:
    analysis_id: object
    input_ref: object
    analysis_kind: object
    model: object
    model_version: object
    spec_revision: object
    confidence: object
    coverage: object
    failure_flags: object

    def __post_init__(self) -> None:
        for name in ANALYSIS_FIELDS:
            if getattr(self, name) is None:
                raise ProcessingContractError(MISSING_REQUIRED, name)
        _check_text(self.analysis_id, 'analysis_id')
        object.__setattr__(self, 'input_ref', _as_input_ref(self.input_ref))
        object.__setattr__(self, 'analysis_kind', _as_kind(self.analysis_kind))
        _check_text(self.model, 'model')
        _check_text(self.model_version, 'model_version')
        _check_text(self.spec_revision, 'spec_revision')
        object.__setattr__(self, 'confidence', _check_unit_interval(self.confidence, 'confidence'))
        object.__setattr__(self, 'coverage', _check_unit_interval(self.coverage, 'coverage'))
        object.__setattr__(self, 'failure_flags', _as_failure_flags(self.failure_flags))

    @classmethod
    def from_mapping(cls, payload: Mapping) -> AnalysisResult:
        if not isinstance(payload, Mapping):
            raise ProcessingContractError(WRONG_TYPE, 'payload')
        for n in ANALYSIS_FIELDS:
            if n not in payload:
                raise ProcessingContractError(MISSING_REQUIRED, n)
        return cls(**{n: payload[n] for n in ANALYSIS_FIELDS})


@dataclasses.dataclass(frozen=True)
class AnalysisRevision:
    revision: int
    result: AnalysisResult

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ProcessingContractError(WRONG_TYPE, 'revision')
        if self.revision < 1:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'revision')
        if not isinstance(self.result, AnalysisResult):
            raise ProcessingContractError(WRONG_TYPE, 'result')


@dataclasses.dataclass(frozen=True)
class AnalysisHistory:
    entries: tuple[AnalysisRevision, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.entries, (str, bytes, Mapping)):
            raise ProcessingContractError(WRONG_TYPE, 'entries')
        try:
            items = tuple(self.entries)
        except TypeError:
            raise ProcessingContractError(WRONG_TYPE, 'entries') from None
        seen_ids: set[str] = set()
        seen_versions: set[tuple] = set()
        counts: dict[tuple, int] = {}
        for entry in items:
            if not isinstance(entry, AnalysisRevision):
                raise ProcessingContractError(WRONG_TYPE, 'entries')
            result = entry.result
            if result.analysis_id in seen_ids:
                raise ProcessingContractError(CONSTRAINT_VIOLATION, 'analysis_id')
            if _version_key(result) in seen_versions:
                raise ProcessingContractError(CONSTRAINT_VIOLATION, 'entries')
            series = _series_key(result)
            counts[series] = counts.get(series, 0) + 1
            if entry.revision != counts[series]:
                raise ProcessingContractError(CONSTRAINT_VIOLATION, 'revision')
            seen_ids.add(result.analysis_id)
            seen_versions.add(_version_key(result))
        object.__setattr__(self, 'entries', items)

    def append(self, result: object) -> AnalysisHistory:
        if not isinstance(result, AnalysisResult):
            raise ProcessingContractError(WRONG_TYPE, 'result')
        version = _version_key(result)
        if any(_version_key(e.result) == version for e in self.entries):
            return self
        if any(e.result.analysis_id == result.analysis_id for e in self.entries):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'analysis_id')
        revision = len(self.revisions(result.input_ref, result.analysis_kind)) + 1
        return AnalysisHistory(self.entries + (AnalysisRevision(revision, result),))

    def revisions(self, input_ref: object, analysis_kind: object) -> tuple[AnalysisRevision, ...]:
        ref = _as_input_ref(input_ref)
        series = (ref.ref, ref.content_sha256, _as_kind(analysis_kind))
        return tuple(e for e in self.entries if _series_key(e.result) == series)

    def get(self, analysis_id: object) -> AnalysisRevision | None:
        for entry in self.entries:
            if entry.result.analysis_id == analysis_id:
                return entry
        return None


__all__ = (
    'ANALYSIS_FIELDS',
    'AnalysisKind',
    'AnalysisResult',
    'AnalysisRevision',
    'AnalysisHistory',
)
