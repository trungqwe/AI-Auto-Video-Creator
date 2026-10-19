"""F-03: RenderPackage boundary validator (CT-RND-002, BINDING-F-RENDER-PACKAGE).

Constants mirror the binding entity RenderPackage; unknown additive fields are ignored;
shell_command and arbitrary_url are rejected at every nesting level.

Pure domain: no I/O, no clock.

coveredIds: CT-RND-002 (schema), TST-SEC-INV-020 (phía F)
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
FORBIDDEN_FIELD = 'forbidden_field'
CONSTRAINT_VIOLATION = 'constraint_violation'
BINDING_VERSION = '1.0.0'


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool
    items: str | None = None


RENDER_PACKAGE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec('render_package_id', 'string', True),
    FieldSpec('package_fingerprint', 'sha256', True),
    FieldSpec('production_snapshot_ref', 'string', True),
    FieldSpec('script_version_ref', 'string', True),
    FieldSpec('production_plan_ref', 'string', True),
    FieldSpec('preset_revision_ref', 'string', True),
    FieldSpec('voice_artifact_ref', 'string', True),
    FieldSpec('word_timing_ref', 'string', True),
    FieldSpec('output_metadata_revision', 'string', True),
    FieldSpec('output_profile_revision', 'string', True),
    FieldSpec('language_validation_refs', 'array', True, 'string'),
    FieldSpec('input_artifacts', 'array', True, 'object'),
    FieldSpec('timeline', 'object', True),
    FieldSpec('hook_placement', 'object', True),
    FieldSpec('subtitle_config', 'object', True),
    FieldSpec('mix_plan', 'object', True),
    FieldSpec('allowed_fallbacks', 'array', True),
    FieldSpec('materialization_manifest', 'object', True),
    FieldSpec('output_path_ref', 'string', True),
)

RENDER_PACKAGE_FORBIDDEN_FIELDS = ('shell_command', 'arbitrary_url')

INPUT_ARTIFACT_FIELDS = MappingProxyType({
    'artifact_version_id': 'string',
    'sha256': 'sha256',
    'size_bytes': 'integer',
    'media_type': 'string',
})


class ContractViolation(ValueError):
    def __init__(self, code: str, field: str, path: str | None = None) -> None:
        self.code = code
        self.field = field
        self.path = path or field
        super().__init__(f'{code}:{self.path}')


@dataclass(frozen=True)
class InputArtifactRecord:
    artifact_version_id: str
    sha256: str
    size_bytes: int
    media_type: str


@dataclass(frozen=True)
class RenderPackageRecord:
    render_package_id: str
    package_fingerprint: str
    production_snapshot_ref: str
    script_version_ref: str
    production_plan_ref: str
    preset_revision_ref: str
    voice_artifact_ref: str
    word_timing_ref: str
    output_metadata_revision: str
    output_profile_revision: str
    language_validation_refs: tuple[str, ...]
    input_artifacts: tuple[InputArtifactRecord, ...]
    timeline: Mapping
    hook_placement: Mapping
    subtitle_config: Mapping
    mix_plan: Mapping
    allowed_fallbacks: tuple
    materialization_manifest: Mapping
    output_path_ref: str


_SHA256_RE = re.compile(r'[0-9a-f]{64}')


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_TYPE_CHECKS = {
    'string': lambda value: isinstance(value, str),
    'integer': _is_int,
    'object': lambda value: isinstance(value, Mapping),
    'array': lambda value: isinstance(value, list),
    'sha256': lambda value: isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
}
_FROZEN_FIELDS = ('timeline', 'hook_placement', 'subtitle_config', 'mix_plan', 'allowed_fallbacks', 'materialization_manifest')


def _child_path(path: str, key: object) -> str:
    return f'{path}.{key}' if path else str(key)


def _scan_forbidden(value: object, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in RENDER_PACKAGE_FORBIDDEN_FIELDS:
                raise ContractViolation(FORBIDDEN_FIELD, key, _child_path(path, key))
            _scan_forbidden(child, _child_path(path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _scan_forbidden(child, f'{path}[{index}]')


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _input_artifact(item: Mapping, index: int) -> InputArtifactRecord:
    values = {}
    for name, type_name in INPUT_ARTIFACT_FIELDS.items():
        path = f'input_artifacts[{index}].{name}'
        if name not in item:
            raise ContractViolation(MISSING_REQUIRED, 'input_artifacts', path)
        value = item[name]
        if value is None or not _TYPE_CHECKS[type_name](value):
            raise ContractViolation(WRONG_TYPE, 'input_artifacts', path)
        if name == 'size_bytes' and value < 0:
            raise ContractViolation(CONSTRAINT_VIOLATION, 'input_artifacts', path)
        values[name] = value
    return InputArtifactRecord(**values)


def validate_render_package_payload(payload: object) -> RenderPackageRecord:
    """Validate render package boundary payload against binding schema.

    Order of checks: non-mapping, forbidden fields at every nesting level,
    fields in binding order, and input artifacts items.
    Raises the first ContractViolation. Does not mutate the input payload;
    unknown additive fields are ignored.
    """
    if not isinstance(payload, Mapping):
        raise ContractViolation(WRONG_TYPE, '$')
    _scan_forbidden(payload, '')
    for spec in RENDER_PACKAGE_FIELDS:
        if spec.name not in payload:
            if spec.required:
                raise ContractViolation(MISSING_REQUIRED, spec.name)
            continue
        value = payload[spec.name]
        if value is None or not _TYPE_CHECKS[spec.type](value):
            raise ContractViolation(WRONG_TYPE, spec.name)
        if spec.items is not None and not all(_TYPE_CHECKS[spec.items](item) for item in value):
            raise ContractViolation(WRONG_TYPE, spec.name)
    values = {spec.name: payload.get(spec.name) for spec in RENDER_PACKAGE_FIELDS}
    values['language_validation_refs'] = tuple(values['language_validation_refs'])
    values['input_artifacts'] = tuple(_input_artifact(item, index) for index, item in enumerate(values['input_artifacts']))
    for name in _FROZEN_FIELDS:
        values[name] = _freeze(values[name])
    return RenderPackageRecord(**values)
