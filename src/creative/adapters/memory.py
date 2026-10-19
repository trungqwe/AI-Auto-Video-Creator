"""In-memory repositories, receipt store, outbox and unit of work of D (D-13); test and fixture use only, PostgreSQL persistence waits for CONV-D-01."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events.contracts import ensure_safe_event_payload
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from creative.domain.snapshot import ProductionSnapshot
from creative.ports.repositories import (
    CommandReceipt,
    DuplicateReceiptError,
    DuplicateRecordError,
    DuplicateSnapshotError,
    KIND_ANALYSIS,
    KIND_OUTPUT_METADATA,
    RECORD_TYPES,
    StoredRecord,
    UNIQUE_ID_ATTRS,
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
        self._rows: dict = {}

    def _write(self) -> None:
        self._uow._require_active()


class InMemorySnapshotRepository(_Table):
    def add(self, snapshot: ProductionSnapshot) -> None:
        self._write()
        if not isinstance(snapshot, ProductionSnapshot):
            raise TypeError('snapshot must be a ProductionSnapshot')
        if snapshot.snapshot_id in self._rows:
            raise DuplicateSnapshotError(snapshot.snapshot_id)
        self._rows[snapshot.snapshot_id] = snapshot

    def get(self, snapshot_id: str) -> ProductionSnapshot | None:
        return self._rows.get(snapshot_id)

    def list_snapshots(self) -> tuple[ProductionSnapshot, ...]:
        return tuple(self._rows.values())


class InMemoryAppendOnlyRepository(_Table):
    def __init__(self, uow: InMemoryUnitOfWork, kind: str) -> None:
        super().__init__(uow)
        if kind not in RECORD_TYPES:
            raise ValueError(f'unknown kind: {kind}')
        self.kind = kind

    def append(self, key: str, revision: int, record: object) -> StoredRecord:
        self._write()
        if not isinstance(key, str) or not key.strip():
            raise ValueError('key must be a non-empty string')
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')
        if not isinstance(record, RECORD_TYPES[self.kind]):
            raise TypeError(f'record must be a {RECORD_TYPES[self.kind].__name__}')

        if self.kind == KIND_ANALYSIS:
            if key != getattr(record, 'analysis_id') or revision != getattr(record, 'revision'):
                raise ValueError('key and revision must match record identity')
        elif self.kind == KIND_OUTPUT_METADATA:
            if key != getattr(record, 'source_job_ref') or revision != getattr(record, 'metadata_revision'):
                raise ValueError('key and revision must match record identity')

        current = self._rows.get(key, ())
        current_revision = current[-1].revision if current else 0
        if revision != current_revision + 1:
            raise RevisionConflictError(current_revision)

        if self.kind in UNIQUE_ID_ATTRS:
            attr = UNIQUE_ID_ATTRS[self.kind]
            target_val = getattr(record, attr)
            for rows_tuple in self._rows.values():
                for item in rows_tuple:
                    if getattr(item.record, attr) == target_val:
                        raise DuplicateRecordError(f'{attr} already stored: {target_val}')

        stored = StoredRecord(self.kind, key, revision, record)
        self._rows[key] = current + (stored,)
        return stored

    def latest(self, key: str) -> StoredRecord | None:
        current = self._rows.get(key)
        return current[-1] if current else None

    def revisions(self, key: str) -> tuple[StoredRecord, ...]:
        return self._rows.get(key, ())


class InMemoryReceiptStore(_Table):
    def get(self, workspace_id: str, idempotency_key: str) -> CommandReceipt | None:
        return self._rows.get((workspace_id, idempotency_key))

    def put(self, receipt: CommandReceipt) -> None:
        self._write()
        if not isinstance(receipt, CommandReceipt):
            raise TypeError('receipt must be a CommandReceipt')
        key = (receipt.workspace_id, receipt.idempotency_key)
        if key in self._rows:
            raise DuplicateReceiptError(receipt.idempotency_key)
        self._rows[key] = receipt


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

        ensure_safe_event_payload(dict(payload))

        if deduplication_id in self._rows:
            return self._rows[deduplication_id].event_id

        event_id = 'evt-' + hashlib.sha256(deduplication_id.encode('utf-8')).hexdigest()[:32]
        self._rows[deduplication_id] = OutboxRecord(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload=MappingProxyType(copy.deepcopy(dict(payload))),
            deduplication_id=deduplication_id,
        )
        return event_id

    def records(self) -> tuple[OutboxRecord, ...]:
        return tuple(self._rows.values())


class InMemoryUnitOfWork(IUnitOfWork):
    """One instance is one in-memory store; leaving the context without commit() rolls back repositories and outbox."""

    def __init__(self) -> None:
        self._snapshot: tuple[dict, ...] | None = None
        self.snapshots = InMemorySnapshotRepository(self)
        self.analyses = InMemoryAppendOnlyRepository(self, 'analysis')
        self.angle_sets = InMemoryAppendOnlyRepository(self, 'angle_set')
        self.scripts = InMemoryAppendOnlyRepository(self, 'script')
        self.plans = InMemoryAppendOnlyRepository(self, 'plan')
        self.variant_validations = InMemoryAppendOnlyRepository(self, 'variant_validation')
        self.output_metadata = InMemoryAppendOnlyRepository(self, 'output_metadata')
        self.invocations = InMemoryAppendOnlyRepository(self, 'invocation_record')
        self.receipts = InMemoryReceiptStore(self)
        self.outbox = InMemoryOutboxWriter(self)
        self._tables: tuple[_Table, ...] = (
            self.snapshots,
            self.analyses,
            self.angle_sets,
            self.scripts,
            self.plans,
            self.variant_validations,
            self.output_metadata,
            self.invocations,
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


__all__ = [
    'InMemoryAppendOnlyRepository',
    'InMemoryOutboxWriter',
    'InMemoryReceiptStore',
    'InMemorySnapshotRepository',
    'InMemoryUnitOfWork',
    'OutboxRecord',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
]
