"""F-13: technical output gates FILE_PLAYABLE, DURATION_RANGE, VOICE_AUDIBLE, OUTPUT_PROFILE_VALID (CT-QC-001).

Gates read OutputMeasurements from OutputProbePort and compare them with caller input: a policy mapping holding
`duration_range_ms` (two integers, both ends inclusive) and `min_voice_level`, plus an `expected_profile` mapping; this module
holds none of these values. A missing or malformed threshold gives not_evaluated with INPUT_NOT_READY (checked first); a missing or
malformed measurement gives failed. GateName, GateStatus and GateResult are declared here with the same values and field order as
render.domain.quality_report (F-12) and are not imported from it.
Pure domain: no I/O, no clock.

coveredIds: CT-QC-001
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum

from render.ports.output_probe import OutputMeasurements, OutputProbePort

INPUT_NOT_READY = 'INPUT_NOT_READY'
REASON_MISSING_MEASUREMENT = 'missing_measurement'
REASON_INVALID_MEASUREMENT = 'invalid_measurement'
REASON_NOT_DECODABLE = 'not_decodable'
REASON_OUT_OF_RANGE = 'out_of_range'
REASON_PROFILE_MISMATCH = 'profile_mismatch'
REASON_NO_AUDIO_STREAM = 'no_audio_stream'
REASON_SEVERE_AUDIO_ERROR = 'severe_audio_error'
REASON_VOICE_TOO_QUIET = 'voice_below_min_level'
POLICY_DURATION_KEY = 'duration_range_ms'
POLICY_VOICE_KEY = 'min_voice_level'
PROFILE_TEXT_KEYS = ('container', 'video_codec', 'audio_codec')
PROFILE_SIZE_KEYS = ('width', 'height')
PROFILE_FPS_KEY = 'fps'
PROFILE_ORDER = (*PROFILE_TEXT_KEYS, *PROFILE_SIZE_KEYS, PROFILE_FPS_KEY)
PLAYABLE_FIELDS = ('duration_ms', 'width', 'height', 'fps', 'video_codec', 'container')


class GateName(StrEnum):
    FILE_PLAYABLE = 'FILE_PLAYABLE'
    DURATION_RANGE = 'DURATION_RANGE'
    VOICE_AUDIBLE = 'VOICE_AUDIBLE'
    OUTPUT_PROFILE_VALID = 'OUTPUT_PROFILE_VALID'


class GateStatus(StrEnum):
    PASSED = 'passed'
    FAILED = 'failed'
    NOT_APPLICABLE = 'not_applicable'
    NOT_EVALUATED = 'not_evaluated'


@dataclass(frozen=True, kw_only=True)
class GateResult:
    """Frozen outcome of one gate; same fields as the F-12 GateResult. Every status other than passed needs a reason."""

    gate: GateName
    status: GateStatus
    evidence_ref: str | None = None
    time_range: tuple[int, int] | None = None
    measured_value: bool | int | float | str | None = None
    threshold_revision: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'gate', GateName(self.gate))
        object.__setattr__(self, 'status', GateStatus(self.status))
        if self.status is not GateStatus.PASSED and not self.reason:
            raise ValueError('missing_required:reason')


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    if _is_int(value):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _scalar(value: object) -> bool | int | float | str | None:
    return value if isinstance(value, (bool, str)) or _is_number(value) else None


def _revision(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _result(gate: GateName, status: GateStatus, reason: str | None = None, *, revision: object = None, measured: object = None) -> GateResult:
    return GateResult(gate=gate, status=status, measured_value=_scalar(measured), threshold_revision=_revision(revision), reason=reason)


def _not_ready(gate: GateName, revision: object) -> GateResult:
    return _result(gate, GateStatus.NOT_EVALUATED, INPUT_NOT_READY, revision=revision)


def _require_measurements(measurements: object) -> OutputMeasurements | None:
    if measurements is not None and not isinstance(measurements, OutputMeasurements):
        raise TypeError('measurements must be OutputMeasurements or None')
    return measurements


def evaluate_file_playable(measurements: OutputMeasurements | None) -> GateResult:
    """failed unless the probe result exists, decodable is True and every core video measurement is present."""
    gate = GateName.FILE_PLAYABLE
    measurements = _require_measurements(measurements)
    if measurements is None:
        return _result(gate, GateStatus.FAILED, REASON_MISSING_MEASUREMENT)
    decodable = measurements.decodable
    measured = decodable if isinstance(decodable, bool) else None
    if decodable is not True:
        reason = REASON_NOT_DECODABLE if decodable is False else REASON_MISSING_MEASUREMENT
        return _result(gate, GateStatus.FAILED, reason, measured=measured)
    missing = [name for name in PLAYABLE_FIELDS if getattr(measurements, name) is None]
    if missing:
        names = ','.join(missing)
        return _result(gate, GateStatus.FAILED, f'{REASON_MISSING_MEASUREMENT}:{names}', measured=measured)
    return _result(gate, GateStatus.PASSED, measured=measured)


def _duration_bounds(policy: Mapping[str, object] | None) -> tuple[int, int] | None:
    if not isinstance(policy, Mapping):
        return None
    value = policy.get(POLICY_DURATION_KEY)
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(_is_int(item) for item in value):
        return None
    low, high = value
    return (low, high) if 0 <= low <= high else None


def evaluate_duration_range(measurements: OutputMeasurements | None, policy: Mapping[str, object] | None, *, threshold_revision: str | None = None) -> GateResult:
    """Both ends of policy duration_range_ms are inclusive; a duration that is not a plain integer fails."""
    gate = GateName.DURATION_RANGE
    bounds = _duration_bounds(policy)
    if bounds is None:
        return _not_ready(gate, threshold_revision)
    measurements = _require_measurements(measurements)
    duration = None if measurements is None else measurements.duration_ms
    if duration is None:
        return _result(gate, GateStatus.FAILED, REASON_MISSING_MEASUREMENT, revision=threshold_revision)
    if not _is_int(duration):
        return _result(gate, GateStatus.FAILED, REASON_INVALID_MEASUREMENT, revision=threshold_revision, measured=duration)
    low, high = bounds
    if low <= duration <= high:
        return _result(gate, GateStatus.PASSED, revision=threshold_revision, measured=duration)
    return _result(gate, GateStatus.FAILED, REASON_OUT_OF_RANGE, revision=threshold_revision, measured=duration)


def _profile_ready(profile: object) -> bool:
    if not isinstance(profile, Mapping):
        return False
    texts = all(isinstance(profile.get(key), str) and profile[key].strip() for key in PROFILE_TEXT_KEYS)
    sizes = all(_is_int(profile.get(key)) and profile[key] > 0 for key in PROFILE_SIZE_KEYS)
    fps = _is_number(profile.get(PROFILE_FPS_KEY)) and profile[PROFILE_FPS_KEY] > 0
    return bool(texts and sizes and fps)


def _profile_matches(key: str, actual: object, expected: object) -> bool:
    if key in PROFILE_TEXT_KEYS:
        return isinstance(actual, str) and actual.strip().casefold() == expected.strip().casefold()
    if key == PROFILE_FPS_KEY:
        return _is_number(actual) and math.isclose(actual, expected)
    return _is_int(actual) and actual == expected


def evaluate_output_profile(measurements: OutputMeasurements | None, expected_profile: Mapping[str, object] | None, *, threshold_revision: str | None = None) -> GateResult:
    """Compare container, codecs, size and fps with expected_profile; all six profile keys are required input."""
    gate = GateName.OUTPUT_PROFILE_VALID
    if not _profile_ready(expected_profile):
        return _not_ready(gate, threshold_revision)
    measurements = _require_measurements(measurements)
    if measurements is None:
        return _result(gate, GateStatus.FAILED, REASON_MISSING_MEASUREMENT, revision=threshold_revision)
    missing = [key for key in PROFILE_ORDER if getattr(measurements, key) is None]
    if missing:
        names = ','.join(missing)
        return _result(gate, GateStatus.FAILED, f'{REASON_MISSING_MEASUREMENT}:{names}', revision=threshold_revision)
    mismatched = [key for key in PROFILE_ORDER if not _profile_matches(key, getattr(measurements, key), expected_profile[key])]
    if mismatched:
        names = ','.join(mismatched)
        return _result(gate, GateStatus.FAILED, f'{REASON_PROFILE_MISMATCH}:{names}', revision=threshold_revision)
    return _result(gate, GateStatus.PASSED, revision=threshold_revision)


def _min_voice_level(policy: Mapping[str, object] | None) -> int | float | None:
    if not isinstance(policy, Mapping):
        return None
    value = policy.get(POLICY_VOICE_KEY)
    return value if _is_number(value) else None


def evaluate_voice_audible(measurements: OutputMeasurements | None, policy: Mapping[str, object] | None, *, threshold_revision: str | None = None) -> GateResult:
    """Needs an audio stream, a level strictly above policy min_voice_level and no severe audio error."""
    gate = GateName.VOICE_AUDIBLE
    minimum = _min_voice_level(policy)
    if minimum is None:
        return _not_ready(gate, threshold_revision)
    measurements = _require_measurements(measurements)
    failed = GateStatus.FAILED
    if measurements is None:
        return _result(gate, failed, REASON_MISSING_MEASUREMENT, revision=threshold_revision)
    if measurements.has_audio_stream is False:
        return _result(gate, failed, REASON_NO_AUDIO_STREAM, revision=threshold_revision, measured=False)
    if measurements.has_audio_stream is not True:
        return _result(gate, failed, REASON_MISSING_MEASUREMENT, revision=threshold_revision)
    level = measurements.audio_level
    errors = measurements.severe_audio_errors
    if level is None or errors is None:
        return _result(gate, failed, REASON_MISSING_MEASUREMENT, revision=threshold_revision)
    if not _is_number(level) or not isinstance(errors, tuple) or not all(isinstance(item, str) for item in errors):
        return _result(gate, failed, REASON_INVALID_MEASUREMENT, revision=threshold_revision, measured=level)
    if errors:
        return _result(gate, failed, REASON_SEVERE_AUDIO_ERROR, revision=threshold_revision, measured=level)
    if level > minimum:
        return _result(gate, GateStatus.PASSED, revision=threshold_revision, measured=level)
    return _result(gate, failed, REASON_VOICE_TOO_QUIET, revision=threshold_revision, measured=level)


def evaluate_technical_gates(probe: OutputProbePort, output_ref: str, *, policy: Mapping[str, object] | None, expected_profile: Mapping[str, object] | None, threshold_revision: str | None = None) -> tuple[GateResult, ...]:
    """Probe once and return FILE_PLAYABLE, DURATION_RANGE, VOICE_AUDIBLE, OUTPUT_PROFILE_VALID in that order, each tagged with output_ref."""
    if not isinstance(output_ref, str) or not output_ref.strip():
        raise ValueError('missing_required:output_ref')
    measurements = probe.probe(output_ref)
    results = (
        evaluate_file_playable(measurements),
        evaluate_duration_range(measurements, policy, threshold_revision=threshold_revision),
        evaluate_voice_audible(measurements, policy, threshold_revision=threshold_revision),
        evaluate_output_profile(measurements, expected_profile, threshold_revision=threshold_revision),
    )
    return tuple(replace(item, evidence_ref=output_ref) for item in results)
