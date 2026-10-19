"""Voice domain sensitive image transform contract (CT-PROC-006)."""
from __future__ import annotations

import copy
import dataclasses
import enum
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from voice.domain.image_safety import (
    CONSTRAINT_VIOLATION,
    ENUM_VIOLATION,
    IMAGE_KIND,
    INPUT_NOT_READY,
    WRONG_TYPE,
    ImageSafetyAssessment,
    ImageSafetyError,
    SafetyNotApplicable,
    SafetyOutcome,
    original_usable_for,
)
from voice.domain.processing import ArtifactRef

HOOK_ALREADY_BLURRED = 'hook_already_blurred'


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ImageSafetyError(WRONG_TYPE, field)
    if not value.strip():
        raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    return value


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


def _action_pairs(value: object, field: str) -> tuple[tuple[str, str], ...]:
    if isinstance(value, Mapping):
        items = tuple(value.items())
    elif isinstance(value, (list, tuple)) and all(isinstance(i, (list, tuple)) and len(i) == 2 for i in value):
        items = tuple(value)
    else:
        raise ImageSafetyError(WRONG_TYPE, field)
    table: dict[str, str] = {}
    for category, action in items:
        if table.setdefault(_text(category, field), _text(action, field)) != action:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    if not table:
        raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
    return tuple(sorted(table.items()))


class TransformStatus(enum.StrEnum):
    SUCCESS = 'success'
    WARNING = 'warning'
    FAILURE = 'failure'


@dataclasses.dataclass(frozen=True)
class TransformRegion:
    category: object
    confidence: object
    mask_ref: object

    def __post_init__(self) -> None:
        _text(self.category, 'category')
        object.__setattr__(self, 'confidence', _unit_interval(self.confidence, 'confidence'))
        _text(self.mask_ref, 'mask_ref')


@dataclasses.dataclass(frozen=True)
class TransformPolicy:
    revision: object
    actions: object

    def __post_init__(self) -> None:
        _text(self.revision, 'revision')
        object.__setattr__(self, 'actions', _action_pairs(self.actions, 'actions'))

    def action_for(self, category: str) -> str | None:
        return dict(self.actions).get(category)


@dataclasses.dataclass(frozen=True)
class TransformOutput:
    processed_ref: object
    evidence_ref: object
    processor_version: object
    post_assessment: object


@dataclasses.dataclass(frozen=True)
class TransformRequest:
    source_ref: object
    regions: object
    categories: object
    actions: object
    transform_policy_revision: object
    output_profile: object

    def __post_init__(self) -> None:
        if not isinstance(self.source_ref, ArtifactRef):
            raise ImageSafetyError(WRONG_TYPE, 'source_ref')
        if not isinstance(self.regions, (list, tuple)):
            raise ImageSafetyError(WRONG_TYPE, 'regions')
        if not all(isinstance(item, TransformRegion) for item in self.regions):
            raise ImageSafetyError(WRONG_TYPE, 'regions')
        categories = _names(self.categories, 'categories', allow_empty=False)
        actions = _action_pairs(self.actions, 'actions')
        if tuple(category for category, _ in actions) != categories:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'actions')
        if not self.regions or any(item.category not in categories for item in self.regions):
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'regions')
        _text(self.transform_policy_revision, 'transform_policy_revision')
        if not isinstance(self.output_profile, Mapping):
            raise ImageSafetyError(WRONG_TYPE, 'output_profile')
        if not self.output_profile:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'output_profile')
        object.__setattr__(self, 'regions', tuple(self.regions))
        object.__setattr__(self, 'categories', categories)
        object.__setattr__(self, 'actions', actions)
        object.__setattr__(self, 'output_profile', MappingProxyType(copy.deepcopy(dict(self.output_profile))))


@runtime_checkable
class TransformPort(Protocol):
    def transform(self, request: TransformRequest) -> TransformOutput:
        """Apply the policy action per category to a new artifact; never mutate or replace the source ref."""
        ...


_POST_OUTCOMES = MappingProxyType({
    TransformStatus.SUCCESS: frozenset({SafetyOutcome.SAFE}),
    TransformStatus.WARNING: frozenset({SafetyOutcome.UNCERTAIN, SafetyOutcome.DETECTION_FAILED}),
    TransformStatus.FAILURE: frozenset({SafetyOutcome.TRANSFORM_FAILED}),
})


@dataclasses.dataclass(frozen=True)
class TransformResult:
    status: object
    original_ref: object
    processed_ref: object
    evidence_ref: object
    processor_version: object
    post_assessment: object
    warnings: object = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, str):
            raise ImageSafetyError(WRONG_TYPE, 'status')
        try:
            status = TransformStatus(self.status)
        except ValueError:
            raise ImageSafetyError(ENUM_VIOLATION, 'status') from None
        if not isinstance(self.original_ref, ArtifactRef):
            raise ImageSafetyError(WRONG_TYPE, 'original_ref')
        post = self.post_assessment
        if not isinstance(post, ImageSafetyAssessment):
            raise ImageSafetyError(WRONG_TYPE, 'post_assessment')
        warnings = _names(self.warnings, 'warnings', allow_empty=True)
        if post.outcome not in _POST_OUTCOMES[status]:
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'post_assessment')
        if status is TransformStatus.FAILURE:
            absent = (
                ('processed_ref', self.processed_ref),
                ('evidence_ref', self.evidence_ref),
                ('processor_version', self.processor_version),
            )
            for field, value in absent:
                if value is not None:
                    raise ImageSafetyError(CONSTRAINT_VIOLATION, field)
        else:
            if not isinstance(self.processed_ref, ArtifactRef):
                raise ImageSafetyError(WRONG_TYPE, 'processed_ref')
            if self.processed_ref.ref == self.original_ref.ref:
                raise ImageSafetyError(CONSTRAINT_VIOLATION, 'processed_ref')
            _text(self.evidence_ref, 'evidence_ref')
            _text(self.processor_version, 'processor_version')
        if bool(warnings) != (status is not TransformStatus.SUCCESS):
            raise ImageSafetyError(CONSTRAINT_VIOLATION, 'warnings')
        object.__setattr__(self, 'status', status)
        object.__setattr__(self, 'warnings', warnings)

    @property
    def outcome(self) -> SafetyOutcome:
        return self.post_assessment.outcome

    @property
    def lineage(self) -> tuple[ArtifactRef, ...]:
        return (self.original_ref,)


