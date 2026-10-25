"""RS-2: PostgreSQL tests for the read-only articles service (module B)."""
from __future__ import annotations

import ast
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, Page, parse_list_query
from controlplane.infrastructure.read_screens.articles import ArticleModuleService
from ingestion.domain.article import Article, ArticleRevision
from ingestion.persistence.repositories import PostgresArticleRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'articles.py'
ROW_KEYS = {'article_id', 'source_id', 'title', 'published_at', 'fetch_evidence_ref', 'revision', 'updated_at'}
FORBIDDEN_KEYS = {'normalized_text', 'requested_url', 'final_url', 'provenance_chain'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'normalized_text')
CANARIES = ('CANARY-NORMALIZED-TEXT', 'https://canary.example/requested', 'https://canary.example/final', 'CANARY-PROVENANCE')
UPDATED_AT = {
    'a-1': '2026-10-01T00:00:00.000000Z',
    'a-2': '2026-10-02T00:00:00.000000Z',
    'a-3': '2026-10-03T00:00:00.000000Z',
    'a-4': '2026-10-03T00:00:00.000000Z',
    'a-5': '2026-10-05T00:00:00.123456Z',
}
ASC = ['a-1', 'a-2', 'a-3', 'a-4', 'a-5']
DESC = ['a-5', 'a-4', 'a-3', 'a-2', 'a-1']


def make_revision(article_id: str, number: int, **overrides: Any) -> ArticleRevision:
    data: dict[str, Any] = {
        'article_revision_id': f'{article_id}-r{number}', 'article_id': article_id, 'revision_number': number,
        'title': f'Title {article_id} v{number}', 'normalized_text': 'CANARY-NORMALIZED-TEXT', 'source_id': 'src-a',
        'source_revision': 1, 'collection_run_id': 'run-1', 'collected_document_id': f'doc-{article_id}-{number}',
        'requested_url': 'https://canary.example/requested', 'final_url': 'https://canary.example/final',
        'provenance_chain': ({'step': 'CANARY-PROVENANCE'},), 'raw_snapshot_ref': f'snap-{article_id}-{number}',
        'published_at': '2026-10-20T00:00:00Z', 'published_at_confidence': 'HIGH', 'fetched_at': '2026-10-22T00:00:00Z',
        'topic': 'tech', 'topic_uncertain': False, 'exact_fingerprint': f'fp-{article_id}-{number}',
        'media_discovery_refs': (), 'extractor_version': '1.0', 'normalizer_version': '1.0', 'is_complete': True,
        'uncertain_fields': (),
    }
    data.update(overrides)
    return ArticleRevision(**data)


def save_article(manager: Any, workspace_id: str, article_id: str, *revisions: ArticleRevision, updated_at: str) -> None:
    article = Article(article_id=article_id, identity_key=f'idk-{article_id}', representative_source_id='src-a', revisions=tuple(revisions))
    with manager.borrow_connection() as connection:
        PostgresArticleRepository(lambda: connection, workspace_id).save(article)
        # save() stamps updated_at with the transaction time; pin it so ordering and ties are deterministic.
        connection.execute('UPDATE controlplane.cp_articles SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND article_id = %s', (updated_at, workspace_id, article_id))


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: ArticleModuleService


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        rev = make_revision
        save_article(manager, workspace_id, 'a-1', rev('a-1', 1, title='Alpha', source_id='src-a', raw_snapshot_ref='snap-a-1'), updated_at=UPDATED_AT['a-1'])
        save_article(manager, workspace_id, 'a-2', rev('a-2', 1, title='Beta v1', source_id='src-old', raw_snapshot_ref='snap-b-1'), rev('a-2', 2, title='Beta v2', source_id='src-b', raw_snapshot_ref='snap-b-2'), updated_at=UPDATED_AT['a-2'])
        save_article(manager, workspace_id, 'a-3', rev('a-3', 1, title='Gamma', source_id='src-a', published_at=None, raw_snapshot_ref=None), updated_at=UPDATED_AT['a-3'])
        save_article(manager, workspace_id, 'a-4', rev('a-4', 1, title='Delta', source_id='src-b'), updated_at=UPDATED_AT['a-4'])
        save_article(manager, workspace_id, 'a-5', rev('a-5', 1, title='Epsilon', source_id='src-a'), updated_at=UPDATED_AT['a-5'])
        save_article(manager, other_workspace_id, 'a-1', rev('a-1', 1, title='Other Alpha', source_id='src-a'), updated_at='2026-10-04T00:00:00.000000Z')
        save_article(manager, other_workspace_id, 'w2-1', rev('w2-1', 1, title='Other Only', source_id='src-a'), updated_at='2026-10-06T00:00:00.000000Z')
        yield Env(manager, workspace_id, other_workspace_id, ArticleModuleService(manager.borrow_connection))


