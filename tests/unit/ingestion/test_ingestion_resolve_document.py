"""B-6: ResolveCollectedDocument, five dispositions and CT-STATE-003 (CT-CNT-001, D8-B-01..04, D8-B-09, D8-B-11)."""
import copy
import itertools
import json
import pathlib
from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from ingestion.application.resolve_document import (
    DUPLICATE_MEDIA_ONLY,
    DUPLICATE_NO_NEW_VALUE,
    FAILED_FINAL,
    FAILED_RETRYABLE,
    NEW_ARTICLE,
    NEW_REVISION,
    REJECTED_INCOMPLETE,
    VALIDATION_ERROR,
    ResolveDocumentError,
    attached_media_refs,
    identity_key,
    resolve_collected_document,
)
from ingestion.domain.fingerprint import exact_fingerprint
from ingestion.domain.package_validation import validate_collected_document_resolution
from ingestion.infrastructure.memory import InMemorySourceTierLookup, InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'a-b-collected-document' / 'payloads.json'
POLICY = {'dedup_policy_revision': 'dedup-policy-r1', 'near_duplicate_jaccard': 0.90, 'shingle_size': 5}
SOURCE_A = '00000000-0000-4000-8000-000000000002'
SOURCE_B = '00000000-0000-4000-8000-0000000000b2'
SOURCE_C = '00000000-0000-4000-8000-0000000000c2'
TIERS = {SOURCE_A: 2, SOURCE_B: 1, SOURCE_C: 3}
TRAIL = ('RECEIVED', 'NORMALIZING', 'RESOLVING_IDENTITY')
LONG_TEXT = ' '.join(f'word{i:02d}' for i in range(40))
NEAR_TEXT = LONG_TEXT.replace('word39', 'changed39')
EMPTY = ((), (), (), (), ())


def _clock() -> datetime:
    return datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['CollectedDocumentPackage']


def _package(number: int = 1, **overrides: object) -> dict:
    package = copy.deepcopy(_fixture()['valid'][0])
    if number != 1:
        package['collected_document_id'] = f'00000000-0000-4000-9000-{number:012d}'
    package.update(overrides)
    return package


def _text(package: dict, text: str) -> dict:
    package['extracted_content_candidate']['text'] = text
    return package


class _Ids:
    def __init__(self) -> None:
        self.issued: list[str] = []

    def __call__(self) -> str:
        self.issued.append(f'b6-{len(self.issued) + 1:04d}')
        return self.issued[-1]


class _Env:
    def __init__(self, tiers: dict | None = None) -> None:
        counter = itertools.count(1)
        self.uow = InMemoryUnitOfWork(id_factory=lambda: f'outbox-{next(counter)}')
        self.tiers = InMemorySourceTierLookup(TIERS if tiers is None else tiers)
        self.ids = _Ids()

    def resolve(self, package: dict, tier_lookup: object = None) -> dict:
        return resolve_collected_document(package, POLICY, self.uow, tier_lookup or self.tiers, _clock, self.ids)

    def articles(self) -> tuple:
        return self.uow.committed('article')

    def outbox(self) -> tuple:
        return self.uow.committed_outbox()

    def snapshot(self) -> tuple:
        kinds = ('collected_document_resolution', 'dedup_evidence', 'article_media_attachment')
        return (self.articles(), *(tuple(dict(r) for r in self.uow.committed(kind)) for kind in kinds), self.outbox())


def _assert_valid(resolution: dict, disposition: str, state: str) -> None:
    assert validate_collected_document_resolution(resolution) == []
    assert resolution['disposition'] == disposition
    assert resolution['dedup_policy_revision'] == POLICY['dedup_policy_revision']
    assert resolution['state'] == state
    assert tuple(resolution['state_trail']) == (*TRAIL, state)


