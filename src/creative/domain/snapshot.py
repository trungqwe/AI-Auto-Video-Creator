"""ProductionSnapshot immutable domain value and boundary validator (CT-AI-001, INV-004, INV-005).

Constants mirror BINDING-B-D-PRODUCTION-SNAPSHOT; unknown additive fields are ignored.
Pure domain: no I/O, no clock, no id generation; snapshot_id, snapshot_timestamp, content ref types and
eligibility_reason are caller input and the module has no hidden default for them.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
INPUT_NOT_READY = 'INPUT_NOT_READY'
NOT_ELIGIBLE = 'NOT_ELIGIBLE'
BINDING_VERSION = '1.0.0'
REF_FIELDS = ('ref_type', 'ref_id', 'revision_id')

PRODUCTION_MODES = ('single_article', 'multi_article_event', 'from_then_to_now')
SNAPSHOT_REQUIRED = MappingProxyType({
    'snapshot_id': 'string',
    'production_mode': 'string',
    'source_refs': 'array',
    'index_revision_refs': 'array',
    'configuration_revision_refs': 'array',
    'source_set_fingerprint': 'sha256',
    'configuration_bundle_fingerprint': 'sha256',
    'eligibility_reason': 'string',
    'snapshot_timestamp': 'datetime',
})
SNAPSHOT_OPTIONAL = MappingProxyType({
    'batch_ref': 'string',
    'video_job_ref': 'string',
    'recent_variant_exclusions': 'array',
})
SNAPSHOT_ENUM = MappingProxyType({'production_mode': PRODUCTION_MODES})
SNAPSHOT_ITEMS = MappingProxyType({
    'source_refs': 'object',
    'index_revision_refs': 'object',
    'configuration_revision_refs': 'object',
})

_RFC3339_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})')
_SHA256_RE = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_RE.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, dict)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'sha256':
        return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
    if type_name == 'datetime':
        return _is_rfc3339(value)
    return False


def validate_production_snapshot(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a ProductionSnapshot payload (CT-AI-001); empty list means valid."""
    if not isinstance(payload, Mapping):
        return [ValidationIssue(WRONG_TYPE, '$')]
    issues: list[ValidationIssue] = []
    for name, type_name in (*SNAPSHOT_REQUIRED.items(), *SNAPSHOT_OPTIONAL.items()):
        if name not in payload:
            if name in SNAPSHOT_REQUIRED:
                issues.append(ValidationIssue(MISSING_REQUIRED, name))
            continue
        value = payload[name]
        if value is None:
            if name in SNAPSHOT_REQUIRED:
                issues.append(ValidationIssue(WRONG_TYPE, name))
            continue
        if not matches_type(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in SNAPSHOT_ITEMS and any(not matches_type(item, SNAPSHOT_ITEMS[name]) for item in value):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in SNAPSHOT_ENUM and value not in SNAPSHOT_ENUM[name]:
            issues.append(ValidationIssue(ENUM_VIOLATION, name))
    return issues


class SnapshotRejected(Exception):
    """The inputs cannot produce a snapshot: `code` is INPUT_NOT_READY or NOT_ELIGIBLE, `reason` is the stable machine reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class ProductionSnapshot:
    """CT-AI-001 value pinning exact revisions; refs are sorted tuples of read-only mappings, so later source or config changes never reach it."""

    snapshot_id: str
    production_mode: str
    source_refs: tuple[Mapping[str, str], ...]
    index_revision_refs: tuple[Mapping[str, str], ...]
    configuration_revision_refs: tuple[Mapping[str, str], ...]
    source_set_fingerprint: str
    configuration_bundle_fingerprint: str
    eligibility_reason: str
    snapshot_timestamp: str
    batch_ref: str | None = None
    video_job_ref: str | None = None
    recent_variant_exclusions: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Return the binding payload (plain dict/list); batch_ref and video_job_ref are omitted when None."""
        payload: dict[str, object] = {
            'snapshot_id': self.snapshot_id,
            'production_mode': self.production_mode,
            'source_refs': [dict(ref) for ref in self.source_refs],
            'index_revision_refs': [dict(ref) for ref in self.index_revision_refs],
            'configuration_revision_refs': [dict(ref) for ref in self.configuration_revision_refs],
            'source_set_fingerprint': self.source_set_fingerprint,
            'configuration_bundle_fingerprint': self.configuration_bundle_fingerprint,
            'eligibility_reason': self.eligibility_reason,
            'snapshot_timestamp': self.snapshot_timestamp,
            'recent_variant_exclusions': list(self.recent_variant_exclusions),
        }
        if self.batch_ref is not None:
            payload['batch_ref'] = self.batch_ref
        if self.video_job_ref is not None:
            payload['video_job_ref'] = self.video_job_ref
        return payload


def fingerprint_refs(refs: Iterable[Mapping[str, str]]) -> str:
    """Return request_hash (RFC 8785 SHA-256 hex) of the refs sorted by (ref_type, ref_id, revision_id); input order never matters."""
    ordered = sorted(
        ({name: ref[name] for name in REF_FIELDS} for ref in refs),
        key=lambda ref: tuple(ref[name] for name in REF_FIELDS),
    )
    return request_hash(ordered)


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _optional_text(name: str, value: object) -> str | None:
    return None if value is None else _require_text(name, value)


def _as_list(name: str, values: object) -> list:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        raise ValueError(f'{name} must be an iterable, not a string or mapping')
    return list(values)


def _pin_refs(name: str, refs: list) -> tuple[Mapping[str, str], ...]:
    """Return refs as a sorted, de-duplicated tuple of read-only mappings holding only REF_FIELDS."""
    pinned: set[tuple[str, str, str]] = set()
    for ref in refs:
        if not isinstance(ref, Mapping):
            raise ValueError(f'{name} items must be mappings')
        ref_type = _require_text(f'{name}.ref_type', ref.get('ref_type'))
        ref_id = _require_text(f'{name}.ref_id', ref.get('ref_id'))
        revision_id = ref.get('revision_id')
        if not isinstance(revision_id, str) or not revision_id:
            raise SnapshotRejected(INPUT_NOT_READY, 'missing_revision_id')
        pinned.add((ref_type, ref_id, revision_id))
    return tuple(MappingProxyType(dict(zip(REF_FIELDS, item))) for item in sorted(pinned))


def build_production_snapshot(
    *,
    snapshot_id: str,
    production_mode: str,
    source_refs: Iterable[Mapping[str, object]],
    index_revision_refs: Iterable[Mapping[str, object]],
    configuration_revision_refs: Iterable[Mapping[str, object]],
    content_ref_types: Iterable[str],
    eligibility_reason: str | None,
    snapshot_timestamp: str,
    batch_ref: str | None = None,
    video_job_ref: str | None = None,
    recent_variant_exclusions: Iterable[str] = (),
) -> ProductionSnapshot:
    """Build the immutable ProductionSnapshot (CT-AI-001) from exact revision refs.

    Raises SnapshotRejected(INPUT_NOT_READY, reason) for missing policy or revision input,
    SnapshotRejected(NOT_ELIGIBLE, 'ref_type_not_content') when a source ref is outside content_ref_types
    (dedup observations never create a snapshot), ValueError for malformed arguments.
    """
    if production_mode not in PRODUCTION_MODES:
        raise ValueError(f'production_mode must be one of {PRODUCTION_MODES!r}')
    _require_text('snapshot_id', snapshot_id)
    if not matches_type(snapshot_timestamp, 'datetime'):
        raise ValueError('snapshot_timestamp must be an RFC 3339 datetime string with offset')
    sources = _as_list('source_refs', source_refs)
    indexes = _as_list('index_revision_refs', index_revision_refs)
    configs = _as_list('configuration_revision_refs', configuration_revision_refs)
    exclusions = {
        _require_text('recent_variant_exclusions item', item)
        for item in _as_list('recent_variant_exclusions', recent_variant_exclusions)
    }
    content_types = {_require_text('content_ref_types item', item) for item in _as_list('content_ref_types', content_ref_types)}
    batch = _optional_text('batch_ref', batch_ref)
    job = _optional_text('video_job_ref', video_job_ref)
    if not content_types:
        raise SnapshotRejected(INPUT_NOT_READY, 'missing_content_ref_types')
    if eligibility_reason is None or eligibility_reason == '':
        raise SnapshotRejected(INPUT_NOT_READY, 'missing_eligibility_reason')
    _require_text('eligibility_reason', eligibility_reason)
    for ref in sources:
        ref_type = ref.get('ref_type') if isinstance(ref, Mapping) else None
        if isinstance(ref, Mapping) and not (isinstance(ref_type, str) and ref_type in content_types):
            raise SnapshotRejected(NOT_ELIGIBLE, 'ref_type_not_content')
    pinned_sources = _pin_refs('source_refs', sources)
    if not pinned_sources:
        raise SnapshotRejected(INPUT_NOT_READY, 'missing_source_refs')
    pinned_indexes = _pin_refs('index_revision_refs', indexes)
    pinned_configs = _pin_refs('configuration_revision_refs', configs)
    if not pinned_configs:
        raise SnapshotRejected(INPUT_NOT_READY, 'missing_configuration_refs')
    snapshot = ProductionSnapshot(
        snapshot_id=snapshot_id,
        production_mode=production_mode,
        source_refs=pinned_sources,
        index_revision_refs=pinned_indexes,
        configuration_revision_refs=pinned_configs,
        source_set_fingerprint=fingerprint_refs(pinned_sources),
        configuration_bundle_fingerprint=fingerprint_refs(pinned_configs),
        eligibility_reason=eligibility_reason,
        snapshot_timestamp=snapshot_timestamp,
        batch_ref=batch,
        video_job_ref=job,
        recent_variant_exclusions=tuple(sorted(exclusions)),
    )
    issues = validate_production_snapshot(snapshot.to_payload())
    if issues:
        raise ValueError(f'snapshot failed boundary validation: {issues!r}')
    return snapshot
