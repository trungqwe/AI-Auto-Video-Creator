"""B-3: InMemoryUnitOfWork commits aggregates and outbox records atomically (D8-B-13, CT-EVT-001)."""
import dataclasses
import itertools

import pytest

from ingestion.application.ports import (
    ArticleRepository,
    EventRepository,
    OutboxWriter,
    RecordRepository,
    ResolutionRepository,
    SourceTierLookup,
    UnitOfWork,
)
from ingestion.domain.article import Article, ArticleRevision
from ingestion.infrastructure.memory import InMemorySourceTierLookup, InMemoryUnitOfWork

DEDUP_ID = 'doc-1:dedup-policy-r1'


def _revision(number: int = 1, **overrides: object) -> ArticleRevision:
    kwargs = {
        'article_revision_id': f'rev-{number}',
        'article_id': 'art-1',
        'revision_number': number,
        'title': 'Sample Title',
        'normalized_text': f'Sample text {number}',
        'source_id': 'src-1',
        'source_revision': 3,
        'collection_run_id': 'run-1',
        'collected_document_id': f'doc-{number}',
        'requested_url': 'https://example.com/a',
        'final_url': 'https://example.com/a',
        'provenance_chain': [{'step': 'final_fetch', 'url': 'https://example.com/a'}],
        'raw_snapshot_ref': 'snapshot-1',
        'published_at': '2026-10-18T08:00:00Z',
        'published_at_confidence': 'candidate',
        'fetched_at': '2026-10-18T08:05:00Z',
        'topic': 'unclassified',
        'topic_uncertain': True,
        'exact_fingerprint': f'{number:064x}',
        'media_discovery_refs': ['media-1'],
        'extractor_version': '1.0.0',
        'normalizer_version': '1.0.0',
        'is_complete': True,
        'uncertain_fields': [],
    }
    kwargs.update(overrides)
    return ArticleRevision(**kwargs)


def _article(*revisions: ArticleRevision) -> Article:
    return Article(
        article_id='art-1',
        identity_key='https://example.com/a',
        representative_source_id='src-1',
        revisions=revisions or (_revision(1),),
    )


def _resolution() -> dict:
    return {
        'collected_document_id': 'doc-1',
        'dedup_policy_revision': 'dedup-policy-r1',
        'disposition': 'NEW_ARTICLE',
        'article_id': 'art-1',
        'article_revision_id': 'rev-1',
    }


def _uow() -> InMemoryUnitOfWork:
    counter = itertools.count(1)
    return InMemoryUnitOfWork(id_factory=lambda: f'evt-{next(counter)}')


def _append(uow: InMemoryUnitOfWork, deduplication_id: str = DEDUP_ID) -> str:
    return uow.outbox.append_event('ArticleRevisionAccepted', 'art-1', {'article_revision_id': 'rev-1'}, deduplication_id)


def _assert_nothing_committed(uow: InMemoryUnitOfWork) -> None:
    assert uow.committed('article') == ()
    assert uow.committed('collected_document_resolution') == ()
    assert uow.committed_outbox() == ()


def test_in_memory_adapters_satisfy_ports() -> None:
    uow = _uow()
    assert isinstance(uow, UnitOfWork)
    pairs = (
        (uow.articles, ArticleRepository),
        (uow.resolutions, ResolutionRepository),
        (uow.events, EventRepository),
        (uow.records, RecordRepository),
        (uow.outbox, OutboxWriter),
    )
    for adapter, port in pairs:
        assert isinstance(adapter, port), port
    tiers = InMemorySourceTierLookup({'src-1': 1})
    assert isinstance(tiers, SourceTierLookup)
    assert tiers.tier_of('src-1') == 1
    with pytest.raises(LookupError):
        tiers.tier_of('src-unknown')


