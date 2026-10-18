"""B-7: ResolveEventLink keeps every Article separate (CT-CNT-004, CT-STATE-004, D8-B-06)."""
import itertools
import pathlib
import re
import unicodedata
from datetime import datetime, timezone

import pytest

from ingestion.application.resolve_event_link import EVENT_LINK_CANDIDATE_KIND, EVENT_LINK_RESOLVED, resolve_event_link
from ingestion.domain.article import Article, ArticleRevision
from ingestion.domain.event_link import (
    DISPOSITIONS,
    KEPT_SEPARATE,
    LINKED,
    NEEDS_MORE_EVIDENCE,
    RELATION_BY_DISPOSITION,
    STATE_BY_DISPOSITION,
    STATE_PROPOSED,
    parse_event_link_policy,
    title_keywords,
)
from ingestion.infrastructure.memory import InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCES = (
    ROOT / 'src' / 'ingestion' / 'domain' / 'event_link.py',
    ROOT / 'src' / 'ingestion' / 'application' / 'resolve_event_link.py',
)
BOUNDARY_RE = re.compile(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)')
THRESHOLD_LITERAL_RE = re.compile(r'(?<![\w.])(0\.5|0\.3|72(?:\.0)?)(?![\w.])')
POLICY = {
    'event_link_policy_revision': 'event-link-policy-r1',
    'link_jaccard': 0.5,
    'review_jaccard': 0.3,
    'max_time_gap_hours': 72,
}
EPOCH = 'epoch-0001'
T0 = '2026-10-18T08:00:00Z'
T10H = '2026-10-18T18:00:00Z'
T72H = '2026-10-21T08:00:00Z'
T72H1S = '2026-10-21T08:00:01Z'
TITLE_A = 'mua lon ngap pho'
TITLE_J60 = 'mua lon ngap duong'
TITLE_J50 = 'mua lon ngap cau truot'
TITLE_J33 = 'mua lon cau truot'
TITLE_J14 = 'mua bong da chung'


def _clock() -> datetime:
    return datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)


def _revision(
    article_id: str,
    title: str,
    *,
    published_at: str | None = T0,
    topic: str = 'thoi-tiet',
    topic_uncertain: bool = False,
) -> ArticleRevision:
    return ArticleRevision(
        article_revision_id=f'{article_id}-r1',
        article_id=article_id,
        revision_number=1,
        title=title,
        normalized_text=f'{title} noi dung tong hop',
        source_id=f'src-{article_id}',
        source_revision=1,
        collection_run_id='run-b7',
        collected_document_id=f'doc-{article_id}',
        requested_url=f'https://example.invalid/{article_id}',
        final_url=f'https://example.invalid/{article_id}',
        provenance_chain=({'step': 'final_fetch'},),
        raw_snapshot_ref=None,
        published_at=published_at,
        published_at_confidence='high' if published_at else 'missing',
        fetched_at='2026-10-18T09:00:00Z',
        topic=topic,
        topic_uncertain=topic_uncertain,
        exact_fingerprint=f'fp-{article_id}',
        media_discovery_refs=(),
        extractor_version='extractor-r1',
        normalizer_version='normalize-text-r1',
        is_complete=True,
        uncertain_fields=() if published_at else ('published_at',),
    )


def _setup(*revisions: ArticleRevision) -> tuple[InMemoryUnitOfWork, object]:
    ids = itertools.count(1)
    outbox_ids = itertools.count(1)
    uow = InMemoryUnitOfWork(id_factory=lambda: f'outbox-{next(outbox_ids):04d}')
    for revision in revisions:
        article = Article(
            article_id=revision.article_id,
            identity_key=f'key-{revision.article_id}',
            representative_source_id=revision.source_id,
            revisions=(revision,),
        )
        with uow:
            uow.articles.save(article)
            uow.commit()
    return uow, lambda: f'b7-{next(ids):04d}'


def _ref(revision: ArticleRevision) -> dict:
    return {'article_id': revision.article_id, 'article_revision_id': revision.article_revision_id}


def _resolve(uow: InMemoryUnitOfWork, ids: object, revisions: list, policy: dict = POLICY) -> tuple:
    results = resolve_event_link([_ref(revision) for revision in revisions], policy, uow, _clock, ids, recovery_epoch=EPOCH)
    assert len(results) == len(revisions)
    return results


def _members(uow: InMemoryUnitOfWork, event_id: str) -> tuple:
    return uow.events.get(event_id)['member_refs']


