"""F-16: in-memory RenderRepository, outbox and unit of work of F; test and fixture use only, PostgreSQL persistence waits for CONV-F-01."""
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
from render.ports.repositories import (
    KIND_ATTEMPT,
    KIND_PACKAGE,
    RECORD_TYPES,
    DuplicateRecordError,
    ImmutableFieldError,
    StoredRecord,
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


def _text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


class _Table:
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow
        self._rows: dict = {}

    def _write(self) -> None:
        self._uow._require_active()


class InMemoryRenderRepository(_Table):
    def append(self, kind: str, key: str, revision: int, record: object) -> StoredRecord:
        self._write()
        _text('kind', kind)
        _text('key', key)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')
        record_type = RECORD_TYPES.get(kind)
        if record_type is None:
            raise ValueError(f'unknown kind: {kind}')
        if not isinstance(record, record_type):
            raise TypeError(f'record must be a {record_type.__name__} for kind {kind}')
        current = self._rows.get((kind, key), ())
        current_revision = current[-1].revision if current else 0
        if revision != current_revision + 1:
            raise RevisionConflictError(current_revision)
        if kind == KIND_PACKAGE:
            self._check_package(key, record, current)
        elif kind == KIND_ATTEMPT:
            self._check_attempt(key, record, current)
        stored = StoredRecord(kind, key, revision, record)
        self._rows[(kind, key)] = current + (stored,)
        return stored

    def _check_package(self, key: str, record: Any, current: tuple) -> None:
        if record.render_package_id != key:
            raise ValueError('key must equal render_package_id')
        if current and current[-1].record.package_fingerprint != record.package_fingerprint:
            raise ImmutableFieldError('package_fingerprint cannot change between revisions')
        for rows in self._rows.values():
            for item in rows:
                if item.kind == KIND_PACKAGE and item.record.package_fingerprint == record.package_fingerprint:
                    raise DuplicateRecordError(f'package_fingerprint already stored: {record.package_fingerprint}')

    def _check_attempt(self, key: str, record: Any, current: tuple) -> None:
        if record.render_attempt_id != key:
            raise ValueError('key must equal render_attempt_id')
        if current:
            first = current[0].record
            if first.package_fingerprint != record.package_fingerprint or first.output_artifact_ref != record.output_artifact_ref:
                raise ImmutableFieldError('package_fingerprint and output_artifact_ref cannot change between attempt revisions')
        for rows in self._rows.values():
            for item in rows:
                if item.kind == KIND_ATTEMPT and item.key != key and item.record.output_artifact_ref == record.output_artifact_ref:
                    raise DuplicateRecordError(f'output_artifact_ref already stored: {record.output_artifact_ref}')

    def latest(self, kind: str, key: str) -> StoredRecord | None:
        current = self._rows.get((kind, key))
        return current[-1] if current else None

    def revisions(self, kind: str, key: str) -> tuple[StoredRecord, ...]:
        return self._rows.get((kind, key), ())


class InMemoryOutboxWriter(_Table, IOutboxWriter):
    def append_event(self, event_type: str, aggregate_id: str, payload: Mapping[str, Any], deduplication_id: str) -> str:
        self._write()
        _text('event_type', event_type)
        _text('aggregate_id', aggregate_id)
        _text('deduplication_id', deduplication_id)
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
    """One instance is one in-memory store; leaving the context without commit() rolls back records and outbox together."""

    def __init__(self) -> None:
        self._snapshot: tuple[dict, ...] | None = None
        self.renders = InMemoryRenderRepository(self)
        self.outbox = InMemoryOutboxWriter(self)
        self._tables: tuple[_Table, ...] = (self.renders, self.outbox)

    @property
    def active(self) -> bool:
        return self._snapshot is not None

    def _require_active(self) -> None:
        if not self.active:
            raise TransactionNotActiveError('UOW_NOT_ACTIVE')

    def begin(self) -> None:
        if self.active:
            raise TransactionAlreadyActiveError('UOW_ALREADY_ACTIVE')
        self._snapshot = tuple(dict(table._rows) for table in self._tables)

    def commit(self) -> None:
        self._require_active()
        self._snapshot = None

    def rollback(self) -> None:
        self._require_active()
        snapshot = self._snapshot
        for table, rows in zip(self._tables, snapshot):
            table._rows = rows
        self._snapshot = None

    def __enter__(self) -> InMemoryUnitOfWork:
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.active:
            self.rollback()


__all__ = [
    'InMemoryOutboxWriter',
    'InMemoryRenderRepository',
    'InMemoryUnitOfWork',
    'OutboxRecord',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
]

