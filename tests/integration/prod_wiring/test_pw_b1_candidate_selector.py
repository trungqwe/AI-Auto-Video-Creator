"""PW-B1: PostgresCandidateSelector chọn ứng viên từ bảng B cho lô trên PostgreSQL thật.

coveredIds: PW-B1-01, CT-ORC-002, CT-CNT-001
"""
from __future__ import annotations

import itertools
import pathlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from controlplane.application.orchestration.batch_allocation import AllocateJobService
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from controlplane.infrastructure.db.uow import TransactionManager
from ingestion.application.candidate_selector import HotnessWeights, PostgresCandidateSelector
from ingestion.application.production_deps import ResolveDepsFactory
from ingestion.application.resolve_document import resolve_collected_document
from ingestion.application.source_set import MULTI_ARTICLE_EVENT, SINGLE_ARTICLE, build_source_set
from ingestion.persistence.uow import PostgresIngestionUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SELECTOR_SOURCE = ROOT / 'src' / 'ingestion' / 'application' / 'candidate_selector.py'
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
SOURCE_TIERS = {'src-a': 'tier_1', 'src-b': 'tier_2', 'src-c': 'tier_3'}
NEWS = (('hot', 'src-a', 2), ('mid', 'src-b', 30), ('old', 'src-c', 200))


@pytest.fixture
def manager(pw_database: Any):
    pool = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield pool
    finally:
        pool.close()


def new_uow(manager, db):
    return PostgresIngestionUnitOfWork(manager, workspace_id=db.workspace_id)


def seed_sources(db):
    with db.connect() as conn:
        for source_id, tier in SOURCE_TIERS.items():
            conn.execute(
                'INSERT INTO controlplane.cp_sources (workspace_id, source_id, canonical_locator, status, revision, payload) VALUES (%s, %s, %s, %s, %s, %s)',
                (db.workspace_id, source_id, f'https://{source_id}.example.invalid/feed', 'ACTIVE', 1, Jsonb({'tier': tier})),
            )


def package(name, source_id, hours_ago):
    published = (NOW - timedelta(hours=hours_ago)).isoformat()
    url = f'https://{source_id}.example.invalid/{name}'
    return {
        'collected_document_id': f'doc-{name}',
        'source_id': source_id,
        'source_revision': 1,
        'collection_run_id': 'run-b1',
        'requested_url': url,
        'final_url': url,
        'fetched_at': published,
        'http_observation': {'status': 200, 'media_type': 'text/html'},
        'extraction_disposition': 'SUCCESS',
        'extractor_version': '1.0.0',
        'provenance_chain': [{'step': 'final_fetch', 'url': url}],
        'warnings': [],
        'content_eligibility': 'candidate',
        'published_at_candidate': published,
        'extracted_content_candidate': {'title': f'Tin {name}', 'text': ' '.join(f'{name}{i}' for i in range(60)), 'language': 'en'},
        'media_discoveries': [],
    }


def resolve_news(manager, db):
    counter = itertools.count(1)
    factory = ResolveDepsFactory(
        uow_factory=lambda: new_uow(manager, db),
        connection_factory=db.connect,
        workspace_id=db.workspace_id,
        id_factory=lambda: f'b1-{next(counter)}',
    )
    for name, source_id, hours_ago in NEWS:
        deps = factory.deps_for_call()
        resolve_collected_document(
            package(name, source_id, hours_ago),
            factory.dedup_policy,
            deps.uow,
            deps.tier_lookup,
            lambda: NOW,
            factory.id_factory,
        )


def found_articles(db) -> dict:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT r.payload->>'collected_document_id', r.article_id, r.payload->>'article_revision_id' "
            "FROM controlplane.cp_article_revisions r WHERE r.workspace_id = %s",
            (db.workspace_id,),
        ).fetchall()
    return {doc_id.removeprefix('doc-'): (article_id, revision_id) for doc_id, article_id, revision_id in rows}


@pytest.fixture
def world(manager, pw_database):
    seed_sources(pw_database)
    resolve_news(manager, pw_database)
    found = found_articles(pw_database)
    assert set(found) == {'hot', 'mid', 'old'}
    return found

def make_selector(manager, db, **overrides):
    options = {
        'connection_factory': db.connect,
        'uow_factory': lambda: new_uow(manager, db),
        'workspace_id': db.workspace_id,
        'clock': lambda: NOW,
    }
    options.update(overrides)
    return PostgresCandidateSelector(**options)


