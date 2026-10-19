"""RenderPresetRevision and PresetCatalog (CT-RND-001).

A preset revision is a frozen, versioned value; preset_fingerprint is request_hash of every other field.
A catalog only grows by returning a new catalog and never overwrites a revision.
Preset names, styles and numeric settings come from the caller; this module holds none (ROADMAP-OPEN-009 is a pending user checkpoint).
Pure domain: no I/O, no clock.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
INVALID_VALUE = 'invalid_value'
PRESET_FINGERPRINT_MISMATCH = 'preset_fingerprint_mismatch'
DUPLICATE_REVISION = 'duplicate_revision'
PRESET_NOT_FOUND = 'preset_not_found'
PRESET_COUNT_NOT_FIVE = 'preset_count_not_five'
REQUIRED_PRESET_COUNT = 5
FINGERPRINT_FIELD = 'preset_fingerprint'
TEXT_FIELDS = ('preset_key', 'output_profile_ref')

_SHA256_RE = re.compile(r'[0-9a-f]{64}')


class PresetValidationError(ValueError):
    """A preset value broke CT-RND-001; `code` is the stable reason and `field` the offending field name."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f'{code}:{field}')
        self.code = code
        self.field = field


class PresetNotFoundError(LookupError):
    """The catalog has no such preset_key (or not the requested revision); `code` is preset_not_found."""

    def __init__(self, preset_key: str, revision: int | None) -> None:
        super().__init__(f'{PRESET_NOT_FOUND}:{preset_key}:{revision}')
        self.code = PRESET_NOT_FOUND
        self.preset_key = preset_key
        self.revision = revision


def _freeze(value: object, name: str) -> object:
    """Deep-freeze JSON-like data: mappings become read-only MappingProxyType, lists and tuples become tuples."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PresetValidationError(INVALID_VALUE, name)
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise PresetValidationError(WRONG_TYPE, name)
        return MappingProxyType({key: _freeze(item, name) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, name) for item in value)
    raise PresetValidationError(WRONG_TYPE, name)


def _thaw(value: object) -> object:
    """Inverse of _freeze for hashing: read-only mappings become dicts and tuples become lists."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: object, name: str) -> str:
    if value is None:
        raise PresetValidationError(MISSING_REQUIRED, name)
    if not isinstance(value, str):
        raise PresetValidationError(WRONG_TYPE, name)
    if not value.strip():
        raise PresetValidationError(MISSING_REQUIRED, name)
    return value


