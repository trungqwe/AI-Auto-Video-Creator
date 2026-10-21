"""PostgreSQL implementations of the source ingestion repository ports."""
from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import Any

import psycopg.errors

from controlplane.domain.concurrency import RevisionConflictError
from source_ingestion.domain.checkpoint import (
    CheckpointRejected,
    CollectionCheckpoint,
    advance_checkpoint,
)
from source_ingestion.domain.collection_run import (
    CollectionRun,
    DuplicatePeriodicRunError,
)
from source_ingestion.domain.source import Source, SourceStatus
from source_ingestion.domain.source_candidate import (
    NO_MATCH,
    IdentityMatch,
    IdentityMatchKind,
    SourceCandidate,
)
from source_ingestion.persistence import _codec
from source_ingestion.persistence._sql import (
    ConnectionProvider,
    dumps,
    savepoint,
    uuid_text,
    violated_constraint,
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


def _run_workspace(conn: Any, run_id: str, source_id: str) -> str:
    row = conn.execute(
        'SELECT workspace_id::text, source_id FROM controlplane.cp_collection_runs WHERE run_id = %s',
        (run_id,),
    ).fetchone()
    if row is None:
        raise RecordNotFoundError(run_id)
    if row[1] != source_id:
        raise ValueError('source_id does not match the collection run')
    return row[0]


class PostgresSourceRepository:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def get(self, workspace_id: str, source_id: str) -> Source | None:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        row = conn.execute(
            'SELECT source_id, canonical_locator, status, revision, payload FROM controlplane.cp_sources WHERE workspace_id = %s AND source_id = %s',
            (ws, source_id),
        ).fetchone()
        if row is None:
            return None
        return _codec.source_from_row(ws, row[0], row[1], row[2], row[3], row[4])

    def list_sources(self, workspace_id: str) -> tuple[Source, ...]:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        rows = conn.execute(
            'SELECT source_id, canonical_locator, status, revision, payload FROM controlplane.cp_sources WHERE workspace_id = %s ORDER BY created_at, source_id',
            (ws,),
        ).fetchall()
        return tuple(_codec.source_from_row(ws, r[0], r[1], r[2], r[3], r[4]) for r in rows)

    def resolve_identity(self, workspace_id: str, canonical_locator: str) -> IdentityMatch:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        row = conn.execute(
            'SELECT source_id, is_tombstone FROM controlplane.cp_source_identities WHERE workspace_id = %s AND canonical_locator = %s',
            (ws, canonical_locator),
        ).fetchone()
        if row is None:
            return NO_MATCH
        if row[1]:
            return IdentityMatch(IdentityMatchKind.TOMBSTONE, row[0])
        return IdentityMatch(IdentityMatchKind.EXISTING_SOURCE, row[0])

    def add(self, source: Source) -> None:
        conn = self._connection()
        ws = uuid_text(source.workspace_id)
        is_tomb = source.status is SourceStatus.REMOVED_TOMBSTONE
        tomb_at = source.updated_at if is_tomb else None
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_sources (workspace_id, source_id, canonical_locator, status, revision, payload, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)',
                    (
                        ws,
                        source.source_id,
                        source.canonical_locator,
                        source.status.value,
                        source.revision,
                        dumps(_codec.source_payload(source)),
                        source.created_at,
                        source.updated_at,
                    ),
                )
                conn.execute(
                    'INSERT INTO controlplane.cp_source_identities (workspace_id, canonical_locator, source_id, is_tombstone, tombstoned_at) VALUES (%s, %s, %s, %s, %s)',
                    (ws, source.canonical_locator, source.source_id, is_tomb, tomb_at),
                )
        except psycopg.errors.UniqueViolation:
            raise DuplicateSourceIdentityError(source.canonical_locator) from None

    def save(self, source: Source) -> None:
        conn = self._connection()
        ws = uuid_text(source.workspace_id)
        row = conn.execute(
            'SELECT canonical_locator, revision FROM controlplane.cp_sources WHERE workspace_id = %s AND source_id = %s FOR UPDATE',
            (ws, source.source_id),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(source.source_id)
        canonical_locator, stored_rev = row
        if source.canonical_locator != canonical_locator:
            raise ValueError('canonical_locator is immutable')
        if source.revision != stored_rev + 1:
            raise RevisionConflictError(stored_rev)
        is_tomb = source.status is SourceStatus.REMOVED_TOMBSTONE
        tomb_at = source.updated_at if is_tomb else None
        conn.execute(
            'UPDATE controlplane.cp_sources SET status = %s, revision = %s, payload = %s::jsonb, updated_at = %s WHERE workspace_id = %s AND source_id = %s',
            (
                source.status.value,
                source.revision,
                dumps(_codec.source_payload(source)),
                source.updated_at,
                ws,
                source.source_id,
            ),
        )
        conn.execute(
            'UPDATE controlplane.cp_source_identities SET is_tombstone = %s, tombstoned_at = %s, updated_at = %s WHERE workspace_id = %s AND canonical_locator = %s',
            (is_tomb, tomb_at, source.updated_at, ws, source.canonical_locator),
        )


class PostgresSourceCandidateRepository:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def get(self, workspace_id: str, candidate_id: str) -> SourceCandidate | None:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        row = conn.execute(
            'SELECT candidate_id, canonical_locator, status, revision, payload FROM controlplane.cp_source_candidates WHERE workspace_id = %s AND candidate_id = %s',
            (ws, candidate_id),
        ).fetchone()
        if row is None:
            return None
        return _codec.candidate_from_row(ws, row[0], row[1], row[2], row[3], row[4])

    def find_by_canonical_locator(self, workspace_id: str, canonical_locator: str) -> tuple[SourceCandidate, ...]:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        rows = conn.execute(
            'SELECT candidate_id, canonical_locator, status, revision, payload FROM controlplane.cp_source_candidates WHERE workspace_id = %s AND canonical_locator = %s ORDER BY created_at, candidate_id',
            (ws, canonical_locator),
        ).fetchall()
        return tuple(_codec.candidate_from_row(ws, r[0], r[1], r[2], r[3], r[4]) for r in rows)

    def add(self, candidate: SourceCandidate) -> None:
        conn = self._connection()
        ws = uuid_text(candidate.workspace_id)
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_source_candidates (workspace_id, candidate_id, canonical_locator, status, revision, payload, updated_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)',
                    (
                        ws,
                        candidate.candidate_id,
                        candidate.canonical_locator,
                        candidate.status.value,
                        candidate.revision,
                        dumps(_codec.candidate_payload(candidate)),
                        candidate.updated_at,
                    ),
                )
        except psycopg.errors.UniqueViolation:
            raise DuplicateRecordError(candidate.candidate_id) from None

    def save(self, candidate: SourceCandidate) -> None:
        conn = self._connection()
        ws = uuid_text(candidate.workspace_id)
        row = conn.execute(
            'SELECT revision FROM controlplane.cp_source_candidates WHERE workspace_id = %s AND candidate_id = %s FOR UPDATE',
            (ws, candidate.candidate_id),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(candidate.candidate_id)
        stored_rev = row[0]
        if candidate.revision != stored_rev + 1:
            raise RevisionConflictError(stored_rev)
        conn.execute(
            'UPDATE controlplane.cp_source_candidates SET status = %s, revision = %s, payload = %s::jsonb, updated_at = %s WHERE workspace_id = %s AND candidate_id = %s',
            (
                candidate.status.value,
                candidate.revision,
                dumps(_codec.candidate_payload(candidate)),
                candidate.updated_at,
                ws,
                candidate.candidate_id,
            ),
        )


class PostgresCollectionRunRepository:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def _load(self, conn: Any, row: Any) -> CollectionRun:
        run_id, ws_text, source_id, run_kind, business_date, status, payload = row
        attempts_rows = conn.execute(
            'SELECT attempt_index, status FROM controlplane.cp_collection_attempts WHERE run_id = %s ORDER BY attempt_index',
            (run_id,),
        ).fetchall()
        return _codec.run_from_rows(
            ws_text,
            run_id,
            source_id,
            run_kind,
            business_date,
            status,
            payload,
            attempts_rows,
        )

    def _write_attempts(self, conn: Any, run: CollectionRun) -> None:
        ws = uuid_text(run.workspace_id)
        for a in run.attempts:
            attempt_id = f'{run.run_id}:{a.attempt_no}'
            conn.execute(
                'INSERT INTO controlplane.cp_collection_attempts (attempt_id, run_id, workspace_id, attempt_index, status, payload) VALUES (%s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (attempt_id) DO UPDATE SET status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = CURRENT_TIMESTAMP',
                (
                    attempt_id,
                    run.run_id,
                    ws,
                    a.attempt_no,
                    a.outcome.value,
                    dumps({'outcome': a.outcome.value}),
                ),
            )

    def get(self, run_id: str) -> CollectionRun | None:
        conn = self._connection()
        row = conn.execute(
            'SELECT run_id, workspace_id::text, source_id, run_kind, business_date, status, payload FROM controlplane.cp_collection_runs WHERE run_id = %s',
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._load(conn, row)

    def get_periodic(self, workspace_id: str, source_id: str, business_date: datetime.date) -> CollectionRun | None:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        row = conn.execute(
            "SELECT run_id, workspace_id::text, source_id, run_kind, business_date, status, payload FROM controlplane.cp_collection_runs WHERE workspace_id = %s AND source_id = %s AND business_date = %s AND run_kind = 'PERIODIC'",
            (ws, source_id, business_date),
        ).fetchone()
        if row is None:
            return None
        return self._load(conn, row)

    def list_by_source(self, workspace_id: str, source_id: str) -> tuple[CollectionRun, ...]:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        rows = conn.execute(
            'SELECT run_id, workspace_id::text, source_id, run_kind, business_date, status, payload FROM controlplane.cp_collection_runs WHERE workspace_id = %s AND source_id = %s ORDER BY created_at, run_id',
            (ws, source_id),
        ).fetchall()
        return tuple(self._load(conn, r) for r in rows)

    def add(self, run: CollectionRun) -> None:
        conn = self._connection()
        ws = uuid_text(run.workspace_id)
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_collection_runs (run_id, workspace_id, source_id, run_kind, business_date, status, revision, payload) VALUES (%s, %s, %s, %s, %s, %s, 1, %s::jsonb)',
                    (
                        run.run_id,
                        ws,
                        run.source_id,
                        run.purpose.value,
                        run.business_date,
                        run.status.value,
                        dumps(_codec.run_payload(run)),
                    ),
                )
                self._write_attempts(conn, run)
        except psycopg.errors.UniqueViolation as exc:
            if violated_constraint(exc) == 'cp_collection_runs_periodic_unique':
                raise DuplicatePeriodicRunError(
                    f'periodic run already exists for {run.unique_key!r}'
                ) from None
            raise DuplicateRecordError(run.run_id) from None

    def save(self, run: CollectionRun) -> None:
        conn = self._connection()
        ws = uuid_text(run.workspace_id)
        row = conn.execute(
            'SELECT workspace_id::text, source_id, run_kind, business_date, revision FROM controlplane.cp_collection_runs WHERE run_id = %s FOR UPDATE',
            (run.run_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(run.run_id)
        stored_ws, stored_source_id, stored_kind, stored_date, stored_rev = row
        if (stored_ws, stored_source_id, stored_kind, stored_date) != (
            ws,
            run.source_id,
            run.purpose.value,
            run.business_date,
        ):
            raise ValueError('collection run key fields are immutable')
        conn.execute(
            'UPDATE controlplane.cp_collection_runs SET status = %s, payload = %s::jsonb, revision = revision + 1, updated_at = CURRENT_TIMESTAMP WHERE run_id = %s',
            (run.status.value, dumps(_codec.run_payload(run)), run.run_id),
        )
        self._write_attempts(conn, run)


class PostgresPackageRepository:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def get(self, source_id: str, canonical_locator: str, observation_fingerprint: str) -> PackageRecord | None:
        conn = self._connection()
        row = conn.execute(
            'SELECT source_id, canonical_locator, observation_fingerprint, collection_run_id, payload FROM controlplane.cp_collected_document_packages WHERE source_id = %s AND canonical_locator = %s AND observation_fingerprint = %s',
            (source_id, canonical_locator, observation_fingerprint),
        ).fetchone()
        if row is None:
            return None
        return PackageRecord(row[0], row[1], row[2], row[3], row[4])

    def list_by_run(self, collection_run_id: str) -> tuple[PackageRecord, ...]:
        conn = self._connection()
        rows = conn.execute(
            'SELECT source_id, canonical_locator, observation_fingerprint, collection_run_id, payload FROM controlplane.cp_collected_document_packages WHERE collection_run_id = %s ORDER BY created_at, canonical_locator, observation_fingerprint',
            (collection_run_id,),
        ).fetchall()
        return tuple(PackageRecord(r[0], r[1], r[2], r[3], r[4]) for r in rows)

    def add(self, record: PackageRecord) -> None:
        conn = self._connection()
        ws = _run_workspace(conn, record.collection_run_id, record.source_id)
        raw_fetched = record.payload.get('fetched_at')
        observed_at = None
        if isinstance(raw_fetched, str):
            try:
                parsed = datetime.datetime.fromisoformat(raw_fetched)
                if parsed.tzinfo is not None:
                    observed_at = parsed
            except (ValueError, TypeError):
                pass
        if observed_at is None:
            observed_at = datetime.datetime.now(datetime.UTC)
        obs_id = '|'.join(record.identity)
        obs_payload = dumps({'collected_document_id': record.payload.get('collected_document_id')})
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_collected_document_packages (workspace_id, source_id, canonical_locator, observation_fingerprint, collection_run_id, payload) VALUES (%s, %s, %s, %s, %s, %s::jsonb)',
                    (
                        ws,
                        record.source_id,
                        record.canonical_locator,
                        record.observation_fingerprint,
                        record.collection_run_id,
                        dumps(dict(record.payload)),
                    ),
                )
                conn.execute(
                    'INSERT INTO controlplane.cp_fetch_observations (observation_id, workspace_id, run_id, source_id, canonical_locator, observation_fingerprint, observed_at, payload) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)',
                    (
                        obs_id,
                        ws,
                        record.collection_run_id,
                        record.source_id,
                        record.canonical_locator,
                        record.observation_fingerprint,
                        observed_at,
                        obs_payload,
                    ),
                )
        except psycopg.errors.UniqueViolation:
            raise DuplicatePackageError(repr(record.identity)) from None


class PostgresCheckpointRepository:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def get_latest(self, source_id: str) -> CollectionCheckpoint | None:
        conn = self._connection()
        row = conn.execute(
            'SELECT payload FROM controlplane.cp_collection_checkpoints WHERE source_id = %s ORDER BY sequence_no DESC LIMIT 1',
            (source_id,),
        ).fetchone()
        if row is None:
            return None
        return _codec.checkpoint_from_payload(row[0])

    def advance(self, proposed: CollectionCheckpoint, durable_item_ids: Iterable[str]) -> CollectionCheckpoint:
        conn = self._connection()
        durable = tuple(durable_item_ids)
        current = self.get_latest(proposed.source_id)
        accepted = advance_checkpoint(current, durable, proposed)
        ws = _run_workspace(conn, accepted.run_id, accepted.source_id)
        checkpoint_id = f'{accepted.source_id}:{accepted.revision}'
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_collection_checkpoints (checkpoint_id, workspace_id, source_id, sequence_no, payload) VALUES (%s, %s, %s, %s, %s::jsonb)',
                    (
                        checkpoint_id,
                        ws,
                        accepted.source_id,
                        accepted.revision,
                        dumps(_codec.checkpoint_payload(accepted)),
                    ),
                )
        except psycopg.errors.UniqueViolation:
            raise CheckpointRejected(
                'CHECKPOINT_REVISION_CONFLICT',
                f'revision {accepted.revision} already stored',
            ) from None
        return accepted


class PostgresReceiptStore:
    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    def get(self, workspace_id: str, idempotency_key: str) -> CommandReceipt | None:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        row = conn.execute(
            'SELECT workspace_id::text, idempotency_key, request_hash, aggregate_ref, aggregate_revision FROM controlplane.cp_source_command_receipts WHERE workspace_id = %s AND idempotency_key = %s',
            (ws, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return CommandReceipt(row[0], row[1], row[2], row[3], row[4])

    def put(self, receipt: CommandReceipt) -> None:
        conn = self._connection()
        ws = uuid_text(receipt.workspace_id)
        try:
            with savepoint(conn):
                conn.execute(
                    'INSERT INTO controlplane.cp_source_command_receipts (workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) VALUES (%s, %s, %s, %s, %s)',
                    (
                        ws,
                        receipt.idempotency_key,
                        receipt.request_hash,
                        receipt.aggregate_ref,
                        receipt.aggregate_revision,
                    ),
                )
        except psycopg.errors.UniqueViolation:
            raise DuplicateReceiptError(receipt.idempotency_key) from None