class SpyBuilder:
    def __init__(self):
        self.calls = []

    def __call__(self, production_mode, subject_id, uow):
        self.calls.append((production_mode, subject_id))
        return build_source_set(production_mode, subject_id, uow)


def seed_batch(db, batch_id, target):
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
            (batch_id, db.workspace_id, 'RUNNING', target),
        )


def allocate(db, selector, batch_id, count, mode=SINGLE_ARTICLE):
    service = AllocateJobService(db.connect, selector, workspace_id=db.workspace_id)
    results = []
    for n in range(1, count + 1):
        request = {
            'input_refs': [
                {'ref_type': 'production_batch', 'ref_id': batch_id},
                {'ref_type': 'allocation_job', 'ref_id': f'{batch_id}:job:{n}'},
                {'ref_type': 'production_mode', 'ref_id': mode},
            ]
        }
        res = service(request, None)
        results.append({ref['ref_type']: ref['ref_id'] for ref in res['output_refs']})
    return results


def stored(db, batch_id):
    with db.connect() as conn:
        return conn.execute(
            'SELECT k.candidate_ref, j.snapshot_ref, k.source_set_ref '
            'FROM controlplane.cp_job_candidates k '
            'JOIN controlplane.cp_video_jobs j ON j.workspace_id = k.workspace_id AND j.job_id = k.job_id '
            'WHERE k.workspace_id = %s AND k.batch_id = %s ORDER BY k.job_id',
            (db.workspace_id, batch_id),
        ).fetchall()


def test_hotter_news_is_chosen_first_and_source_set_comes_from_build_source_set(manager, pw_database, world):
    spy = SpyBuilder()
    candidate = make_selector(manager, pw_database, source_set_builder=spy).next_candidate('batch-1', SINGLE_ARTICLE)
    hot = world['hot'][0]
    with new_uow(manager, pw_database) as uow:
        pinned = build_source_set(SINGLE_ARTICLE, hot, uow)
    assert candidate == AllocationCandidate(hot, 'angle-1', f'{SINGLE_ARTICLE}:{hot}:{pinned.source_set_fingerprint}')
    assert spy.calls == [(SINGLE_ARTICLE, hot)]


def test_two_videos_per_news_get_different_angle_slots_and_used_candidates_never_repeat(manager, pw_database, world):
    seed_batch(pw_database, 'batch-1', 6)
    results = allocate(pw_database, make_selector(manager, pw_database), 'batch-1', 7)
    ids = [world[n][0] for n in ('hot', 'hot', 'mid', 'mid', 'old', 'old')]
    assert [r.get('job_candidate') for r in results[:6]] == ids
    assert results[6] == {'no_more_jobs': 'candidates_exhausted'}
    rows = stored(pw_database, 'batch-1')
    assert [r[0] for r in rows] == ids
    assert [r[1] for r in rows] == ['allocation:angle-1', 'allocation:angle-2'] * 3
    assert all(r[2] and r[2].startswith(f'{SINGLE_ARTICLE}:{r[0]}:') for r in rows)
    assert [r['source_set'] for r in results[:6]] == [r[2] for r in rows]

def test_candidates_do_not_repeat_between_batches(manager, pw_database, world):
    selector = make_selector(manager, pw_database)
    seed_batch(pw_database, 'batch-1', 1)
    seed_batch(pw_database, 'batch-2', 5)
    seed_batch(pw_database, 'batch-3', 5)
    first = allocate(pw_database, selector, 'batch-1', 1)
    second = allocate(pw_database, selector, 'batch-2', 6)
    hot, mid, old = (world[n][0] for n in ('hot', 'mid', 'old'))
    assert [r.get('job_candidate') for r in first] == [hot]
    assert [r.get('job_candidate') for r in second[:5]] == [hot, mid, mid, old, old]
    assert second[5] == {'no_more_jobs': 'candidates_exhausted'}
    assert stored(pw_database, 'batch-2')[0][1] == 'allocation:angle-2'
    assert allocate(pw_database, selector, 'batch-3', 1) == [{'no_more_jobs': 'candidates_exhausted'}]
    with pw_database.connect() as conn:
        counts = conn.execute(
            'SELECT count(*) FROM controlplane.cp_job_candidates WHERE workspace_id = %s GROUP BY candidate_ref',
            (pw_database.workspace_id,),
        ).fetchall()
    assert sorted(c[0] for c in counts) == [2, 2, 2]


