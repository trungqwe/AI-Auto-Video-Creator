"""Media policy of E built from the production profile parameters (PW-E3; CT-PROC-005, CT-PROC-006, CT-PROC-007, DQ-11). Every number comes from a profile parameter: a missing or malformed parameter raises ProfileParameterMissing (code BLOCKED) and nothing is invented. The builders take ProductionProfile.parameters (dotted parameter name to value). GIẢ ĐỊNH (D8): require_transform_before_use is the fixed DQ-11 invariant True, and uncertain_range.max_exclusive is the confidence threshold of ImageSafetyPolicy."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from voice.domain.audio_bed import LoudnessConstraints
from voice.domain.image_safety import ImageSafetyAssessment, ImageSafetyPolicy, SafetyOutcome
from voice.domain.image_transform import TransformPolicy
from voice.domain.normalize import NormalizeSpec, NormalizeStep

BLOCKED = 'BLOCKED'
BLUR_ACTION = 'blur'
REJECT_ACTION = 'reject'
USE_ORIGINAL_ACTION = 'use_original'
USABLE = 'usable'
TRANSFORM = 'transform'
EXCLUDED = 'excluded'


class ProfileParameterMissing(ValueError):
    def __init__(self, parameter: str, reason: str) -> None:
        super().__init__(f'{BLOCKED}: {reason}: {parameter}')
        self.code = BLOCKED
        self.parameter = parameter
        self.reason = reason


@dataclass(frozen=True)
class ImageSafetyRules:
    revision: str
    categories: tuple[str, ...]
    reject_min_confidence: Mapping[str, float]
    blur_min_confidence: Mapping[str, float]
    uncertain_min: float
    uncertain_max_exclusive: float

    @property
    def reject_categories(self) -> frozenset[str]:
        return frozenset(self.reject_min_confidence)

    @property
    def blur_categories(self) -> frozenset[str]:
        return frozenset(self.blur_min_confidence)


def _value(parameters: Mapping[str, object], name: str) -> object:
    if not isinstance(parameters, Mapping) or parameters.get(name) is None:
        raise ProfileParameterMissing(name, 'missing parameter')
    return parameters[name]


def _member(value: object, name: str, key: str) -> object:
    if not isinstance(value, Mapping) or value.get(key) is None:
        raise ProfileParameterMissing(f'{name}.{key}', 'missing parameter')
    return value[key]


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileParameterMissing(name, 'invalid parameter')
    return value


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProfileParameterMissing(name, 'invalid parameter')
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileParameterMissing(name, 'invalid parameter')
    return value


def _revision(parameters: Mapping[str, object]) -> int:
    return _positive_int(_value(parameters, 'meta.revision'), 'meta.revision')


def _confidence_map(value: object, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise ProfileParameterMissing(name, 'invalid parameter')
    table: dict[str, float] = {}
    for key, number in value.items():
        _text(key, name)
        if not 0 < _number(number, f'{name}.{key}') <= 1:
            raise ProfileParameterMissing(f'{name}.{key}', 'invalid parameter')
        table[key] = number
    return table


def build_image_safety_rules(parameters: Mapping[str, object]) -> ImageSafetyRules:
    name = 'image_safety.thresholds'
    categories = _value(parameters, 'image_safety.categories')
    if not isinstance(categories, (list, tuple)) or not categories:
        raise ProfileParameterMissing('image_safety.categories', 'invalid parameter')
    categories = tuple(_text(item, 'image_safety.categories') for item in categories)
    thresholds = _value(parameters, name)
    reject = _confidence_map(_member(thresholds, name, 'reject_min_confidence'), f'{name}.reject_min_confidence')
    blur = _confidence_map(_member(thresholds, name, 'blur_min_confidence'), f'{name}.blur_min_confidence')
    uncertain = _member(thresholds, name, 'uncertain_range')
    low = _number(_member(uncertain, f'{name}.uncertain_range', 'min'), f'{name}.uncertain_range.min')
    high = _number(_member(uncertain, f'{name}.uncertain_range', 'max_exclusive'), f'{name}.uncertain_range.max_exclusive')
    if not 0 < low < high <= 1:
        raise ProfileParameterMissing(f'{name}.uncertain_range', 'invalid parameter')
    actions = (
        (f'{name}.blur_without_region_action', _member(thresholds, name, 'blur_without_region_action'), REJECT_ACTION),
        (f'{name}.uncertain_range.action', _member(uncertain, f'{name}.uncertain_range', 'action'), USE_ORIGINAL_ACTION),
        (f'{name}.detector_failure_action', _member(thresholds, name, 'detector_failure_action'), REJECT_ACTION),
    )
    for action_name, action, expected in actions:
        if action != expected:
            raise ProfileParameterMissing(action_name, 'unsupported action')
    if set(reject) & set(blur) or set(reject) | set(blur) != set(categories):
        raise ProfileParameterMissing(name, 'categories not covered')
    return ImageSafetyRules(f'image-safety-r{_revision(parameters)}', categories, reject, blur, low, high)


def build_image_safety_policy(parameters: Mapping[str, object]) -> ImageSafetyPolicy:
    rules = build_image_safety_rules(parameters)
    return ImageSafetyPolicy(
        revision=rules.revision,
        confidence_threshold=rules.uncertain_max_exclusive,
        transform_categories=rules.categories,
        require_transform_before_use=True,
    )


def build_transform_policy(parameters: Mapping[str, object]) -> TransformPolicy:
    rules = build_image_safety_rules(parameters)
    return TransformPolicy(revision=rules.revision, actions={name: BLUR_ACTION for name in sorted(rules.blur_categories)})


def build_transform_output_profile(parameters: Mapping[str, object]) -> dict[str, object]:
    name = 'image_safety.boxblur'
    boxblur = _value(parameters, name)
    radius = _positive_int(_member(boxblur, name, 'luma_radius'), f'{name}.luma_radius')
    power = _positive_int(_member(boxblur, name, 'luma_power'), f'{name}.luma_power')
    return {'filter': 'boxblur', 'luma_radius': radius, 'luma_power': power}


def build_normalize_spec(parameters: Mapping[str, object], *, tool_version: str) -> NormalizeSpec:
    name = 'render.profile'
    profile = _value(parameters, name)
    width = _positive_int(_member(profile, name, 'width'), f'{name}.width')
    height = _positive_int(_member(profile, name, 'height'), f'{name}.height')
    step = NormalizeStep('resize', {'width': width, 'height': height})
    return NormalizeSpec(operations=(step,), tool_version=_text(tool_version, 'tool_version'), spec_revision=f'normalize-r{_revision(parameters)}')


def read_ffmpeg_tool_version(lock_path: Path | str) -> str:
    name = 'runtime.lock.pins.ffmpeg'
    try:
        entry = json.loads(Path(lock_path).read_text(encoding='utf-8'))['pins']['ffmpeg']
    except (OSError, ValueError, KeyError, TypeError):
        raise ProfileParameterMissing(name, 'missing parameter') from None
    if not isinstance(entry, Mapping) or entry.get('status') != 'PINNED':
        raise ProfileParameterMissing(name, 'not pinned')
    return _text(entry.get('archive_name'), f'{name}.archive_name')


def build_voice_duration_policy(parameters: Mapping[str, object]) -> tuple[int, int]:
    name = 'voice.duration_range_ms'
    value = _value(parameters, name)
    low = _positive_int(_member(value, name, 'min'), f'{name}.min')
    high = _positive_int(_member(value, name, 'max'), f'{name}.max')
    if low > high:
        raise ProfileParameterMissing(name, 'invalid parameter')
    return (low, high)


def build_loudness_constraints(parameters: Mapping[str, object]) -> LoudnessConstraints:
    name = 'audio.loudness'
    value = _value(parameters, name)
    target = _number(_member(value, name, 'integrated_lufs'), f'{name}.integrated_lufs')
    tolerance = _number(_member(value, name, 'warn_tolerance_lu'), f'{name}.warn_tolerance_lu')
    peak = _number(_member(value, name, 'true_peak_dbtp'), f'{name}.true_peak_dbtp')
    if tolerance < 0:
        raise ProfileParameterMissing(f'{name}.warn_tolerance_lu', 'invalid parameter')
    return LoudnessConstraints(min_lufs=target - tolerance, max_lufs=target + tolerance, max_true_peak_dbtp=peak)


def build_mix_constraints(parameters: Mapping[str, object]) -> dict[str, object]:
    return {'bed_gain_db': _number(_value(parameters, 'audio.bed_gain_db'), 'audio.bed_gain_db')}


def build_vision_timeout_seconds(parameters: Mapping[str, object]) -> float:
    name = 'image_safety.vision'
    seconds = _number(_member(_value(parameters, name), name, 'timeout_seconds'), f'{name}.timeout_seconds')
    if seconds <= 0:
        raise ProfileParameterMissing(f'{name}.timeout_seconds', 'invalid parameter')
    return float(seconds)


def image_disposition(assessment: ImageSafetyAssessment, rules: ImageSafetyRules, *, has_regions: bool) -> tuple[str, str]:
    outcome = assessment.outcome
    if outcome is SafetyOutcome.SAFE:
        return (USABLE, 'safe')
    if outcome is SafetyOutcome.UNCERTAIN:
        return (USABLE, 'uncertain')
    if outcome is SafetyOutcome.TRANSFORM_REQUIRED:
        categories = set(assessment.categories)
        if categories & rules.reject_categories:
            return (EXCLUDED, 'reject_category')
        if not categories <= rules.blur_categories:
            return (EXCLUDED, 'unknown_category')
        if not has_regions:
            return (EXCLUDED, 'blur_without_region')
        return (TRANSFORM, 'blur_required')
    return (EXCLUDED, outcome.value.lower())


__all__ = (
    'BLOCKED',
    'BLUR_ACTION',
    'EXCLUDED',
    'ImageSafetyRules',
    'ProfileParameterMissing',
    'REJECT_ACTION',
    'TRANSFORM',
    'USABLE',
    'USE_ORIGINAL_ACTION',
    'build_image_safety_policy',
    'build_image_safety_rules',
    'build_loudness_constraints',
    'build_mix_constraints',
    'build_normalize_spec',
    'build_transform_output_profile',
    'build_transform_policy',
    'build_vision_timeout_seconds',
    'build_voice_duration_policy',
    'image_disposition',
    'read_ffmpeg_tool_version',
)
