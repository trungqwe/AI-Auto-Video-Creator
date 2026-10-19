"""B-10: read-only source trace, search/filter and NEW_ARTICLE count queries (CT-CNT-006, D8-B-10)."""
import pathlib
import re
import unicodedata
from datetime import date, datetime

import pytest

from ingestion.application.queries import SEARCH_FILTERS, TRACE_FIELDS, IngestionQueries
from ingestion.domain.article import Article, ArticleRevision
from ingestion.infrastructure.memory import InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
QUERIES_PATH = ROOT / 'src' / 'ingestion' / 'application' / 'queries.py'
BOUNDARY_RE = re.compile(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)')
WRITE_CALL_RE = re.compile(r'\.(save|put|commit|rollback|append_event)\(|\bwith\s+[\w.]*uow\b')
POLICY = 'dedup-policy-r1'


def _revision(
    article_id: str,
    number: int = 1,
    *,
    title: str = 'Mua lon ngap pho',
    topic: str = 'thoi-tiet',
    source_id: str | None = None,
    fetched_at: str = '2026-10-18T09:00:00Z',
    **overrides: object,
) -> ArticleRevision:
    values = {
        'article_revision_id': f'{article_id}-r{number}',
        'article_id': article_id,
        'revision_number': number,
        'title': title,
        'normalized_text': f'{title} noi dung tong hop',
        'source_id': source_id if source_id is not None else f'src-{article_id}',
        'source_revision': 3,
        'collection_run_id': 'run-b10',
        'collected_document_id': f'doc-{article_id}-{number}',
        'requested_url': f'https://example.invalid/{article_id}?r={number}',
        'final_url': f'https://example.invalid/{article_id}',
        'provenance_chain': ({'step': 'final_fetch', 'url': f'https://example.invalid/{article_id}'},),
        'raw_snapshot_ref': f'snapshot://{article_id}/{number}',
        'published_at': '2026-10-18T08:00:00Z',
        'published_at_confidence': 'high',
        'fetched_at': fetched_at,
        'topic': topic,
        'topic_uncertain': False,
        'exact_fingerprint': f'fp-{article_id}-{number}',
        'media_discovery_refs': (),
        'extractor_version': 'extractor-r1',
        'normalizer_version': 'normalize-text-r1',
        'is_complete': True,
        'uncertain_fields': (),
    }
    values.update(overrides)
    return ArticleRevision(**values)


A1 = _revision('art-a')
A2 = _revision('art-a', 2, title='Mua lon ngap pho cap nhat', fetched_at='2026-10-18T23:59:59Z')
B1 = _revision('art-b', title='Bão số 5 đổ bộ', source_id='src-shared')
C1 = _revision('art-c', title='Giá vàng tăng', topic='kinh-te', source_id='src-shared', fetched_at='2026-10-19T00:00:00Z')
D1 = _revision('art-d', title='Mưa lớn ở miền Trung', fetched_at='2026-10-18T06:30:00+07:00')


def _resolution(revision: ArticleRevision | None, disposition: str, document_id: str, policy: str = POLICY) -> dict:
    record = {'collected_document_id': document_id, 'dedup_policy_revision': policy, 'disposition': disposition}
    if revision is not None:
        record.update(article_id=revision.article_id, article_revision_id=revision.article_revision_id)
    return record


def _event(event_id: str, *revisions: ArticleRevision) -> dict:
    refs = tuple((revision.article_id, revision.article_revision_id) for revision in revisions)
    return {'event_id': event_id, 'status': 'candidate', 'revision': 1, 'topic': 'thoi-tiet', 'member_refs': refs}


def _seed(groups: list, resolutions: list, events: list) -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork(id_factory=lambda: 'outbox-unused')
    with uow:
        for revisions in groups:
            first = revisions[0]
            uow.articles.save(
                Article(
                    article_id=first.article_id,
                    identity_key=f'key-{first.article_id}',
                    representative_source_id=first.source_id,
                    revisions=tuple(revisions),
                )
            )
        for resolution in resolutions:
            uow.resolutions.save(resolution)
        for event in events:
            uow.events.save(event)
        uow.commit()
    return uow


