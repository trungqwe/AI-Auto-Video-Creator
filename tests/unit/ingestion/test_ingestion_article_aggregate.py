"""B-3: Article / ArticleRevision aggregate (CT-CNT-003); stored revisions are immutable."""
import dataclasses

import pytest

from ingestion.domain.article import Article, ArticleRevision

CT_CNT_003_FIELDS = {
    'article_revision_id', 'article_id', 'revision_number', 'title', 'normalized_text',
    'source_id', 'source_revision', 'collection_run_id', 'collected_document_id',
    'requested_url', 'final_url', 'provenance_chain', 'raw_snapshot_ref',
    'published_at', 'published_at_confidence', 'fetched_at', 'topic', 'topic_uncertain',
    'exact_fingerprint', 'media_discovery_refs', 'extractor_version', 'normalizer_version',
    'is_complete', 'uncertain_fields',
}
ARTICLE_FIELDS = {'article_id', 'identity_key', 'representative_source_id', 'revisions'}


def _revision_kwargs(number: int = 1, **overrides: object) -> dict:
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
    return kwargs


def _revision(number: int = 1, **overrides: object) -> ArticleRevision:
    return ArticleRevision(**_revision_kwargs(number, **overrides))


def _article(*revisions: ArticleRevision) -> Article:
    return Article(article_id='art-1', identity_key='https://example.com/a', representative_source_id='src-1', revisions=revisions)

def test_revision_declares_ct_cnt_003_fields_without_defaults() -> None:
    fields = dataclasses.fields(ArticleRevision)
    assert {f.name for f in fields} == CT_CNT_003_FIELDS
    assert all(f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING for f in fields)
    assert {f.name for f in dataclasses.fields(Article)} == ARTICLE_FIELDS


@pytest.mark.parametrize('name', ['article_revision_id', 'title', 'requested_url'])
def test_missing_required_field_raises_type_error(name: str) -> None:
    kwargs = _revision_kwargs()
    del kwargs[name]
    with pytest.raises(TypeError):
        ArticleRevision(**kwargs)


def test_revision_is_frozen() -> None:
    revision = _revision()
    with pytest.raises(dataclasses.FrozenInstanceError):
        revision.title = 'Changed'


def test_with_revision_returns_new_article_and_keeps_old_revision() -> None:
    first_revision = _revision(1)
    before = (first_revision.article_revision_id, first_revision.title, first_revision.requested_url)
    first = _article(first_revision)
    second = first.with_revision(_revision(2, title='Updated Title', requested_url='https://example.com/b'))
    assert second is not first
    assert first.revisions == (first_revision,)
    assert [r.revision_number for r in second.revisions] == [1, 2]
    assert second.revisions[0] is first_revision
    kept = second.revisions[0]
    assert (kept.article_revision_id, kept.title, kept.requested_url) == before
    assert second.latest_revision.title == 'Updated Title'
    assert second.next_revision_number == 3


def test_revision_number_must_increase_by_one() -> None:
    first = _article(_revision(1))
    for number in (1, 3):
        with pytest.raises(ValueError):
            first.with_revision(_revision(number, article_revision_id=f'rev-new-{number}'))
    for revisions in ((_revision(2),), (_revision(1), _revision(3)), (_revision(1, revision_number=True),)):
        with pytest.raises(ValueError):
            _article(*revisions)


def test_revision_of_other_article_or_duplicate_id_is_rejected() -> None:
    first = _article(_revision(1))
    with pytest.raises(ValueError):
        first.with_revision(_revision(2, article_id='art-2'))
    with pytest.raises(ValueError):
        first.with_revision(_revision(2, article_revision_id='rev-1'))


def test_revision_copies_mutable_inputs() -> None:
    kwargs = _revision_kwargs()
    revision = ArticleRevision(**kwargs)
    kwargs['provenance_chain'][0]['step'] = 'tampered'
    kwargs['provenance_chain'].append({'step': 'extra'})
    kwargs['media_discovery_refs'].append('media-2')
    assert revision.provenance_chain[0]['step'] == 'final_fetch'
    assert len(revision.provenance_chain) == 1
    assert revision.media_discovery_refs == ('media-1',)
    assert isinstance(revision.uncertain_fields, tuple)
    with pytest.raises(TypeError):
        revision.provenance_chain[0]['step'] = 'x'