def test_commit_persists_aggregate_and_outbox_together() -> None:
    uow = _uow()
    article = _article()
    with uow:
        uow.articles.save(article)
        uow.resolutions.save(_resolution())
        event_id = _append(uow)
        assert uow.articles.get('art-1') == article
        _assert_nothing_committed(uow)
        uow.commit()
    assert uow.committed('article') == (article,)
    assert uow.resolutions.get('doc-1', 'dedup-policy-r1')['article_revision_id'] == 'rev-1'
    (record,) = uow.committed_outbox()
    assert (event_id, record.event_id, record.event_type, record.aggregate_id, record.deduplication_id) == (
        'evt-1', 'evt-1', 'ArticleRevisionAccepted', 'art-1', DEDUP_ID,
    )
    assert dict(record.payload) == {'article_revision_id': 'rev-1'}


@pytest.mark.parametrize('failure_point', ['after_aggregate', 'after_event', 'after_both'])
def test_exception_before_commit_persists_nothing(failure_point: str) -> None:
    uow = _uow()
    with pytest.raises(RuntimeError, match='boom'):
        with uow:
            if failure_point != 'after_event':
                uow.articles.save(_article())
                uow.resolutions.save(_resolution())
            if failure_point != 'after_aggregate':
                _append(uow)
            raise RuntimeError('boom')
    _assert_nothing_committed(uow)
    assert uow.articles.get('art-1') is None


def test_exit_without_commit_discards_staged_writes() -> None:
    uow = _uow()
    with uow:
        uow.articles.save(_article())
        _append(uow)
    _assert_nothing_committed(uow)
    assert uow.articles.get('art-1') is None


def test_duplicate_deduplication_id_is_written_once() -> None:
    uow = _uow()
    with uow:
        first = _append(uow)
        assert _append(uow) == first
        uow.commit()
    with uow:
        assert _append(uow) == first
        uow.commit()
    assert [record.event_id for record in uow.committed_outbox()] == [first]


def test_writes_require_active_unit_of_work() -> None:
    uow = _uow()
    for write in (lambda: uow.articles.save(_article()), lambda: _append(uow), uow.commit):
        with pytest.raises(RuntimeError):
            write()
    with uow:
        with pytest.raises(RuntimeError):
            uow.__enter__()
    _assert_nothing_committed(uow)


def test_stored_revisions_cannot_be_rewritten() -> None:
    uow = _uow()
    article = _article()
    with uow:
        uow.articles.save(article)
        uow.commit()
    tampered = Article(
        article_id='art-1',
        identity_key=article.identity_key,
        representative_source_id='src-1',
        revisions=(dataclasses.replace(article.revisions[0], title='Tampered'),),
    )
    with uow:
        with pytest.raises(ValueError):
            uow.articles.save(tampered)
        uow.articles.save(article.with_revision(_revision(2)))
        uow.commit()
    (stored,) = uow.committed('article')
    assert [r.title for r in stored.revisions] == ['Sample Title', 'Sample Title']
    assert uow.articles.find_by_identity_key('https://example.com/a') == stored
    assert uow.articles.find_by_exact_fingerprint(_revision(2).exact_fingerprint) == stored


def test_records_are_stored_by_kind() -> None:
    uow = _uow()
    with uow:
        uow.records.put('dedup_evidence', 'de-1', {'collected_document_id': 'doc-1'})
        uow.records.put('event_link_candidate', 'elc-1', {'event_id': 'ev-1'})
        uow.events.save({'event_id': 'ev-1', 'topic': 'unclassified'})
        with pytest.raises(ValueError):
            uow.records.put('article', 'art-1', {'article_id': 'art-1'})
        uow.commit()
    assert [dict(r) for r in uow.committed('dedup_evidence')] == [{'collected_document_id': 'doc-1'}]
    assert [dict(r) for r in uow.committed('event_link_candidate')] == [{'event_id': 'ev-1'}]
    assert uow.events.get('ev-1')['topic'] == 'unclassified'
    assert uow.records.get('dedup_evidence', 'de-1')['collected_document_id'] == 'doc-1'
    assert uow.records.list('event_update') == ()