@dataclasses.dataclass(frozen=True)
class TransformSkipped:
    reason: str = HOOK_ALREADY_BLURRED


_POST_FAILURE_REASON = MappingProxyType({
    SafetyOutcome.TRANSFORM_REQUIRED: 'post_assessment_still_transform_required',
    SafetyOutcome.UNREADABLE: 'processed_unreadable',
    SafetyOutcome.TRANSFORM_FAILED: 'post_assessment_transform_failed',
})


def _failure(request: TransformRequest, reason: str) -> TransformResult:
    return TransformResult(
        status=TransformStatus.FAILURE,
        original_ref=request.source_ref,
        processed_ref=None,
        evidence_ref=None,
        processor_version=None,
        post_assessment=ImageSafetyAssessment(
            outcome=SafetyOutcome.TRANSFORM_FAILED,
            original_usable=original_usable_for(SafetyOutcome.TRANSFORM_FAILED),
            reason=reason,
            warnings=(reason,),
            categories=request.categories,
            policy_revision=request.transform_policy_revision,
        ),
        warnings=(reason,),
    )


def _judge(request: TransformRequest, output: object) -> TransformResult:
    if (
        not isinstance(output, TransformOutput)
        or not isinstance(output.processed_ref, ArtifactRef)
        or not isinstance(output.post_assessment, ImageSafetyAssessment)
        or not _is_text(output.evidence_ref)
        or not _is_text(output.processor_version)
    ):
        return _failure(request, 'transform_bad_result')
    if output.processed_ref.ref == request.source_ref.ref:
        return _failure(request, 'processed_replaces_original')
    post = output.post_assessment
    if post.outcome in _POST_FAILURE_REASON:
        return _failure(request, _POST_FAILURE_REASON[post.outcome])
    safe = post.outcome is SafetyOutcome.SAFE
    return TransformResult(
        status=TransformStatus.SUCCESS if safe else TransformStatus.WARNING,
        original_ref=request.source_ref,
        processed_ref=output.processed_ref,
        evidence_ref=output.evidence_ref,
        processor_version=output.processor_version,
        post_assessment=post,
        warnings=() if safe else (f'post_assessment_{post.outcome.value.lower()}',),
    )


def transform_sensitive_image(
    media_kind: object,
    user_visual_hook: object,
    assessment: object,
    source_ref: object,
    regions: object,
    policy: object,
    output_profile: object,
    port: object,
) -> TransformResult | SafetyNotApplicable | TransformSkipped:
    if not isinstance(media_kind, str):
        raise ImageSafetyError(WRONG_TYPE, 'media_kind')
    if media_kind != IMAGE_KIND:
        return SafetyNotApplicable(media_kind=media_kind)
    if not isinstance(user_visual_hook, bool):
        raise ImageSafetyError(WRONG_TYPE, 'user_visual_hook')
    if user_visual_hook:
        return TransformSkipped(HOOK_ALREADY_BLURRED)
    if not isinstance(assessment, ImageSafetyAssessment):
        raise ImageSafetyError(WRONG_TYPE, 'assessment')
    if assessment.outcome is not SafetyOutcome.TRANSFORM_REQUIRED:
        raise ImageSafetyError(CONSTRAINT_VIOLATION, 'assessment_not_transform_required')
    if policy is None:
        raise ImageSafetyError(INPUT_NOT_READY, 'missing_policy')
    if not isinstance(policy, TransformPolicy):
        raise ImageSafetyError(WRONG_TYPE, 'policy')
    actions = []
    for category in assessment.categories:
        action = policy.action_for(category)
        if action is None:
            raise ImageSafetyError(INPUT_NOT_READY, f'missing_action:{category}')
        actions.append((category, action))
    request = TransformRequest(
        source_ref, regions, assessment.categories, tuple(actions), policy.revision, output_profile
    )
    if port is None:
        raise ImageSafetyError(INPUT_NOT_READY, 'missing_port')
    if not isinstance(port, TransformPort):
        raise ImageSafetyError(WRONG_TYPE, 'port')
    try:
        output = port.transform(request)
    except Exception:
        return _failure(request, 'transform_raised')
    return _judge(request, output)


__all__ = (
    'HOOK_ALREADY_BLURRED',
    'TransformStatus',
    'TransformRegion',
    'TransformPolicy',
    'TransformOutput',
    'TransformRequest',
    'TransformPort',
    'TransformResult',
    'TransformSkipped',
    'transform_sensitive_image',
)