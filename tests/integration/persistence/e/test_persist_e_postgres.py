"""PERSIST-E: PostgreSQL adapter of voice (OutputRepository and unit of work); PostgreSQL 18.6, one disposable database per test."""
from __future__ import annotations

import os
import re
import subprocess
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from voice.application.media_pipeline import MediaUnitOfWork
from voice.application.voice_pipeline import VoiceUnitOfWork
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord, validate_word_timing
from voice.persistence import (
    PostgresVoiceUnitOfWork,
    TransactionAlreadyActiveError,
    TransactionNotActiveError,
    UnsupportedKindError,
    WorkspaceNotBoundError,
)
from voice.ports.repositories import KIND_VOICE, KIND_WORD_TIMING, DuplicateOutputError, OutputRepository

MIGRATIONS = Path(__file__).parents[4] / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
TEST_DATABASE_NAME = re.compile(r'^persist_e_[0-9a-f]+$')
WORKSPACE_ID = '00000000-0000-0000-0000-0000000000e1'
OTHER_WORKSPACE_ID = '00000000-0000-0000-0000-0000000000e2'


def _admin_dsn() -> str:
    configured = os.environ.get('M2_TEST_PG_DSN')
    if configured:
        return configured
    try:
        port = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True, stderr=subprocess.DEVNULL).strip().split(':')[-1]
    except Exception:
        port = '57027'
    return f'postgresql://m2test:m2test@127.0.0.1:{port}/postgres'


@dataclass
class Db:
    name: str
    dsn: str = field(repr=False)
    connections: list = field(default_factory=list)

    def connect(self) -> psycopg.Connection:
        connection = psycopg.connect(self.dsn, autocommit=True)
        self.connections.append(connection)
        return connection


@pytest.fixture
def disposable_db() -> Iterator[Db]:
    admin_dsn = _admin_dsn()
    try:
        psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5).close()
    except psycopg.OperationalError as exc:
        pytest.fail(f'BLOCKED_EXTERNAL: PostgreSQL test server is unreachable: {exc}')
    name = f'persist_e_{uuid.uuid4().hex}'
    assert TEST_DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if not admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]:
            pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.')
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    database = Db(name=name, dsn=make_conninfo(admin_dsn, dbname=name))
    try:
        yield database
    finally:
        for connection in database.connections:
            if not connection.closed:
                connection.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            assert TEST_DATABASE_NAME.fullmatch(name)
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s', (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (name,)).fetchone()[0] == 0


@pytest.fixture
def migrated_db(disposable_db: Db) -> Db:
    MigrationRunner(disposable_db.dsn, MIGRATIONS, is_test_env=True, expected_database_name=disposable_db.name).migrate_up()
    with disposable_db.connect() as connection:
        versions = [row[0] for row in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()]
        assert versions == list(range(1, 19))
        connection.execute("INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'persist-e', 'ACTIVE')", (WORKSPACE_ID,))
    return disposable_db


@pytest.fixture
def manager(migrated_db: Db) -> Iterator[TransactionManager]:
    transaction_manager = TransactionManager(migrated_db.dsn)
    try:
        yield transaction_manager
    finally:
        transaction_manager.close()


def _sha(n: int) -> str:
    return f'{n:064x}'


def _voice(n: int, *, voice_hash: str | None = None) -> VoiceTrack:
    return VoiceTrack(voice_artifact_ref=f'artifact:voice-{n}', script_version_id='script-v1', script_fingerprint=_sha(900), voice_hash=voice_hash or _sha(n), actual_duration_ms=4200, provider_model_voice_revision='kokoro:voice-a:1', usage_metrics={'characters': 120, 'nested': {'a': [1, 2]}}, warnings=('slow',), receipt_ref=f'receipt:voice-{n}')


def _timing(n: int, *, timing_ref: str | None = None) -> WordTimingRecord:
    return validate_word_timing({'script_version_id': 'script-v1', 'script_fingerprint': _sha(900), 'voice_hash': _sha(n), 'timing_artifact_ref': timing_ref or f'artifact:timing-{n}', 'words': [{'start_ms': 0, 'end_ms': 400, 'text': 'Xin', 'normalized_text': 'xin', 'confidence': 0.9}, {'start_ms': 400, 'end_ms': 900, 'text': 'chào'}], 'segment_boundaries': [{'start_ms': 0, 'end_ms': 900}], 'validation_report_ref': f'report:timing-{n}', 'voice_duration_ms': 1000, 'alignment_gaps': [{'after_index': 0, 'gap_ms': 0}]})