def test_dispositions_map_to_ct_state_004() -> None:
    assert DISPOSITIONS == (LINKED, KEPT_SEPARATE, NEEDS_MORE_EVIDENCE) == ('linked', 'kept_separate', 'needs_more_evidence')
    assert dict(STATE_BY_DISPOSITION) == {'linked': 'LINKED', 'kept_separate': 'KEPT_SEPARATE', 'needs_more_evidence': 'NEEDS_MORE_EVIDENCE'}
    assert dict(RELATION_BY_DISPOSITION) == {'linked': 'same_event', 'kept_separate': 'separate_event', 'needs_more_evidence': 'possible_same_event'}
    assert STATE_PROPOSED == 'PROPOSED'


def test_title_keywords_are_casefolded_nfc_words() -> None:
    assert title_keywords('Mưa LỚN, ngập phố!') == frozenset({'mưa', 'lớn', 'ngập', 'phố'})
    assert title_keywords(unicodedata.normalize('NFD', 'Mưa lớn ngập phố')) == title_keywords('mưa lớn ngập phố')
    assert title_keywords('') == frozenset()


def test_first_article_opens_new_event_candidate_kept_separate() -> None:
    a = _revision('art-a', TITLE_A)
    uow, ids = _setup(a)
    (result,) = _resolve(uow, ids, [a])
    assert (result.disposition, result.state, result.relation_type) == (KEPT_SEPARATE, 'KEPT_SEPARATE', 'separate_event')
    assert result.is_new_event is True
    assert (result.confidence, result.explanation) == (0.0, ('no_comparable_event',))
    assert result.effective_time_range == (T0, T0)
    event = uow.events.get(result.event_id)
    assert (event['status'], event['revision'], event['member_refs']) == ('candidate', 1, (('art-a', 'art-a-r1'),))


def test_similar_title_same_topic_within_window_is_linked() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J60, published_at=T10H)
    uow, ids = _setup(a, b)
    first, second = _resolve(uow, ids, [a, b])
    assert (second.disposition, second.state, second.relation_type) == (LINKED, 'LINKED', 'same_event')
    assert (second.event_id, second.is_new_event) == (first.event_id, False)
    assert second.confidence == pytest.approx(3 / 5)
    assert second.explanation == ('same_topic', 'within_time_window', 'title_jaccard_at_least_link')
    assert second.effective_time_range == (T0, T10H)
    event = uow.events.get(first.event_id)
    assert event['member_refs'] == (('art-a', 'art-a-r1'), ('art-b', 'art-b-r1'))
    assert event['revision'] == 2
    assert len(uow.events.list_all()) == 1


def test_linking_never_merges_or_deletes_articles() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J60, published_at=T10H)
    uow, ids = _setup(a, b)
    before = {article.article_id: article for article in uow.articles.list_all()}
    _, second = _resolve(uow, ids, [a, b])
    after = {article.article_id: article for article in uow.articles.list_all()}
    assert second.disposition == LINKED
    assert after == before
    assert set(after) == {'art-a', 'art-b'}
    assert (after['art-a'].revisions, after['art-b'].revisions) == ((a,), (b,))


def test_mid_band_jaccard_needs_more_evidence_without_joining_event() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J33, published_at=T10H)
    uow, ids = _setup(a, b)
    first, second = _resolve(uow, ids, [a, b])
    assert (second.disposition, second.state, second.relation_type) == (NEEDS_MORE_EVIDENCE, 'NEEDS_MORE_EVIDENCE', 'possible_same_event')
    assert (second.event_id, second.is_new_event) == (first.event_id, False)
    assert second.confidence == pytest.approx(2 / 6)
    assert second.explanation == ('same_topic', 'within_time_window', 'title_jaccard_below_link')
    assert _members(uow, first.event_id) == (('art-a', 'art-a-r1'),)


@pytest.mark.parametrize(
    ('title', 'published_at', 'topic', 'reason'),
    [
        (TITLE_J14, T10H, 'thoi-tiet', 'title_jaccard_below_review'),
        (TITLE_J60, T72H1S, 'thoi-tiet', 'outside_time_window'),
        (TITLE_A, T10H, 'the-thao', 'topic_mismatch'),
    ],
)
def test_rule_failure_keeps_article_separate_in_new_event(title: str, published_at: str, topic: str, reason: str) -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', title, published_at=published_at, topic=topic)
    uow, ids = _setup(a, b)
    first, second = _resolve(uow, ids, [a, b])
    assert (second.disposition, second.state) == (KEPT_SEPARATE, 'KEPT_SEPARATE')
    assert second.is_new_event is True and second.event_id != first.event_id
    assert second.explanation[-1] == reason
    assert _members(uow, first.event_id) == (('art-a', 'art-a-r1'),)
    assert _members(uow, second.event_id) == (('art-b', 'art-b-r1'),)


