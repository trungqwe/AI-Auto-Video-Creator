"""PostgreSQL OutputRepository of E for every kind written by VoicePipeline and MediaPipeline (CONV-E-01); every statement runs on the connection of the unit of work."""

from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Mapping
from typing import Any

import psycopg.errors
from psycopg.types.json import Jsonb

from controlplane.domain.concurrency import RevisionConflictError
from voice.application import media_pipeline, voice_pipeline
from voice.domain import audio_bed, image_safety, image_transform, language_evidence, normalize, probe, processing, timing_coverage, tts_invocation
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord
from voice.persistence.errors import UnsupportedKindError
from voice.persistence.serialization import timing_from_payload, timing_to_payload, voice_from_payload, voice_to_payload
from voice.ports.repositories import KIND_VOICE, KIND_WORD_TIMING, DuplicateOutputError, StoredOutput

KIND_RECEIPT = 'receipt'
# kind -> table of 0016_voice.sql (11 kinds, 11 tables, no new migration); receipt_by_request uses cp_analysis_results, the only unused table with the (record_key, revision, payload) shape.
_TABLES = {
    KIND_VOICE: 'controlplane.cp_voice_tracks',
    KIND_WORD_TIMING: 'controlplane.cp_word_timings',
    'tts_invocation': 'controlplane.cp_tts_invocation_records',
    KIND_RECEIPT: 'controlplane.cp_voice_receipts',
    'timing_report': 'controlplane.cp_timing_validation_reports',
    'language_evidence': 'controlplane.cp_language_evidence',
    'probe_report': 'controlplane.cp_probe_reports',
    'image_safety_assessment': 'controlplane.cp_image_safety_assessments',
    'processed_media': 'controlplane.cp_processed_media',
    'audio_bed_result': 'controlplane.cp_audio_bed_results',
    'receipt_by_request': 'controlplane.cp_analysis_results',
}
SUPPORTED_KINDS = tuple(_TABLES)
_UNIQUE_COLUMNS = {KIND_VOICE: 'voice_hash', KIND_WORD_TIMING: 'timing_artifact_ref'}
_RECORD_TYPES = {
    KIND_VOICE: VoiceTrack,
    KIND_WORD_TIMING: WordTimingRecord,
    'tts_invocation': tts_invocation.TtsInvocationRecord,
    KIND_RECEIPT: (voice_pipeline.PipelineReceipt, media_pipeline.OperationReceipt),
    'timing_report': voice_pipeline.TimingValidationReport,
    'language_evidence': language_evidence.LanguageEvidence,
    'probe_report': probe.ProbeReport,
    'image_safety_assessment': image_safety.ImageSafetyAssessment,
    'processed_media': (image_transform.TransformResult, media_pipeline.ProcessedRendition),
    'audio_bed_result': audio_bed.AudioBedResult,
    'receipt_by_request': media_pipeline.OperationReceipt,
}
_TO_PAYLOAD = {KIND_VOICE: voice_to_payload, KIND_WORD_TIMING: timing_to_payload}
_FROM_PAYLOAD = {KIND_VOICE: voice_from_payload, KIND_WORD_TIMING: timing_from_payload}


_CODEC_MODULES = (voice_pipeline, media_pipeline, audio_bed, image_safety, image_transform, language_evidence, normalize, probe, processing, timing_coverage, tts_invocation)


def _codec_classes() -> dict[str, type]:
    classes: dict[str, type] = {}
    for module in _CODEC_MODULES:
        for value in vars(module).values():
            if isinstance(value, type) and value.__module__ == module.__name__ and (dataclasses.is_dataclass(value) or issubclass(value, enum.Enum)):
                classes[f'{module.__name__}.{value.__qualname__}'] = value
    return classes


_CLASSES = _codec_classes()
_TAGS = {cls: tag for tag, cls in _CLASSES.items()}


def _tag(cls: type) -> str:
    if cls not in _TAGS:
        raise TypeError(f'cannot persist instances of {cls.__name__}')
    return _TAGS[cls]


def _class(tag: Any) -> type:
    if not isinstance(tag, str) or tag not in _CLASSES:
        raise ValueError(f'unknown stored class: {tag}')
    return _CLASSES[tag]


