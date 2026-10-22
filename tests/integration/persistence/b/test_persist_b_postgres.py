"""PostgreSQL integration tests for module B persistence adapters (PERSIST-B, REQ-B-CONV-02)."""
from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from ingestion import persistence
from ingestion.application.ports import (
    ArticleRepository,
    EventRepository,
    RecordRepository,
    ResolutionRepository,
    UnitOfWork,
)
from ingestion.domain.article import Article, ArticleRevision

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
DB_NAME = re.compile(r'^persist_b_[0-9a-f]+$')

ALLOWED_TABLES = frozenset({
    'cp_articles',
    'cp_article_revisions',
    'cp_collected_document_resolutions',
    'cp_dedup_evidence',
    'cp_events',
    'cp_event_link_candidates',
    'cp_event_updates',
    'cp_event_update_candidates',
    'cp_outbox_events',
})


@pytest.fixture
def migrated_dsn() -> Iterator[str]:
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.')
    name = f'persist_b_{uuid.uuid4().hex}'
    assert DB_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if not admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]:
            pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.')
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as connection:
            versions = [row[0] for row in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()]
            assert versions == list(range(1, 19)), f'unexpected applied migrations: {versions}'
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s', (name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (name,)).fetchone()[0] == 0


@pytest.fixture
def workspace_id(migrated_dsn: str) -> str:
    wid = str(uuid.uuid4())
    with psycopg.connect(migrated_dsn, autocommit=True) as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
            (wid, 'PERSIST-B test workspace', 'ACTIVE'),
        )
    return wid


@pytest.fixture
def manager(migrated_dsn: str) -> Iterator[TransactionManager]:
    mgr = TransactionManager(migrated_dsn)
    try:
        yield mgr
    finally:
        mgr.close()


def new_uow(manager: TransactionManager, workspace_id: str) -> UnitOfWork:
    assert hasattr(persistence, 'PostgresIngestionUnitOfWork'), 'ingestion.persistence must export PostgresIngestionUnitOfWork'
    return persistence.PostgresIngestionUnitOfWork(manager, workspace_id=workspace_id)


def count(dsn: str, table: str, where: str = 'true', params: tuple[Any, ...] = ()) -> int:
    assert table in ALLOWED_TABLES, f'untrusted table {table}'
    query = sql.SQL('SELECT count(*) FROM controlplane.{} WHERE ').format(sql.Identifier(table)) + sql.SQL(where)
    with psycopg.connect(dsn, autocommit=True) as conn:
        return int(conn.execute(query, params).fetchone()[0])


def make_revision(article_id: str, number: int, fingerprint: str, **overrides: Any) -> ArticleRevision:
    data: dict[str, Any] = {
        'article_revision_id': f'{article_id}-r{number}',
        'article_id': article_id,
        'revision_number': number,
        'title': f'Title {number}',
        'normalized_text': f'Normalized text {number}',
        'source_id': 'src-1',
        'source_revision': 1,
        'collection_run_id': 'run-1',
        'collected_document_id': f'doc-{number}',
        'requested_url': f'https://example.com/{number}',
        'final_url': f'https://example.com/{number}',
        'provenance_chain': ({'step': 'fetch'},),
        'raw_snapshot_ref': f'snap-{number}',
        'published_at': '2026-10-22T00:00:00Z',
        'published_at_confidence': 'HIGH',
        'fetched_at': '2026-10-22T00:00:00Z',
        'topic': 'tech',
        'topic_uncertain': False,
        'exact_fingerprint': fingerprint,
        'media_discovery_refs': ('m1',),
        'extractor_version': '1.0',
        'normalizer_version': '1.0',
        'is_complete': True,
        'uncertain_fields': (),
    }
    data.update(overrides)
    return ArticleRevision(**data)


def make_article(article_id: str, identity_key: str, revisions: tuple[ArticleRevision, ...] = ()) -> Article:
    return Article(
        article_id=article_id,
        identity_key=identity_key,
        representative_source_id='src-1',
        revisions=revisions,
    )


def test_migrated_schema_matches_expected_version_and_tables(migrated_dsn: str) -> None:
    expected_tables = (
        'cp_articles',
        'cp_article_revisions',
        'cp_collected_document_resolutions',
        'cp_dedup_evidence',
        'cp_events',
        'cp_event_link_candidates',
        'cp_event_updates',
        'cp_event_update_candidates',
    )
    with psycopg.connect(migrated_dsn, autocommit=True) as conn:
        for tbl in expected_tables:
            regclass = conn.execute('SELECT to_regclass(%s)', (f'controlplane.{tbl}',)).fetchone()[0]
            assert regclass == f'controlplane.{tbl}', f'missing table controlplane.{tbl}'


