"""PostgreSQL OutputRepository of E for the kinds declared by the port (voice, word_timing); every statement runs on the connection of the unit of work."""

from __future__ import annotations

from typing import Any

import psycopg.errors
from psycopg.types.json import Jsonb

from controlplane.domain.concurrency import RevisionConflictError
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord
from voice.persistence.errors import UnsupportedKindError
from voice.persistence.serialization import timing_from_payload, timing_to_payload, voice_from_payload, voice_to_payload
from voice.ports.repositories import KIND_VOICE, KIND_WORD_TIMING, DuplicateOutputError, StoredOutput

_TABLES = {KIND_VOICE: 'controlplane.cp_voice_tracks', KIND_WORD_TIMING: 'controlplane.cp_word_timings'}
_UNIQUE_COLUMNS = {KIND_VOICE: 'voice_hash', KIND_WORD_TIMING: 'timing_artifact_ref'}
_RECORD_TYPES = {KIND_VOICE: VoiceTrack, KIND_WORD_TIMING: WordTimingRecord}
_TO_PAYLOAD = {KIND_VOICE: voice_to_payload, KIND_WORD_TIMING: timing_to_payload}
_FROM_PAYLOAD = {KIND_VOICE: voice_from_payload, KIND_WORD_TIMING: timing_from_payload}


def _table(kind: Any) -> str:
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError('kind must be a non-empty string')
    if kind not in _TABLES:
        raise UnsupportedKindError(f'unsupported kind: {kind}')
    return _TABLES[kind]


def _check_key(key: Any) -> None:
    if not isinstance(key, str) or not key.strip():
        raise ValueError('key must be a non-empty string')


def _current_revision(connection: Any, table: str, workspace_id: str, key: str) -> int:
    row = connection.execute(f'SELECT COALESCE(MAX(revision), 0) FROM {table} WHERE workspace_id = %s::uuid AND record_key = %s', (workspace_id, key)).fetchone()
    return int(row[0])


class PostgresOutputRepository:
    def __init__(self, session: Any) -> None:
        self._session = session

    def append(self, kind: str, key: str, revision: int, record: object) -> StoredOutput:
        table = _table(kind)
        _check_key(key)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')
        if not isinstance(record, _RECORD_TYPES[kind]):
            raise TypeError(f'record must be a {_RECORD_TYPES[kind].__name__} for {kind} kind')
        connection = self._session.connection
        workspace_id = self._session.require_workspace()
        current = _current_revision(connection, table, workspace_id, key)
        if revision != current + 1:
            raise RevisionConflictError(current)
        column = _UNIQUE_COLUMNS[kind]
        value = getattr(record, column)
        if connection.execute(f'SELECT 1 FROM {table} WHERE {column} = %s', (value,)).fetchone() is not None:
            raise DuplicateOutputError(f'{column} already stored: {value}')
        try:
            with connection.transaction():
                connection.execute(f'INSERT INTO {table} (workspace_id, record_key, revision, payload, {column}) VALUES (%s::uuid, %s, %s, %s, %s)', (workspace_id, key, revision, Jsonb(_TO_PAYLOAD[kind](record)), value))
        except psycopg.errors.UniqueViolation as exc:
            if column in (exc.diag.constraint_name or ''):
                raise DuplicateOutputError(f'{column} already stored: {value}') from exc
            raise RevisionConflictError(_current_revision(connection, table, workspace_id, key)) from exc
        return StoredOutput(kind, key, revision, record)

    def _stored(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        table = _table(kind)
        _check_key(key)
        workspace_id = self._session.require_workspace()
        with self._session.reading() as connection:
            rows = connection.execute(f'SELECT revision, payload FROM {table} WHERE workspace_id = %s::uuid AND record_key = %s ORDER BY revision', (workspace_id, key)).fetchall()
        convert = _FROM_PAYLOAD[kind]
        return tuple(StoredOutput(kind, key, int(revision), convert(payload)) for revision, payload in rows)

    def latest(self, kind: str, key: str) -> StoredOutput | None:
        rows = self._stored(kind, key)
        return rows[-1] if rows else None

    def revisions(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        return self._stored(kind, key)
