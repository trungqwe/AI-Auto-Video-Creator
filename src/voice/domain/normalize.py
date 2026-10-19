"""NormalizeMedia planning: spec, fingerprint and rendition plan with lineage (CT-PROC-007).

Pure domain: no I/O, no clock, no process execution. A plan is data only; MediaToolPort runs it.
Crop coordinates are in input-frame pixels (GIẢ ĐỊNH, IMPL-PLAN-E §7); every crop must keep the focus region of the plan.
Blur and recolor are safety transforms (CT-PROC-006), never normalize operations; clips reject them with a dedicated code.
"""
from __future__ import annotations

import dataclasses
import enum
import math
import re
from collections.abc import Mapping
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash
from voice.domain.processing import (
    CONSTRAINT_VIOLATION,
    ENUM_VIOLATION,
    MISSING_REQUIRED,
    WRONG_TYPE,
    ArtifactRef,
    Disposition,
    OutputClass,
    ProcessingContractError,
    retention_intent,
)
from voice.ports.media_tool import ToolOutcome

FOCUS_RULE_VIOLATION = 'focus_rule_violation'
SAFETY_TRANSFORM_NOT_APPLICABLE = 'safety_transform_not_applicable'
SHELL_COMMAND_REJECTED = 'shell_command_rejected'
MEDIA_KINDS = ('image', 'clip', 'audio')
SAFETY_TRANSFORM_NAMES = frozenset({'blur', 'recolor'})

_MAX_SAFE_INT = 2**53 - 1
_SHELL_CHARS = frozenset(';&|`$<>()\n\r')
_SHELL_TOOL_PATTERN = r'\s*(ffmpeg|ffprobe|sox|magick|bash|sh|cmd|powershell|pwsh)\s+\S'


class NormalizeOperation(enum.StrEnum):
    CROP = 'crop'
    RESIZE = 'resize'
    PAD = 'pad'
    COLOR_CONVERSION = 'color_conversion'
    TRANSCODE = 'transcode'
    AUDIO_NORMALIZE = 'audio_normalize'
    EXTRACT_FRAME = 'extract_frame'
    DURATION_TRIM = 'duration_trim'


def _check_no_shell(text: str, field: str) -> str:
    if any(ch in _SHELL_CHARS for ch in text) or re.match(_SHELL_TOOL_PATTERN, text, re.IGNORECASE):
        raise ProcessingContractError(SHELL_COMMAND_REJECTED, field)
    return text


def _check_text(value: object, field: str) -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    if not value.strip():
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return _check_no_shell(value, field)


def _check_int(value: object, field: str, minimum: int) -> int:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProcessingContractError(WRONG_TYPE, field)
    if value < minimum or value > _MAX_SAFE_INT:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return value


def _freeze(value: object, field: str) -> object:
    """Deep-copy JSON-like params into immutable values; reject non-finite numbers and shell text."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _check_no_shell(value, field)
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INT:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
        return value
    if isinstance(value, Mapping):
        items = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProcessingContractError(WRONG_TYPE, field)
            items[_check_no_shell(key, field)] = _freeze(item, f'{field}.{key}')
        return MappingProxyType(items)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, f'{field}[{index}]') for index, item in enumerate(value))
    raise ProcessingContractError(WRONG_TYPE, field)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclasses.dataclass(frozen=True)
class FocusRegion:
    """Pixel rectangle of the input frame that the plan must keep."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _check_int(self.x, 'focus_region.x', 0)
        _check_int(self.y, 'focus_region.y', 0)
        _check_int(self.width, 'focus_region.width', 1)
        _check_int(self.height, 'focus_region.height', 1)

    def is_inside(self, x: int, y: int, width: int, height: int) -> bool:
        return (
            x <= self.x
            and y <= self.y
            and self.x + self.width <= x + width
            and self.y + self.height <= y + height
        )


