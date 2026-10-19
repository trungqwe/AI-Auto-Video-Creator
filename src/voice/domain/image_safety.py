"""Voice domain image safety assessment (CT-PROC-005, CT-STATE-006)."""
from __future__ import annotations

import dataclasses
import enum
import math
from types import MappingProxyType

INPUT_NOT_READY = 'INPUT_NOT_READY'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
CONSTRAINT_VIOLATION = 'constraint_violation'
IMAGE_KIND = 'image'


class ImageSafetyError(ValueError):
    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f'{code}: {reason}')


class SafetyOutcome(enum.StrEnum):
    SAFE = 'SAFE'
    TRANSFORM_REQUIRED = 'TRANSFORM_REQUIRED'
    UNCERTAIN = 'UNCERTAIN'
    DETECTION_FAILED = 'DETECTION_FAILED'
    TRANSFORM_FAILED = 'TRANSFORM_FAILED'
    UNREADABLE = 'UNREADABLE'


class DetectionStatus(enum.StrEnum):
    COMPLETED = 'completed'
    FAILED = 'failed'
    UNREADABLE = 'unreadable'


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ImageSafetyError(WRONG_TYPE, field)
    if not value.strip():
        raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    return value


def _names(value: object, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ImageSafetyError(WRONG_TYPE, field)
    names = tuple(sorted({_text(item, field) for item in value}))
    if not names and not allow_empty:
        raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    return names


def _unit_interval(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImageSafetyError(WRONG_TYPE, field)
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    return number


def _enum_member(enum_type: type[enum.StrEnum], value: object, field: str):
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ImageSafetyError(WRONG_TYPE, field)
    try:
        return enum_type(value)
    except ValueError:
        raise ImageSafetyError(ENUM_VIOLATION, field) from None


@dataclasses.dataclass(frozen=True)
class ImageDetection:
    status: object
    categories: object = ()
    confidence: object = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'status', _enum_member(DetectionStatus, self.status, 'status'))
        object.__setattr__(self, 'categories', _names(self.categories, 'categories', allow_empty=True))
        if self.confidence is not None:
            object.__setattr__(self, 'confidence', _unit_interval(self.confidence, 'confidence'))


@dataclasses.dataclass(frozen=True)
class ImageSafetyPolicy:
    revision: object
    confidence_threshold: object
    transform_categories: object
    require_transform_before_use: object

    def __post_init__(self) -> None:
        _text(self.revision, 'revision')
        threshold = _unit_interval(self.confidence_threshold, 'confidence_threshold')
        if threshold <= 0.0:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'confidence_threshold')
        object.__setattr__(self, 'confidence_threshold', threshold)
        object.__setattr__(
            self, 'transform_categories', _names(self.transform_categories, 'transform_categories', allow_empty=False)
        )
        if not isinstance(self.require_transform_before_use, bool):
            raise ImageSafetyError(WRONG_TYPE, 'require_transform_before_use')


_FIXED_ORIGINAL_USABLE = MappingProxyType({
    SafetyOutcome.SAFE: True,
    SafetyOutcome.UNCERTAIN: True,
    SafetyOutcome.DETECTION_FAILED: True,
    SafetyOutcome.TRANSFORM_FAILED: True,
    SafetyOutcome.UNREADABLE: False,
})
_WARNING_OUTCOMES = frozenset({
    SafetyOutcome.UNCERTAIN,
    SafetyOutcome.DETECTION_FAILED,
    SafetyOutcome.TRANSFORM_FAILED,
})


def original_usable_for(outcome: object, require_transform_before_use: object = False) -> bool:
    if not isinstance(require_transform_before_use, bool):
        raise ImageSafetyError(WRONG_TYPE, 'require_transform_before_use')
    member = _enum_member(SafetyOutcome, outcome, 'outcome')
    if member is SafetyOutcome.TRANSFORM_REQUIRED:
        return not require_transform_before_use
    return _FIXED_ORIGINAL_USABLE[member]