def test_missing_published_at_is_never_linked() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_A, published_at=None)
    uow, ids = _setup(a, b)
    first, second = _resolve(uow, ids, [a, b])
    assert second.disposition == NEEDS_MORE_EVIDENCE and second.confidence == 1.0
    assert second.explanation == ('same_topic', 'published_at_missing', 'title_jaccard_at_least_link')
    assert _members(uow, first.event_id) == (('art-a', 'art-a-r1'),)


def test_uncertain_topic_is_never_linked() -> None:
    a = _revision('art-a', TITLE_A, topic='unclassified', topic_uncertain=True)
    b = _revision('art-b', TITLE_A, published_at=T10H, topic='unclassified', topic_uncertain=True)
    uow, ids = _setup(a, b)
    first, second = _resolve(uow, ids, [a, b])
    assert second.disposition == NEEDS_MORE_EVIDENCE
    assert second.explanation == ('same_topic', 'within_time_window', 'topic_uncertain', 'title_jaccard_at_least_link')
    assert _members(uow, first.event_id) == (('art-a', 'art-a-r1'),)


@pytest.mark.parametrize(
    ('overrides', 'expected'),
    [
        ({}, LINKED),
        ({'link_jaccard': 0.7, 'review_jaccard': 0.6}, NEEDS_MORE_EVIDENCE),
        ({'link_jaccard': 0.9, 'review_jaccard': 0.8}, KEPT_SEPARATE),
        ({'max_time_gap_hours': 5}, KEPT_SEPARATE),
        ({'event_link_policy_revision': 'event-link-policy-r2'}, LINKED),
    ],
)
def test_thresholds_come_from_policy(overrides: dict, expected: str) -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J60, published_at=T10H)
    uow, ids = _setup(a, b)
    policy = {**POLICY, **overrides}
    _, second = _resolve(uow, ids, [a, b], policy=policy)
    assert second.disposition == expected
    assert second.event_link_policy_revision == policy['event_link_policy_revision']


def test_policy_boundaries_are_inclusive() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J50, published_at=T72H)
    uow, ids = _setup(a, b)
    _, second = _resolve(uow, ids, [a, b])
    assert (second.disposition, second.confidence) == (LINKED, 0.5)


def test_thresholds_are_not_hard_coded_in_source() -> None:
    for path in SOURCES:
        assert not THRESHOLD_LITERAL_RE.search(path.read_text(encoding='utf-8')), path.name


def test_each_resolution_emits_event_link_resolved_with_refs_only() -> None:
    a = _revision('art-a', TITLE_A)
    b = _revision('art-b', TITLE_J60, published_at=T10H)
    c = _revision('art-c', TITLE_J33, published_at=T10H)
    d = _revision('art-d', TITLE_J14, published_at=T10H)
    uow, ids = _setup(a, b, c, d)
    results = _resolve(uow, ids, [a, b, c, d])
    assert [result.disposition for result in results] == [KEPT_SEPARATE, LINKED, NEEDS_MORE_EVIDENCE, KEPT_SEPARATE]
    outbox = uow.committed_outbox()
    assert [record.event_type for record in outbox] == [EVENT_LINK_RESOLVED] * 4
    for result, record in zip(results, outbox):
        envelope = record.payload
        assert record.aggregate_id == result.event_id
        assert record.deduplication_id == f'{EVENT_LINK_RESOLVED}:{result.event_link_candidate_id}'
        assert (envelope['event_name'], envelope['aggregate_type'], envelope['aggregate_id']) == ('EventLinkResolved', 'Event', result.event_id)
        assert (envelope['producer'], envelope['recovery_epoch'], envelope['event_id']) == ('B', EPOCH, result.domain_event_id)
        assert envelope['payload'] == {
            'event_link_candidate_id': result.event_link_candidate_id,
            'event_id': result.event_id,
            'article_id': result.article_id,
            'article_revision_id': result.article_revision_id,
            'event_link_policy_revision': 'event-link-policy-r1',
        }
    rendered = repr(outbox)
    for title in (TITLE_A, TITLE_J60, TITLE_J33, TITLE_J14):
        assert title not in rendered


