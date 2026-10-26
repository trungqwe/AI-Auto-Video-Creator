"""RS-9: PostgreSQL tests for the read-only sessions service (module G).

src/ has no writer for cp_app_sessions yet (BL-RS-04), so this test seeds the table with minimal INSERT SQL. Only this test inserts; the service never does.
"""
from __future__ import annotations

import ast
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, ListQueryError, Page, parse_list_query
from controlplane.infrastructure.read_screens.sessions import SessionModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'sessions.py'
ROW_KEYS = {'session_id', 'status', 'started_at', 'finished_at'}
FORBIDDEN_KEYS = {'recovery_epoch', 'session_ref', 'workspace_id', 'ended_at', 'created_at', 'updated_at', 'job_id', 'token_hash', 'actor_id'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'cp_auth_sessions', 'token_hash', 'recovery_epoch')
EPOCH_CANARY = 'CANARY-EPOCH'
AUTH_ACTOR_ID = '00000000-0000-0000-0000-00000000a0c1'
AUTH_SESSION_ID = '00000000-0000-0000-0000-00000000c0de'
AUTH_TOKEN_HASH = bytes([0xAB]) * 32
AUTH_CANARIES = ('CANARY-AUTH-ACTOR', AUTH_ACTOR_ID, AUTH_SESSION_ID, AUTH_TOKEN_HASH.hex())
# (session_ref, status, started_at, ended_at). Creation order differs from id order on purpose; ses-b and ses-d share started_at, so they are ordered by id. Three statuses are covered.
W1_SESSIONS = [
    ('ses-c', 'ENDED', '2026-10-01T08:00:00.123456+00:00', '2026-10-01T09:30:00.500000+00:00'),
    ('ses-a', 'ACTIVE', '2026-10-02T08:00:00+00:00', None),
    ('ses-b', 'ABANDONED', '2026-10-03T08:00:00+00:00', '2026-10-03T08:10:00+00:00'),
    ('ses-d', 'ACTIVE', '2026-10-03T08:00:00+00:00', None),
]
# The other workspace reuses the id ses-a of W1 on purpose, with a different status.
OTHER_SESSIONS = [
    ('ses-a', 'ENDED', '2026-10-05T08:00:00+00:00', '2026-10-05T08:30:00+00:00'),
    ('ses-z', 'ABANDONED', '2026-10-04T08:00:00+00:00', '2026-10-04T08:05:00+00:00'),
]
EXPECTED = {ref: (status, started, ended) for ref, status, started, ended in W1_SESSIONS}
OTHER_EXPECTED = {ref: (status, started, ended) for ref, status, started, ended in OTHER_SESSIONS}
ASC = ['ses-c', 'ses-a', 'ses-b', 'ses-d']
DESC = list(reversed(ASC))

@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: SessionModuleService
    statements: list[str]


class RecordingConnection:
    def __init__(self, inner: Any, statements: list[str]) -> None:
        self._inner = inner
        self._statements = statements

    def execute(self, statement: Any, params: Any = None) -> Any:
        self._statements.append(str(statement))
        return self._inner.execute(statement, params)


@contextmanager
def recording_scope(manager: Any, statements: list[str]):
    with manager.borrow_connection() as connection:
        yield RecordingConnection(connection, statements)


def utc_of(text: str) -> str:
    return datetime.fromisoformat(text).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def seed(manager: Any, workspace_id: str, sessions: list[Any]) -> None:
    with manager.borrow_connection() as connection:
        for ref, status, started_at, ended_at in sessions:
            connection.execute(
                'INSERT INTO controlplane.cp_app_sessions (workspace_id, session_ref, status, recovery_epoch, started_at, ended_at) VALUES (%s::uuid, %s, %s, %s, %s::timestamptz, %s::timestamptz)',
                (workspace_id, ref, status, f'{EPOCH_CANARY}-{ref}', started_at, ended_at),
            )