def _revision_number(value: object, name: str) -> int:
    if value is None:
        raise PresetValidationError(MISSING_REQUIRED, name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PresetValidationError(WRONG_TYPE, name)
    if value < 1:
        raise PresetValidationError(INVALID_VALUE, name)
    return value


def _section(value: object, name: str) -> object:
    if value is None:
        raise PresetValidationError(MISSING_REQUIRED, name)
    if not isinstance(value, Mapping):
        raise PresetValidationError(WRONG_TYPE, name)
    if not value:
        raise PresetValidationError(MISSING_REQUIRED, name)
    return _freeze(value, name)


def _check_input(name: str, value: object) -> object:
    if name == 'revision':
        return _revision_number(value, name)
    if name in TEXT_FIELDS:
        return _text(value, name)
    return _section(value, name)


@dataclass(frozen=True, kw_only=True)
class RenderPresetRevision:
    """Frozen CT-RND-001 revision: sections are deep-frozen read-only mappings; preset_fingerprint is request_hash of every other field."""

    preset_key: str
    revision: int
    visual_rhythm: Mapping[str, object]
    layout_rules: Mapping[str, object]
    thumbnail_overlay_style: Mapping[str, object]
    typography_karaoke_style: Mapping[str, object]
    hook_treatment: Mapping[str, object]
    mix_rules: Mapping[str, object]
    color_effect_rules: Mapping[str, object]
    output_profile_ref: str
    fallback_constraints: Mapping[str, object]
    compatibility_requirements: Mapping[str, object]
    preset_fingerprint: str

    def __post_init__(self) -> None:
        for name in INPUT_FIELDS:
            object.__setattr__(self, name, _check_input(name, getattr(self, name)))
        if not _SHA256_RE.fullmatch(_text(self.preset_fingerprint, FINGERPRINT_FIELD)):
            raise PresetValidationError(INVALID_VALUE, FINGERPRINT_FIELD)

    def __hash__(self) -> int:
        return hash((self.preset_key, self.revision, self.preset_fingerprint))

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> RenderPresetRevision:
        """Load a stored revision: all thirteen fields are required and preset_fingerprint must match."""
        if not isinstance(payload, Mapping):
            raise PresetValidationError(WRONG_TYPE, 'payload')
        preset = cls(**{name: payload.get(name) for name in (*INPUT_FIELDS, FINGERPRINT_FIELD)})
        verify_preset_fingerprint(preset)
        return preset


INPUT_FIELDS = tuple(item.name for item in fields(RenderPresetRevision) if item.name != FINGERPRINT_FIELD)


def _input_values(source: object) -> dict[str, object]:
    if isinstance(source, Mapping):
        return {name: source.get(name) for name in INPUT_FIELDS}
    return {name: getattr(source, name, None) for name in INPUT_FIELDS}


def compute_preset_fingerprint(source: object) -> str:
    """request_hash over every field except preset_fingerprint; source is a RenderPresetRevision or a mapping holding those fields."""
    basis = {name: _thaw(_check_input(name, value)) for name, value in _input_values(source).items()}
    try:
        return request_hash(basis)
    except ValueError as exc:
        raise PresetValidationError(INVALID_VALUE, FINGERPRINT_FIELD) from exc


def verify_preset_fingerprint(preset: RenderPresetRevision) -> None:
    """Raise PresetValidationError(preset_fingerprint_mismatch, preset_fingerprint) when the stored fingerprint differs from the content."""
    if preset.preset_fingerprint != compute_preset_fingerprint(preset):
        raise PresetValidationError(PRESET_FINGERPRINT_MISMATCH, FINGERPRINT_FIELD)


def build_preset_revision(payload: Mapping[str, object]) -> RenderPresetRevision:
    """Build a revision from the twelve input fields and compute preset_fingerprint; an incoming preset_fingerprint key is ignored."""
    if not isinstance(payload, Mapping):
        raise PresetValidationError(WRONG_TYPE, 'payload')
    values = {name: payload.get(name) for name in INPUT_FIELDS}
    return RenderPresetRevision(**values, preset_fingerprint=compute_preset_fingerprint(values))


@dataclass(frozen=True)
class PresetCatalog:
    """Immutable collection of verified revisions sorted by (preset_key, revision); add_revision returns a new catalog."""

    revisions: tuple[RenderPresetRevision, ...] = ()

    def __post_init__(self) -> None:
        items = tuple(self.revisions)
        if not all(isinstance(item, RenderPresetRevision) for item in items):
            raise PresetValidationError(WRONG_TYPE, 'revisions')
        for item in items:
            verify_preset_fingerprint(item)
        identities = [(item.preset_key, item.revision) for item in items]
        if len(set(identities)) != len(identities):
            raise PresetValidationError(DUPLICATE_REVISION, 'revisions')
        object.__setattr__(self, 'revisions', tuple(sorted(items, key=lambda item: (item.preset_key, item.revision))))

    def add_revision(self, preset: RenderPresetRevision) -> PresetCatalog:
        """Return a new catalog with preset added; an equal revision returns self, a different one with the same key and revision is rejected."""
        if not isinstance(preset, RenderPresetRevision):
            raise PresetValidationError(WRONG_TYPE, 'preset')
        for existing in self.revisions:
            if (existing.preset_key, existing.revision) == (preset.preset_key, preset.revision):
                if existing == preset:
                    return self
                raise PresetValidationError(DUPLICATE_REVISION, 'revision')
        return PresetCatalog(revisions=(*self.revisions, preset))


def resolve_preset(catalog: PresetCatalog, preset_key: str, revision: int | None = None) -> RenderPresetRevision:
    """Deterministic lookup: the exact revision when given, otherwise the highest revision of preset_key; raises PresetNotFoundError."""
    if revision is not None:
        _revision_number(revision, 'revision')
    matches = [item for item in catalog.revisions if item.preset_key == preset_key]
    if revision is not None:
        matches = [item for item in matches if item.revision == revision]
    if not matches:
        raise PresetNotFoundError(preset_key, revision)
    return max(matches, key=lambda item: item.revision)


def completeness_issue(catalog: PresetCatalog) -> str | None:
    """PRESET_COUNT_NOT_FIVE unless the catalog holds exactly REQUIRED_PRESET_COUNT distinct preset_key values, else None."""
    distinct = {item.preset_key for item in catalog.revisions}
    return None if len(distinct) == REQUIRED_PRESET_COUNT else PRESET_COUNT_NOT_FIVE


def is_complete(catalog: PresetCatalog) -> bool:
    return completeness_issue(catalog) is None