def test_same_data_gives_the_same_candidate_and_no_data_gives_none(manager, pw_database):
    empty = make_selector(manager, pw_database)
    assert empty.next_candidate('batch-1', SINGLE_ARTICLE) is None
    assert empty.next_candidate('batch-1', MULTI_ARTICLE_EVENT) is None
    seed_sources(pw_database)
    resolve_news(manager, pw_database)
    first, second = make_selector(manager, pw_database), make_selector(manager, pw_database)
    runs = [s.next_candidate('batch-1', SINGLE_ARTICLE) for s in (first, second, first)]
    assert runs[0] is not None and runs[0] == runs[1] == runs[2]

def seed_events(manager, db, world):
    with new_uow(manager, db) as uow:
        for event_id, names in (('event-hot', ('hot', 'mid')), ('event-solo', ('old',))):
            uow.events.save({
                'event_id': event_id,
                'revision': 1,
                'status': 'candidate',
                'topic': 'tech',
                'member_refs': tuple(world[n] for n in names),
            })
        uow.commit()


def test_event_mode_ranks_events_by_independent_sources_and_skips_ineligible_events(manager, pw_database, world):
    seed_events(manager, pw_database, world)
    spy = SpyBuilder()
    seed_batch(pw_database, 'batch-1', 5)
    results = allocate(pw_database, make_selector(manager, pw_database, source_set_builder=spy), 'batch-1', 3, MULTI_ARTICLE_EVENT)
    assert [r.get('job_candidate') for r in results[:2]] == ['event-hot', 'event-hot']
    assert results[2] == {'no_more_jobs': 'candidates_exhausted'}
    assert spy.calls == [(MULTI_ARTICLE_EVENT, 'event-hot')] * 2 + [(MULTI_ARTICLE_EVENT, 'event-solo')]
    rows = stored(pw_database, 'batch-1')
    assert [r[0] for r in rows] == ['event-hot', 'event-hot']
    assert [r[1] for r in rows] == ['allocation:angle-1', 'allocation:angle-2']
    assert all(r[2].startswith(f'{MULTI_ARTICLE_EVENT}:event-hot:') for r in rows)


def test_weights_provider_is_read_on_each_call_so_ui_edits_change_the_ranking(manager, pw_database, world):
    current = {'weights': HotnessWeights()}
    selector = make_selector(manager, pw_database, weights_provider=lambda: current['weights'])
    assert selector.next_candidate('batch-1', SINGLE_ARTICLE).candidate_ref == world['hot'][0]
    current['weights'] = HotnessWeights(independent_sources=0.0, freshness=0.0, tier=1.0, tier_scores={1: 0.0, 2: 0.5, 3: 1.0})
    assert selector.next_candidate('batch-1', SINGLE_ARTICLE).candidate_ref == world['old'][0]

def test_invalid_arguments_are_rejected(manager, pw_database):
    selector = make_selector(manager, pw_database)
    with pytest.raises(ValueError):
        selector.next_candidate('batch-1', 'bogus_mode')
    with pytest.raises(ValueError):
        selector.next_candidate(' ', SINGLE_ARTICLE)
    for bad in (0, -1, True, 2.5):
        with pytest.raises(ValueError):
            make_selector(manager, pw_database, videos_per_news_per_round=bad)


def test_videos_per_news_per_round_is_configurable(manager, pw_database, world):
    seed_batch(pw_database, 'batch-1', 5)
    results = allocate(pw_database, make_selector(manager, pw_database, videos_per_news_per_round=1), 'batch-1', 4)
    assert [r.get('job_candidate') for r in results[:3]] == [world[n][0] for n in ('hot', 'mid', 'old')]
    assert results[3] == {'no_more_jobs': 'candidates_exhausted'}
    assert [r[1] for r in stored(pw_database, 'batch-1')] == ['allocation:angle-1'] * 3


def test_selector_source_uses_build_source_set_and_keeps_the_import_boundary():
    text = SELECTOR_SOURCE.read_text(encoding='utf-8')
    assert 'build_source_set' in text
    assert 'random' not in text.lower()
    assert 'from src.' not in text
    assert not re.search(r'(?m)^\s*(from|import)\s+psycopg', text)
    for name in ('cp_articles', 'cp_article_revisions', 'cp_events', 'cp_job_candidates'):
        assert name in text
    assert callable(PostgresCandidateSelector.next_candidate)