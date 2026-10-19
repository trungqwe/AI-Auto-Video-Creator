"""F-16: storage port of F, the append-only RenderRepository Protocol (CT-EVT-002, CT-EVT-003, CONV-F-01); pure, no I/O, no clock.

A stored record is never overwritten or deleted: append adds revision latest + 1 and every earlier revision stays readable.
package_fingerprint, render_attempt_id and output_artifact_ref are unique; the in-memory adapter enforces it and the PostgreSQL adapter of CONV-F-01 must too.

coveredIds: CT-EVT-002, CT-EVT-003
"""
from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import QualityReport
from render.domain.render_attempt import RenderAttempt

KIND_PACKAGE = 'render_package'
KIND_ATTEMPT = 'render_attempt'
KIND_QUALITY_REPORT = 'quality_report'

RECORD_TYPES = MappingProxyType({
    KIND_PACKAGE: RenderPackageRecord,
    KIND_ATTEMPT: RenderAttempt,
    KIND_QUALITY_REPORT: QualityReport,
})


class DuplicateRecordError(ValueError):
    """A unique value (package_fingerprint, render_attempt_id or output_artifact_ref) is already stored."""


class ImmutableFieldError(ValueError):
    """A new revision of a stored record tried to change an identity field."""


@dataclasses.dataclass(frozen=True)
class StoredRecord:
    kind: str
    key: str
    revision: int
    record: object


@runtime_checkable
class RenderRepository(Protocol):
    def append(self, kind: str, key: str, revision: int, record: object) -> StoredRecord:
        """Append revision latest + 1 for (kind, key); never overwrites or deletes an earlier revision."""
        ...

    def latest(self, kind: str, key: str) -> StoredRecord | None:
        """Return the newest stored revision or None."""
        ...

    def revisions(self, kind: str, key: str) -> tuple[StoredRecord, ...]:
        """Return every stored revision in ascending order."""
        ...


__all__ = [
    'DuplicateRecordError',
    'ImmutableFieldError',
    'KIND_ATTEMPT',
    'KIND_PACKAGE',
    'KIND_QUALITY_REPORT',
    'RECORD_TYPES',
    'RenderRepository',
    'StoredRecord',
]
