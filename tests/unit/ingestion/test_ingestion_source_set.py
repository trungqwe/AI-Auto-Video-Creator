"""B-9: pinned source set and timeline eligibility for ProductionSnapshot (CT-AI-001, TST-INT-INV-004, TST-CTR-INV-006)."""
import hashlib
import json
import pathlib
import re
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields

import pytest

from ingestion.application.source_set import (
    FROM_THEN_TO_NOW,
    MULTI_ARTICLE_EVENT,
    PRODUCTION_MODES,
    SINGLE_ARTICLE,
    SOURCE_REF_FIELDS,
    SourceSet,
    SourceSetRejected,
    build_source_set,
)
from ingestion.domain.article import Article, ArticleRevision
from ingestion.infrastructure.memory import InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE_PATH = ROOT / 'src' / 'ingestion' / 'application' / 'source_set.py'
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'b-d-production-snapshot.json'
BOUNDARY_RE = re.compile(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)')
WRITE_CALL_RE = re.compile(r'\.(save|put|commit|rollback|append_event)\(|\bwith\s+[\w.]*uow\b')
SHA256_RE = re.compile(r'[0-9a-f]{64}')
UPDATE_KIND = 'event_update'


def _revision(article_id: str, number: int = 1, *, source_id: str | None = None, source_revision: int = 3) -> ArticleRevision:
    return ArticleRevision(
        article_revision_id=f'{article_id}-r{number}',
        article_id=article_id,
        revision_number=number,
        title=f'Tieu de {article_id}',
        normalized_text=f'noi dung {article_id} {number}',
        source_id=source_id if source_id is not None else f'src-{article_id}',
        source_revision=source_revision,
        collection_run_id='run-b9',
        collected_document_id=f'doc-{article_id}-{number}',
        requested_url=f'https://example.invalid/{article_id}',
        final_url=f'https://example.invalid/{article_id}',
        provenance_chain=({'step': 'final_fetch'},),
        raw_snapshot_ref=f'snapshot://{article_id}/{number}',
        published_at='2026-10-18T08:00:00Z',
        published_at_confidence='high',
        fetched_at='2026-10-18T09:00:00Z',
        topic='thoi-tiet',
        topic_uncertain=False,
        exact_fingerprint=f'fp-{article_id}-{number}',
        media_discovery_refs=(),
        extractor_version='extractor-r1',
        normalizer_version='normalize-text-r1',
        is_complete=True,
        uncertain_fields=(),
    )


def _article(article_id: str, *revisions: ArticleRevision) -> Article:
    return Article(
        article_id=article_id,
        identity_key=f'key-{article_id}',
        representative_source_id=revisions[0].source_id,
        revisions=tuple(revisions),
    )


def _event(event_id: str, *revisions: ArticleRevision) -> dict:
    refs = tuple((revision.article_id, revision.article_revision_id) for revision in revisions)
    return {'event_id': event_id, 'status': 'candidate', 'revision': 1, 'topic': 'thoi-tiet', 'member_refs': refs}


def _update(event_id: str, revision: ArticleRevision, state: str = 'ACCEPTED_NEW_DEVELOPMENT') -> dict:
    return {
        'event_update_id': f'upd-{event_id}-{revision.article_revision_id}',
        'event_id': event_id,
        'article_id': revision.article_id,
        'article_revision_id': revision.article_revision_id,
        'new_claim_refs': ('claim-1',),
        'state': state,
    }


def _seed(articles: list, events: list = (), updates: list = ()) -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork(id_factory=lambda: 'outbox-unused')
    with uow:
        for article in articles:
            uow.articles.save(article)
        for event in events:
            uow.events.save(event)
        for update in updates:
            uow.records.put(UPDATE_KIND, update['event_update_id'], update)
        uow.commit()
    return uow


def _commit(uow: InMemoryUnitOfWork, *, article: Article | None = None, update: dict | None = None) -> None:
    with uow:
        if article is not None:
            uow.articles.save(article)
        if update is not None:
            uow.records.put(UPDATE_KIND, update['event_update_id'], update)
        uow.commit()


A1 = _revision('art-a')
A2 = _revision('art-a', 2, source_revision=4)
B1 = _revision('art-b', source_id='src-shared')
C1 = _revision('art-c', source_id='src-shared', source_revision=7)


