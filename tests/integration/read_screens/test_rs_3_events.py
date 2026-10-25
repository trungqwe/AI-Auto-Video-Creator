"""RS-3: PostgreSQL tests for the read-only events service (module B)."""
from __future__ import annotations

import ast
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, Page, parse_list_query
from controlplane.infrastructure.read_screens.events import EventModuleService
from ingestion.domain.article import Article, ArticleRevision
from ingestion.persistence.repositories import PostgresArticleRepository, PostgresEventRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'events.py'
ROW_KEYS = {'event_id', 'title', 'status', 'source_id', 'fetch_evidence_ref', 'revision', 'updated_at'}
FORBIDDEN_KEYS = {'member_refs', 'effective_time_range', 'topic', 'normalized_text', 'requested_url', 'final_url', 'provenance_chain'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'normalized_text')
CANARIES = (
    'CANARY-TOPIC',
    'CANARY-RANGE-START',
    'CANARY-RANGE-END',
    'CANARY-MEMBER-ARTICLE',
    'CANARY-MEMBER-REVISION',
    'CANARY-NORMALIZED-TEXT',
    'https://canary.example/requested',
    'https://canary.example/final',
    'CANARY-PROVENANCE',
)
UPDATED_AT = {
    'e-1': '2026-10-01T00:00:00.000000Z',
    'e-2': '2026-10-02T00:00:00.000000Z',
    'e-3': '2026-10-03T00:00:00.000000Z',
    'e-4': '2026-10-03T00:00:00.000000Z',
    'e-5': '2026-10-05T00:00:00.123456Z',
    'e-6': '2026-10-06T00:00:00.000000Z',
    'other-e-1': '2026-10-04T00:00:00.000000Z',
    'w2-1': '2026-10-07T00:00:00.000000Z',
}
ASC = ['e-1', 'e-2', 'e-3', 'e-4', 'e-5', 'e-6']
DESC = ['e-6', 'e-5', 'e-4', 'e-3', 'e-2', 'e-1']


def make_revision(article_id: str, number: int, **overrides: Any) -> ArticleRevision:
    data: dict[str, Any] = {
        'article_revision_id': f'{article_id}-r{number}',
        'article_id': article_id,
        'revision_number': number,
        'title': f'Title {article_id} v{number}',
        'normalized_text': 'CANARY-NORMALIZED-TEXT',
        'source_id': 'src-a',
        'source_revision': 1,
        'collection_run_id': 'run-1',
        'collected_document_id': f'doc-{article_id}-{number}',
        'requested_url': 'https://canary.example/requested',
        'final_url': 'https://canary.example/final',
        'provenance_chain': ({'step': 'CANARY-PROVENANCE'},),
        'raw_snapshot_ref': f'snap-{article_id}-{number}',
        'published_at': '2026-10-20T00:00:00Z',
        'published_at_confidence': 'HIGH',
        'fetched_at': '2026-10-22T00:00:00Z',
        'topic': 'tech',
        'topic_uncertain': False,
        'exact_fingerprint': f'fp-{article_id}-{number}',
        'media_discovery_refs': (),
        'extractor_version': '1.0',
        'normalizer_version': '1.0',
        'is_complete': True,
        'uncertain_fields': (),
    }
    data.update(overrides)
    return ArticleRevision(**data)


def save_article(manager: Any, workspace_id: str, article_id: str, *revisions: ArticleRevision) -> None:
    article = Article(
        article_id=article_id,
        identity_key=f'idk-{article_id}',
        representative_source_id='src-a',
        revisions=tuple(revisions),
    )
    with manager.borrow_connection() as connection:
        PostgresArticleRepository(lambda: connection, workspace_id).save(article)


