"""CollectedDocumentPackage validation in two layers (CT-SRC-006).

Layer 1 checks top-level fields against BINDING-A-B-COLLECTED-DOCUMENT 1.0.0.
Layer 2 decides content eligibility under a caller-supplied ExtractionPolicy revision.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
VALIDATION_ERROR = 'VALIDATION_ERROR'
INPUT_NOT_READY = 'INPUT_NOT_READY'
ELIGIBILITY_CANDIDATE = 'candidate'
ELIGIBILITY_INCOMPLETE = 'incomplete'
REASON_MISSING_POLICY = 'missing_extraction_policy'
REASON_MISSING_SOURCE_KIND_POLICY = 'missing_source_kind_policy'
REASON_MISSING_CONTENT = 'missing_extracted_content'
REASON_EMPTY_TEXT = 'empty_main_text'
REASON_MISSING_TITLE = 'missing_required_title'

_RFC3339_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})')


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool
    enum: tuple[str, ...] | None = None
    items: str | None = None


PACKAGE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec('collected_document_id', 'string', True),
    FieldSpec('source_id', 'string', True),
    FieldSpec('source_revision', 'integer', True),
    FieldSpec('collection_run_id', 'string', True),
    FieldSpec('requested_url', 'string', True),
    FieldSpec('final_url', 'string', True),
    FieldSpec('fetched_at', 'datetime', True),
    FieldSpec('http_observation', 'object', True),
    FieldSpec('extraction_disposition', 'string', True),
    FieldSpec('extractor_version', 'string', True),
    FieldSpec('provenance_chain', 'array', True, items='object'),
    FieldSpec('warnings', 'array', True),
    FieldSpec('canonical_url_candidate', 'string', False),
    FieldSpec('published_at_candidate', 'datetime', False),
    FieldSpec('raw_snapshot_ref', 'string', False),
    FieldSpec('extracted_content_candidate', 'object', False),
    FieldSpec('content_eligibility', 'string', False, enum=('candidate', 'incomplete')),
    FieldSpec('eligibility_reason', 'string', False),
    FieldSpec('content_fingerprints', 'object', False),
    FieldSpec('media_discoveries', 'array', False, items='object'),
)
# extraction_disposition stays free text (IMPL-PLAN-A §2(c)); layer 1 only rejects blank strings.
NON_EMPTY_STRING_FIELDS = frozenset({'extraction_disposition'})


@dataclass(frozen=True)
class SchemaError:
    code: str
    field: str


class PackageValidationError(ValueError):
    code = VALIDATION_ERROR

    def __init__(self, errors: tuple[SchemaError, ...]) -> None:
        super().__init__(VALIDATION_ERROR)
        self.errors = errors


@dataclass(frozen=True)
class ExtractionPolicy:
    revision: str
    title_required_by_source_kind: Mapping[str, bool]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError('ExtractionPolicy.revision must be a non-empty string')
        rules = dict(self.title_required_by_source_kind)
        if any(not isinstance(kind, str) or not kind or not isinstance(flag, bool) for kind, flag in rules.items()):
            raise ValueError('title_required_by_source_kind must map non-empty source kinds to bool')
        object.__setattr__(self, 'title_required_by_source_kind', MappingProxyType(rules))


@dataclass(frozen=True)
class ContentAssessment:
    outcome: str
    reason: str | None
    policy_revision: str | None


def _is_rfc3339(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_RE.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, dict)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'datetime':
        return _is_rfc3339(value)
    return False


def _field_error(spec: FieldSpec, value: object) -> str | None:
    if not _matches_type(value, spec.type):
        return WRONG_TYPE
    if spec.items is not None and any(not _matches_type(item, spec.items) for item in value):
        return WRONG_TYPE
    if spec.name in NON_EMPTY_STRING_FIELDS and not value.strip():
        return WRONG_TYPE
    if spec.enum is not None and value not in spec.enum:
        return ENUM_VIOLATION
    return None


def validate_package_schema(payload: object) -> tuple[SchemaError, ...]:
    """Layer 1: top-level presence, type and enum checks; unknown additive fields are tolerated."""
    if not isinstance(payload, Mapping):
        return (SchemaError(WRONG_TYPE, '$'),)
    errors: list[SchemaError] = []
    for spec in PACKAGE_FIELDS:
        if spec.name not in payload:
            if spec.required:
                errors.append(SchemaError(MISSING_REQUIRED, spec.name))
            continue
        value = payload[spec.name]
        if value is None:
            if spec.required:
                errors.append(SchemaError(WRONG_TYPE, spec.name))
            continue
        code = _field_error(spec, value)
        if code is not None:
            errors.append(SchemaError(code, spec.name))
    return tuple(errors)


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def assess_content_eligibility(
    payload: object, source_kind: str, policy: ExtractionPolicy | None
) -> ContentAssessment:
    """Layer 2: content eligibility under an extraction policy revision; schema errors raise first."""
    errors = validate_package_schema(payload)
    if errors:
        raise PackageValidationError(errors)
    if policy is None:
        return ContentAssessment(INPUT_NOT_READY, REASON_MISSING_POLICY, None)
    title_required = policy.title_required_by_source_kind.get(source_kind)
    if title_required is None:
        return ContentAssessment(INPUT_NOT_READY, REASON_MISSING_SOURCE_KIND_POLICY, policy.revision)
    content = payload.get('extracted_content_candidate')
    if content is None:
        return ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_MISSING_CONTENT, policy.revision)
    if not _non_empty_text(content.get('text')):
        return ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_EMPTY_TEXT, policy.revision)
    if title_required and not _non_empty_text(content.get('title')):
        return ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_MISSING_TITLE, policy.revision)
    return ContentAssessment(ELIGIBILITY_CANDIDATE, None, policy.revision)
