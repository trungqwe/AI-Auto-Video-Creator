"""CollectedDocumentPackage and CollectedDocumentResolution boundary checks for module B (CT-SRC-006, CT-CNT-001).

Constants mirror BINDING-A-B-COLLECTED-DOCUMENT; unknown additive fields are ignored.
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
UNSUPPORTED_BINDING_VERSION = 'unsupported_binding_version'
BINDING_VERSION = '1.0.0'
SUPPORTED_BINDING_MAJOR = 1

PACKAGE_REQUIRED = MappingProxyType({
    'collected_document_id': 'string',
    'source_id': 'string',
    'source_revision': 'integer',
    'collection_run_id': 'string',
    'requested_url': 'string',
    'final_url': 'string',
    'fetched_at': 'datetime',
    'http_observation': 'object',
    'extraction_disposition': 'string',
    'extractor_version': 'string',
    'provenance_chain': 'array',
    'warnings': 'array',
})
PACKAGE_OPTIONAL = MappingProxyType({
    'canonical_url_candidate': 'string',
    'published_at_candidate': 'datetime',
    'raw_snapshot_ref': 'string',
    'extracted_content_candidate': 'object',
    'content_eligibility': 'string',
    'eligibility_reason': 'string',
    'content_fingerprints': 'object',
    'media_discoveries': 'array',
})
PACKAGE_ENUM = MappingProxyType({'content_eligibility': ('candidate', 'incomplete')})
PACKAGE_ITEMS = MappingProxyType({'provenance_chain': 'object', 'media_discoveries': 'object'})
RESOLUTION_REQUIRED = MappingProxyType({
    'collected_document_id': 'string',
    'dedup_policy_revision': 'string',
    'disposition': 'string',
})
RESOLUTION_OPTIONAL = MappingProxyType({'article_id': 'string', 'article_revision_id': 'string'})
RESOLUTION_ENUM = MappingProxyType({
    'disposition': (
        'NEW_ARTICLE',
        'NEW_REVISION',
        'DUPLICATE_MEDIA_ONLY',
        'DUPLICATE_NO_NEW_VALUE',
        'REJECTED_INCOMPLETE',
    ),
})
RESOLUTION_ITEMS = MappingProxyType({})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


_RFC3339_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})')
_SEMVER_RE = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')


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


def _supports_binding_version(payload: Mapping) -> bool:
    if 'binding_version' not in payload:
        return True
    version = payload['binding_version']
    match = _SEMVER_RE.fullmatch(version) if isinstance(version, str) else None
    return match is not None and int(match.group(1)) == SUPPORTED_BINDING_MAJOR


def _validate(payload: object, required: Mapping, optional: Mapping, enum: Mapping, items: Mapping) -> list[ValidationIssue]:
    if not isinstance(payload, Mapping):
        return [ValidationIssue(WRONG_TYPE, '$')]
    if not _supports_binding_version(payload):
        return [ValidationIssue(UNSUPPORTED_BINDING_VERSION, 'binding_version')]
    issues: list[ValidationIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        if name not in payload:
            if name in required:
                issues.append(ValidationIssue(MISSING_REQUIRED, name))
            continue
        value = payload[name]
        if value is None:
            if name in required:
                issues.append(ValidationIssue(WRONG_TYPE, name))
            continue
        if not _matches_type(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in items and any(not _matches_type(item, items[name]) for item in value):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in enum and value not in enum[name]:
            issues.append(ValidationIssue(ENUM_VIOLATION, name))
    return issues


def validate_collected_document_package(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a CollectedDocumentPackage payload (CT-SRC-006); empty list means valid."""
    return _validate(payload, PACKAGE_REQUIRED, PACKAGE_OPTIONAL, PACKAGE_ENUM, PACKAGE_ITEMS)


def validate_collected_document_resolution(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a CollectedDocumentResolution payload (CT-CNT-001); empty list means valid."""
    return _validate(payload, RESOLUTION_REQUIRED, RESOLUTION_OPTIONAL, RESOLUTION_ENUM, RESOLUTION_ITEMS)