def _uow(manager: TransactionManager) -> PostgresVoiceUnitOfWork:
    return PostgresVoiceUnitOfWork(manager, workspace_id=WORKSPACE_ID)


def _count(db: Db, table: str) -> int:
    with db.connect() as connection:
        return connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0]


def _outbox_rows(db: Db) -> list:
    with db.connect() as connection:
        return connection.execute('SELECT event_id::text, event_name, aggregate_type, aggregate_id, aggregate_revision, producer, schema_version, workspace_id::text, payload FROM controlplane.cp_outbox_events ORDER BY recorded_at, event_id').fetchall()


def _event_payload(n: int) -> dict[str, str]:
    return {'voice_artifact_ref': f'artifact:voice-{n}', 'voice_hash': _sha(n), 'script_version_id': 'script-v1', 'receipt_ref': f'receipt:voice-{n}'}


def _dedup(n: int, revision: int = 1) -> str:
    return f'{WORKSPACE_ID}:VoiceReady:track-{n}:{revision}'


TABLES = ('cp_processed_media', 'cp_image_safety_assessments', 'cp_voice_tracks', 'cp_word_timings', 'cp_timing_validation_reports', 'cp_tts_invocation_records', 'cp_language_evidence', 'cp_audio_bed_results', 'cp_probe_reports', 'cp_analysis_results', 'cp_voice_receipts')
EXTRA_COLUMN = {'cp_voice_tracks': ('voice_hash', _sha(1)), 'cp_word_timings': ('timing_artifact_ref', 'artifact:timing-1')}


def _columns(db: Db, table: str) -> set[str]:
    with db.connect() as connection:
        rows = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'controlplane' AND table_name = %s", (table,)).fetchall()
    return {row[0] for row in rows}


def _seed(connection: psycopg.Connection, table: str) -> str:
    """Insert one row into a 0016 table and return an UPDATE statement for it."""
    if table == 'cp_voice_receipts':
        connection.execute("INSERT INTO controlplane.cp_voice_receipts (workspace_id, idempotency_key, request_hash, aggregate_ref, aggregate_revision) VALUES (%s, 'k', 'h', 'ref', 1)", (WORKSPACE_ID,))
        return "UPDATE controlplane.cp_voice_receipts SET request_hash = 'x'"
    columns, marks, params = '', '', [WORKSPACE_ID]
    if table in EXTRA_COLUMN:
        columns, marks = f', {EXTRA_COLUMN[table][0]}', ', %s'
        params.append(EXTRA_COLUMN[table][1])
    connection.execute(f"INSERT INTO controlplane.{table} (workspace_id, record_key, revision, payload{columns}) VALUES (%s, 'k', 1, '{{}}'::jsonb{marks})", params)
    return f'UPDATE controlplane.{table} SET revision = 2'


def test_persist_e_schema_matches_migration_0016(migrated_db: Db) -> None:
    for table in TABLES:
        assert _columns(migrated_db, table), table
    base = {'workspace_id', 'record_key', 'revision', 'payload'}
    assert base | {'voice_hash'} <= _columns(migrated_db, 'cp_voice_tracks')
    assert base | {'timing_artifact_ref'} <= _columns(migrated_db, 'cp_word_timings')
    with migrated_db.connect() as connection:
        triggers = connection.execute("SELECT event_object_table, trigger_name FROM information_schema.triggers WHERE trigger_schema = 'controlplane'").fetchall()
    assert set(TABLES) <= {table for table, name in triggers if name.endswith('_append_only')}


def test_persist_e_history_tables_reject_update_and_delete(migrated_db: Db) -> None:
    with migrated_db.connect() as connection:
        for table in TABLES:
            update = _seed(connection, table)
            with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
                connection.execute(update)
            with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
                connection.execute(f'DELETE FROM controlplane.{table}')
            assert connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0] == 1, table


