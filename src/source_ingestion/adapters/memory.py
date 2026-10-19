"""In-memory unit of work, repositories, outbox and partner fakes (A-08).

Test and fixture use only; PostgreSQL persistence waits for CONV-A-01. The unit of work implements
controlplane IUnitOfWork and the outbox implements controlplane IOutboxWriter.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security import SecretHandle
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.orchestration import ExecutionGrant

from source_ingestion.domain.checkpoint import (
    CollectionCheckpoint,
    advance_checkpoint,
)
from source_ingestion.domain.collection_run import (
    CollectionPurpose,
    CollectionRun,
    ensure_periodic_unique,
)
from source_ingestion.domain.package import (
    PackageValidationError,
    validate_package_schema,
)
from source_ingestion.domain.source import Source, SourceStatus
from source_ingestion.domain.source_candidate import (
    IdentityMatch,
    IdentityMatchKind,
    SourceCandidate,
    NO_MATCH,
)
from source_ingestion.ports.partners import (
    DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS,
    DECLARE_ARTIFACT_VERSION_RESULT_FIELDS,
    PolicyRevisionRef,
)
from source_ingestion.ports.repositories import (
    CommandReceipt,
    DuplicatePackageError,
    DuplicateReceiptError,
    DuplicateRecordError,
    DuplicateSourceIdentityError,
    PackageRecord,
    RecordNotFoundError,
)


class TransactionNotActiveError(RuntimeError):
    pass


class TransactionAlreadyActiveError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class OutboxRecord:
    event_id: str
    event_type: str
    aggregate_id: str
    payload: Mapping[str, Any]
    deduplication_id: str


class _Table:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow
        self._rows: dict[Any, Any] = {}

    def _write(self) -> None:
        self._uow._require_active()


class InMemoryOutboxWriter(_Table, IOutboxWriter):
    def append_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        deduplication_id: str,
    ) -> str:
        self._write()
        for name, value in (
            ('event_type', event_type),
            ('aggregate_id', aggregate_id),
            ('deduplication_id', deduplication_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')
        if not isinstance(payload, Mapping):
            raise ValueError('payload must be a mapping')
        if deduplication_id in self._rows:
            return self._rows[deduplication_id].event_id
        event_id = 'evt-' + hashlib.sha256(deduplication_id.encode('utf-8')).hexdigest()[:32]
        self._rows[deduplication_id] = OutboxRecord(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload=MappingProxyType(dict(payload)),
            deduplication_id=deduplication_id,
        )
        return event_id

    def records(self) -> tuple[OutboxRecord, ...]:
        return tuple(self._rows.values())


class InMemorySourceRepository(_Table):
    def get(self, workspace_id: str, source_id: str) -> Source | None:
        source = self._rows.get(source_id)
        if source is not None and source.workspace_id == workspace_id:
            return source
        return None

    def list_sources(self, workspace_id: str) -> tuple[Source, ...]:
        return tuple(s for s in self._rows.values() if s.workspace_id == workspace_id)

    def _by_locator(self, workspace_id: str, canonical_locator: str) -> Source | None:
        for s in self._rows.values():
            if s.workspace_id == workspace_id and s.canonical_locator == canonical_locator:
                return s
        return None

    def resolve_identity(self, workspace_id: str, canonical_locator: str) -> IdentityMatch:
        source = self._by_locator(workspace_id, canonical_locator)
        if source is None:
            return NO_MATCH
        if source.status is SourceStatus.REMOVED_TOMBSTONE:
            return IdentityMatch(IdentityMatchKind.TOMBSTONE, source.source_id)
        return IdentityMatch(IdentityMatchKind.EXISTING_SOURCE, source.source_id)

    def add(self, source: Source) -> None:
        self._write()
        if source.source_id in self._rows or self._by_locator(source.workspace_id, source.canonical_locator) is not None:
            raise DuplicateSourceIdentityError(source.canonical_locator)
        self._rows[source.source_id] = source

    def save(self, source: Source) -> None:
        self._write()
        stored = self._rows.get(source.source_id)
        if stored is None or stored.workspace_id != source.workspace_id:
            raise RecordNotFoundError(source.source_id)
        if source.canonical_locator != stored.canonical_locator:
            raise ValueError('canonical_locator is immutable')
        if source.revision != stored.revision + 1:
            raise RevisionConflictError(stored.revision)
        self._rows[source.source_id] = source


class InMemorySourceCandidateRepository(_Table):
    def get(self, workspace_id: str, candidate_id: str) -> SourceCandidate | None:
        cand = self._rows.get(candidate_id)
        if cand is not None and cand.workspace_id == workspace_id:
            return cand
        return None

    def find_by_canonical_locator(self, workspace_id: str, canonical_locator: str) -> tuple[SourceCandidate, ...]:
        return tuple(
            c for c in self._rows.values()
            if c.workspace_id == workspace_id and c.canonical_locator == canonical_locator
        )

    def add(self, candidate: SourceCandidate) -> None:
        self._write()
        if candidate.candidate_id in self._rows:
            raise DuplicateRecordError(candidate.candidate_id)
        self._rows[candidate.candidate_id] = candidate

    def save(self, candidate: SourceCandidate) -> None:
        self._write()
        stored = self._rows.get(candidate.candidate_id)
        if stored is None or stored.workspace_id != candidate.workspace_id:
            raise RecordNotFoundError(candidate.candidate_id)
        if candidate.revision != stored.revision + 1:
            raise RevisionConflictError(stored.revision)
        self._rows[candidate.candidate_id] = candidate


class InMemoryCollectionRunRepository(_Table):
    def get(self, run_id: str) -> CollectionRun | None:
        return self._rows.get(run_id)

    def get_periodic(self, workspace_id: str, source_id: str, business_date: datetime.date) -> CollectionRun | None:
        target_key = (workspace_id, source_id, business_date, CollectionPurpose.PERIODIC)
        for run in self._rows.values():
            if run.unique_key == target_key:
                return run
        return None

    def list_by_source(self, workspace_id: str, source_id: str) -> tuple[CollectionRun, ...]:
        return tuple(
            r for r in self._rows.values()
            if r.workspace_id == workspace_id and r.source_id == source_id
        )

    def add(self, run: CollectionRun) -> None:
        self._write()
        if run.run_id in self._rows:
            raise DuplicateRecordError(run.run_id)
        ensure_periodic_unique(self._rows.values(), run)
        self._rows[run.run_id] = run

    def save(self, run: CollectionRun) -> None:
        self._write()
        stored = self._rows.get(run.run_id)
        if stored is None:
            raise RecordNotFoundError(run.run_id)
        if (run.workspace_id, run.source_id, run.business_date, run.purpose) != (
            stored.workspace_id, stored.source_id, stored.business_date, stored.purpose
        ):
            raise ValueError('collection run key fields are immutable')
        self._rows[run.run_id] = run


class InMemoryPackageRepository(_Table):
    def get(self, source_id: str, canonical_locator: str, observation_fingerprint: str) -> PackageRecord | None:
        return self._rows.get((source_id, canonical_locator, observation_fingerprint))

    def list_by_run(self, collection_run_id: str) -> tuple[PackageRecord, ...]:
        return tuple(p for p in self._rows.values() if p.collection_run_id == collection_run_id)

    def add(self, record: PackageRecord) -> None:
        self._write()
        if record.identity in self._rows:
            raise DuplicatePackageError(repr(record.identity))
        self._rows[record.identity] = record


class InMemoryCheckpointRepository(_Table):
    def get_latest(self, source_id: str) -> CollectionCheckpoint | None:
        return self._rows.get(source_id)

    def advance(self, proposed: CollectionCheckpoint, durable_item_ids: Iterable[str]) -> CollectionCheckpoint:
        self._write()
        accepted = advance_checkpoint(self._rows.get(proposed.source_id), durable_item_ids, proposed)
        self._rows[accepted.source_id] = accepted
        return accepted


class InMemoryReceiptStore(_Table):
    def get(self, workspace_id: str, idempotency_key: str) -> CommandReceipt | None:
        return self._rows.get((workspace_id, idempotency_key))

    def put(self, receipt: CommandReceipt) -> None:
        self._write()
        key = (receipt.workspace_id, receipt.idempotency_key)
        if key in self._rows:
            raise DuplicateReceiptError(receipt.idempotency_key)
        self._rows[key] = receipt


class InMemoryUnitOfWork(IUnitOfWork):
    """One instance is one in-memory store; leaving the context without commit() rolls back."""

    def __init__(self) -> None:
        self._snapshot: tuple[dict, ...] | None = None
        self.sources = InMemorySourceRepository(self)
        self.candidates = InMemorySourceCandidateRepository(self)
        self.runs = InMemoryCollectionRunRepository(self)
        self.packages = InMemoryPackageRepository(self)
        self.checkpoints = InMemoryCheckpointRepository(self)
        self.receipts = InMemoryReceiptStore(self)
        self.outbox = InMemoryOutboxWriter(self)
        self._tables: tuple[_Table, ...] = (
            self.sources,
            self.candidates,
            self.runs,
            self.packages,
            self.checkpoints,
            self.receipts,
            self.outbox,
        )

    @property
    def active(self) -> bool:
        return self._snapshot is not None

    def _require_active(self) -> None:
        if not self.active:
            raise TransactionNotActiveError('UOW_NOT_ACTIVE')

    def begin(self) -> None:
        if self.active:
            raise TransactionAlreadyActiveError('UOW_ALREADY_ACTIVE')
        self._snapshot = tuple(dict(t._rows) for t in self._tables)

    def commit(self) -> None:
        self._require_active()
        self._snapshot = None

    def rollback(self) -> None:
        self._require_active()
        assert self._snapshot is not None
        for table, rows in zip(self._tables, self._snapshot):
            table._rows = rows
        self._snapshot = None

    def __enter__(self) -> InMemoryUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.active:
            self.rollback()


_SHA256_RE = re.compile(r'[0-9a-f]{64}')


def _matches(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'sha256':
        return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'boolean':
        return isinstance(value, bool)
    if type_name == 'array':
        return isinstance(value, list)
    return False


def contract_errors(
    payload: object, fields: tuple[tuple[str, str, bool], ...]
) -> tuple[tuple[str, str], ...]:
    if not isinstance(payload, Mapping):
        return (('wrong_type', '$'),)
    errors: list[tuple[str, str]] = []
    for name, type_name, required in fields:
        if name not in payload:
            if required:
                errors.append(('missing_required', name))
            continue
        val = payload[name]
        if not _matches(val, type_name):
            errors.append(('wrong_type', name))
    return tuple(errors)


def _raise_contract(errors: tuple[tuple[str, str], ...]) -> None:
    if errors:
        code, field = errors[0]
        raise ValueError(f'{code}:{field}')


class FakeArtifactPort:
    """Fixture-bound I fake (CT-STO-001); never touches real storage."""

    def __init__(self, result: Mapping[str, object]) -> None:
        _raise_contract(contract_errors(result, DECLARE_ARTIFACT_VERSION_RESULT_FIELDS))
        self._result = dict(result)
        self.requests: list[dict[str, object]] = []

    def declare_artifact_version(self, request: Mapping[str, object]) -> Mapping[str, object]:
        _raise_contract(contract_errors(request, DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS))
        self.requests.append(dict(request))
        return dict(self._result)


class FakeContentHandoffPort:
    def __init__(self, resolution: Mapping[str, object]) -> None:
        if not isinstance(resolution, Mapping):
            raise ValueError('resolution must be a mapping')
        self._resolution = dict(resolution)
        self.submitted: list[dict[str, object]] = []

    def resolve_collected_document(self, package: Mapping[str, object]) -> Mapping[str, object]:
        errors = validate_package_schema(package)
        if errors:
            raise PackageValidationError(errors)
        self.submitted.append(dict(package))
        return dict(self._resolution)


class FakeConfigPort:
    def __init__(
        self,
        policies: Iterable[PolicyRevisionRef] = (),
        credential_handles: Mapping[tuple[str, str], SecretHandle] | None = None,
    ) -> None:
        self._policies: dict[tuple[str, str], PolicyRevisionRef] = {}
        for p in policies:
            if not isinstance(p, PolicyRevisionRef):
                raise TypeError('policies must be PolicyRevisionRef')
            self._policies[(p.workspace_id, p.policy_kind)] = p
        self._handles: dict[tuple[str, str], SecretHandle] = {}
        if credential_handles is not None:
            for k, v in credential_handles.items():
                if not isinstance(v, SecretHandle):
                    raise TypeError('credential handles must be SecretHandle, never raw secrets')
                self._handles[k] = v

    def get_policy_revision(self, workspace_id: str, policy_kind: str) -> PolicyRevisionRef | None:
        return self._policies.get((workspace_id, policy_kind))

    def get_credential_handle(self, workspace_id: str, source_id: str) -> SecretHandle | None:
        return self._handles.get((workspace_id, source_id))


class FakeActivityGrantPort:
    def __init__(self, current_grants: Iterable[ExecutionGrant] = ()) -> None:
        grants = tuple(current_grants)
        for g in grants:
            if not isinstance(g, ExecutionGrant):
                raise TypeError('current_grants must be ExecutionGrant')
        self._current = frozenset(grants)

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        return isinstance(grant, ExecutionGrant) and grant in self._current


__all__ = [
    'FakeActivityGrantPort',
    'FakeArtifactPort',
    'FakeConfigPort',
    'FakeContentHandoffPort',
    'InMemoryCheckpointRepository',
    'InMemoryCollectionRunRepository',
    'InMemoryOutboxWriter',
    'InMemoryPackageRepository',
    'InMemoryReceiptStore',
    'InMemorySourceCandidateRepository',
    'InMemorySourceRepository',
    'InMemoryUnitOfWork',
    'OutboxRecord',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
    'contract_errors',
]