# Self-describing JSON: {'@dc': tag, 'fields': {...}}, {'@enum': tag, 'value': v}, {'@tuple': [...]}; lists and string-keyed mappings stay plain.
def _encode(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return {'@enum': _tag(type(value)), 'value': value.value}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {'@dc': _tag(type(value)), 'fields': {field.name: _encode(getattr(value, field.name)) for field in dataclasses.fields(value)}}
    if isinstance(value, tuple):
        return {'@tuple': [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or key.startswith('@') for key in value):
            raise ValueError('mapping keys must be strings that do not start with @')
        return {key: _encode(item) for key, item in value.items()}
    raise TypeError(f'cannot persist value of type {type(value).__name__}')


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if '@enum' in value:
        return _class(value['@enum'])(value['value'])
    if '@dc' in value:
        return _class(value['@dc'])(**{name: _decode(item) for name, item in value['fields'].items()})
    if '@tuple' in value:
        return tuple(_decode(item) for item in value['@tuple'])
    return {key: _decode(item) for key, item in value.items()}


def _to_payload(kind: str, record: object) -> Any:
    return _TO_PAYLOAD.get(kind, _encode)(record)


def _from_payload(kind: str, payload: Any) -> Any:
    if kind == KIND_RECEIPT:
        return _decode(json.loads(payload))
    return _FROM_PAYLOAD.get(kind, _decode)(payload)


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


def _receipt_revision(connection: Any, workspace_id: str, key: str) -> int:
    row = connection.execute(f'SELECT COALESCE(MAX(aggregate_revision), 0) FROM {_TABLES[KIND_RECEIPT]} WHERE workspace_id = %s::uuid AND idempotency_key = %s', (workspace_id, key)).fetchone()
    return int(row[0])


class PostgresOutputRepository:
    def __init__(self, session: Any) -> None:
        self._session = session

    def append(self, kind: str, key: str, revision: int, record: object) -> StoredOutput:
        table = _table(kind)
        _check_key(key)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')
        expected = _RECORD_TYPES[kind]
        if not isinstance(record, expected):
            names = ' or '.join(item.__name__ for item in (expected if isinstance(expected, tuple) else (expected,)))
            raise TypeError(f'record must be a {names} for {kind} kind')
        connection = self._session.connection
        workspace_id = self._session.require_workspace()
        if kind == KIND_RECEIPT:
            return self._append_receipt(connection, workspace_id, key, revision, record)
        current = _current_revision(connection, table, workspace_id, key)
        if revision != current + 1:
            raise RevisionConflictError(current)
        column = _UNIQUE_COLUMNS.get(kind)
        value = None if column is None else getattr(record, column)
        if column is not None and connection.execute(f'SELECT 1 FROM {table} WHERE {column} = %s', (value,)).fetchone() is not None:
            raise DuplicateOutputError(f'{column} already stored: {value}')
        columns, marks, params = '', '', [workspace_id, key, revision, Jsonb(_to_payload(kind, record))]
        if column is not None:
            columns, marks = f', {column}', ', %s'
            params.append(value)
        try:
            with connection.transaction():
                connection.execute(f'INSERT INTO {table} (workspace_id, record_key, revision, payload{columns}) VALUES (%s::uuid, %s, %s, %s{marks})', params)
        except psycopg.errors.UniqueViolation as exc:
            if column is not None and column in (exc.diag.constraint_name or ''):
                raise DuplicateOutputError(f'{column} already stored: {value}') from exc
            raise RevisionConflictError(_current_revision(connection, table, workspace_id, key)) from exc
        return StoredOutput(kind, key, revision, record)

    def _append_receipt(self, connection: Any, workspace_id: str, key: str, revision: int, record: object) -> StoredOutput:
        current = _receipt_revision(connection, workspace_id, key)
        if revision != 1 or current != 0:
            raise RevisionConflictError(current)
        digest = record.request_hash if isinstance(record, voice_pipeline.PipelineReceipt) else record.request_fingerprint
        text = json.dumps(_encode(record), sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        try:
            with connection.transaction():
                connection.execute(f'INSERT INTO {_TABLES[KIND_RECEIPT]} (workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) VALUES (%s::uuid, %s, %s, %s, %s)', (workspace_id, key, digest, text, revision))
        except psycopg.errors.UniqueViolation as exc:
            raise RevisionConflictError(_receipt_revision(connection, workspace_id, key)) from exc
        return StoredOutput(KIND_RECEIPT, key, revision, record)

    def _stored(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        table = _table(kind)
        _check_key(key)
        workspace_id = self._session.require_workspace()
        if kind == KIND_RECEIPT:
            query = f'SELECT aggregate_revision, aggregate_ref FROM {table} WHERE workspace_id = %s::uuid AND idempotency_key = %s ORDER BY aggregate_revision'
        else:
            query = f'SELECT revision, payload FROM {table} WHERE workspace_id = %s::uuid AND record_key = %s ORDER BY revision'
        with self._session.reading() as connection:
            rows = connection.execute(query, (workspace_id, key)).fetchall()
        return tuple(StoredOutput(kind, key, int(revision), _from_payload(kind, payload)) for revision, payload in rows)

    def latest(self, kind: str, key: str) -> StoredOutput | None:
        rows = self._stored(kind, key)
        return rows[-1] if rows else None

    def revisions(self, kind: str, key: str) -> tuple[StoredOutput, ...]:
        return self._stored(kind, key)