def test_persist_e_database_unique_constraints(migrated_db: Db) -> None:
    with migrated_db.connect() as connection:
        _seed(connection, 'cp_voice_tracks')
        _seed(connection, 'cp_word_timings')
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute("INSERT INTO controlplane.cp_voice_tracks (workspace_id, record_key, revision, payload, voice_hash) VALUES (%s, 'other', 1, '{}'::jsonb, %s)", (WORKSPACE_ID, _sha(1)))
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute("INSERT INTO controlplane.cp_word_timings (workspace_id, record_key, revision, payload, timing_artifact_ref) VALUES (%s, 'other', 1, '{}'::jsonb, 'artifact:timing-1')", (WORKSPACE_ID,))


def test_persist_e_voice_round_trip_latest_and_revisions(manager: TransactionManager, migrated_db: Db) -> None:
    first, second = _voice(1), _voice(2)
    uow = _uow(manager)
    assert isinstance(uow.outputs, OutputRepository)
    with uow:
        stored = uow.outputs.append(KIND_VOICE, 'track-1', 1, first)
        assert (stored.kind, stored.key, stored.revision, stored.record) == (KIND_VOICE, 'track-1', 1, first)
        uow.outputs.append(KIND_VOICE, 'track-1', 2, second)
        uow.commit()
    latest = uow.outputs.latest(KIND_VOICE, 'track-1')
    assert latest is not None and latest.revision == 2
    assert latest.record == second and latest.record.to_payload() == second.to_payload()
    revisions = uow.outputs.revisions(KIND_VOICE, 'track-1')
    assert [item.revision for item in revisions] == [1, 2]
    assert [item.record for item in revisions] == [first, second]
    assert uow.outputs.latest(KIND_VOICE, 'missing') is None
    assert uow.outputs.revisions(KIND_VOICE, 'missing') == ()
    assert _count(migrated_db, 'cp_voice_tracks') == 2
    with migrated_db.connect() as connection:
        row = connection.execute('SELECT voice_hash, payload ->> %s FROM controlplane.cp_voice_tracks WHERE revision = 2', ('voice_artifact_ref',)).fetchone()
    assert row == (second.voice_hash, second.voice_artifact_ref)


def test_persist_e_word_timing_round_trip_latest_and_revisions(manager: TransactionManager, migrated_db: Db) -> None:
    first, second = _timing(1), _timing(2)
    uow = _uow(manager)
    with uow:
        uow.outputs.append(KIND_WORD_TIMING, 'track-1', 1, first)
        uow.outputs.append(KIND_WORD_TIMING, 'track-1', 2, second)
        uow.commit()
    latest = uow.outputs.latest(KIND_WORD_TIMING, 'track-1')
    assert latest is not None and latest.revision == 2
    assert latest.record == second and latest.record.words[1].text == 'chào'
    revisions = uow.outputs.revisions(KIND_WORD_TIMING, 'track-1')
    assert [item.record for item in revisions] == [first, second]
    assert _count(migrated_db, 'cp_word_timings') == 2
    with migrated_db.connect() as connection:
        row = connection.execute('SELECT timing_artifact_ref FROM controlplane.cp_word_timings WHERE revision = 1').fetchone()
    assert row == (first.timing_artifact_ref,)


def test_persist_e_outputs_are_scoped_by_workspace(manager: TransactionManager, migrated_db: Db) -> None:
    with migrated_db.connect() as connection:
        connection.execute("INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'other', 'ACTIVE')", (OTHER_WORKSPACE_ID,))
    with _uow(manager) as uow:
        uow.outputs.append(KIND_VOICE, 'track-1', 1, _voice(1))
        uow.commit()
    other = PostgresVoiceUnitOfWork(manager, workspace_id=OTHER_WORKSPACE_ID)
    assert other.outputs.latest(KIND_VOICE, 'track-1') is None
    assert other.outputs.revisions(KIND_VOICE, 'track-1') == ()
    assert _uow(manager).outputs.latest(KIND_VOICE, 'track-1') is not None


@pytest.mark.parametrize('kind, build, table', [(KIND_VOICE, _voice, 'cp_voice_tracks'), (KIND_WORD_TIMING, _timing, 'cp_word_timings')])
def test_persist_e_revision_must_advance_by_exactly_one(manager: TransactionManager, migrated_db: Db, kind: str, build, table: str) -> None:
    uow = _uow(manager)
    with uow:
        with pytest.raises(RevisionConflictError) as skipped:
            uow.outputs.append(kind, 'track-1', 2, build(1))
        assert skipped.value.current_revision == 0
        uow.outputs.append(kind, 'track-1', 1, build(1))
        with pytest.raises(RevisionConflictError) as repeated:
            uow.outputs.append(kind, 'track-1', 1, build(2))
        assert repeated.value.current_revision == 1
        with pytest.raises(RevisionConflictError):
            uow.outputs.append(kind, 'track-1', 3, build(3))
        uow.commit()
    assert _count(migrated_db, table) == 1