def test_new_article_revision_comes_from_fixture_and_matches_resolution() -> None:
    env = _Env()
    package = _package()
    resolution = env.resolve(package)
    _assert_valid(resolution, NEW_ARTICLE, 'NEW_ARTICLE_ACCEPTED')
    (article,) = env.articles()
    (revision,) = article.revisions
    assert revision.title == 'Sample Title'
    assert revision.requested_url == package['requested_url']
    assert revision.article_revision_id == resolution['article_revision_id']
    assert revision.article_id == article.article_id == resolution['article_id']
    assert {resolution['article_id'], resolution['article_revision_id']} <= set(env.ids.issued)
    assert (revision.revision_number, revision.normalized_text) == (1, 'Sample text')
    assert revision.exact_fingerprint == exact_fingerprint('Sample text')
    assert (revision.source_id, revision.collected_document_id, revision.final_url) == (
        package['source_id'], package['collected_document_id'], package['final_url'],
    )
    assert [dict(step) for step in revision.provenance_chain] == package['provenance_chain']
    assert revision.fetched_at == '2026-10-18T08:00:00Z'
    assert (article.identity_key, article.representative_source_id) == (package['final_url'], SOURCE_A)
    assert dict(env.uow.resolutions.get(package['collected_document_id'], 'dedup-policy-r1')) == resolution
    assert resolution['resolved_at'] == '2026-10-18T09:00:00Z'


def test_missing_title_is_stored_as_empty_string() -> None:
    env = _Env()
    package = _package()
    del package['extracted_content_candidate']['title']
    resolution = env.resolve(package)
    (article,) = env.articles()
    assert article.revisions[0].title == ''
    assert 'title' in article.revisions[0].uncertain_fields
    assert article.revisions[0].article_revision_id == resolution['article_revision_id']


def test_new_article_emits_article_revision_accepted_without_text() -> None:
    env = _Env()
    resolution = env.resolve(_package())
    (record,) = env.outbox()
    assert (record.event_type, record.aggregate_id) == ('ArticleRevisionAccepted', resolution['article_id'])
    event = record.payload
    assert (event['event_name'], event['producer'], event['aggregate_type'], event['aggregate_revision']) == (
        'ArticleRevisionAccepted', 'B', 'Article', 1,
    )
    assert event['payload']['article_revision_id'] == resolution['article_revision_id']
    assert event['payload']['collected_document_id'] == resolution['collected_document_id']
    assert 'Sample text' not in repr(dict(event)) and 'Sample Title' not in repr(dict(event))


def test_changed_text_with_same_identity_is_new_revision() -> None:
    env = _Env()
    first = env.resolve(_package())
    second = env.resolve(_text(_package(2), 'Sample text updated with a correction'))
    _assert_valid(second, NEW_REVISION, 'NEW_REVISION_ACCEPTED')
    (article,) = env.articles()
    assert [r.article_revision_id for r in article.revisions] == [first['article_revision_id'], second['article_revision_id']]
    assert second['article_id'] == first['article_id']
    assert article.revisions[1].revision_number == 2
    assert [r.event_type for r in env.outbox()] == ['ArticleRevisionAccepted', 'ArticleRevisionAccepted']
    assert env.outbox()[1].payload['aggregate_revision'] == 2


def test_canonical_url_candidate_drives_identity_key() -> None:
    env = _Env()
    canonical = 'HTTPS://Example.COM/story/?id=7#top'
    first = env.resolve(_package(canonical_url_candidate=canonical))
    second = env.resolve(
        _text(_package(2, canonical_url_candidate=canonical, final_url='https://example.com/amp/story'), 'Sample text revised'),
    )
    assert (first['disposition'], second['disposition']) == (NEW_ARTICLE, NEW_REVISION)
    (article,) = env.articles()
    assert article.identity_key == 'https://example.com/story?id=7'


@pytest.mark.parametrize(('url', 'expected'), [
    ('HTTPS://Example.COM/a/?q=1#frag', 'https://example.com/a?q=1'),
    ('https://example.com/a/', 'https://example.com/a'),
    ('https://example.com/a?utm_source=x', 'https://example.com/a?utm_source=x'),
    ('https://example.com/', 'https://example.com'),
])
def test_identity_key_normalization(url: str, expected: str) -> None:
    assert identity_key(url) == expected