A2_ROW = {'article_id': 'a-2', 'source_id': 'src-b', 'title': 'Beta v2', 'published_at': '2026-10-20T00:00:00Z', 'fetch_evidence_ref': 'snap-b-2', 'revision': 2, 'updated_at': UPDATED_AT['a-2']}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['updated_at'], allowed_filters={'source_id'}, default_limit=20, max_limit=100)


def get_page(env: Env, params: dict[str, str], workspace_id: str | None = None) -> Page:
    workspace_id = workspace_id or env.workspace_id
    return env.service.fetch_page(rs_support.FakeRequest(workspace_id, params), workspace_id, make_query(params))


def get_one(env: Env, item_id: str, workspace_id: str | None = None) -> dict[str, Any] | None:
    workspace_id = workspace_id or env.workspace_id
    return env.service.fetch_one(rs_support.FakeRequest(workspace_id), workspace_id, item_id)


def walk(env: Env, params: dict[str, str], limit: int, workspace_id: str | None = None) -> list[Page]:
    pages: list[Page] = []
    cursor = None
    for _ in range(20):
        step = {**params, 'limit': str(limit)}
        if cursor is not None:
            step['cursor'] = cursor
        page = get_page(env, step, workspace_id)
        pages.append(page)
        cursor = page.next_cursor
        if cursor is None:
            return pages
    raise AssertionError('pagination did not terminate')