def save_event(
    manager: Any,
    workspace_id: str,
    event_id: str,
    *,
    status: str,
    revision: int,
    member_refs: Any,
    updated_at: str,
) -> None:
    event = {
        'event_id': event_id,
        'status': status,
        'revision': revision,
        'topic': 'CANARY-TOPIC',
        'member_refs': member_refs,
        'effective_time_range': ('CANARY-RANGE-START', 'CANARY-RANGE-END'),
        'event_link_policy_revision': 'elp-1',
        'created_at': '2026-09-30T00:00:00Z',
        'updated_at': '2000-01-01T00:00:00Z',
    }
    with manager.borrow_connection() as connection:
        PostgresEventRepository(lambda: connection, workspace_id).save(event)
        connection.execute(
            'UPDATE controlplane.cp_events SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND event_id = %s',
            (updated_at, workspace_id, event_id),
        )


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: EventModuleService


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        rev = make_revision
        save_article(manager, workspace_id, 'a-1', rev('a-1', 1, title='Alpha', source_id='src-a', raw_snapshot_ref='snap-a-1'))
        save_article(
            manager,
            workspace_id,
            'a-2',
            rev('a-2', 1, title='Beta v1', source_id='src-old', raw_snapshot_ref='snap-b-1'),
            rev('a-2', 2, title='Beta v2', source_id='src-b', raw_snapshot_ref='snap-b-2'),
        )
        save_article(manager, workspace_id, 'a-3', rev('a-3', 1, title='Gamma', source_id='src-a', raw_snapshot_ref='snap-a-3'))

        save_event(manager, workspace_id, 'e-1', status='candidate', revision=1, member_refs=(('a-1', 'a-1-r1'),), updated_at=UPDATED_AT['e-1'])
        save_event(manager, workspace_id, 'e-2', status='confirmed', revision=2, member_refs=(('a-2', 'a-2-r1'), ('a-3', 'a-3-r1')), updated_at=UPDATED_AT['e-2'])
        save_event(manager, workspace_id, 'e-3', status='candidate', revision=1, member_refs=(('CANARY-MEMBER-ARTICLE', 'CANARY-MEMBER-REVISION'),), updated_at=UPDATED_AT['e-3'])
        save_event(manager, workspace_id, 'e-4', status='confirmed', revision=1, member_refs=(), updated_at=UPDATED_AT['e-4'])
        save_event(manager, workspace_id, 'e-5', status='candidate', revision=3, member_refs=(('a-2', 'a-2-r2'),), updated_at=UPDATED_AT['e-5'])
        save_event(manager, workspace_id, 'e-6', status='candidate', revision=1, member_refs=(('a-1', 'a-1-r9'),), updated_at=UPDATED_AT['e-6'])

        save_article(manager, other_workspace_id, 'a-1', rev('a-1', 1, title='Other Alpha', source_id='src-other', raw_snapshot_ref='snap-other-a-1'))
        save_event(manager, other_workspace_id, 'e-1', status='candidate', revision=1, member_refs=(('a-1', 'a-1-r1'),), updated_at=UPDATED_AT['other-e-1'])
        save_event(manager, other_workspace_id, 'w2-1', status='confirmed', revision=2, member_refs=(('a-2', 'a-2-r1'),), updated_at=UPDATED_AT['w2-1'])

        yield Env(manager, workspace_id, other_workspace_id, EventModuleService(manager.borrow_connection))


SPEC = {
    'e-1': ('Alpha', 'candidate', 'src-a', 'snap-a-1', 1),
    'e-2': ('Beta v1', 'confirmed', 'src-old', 'snap-b-1', 2),
    'e-3': (None, 'candidate', None, None, 1),
    'e-4': (None, 'confirmed', None, None, 1),
    'e-5': ('Beta v2', 'candidate', 'src-b', 'snap-b-2', 3),
    'e-6': (None, 'candidate', None, None, 1),
}
OTHER_SPEC = {
    'e-1': ('Other Alpha', 'candidate', 'src-other', 'snap-other-a-1', 1),
    'w2-1': (None, 'confirmed', None, None, 2),
}