def _corpus(*, reverse: bool = False) -> InMemoryUnitOfWork:
    groups = [(A1, A2), (B1,), (C1,), (D1,)]
    resolutions = [
        _resolution(A1, 'NEW_ARTICLE', 'doc-art-a-1'),
        _resolution(A1, 'NEW_ARTICLE', 'doc-art-a-1', 'dedup-policy-r2'),
        _resolution(A2, 'NEW_REVISION', 'doc-art-a-2'),
        _resolution(A1, 'DUPLICATE_MEDIA_ONLY', 'doc-dup-media'),
        _resolution(A1, 'DUPLICATE_NO_NEW_VALUE', 'doc-dup-none'),
        _resolution(None, 'REJECTED_INCOMPLETE', 'doc-rejected'),
        _resolution(B1, 'NEW_ARTICLE', 'doc-art-b-1'),
        _resolution(C1, 'NEW_ARTICLE', 'doc-art-c-1'),
        _resolution(D1, 'NEW_ARTICLE', 'doc-art-d-1'),
    ]
    events = [_event('evt-2', A2, B1), _event('evt-1', C1, B1)]
    if reverse:
        groups, resolutions, events = groups[::-1], resolutions[::-1], events[::-1]
    return _seed(groups, resolutions, events)


def _ids(results: tuple) -> list[str]:
    return [item['article_revision_id'] for item in results]


def test_query_constants_match_acceptance() -> None:
    assert TRACE_FIELDS == (
        'source_id', 'source_revision', 'collection_run_id', 'collected_document_id', 'requested_url',
        'final_url', 'fetched_at', 'raw_snapshot_ref', 'provenance_chain',
    )
    assert SEARCH_FILTERS == ('topic', 'source_id', 'event_id', 'article_revision_id', 'title_contains')


def test_trace_revision_returns_full_provenance() -> None:
    trace = IngestionQueries(_corpus()).trace_revision('art-a-r2')
    assert {name: trace[name] for name in TRACE_FIELDS} == {
        'source_id': 'src-art-a', 'source_revision': 3, 'collection_run_id': 'run-b10', 'collected_document_id': 'doc-art-a-2',
        'requested_url': 'https://example.invalid/art-a?r=2', 'final_url': 'https://example.invalid/art-a',
        'fetched_at': '2026-10-18T23:59:59Z', 'raw_snapshot_ref': 'snapshot://art-a/2',
        'provenance_chain': ({'step': 'final_fetch', 'url': 'https://example.invalid/art-a'},),
    }
    assert (trace['article_id'], trace['article_revision_id'], trace['revision_number']) == ('art-a', 'art-a-r2', 2)
    assert (trace['uncertain_fields'], trace['is_fully_traced']) == ((), True)
    assert all(type(step) is dict for step in trace['provenance_chain'])


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('raw_snapshot_ref', None), ('provenance_chain', ()), ('final_url', ''), ('requested_url', '  '),
        ('collection_run_id', ''), ('collected_document_id', ''), ('source_id', ''), ('fetched_at', 'not-a-time'),
    ],
)
def test_missing_trace_field_is_reported_in_uncertain_fields(field: str, value: object) -> None:
    trace = IngestionQueries(_seed([(_revision('art-x', **{field: value}),)], [], [])).trace_revision('art-x-r1')
    assert (trace['uncertain_fields'], trace['is_fully_traced']) == ((field,), False)


def test_revision_uncertain_fields_follow_missing_trace_fields() -> None:
    revision = _revision('art-x', raw_snapshot_ref=None, uncertain_fields=('published_at', 'raw_snapshot_ref'))
    trace = IngestionQueries(_seed([(revision,)], [], [])).trace_revision('art-x-r1')
    assert (trace['uncertain_fields'], trace['is_fully_traced']) == (('raw_snapshot_ref', 'published_at'), False)