def _ref(revision: ArticleRevision) -> dict:
    return {
        'article_id': revision.article_id,
        'article_revision_id': revision.article_revision_id,
        'source_id': revision.source_id,
        'source_revision': revision.source_revision,
    }


def _refs(source_set: SourceSet) -> list[dict]:
    return [dict(ref) for ref in source_set.source_refs]


def _digest(refs: list[dict]) -> str:
    return hashlib.sha256(json.dumps(refs, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _reason(mode: str, subject_id: str, uow: InMemoryUnitOfWork) -> str:
    with pytest.raises(SourceSetRejected) as info:
        build_source_set(mode, subject_id, uow)
    return info.value.reason


def _corpus(*, updates: list = (), members: tuple = (A1, B1)) -> InMemoryUnitOfWork:
    articles = [_article('art-a', A1), _article('art-b', B1), _article('art-c', C1)]
    return _seed(articles, [_event('evt-1', *members)], list(updates))


def _binding_fields() -> dict[str, dict]:
    entities = json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']
    entity = next(item for item in entities if item['name'] == 'ProductionSnapshot')
    return {field['name']: field for field in entity['fields']}


def test_production_modes_match_binding_enum() -> None:
    assert PRODUCTION_MODES == tuple(_binding_fields()['production_mode']['enum'])


def test_source_set_fields_match_binding_names_and_types() -> None:
    binding = _binding_fields()
    names = {field.name for field in fields(SourceSet)}
    assert names == {'production_mode', 'source_refs', 'source_set_fingerprint', 'eligibility_reason'}
    assert all(binding[name]['required'] for name in names)
    assert (binding['production_mode']['type'], binding['source_refs']['type'], binding['source_refs']['items']) == ('string', 'array', 'object')
    assert (binding['source_set_fingerprint']['type'], binding['eligibility_reason']['type']) == ('sha256', 'string')
    result = build_source_set(SINGLE_ARTICLE, 'art-a', _seed([_article('art-a', A1)]))
    assert isinstance(result, SourceSet)
    assert result.production_mode in binding['production_mode']['enum']
    assert isinstance(result.source_refs, tuple) and result.source_refs
    assert all(isinstance(ref, Mapping) for ref in result.source_refs)
    assert SHA256_RE.fullmatch(result.source_set_fingerprint)
    assert isinstance(result.eligibility_reason, str) and result.eligibility_reason


def test_source_ref_has_exact_field_names_and_types() -> None:
    assert SOURCE_REF_FIELDS == ('article_id', 'article_revision_id', 'source_id', 'source_revision')
    result = build_source_set(SINGLE_ARTICLE, 'art-a', _seed([_article('art-a', A1)]))
    assert result.source_refs
    for ref in result.source_refs:
        assert set(ref) == set(SOURCE_REF_FIELDS)
        assert [type(ref[name]) for name in SOURCE_REF_FIELDS] == [str, str, str, int]


def test_single_article_pins_latest_revision_as_representative() -> None:
    result = build_source_set(SINGLE_ARTICLE, 'art-a', _seed([_article('art-a', A1, A2)]))
    assert result.production_mode == SINGLE_ARTICLE
    assert _refs(result) == [_ref(A2)]
    assert result.eligibility_reason == 'single_article_eligible'
    assert result.source_set_fingerprint == _digest([_ref(A2)])


def test_single_article_without_revision_is_rejected() -> None:
    empty = Article(article_id='art-e', identity_key='key-e', representative_source_id='src-e')
    assert _reason(SINGLE_ARTICLE, 'art-e', _seed([empty])) == 'no_representative_revision'


def test_single_article_unknown_subject_raises_lookup_error() -> None:
    with pytest.raises(LookupError):
        build_source_set(SINGLE_ARTICLE, 'art-missing', _seed([_article('art-a', A1)]))


def test_multi_article_event_pins_every_member_revision() -> None:
    result = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', _corpus(members=(A1, B1, C1)))
    expected = [_ref(A1), _ref(B1), _ref(C1)]
    assert result.production_mode == MULTI_ARTICLE_EVENT
    assert _refs(result) == expected
    assert result.eligibility_reason == 'multi_article_event_eligible'
    assert result.source_set_fingerprint == _digest(expected)


@pytest.mark.parametrize('members', [(A1,), (A1, A2)], ids=['one_member', 'two_revisions_of_one_article'])
def test_multi_article_event_needs_two_linked_articles(members: tuple) -> None:
    uow = _seed([_article('art-a', A1, A2)], [_event('evt-1', *members)])
    assert _reason(MULTI_ARTICLE_EVENT, 'evt-1', uow) == 'event_needs_two_linked_articles'


def test_multi_article_event_unknown_event_raises_lookup_error() -> None:
    with pytest.raises(LookupError):
        build_source_set(MULTI_ARTICLE_EVENT, 'evt-missing', _corpus())


def test_multi_article_event_member_without_stored_revision_raises_lookup_error() -> None:
    event = {**_event('evt-1', A1, B1), 'member_refs': (('art-a', 'art-a-r1'), ('art-b', 'art-b-r9'))}
    uow = _seed([_article('art-a', A1), _article('art-b', B1)], [event])
    with pytest.raises(LookupError):
        build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', uow)


def test_from_then_to_now_without_update_is_rejected() -> None:
    assert _reason(FROM_THEN_TO_NOW, 'evt-1', _corpus()) == 'event_update_not_accepted'


@pytest.mark.parametrize('state', ['REJECTED_REPOST', 'REJECTED_NO_NEW_FACT', 'UNCERTAIN', 'PROPOSED'])
def test_from_then_to_now_with_non_accepted_update_is_rejected(state: str) -> None:
    uow = _corpus(updates=[_update('evt-1', C1, state)])
    assert _reason(FROM_THEN_TO_NOW, 'evt-1', uow) == 'event_update_not_accepted'


def test_from_then_to_now_ignores_update_of_another_event() -> None:
    uow = _corpus(updates=[_update('evt-2', C1)])
    assert _reason(FROM_THEN_TO_NOW, 'evt-1', uow) == 'event_update_not_accepted'


def test_from_then_to_now_with_accepted_update_pins_members_and_update_revision() -> None:
    result = build_source_set(FROM_THEN_TO_NOW, 'evt-1', _corpus(updates=[_update('evt-1', C1)]))
    expected = [_ref(A1), _ref(B1), _ref(C1)]
    assert result.production_mode == FROM_THEN_TO_NOW
    assert _refs(result) == expected
    assert result.eligibility_reason == 'from_then_to_now_eligible'
    assert result.source_set_fingerprint == _digest(expected)


def test_from_then_to_now_does_not_duplicate_update_revision_that_is_a_member() -> None:
    result = build_source_set(FROM_THEN_TO_NOW, 'evt-1', _corpus(updates=[_update('evt-1', B1)]))
    assert _refs(result) == [_ref(A1), _ref(B1)]


def test_from_then_to_now_unknown_event_raises_lookup_error() -> None:
    with pytest.raises(LookupError):
        build_source_set(FROM_THEN_TO_NOW, 'evt-missing', _corpus(updates=[_update('evt-1', C1)]))


def test_timeline_eligibility_follows_accepted_update() -> None:
    uow = _corpus()
    assert _reason(FROM_THEN_TO_NOW, 'evt-1', uow) == 'event_update_not_accepted'
    _commit(uow, update=_update('evt-1', C1))
    result = build_source_set(FROM_THEN_TO_NOW, 'evt-1', uow)
    assert _refs(result) == [_ref(A1), _ref(B1), _ref(C1)]


def test_returned_refs_do_not_change_when_a_new_revision_arrives() -> None:
    uow = _seed([_article('art-a', A1)])
    first = build_source_set(SINGLE_ARTICLE, 'art-a', uow)
    before = (_refs(first), first.source_set_fingerprint)
    _commit(uow, article=_article('art-a', A1, A2))
    assert (_refs(first), first.source_set_fingerprint) == before
    assert _refs(first) == [_ref(A1)]
    second = build_source_set(SINGLE_ARTICLE, 'art-a', uow)
    assert _refs(second) == [_ref(A2)]
    assert second.source_set_fingerprint != first.source_set_fingerprint


@pytest.mark.parametrize('mode', [MULTI_ARTICLE_EVENT, FROM_THEN_TO_NOW])
def test_event_source_set_keeps_pinned_member_revisions_after_new_revision(mode: str) -> None:
    uow = _corpus(updates=[_update('evt-1', C1)])
    first = build_source_set(mode, 'evt-1', uow)
    _commit(uow, article=_article('art-a', A1, A2))
    again = build_source_set(mode, 'evt-1', uow)
    assert _refs(again) == _refs(first)
    assert again.source_set_fingerprint == first.source_set_fingerprint
    assert all(ref['article_revision_id'] != 'art-a-r2' for ref in again.source_refs)


def test_source_set_is_immutable() -> None:
    result = build_source_set(SINGLE_ARTICLE, 'art-a', _seed([_article('art-a', A1)]))
    assert result.source_refs and isinstance(result.source_refs, tuple)
    with pytest.raises(FrozenInstanceError):
        result.source_set_fingerprint = 'x'
    with pytest.raises(TypeError):
        result.source_refs[0]['source_revision'] = 99


def test_fingerprint_does_not_depend_on_member_order() -> None:
    forward = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', _corpus(members=(A1, B1, C1)))
    reverse = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', _corpus(members=(C1, B1, A1)))
    sorted_refs = [_ref(A1), _ref(B1), _ref(C1)]
    assert _refs(forward) == _refs(reverse) == sorted_refs
    assert forward.source_set_fingerprint == reverse.source_set_fingerprint == _digest(sorted_refs)
    assert _digest(list(reversed(sorted_refs))) != forward.source_set_fingerprint


def test_fingerprint_changes_with_member_set_and_source_revision() -> None:
    base = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', _corpus(members=(A1, B1)))
    other_member = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', _corpus(members=(A1, C1)))
    bumped = _revision('art-a', source_revision=9)
    uow = _seed([_article('art-a', bumped), _article('art-b', B1)], [_event('evt-1', bumped, B1)])
    other_source_revision = build_source_set(MULTI_ARTICLE_EVENT, 'evt-1', uow)
    fingerprints = {base.source_set_fingerprint, other_member.source_set_fingerprint, other_source_revision.source_set_fingerprint}
    assert len(fingerprints) == 3


@pytest.mark.parametrize('mode', ['timeline', '', None, 1, 'SINGLE_ARTICLE'])
def test_invalid_production_mode_raises_value_error(mode: object) -> None:
    with pytest.raises(ValueError):
        build_source_set(mode, 'art-a', _seed([_article('art-a', A1)]))


@pytest.mark.parametrize('subject_id', ['', None, 5])
def test_invalid_subject_id_raises_value_error(subject_id: object) -> None:
    with pytest.raises(ValueError):
        build_source_set(SINGLE_ARTICLE, subject_id, _seed([_article('art-a', A1)]))


def test_rejection_is_not_a_value_error_and_carries_reason() -> None:
    assert not issubclass(SourceSetRejected, ValueError)
    rejected = SourceSetRejected('event_update_not_accepted')
    assert rejected.reason == 'event_update_not_accepted'
    assert str(rejected) == 'event_update_not_accepted'


def test_build_source_set_never_writes() -> None:
    uow = _corpus(updates=[_update('evt-1', C1)])

    def state() -> tuple:
        return (uow.committed('article'), uow.committed('event'), uow.committed(UPDATE_KIND), uow.committed_outbox())

    before = state()
    for mode, subject_id in ((SINGLE_ARTICLE, 'art-a'), (MULTI_ARTICLE_EVENT, 'evt-1'), (FROM_THEN_TO_NOW, 'evt-1')):
        assert build_source_set(mode, subject_id, uow).source_refs
    assert state() == before


def test_boundary_regex_detects_forbidden_imports() -> None:
    for line in ('from src.controlplane import x', 'import requests', '    import socket', 'from urllib.parse import urlparse', 'import psycopg'):
        assert BOUNDARY_RE.search(line), line
    for line in ('import json', 'from dataclasses import dataclass', 'from ingestion.domain import article'):
        assert not BOUNDARY_RE.search(line), line


def test_source_set_source_has_no_write_calls_or_forbidden_imports() -> None:
    text = SOURCE_PATH.read_text(encoding='utf-8')
    assert not BOUNDARY_RE.search(text)
    assert not WRITE_CALL_RE.search(text)
