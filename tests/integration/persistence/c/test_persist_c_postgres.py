'''PERSIST-C: kiểm adapter PostgreSQL của catalog trên PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test.'''
from __future__ import annotations

import dataclasses
import inspect
import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

from catalog.application.hooks import HookHistory, import_hook, update_hook_metadata
from catalog.application.usage import MediaUsageRecorder
from catalog.domain.hooks import HookKind
from catalog.domain.identity import CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus
from catalog.domain.renditions import Rendition, RenditionKind, RenditionSet
from catalog.persistence.assets import PostgresMediaAssetRepository
from catalog.persistence.hooks import PostgresHookHistory
from catalog.persistence.renditions import PostgresRenditionStore
from catalog.persistence.usage import PostgresMediaUsageRepository, media_usage_repository_factory
from catalog.ports.usage import MediaUsageRecord, UsageKind
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
PERSISTENCE_DIR = REPO_ROOT / 'src' / 'catalog' / 'persistence'
FP = CanonicalFingerprint('a' * 64)
FP2 = CanonicalFingerprint('b' * 64)
try:
    _port = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True, stderr=subprocess.DEVNULL).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)


def add_workspace(dsn: str) -> str:
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as seed:
        seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'w', 'ACTIVE'))
    return str(workspace_id)


@pytest.fixture
def db():
    name = f'persist_c_{uuid.uuid4().hex[:8]}'
    admin = psycopg.connect(PG_DSN, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        yield dsn, add_workspace(dsn)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        admin.close()


@pytest.fixture
def conn(db):
    with psycopg.connect(db[0]) as connection:
        yield connection


def count(connection, table, where='true', params=()):
    return connection.execute(f'SELECT count(*) FROM controlplane.{table} WHERE {where}', params).fetchone()[0]


def assert_rejected(connection, statement, params=()):
    with pytest.raises(psycopg.errors.RaiseException):
        connection.execute(statement, params)
    connection.rollback()


def make_entry(article='article-1', relation=ProvenanceRelation.HERO_IMAGE):
    return ProvenanceEntry(source_ref='source-1', article_ref=article, event_ref='event-1', original_locator=f'https://example.test/{article}/hero.jpg', observed_at='2026-10-18T00:00:00Z', relation=relation)


def make_asset(asset_id='asset-1', fingerprint=FP, article='article-1', kind=MediaKind.IMAGE):
    return MediaAsset(media_asset_id=asset_id, kind=kind, fingerprint=fingerprint, provenance=(make_entry(article),), rights=RightsAssessment(RightsStatus.UNKNOWN, ()), index_revision=1)


CATALOG_COLUMNS = {
    'cp_media_assets': {'media_asset_id', 'fingerprint', 'discovery_id', 'status', 'revision', 'payload', 'search_text'},
    'cp_media_provenance': {'provenance_id', 'media_asset_id', 'relation', 'payload'},
    'cp_media_renditions': {'rendition_ref', 'media_asset_id', 'kind', 'artifact_version_ref', 'source_artifact_version_ref', 'transformation_spec_revision', 'processor_version', 'lineage_refs'},
    'cp_hooks': {'hook_id', 'kind', 'current_revision', 'is_enabled', 'search_text'},
    'cp_hook_revisions': {'hook_id', 'revision', 'artifact_version_ref', 'payload'},
    'cp_media_usage': {'usage_id', 'completion_id', 'video_job_id', 'media_asset_id', 'role', 'usage_kind', 'rendition_ref', 'artifact_version_ref', 'selection_rationale'},
}


def test_schema_matches_catalog_migration(db):
    with psycopg.connect(db[0], autocommit=True) as connection:
        for table, expected in CATALOG_COLUMNS.items():
            rows = connection.execute('SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s', ('controlplane', table)).fetchall()
            assert expected <= {row[0] for row in rows}, table
        assert connection.execute('SELECT count(*) FROM pg_extension WHERE extname = %s', ('vector',)).fetchone()[0] == 0
        defs = dict(connection.execute('SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s', ('controlplane',)).fetchall())
        for index in ('cp_media_assets_fts_idx', 'cp_hooks_fts_idx'):
            assert 'USING gin' in defs[index], index
        checks = connection.execute('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass AND contype = %s', ('controlplane.cp_media_usage', 'c')).fetchall()
        assert any('production' in row[0] and 'technical' in row[0] for row in checks)


def test_asset_round_trip_and_lookups(conn, db):
    repo = PostgresMediaAssetRepository(conn, db[1])
    asset = make_asset()
    repo.save(asset, discovery_id='discovery-1')
    conn.commit()
    with psycopg.connect(db[0]) as other:
        fresh = PostgresMediaAssetRepository(other, db[1])
        assert fresh.get('asset-1') == asset
        assert fresh.find_by_fingerprint(FP) == asset
        assert fresh.find_by_discovery_id('discovery-1') == asset
        assert fresh.get('missing') is None
        assert fresh.find_by_fingerprint(FP2) is None
        assert fresh.find_by_discovery_id('missing') is None


def test_fingerprint_is_set_once(conn, db):
    repo = PostgresMediaAssetRepository(conn, db[1])
    pending = make_asset(fingerprint=None)
    repo.save(pending, discovery_id='discovery-1')
    assert repo.get('asset-1') == pending
    assert repo.find_by_fingerprint(FP) is None
    acquired = pending.with_fingerprint(FP)
    repo.save(acquired)
    assert repo.get('asset-1') == acquired
    assert repo.find_by_fingerprint(FP) == acquired
    assert repo.find_by_discovery_id('discovery-1') == acquired
    with pytest.raises(ValueError):
        repo.save(make_asset(fingerprint=FP2))
    with pytest.raises(ValueError):
        repo.save(make_asset(fingerprint=None))
    assert repo.get('asset-1') == acquired


def test_provenance_is_append_only_and_discovery_ids_accumulate(conn, db):
    repo = PostgresMediaAssetRepository(conn, db[1])
    first = make_asset()
    repo.save(first, discovery_id='discovery-1')
    second = first.with_provenance(make_entry('article-2'))
    repo.save(second, discovery_id='discovery-2')
    repo.save(second)
    assert repo.get('asset-1') == second
    assert repo.get('asset-1').provenance == (make_entry('article-1'), make_entry('article-2'))
    assert repo.find_by_discovery_id('discovery-1') == second
    assert repo.find_by_discovery_id('discovery-2') == second
    assert count(conn, 'cp_media_provenance') == 2
    with pytest.raises(ValueError):
        repo.save(make_asset('asset-2', FP2), discovery_id='discovery-1')
    assert count(conn, 'cp_media_assets') == 1


def test_fts_search_returns_only_matching_assets(conn, db):
    repo = PostgresMediaAssetRepository(conn, db[1])
    alpha = make_asset('asset-a', FP, article='alpha-story')
    beta = make_asset('asset-b', FP2, article='beta-story')
    repo.save(alpha)
    repo.save(beta)
    assert repo.search('alpha') == [alpha]
    assert repo.search('ALPHA') == [alpha]
    assert repo.search('story') == [alpha, beta]
    assert repo.search('alpha beta') == []
    assert repo.search('   ') == []
    conn.execute('SET LOCAL enable_seqscan = off')
    plan = ' '.join(row[0] for row in conn.execute('''EXPLAIN SELECT 1 FROM controlplane.cp_media_assets WHERE string_to_array(search_text, ' ') @> ARRAY['alpha']''').fetchall())
    assert 'cp_media_assets_fts_idx' in plan


def test_workspaces_are_isolated(conn, db):
    repo = PostgresMediaAssetRepository(conn, db[1])
    repo.save(make_asset(), discovery_id='discovery-1')
    other = PostgresMediaAssetRepository(conn, add_workspace(db[0]))
    assert repo.get('asset-1') == make_asset()
    assert other.get('asset-1') is None
    assert other.find_by_fingerprint(FP) is None
    assert other.find_by_discovery_id('discovery-1') is None
    assert other.search('image') == []
    other.save(make_asset(), discovery_id='discovery-1')
    assert count(conn, 'cp_media_assets') == 2


def make_rendition(ref='rendition-1', kind=RenditionKind.ORIGINAL, revision='3'):
    return Rendition(rendition_ref=ref, media_asset_id='asset-1', kind=kind, artifact_version_ref=f'av-{ref}', source_artifact_version_ref='av-source', transformation_spec_revision=revision, processor_version='ffmpeg-1', lineage=('av-source',))


def test_renditions_round_trip_and_are_immutable(conn, db):
    store = PostgresRenditionStore(conn, db[1])
    original = make_rendition()
    thumb = make_rendition('rendition-2', RenditionKind.THUMBNAIL)
    store.add(original)
    store.add(thumb)
    store.add(original)
    conn.commit()
    assert store.list_for_asset('asset-1') == RenditionSet('asset-1', (original, thumb))
    assert store.get('rendition-2') == thumb
    assert store.get('missing') is None
    assert count(conn, 'cp_media_renditions') == 2
    with pytest.raises(ValueError):
        store.add(make_rendition(revision='4'))
    with pytest.raises(ValueError):
        store.add(make_rendition('rendition-3', revision='v1'))
    assert_rejected(conn, 'UPDATE controlplane.cp_media_renditions SET processor_version = %s', ('x',))
    assert_rejected(conn, 'DELETE FROM controlplane.cp_media_renditions')
    assert store.list_for_asset('asset-1') == RenditionSet('asset-1', (original, thumb))


def test_hook_history_round_trip_and_matches_in_memory(conn, db):
    history = PostgresHookHistory(conn, db[1])
    arguments = dict(hook_id='hook-1', kind=HookKind.VISUAL_HOOK, artifact_version_ref='av-1', tags=('Sports', 'goal'), description='Late winner', note='check', technical_metadata=(('fps', '30'),))
    first = import_hook(history, **arguments)
    assert history.get('hook-1', 1) == first
    second = update_hook_metadata(history, 'hook-1', 1, tags=('sports',), enabled=False)
    conn.commit()
    with psycopg.connect(db[0]) as other:
        reread = PostgresHookHistory(other, db[1])
        assert reread.get('hook-1', 1) == first
        assert reread.get('hook-1', 2) == second
        assert reread.latest('hook-1') == second
    memory = HookHistory()
    memory_first = import_hook(memory, **arguments)
    memory_second = update_hook_metadata(memory, 'hook-1', 1, tags=('sports',), enabled=False)
    assert (memory_first, memory_second) == (first, second)
    for bad in (0, 3, True, '1', None):
        with pytest.raises(KeyError):
            history.get('hook-1', bad)
    with pytest.raises(KeyError):
        history.latest('missing')
    with pytest.raises(RevisionConflictError) as stale:
        update_hook_metadata(history, 'hook-1', 1, note='stale')
    assert stale.value.current_revision == 2
    with pytest.raises(RevisionConflictError) as skipped:
        history.append(dataclasses.replace(second, revision=4))
    assert skipped.value.current_revision == 2


def test_hook_history_signatures_match_hook_history():
    for name in ('get', 'latest', 'append'):
        expected = list(inspect.signature(getattr(HookHistory, name)).parameters)
        assert list(inspect.signature(getattr(PostgresHookHistory, name)).parameters) == expected, name


def test_hook_revisions_are_immutable_and_searchable(conn, db):
    history = PostgresHookHistory(conn, db[1])
    first = import_hook(history, hook_id='hook-1', kind=HookKind.VISUAL_HOOK, artifact_version_ref='av-1', tags=('sports',), description='Late winner')
    assert history.search('late winner') == [first]
    disabled = update_hook_metadata(history, 'hook-1', 1, enabled=False)
    audio = import_hook(history, hook_id='hook-2', kind=HookKind.AUDIO_HOOK, artifact_version_ref='av-2', tags=('sports',), description='Crowd roar')
    conn.commit()
    assert history.search('sports') == [audio]
    assert history.search('sports', enabled_only=False) == [disabled, audio]
    assert history.search('late winner', enabled_only=False) == [disabled]
    assert history.search('late roar', enabled_only=False) == []
    assert history.search('') == []
    assert count(conn, 'cp_hook_revisions') == 3
    assert_rejected(conn, 'UPDATE controlplane.cp_hook_revisions SET artifact_version_ref = %s', ('x',))
    assert_rejected(conn, 'DELETE FROM controlplane.cp_hook_revisions')
    assert count(conn, 'cp_hook_revisions') == 3
    assert history.latest('hook-1') == disabled


def make_usage(asset_id='asset-1', role='hero', kind=UsageKind.production, completion_id='completion-1'):
    return MediaUsageRecord(completion_id=completion_id, video_job_id='job-1', media_asset_id=asset_id, role=role, usage_kind=kind, rendition_ref='rendition-1', selection_rationale='best match')


def test_usage_is_unique_and_replay_does_not_duplicate(conn, db):
    repo = PostgresMediaUsageRepository(conn, db[1])
    assert repo.exists('completion-1', 'asset-1', 'hero', UsageKind.production) is False
    repo.add(make_usage())
    repo.add(make_usage())
    assert repo.exists('completion-1', 'asset-1', 'hero', UsageKind.production) is True
    assert repo.exists('completion-1', 'asset-1', 'hero', UsageKind.technical) is False
    repo.add(make_usage(kind=UsageKind.technical))
    assert count(conn, 'cp_media_usage') == 2
    conn.commit()
    insert = 'INSERT INTO controlplane.cp_media_usage (workspace_id, usage_id, completion_id, video_job_id, media_asset_id, role, usage_kind) VALUES (%s, %s, %s, %s, %s, %s, %s)'
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(insert, (uuid.UUID(db[1]), 'other-usage', 'completion-1', 'job-1', 'asset-1', 'hero', 'production'))
    conn.rollback()
    assert_rejected(conn, 'UPDATE controlplane.cp_media_usage SET role = %s', ('x',))
    assert_rejected(conn, 'DELETE FROM controlplane.cp_media_usage')
    assert count(conn, 'cp_media_usage') == 2


def test_only_production_rows_are_counted(conn, db):
    repo = PostgresMediaUsageRepository(conn, db[1])
    repo.add(make_usage())
    repo.add(make_usage(role='inline'))
    repo.add(make_usage(kind=UsageKind.technical))
    repo.add(make_usage('asset-2', kind=UsageKind.technical))
    assert repo.count_production('asset-1') == 2
    assert repo.count_production('asset-2') == 0
    assert repo.count_production('missing') == 0
    assert count(conn, 'cp_media_usage') == 4


MANIFEST_REQUEST = {'video_job_id': 'job-1', 'media_usage_manifest': [{'media_asset_id': 'asset-1', 'role': 'hero'}, {'media_asset_id': 'asset-2', 'role': 'inline', 'rendition_ref': 'rendition-1'}]}


def _no_second_connection(*args, **kwargs):
    raise AssertionError('adapter opened a second connection')


def test_recorder_shares_the_completion_transaction(db, monkeypatch):
    dsn, workspace_id = db
    manager = TransactionManager(dsn, pool_max_size=2)
    recorder = MediaUsageRecorder(media_usage_repository_factory(workspace_id))
    try:
        with psycopg.connect(dsn, autocommit=True) as observer:
            with pytest.raises(RuntimeError, match='after add'):
                with manager.unit_of_work() as uow:
                    assert media_usage_repository_factory(workspace_id)(uow)._connection is uow.connection
                    with monkeypatch.context() as patched:
                        patched.setattr(psycopg, 'connect', _no_second_connection)
                        patched.setattr(psycopg.Connection, 'connect', _no_second_connection)
                        assert recorder.record_production_usage(uow, 'completion-1', MANIFEST_REQUEST) == 2
                    assert count(observer, 'cp_media_usage') == 0
                    raise RuntimeError('after add')
            assert count(observer, 'cp_media_usage') == 0
            with manager.unit_of_work() as uow:
                assert recorder.record_production_usage(uow, 'completion-1', MANIFEST_REQUEST) == 2
            assert count(observer, 'cp_media_usage') == 2
            with manager.unit_of_work() as uow:
                assert recorder.record_production_usage(uow, 'completion-1', MANIFEST_REQUEST) == 0
                assert recorder.record_technical_usage(uow, make_usage(kind=UsageKind.technical)) is True
            assert count(observer, 'cp_media_usage') == 3
            assert count(observer, 'cp_media_usage', 'usage_kind = %s', ('production',)) == 2
    finally:
        manager.close()


def test_adapter_source_has_no_ddl_connection_or_transaction_control():
    files = list(PERSISTENCE_DIR.rglob('*.py'))
    assert files
    text = '\n'.join(path.read_text(encoding='utf-8') for path in files)
    for banned in ('connect(', 'ConnectionPool', 'TransactionManager', '.commit(', '.rollback(', 'CREATE TABLE', 'ALTER TABLE', 'CREATE EXTENSION', 'CREATE INDEX', 'vector', 'from src.', 'import src'):
        assert banned not in text, banned