def make_row(event_id: str, spec: tuple[Any, ...], updated_at: str) -> dict[str, Any]:
    title, status, source_id, fetch_evidence_ref, revision = spec
    return {
        'event_id': event_id,
        'title': title,
        'status': status,
        'source_id': source_id,
        'fetch_evidence_ref': fetch_evidence_ref,
        'revision': revision,
        'updated_at': updated_at,
    }


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['updated_at'], allowed_filters={'status'}, default_limit=20, max_limit=100)


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
    return [item['event_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [event_id for page in pages for event_id in ids(page)]


def test_rows_have_exact_keys_and_use_first_member_article(env):
    page = get_page(env, {})
    assert ids(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    rows = {item['event_id']: item for item in page.items}
    assert rows == {k: make_row(k, SPEC[k], UPDATED_AT[k]) for k in SPEC}
    assert rows['e-2']['title'] == 'Beta v1' and rows['e-2']['title'] != 'Gamma'
    assert rows['e-5']['title'] == 'Beta v2'


def test_events_without_resolvable_article_have_null_columns(env):
    page = get_page(env, {})
    rows = {item['event_id']: item for item in page.items}
    for event_id in ('e-3', 'e-4', 'e-6'):
        row = rows[event_id]
        assert row['title'] is None
        assert row['source_id'] is None
        assert row['fetch_evidence_ref'] is None
        assert row['status'] == SPEC[event_id][1]
        assert row['revision'] == SPEC[event_id][4]
        assert row['updated_at'] == UPDATED_AT[event_id]
    other_page = get_page(env, {}, env.other_workspace_id)
    other_rows = {item['event_id']: item for item in other_page.items}
    assert other_rows['w2-1']['title'] is None
    assert other_rows['w2-1']['source_id'] is None
    assert other_rows['w2-1']['fetch_evidence_ref'] is None


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


@pytest.mark.parametrize(
    'status, expected',
    [
        ('candidate', ['e-6', 'e-5', 'e-3', 'e-1']),
        ('confirmed', ['e-4', 'e-2']),
        ('CANDIDATE', []),
        ('unknown', []),
        ('', []),
    ],
)
def test_status_filter_is_exact_and_unknown_value_is_empty(env, status, expected):
    page = get_page(env, {'status': status})
    assert ids(page) == expected
    assert page.next_cursor is None


def test_status_filter_paginates(env):
    pages = walk(env, {'status': 'candidate', 'direction': 'asc'}, 2)
    assert len(pages) == 2
    assert all_ids(pages) == ['e-1', 'e-3', 'e-5', 'e-6']


def test_unsupported_filter_name_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=(('source_id', 'x'),))
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_fetch_one_returns_row_or_none(env):
    assert get_one(env, 'e-2') == make_row('e-2', SPEC['e-2'], UPDATED_AT['e-2'])
    assert get_one(env, 'e-3') == make_row('e-3', SPEC['e-3'], UPDATED_AT['e-3'])
    assert get_one(env, 'nope') is None
    assert get_one(env, 'w2-1') is None


def test_workspaces_are_isolated(env):
    mine = get_page(env, {})
    theirs = get_page(env, {}, env.other_workspace_id)
    assert ids(mine) == DESC
    assert ids(theirs) == ['w2-1', 'e-1']
    assert theirs.items[0] == make_row('w2-1', OTHER_SPEC['w2-1'], UPDATED_AT['w2-1'])
    assert theirs.items[1] == make_row('e-1', OTHER_SPEC['e-1'], UPDATED_AT['other-e-1'])
    assert get_one(env, 'e-1')['title'] == 'Alpha'
    assert get_one(env, 'e-1', env.other_workspace_id)['title'] == 'Other Alpha'
    assert get_one(env, 'e-2', env.other_workspace_id) is None
    assert ids(get_page(env, {'status': 'confirmed'}, env.other_workspace_id)) == ['w2-1']
    assert ids(get_page(env, {'status': 'candidate'}, env.other_workspace_id)) == ['e-1']
    assert all_ids(walk(env, {}, 1, env.other_workspace_id)) == ['w2-1', 'e-1']
    assert not any(item['title'] and item['title'].startswith('Other ') for item in mine.items)


def count_rows(env: Env) -> tuple[int, int]:
    with env.manager.borrow_connection() as connection:
        events = connection.execute('SELECT count(*) FROM controlplane.cp_events').fetchone()[0]
        revisions = connection.execute('SELECT count(*) FROM controlplane.cp_article_revisions').fetchone()[0]
    return (events, revisions)


def snapshot_events(env: Env) -> list[tuple[Any, ...]]:
    with env.manager.borrow_connection() as connection:
        return connection.execute('SELECT event_id, revision, updated_at FROM controlplane.cp_events ORDER BY workspace_id, event_id').fetchall()


def test_service_does_not_change_source_tables(env):
    before = count_rows(env)
    assert before == (8, 5)
    snapshot = snapshot_events(env)
    get_page(env, {})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'e-2')
    get_one(env, 'nope')
    assert count_rows(env) == before
    assert snapshot_events(env) == snapshot


class CountingConnection:
    def __init__(self, inner: Any, statements: list[str]) -> None:
        self._inner = inner
        self._statements = statements

    def execute(self, query: Any, params: Any = None) -> Any:
        self._statements.append(str(query))
        return self._inner.execute(query, params)


def test_one_query_per_call_whatever_the_event_count(env):
    statements: list[str] = []

    @contextmanager
    def scope():
        with env.manager.borrow_connection() as connection:
            yield CountingConnection(connection, statements)

    service = EventModuleService(scope)
    for workspace_id, expected in ((env.workspace_id, 6), (env.other_workspace_id, 2)):
        statements.clear()
        page = service.fetch_page(rs_support.FakeRequest(workspace_id, {}), workspace_id, make_query({}))
        assert len(page.items) == expected
        assert len(statements) == 1
        sql_text = ' '.join(statements[0].lower().split())
        assert 'cp_events' in sql_text and 'cp_article_revisions' in sql_text and 'left join' in sql_text
    statements.clear()
    assert service.fetch_one(rs_support.FakeRequest(env.workspace_id), env.workspace_id, 'e-2') is not None
    assert len(statements) == 1


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'e-1'), ('', 'e-1'), ('2026-13-45T01:02:03Z', 'e-1'), ('2026-10-25', 'e-1')])
def test_invalid_cursor_time_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='updated_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows = [*get_page(env, {}).items, *get_page(env, {}, env.other_workspace_id).items, get_one(env, 'e-2'), get_one(env, 'e-3')]
    text = json.dumps(rows)
    assert not [canary for canary in CANARIES if canary in text]
    assert all(not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'LEFT JOIN' in text
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