def seed_auth_session(manager: Any, workspace_id: str) -> None:
    # Canary rows in the authentication tables: the service must never read them.
    with manager.borrow_connection() as connection:
        connection.execute("INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s::uuid, %s::uuid, 'human', 'CANARY-AUTH-ACTOR', 'ACTIVE')", (AUTH_ACTOR_ID, workspace_id))
        connection.execute("INSERT INTO controlplane.cp_auth_sessions (session_id, workspace_id, actor_id, status, token_hash) VALUES (%s::uuid, %s::uuid, %s::uuid, 'ACTIVE', %s)", (AUTH_SESSION_ID, workspace_id, AUTH_ACTOR_ID, AUTH_TOKEN_HASH))


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        seed(manager, workspace_id, W1_SESSIONS)
        seed(manager, other_workspace_id, OTHER_SESSIONS)
        seed_auth_session(manager, workspace_id)
        statements: list[str] = []
        yield Env(manager, workspace_id, other_workspace_id, SessionModuleService(lambda: recording_scope(manager, statements)), statements)

def make_row(ref: str, other: bool = False) -> dict[str, Any]:
    status, started, ended = (OTHER_EXPECTED if other else EXPECTED)[ref]
    return {'session_id': ref, 'status': status, 'started_at': utc_of(started), 'finished_at': None if ended is None else utc_of(ended)}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['started_at'], allowed_filters={'status'}, default_limit=20, max_limit=100)


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