@dataclasses.dataclass(frozen=True)
class NormalizeStep:
    """One ordered operation with copied, immutable params; names outside NormalizeOperation stay plain text."""

    operation: str
    params: Mapping = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        operation = _check_text(self.operation, 'operation')
        try:
            operation = NormalizeOperation(operation)
        except ValueError:
            pass
        object.__setattr__(self, 'operation', operation)
        if self.params is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'params')
        if not isinstance(self.params, Mapping):
            raise ProcessingContractError(WRONG_TYPE, 'params')
        object.__setattr__(self, 'params', _freeze(self.params, 'params'))

    @property
    def is_safety_transform(self) -> bool:
        names = {str(self.operation).lower(), *(key.lower() for key in self.params)}
        return not names.isdisjoint(SAFETY_TRANSFORM_NAMES)


@dataclasses.dataclass(frozen=True)
class NormalizeSpec:
    """Ordered operations plus tool_version, spec_revision and optional seed; the fingerprint is request_hash of all of them."""

    operations: tuple
    tool_version: str
    spec_revision: str
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.operations is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'operations')
        if isinstance(self.operations, (str, bytes, Mapping)):
            raise ProcessingContractError(WRONG_TYPE, 'operations')
        try:
            steps = tuple(self.operations)
        except TypeError:
            raise ProcessingContractError(WRONG_TYPE, 'operations') from None
        if not steps:
            raise ProcessingContractError(MISSING_REQUIRED, 'operations')
        if not all(isinstance(step, NormalizeStep) for step in steps):
            raise ProcessingContractError(WRONG_TYPE, 'operations')
        object.__setattr__(self, 'operations', steps)
        _check_text(self.tool_version, 'tool_version')
        _check_text(self.spec_revision, 'spec_revision')
        if self.seed is not None:
            _check_int(self.seed, 'seed', -_MAX_SAFE_INT)

    @property
    def spec_fingerprint(self) -> str:
        return compute_spec_fingerprint(self)


def compute_spec_fingerprint(spec: object) -> str:
    if not isinstance(spec, NormalizeSpec):
        raise ProcessingContractError(WRONG_TYPE, 'spec')
    return request_hash({
        'operations': [
            {'operation': str(step.operation), 'params': _thaw(step.params)} for step in spec.operations
        ],
        'tool_version': spec.tool_version,
        'spec_revision': spec.spec_revision,
        'seed': spec.seed,
    })


def compute_plan_fingerprint(input_ref: ArtifactRef, spec_fingerprint: str) -> str:
    """Dedup key: same input bytes and spec fingerprint give the same key; focus region and media kind do not change it."""
    return request_hash({
        'input_artifact_ref': {'ref': input_ref.ref, 'content_sha256': input_ref.content_sha256},
        'spec_fingerprint': spec_fingerprint,
    })


def _crop_rect(params: Mapping, field: str) -> tuple[int, int, int, int]:
    x = _check_int(params.get('x'), f'{field}.x', 0)
    y = _check_int(params.get('y'), f'{field}.y', 0)
    width = _check_int(params.get('width'), f'{field}.width', 1)
    height = _check_int(params.get('height'), f'{field}.height', 1)
    return x, y, width, height


def _validate_operations(spec: NormalizeSpec, media_kind: str, focus_region: FocusRegion | None) -> None:
    if media_kind == 'clip' and any(step.is_safety_transform for step in spec.operations):
        raise ProcessingContractError(SAFETY_TRANSFORM_NOT_APPLICABLE, 'operations')
    for index, step in enumerate(spec.operations):
        field = f'operations[{index}]'
        if step.is_safety_transform or not isinstance(step.operation, NormalizeOperation):
            raise ProcessingContractError(ENUM_VIOLATION, f'{field}.operation')
        if step.operation is NormalizeOperation.CROP:
            x, y, width, height = _crop_rect(step.params, f'{field}.params')
            if focus_region is not None and not focus_region.is_inside(x, y, width, height):
                raise ProcessingContractError(FOCUS_RULE_VIOLATION, f'{field}.params')


