"""RS-1: pure tests for read_screens.common and PostgreSQL tests for rs_support.temp_database."""
from __future__ import annotations

import ast
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ContextManager

import pytest

from controlplane.application.projections.list_query import ListQuery, Page, encode_cursor
from controlplane.infrastructure.read_screens import common

import rs_support

ROOT = Path(__file__).resolve().parents[3]
UTC = timezone.utc
CURSOR_TEXT = '2026-10-25T01:02:03.000004Z'
CURSOR_TIME = datetime(2026, 10, 25, 1, 2, 3, 4, tzinfo=UTC)


def make_query(direction='asc', cursor=None, limit=2):
    return ListQuery(limit=limit, cursor=cursor, sort_key='updated_at', direction=direction, filters=())


def test_connection_scope_alias():
    assert common.ConnectionScope == Callable[[], ContextManager[Any]]


def test_utc_text_converts_offset_to_utc_with_microseconds():
    plus7 = timezone(timedelta(hours=7))
    assert common.utc_text(datetime(2026, 10, 25, 8, 30, 15, 123456, tzinfo=plus7)) == '2026-10-25T01:30:15.123456Z'


def test_utc_text_pads_zero_microseconds():
    assert common.utc_text(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == '2026-01-02T03:04:05.000000Z'


@pytest.mark.parametrize('text, expected', [
    (CURSOR_TEXT, CURSOR_TIME),
    ('2026-10-25T08:02:03.000004+07:00', CURSOR_TIME),
    ('2026-10-25T01:02:03Z', datetime(2026, 10, 25, 1, 2, 3, tzinfo=UTC)),
    ('2026-10-25T01:02:03.5Z', datetime(2026, 10, 25, 1, 2, 3, 500000, tzinfo=UTC)),
    ('2026-10-25t01:02:03z', datetime(2026, 10, 25, 1, 2, 3, tzinfo=UTC)),
])
def test_parse_cursor_time_accepts_rfc3339(text, expected):
    parsed = common.parse_cursor_time(text)
    assert parsed == expected
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize('text', ['', 'garbage', '2026-10-25', '2026-10-25T01:02:03', '2026-13-45T01:02:03Z', ' 2026-10-25T01:02:03Z', '2026-10-25T01:02:03Z\n', '0001-01-01T00:00:00+07:00', None])
def test_parse_cursor_time_rejects_non_timestamps(text):
    with pytest.raises(ValueError):
        common.parse_cursor_time(text)


def test_effective_direction_defaults_to_desc_without_direction_param():
    request = rs_support.FakeRequest('w', {})
    assert common.effective_direction(request, make_query('asc')) == 'desc'


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_effective_direction_keeps_query_direction_when_param_present(direction):
    request = rs_support.FakeRequest('w', {'direction': direction})
    assert common.effective_direction(request, make_query(direction)) == direction


def test_keyset_asc_without_cursor():
    where, params, order = common.keyset(make_query('asc'), sort_sql='updated_at', id_sql='hook_id')
    assert (where, params) == ('TRUE', [])
    assert order == 'ORDER BY updated_at ASC, (hook_id)::text ASC'


def test_keyset_desc_without_cursor():
    where, params, order = common.keyset(make_query('desc'), sort_sql='updated_at', id_sql='hook_id')
    assert (where, params) == ('TRUE', [])
    assert order == 'ORDER BY updated_at DESC, (hook_id)::text DESC'


def test_keyset_asc_with_cursor_compares_greater():
    where, params, order = common.keyset(make_query('asc', cursor=(CURSOR_TEXT, 'abc')), sort_sql='updated_at', id_sql='hook_id')
    assert where == '(updated_at, (hook_id)::text) > (%s::timestamptz, %s)'
    assert params == [CURSOR_TIME, 'abc']
    assert order == 'ORDER BY updated_at ASC, (hook_id)::text ASC'


def test_keyset_desc_with_cursor_compares_less():
    where, params, order = common.keyset(make_query('desc', cursor=(CURSOR_TEXT, 'abc')), sort_sql='updated_at', id_sql='hook_id')
    assert where == '(updated_at, (hook_id)::text) < (%s::timestamptz, %s)'
    assert params == [CURSOR_TIME, 'abc']
    assert order == 'ORDER BY updated_at DESC, (hook_id)::text DESC'


def test_keyset_placeholders_match_params():
    for direction in ('asc', 'desc'):
        for cursor in (None, (CURSOR_TEXT, 'abc')):
            where, params, _ = common.keyset(make_query(direction, cursor=cursor), sort_sql='updated_at', id_sql='hook_id')
            assert where.count('%s') == len(params)


@pytest.mark.parametrize('cursor', [('not-a-time', 'abc'), ('', 'abc'), ('2026-10-25', 'abc')])
def test_keyset_rejects_cursor_that_is_not_a_timestamp(cursor):
    with pytest.raises(ValueError):
        common.keyset(make_query('desc', cursor=cursor), sort_sql='updated_at', id_sql='hook_id')


def test_keyset_rejects_unknown_direction():
    with pytest.raises(ValueError):
        common.keyset(make_query('sideways'), sort_sql='updated_at', id_sql='hook_id')


ROWS = [{'updated_at': f'2026-10-25T01:02:0{n}.000000Z', 'item_id': f'id-{n}'} for n in range(3)]


def test_page_of_returns_next_cursor_when_more_rows():
    page = common.page_of(ROWS, make_query(limit=2), 'updated_at', 'item_id')
    assert isinstance(page, Page)
    assert page.items == tuple(ROWS[:2])
    assert page.next_cursor == encode_cursor(ROWS[1]['updated_at'], ROWS[1]['item_id'])


def test_page_of_has_no_cursor_on_last_page():
    page = common.page_of(ROWS[:2], make_query(limit=2), 'updated_at', 'item_id')
    assert page.items == tuple(ROWS[:2])
    assert page.next_cursor is None


def test_pick_reads_nested_keys():
    payload = {'trace': {'model': 'm1'}, 'zero': 0}
    assert common.pick(payload, 'trace', 'model') == 'm1'
    assert common.pick(payload, 'zero') == 0
    assert common.pick(payload, 'trace') == {'model': 'm1'}


def test_pick_returns_none_when_missing():
    payload = {'trace': {'model': 'm1'}, 'text': 'x', 'nothing': None}
    assert common.pick(payload, 'absent') is None
    assert common.pick(payload, 'trace', 'absent') is None
    assert common.pick(payload, 'text', 'deeper') is None
    assert common.pick(payload, 'nothing', 'deeper') is None
    assert common.pick(None, 'a') is None


READ_SCREENS_SRC = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens'
READ_SCREENS_TESTS = ROOT / 'tests' / 'integration' / 'read_screens'
ENV_ACCESS = 'os.' + 'environ'


def test_package_init_has_only_a_docstring():
    tree = ast.parse((READ_SCREENS_SRC / '__init__.py').read_text(encoding='utf-8'))
    assert len(tree.body) == 1
    assert isinstance(tree.body[0], ast.Expr)
    assert ast.get_docstring(tree)


def test_tests_dir_has_no_init_or_conftest():
    assert not (READ_SCREENS_TESTS / '__init__.py').exists()
    assert not (READ_SCREENS_TESTS / 'conftest.py').exists()


def test_environment_access_only_in_rs_support():
    assert ENV_ACCESS in (READ_SCREENS_TESTS / 'rs_support.py').read_text(encoding='utf-8')
    assert ENV_ACCESS not in (READ_SCREENS_SRC / 'common.py').read_text(encoding='utf-8')


def test_fake_request_exposes_identity_and_query_params():
    request = rs_support.FakeRequest('ws-1', {'direction': 'asc'})
    assert request.state.identity['workspace_id'] == 'ws-1'
    assert request.query_params == {'direction': 'asc'}
    assert 'direction' in request.query_params
    assert 'direction' not in rs_support.FakeRequest('ws-1', {}).query_params


def database_name(manager) -> str:
    return manager.dsn.rsplit('/', 1)[1]


def test_temp_database_migrates_and_seeds_two_workspaces():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        assert workspace_id != other_workspace_id
        with manager.borrow_connection() as connection:
            rows = connection.execute('SELECT workspace_id::text FROM controlplane.cp_workspaces').fetchall()
            ingestion_table = connection.execute("SELECT to_regclass('controlplane.cp_articles')::text").fetchone()[0]
        assert ingestion_table is not None
        assert sorted(row[0] for row in rows) == sorted([workspace_id, other_workspace_id])


def test_temp_database_is_dropped_on_exit():
    with rs_support.temp_database() as (manager, _workspace_id, _other_workspace_id):
        name = database_name(manager)
        assert rs_support.database_exists(name)
    assert not rs_support.database_exists(name)


def test_temp_database_is_dropped_when_body_raises():
    names = []
    with pytest.raises(RuntimeError, match='rs-1-boom'):
        with rs_support.temp_database() as (manager, _workspace_id, _other_workspace_id):
            names.append(database_name(manager))
            raise RuntimeError('rs-1-boom')
    assert len(names) == 1
    assert not rs_support.database_exists(names[0])


def test_missing_dsn_fails_instead_of_skipping(monkeypatch):
    monkeypatch.delenv('M2_TEST_PG_DSN', raising=False)
    with pytest.raises(pytest.fail.Exception, match='BLOCKED_EXTERNAL'):
        with rs_support.temp_database():
            pass