def test_schema_constraints_and_indexes(migrated_dsn: str) -> None:
    with psycopg.connect(migrated_dsn, autocommit=True) as conn:
        for tbl in ('cp_article_revisions', 'cp_dedup_evidence', 'cp_event_updates'):
            triggers = [
                row[0]
                for row in conn.execute(
                    'SELECT trigger_name FROM information_schema.triggers WHERE event_object_schema = %s AND event_object_table = %s',
                    ('controlplane', tbl),
                ).fetchall()
            ]
            assert any('append_only' in t for t in triggers), f'missing append-only trigger on {tbl}: {triggers}'

        indexes = [
            row[0]
            for row in conn.execute(
                'SELECT indexname FROM pg_indexes WHERE schemaname = %s',
                ('controlplane',),
            ).fetchall()
        ]
        for expected_idx in ('cp_articles_fingerprint_idx', 'cp_dedup_evidence_document_idx', 'cp_event_updates_event_idx'):
            assert expected_idx in indexes, f'missing index {expected_idx}: {indexes}'


def test_unit_of_work_exposes_expected_repositories_and_outbox(manager: TransactionManager, workspace_id: str) -> None:
    uow = new_uow(manager, workspace_id)
    assert isinstance(uow, UnitOfWork)
    assert hasattr(uow, 'articles') and isinstance(uow.articles, ArticleRepository)
    assert hasattr(uow, 'resolutions') and isinstance(uow.resolutions, ResolutionRepository)
    assert hasattr(uow, 'events') and isinstance(uow.events, EventRepository)
    assert hasattr(uow, 'records') and isinstance(uow.records, RecordRepository)
    assert hasattr(uow, 'outbox')