def test_persist_e_voice_hash_is_unique(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with uow:
        uow.outputs.append(KIND_VOICE, 'a', 1, _voice(1))
        with pytest.raises(DuplicateOutputError):
            uow.outputs.append(KIND_VOICE, 'b', 1, _voice(7, voice_hash=_sha(1)))
        with pytest.raises(DuplicateOutputError):
            uow.outputs.append(KIND_VOICE, 'a', 2, _voice(8, voice_hash=_sha(1)))
        uow.outputs.append(KIND_VOICE, 'b', 1, _voice(2))
        uow.commit()
    assert _count(migrated_db, 'cp_voice_tracks') == 2


def test_persist_e_timing_artifact_ref_is_unique(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with uow:
        uow.outputs.append(KIND_WORD_TIMING, 'a', 1, _timing(1))
        with pytest.raises(DuplicateOutputError):
            uow.outputs.append(KIND_WORD_TIMING, 'b', 1, _timing(7, timing_ref='artifact:timing-1'))
        with pytest.raises(DuplicateOutputError):
            uow.outputs.append(KIND_WORD_TIMING, 'a', 2, _timing(8, timing_ref='artifact:timing-1'))
        uow.outputs.append(KIND_WORD_TIMING, 'b', 1, _timing(2))
        uow.commit()
    assert _count(migrated_db, 'cp_word_timings') == 2


def test_persist_e_rejects_unsupported_kind_bad_arguments_and_wrong_record(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with uow:
        with pytest.raises(UnsupportedKindError):
            uow.outputs.append('receipt', 'k', 1, object())
        with pytest.raises(UnsupportedKindError):
            uow.outputs.latest('receipt', 'k')
        with pytest.raises(TypeError):
            uow.outputs.append(KIND_VOICE, 'k', 1, _timing(1))
        with pytest.raises(TypeError):
            uow.outputs.append(KIND_WORD_TIMING, 'k', 1, _voice(1))
        for key, revision in (('', 1), ('  ', 1), ('k', 0), ('k', True)):
            with pytest.raises(ValueError):
                uow.outputs.append(KIND_VOICE, key, revision, _voice(1))
        uow.commit()
    assert _count(migrated_db, 'cp_voice_tracks') == 0 and _count(migrated_db, 'cp_word_timings') == 0


def test_persist_e_commit_stores_output_and_outbox_on_one_connection(manager: TransactionManager, migrated_db: Db) -> None:
    voice, dedup = _voice(1), _dedup(1)
    uow = _uow(manager)
    with uow:
        uow.outputs.append(KIND_VOICE, 'track-1', 1, voice)
        event_id = uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), dedup)
        stored = uow.outputs.latest(KIND_VOICE, 'track-1')
        assert stored is not None and stored.record == voice
        assert uow.connection.execute('SELECT count(*) FROM controlplane.cp_voice_tracks').fetchone()[0] == 1
        assert uow.connection.execute('SELECT count(*) FROM controlplane.cp_outbox_events').fetchone()[0] == 1
        assert _count(migrated_db, 'cp_voice_tracks') == 0 and _outbox_rows(migrated_db) == []
        uow.commit()
        assert not uow.active
    assert event_id == str(uuid.uuid5(uuid.NAMESPACE_URL, dedup))
    assert _count(migrated_db, 'cp_voice_tracks') == 1
    rows = _outbox_rows(migrated_db)
    assert len(rows) == 1 and rows[0][0] == event_id
    assert rows[0][1:8] == ('VoiceReady', 'VoiceTrack', 'track-1', 1, 'E', 1, WORKSPACE_ID)
    assert rows[0][8] == _event_payload(1)


def test_persist_e_rollback_discards_output_and_outbox_together(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with pytest.raises(RuntimeError, match='boom'):
        with uow:
            uow.outputs.append(KIND_VOICE, 'track-1', 1, _voice(1))
            uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1))
            raise RuntimeError('boom')
    assert not uow.active
    with uow:
        uow.outputs.append(KIND_VOICE, 'track-2', 1, _voice(2))
        uow.outbox.append_event('VoiceReady', 'track-2', _event_payload(2), _dedup(2))
    with uow:
        uow.outputs.append(KIND_WORD_TIMING, 'track-3', 1, _timing(3))
        uow.rollback()
        assert not uow.active
    assert _count(migrated_db, 'cp_voice_tracks') == 0 and _count(migrated_db, 'cp_word_timings') == 0
    assert _outbox_rows(migrated_db) == []


