"""RS-10: PostgreSQL tests for the read-only accounts service (module J).

src/ has no writer for cp_external_accounts yet (BL-RS-04), so this test seeds the table with minimal INSERT SQL. Only this test inserts; the service never does.
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
from controlplane.infrastructure.read_screens.accounts import AccountModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'accounts.py'
ROW_KEYS = {'account_ref', 'provider', 'account_label', 'status', 'updated_at'}
FORBIDDEN_KEYS = {'external_account_id', 'workspace_id', 'capabilities_json', 'credential_version', 'credential_updated_at', 'credential_expires_at', 'quota_observation_ref', 'project_ref', 'health', 'revision', 'created_at'}
FORBIDDEN_FRAGMENTS = ('capabilities_json', 'credential_', 'project_ref', 'quota_observation_ref', 'health', 'insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ')
PROJECT_CANARY = 'CANARY-PROJECT'
CAPABILITY_CANARY = 'CANARY-CAPABILITY'
HEALTH_CANARY = 'CANARY-HEALTH'
QUOTA_CANARY = 'CANARY-QUOTA'
CANARIES = (PROJECT_CANARY, CAPABILITY_CANARY, HEALTH_CANARY, QUOTA_CANARY)

# (account_ref, provider, account_label, status, updated_at). Creation order differs from id order on purpose; acc-b and acc-d share updated_at, so they are ordered by id.
W1_ACCOUNTS = [
    ('acc-c', 'drive', 'Drive chính', 'ENABLED', '2026-10-01T08:00:00.123456+00:00'),
    ('acc-a', 'drive', 'Drive phụ', 'DEGRADED', '2026-10-02T08:00:00+00:00'),
    ('acc-b', 'router', 'Router chính', 'ENABLED', '2026-10-03T08:00:00+00:00'),
    ('acc-d', 'router', 'Router phụ', 'DISABLED', '2026-10-03T08:00:00+00:00'),
    ('acc-e', 'drive', 'Drive cũ', 'REVOKED', '2026-09-30T08:00:00+00:00'),
    ('acc-f', 'router', 'Router lỗi', 'INVALID', '2026-09-29T08:00:00+00:00'),
]
# The other workspace reuses the id acc-a of W1 on purpose.
OTHER_ACCOUNTS = [
    ('acc-a', 'drive', 'Drive khác', 'ENABLED', '2026-10-05T08:00:00+00:00'),
    ('acc-z', 'router', 'Router khác', 'INVALID', '2026-10-04T08:00:00+00:00'),
]
EXPECTED = {ref: (provider, label, status, updated_at) for ref, provider, label, status, updated_at in W1_ACCOUNTS}
OTHER_EXPECTED = {ref: (provider, label, status, updated_at) for ref, provider, label, status, updated_at in OTHER_ACCOUNTS}
ASC = ['acc-f', 'acc-e', 'acc-c', 'acc-a', 'acc-b', 'acc-d']
DESC = list(reversed(ASC))


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: AccountModuleService
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


def seed(manager: Any, workspace_id: str, accounts: list[Any]) -> None:
    with manager.borrow_connection() as connection:
        for ref, provider, label, status, updated_at in accounts:
            connection.execute(
                'INSERT INTO controlplane.cp_external_accounts (workspace_id, external_account_id, provider, account_label, status, project_ref, capabilities_json, credential_version, credential_updated_at, credential_expires_at, quota_observation_ref, health, updated_at) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::timestamptz, %s::timestamptz, %s, %s, %s::timestamptz)',
                (
                    workspace_id,
                    ref,
                    provider,
                    label,
                    status,
                    f'{PROJECT_CANARY}-{ref}',
                    json.dumps([f'{CAPABILITY_CANARY}-{ref}']),
                    7,
                    '2026-10-20T00:00:00+00:00',
                    '2027-10-20T00:00:00+00:00',
                    f'{QUOTA_CANARY}-{ref}',
                    f'{HEALTH_CANARY}-{ref}',
                    updated_at,
                ),
            )


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        seed(manager, workspace_id, W1_ACCOUNTS)
        seed(manager, other_workspace_id, OTHER_ACCOUNTS)
        statements: list[str] = []
        yield Env(manager, workspace_id, other_workspace_id, AccountModuleService(lambda: recording_scope(manager, statements)), statements)


def make_row(ref: str, other: bool = False) -> dict[str, Any]:
    provider, label, status, updated_at = (OTHER_EXPECTED if other else EXPECTED)[ref]
    return {
        'account_ref': ref,
        'provider': provider,
        'account_label': label,
        'status': status,
        'updated_at': utc_of(updated_at),
    }


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['updated_at'], allowed_filters={'provider', 'status'}, default_limit=20, max_limit=100)


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
    return [item['account_ref'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [ref for page in pages for ref in ids_of(page)]

def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids_of(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['account_ref']: item for item in page.items} == {ref: make_row(ref) for ref in ASC}


def test_updated_at_is_utc_text_with_microseconds(env):
    rows = {item['account_ref']: item for item in get_page(env, {}).items}
    assert rows['acc-c']['updated_at'] == '2026-10-01T08:00:00.123456Z'
    assert rows['acc-b']['updated_at'] == '2026-10-03T08:00:00.000000Z'
    assert {row['status'] for row in rows.values()} == {'ENABLED', 'DISABLED', 'DEGRADED', 'INVALID', 'REVOKED'}
    assert {row['provider'] for row in rows.values()} == {'drive', 'router'}
    assert rows['acc-c']['account_label'] == 'Drive chính'


def test_order_follows_updated_at_then_id(env):
    ascending = ids_of(get_page(env, {'direction': 'asc'}))
    assert ascending == ASC
    assert ascending != sorted(ASC)
    assert ids_of(get_page(env, {})) == DESC
    assert ids_of(get_page(env, {'sort': 'updated_at'})) == DESC
    assert ids_of(get_page(env, {'direction': 'desc'})) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 4])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, limit):
    pages = walk(env, {'direction': direction}, limit)
    expected = ASC if direction == 'asc' else DESC
    assert all_ids(pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 4)
    assert len(pages) == 2
    assert all_ids(pages) == DESC


@pytest.mark.parametrize(
    'provider, expected',
    [
        ('drive', ['acc-a', 'acc-c', 'acc-e']),
        ('router', ['acc-d', 'acc-b', 'acc-f']),
        ('unknown', []),
        ('DRIVE', []),
        ('drive ', []),
        ('', []),
    ],
)
def test_provider_filter_exact_match_and_unknown_value_is_empty(env, provider, expected):
    page = get_page(env, {'provider': provider})
    assert ids_of(page) == expected
    assert page.next_cursor is None


@pytest.mark.parametrize(
    'status, expected',
    [
        ('ENABLED', ['acc-b', 'acc-c']),
        ('DEGRADED', ['acc-a']),
        ('DISABLED', ['acc-d']),
        ('INVALID', ['acc-f']),
        ('REVOKED', ['acc-e']),
        ('PENDING', []),
        ('enabled', []),
        ('ENABLED ', []),
        ('', []),
    ],
)
def test_status_filter_exact_match_and_unknown_value_is_empty(env, status, expected):
    page = get_page(env, {'status': status})
    assert ids_of(page) == expected
    assert page.next_cursor is None


def test_combined_filters_and_pagination_both_ways(env):
    assert ids_of(get_page(env, {'provider': 'router', 'status': 'ENABLED'})) == ['acc-b']
    assert ids_of(get_page(env, {'provider': 'drive', 'status': 'ENABLED'})) == ['acc-c']
    assert ids_of(get_page(env, {'provider': 'drive', 'status': 'INVALID'})) == []
    pages_asc = walk(env, {'provider': 'drive', 'direction': 'asc'}, 1)
    assert len(pages_asc) == 3
    assert all_ids(pages_asc) == ['acc-e', 'acc-c', 'acc-a']
    pages_desc = walk(env, {'provider': 'drive'}, 1)
    assert len(pages_desc) == 3
    assert all_ids(pages_desc) == ['acc-a', 'acc-c', 'acc-e']


def test_fetch_one_returns_row_or_none(env):
    for ref in ASC:
        assert get_one(env, ref) == make_row(ref)
    for missing in ('acc-', 'ACC-A', 'acc-a ', 'nope', '', 'acc-z'):
        assert get_one(env, missing) is None
    assert get_one(env, 'acc-c', env.other_workspace_id) is None
    assert get_one(env, 'acc-z', env.other_workspace_id) == make_row('acc-z', other=True)
    assert get_one(env, 'acc-a', env.other_workspace_id) == make_row('acc-a', other=True)


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    theirs = get_page(env, {}, other)
    assert ids_of(theirs) == ['acc-a', 'acc-z']
    assert list(theirs.items) == [make_row('acc-a', other=True), make_row('acc-z', other=True)]
    assert all_ids(walk(env, {'direction': 'asc'}, 1, other)) == ['acc-z', 'acc-a']
    mine = get_page(env, {})
    assert ids_of(mine) == DESC
    assert ids_of(get_page(env, {'status': 'ENABLED'})) == ['acc-b', 'acc-c']
    assert ids_of(get_page(env, {'status': 'ENABLED'}, other)) == ['acc-a']
    assert ids_of(get_page(env, {'status': 'INVALID'})) == ['acc-f']
    assert ids_of(get_page(env, {'status': 'INVALID'}, other)) == ['acc-z']
    assert ids_of(get_page(env, {'status': 'DISABLED'}, other)) == []
    assert ids_of(get_page(env, {'provider': 'drive'}, other)) == ['acc-a']
    assert get_one(env, 'acc-a')['status'] == 'DEGRADED'
    assert get_one(env, 'acc-a', other)['status'] == 'ENABLED'
    assert not any(item['account_label'] in ('Drive khác', 'Router khác') for item in mine.items)


def test_unsupported_filter_and_sort_raise_value_error(env):
    for name in ('job_id', 'account_ref', 'external_account_id', 'project_ref', 'health', 'workspace_id'):
        query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=((name, 'x'),))
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    for sort_key in ('external_account_id', 'created_at', 'provider'):
        query = ListQuery(limit=5, cursor=None, sort_key=sort_key, direction='desc', filters=())
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    with pytest.raises(ListQueryError):
        make_query({'job_id': 'x'})


def table_state(env: Env) -> list[Any]:
    with env.manager.borrow_connection() as connection:
        return connection.execute(
            'SELECT workspace_id::text, external_account_id, provider, account_label, status, project_ref, capabilities_json::text, credential_version, credential_updated_at, credential_expires_at, quota_observation_ref, health, revision, created_at, updated_at '
            'FROM controlplane.cp_external_accounts '
            'ORDER BY workspace_id, external_account_id'
        ).fetchall()


def test_reads_do_not_change_the_table(env):
    before = table_state(env)
    assert len(before) == 8
    get_page(env, {})
    get_page(env, {'status': 'ENABLED'})
    get_page(env, {'provider': 'drive'})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'acc-a')
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('acc-a', 'acc-a')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='updated_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, ref, workspace_id) for ref in (*ASC, 'acc-z'))
    rows = [row for row in rows if row is not None]
    text = json.dumps(rows)
    assert rows
    assert not [c for c in CANARIES if c in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_reads_only_the_accounts_table_with_workspace_scope(env):
    env.statements.clear()
    get_page(env, {})
    get_page(env, {'status': 'ENABLED', 'direction': 'asc'})
    get_page(env, {'provider': 'drive'})
    walk(env, {}, 1)
    get_one(env, 'acc-a')
    get_one(env, 'nope')
    assert len(env.statements) >= 8
    for statement in env.statements:
        lowered = statement.lower()
        assert lowered.startswith('select ')
        assert 'controlplane.cp_external_accounts' in lowered
        assert 'workspace_id = %s::uuid' in lowered
        assert not any(frag in lowered for frag in ('capabilities_json', 'credential_', 'project_ref', 'quota_observation_ref', 'health', 'revision', 'created_at'))


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [f for f in FORBIDDEN_FRAGMENTS if f in lowered]
    assert 'cp_external_accounts' in lowered and 'external_account_id' in lowered and 'updated_at' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not any(m and (m.startswith('controlplane.api') or m.startswith('src')) for m in modules)