def ids(page: Page) -> list[str]:
    return [item['article_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [article_id for page in pages for article_id in ids(page)]


def test_rows_have_exact_keys_and_show_latest_revision(env):
    page = get_page(env, {})
    assert ids(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    rows = {item['article_id']: item for item in page.items}
    assert rows['a-2'] == A2_ROW
    assert rows['a-1']['title'] == 'Alpha' and rows['a-1']['revision'] == 1
    assert rows['a-1']['fetch_evidence_ref'] == 'snap-a-1'
    assert rows['a-3']['published_at'] is None and rows['a-3']['fetch_evidence_ref'] is None
    assert [item['updated_at'] for item in page.items] == [UPDATED_AT[i] for i in DESC]


def test_direction_defaults_to_desc_and_honours_explicit_direction(env):
    assert ids(get_page(env, {})) == DESC
    assert ids(get_page(env, {'direction': 'desc'})) == DESC
    assert ids(get_page(env, {'direction': 'asc'})) == ASC


@pytest.mark.parametrize('direction, expected', [('asc', ASC), ('desc', DESC)])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, expected, limit):
    pages = walk(env, {'direction': direction}, limit)
    assert all_ids(pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_direction_pagination_is_newest_first(env):
    pages = walk(env, {}, 2)
    assert len(pages) == 3
    assert all_ids(pages) == DESC


@pytest.mark.parametrize('source_id, expected', [('src-a', ['a-5', 'a-3', 'a-1']), ('src-b', ['a-4', 'a-2']), ('src-old', []), ('src-unknown', []), ('', [])])
def test_source_id_filter_uses_latest_revision_and_unknown_value_is_empty(env, source_id, expected):
    page = get_page(env, {'source_id': source_id})
    assert ids(page) == expected
    assert page.next_cursor is None


def test_source_id_filter_paginates(env):
    pages = walk(env, {'source_id': 'src-a', 'direction': 'asc'}, 2)
    assert len(pages) == 2
    assert all_ids(pages) == ['a-1', 'a-3', 'a-5']


def test_unsupported_filter_name_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=(('status', 'x'),))
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_fetch_one_returns_latest_revision_row_or_none(env):
    assert get_one(env, 'a-2') == A2_ROW
    assert set(get_one(env, 'a-3')) == ROW_KEYS
    assert get_one(env, 'nope') is None


def test_workspaces_are_isolated(env):
    mine = get_page(env, {})
    theirs = get_page(env, {}, env.other_workspace_id)
    assert ids(mine) == DESC
    assert ids(theirs) == ['w2-1', 'a-1']
    assert {item['title'] for item in theirs.items} == {'Other Alpha', 'Other Only'}
    assert not {'Other Alpha', 'Other Only'} & {item['title'] for item in mine.items}
    assert get_one(env, 'w2-1') is None
    assert get_one(env, 'a-2', env.other_workspace_id) is None
    assert get_one(env, 'a-1')['title'] == 'Alpha'
    assert get_one(env, 'a-1', env.other_workspace_id)['title'] == 'Other Alpha'
    assert ids(get_page(env, {'source_id': 'src-b'}, env.other_workspace_id)) == []
    assert all_ids(walk(env, {}, 1, env.other_workspace_id)) == ['w2-1', 'a-1']


def count_rows(env: Env) -> tuple[int, int]:
    with env.manager.borrow_connection() as connection:
        articles = connection.execute('SELECT count(*) FROM controlplane.cp_articles').fetchone()[0]
        revisions = connection.execute('SELECT count(*) FROM controlplane.cp_article_revisions').fetchone()[0]
    return (articles, revisions)


def test_service_does_not_change_source_tables(env):
    before = count_rows(env)
    assert before == (7, 8)
    get_page(env, {})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'a-2')
    get_one(env, 'nope')
    assert count_rows(env) == before
    assert [item['updated_at'] for item in get_page(env, {}).items] == [UPDATED_AT[i] for i in DESC]


class CountingConnection:
    def __init__(self, inner: Any, statements: list[str]) -> None:
        self._inner = inner
        self._statements = statements

    def execute(self, query: Any, params: Any = None) -> Any:
        self._statements.append(str(query))
        return self._inner.execute(query, params)


def test_one_query_per_call_whatever_the_article_count(env):
    statements: list[str] = []

    @contextmanager
    def scope():
        with env.manager.borrow_connection() as connection:
            yield CountingConnection(connection, statements)

    service = ArticleModuleService(scope)
    for workspace_id, expected in ((env.workspace_id, 5), (env.other_workspace_id, 2)):
        statements.clear()
        page = service.fetch_page(rs_support.FakeRequest(workspace_id, {}), workspace_id, make_query({}))
        assert len(page.items) == expected
        assert len(statements) == 1
        sql_text = ' '.join(statements[0].lower().split())
        assert 'cp_article_revisions' in sql_text and 'r.revision = a.revision' in sql_text
    statements.clear()
    assert service.fetch_one(rs_support.FakeRequest(env.workspace_id), env.workspace_id, 'a-2') is not None
    assert len(statements) == 1


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'a-1'), ('', 'a-1'), ('2026-13-45T01:02:03Z', 'a-1'), ('2026-10-25', 'a-1')])
def test_invalid_cursor_time_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='updated_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows = [*get_page(env, {}).items, *get_page(env, {}, env.other_workspace_id).items, get_one(env, 'a-2'), get_one(env, 'a-3')]
    text = json.dumps(rows)
    assert not [canary for canary in CANARIES if canary in text]
    assert all(not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'r.revision = a.revision' in text
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