def test_trace_field_flagged_uncertain_is_not_fully_traced() -> None:
    trace = IngestionQueries(_seed([(_revision('art-x', uncertain_fields=('final_url',)),)], [], [])).trace_revision('art-x-r1')
    assert (trace['uncertain_fields'], trace['is_fully_traced']) == (('final_url',), False)


@pytest.mark.parametrize('article_revision_id', ['art-missing-r1', 'art-a-r3'])
def test_unknown_revision_is_reported_not_hidden(article_revision_id: str) -> None:
    with pytest.raises(LookupError, match=article_revision_id):
        IngestionQueries(_corpus()).trace_revision(article_revision_id)


@pytest.mark.parametrize('article_revision_id', ['', None, 7])
def test_invalid_revision_id_is_rejected(article_revision_id: object) -> None:
    with pytest.raises(ValueError):
        IngestionQueries(_corpus()).trace_revision(article_revision_id)


def test_trace_returns_copies_of_provenance() -> None:
    uow = _corpus()
    trace = IngestionQueries(uow).trace_revision('art-a-r1')
    assert trace['provenance_chain'] == ({'step': 'final_fetch', 'url': 'https://example.invalid/art-a'},)
    trace['provenance_chain'][0]['step'] = 'tampered'
    assert IngestionQueries(uow).trace_revision('art-a-r1')['provenance_chain'][0]['step'] == 'final_fetch'
    assert uow.articles.get('art-a').revisions[0].provenance_chain[0]['step'] == 'final_fetch'


def test_search_without_filters_lists_every_revision_in_stable_order() -> None:
    assert _ids(IngestionQueries(_corpus()).search({})) == ['art-a-r1', 'art-a-r2', 'art-b-r1', 'art-c-r1', 'art-d-r1']


@pytest.mark.parametrize(
    ('filters', 'expected'),
    [
        ({'topic': 'kinh-te'}, ['art-c-r1']),
        ({'source_id': 'src-shared'}, ['art-b-r1', 'art-c-r1']),
        ({'event_id': 'evt-2'}, ['art-a-r2', 'art-b-r1']),
        ({'event_id': 'evt-1'}, ['art-b-r1', 'art-c-r1']),
        ({'article_revision_id': 'art-a-r1'}, ['art-a-r1']),
        ({'title_contains': 'NGAP PHO'}, ['art-a-r1', 'art-a-r2']),
        ({'title_contains': 'mưa lớn'}, ['art-d-r1']),
        ({'title_contains': unicodedata.normalize('NFD', 'Bão số 5')}, ['art-b-r1']),
        ({'title_contains': 'cap nhat', 'topic': 'thoi-tiet'}, ['art-a-r2']),
        ({'source_id': 'src-shared', 'topic': 'thoi-tiet'}, ['art-b-r1']),
        ({'event_id': 'evt-missing'}, []),
        ({'topic': 'kinh-te', 'event_id': 'evt-2'}, []),
    ],
)
def test_search_filters_combine_with_and(filters: dict, expected: list) -> None:
    assert _ids(IngestionQueries(_corpus()).search(filters)) == expected


def test_search_result_carries_refs_and_sorted_event_ids() -> None:
    results = IngestionQueries(_corpus()).search({'article_revision_id': 'art-b-r1'})
    assert _ids(results) == ['art-b-r1']
    assert results[0] == {
        'article_id': 'art-b', 'article_revision_id': 'art-b-r1', 'revision_number': 1, 'title': 'Bão số 5 đổ bộ',
        'topic': 'thoi-tiet', 'source_id': 'src-shared', 'fetched_at': '2026-10-18T09:00:00Z', 'event_ids': ('evt-1', 'evt-2'),
    }


def test_search_order_is_stable_across_calls_and_insertion_order() -> None:
    forward, backward = IngestionQueries(_corpus()), IngestionQueries(_corpus(reverse=True))
    assert len(forward.search({})) == 5
    for filters in ({}, {'topic': 'thoi-tiet'}, {'source_id': 'src-shared'}, {'event_id': 'evt-1'}, {'title_contains': 'mua'}):
        assert forward.search(filters) == backward.search(filters) == forward.search(filters), filters