@dataclasses.dataclass(frozen=True)
class ImageSafetyAssessment:
    outcome: object
    original_usable: object
    reason: object
    warnings: object = ()
    categories: object = ()
    confidence: object = None
    policy_revision: object = None

    def __post_init__(self) -> None:
        outcome = _enum_member(SafetyOutcome, self.outcome, 'outcome')
        if not isinstance(self.original_usable, bool):
            raise ImageSafetyError(WRONG_TYPE, 'original_usable')
        _text(self.reason, 'reason')
        warnings = _names(self.warnings, 'warnings', allow_empty=True)
        categories = _names(self.categories, 'categories', allow_empty=True)
        confidence = None if self.confidence is None else _unit_interval(self.confidence, 'confidence')
        if self.policy_revision is not None:
            _text(self.policy_revision, 'policy_revision')
        if outcome is not SafetyOutcome.TRANSFORM_REQUIRED and self.original_usable != _FIXED_ORIGINAL_USABLE[outcome]:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'original_usable')
        if outcome in _WARNING_OUTCOMES and not warnings:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'warnings')
        if outcome is SafetyOutcome.SAFE and (warnings or categories):
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'safe_not_clean')
        if outcome is SafetyOutcome.TRANSFORM_REQUIRED and not categories:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'categories')
        object.__setattr__(self, 'outcome', outcome)
        object.__setattr__(self, 'warnings', warnings)
        object.__setattr__(self, 'categories', categories)
        object.__setattr__(self, 'confidence', confidence)


@dataclasses.dataclass(frozen=True)
class SafetyNotApplicable:
    media_kind: str
    reason: str = 'image_safety_applies_to_images_only'


_DETECTOR_RAISED = object()


def _run_detector(detection: object) -> object:
    if not callable(detection):
        return detection
    try:
        return detection()
    except Exception:
        return _DETECTOR_RAISED


def _build(
    outcome: SafetyOutcome,
    reason: str,
    policy: ImageSafetyPolicy,
    confidence: float | None = None,
    categories: tuple[str, ...] = (),
) -> ImageSafetyAssessment:
    return ImageSafetyAssessment(
        outcome=outcome,
        original_usable=original_usable_for(outcome, policy.require_transform_before_use),
        reason=reason,
        warnings=(reason,) if outcome in _WARNING_OUTCOMES else (),
        categories=categories,
        confidence=confidence,
        policy_revision=policy.revision,
    )


def assess_image_safety(
    media_kind: object, detection: object, policy: object
) -> ImageSafetyAssessment | SafetyNotApplicable:
    if not isinstance(media_kind, str):
        raise ImageSafetyError(WRONG_TYPE, 'media_kind')
    if media_kind != IMAGE_KIND:
        return SafetyNotApplicable(media_kind=media_kind)
    if policy is None:
        raise ImageSafetyError(INPUT_NOT_READY, 'missing_policy')
    if not isinstance(policy, ImageSafetyPolicy):
        raise ImageSafetyError(WRONG_TYPE, 'policy')
    result = _run_detector(detection)
    if result is _DETECTOR_RAISED:
        return _build(SafetyOutcome.DETECTION_FAILED, 'detector_raised', policy)
    if not isinstance(result, ImageDetection):
        return _build(SafetyOutcome.DETECTION_FAILED, 'detector_bad_result', policy)
    if result.status is DetectionStatus.UNREADABLE:
        return _build(SafetyOutcome.UNREADABLE, 'unreadable_file', policy)
    if result.status is DetectionStatus.FAILED:
        return _build(SafetyOutcome.DETECTION_FAILED, 'detector_failed', policy)
    if result.confidence is None or result.confidence < policy.confidence_threshold:
        return _build(SafetyOutcome.UNCERTAIN, 'confidence_below_threshold', policy, result.confidence)
    matched = tuple(name for name in result.categories if name in policy.transform_categories)
    if matched:
        return _build(
            SafetyOutcome.TRANSFORM_REQUIRED, 'categories_require_transform', policy, result.confidence, matched
        )
    return _build(SafetyOutcome.SAFE, 'no_sensitive_category', policy, result.confidence)


__all__ = (
    'INPUT_NOT_READY',
    'WRONG_TYPE',
    'ENUM_VIOLATION',
    'CONSTRAINT_VIOLATION',
    'IMAGE_KIND',
    'ImageSafetyError',
    'SafetyOutcome',
    'DetectionStatus',
    'ImageDetection',
    'ImageSafetyPolicy',
    'ImageSafetyAssessment',
    'SafetyNotApplicable',
    'original_usable_for',
    'assess_image_safety',
)