@pytest.mark.parametrize('final_url', ['https://example.com/article-1-final', 'https://mirror.example.net/repost-1'])
def test_exact_repost_without_new_value_creates_nothing(final_url: str) -> None:
    env = _Env()
    first = env.resolve(_package())
    repost = env.resolve(_package(2, final_url=final_url, requested_url=final_url))
    _assert_valid(repost, DUPLICATE_NO_NEW_VALUE, DUPLICATE_NO_NEW_VALUE)
    (article,) = env.articles()
    assert len(article.revisions) == 1
    assert repost['article_id'] == first['article_id'] and 'article_revision_id' not in repost
    record = env.outbox()[-1]
    assert (record.event_type, len(env.outbox())) == ('DuplicateDocumentResolved', 2)
    assert record.payload['aggregate_type'] == 'CollectedDocumentResolution'
    assert record.payload['payload']['article_id'] == first['article_id']
    assert 'new_media_discovery_refs' not in record.payload['payload']
    (evidence,) = env.uow.committed('dedup_evidence')
    assert evidence['collected_document_id'] == repost['collected_document_id']


def test_repost_with_new_media_attaches_media_to_representative() -> None:
    env = _Env()
    first = env.resolve(_package())
    media = [{'ref': 'media-discovery:m-1', 'kind': 'image'}, {'url': 'https://cdn.example.net/v.mp4', 'kind': 'video'}]
    repost = env.resolve(_package(2, source_id=SOURCE_C, final_url='https://other.example.org/r', media_discoveries=media))
    _assert_valid(repost, DUPLICATE_MEDIA_ONLY, DUPLICATE_MEDIA_ONLY)
    (article,) = env.articles()
    assert len(article.revisions) == 1 and repost['article_id'] == first['article_id']
    refs = ['media-discovery:m-1', 'https://cdn.example.net/v.mp4']
    assert list(attached_media_refs(env.uow, first['article_id'])) == refs
    record = env.outbox()[-1]
    assert record.event_type == 'DuplicateDocumentResolved'
    assert record.payload['payload']['new_media_discovery_refs'] == refs
    assert article.representative_source_id == SOURCE_A


def test_known_media_from_known_source_is_no_new_value() -> None:
    env = _Env()
    media = [{'ref': 'media-discovery:m-1'}]
    env.resolve(_package(media_discoveries=media))
    repost = env.resolve(_package(2, final_url='https://mirror.example.net/r', media_discoveries=media))
    assert repost['disposition'] == DUPLICATE_NO_NEW_VALUE
    (article,) = env.articles()
    assert list(attached_media_refs(env.uow, article.article_id)) == ['media-discovery:m-1']


def test_near_duplicate_from_new_source_is_media_only_with_new_provenance() -> None:
    env = _Env()
    first = env.resolve(_text(_package(), LONG_TEXT))
    near = env.resolve(_text(_package(2, source_id=SOURCE_C, final_url='https://other.example.org/near'), NEAR_TEXT))
    assert near['disposition'] == DUPLICATE_MEDIA_ONLY and near['article_id'] == first['article_id']
    assert len(env.articles()) == 1 and len(env.articles()[0].revisions) == 1
    assert env.outbox()[-1].payload['payload']['new_media_discovery_refs'] == []
    (evidence,) = env.uow.committed('dedup_evidence')
    assert evidence['match'] == 'near'


def test_higher_tier_duplicate_source_becomes_representative_for_future_production() -> None:
    env = _Env()
    first = env.resolve(_package())
    env.resolve(_package(2, source_id=SOURCE_B, final_url='https://tier1.example.org/a'))
    (article,) = env.articles()
    assert article.representative_source_id == SOURCE_B
    assert [r.article_revision_id for r in article.revisions] == [first['article_revision_id']]
    assert env.outbox()[-1].payload['payload']['representative_source_id'] == SOURCE_B
    (evidence,) = env.uow.committed('dedup_evidence')
    assert evidence['selection_reason'] == 'higher_tier'