def ids_of(page: Page) -> list[str]:
    return [item['session_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [session_id for page in pages for session_id in ids_of(page)]

def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids_of(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['session_id']: item for item in page.items} == {ref: make_row(ref) for ref in ASC}


def test_finished_at_is_null_while_running_and_text_when_ended(env):
    rows = {item['session_id']: item for item in get_page(env, {}).items}
    assert rows['ses-a']['finished_at'] is None and rows['ses-d']['finished_at'] is None
    assert rows['ses-a']['status'] == 'ACTIVE'
    assert rows['ses-c']['finished_at'] == '2026-10-01T09:30:00.500000Z'
    assert rows['ses-b']['finished_at'] == '2026-10-03T08:10:00.000000Z'
    assert rows['ses-c']['started_at'] == '2026-10-01T08:00:00.123456Z'
    assert {row['status'] for row in rows.values()} == {'ACTIVE', 'ENDED', 'ABANDONED'}
    assert all(row['finished_at'] != '' for row in rows.values())
    assert get_one(env, 'ses-a')['finished_at'] is None


def test_order_follows_started_at_then_id(env):
    ascending = ids_of(get_page(env, {'direction': 'asc'}))
    assert ascending == ASC
    assert ascending != sorted(ASC)
    assert ids_of(get_page(env, {})) == DESC
    assert ids_of(get_page(env, {'sort': 'started_at'})) == DESC
    assert ids_of(get_page(env, {'direction': 'desc'})) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, limit):
    pages = walk(env, {'direction': direction}, limit)
    expected = ASC if direction == 'asc' else DESC
    assert all_ids(pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 2)
    assert len(pages) == 2
    assert all_ids(pages) == DESC


@pytest.mark.parametrize('status, expected', [('ACTIVE', ['ses-d', 'ses-a']), ('ENDED', ['ses-c']), ('ABANDONED', ['ses-b']), ('RUNNING', []), ('FINISHED', []), ('active', []), ('ACTIVE ', []), ('', [])])
def test_status_filter_exact_match_and_unknown_value_is_empty(env, status, expected):
    page = get_page(env, {'status': status})
    assert ids_of(page) == expected
    assert page.next_cursor is None


def test_status_filter_paginates_both_ways(env):
    pages = walk(env, {'status': 'ACTIVE', 'direction': 'asc'}, 1)
    assert len(pages) == 2
    assert all_ids(pages) == ['ses-a', 'ses-d']
    pages = walk(env, {'status': 'ACTIVE'}, 1)
    assert len(pages) == 2
    assert all_ids(pages) == ['ses-d', 'ses-a']

def test_fetch_one_returns_row_or_none(env):
    for ref in ASC:
        assert get_one(env, ref) == make_row(ref)
    for missing in ('ses-', 'SES-A', 'ses-a ', 'nope', '', 'ses-z'):
        assert get_one(env, missing) is None
    assert get_one(env, 'ses-c', env.other_workspace_id) is None
    assert get_one(env, 'ses-z', env.other_workspace_id) == make_row('ses-z', other=True)
    assert get_one(env, 'ses-a', env.other_workspace_id) == make_row('ses-a', other=True)


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    theirs = get_page(env, {}, other)
    assert ids_of(theirs) == ['ses-a', 'ses-z']
    assert list(theirs.items) == [make_row('ses-a', other=True), make_row('ses-z', other=True)]
    assert all_ids(walk(env, {'direction': 'asc'}, 1, other)) == ['ses-z', 'ses-a']
    mine = get_page(env, {})
    assert ids_of(mine) == DESC
    foreign_starts = {utc_of(OTHER_EXPECTED['ses-a'][1]), utc_of(OTHER_EXPECTED['ses-z'][1])}
    assert not [item for item in mine.items if item['started_at'] in foreign_starts]
    assert ids_of(get_page(env, {'status': 'ENDED'})) == ['ses-c']
    assert ids_of(get_page(env, {'status': 'ENDED'}, other)) == ['ses-a']
    assert ids_of(get_page(env, {'status': 'ABANDONED'}, other)) == ['ses-z']
    assert ids_of(get_page(env, {'status': 'ACTIVE'}, other)) == []
    assert get_one(env, 'ses-a')['status'] == 'ACTIVE'
    assert get_one(env, 'ses-a', other)['status'] == 'ENDED'


def test_unsupported_filter_and_sort_raise_value_error(env):
    for name in ('job_id', 'session_id', 'recovery_epoch', 'workspace_id'):
        query = ListQuery(limit=5, cursor=None, sort_key='started_at', direction='desc', filters=((name, 'x'),))
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    for sort_key in ('session_ref', 'ended_at', 'created_at'):
        query = ListQuery(limit=5, cursor=None, sort_key=sort_key, direction='desc', filters=())
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    with pytest.raises(ListQueryError):
        make_query({'job_id': 'x'})


def table_state(env: Env) -> tuple[list[Any], list[Any]]:
    with env.manager.borrow_connection() as connection:
        sessions = connection.execute('SELECT workspace_id::text, session_ref, status, recovery_epoch, started_at, ended_at, created_at, updated_at FROM controlplane.cp_app_sessions ORDER BY workspace_id, session_ref').fetchall()
        auth = connection.execute('SELECT session_id::text, workspace_id::text, actor_id::text, status, token_hash FROM controlplane.cp_auth_sessions').fetchall()
    return sessions, auth


def test_reads_do_not_change_the_tables(env):
    before = table_state(env)
    assert len(before[0]) == 6 and len(before[1]) == 1
    get_page(env, {})
    get_page(env, {'status': 'ENDED'})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'ses-a')
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('ses-a', 'ses-a')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='started_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)

def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, ref, workspace_id) for ref in (*ASC, 'ses-z'))
    rows = [row for row in rows if row is not None]
    text = json.dumps(rows)
    assert rows
    assert EPOCH_CANARY not in text
    assert not [token for token in AUTH_CANARIES if token in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_never_reads_auth_sessions_or_recovery_epoch(env):
    env.statements.clear()
    get_page(env, {})
    get_page(env, {'status': 'ENDED', 'direction': 'asc'})
    walk(env, {}, 1)
    get_one(env, 'ses-a')
    get_one(env, 'nope')
    assert len(env.statements) >= 8
    for statement in env.statements:
        lowered = statement.lower()
        assert lowered.startswith('select ') and 'controlplane.cp_app_sessions' in lowered
        assert 'workspace_id = %s::uuid' in lowered
        assert not [name for name in ('cp_auth_sessions', 'cp_actors', 'token_hash', 'recovery_epoch') if name in lowered]


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'cp_app_sessions' in lowered and 'session_ref' in lowered and 'started_at' in lowered and 'ended_at' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