def test_article_round_trip_and_lookups(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    rev1 = make_revision('art-1', 1, 'fp-1')
    rev2 = make_revision('art-1', 2, 'fp-2')
    art = make_article('art-1', 'idk-1', (rev1, rev2))
    with new_uow(manager, workspace_id) as uow:
        uow.articles.save(art)
        uow.commit()

    with new_uow(manager, workspace_id) as uow:
        loaded = uow.articles.get('art-1')
        assert loaded == art
        assert uow.articles.find_by_identity_key('idk-1') == art
        assert uow.articles.find_by_exact_fingerprint('fp-1') == art
        assert uow.articles.find_by_exact_fingerprint('fp-2') == art
        assert uow.articles.find_by_exact_fingerprint('nope') is None
        all_articles = uow.articles.list_all()
        assert len(all_articles) == 1 and all_articles[0] == art
    assert count(migrated_dsn, 'cp_article_revisions') == 2

    rev3 = make_revision('art-1', 3, 'fp-3')
    art_with_3 = art.with_revision(rev3)
    with new_uow(manager, workspace_id) as uow:
        uow.articles.save(art_with_3)
        uow.commit()
    assert count(migrated_dsn, 'cp_article_revisions') == 3
    with new_uow(manager, workspace_id) as uow:
        loaded_3 = uow.articles.get('art-1')
        assert loaded_3 is not None and len(loaded_3.revisions) == 3

    bad_rev1 = replace(rev1, title='tampered title')
    bad_art = Article(article_id='art-1', identity_key='idk-1', representative_source_id='src-1', revisions=(bad_rev1, rev2, rev3))
    with pytest.raises(ValueError):
        with new_uow(manager, workspace_id) as uow:
            uow.articles.save(bad_art)


def test_resolution_round_trip_and_unique_key(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    res1 = {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'state': 'ACCEPTED'}
    with new_uow(manager, workspace_id) as uow:
        uow.resolutions.save(res1)
        uow.commit()

    with new_uow(manager, workspace_id) as uow:
        assert uow.resolutions.get('doc-1', 'dedup-policy-r1') == res1
        assert uow.resolutions.get('doc-1', 'dedup-policy-r2') is None

    res2 = {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'state': 'REJECTED'}
    with new_uow(manager, workspace_id) as uow:
        uow.resolutions.save(res2)
        uow.commit()
    assert count(migrated_dsn, 'cp_collected_document_resolutions') == 1
    with new_uow(manager, workspace_id) as uow:
        assert uow.resolutions.get('doc-1', 'dedup-policy-r1') == res2

    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(migrated_dsn, autocommit=True) as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_collected_document_resolutions (workspace_id, collected_document_id, dedup_policy_revision, payload) VALUES (%s, %s, %s, %s)',
                (workspace_id, 'doc-1', 'dedup-policy-r1', json.dumps(res1)),
            )


def test_event_round_trip(manager: TransactionManager, workspace_id: str) -> None:
    ev1 = {'event_id': 'ev-1', 'revision': 1, 'title': 't'}
    with new_uow(manager, workspace_id) as uow:
        uow.events.save(ev1)
        uow.commit()
    ev2 = {'event_id': 'ev-1', 'revision': 2, 'title': 't-updated'}
    with new_uow(manager, workspace_id) as uow:
        uow.events.save(ev2)
        uow.commit()
    with new_uow(manager, workspace_id) as uow:
        loaded = uow.events.get('ev-1')
        assert loaded is not None and loaded['revision'] == 2 and loaded['title'] == 't-updated'
        all_events = uow.events.list_all()
        assert len(all_events) == 1 and all_events[0]['revision'] == 2


def test_record_kinds_map_to_four_tables(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    rec1 = {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'match': 'exact'}
    rec2 = {'k': 'v'}
    rec3 = {'event_id': 'ev-1', 'k': 'v'}
    rec4 = {'k': 'v'}
    with new_uow(manager, workspace_id) as uow:
        uow.records.put('dedup_evidence', 'evid-1', rec1)
        uow.records.put('event_link_candidate', 'elc-1', rec2)
        uow.records.put('event_update', 'eu-1', rec3)
        uow.records.put('event_update_candidate', 'euc-1', rec4)
        uow.commit()

    assert count(migrated_dsn, 'cp_dedup_evidence') == 1
    assert count(migrated_dsn, 'cp_event_link_candidates') == 1
    assert count(migrated_dsn, 'cp_event_updates') == 1
    assert count(migrated_dsn, 'cp_event_update_candidates') == 1

    with new_uow(manager, workspace_id) as uow:
        assert uow.records.get('dedup_evidence', 'evid-1') == rec1
        assert uow.records.list('dedup_evidence') == (rec1,)
        assert uow.records.get('event_link_candidate', 'elc-1') == rec2
        assert uow.records.list('event_link_candidate') == (rec2,)
        assert uow.records.get('event_update', 'eu-1') == rec3
        assert uow.records.list('event_update') == (rec3,)
        assert uow.records.get('event_update_candidate', 'euc-1') == rec4
        assert uow.records.list('event_update_candidate') == (rec4,)

    with pytest.raises(ValueError):
        with new_uow(manager, workspace_id) as uow:
            uow.records.put('unknown_kind', 'x-1', {'k': 'v'})
    with pytest.raises(ValueError):
        with new_uow(manager, workspace_id) as uow:
            uow.records.get('unknown_kind', 'x-1')
    with pytest.raises(ValueError):
        with new_uow(manager, workspace_id) as uow:
            uow.records.list('unknown_kind')


def test_article_and_outbox_commit_together(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    art = make_article('art-1', 'idk-1', (make_revision('art-1', 1, 'fp-1'),))
    with new_uow(manager, workspace_id) as uow:
        uow.articles.save(art)
        event_id = uow.outbox.append_event('IngestionArticleResolved', 'art-1', {'article_id': 'art-1'}, 'dedup-1')
        assert count(migrated_dsn, 'cp_articles') == 0
        assert count(migrated_dsn, 'cp_outbox_events') == 0
        uow.commit()

    assert count(migrated_dsn, 'cp_articles') == 1
    assert count(migrated_dsn, 'cp_outbox_events', "aggregate_id = 'art-1'") == 1
    assert uuid.UUID(event_id)


def test_outbox_deduplication_id_is_idempotent(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    with new_uow(manager, workspace_id) as uow:
        e1 = uow.outbox.append_event('TypeA', 'agg-1', {'a': 1}, 'dedup-idemp')
        e2 = uow.outbox.append_event('TypeA', 'agg-1', {'a': 1}, 'dedup-idemp')
        assert e1 == e2
        uow.commit()

    with new_uow(manager, workspace_id) as uow:
        e3 = uow.outbox.append_event('TypeA', 'agg-1', {'a': 1}, 'dedup-idemp')
        assert e3 == e1
        uow.commit()

    assert count(migrated_dsn, 'cp_outbox_events') == 1


def test_error_after_aggregate_write_rolls_back_aggregate_and_outbox(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    art = make_article('art-boom', 'idk-boom', (make_revision('art-boom', 1, 'fp-boom'),))
    with pytest.raises(RuntimeError, match='boom'):
        with new_uow(manager, workspace_id) as uow:
            uow.articles.save(art)
            uow.outbox.append_event('TypeBoom', 'art-boom', {'k': 'v'}, 'dedup-boom')
            raise RuntimeError('boom')

    assert count(migrated_dsn, 'cp_articles') == 0
    assert count(migrated_dsn, 'cp_article_revisions') == 0
    assert count(migrated_dsn, 'cp_outbox_events') == 0


def test_exit_without_commit_rolls_back(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    art = make_article('art-nocommit', 'idk-nocommit', (make_revision('art-nocommit', 1, 'fp-nocommit'),))
    with new_uow(manager, workspace_id) as uow:
        uow.articles.save(art)
        uow.outbox.append_event('TypeNoCommit', 'art-nocommit', {'k': 'v'}, 'dedup-nocommit')

    assert count(migrated_dsn, 'cp_articles') == 0
    assert count(migrated_dsn, 'cp_outbox_events') == 0


def test_unsafe_outbox_payload_rolls_back_aggregate(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    art = make_article('art-unsafe', 'idk-unsafe', (make_revision('art-unsafe', 1, 'fp-unsafe'),))
    with pytest.raises(ValueError):
        with new_uow(manager, workspace_id) as uow:
            uow.articles.save(art)
            uow.outbox.append_event('X', 'art-unsafe', {'password': 'x'}, 'dedup-unsafe')

    assert count(migrated_dsn, 'cp_articles') == 0
    assert count(migrated_dsn, 'cp_outbox_events') == 0


def test_append_only_tables_reject_update(manager: TransactionManager, workspace_id: str, migrated_dsn: str) -> None:
    rev1 = make_revision('art-app', 1, 'fp-app-1')
    rev2 = make_revision('art-app', 2, 'fp-app-2')
    art = make_article('art-app', 'idk-app', (rev1, rev2))
    with new_uow(manager, workspace_id) as uow:
        uow.articles.save(art)
        uow.records.put('dedup_evidence', 'evid-app', {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'match': 'exact'})
        uow.records.put('event_update', 'eu-app', {'event_id': 'ev-app', 'k': 'v'})
        uow.commit()

    with psycopg.connect(migrated_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute("UPDATE controlplane.cp_article_revisions SET payload='{}'::jsonb")
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute('DELETE FROM controlplane.cp_article_revisions')
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute("UPDATE controlplane.cp_dedup_evidence SET payload='{}'::jsonb")
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute('DELETE FROM controlplane.cp_dedup_evidence')
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute("UPDATE controlplane.cp_event_updates SET payload='{}'::jsonb")
        with pytest.raises(psycopg.Error, match='append-only'):
            conn.execute('DELETE FROM controlplane.cp_event_updates')

    with pytest.raises(ValueError, match='append-only'):
        with new_uow(manager, workspace_id) as uow:
            uow.records.put('dedup_evidence', 'evid-app', {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'match': 'different'})

    with new_uow(manager, workspace_id) as uow:
        uow.records.put('dedup_evidence', 'evid-app', {'collected_document_id': 'doc-1', 'dedup_policy_revision': 'dedup-policy-r1', 'match': 'exact'})
        uow.commit()


def test_persistence_package_has_no_ddl_or_package_a_dependency() -> None:
    pkg_dir = REPO_ROOT / 'src' / 'ingestion' / 'persistence'
    files = list(pkg_dir.rglob('*.py'))
    assert len(files) >= 3, f'expected at least 3 files in {pkg_dir}, found {len(files)}'
    content = ' '.join(f.read_text(encoding='utf-8') for f in files)
    for forbidden in ('CREATE TABLE', 'ALTER TABLE', 'from src.', 'import src.', 'source_ingestion', 'cp_collected_document_package', ' JOIN '):
        assert forbidden not in content, f'forbidden substring {forbidden!r} found'
