"""PostgreSQL implementation of RenderRepository for render ports (PERSIST-F)."""
from __future__ import annotations

from typing import Any

import psycopg.errors

from controlplane.domain.concurrency import RevisionConflictError
from render.persistence import _codec
from render.persistence._sql import (
    ConnectionProvider,
    ReadProvider,
    dumps,
    resolve_workspace,
    savepoint,
    violated_constraint,
)
from render.ports.repositories import (
    KIND_ATTEMPT,
    KIND_PACKAGE,
    KIND_QUALITY_REPORT,
    RECORD_TYPES,
    DuplicateRecordError,
    ImmutableFieldError,
    StoredRecord,
)

_TABLES = {
    KIND_PACKAGE: 'controlplane.cp_render_packages',
    KIND_ATTEMPT: 'controlplane.cp_render_attempts',
    KIND_QUALITY_REPORT: 'controlplane.cp_quality_reports',
}


class PostgresRenderRepository:
    """Append-only PostgreSQL repository for KIND_PACKAGE, KIND_ATTEMPT, and KIND_QUALITY_REPORT."""

    def __init__(
        self,
        connection: ConnectionProvider,
        reader: ReadProvider,
        workspace_id: str | None,
    ) -> None:
        self._connection = connection
        self._reader = reader
        self._workspace_id = workspace_id

    def _workspace(self) -> str:
        return resolve_workspace(self._workspace_id)

    def _decode(self, kind: str, row: tuple[Any, ...]) -> Any:
        if kind == KIND_PACKAGE:
            return _codec.package_from_payload(row[1])
        if kind == KIND_ATTEMPT:
            return _codec.attempt_from_payload(row[1])
        if kind == KIND_QUALITY_REPORT:
            return _codec.quality_from_payload(row[1], row[2])
        raise ValueError(f'unknown kind: {kind}')

    def _load(self, kind: str, key: str, newest_only: bool) -> list[StoredRecord]:
        if kind not in _TABLES:
            return []
        ws = self._workspace()
        if kind == KIND_QUALITY_REPORT:
            suffix = ' DESC LIMIT 1' if newest_only else ''
            query = (
                f'SELECT r.revision, r.payload, g.payload FROM controlplane.cp_quality_reports r '
                f'JOIN controlplane.cp_quality_gate_results g '
                f'ON g.workspace_id = r.workspace_id AND g.record_key = r.record_key AND g.revision = r.revision '
                f'WHERE r.workspace_id = %s AND r.record_key = %s ORDER BY r.revision{suffix}'
            )
        else:
            table = _TABLES[kind]
            suffix = ' DESC LIMIT 1' if newest_only else ''
            query = (
                f'SELECT revision, payload FROM {table} '
                f'WHERE workspace_id = %s AND record_key = %s ORDER BY revision{suffix}'
            )
        with self._reader() as conn:
            rows = conn.execute(query, (ws, key)).fetchall()
        return [
            StoredRecord(kind=kind, key=key, revision=r[0], record=self._decode(kind, r))
            for r in rows
        ]

    def latest(self, kind: str, key: str) -> StoredRecord | None:
        records = self._load(kind, key, True)
        return records[0] if records else None

    def revisions(self, kind: str, key: str) -> tuple[StoredRecord, ...]:
        return tuple(self._load(kind, key, False))

    def _translate(
        self,
        exc: Exception,
        current: int,
        kind: str,
        key: str,
        record: Any,
    ) -> Exception:
        constraint = violated_constraint(exc)
        if constraint == 'cp_render_packages_fingerprint_unique':
            return DuplicateRecordError(f'package_fingerprint already stored: {record.package_fingerprint}')
        if constraint == 'cp_render_attempts_attempt_id_unique':
            return DuplicateRecordError(f'render_attempt_id already stored: {key}')
        if constraint == 'cp_video_outputs_pkey':
            return DuplicateRecordError(f'output_artifact_ref already stored: {record.output_artifact_ref}')
        if constraint and constraint.endswith('_pkey'):
            return RevisionConflictError(current)
        return exc

    def append(self, kind: str, key: str, revision: int, record: Any) -> StoredRecord:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError('kind must be a non-empty string')
        if not isinstance(key, str) or not key.strip():
            raise ValueError('key must be a non-empty string')
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError('revision must be a positive integer')

        record_type = RECORD_TYPES.get(kind)
        if record_type is None:
            raise ValueError(f'unknown kind: {kind}')
        if not isinstance(record, record_type):
            raise TypeError(f'record must be a {record_type.__name__} for kind {kind}')

        if kind == KIND_PACKAGE and record.render_package_id != key:
            raise ValueError('key must equal render_package_id')
        if kind == KIND_ATTEMPT and record.render_attempt_id != key:
            raise ValueError('key must equal render_attempt_id')

        conn = self._connection()
        ws = self._workspace()
        table = _TABLES[kind]

        row = conn.execute(
            f'SELECT COALESCE(MAX(revision), 0) FROM {table} WHERE workspace_id = %s AND record_key = %s',
            (ws, key),
        ).fetchone()
        current = row[0] if row is not None else 0

        if revision != current + 1:
            raise RevisionConflictError(current)

        if current > 0:
            if kind == KIND_PACKAGE:
                first_row = conn.execute(
                    'SELECT package_fingerprint FROM controlplane.cp_render_packages WHERE workspace_id = %s AND record_key = %s AND revision = 1',
                    (ws, key),
                ).fetchone()
                if first_row is not None and first_row[0] != record.package_fingerprint:
                    raise ImmutableFieldError('package_fingerprint cannot change between revisions')
            elif kind == KIND_ATTEMPT:
                first_row = conn.execute(
                    'SELECT payload FROM controlplane.cp_render_attempts WHERE workspace_id = %s AND record_key = %s AND revision = 1',
                    (ws, key),
                ).fetchone()
                if first_row is not None:
                    payload = first_row[0]
                    if (
                        payload.get('package_fingerprint') != record.package_fingerprint
                        or payload.get('output_artifact_ref') != record.output_artifact_ref
                    ):
                        raise ImmutableFieldError(
                            'package_fingerprint and output_artifact_ref cannot change between attempt revisions'
                        )

        try:
            with savepoint(conn):
                if kind == KIND_PACKAGE:
                    conn.execute(
                        'INSERT INTO controlplane.cp_render_packages '
                        '(workspace_id, record_key, revision, payload, package_fingerprint) '
                        'VALUES (%s, %s, %s, %s::jsonb, %s)',
                        (ws, key, revision, dumps(_codec.package_payload(record)), record.package_fingerprint),
                    )
                elif kind == KIND_ATTEMPT:
                    conn.execute(
                        'INSERT INTO controlplane.cp_render_attempts '
                        '(workspace_id, record_key, revision, payload, render_attempt_id) '
                        'VALUES (%s, %s, %s, %s::jsonb, %s)',
                        (ws, key, revision, dumps(_codec.attempt_payload(record)), record.render_attempt_id),
                    )
                    if revision == 1:
                        conn.execute(
                            'INSERT INTO controlplane.cp_video_outputs '
                            '(output_artifact_ref, workspace_id, render_attempt_id, payload) '
                            'VALUES (%s, %s, %s, %s::jsonb)',
                            (
                                record.output_artifact_ref,
                                ws,
                                record.render_attempt_id,
                                dumps({
                                    'render_attempt_id': record.render_attempt_id,
                                    'package_fingerprint': record.package_fingerprint,
                                    'output_artifact_ref': record.output_artifact_ref,
                                }),
                            ),
                        )
                elif kind == KIND_QUALITY_REPORT:
                    conn.execute(
                        'INSERT INTO controlplane.cp_quality_reports '
                        '(workspace_id, record_key, revision, payload) '
                        'VALUES (%s, %s, %s, %s::jsonb)',
                        (ws, key, revision, dumps(_codec.quality_header(record))),
                    )
                    conn.execute(
                        'INSERT INTO controlplane.cp_quality_gate_results '
                        '(workspace_id, record_key, revision, payload) '
                        'VALUES (%s, %s, %s, %s::jsonb)',
                        (ws, key, revision, dumps(_codec.quality_gates(record))),
                    )
        except psycopg.errors.UniqueViolation as exc:
            raise self._translate(exc, current, kind, key, record) from None

        return StoredRecord(kind=kind, key=key, revision=revision, record=record)