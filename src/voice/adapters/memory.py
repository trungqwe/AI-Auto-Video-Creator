"""In-memory output repository, outbox and unit of work of E (E-15); test and fixture use only, PostgreSQL persistence waits for CONV-E-01."""

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
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord
from voice.ports.repositories import KIND_VOICE, KIND_WORD_TIMING, DuplicateOutputError, StoredOutput


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


class InMemoryOutputRepository(_Table):
    def append(self, kind: str, key: str, revision: int, record: object) -> StoredOutput:
        self._write()
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError('kind must be a non-empty string')
        if not isinstance(key, str) or not key.strip():
            raise ValueError('key must be a non-empty string')
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')

        if kind == KIND_VOICE and not isinstance(record, VoiceTrack):
            raise TypeError('record must be a VoiceTrack for voice kind')
        if kind == KIND_WORD_TIMING and not isinstance(record, WordTimingRecord):
            raise TypeError('record must be a WordTimingRecord for word_timing kind')

        current = self._rows.get((kind, key), ())
        current_revision = current[-1].revision if current else 0
        if revision != current_revision + 1:
            raise RevisionConflictError(current_revision)

        if kind == KIND_VOICE:
            for rows_tuple in self._rows.values():
                for item in rows_tuple:
                    if item.kind == KIND_VOICE and item.record.voice_hash == record.voice_hash:
                        raise DuplicateOutputError(f'voice_hash already stored: {record.voice_hash}')
        elif kind == KIND_WORD_TIMING:
            for rows_tuple in self._rows.values():
                for item in rows_tuple:
                    if item.kind == KIND_WORD_TIMING and item.record.timing_artifact_ref == record.timing_artifact_ref:
                        raise DuplicateOutputError(f'timing_artifact_ref already stored: {record.timing_artifact_ref}')

        stored = StoredOutput(kind, key, revision, record)
        self._rows[(kind, key)] = current + (stored,)
        return stored

    def latest(self, kind: str, key: str) -> StoredOutput | None:
        current = self._rows.get((kind, key))
        return current[-1] if current else None

    def revisions(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        return self._rows.get((kind, key), ())


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
    """One instance is one in-memory store; leaving the context without commit() rolls back outputs and outbox."""

    def __init__(self) -> None:
        self._snapshot: tuple[dict, ...] | None = None
        self.outputs = InMemoryOutputRepository(self)
        self.outbox = InMemoryOutboxWriter(self)
        self._tables: tuple[_Table, ...] = (self.outputs, self.outbox)

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
    'InMemoryOutboxWriter',
    'InMemoryOutputRepository',
    'InMemoryUnitOfWork',
    'OutboxRecord',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
]
