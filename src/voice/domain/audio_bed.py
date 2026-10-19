"""E-13: PrepareAudioBed value validators (CT-AUD-001). Pure domain: no I/O, no clock, no random; loudness numbers only come from caller constraints."""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

INPUT_NOT_READY = 'INPUT_NOT_READY'
LOUDNESS_OUT_OF_TARGET = 'loudness_out_of_target'
SUBSTITUTION_NOT_ALLOWED = 'substitution_not_allowed'
MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
CONSTRAINT_VIOLATION = 'constraint_violation'

CUE_KINDS = ('music', 'sfx')
SUBSTITUTION_CHANGES = ('track', 'mood')


class AudioBedError(ValueError):
    """Domain error with machine-readable code and field."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f'{code}:{field}')
        self.code = code
        self.field = field


class AudioBedRejected(Exception):
    """Domain rejection indicating missing or unready input."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_str(v: object, field: str, optional: bool = False) -> str | None:
    if v is None:
        if optional:
            return None
        raise AudioBedError(MISSING_REQUIRED, field)
    if not isinstance(v, str):
        raise AudioBedError(WRONG_TYPE, field)
    if not v.strip():
        raise AudioBedError(CONSTRAINT_VIOLATION, field)
    return v


def _check_int(v: object, field: str) -> int:
    if v is None:
        raise AudioBedError(MISSING_REQUIRED, field)
    if not _is_int(v):
        raise AudioBedError(WRONG_TYPE, field)
    return v


def _check_number(v: object, field: str, allow_none: bool = False) -> int | float | None:
    if v is None:
        if allow_none:
            return None
        raise AudioBedError(MISSING_REQUIRED, field)
    if not _is_number(v):
        raise AudioBedError(WRONG_TYPE, field)
    if not math.isfinite(v):
        raise AudioBedError(CONSTRAINT_VIOLATION, field)
    return v


def _check_mapping(v: object, field: str) -> MappingProxyType | None:
    if v is None:
        return None
    if not isinstance(v, Mapping):
        raise AudioBedError(WRONG_TYPE, field)
    return MappingProxyType(copy.deepcopy(dict(v)))


def _check_ref_tuple(v: object, field: str) -> tuple:
    if v is None:
        raise AudioBedError(MISSING_REQUIRED, field)
    if isinstance(v, (str, bytes, Mapping)) or not isinstance(v, (list, tuple)):
        raise AudioBedError(WRONG_TYPE, field)
    return tuple(v)


@dataclass(frozen=True, kw_only=True)
class AudioCue:
    kind: str
    start_ms: int
    end_ms: int
    artifact_ref: str
    mood: str | None = None

    def __post_init__(self) -> None:
        if self.kind is None:
            raise AudioBedError(MISSING_REQUIRED, 'kind')
        if not isinstance(self.kind, str):
            raise AudioBedError(WRONG_TYPE, 'kind')
        if self.kind not in CUE_KINDS:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'kind')

        _check_int(self.start_ms, 'start_ms')
        _check_int(self.end_ms, 'end_ms')
        _check_str(self.artifact_ref, 'artifact_ref')
        _check_str(self.mood, 'mood', optional=True)

        if self.start_ms < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'start_ms')
        if self.end_ms < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'end_ms')
        if self.start_ms >= self.end_ms:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'end_ms')


@dataclass(frozen=True, kw_only=True)
class LoudnessConstraints:
    min_lufs: int | float | None
    max_lufs: int | float | None
    max_true_peak_dbtp: int | float | None

    def __post_init__(self) -> None:
        _check_number(self.min_lufs, 'min_lufs', allow_none=True)
        _check_number(self.max_lufs, 'max_lufs', allow_none=True)
        _check_number(self.max_true_peak_dbtp, 'max_true_peak_dbtp', allow_none=True)
        if self.min_lufs is not None and self.max_lufs is not None and self.min_lufs > self.max_lufs:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'min_lufs')


@dataclass(frozen=True, kw_only=True)
class LoudnessReport:
    integrated_lufs: int | float
    true_peak_dbtp: int | float

    def __post_init__(self) -> None:
        _check_number(self.integrated_lufs, 'integrated_lufs', allow_none=False)
        _check_number(self.true_peak_dbtp, 'true_peak_dbtp', allow_none=False)


@dataclass(frozen=True, kw_only=True)
class PreparedRendition:
    cue_index: int
    rendition_ref: str
    source_artifact_ref: str
    mood: str | None = None

    def __post_init__(self) -> None:
        _check_int(self.cue_index, 'cue_index')
        if self.cue_index < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'cue_index')
        _check_str(self.rendition_ref, 'rendition_ref')
        _check_str(self.source_artifact_ref, 'source_artifact_ref')
        _check_str(self.mood, 'mood', optional=True)