@pytest.mark.parametrize(('mutate', 'reason'), [
    pytest.param(lambda p: p.pop('content_eligibility'), 'content_eligibility_absent', id='eligibility_absent'),
    pytest.param(lambda p: p.update(content_eligibility='incomplete'), 'content_incomplete', id='eligibility_incomplete'),
    pytest.param(lambda p: p['extracted_content_candidate'].update(text=' ​	 '), 'empty_main_text', id='blank_text'),
    pytest.param(lambda p: p.pop('extracted_content_candidate'), 'empty_main_text', id='no_content'),
])
def test_incomplete_package_is_rejected_without_article_or_event(mutate: Callable[[dict], object], reason: str) -> None:
    env = _Env()
    package = _package()
    mutate(package)
    resolution = env.resolve(package)
    _assert_valid(resolution, REJECTED_INCOMPLETE, REJECTED_INCOMPLETE)
    assert resolution['reason'] == reason
    assert 'article_id' not in resolution and 'article_revision_id' not in resolution
    assert env.articles() == () and env.outbox() == ()
    assert [dict(r) for r in env.uow.committed('collected_document_resolution')] == [resolution]


@pytest.mark.parametrize('case', [pytest.param(case, id=case['case']) for case in _fixture()['invalid']])
def test_invalid_package_raises_validation_error_before_received(case: dict) -> None:
    env = _Env()
    with pytest.raises(ResolveDocumentError) as raised:
        env.resolve(copy.deepcopy(case['payload']))
    assert (raised.value.code, raised.value.state) == (VALIDATION_ERROR, None)
    expected = case['expected_error']
    assert [(issue.code, issue.field) for issue in raised.value.issues] == [(expected['code'], expected['field'])]
    assert env.snapshot() == EMPTY
    assert env.ids.issued == []


@pytest.mark.parametrize('variant', ['new_article', 'duplicate', 'rejected'])
def test_resubmission_returns_same_resolution_without_new_writes(variant: str) -> None:
    env = _Env()
    package = _package()
    if variant == 'rejected':
        package.pop('content_eligibility')
    if variant == 'duplicate':
        env.resolve(_package(9))
        package = _package(2, final_url='https://mirror.example.net/r')
    first = env.resolve(package)
    assert validate_collected_document_resolution(first) == []
    before, issued = env.snapshot(), list(env.ids.issued)
    changed = _text(copy.deepcopy(package), 'Completely different body text for the same observation')
    assert env.resolve(package) == first
    assert env.resolve(changed) == first
    assert env.snapshot() == before and env.ids.issued == issued


@pytest.mark.parametrize(('port', 'method'), [('articles', 'save'), ('outbox', 'append_event'), ('resolutions', 'save')])
def test_infrastructure_error_is_failed_retryable_without_partial_writes(
    port: str, method: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _Env()

    def down(*args: object, **kwargs: object) -> None:
        raise ConnectionError('storage unavailable')

    monkeypatch.setattr(getattr(env.uow, port), method, down)
    with pytest.raises(ResolveDocumentError) as raised:
        env.resolve(_package())
    assert (raised.value.code, raised.value.state) == (FAILED_RETRYABLE, FAILED_RETRYABLE)
    assert isinstance(raised.value.__cause__, ConnectionError)
    assert env.snapshot() == EMPTY
    monkeypatch.undo()
    assert env.resolve(_package())['disposition'] == NEW_ARTICLE
    assert (len(env.articles()), len(env.outbox())) == (1, 1)


class _TierDown:
    def tier_of(self, source_id: str) -> int:
        raise TimeoutError('tier lookup timed out')


def test_tier_lookup_outage_on_duplicate_is_failed_retryable() -> None:
    env = _Env()
    env.resolve(_package())
    before = env.snapshot()
    with pytest.raises(ResolveDocumentError) as raised:
        env.resolve(_package(2, final_url='https://mirror.example.net/r'), tier_lookup=_TierDown())
    assert (raised.value.code, raised.value.state) == (FAILED_RETRYABLE, FAILED_RETRYABLE)
    assert env.snapshot() == before


def test_unknown_source_tier_is_failed_final() -> None:
    env = _Env(tiers={SOURCE_A: 2})
    env.resolve(_package())
    before = env.snapshot()
    with pytest.raises(ResolveDocumentError) as raised:
        env.resolve(_package(2, source_id=SOURCE_C, final_url='https://other.example.org/r'))
    assert (raised.value.code, raised.value.state) == (FAILED_FINAL, FAILED_FINAL)
    assert env.snapshot() == before