@pytest.mark.parametrize(
    'filters',
    [None, ['topic'], {'unknown': 'x'}, {'topic': ''}, {'topic': 5}, {'event_id': None}, {'title_contains': '   '}],
)
def test_invalid_filters_fail_closed(filters: object) -> None:
    with pytest.raises(ValueError):
        IngestionQueries(_corpus()).search(filters)


def test_count_new_articles_counts_distinct_new_article_by_utc_date() -> None:
    queries = IngestionQueries(_corpus())
    assert queries.count_new_articles('thoi-tiet', date(2026, 10, 18)) == 2
    assert queries.count_new_articles('thoi-tiet', '2026-10-18') == 2
    assert queries.count_new_articles('thoi-tiet', date(2026, 10, 17)) == 1
    assert queries.count_new_articles('kinh-te', date(2026, 10, 19)) == 1
    assert queries.count_new_articles('kinh-te', date(2026, 10, 18)) == 0
    assert queries.count_new_articles('the-thao', date(2026, 10, 18)) == 0


@pytest.mark.parametrize('disposition', ['NEW_REVISION', 'DUPLICATE_MEDIA_ONLY', 'DUPLICATE_NO_NEW_VALUE'])
def test_count_new_articles_ignores_other_dispositions(disposition: str) -> None:
    uow = _seed([(A1,)], [_resolution(A1, disposition, 'doc-other')], [])
    assert IngestionQueries(uow).count_new_articles('thoi-tiet', date(2026, 10, 18)) == 0


@pytest.mark.parametrize(
    ('topic', 'business_date'),
    [
        ('', date(2026, 10, 18)), (None, date(2026, 10, 18)), ('thoi-tiet', datetime(2026, 10, 18, 9)),
        ('thoi-tiet', '18/10/2026'), ('thoi-tiet', '20261018'), ('thoi-tiet', '2026-10-18T00:00:00Z'),
        ('thoi-tiet', '2026-13-01'), ('thoi-tiet', 20261018),
    ],
)
def test_count_new_articles_rejects_invalid_arguments(topic: object, business_date: object) -> None:
    with pytest.raises(ValueError):
        IngestionQueries(_corpus()).count_new_articles(topic, business_date)


def test_count_new_articles_reports_dangling_new_article_resolution() -> None:
    uow = _seed([(A1,)], [_resolution(B1, 'NEW_ARTICLE', 'doc-art-b-1')], [])
    with pytest.raises(LookupError, match='doc-art-b-1'):
        IngestionQueries(uow).count_new_articles('thoi-tiet', date(2026, 10, 18))


def test_queries_never_write(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = _corpus()
    kinds = ('article', 'collected_document_resolution', 'event')
    before = ({kind: uow.committed(kind) for kind in kinds}, uow.committed_outbox())

    def _forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError('query attempted a write')

    targets = (
        (uow.articles, 'save'), (uow.resolutions, 'save'), (uow.events, 'save'), (uow.records, 'put'),
        (uow.outbox, 'append_event'), (uow, 'commit'), (uow, 'rollback'),
    )
    for target, name in targets:
        monkeypatch.setattr(target, name, _forbid)
    monkeypatch.setattr(InMemoryUnitOfWork, '__enter__', _forbid)
    queries = IngestionQueries(uow)
    queries.trace_revision('art-a-r1')
    queries.search({})
    queries.search({'event_id': 'evt-2', 'title_contains': 'mua'})
    queries.count_new_articles('thoi-tiet', date(2026, 10, 18))
    assert ({kind: uow.committed(kind) for kind in kinds}, uow.committed_outbox()) == before


def test_queries_source_has_no_write_calls_or_forbidden_imports() -> None:
    source = QUERIES_PATH.read_text(encoding='utf-8')
    assert not WRITE_CALL_RE.search(source)
    assert not BOUNDARY_RE.search(source)
