"""Repository ports for source ingestion (A-08, IMPL-PLAN-A section 4).

Protocols only. Writes run inside a controlplane IUnitOfWork; the in-memory implementation is
source_ingestion.adapters.memory and PostgreSQL persistence waits for CONV-A-01.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from source_ingestion.domain.checkpoint import CollectionCheckpoint
from source_ingestion.domain.collection_run import CollectionRun
from source_ingestion.domain.source import Source
from source_ingestion.domain.source_candidate import IdentityMatch, SourceCandidate


class DuplicateRecordError(ValueError):
    """A unique key already holds a record."""


class DuplicateSourceIdentityError(DuplicateRecordError):
    """Canonical locator already registered in the workspace, tombstones included."""


class DuplicatePackageError(DuplicateRecordError):
    """Package with same source, canonical locator and fingerprint already exists."""


class DuplicateReceiptError(DuplicateRecordError):
    """Idempotency key already holds a receipt in this workspace."""


class RecordNotFoundError(LookupError):
    """Update targets a record that was never added."""


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string')


@dataclass(frozen=True)
class PackageRecord:
    source_id: str
    canonical_locator: str
    observation_fingerprint: str
    collection_run_id: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _require_text(self.source_id, 'source_id')
        _require_text(self.canonical_locator, 'canonical_locator')
        _require_text(self.observation_fingerprint, 'observation_fingerprint')
        _require_text(self.collection_run_id, 'collection_run_id')
        if not isinstance(self.payload, Mapping):
            raise ValueError('payload must be a mapping')
        object.__setattr__(self, 'payload', MappingProxyType(dict(self.payload)))

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source_id, self.canonical_locator, self.observation_fingerprint)


@dataclass(frozen=True)
class CommandReceipt:
    workspace_id: str
    idempotency_key: str
    request_hash: str
    aggregate_ref: str
    aggregate_revision: int

    def __post_init__(self) -> None:
        _require_text(self.workspace_id, 'workspace_id')
        _require_text(self.idempotency_key, 'idempotency_key')
        _require_text(self.request_hash, 'request_hash')
        _require_text(self.aggregate_ref, 'aggregate_ref')
        if type(self.aggregate_revision) is not int or self.aggregate_revision < 1:
            raise ValueError('aggregate_revision must be an int >= 1')


@runtime_checkable
class SourceRepository(Protocol):
    """Source aggregate store; canonical identity is unique per workspace and tombstones keep it."""

    def get(self, workspace_id: str, source_id: str) -> Source | None:
        ...

    def list_sources(self, workspace_id: str) -> tuple[Source, ...]:
        ...

    def resolve_identity(self, workspace_id: str, canonical_locator: str) -> IdentityMatch:
        ...

    def add(self, source: Source) -> None:
        ...

    def save(self, source: Source) -> None:
        ...


@runtime_checkable
class SourceCandidateRepository(Protocol):
    def get(self, workspace_id: str, candidate_id: str) -> SourceCandidate | None:
        ...

    def find_by_canonical_locator(self, workspace_id: str, canonical_locator: str) -> tuple[SourceCandidate, ...]:
        ...

    def add(self, candidate: SourceCandidate) -> None:
        ...

    def save(self, candidate: SourceCandidate) -> None:
        ...


@runtime_checkable
class CollectionRunRepository(Protocol):
    """Periodic key (workspace, source, business_date, PERIODIC) is unique and excludes policy revision (A-RULE-004)."""

    def get(self, run_id: str) -> CollectionRun | None:
        ...

    def get_periodic(self, workspace_id: str, source_id: str, business_date: datetime.date) -> CollectionRun | None:
        ...

    def list_by_source(self, workspace_id: str, source_id: str) -> tuple[CollectionRun, ...]:
        ...

    def add(self, run: CollectionRun) -> None:
        ...

    def save(self, run: CollectionRun) -> None:
        ...


@runtime_checkable
class PackageRepository(Protocol):
    """Unique by source, canonical locator and observation fingerprint."""

    def get(self, source_id: str, canonical_locator: str, observation_fingerprint: str) -> PackageRecord | None:
        ...

    def list_by_run(self, collection_run_id: str) -> tuple[PackageRecord, ...]:
        ...

    def add(self, record: PackageRecord) -> None:
        ...


@runtime_checkable
class CheckpointRepository(Protocol):
    def get_latest(self, source_id: str) -> CollectionCheckpoint | None:
        ...

    def advance(self, proposed: CollectionCheckpoint, durable_item_ids: Iterable[str]) -> CollectionCheckpoint:
        """Delegates to advance_checkpoint; CheckpointRejected keeps the current checkpoint."""
        ...


@runtime_checkable
class ReceiptStore(Protocol):
    def get(self, workspace_id: str, idempotency_key: str) -> CommandReceipt | None:
        ...

    def put(self, receipt: CommandReceipt) -> None:
        ...


__all__ = [
    'CheckpointRepository',
    'CollectionRunRepository',
    'CommandReceipt',
    'DuplicatePackageError',
    'DuplicateReceiptError',
    'DuplicateRecordError',
    'DuplicateSourceIdentityError',
    'PackageRecord',
    'PackageRepository',
    'ReceiptStore',
    'RecordNotFoundError',
    'SourceCandidateRepository',
    'SourceRepository',
]