def test_persist_e_failure_on_either_side_rolls_back_both(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with pytest.raises(ValueError):
        with uow:
            uow.outputs.append(KIND_VOICE, 'track-1', 1, _voice(1))
            uow.outbox.append_event('VoiceReady', 'track-1', {'api_token': 'x'}, _dedup(1))
            uow.commit()
    assert _count(migrated_db, 'cp_voice_tracks') == 0 and _outbox_rows(migrated_db) == []
    with uow:
        uow.outputs.append(KIND_VOICE, 'track-1', 1, _voice(1))
        uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1))
        uow.commit()
    with pytest.raises(DuplicateOutputError):
        with uow:
            uow.outbox.append_event('VoiceReady', 'track-2', _event_payload(2), _dedup(2))
            uow.outputs.append(KIND_VOICE, 'track-2', 1, _voice(1))
            uow.commit()
    assert _count(migrated_db, 'cp_voice_tracks') == 1 and len(_outbox_rows(migrated_db)) == 1


def test_persist_e_outbox_deduplicates_by_deduplication_id(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    with uow:
        first = uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1))
        assert uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1)) == first
        uow.commit()
    with uow:
        assert uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1)) == first
        second = uow.outbox.append_event('VoiceReady', 'track-1', _event_payload(1), _dedup(1, 2))
        uow.commit()
    assert second != first
    rows = _outbox_rows(migrated_db)
    assert len(rows) == 2 and sorted(row[4] for row in rows) == [1, 2]


def test_persist_e_unit_of_work_guards(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    assert isinstance(uow, IUnitOfWork) and isinstance(uow.outbox, IOutboxWriter)
    with pytest.raises(TransactionNotActiveError):
        uow.outputs.append(KIND_VOICE, 'k', 1, _voice(1))
    with pytest.raises(TransactionNotActiveError):
        uow.outbox.append_event('VoiceReady', 'k', _event_payload(1), _dedup(1))
    with pytest.raises(TransactionNotActiveError):
        uow.commit()
    with uow:
        with pytest.raises(TransactionAlreadyActiveError):
            uow.begin()
    unbound = PostgresVoiceUnitOfWork(manager)
    with pytest.raises(WorkspaceNotBoundError):
        unbound.begin()
    with pytest.raises(WorkspaceNotBoundError):
        unbound.outputs.latest(KIND_VOICE, 'k')
    with unbound.bind(workspace_id=WORKSPACE_ID):
        assert unbound.outputs.latest(KIND_VOICE, 'k') is None


@pytest.mark.parametrize('protocol', [VoiceUnitOfWork, MediaUnitOfWork])
def test_persist_e_unit_of_work_satisfies_voice_and_media_ports(manager: TransactionManager, protocol: type) -> None:
    uow = _uow(manager)
    required = {'outputs', 'outbox', 'commit', '__enter__', '__exit__'}
    assert set(protocol.__annotations__) <= required
    for name in required | set(protocol.__annotations__):
        assert hasattr(uow, name), name
    assert isinstance(uow.outputs, OutputRepository) and isinstance(uow.outbox, IOutboxWriter)
    with uow as entered:
        assert entered is uow and uow.active
        uow.commit()
    assert not uow.active


def test_persist_e_connections_return_to_pool(manager: TransactionManager, migrated_db: Db) -> None:
    uow = _uow(manager)
    for n in range(1, 13):
        if n % 3 == 0:
            with pytest.raises(RuntimeError):
                with uow:
                    uow.outputs.append(KIND_VOICE, f'track-{n}', 1, _voice(n))
                    raise RuntimeError('boom')
        else:
            with uow:
                uow.outputs.append(KIND_VOICE, f'track-{n}', 1, _voice(n))
                if n % 3 == 1:
                    uow.commit()
    assert _count(migrated_db, 'cp_voice_tracks') == 4