@dataclass(frozen=True, kw_only=True)
class AudioBedRequest:
    cues: tuple
    voice_artifact_ref: str
    preset_audio_policy_revision: str
    loudness_constraints: LoudnessConstraints | None
    mix_constraints: Mapping | None
    fallback_allowed: bool
    fallback_artifact_refs: tuple = ()

    def __post_init__(self) -> None:
        if self.cues is None:
            raise AudioBedError(MISSING_REQUIRED, 'cues')
        if isinstance(self.cues, (str, bytes, Mapping)) or not isinstance(self.cues, (list, tuple)):
            raise AudioBedError(WRONG_TYPE, 'cues')
        if not self.cues:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'cues')
        for item in self.cues:
            if not isinstance(item, AudioCue):
                raise AudioBedError(WRONG_TYPE, 'cues')
        object.__setattr__(self, 'cues', tuple(self.cues))

        _check_str(self.voice_artifact_ref, 'voice_artifact_ref')
        _check_str(self.preset_audio_policy_revision, 'preset_audio_policy_revision')

        if self.loudness_constraints is not None and not isinstance(self.loudness_constraints, LoudnessConstraints):
            raise AudioBedError(WRONG_TYPE, 'loudness_constraints')

        mix = _check_mapping(self.mix_constraints, 'mix_constraints')
        object.__setattr__(self, 'mix_constraints', mix)

        if self.fallback_allowed is None:
            raise AudioBedError(MISSING_REQUIRED, 'fallback_allowed')
        if type(self.fallback_allowed) is not bool:
            raise AudioBedError(WRONG_TYPE, 'fallback_allowed')

        raw_refs = _check_ref_tuple(self.fallback_artifact_refs, 'fallback_artifact_refs')
        for item in raw_refs:
            _check_str(item, 'fallback_artifact_refs')
        object.__setattr__(self, 'fallback_artifact_refs', raw_refs)


@dataclass(frozen=True, kw_only=True)
class AudioBedResult:
    renditions: tuple
    cue_timings: tuple
    loudness_report: LoudnessReport
    provenance: Mapping
    risk_metadata: Mapping
    warnings: tuple
    substitutions: tuple

    def __post_init__(self) -> None:
        for field_name in ('renditions', 'cue_timings', 'substitutions', 'warnings'):
            v = getattr(self, field_name)
            if v is None:
                raise AudioBedError(MISSING_REQUIRED, field_name)
            if isinstance(v, (str, bytes, Mapping)) or not isinstance(v, (list, tuple)):
                raise AudioBedError(WRONG_TYPE, field_name)

        for item in self.renditions:
            if not isinstance(item, PreparedRendition):
                raise AudioBedError(WRONG_TYPE, 'renditions')
        object.__setattr__(self, 'renditions', tuple(self.renditions))

        for item in self.cue_timings:
            if not isinstance(item, CueTiming):
                raise AudioBedError(WRONG_TYPE, 'cue_timings')
        object.__setattr__(self, 'cue_timings', tuple(self.cue_timings))

        for item in self.substitutions:
            if not isinstance(item, Substitution):
                raise AudioBedError(WRONG_TYPE, 'substitutions')
        object.__setattr__(self, 'substitutions', tuple(self.substitutions))

        for item in self.warnings:
            if not isinstance(item, str):
                raise AudioBedError(WRONG_TYPE, 'warnings')
        object.__setattr__(self, 'warnings', tuple(self.warnings))

        if self.loudness_report is None:
            raise AudioBedError(MISSING_REQUIRED, 'loudness_report')
        if not isinstance(self.loudness_report, LoudnessReport):
            raise AudioBedError(WRONG_TYPE, 'loudness_report')

        if self.provenance is None:
            raise AudioBedError(MISSING_REQUIRED, 'provenance')
        if not isinstance(self.provenance, Mapping):
            raise AudioBedError(WRONG_TYPE, 'provenance')
        object.__setattr__(self, 'provenance', MappingProxyType(copy.deepcopy(dict(self.provenance))))

        if self.risk_metadata is None:
            raise AudioBedError(MISSING_REQUIRED, 'risk_metadata')
        if not isinstance(self.risk_metadata, Mapping):
            raise AudioBedError(WRONG_TYPE, 'risk_metadata')
        object.__setattr__(self, 'risk_metadata', MappingProxyType(copy.deepcopy(dict(self.risk_metadata))))


@dataclass(frozen=True)
class LoudnessFinding:
    code: str
    field: str
    measured: int | float


@dataclass(frozen=True)
class CueTiming:
    cue_index: int
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        _check_int(self.cue_index, 'cue_index')
        _check_int(self.start_ms, 'start_ms')
        _check_int(self.end_ms, 'end_ms')
        if self.cue_index < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'cue_index')
        if self.start_ms < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'start_ms')
        if self.end_ms < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'end_ms')
        if self.start_ms >= self.end_ms:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'end_ms')


