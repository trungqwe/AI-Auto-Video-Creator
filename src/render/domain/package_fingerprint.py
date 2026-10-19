"""F-04: immutable RenderPackage fingerprint (CT-RND-002).

package_fingerprint is request_hash of every RenderPackageRecord field except package_fingerprint and render_package_id.
input_artifacts are sorted by (artifact_version_id, sha256, size_bytes, media_type) and language_validation_refs as strings
before hashing; timeline.segments and every other sequence keep their order; mapping key order never matters (JCS).
Pure domain: no I/O, no clock.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain.package_contract import InputArtifactRecord, RenderPackageRecord

WRONG_TYPE = 'wrong_type'
INVALID_VALUE = 'invalid_value'
PACKAGE_FINGERPRINT_MISMATCH = 'package_fingerprint_mismatch'
FINGERPRINT_FIELD = 'package_fingerprint'
EXCLUDED_FIELDS = (FINGERPRINT_FIELD, 'render_package_id')
HASHED_FIELDS = tuple(item.name for item in fields(RenderPackageRecord) if item.name not in EXCLUDED_FIELDS)


class PackageFingerprintError(ValueError):
    """A package broke CT-RND-002 fingerprinting; `code` is the stable reason and `field` the offending field name."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f'{code}:{field}')
        self.code = code
        self.field = field


def _thaw(value: object) -> object:
    """Read-only mappings become dicts and tuples become lists so the canonicalizer accepts them."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _artifact_key(item: InputArtifactRecord) -> tuple:
    return (item.artifact_version_id, item.sha256, item.size_bytes, item.media_type)


def _artifacts_basis(items: object) -> list[dict[str, object]]:
    if not isinstance(items, (list, tuple)) or not all(isinstance(item, InputArtifactRecord) for item in items):
        raise PackageFingerprintError(WRONG_TYPE, 'input_artifacts')
    try:
        ordered = sorted(items, key=_artifact_key)
    except TypeError as exc:
        raise PackageFingerprintError(WRONG_TYPE, 'input_artifacts') from exc
    return [{part.name: getattr(item, part.name) for part in fields(InputArtifactRecord)} for item in ordered]


def _refs_basis(items: object) -> list[str]:
    if not isinstance(items, (list, tuple)) or not all(isinstance(item, str) for item in items):
        raise PackageFingerprintError(WRONG_TYPE, 'language_validation_refs')
    return sorted(items)


def _basis(record: object) -> dict[str, object]:
    if not isinstance(record, RenderPackageRecord):
        raise PackageFingerprintError(WRONG_TYPE, 'record')
    basis = {name: _thaw(getattr(record, name)) for name in HASHED_FIELDS}
    basis['input_artifacts'] = _artifacts_basis(record.input_artifacts)
    basis['language_validation_refs'] = _refs_basis(record.language_validation_refs)
    return basis


def compute_package_fingerprint(record: RenderPackageRecord) -> str:
    """request_hash over every field except package_fingerprint and render_package_id; raises PackageFingerprintError on bad input."""
    basis = _basis(record)
    try:
        return request_hash(basis)
    except ValueError as exc:
        raise PackageFingerprintError(INVALID_VALUE, FINGERPRINT_FIELD) from exc


def verify_package_fingerprint(record: RenderPackageRecord) -> None:
    """Raise PackageFingerprintError(package_fingerprint_mismatch, package_fingerprint) when the stored fingerprint differs from the content."""
    expected = compute_package_fingerprint(record)
    if record.package_fingerprint != expected:
        raise PackageFingerprintError(PACKAGE_FINGERPRINT_MISMATCH, FINGERPRINT_FIELD)