def test_candidate_record_moves_from_proposed_to_terminal_state() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J60, published_at=T10H)
    uow, ids = _setup(a, b)
    _, second = _resolve(uow, ids, [a, b])
    record = uow.records.get(EVENT_LINK_CANDIDATE_KIND, second.event_link_candidate_id)
    assert record['state_history'] == (STATE_PROPOSED, 'LINKED')
    assert (record['disposition'], record['event_id'], record['article_revision_id']) == (LINKED, second.event_id, 'art-b-r1')
    assert record['resolved_at'] == '2026-10-19T08:00:00Z'


def test_replay_with_same_policy_revision_writes_nothing() -> None:
    a, b = _revision('art-a', TITLE_A), _revision('art-b', TITLE_J60, published_at=T10H)
    uow, ids = _setup(a, b)
    first_run = _resolve(uow, ids, [a, b])
    outbox_before, events_before = uow.committed_outbox(), uow.events.list_all()
    assert _resolve(uow, ids, [a, b]) == first_run
    assert uow.committed_outbox() == outbox_before
    assert uow.events.list_all() == events_before
    assert len(uow.records.list(EVENT_LINK_CANDIDATE_KIND)) == 2


@pytest.mark.parametrize(
    'overrides',
    [
        {'event_link_policy_revision': ''},
        {'event_link_policy_revision': 'event link r1'},
        {'link_jaccard': 0},
        {'link_jaccard': 1.5},
        {'link_jaccard': True},
        {'link_jaccard': '0.5'},
        {'review_jaccard': 0},
        {'review_jaccard': 0.6},
        {'max_time_gap_hours': 0},
        {'max_time_gap_hours': -1},
        {'max_time_gap_hours': float('inf')},
    ],
)
def test_invalid_policy_fails_closed_without_writes(overrides: dict) -> None:
    a = _revision('art-a', TITLE_A)
    uow, ids = _setup(a)
    with pytest.raises(ValueError):
        resolve_event_link([_ref(a)], {**POLICY, **overrides}, uow, _clock, ids, recovery_epoch=EPOCH)
    assert uow.events.list_all() == () and uow.committed_outbox() == ()


@pytest.mark.parametrize('key', sorted(POLICY))
def test_policy_missing_key_fails_closed(key: str) -> None:
    with pytest.raises(ValueError):
        parse_event_link_policy({name: value for name, value in POLICY.items() if name != key})


@pytest.mark.parametrize('refs', [[], 'art-a-r1', ['art-a-r1'], [{'article_id': 'art-a'}]])
def test_invalid_refs_fail_closed_without_writes(refs: object) -> None:
    a = _revision('art-a', TITLE_A)
    uow, ids = _setup(a)
    with pytest.raises(ValueError):
        resolve_event_link(refs, POLICY, uow, _clock, ids, recovery_epoch=EPOCH)
    assert uow.events.list_all() == () and uow.committed_outbox() == ()


@pytest.mark.parametrize('epoch', ['', 'epoch 1', None])
def test_invalid_recovery_epoch_fails_closed_without_writes(epoch: object) -> None:
    a = _revision('art-a', TITLE_A)
    uow, ids = _setup(a)
    with pytest.raises(ValueError):
        resolve_event_link([_ref(a)], POLICY, uow, _clock, ids, recovery_epoch=epoch)
    assert uow.events.list_all() == () and uow.committed_outbox() == ()


def test_unknown_revision_raises_lookup_error_without_writes() -> None:
    a = _revision('art-a', TITLE_A)
    uow, ids = _setup(a)
    with pytest.raises(LookupError):
        resolve_event_link([{'article_id': 'art-a', 'article_revision_id': 'art-a-r9'}], POLICY, uow, _clock, ids, recovery_epoch=EPOCH)
    assert uow.events.list_all() == () and uow.committed_outbox() == ()


def test_new_modules_respect_check_b_import_boundary() -> None:
    for line in ('from src.ingestion.domain import event_link', 'import socket'):
        assert BOUNDARY_RE.search(line), line
    for path in SOURCES:
        assert path.exists(), path
        assert not BOUNDARY_RE.search(path.read_text(encoding='utf-8')), path.name
    for relative in ('tests/unit/ingestion/__init__.py', 'tests/integration/ingestion/__init__.py'):
        assert not (ROOT / relative).exists(), relative