@dataclass(frozen=True)
class Substitution:
    cue_index: int
    change: str
    original: str | None
    replacement: str | None

    def __post_init__(self) -> None:
        _check_int(self.cue_index, 'cue_index')
        if self.cue_index < 0:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'cue_index')
        if not isinstance(self.change, str):
            raise AudioBedError(WRONG_TYPE, 'change')
        if self.change not in SUBSTITUTION_CHANGES:
            raise AudioBedError(CONSTRAINT_VIOLATION, 'change')
        if self.original is not None and not isinstance(self.original, str):
            raise AudioBedError(WRONG_TYPE, 'original')
        if self.replacement is not None and not isinstance(self.replacement, str):
            raise AudioBedError(WRONG_TYPE, 'replacement')


def validate_loudness_report(
    report: LoudnessReport, constraints: LoudnessConstraints | None
) -> tuple[LoudnessFinding, ...]:
    """Validate loudness report measurements against given constraints."""
    if constraints is None:
        raise AudioBedRejected(INPUT_NOT_READY, 'missing_loudness_constraints')
    if not isinstance(constraints, LoudnessConstraints):
        raise AudioBedError(WRONG_TYPE, 'constraints')
    if (
        constraints.min_lufs is None
        or constraints.max_lufs is None
        or constraints.max_true_peak_dbtp is None
    ):
        raise AudioBedRejected(INPUT_NOT_READY, 'missing_loudness_constraints')
    if not isinstance(report, LoudnessReport):
        raise AudioBedError(WRONG_TYPE, 'report')

    findings: list[LoudnessFinding] = []
    if report.integrated_lufs < constraints.min_lufs or report.integrated_lufs > constraints.max_lufs:
        findings.append(LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'integrated_lufs', report.integrated_lufs))
    if report.true_peak_dbtp > constraints.max_true_peak_dbtp:
        findings.append(LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'true_peak_dbtp', report.true_peak_dbtp))

    return tuple(findings)


def detect_substitutions(
    request: AudioBedRequest, renditions: Iterable[PreparedRendition]
) -> tuple[Substitution, ...]:
    """Detect rendition substitutions against original request cues."""
    if not isinstance(request, AudioBedRequest):
        raise AudioBedError(WRONG_TYPE, 'request')
    if isinstance(renditions, (str, bytes, Mapping)) or not isinstance(renditions, (list, tuple)):
        raise AudioBedError(WRONG_TYPE, 'renditions')
    for item in renditions:
        if not isinstance(item, PreparedRendition):
            raise AudioBedError(WRONG_TYPE, 'renditions')

    indices = [r.cue_index for r in renditions]
    expected_indices = list(range(len(request.cues)))
    if sorted(indices) != expected_indices or len(set(indices)) != len(indices):
        raise AudioBedError(CONSTRAINT_VIOLATION, 'renditions')

    rendition_map = {r.cue_index: r for r in renditions}
    substitutions: list[Substitution] = []
    allowed_track_refs = {cue.artifact_ref for cue in request.cues} | set(request.fallback_artifact_refs)

    for i, cue in enumerate(request.cues):
        rendition = rendition_map[i]
        if rendition.source_artifact_ref != cue.artifact_ref:
            substitutions.append(
                Substitution(i, 'track', cue.artifact_ref, rendition.source_artifact_ref)
            )
        if rendition.mood != cue.mood:
            substitutions.append(
                Substitution(i, 'mood', cue.mood, rendition.mood)
            )

    if substitutions and not request.fallback_allowed:
        raise AudioBedError(SUBSTITUTION_NOT_ALLOWED, 'renditions')

    if request.fallback_allowed:
        for sub in substitutions:
            if sub.change == 'track' and sub.replacement not in allowed_track_refs:
                raise AudioBedError(SUBSTITUTION_NOT_ALLOWED, 'renditions')

    return tuple(substitutions)


def build_audio_bed_result(
    request: AudioBedRequest,
    *,
    renditions: Iterable[PreparedRendition],
    loudness_report: LoudnessReport,
    provenance: Mapping,
    risk_metadata: Mapping,
    warnings: tuple = (),
) -> AudioBedResult:
    """Build verified immutable AudioBedResult."""
    if not isinstance(request, AudioBedRequest):
        raise AudioBedError(WRONG_TYPE, 'request')

    findings = validate_loudness_report(loudness_report, request.loudness_constraints)
    if findings:
        raise AudioBedError(LOUDNESS_OUT_OF_TARGET, findings[0].field)

    substitutions = detect_substitutions(request, renditions)
    cue_timings = tuple(
        CueTiming(i, cue.start_ms, cue.end_ms)
        for i, cue in enumerate(request.cues)
    )

    return AudioBedResult(
        renditions=tuple(renditions),
        cue_timings=cue_timings,
        loudness_report=loudness_report,
        provenance=provenance,
        risk_metadata=risk_metadata,
        warnings=tuple(warnings),
        substitutions=substitutions,
    )