@dataclasses.dataclass(frozen=True)
class RenditionPlan:
    """Data-only plan for one new rendition: lineage to the input, a new output ref and both fingerprints."""

    input_ref: ArtifactRef
    output_ref: str
    media_kind: str
    spec: NormalizeSpec
    spec_fingerprint: str
    plan_fingerprint: str
    lineage_refs: tuple
    focus_region: FocusRegion | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.input_ref, ArtifactRef):
            raise ProcessingContractError(WRONG_TYPE, 'input_ref')
        _check_text(self.output_ref, 'output_ref')
        if self.output_ref == self.input_ref.ref:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_ref')
        if self.media_kind not in MEDIA_KINDS:
            raise ProcessingContractError(ENUM_VIOLATION, 'media_kind')
        if not isinstance(self.spec, NormalizeSpec):
            raise ProcessingContractError(WRONG_TYPE, 'spec')
        if self.focus_region is not None and not isinstance(self.focus_region, FocusRegion):
            raise ProcessingContractError(WRONG_TYPE, 'focus_region')
        lineage = self.lineage_refs
        if lineage is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'lineage_refs')
        if isinstance(lineage, (str, bytes, Mapping)):
            raise ProcessingContractError(WRONG_TYPE, 'lineage_refs')
        try:
            lineage = tuple(lineage)
        except TypeError:
            raise ProcessingContractError(WRONG_TYPE, 'lineage_refs') from None
        if not all(isinstance(ref, str) for ref in lineage):
            raise ProcessingContractError(WRONG_TYPE, 'lineage_refs')
        if self.input_ref.ref not in lineage or self.output_ref in lineage:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'lineage_refs')
        if self.spec_fingerprint != compute_spec_fingerprint(self.spec):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'spec_fingerprint')
        if self.plan_fingerprint != compute_plan_fingerprint(self.input_ref, self.spec_fingerprint):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'plan_fingerprint')
        _validate_operations(self.spec, self.media_kind, self.focus_region)
        object.__setattr__(self, 'lineage_refs', lineage)

    @property
    def output_class(self) -> OutputClass:
        return retention_intent('rendition')


def plan_rendition(
    input_ref: ArtifactRef,
    spec: NormalizeSpec,
    media_kind: str,
    focus_region: FocusRegion | None = None,
    output_ref: str | None = None,
) -> RenditionPlan:
    """Plan one new rendition of input_ref; the default output ref is derived from the plan fingerprint and never equals the input."""
    if not isinstance(input_ref, ArtifactRef):
        raise ProcessingContractError(WRONG_TYPE, 'input_ref')
    spec_fp = compute_spec_fingerprint(spec)
    plan_fp = compute_plan_fingerprint(input_ref, spec_fp)
    return RenditionPlan(
        input_ref=input_ref,
        output_ref=f'rendition:{plan_fp}' if output_ref is None else output_ref,
        media_kind=media_kind,
        spec=spec,
        spec_fingerprint=spec_fp,
        plan_fingerprint=plan_fp,
        lineage_refs=(input_ref.ref,),
        focus_region=focus_region,
    )


def verify_tool_outcome(plan: RenditionPlan, outcome: ToolOutcome) -> None:
    """A succeeded outcome must name exactly the planned new output ref, never the original."""
    if not isinstance(plan, RenditionPlan):
        raise ProcessingContractError(WRONG_TYPE, 'plan')
    if not isinstance(outcome, ToolOutcome):
        raise ProcessingContractError(WRONG_TYPE, 'outcome')
    if outcome.status is Disposition.SUCCEEDED and outcome.output_ref != plan.output_ref:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_ref')


__all__ = (
    'FOCUS_RULE_VIOLATION',
    'SAFETY_TRANSFORM_NOT_APPLICABLE',
    'SHELL_COMMAND_REJECTED',
    'MEDIA_KINDS',
    'NormalizeOperation',
    'FocusRegion',
    'NormalizeStep',
    'NormalizeSpec',
    'RenditionPlan',
    'compute_spec_fingerprint',
    'compute_plan_fingerprint',
    'plan_rendition',
    'verify_tool_outcome',
)
