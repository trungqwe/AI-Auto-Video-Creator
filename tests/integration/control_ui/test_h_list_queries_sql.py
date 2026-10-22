"""H-04: SQL keyset tham số hóa cho danh sách (connection giả).

coveredIds: CT-API-001, CT-API-002, QR-PERF-005
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from controlplane.api.main import create_app
from controlplane.application.projections.list_query import ListQuery, Page, decode_cursor, encode_cursor
from controlplane.infrastructure.db.control_api_queries import PostgresControlQueries
from controlplane.infrastructure.db.projections.list_queries import (
    BATCHES_SPEC,
    JOBS_SPEC,
    ListSpec,
    build_list_sql,
    fetch_page,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'projections' / 'list_queries.py'
QUERIES_PATH = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'control_api_queries.py'
CONTROL_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'control.py'
WORKSPACE = 'ws-1'
EVIL = "x'; DROP TABLE controlplane.cp_video_jobs; --"
CURSOR = ('2026-01-01T00:00:00+00:00', 'job-09')


def make_query(**overrides):
    values = {'limit': 50, 'cursor': None, 'sort_key': 'created_at', 'direction': 'desc', 'filters': ()}
    values.update(overrides)
    return ListQuery(**values)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return FakeResult(self.rows)


def test_workspace_condition_is_first_where_condition():
    query = make_query(filters=(('status', 'RUNNING'),), cursor=CURSOR)
    sql, params = build_list_sql(JOBS_SPEC, query, workspace_id=WORKSPACE)
    assert ' WHERE workspace_id = %s AND ' in sql
    assert params[0] == WORKSPACE


def test_batches_sql_matches_existing_query_shape():
    sql, params = build_list_sql(BATCHES_SPEC, make_query(), workspace_id=WORKSPACE)
    assert sql == (
        'SELECT batch_id, status, target_count, created_at FROM controlplane.cp_production_batches '
        'WHERE workspace_id = %s ORDER BY created_at DESC, batch_id DESC LIMIT %s'
    )
    assert params == (WORKSPACE, 51)


def test_jobs_sql_with_filters_in_query_order():
    query = make_query(filters=(('batch_id', 'b-1'), ('status', 'RUNNING')))
    sql, params = build_list_sql(JOBS_SPEC, query, workspace_id=WORKSPACE)
    assert 'WHERE workspace_id = %s AND batch_id = %s AND status = %s ORDER BY' in sql
    assert params == (WORKSPACE, 'b-1', 'RUNNING', 51)


def test_malicious_values_only_travel_in_params():
    query = make_query(filters=(('status', EVIL),), cursor=(EVIL, EVIL))
    sql, params = build_list_sql(JOBS_SPEC, query, workspace_id=EVIL)
    assert 'DROP' not in sql and "'" not in sql and '--' not in sql
    assert params == (EVIL, EVIL, EVIL, EVIL, 51)


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [None, CURSOR])
@pytest.mark.parametrize('filters', [(), (('status', 'RUNNING'),)])
def test_placeholders_match_params_and_no_offset(direction, cursor, filters):
    query = make_query(direction=direction, cursor=cursor, filters=filters)
    sql, params = build_list_sql(JOBS_SPEC, query, workspace_id=WORKSPACE)
    assert sql.count('%s') == len(params)
    assert sql.count('%') == sql.count('%s')
    assert 'OFFSET' not in sql.upper()
    assert sql.endswith(' LIMIT %s')


def test_desc_cursor_uses_less_than():
    sql, params = build_list_sql(JOBS_SPEC, make_query(cursor=CURSOR), workspace_id=WORKSPACE)
    assert 'AND (created_at, job_id) < (%s, %s) ORDER BY created_at DESC, job_id DESC LIMIT %s' in sql
    assert '>' not in sql
    assert params == (WORKSPACE, *CURSOR, 51)


def test_asc_cursor_uses_greater_than():
    query = make_query(direction='asc', cursor=CURSOR)
    sql, params = build_list_sql(JOBS_SPEC, query, workspace_id=WORKSPACE)
    assert 'AND (created_at, job_id) > (%s, %s) ORDER BY created_at ASC, job_id ASC LIMIT %s' in sql
    assert '<' not in sql
    assert params == (WORKSPACE, *CURSOR, 51)


def test_no_cursor_has_no_keyset_condition():
    sql, _ = build_list_sql(JOBS_SPEC, make_query(), workspace_id=WORKSPACE)
    assert '(%s, %s)' not in sql
    assert '<' not in sql and '>' not in sql


@pytest.mark.parametrize('limit', [1, 50, 100])
def test_last_param_is_limit_plus_one(limit):
    _, params = build_list_sql(JOBS_SPEC, make_query(limit=limit), workspace_id=WORKSPACE)
    assert params[-1] == limit + 1


@pytest.mark.parametrize('sort_key', ['created_at; DROP', 'status', 'job_id', 'workspace_id', 'CREATED_AT', ''])
def test_sort_key_outside_whitelist_is_rejected(sort_key):
    with pytest.raises(ValueError, match='^column_not_allowed$'):
        build_list_sql(JOBS_SPEC, make_query(sort_key=sort_key), workspace_id=WORKSPACE)


@pytest.mark.parametrize('name', ['workspace_id', 'actor_id', 'snapshot_ref', 'status; DROP', 'STATUS', ''])
def test_filter_outside_whitelist_is_rejected(name):
    with pytest.raises(ValueError, match='^column_not_allowed$'):
        build_list_sql(JOBS_SPEC, make_query(filters=((name, 'x'),)), workspace_id=WORKSPACE)


def test_batches_spec_rejects_job_only_filter():
    with pytest.raises(ValueError, match='^column_not_allowed$'):
        build_list_sql(BATCHES_SPEC, make_query(filters=(('batch_id', 'b-1'),)), workspace_id=WORKSPACE)


@pytest.mark.parametrize('direction', ['DESC', 'asc; DROP', '', None])
def test_direction_outside_asc_desc_is_rejected(direction):
    with pytest.raises(ValueError, match='^direction_invalid$'):
        build_list_sql(JOBS_SPEC, make_query(direction=direction), workspace_id=WORKSPACE)


@pytest.mark.parametrize('limit', [0, -1, True, '5', None])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(ValueError, match='^limit_invalid$'):
        build_list_sql(JOBS_SPEC, make_query(limit=limit), workspace_id=WORKSPACE)


def make_spec(**overrides):
    values = {
        'table': 'controlplane.cp_video_jobs',
        'id_column': 'job_id',
        'sort_columns': ('created_at',),
        'filter_columns': ('status',),
        'select_columns': ('job_id', 'status', 'created_at'),
    }
    values.update(overrides)
    return ListSpec(**values)


def test_list_spec_is_frozen():
    spec = make_spec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.table = 'controlplane.other'


BAD_IDENTIFIERS = ['t; DROP', 'Table', 'job_id1', '', 'a b', 'a\n', "a'", 'a-b', 'a,b']


@pytest.mark.parametrize('bad', BAD_IDENTIFIERS)
@pytest.mark.parametrize('field', ['table', 'id_column', 'sort_columns', 'filter_columns', 'select_columns'])
def test_list_spec_rejects_invalid_identifier(field, bad):
    value = bad if field in ('table', 'id_column') else ('created_at', bad)
    with pytest.raises(ValueError, match='^invalid_identifier$'):
        make_spec(**{field: value})


@pytest.mark.parametrize(
    'overrides',
    [
        {'id_column': 'other_id'},
        {'sort_columns': ('missing',)},
        {'sort_columns': ()},
        {'sort_columns': 'created_at'},
        {'filter_columns': ['status']},
    ],
)
def test_list_spec_rejects_inconsistent_spec(overrides):
    with pytest.raises(ValueError, match='^invalid_spec$'):
        make_spec(**overrides)


def test_shipped_specs_have_expected_shape():
    assert BATCHES_SPEC == ListSpec(
        table='controlplane.cp_production_batches',
        id_column='batch_id',
        sort_columns=('created_at',),
        filter_columns=('status',),
        select_columns=('batch_id', 'status', 'target_count', 'created_at'),
    )
    assert JOBS_SPEC == ListSpec(
        table='controlplane.cp_video_jobs',
        id_column='job_id',
        sort_columns=('created_at',),
        filter_columns=('batch_id', 'status'),
        select_columns=('job_id', 'batch_id', 'status', 'snapshot_ref', 'revision', 'created_at'),
    )


def job_row(index):
    return (f'job-{index:02d}', 'b-1', 'RUNNING', f'snap-{index:02d}', 1, f'2026-01-01T00:00:{index:02d}+00:00')


def test_fetch_page_returns_limit_items_and_next_cursor():
    connection = FakeConnection([job_row(i) for i in range(51)])
    query = make_query()
    page = fetch_page(connection, JOBS_SPEC, query, workspace_id=WORKSPACE)
    assert len(page.items) == 50
    assert page.next_cursor is not None
    assert decode_cursor(page.next_cursor) == ('2026-01-01T00:00:49+00:00', 'job-49')
    assert tuple(page.items[0]) == JOBS_SPEC.select_columns
    assert page.items[0]['job_id'] == 'job-00' and page.items[0]['revision'] == 1
    assert connection.calls == [build_list_sql(JOBS_SPEC, query, workspace_id=WORKSPACE)]
    assert connection.calls[0][1][-1] == 51


def test_fetch_page_without_extra_row_has_no_next_cursor():
    connection = FakeConnection([job_row(i) for i in range(3)])
    page = fetch_page(connection, JOBS_SPEC, make_query(), workspace_id=WORKSPACE)
    assert len(page.items) == 3
    assert page.next_cursor is None


def test_fetch_page_serializes_datetime_for_items_and_cursor():
    created = [datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc) for i in range(3)]
    rows = [(f'b-{i}', 'CREATED', 5, created[i]) for i in range(3)]
    page = fetch_page(FakeConnection(rows), BATCHES_SPEC, make_query(limit=2), workspace_id=WORKSPACE)
    assert [item['created_at'] for item in page.items] == [created[0].isoformat(), created[1].isoformat()]
    assert decode_cursor(page.next_cursor) == (created[1].isoformat(), 'b-1')


def test_fetch_page_rejects_before_touching_connection():
    connection = FakeConnection()
    with pytest.raises(ValueError, match='^column_not_allowed$'):
        fetch_page(connection, JOBS_SPEC, make_query(sort_key='created_at; DROP'), workspace_id=WORKSPACE)
    assert connection.calls == []


def test_module_has_no_database_driver_and_no_offset():
    text = MODULE_PATH.read_text(encoding='utf-8')
    assert 'psycopg' not in text.lower()
    assert 'OFFSET' not in text.upper()
    imported = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    allowed = {'__future__', 're', 'dataclasses', 'typing', 'controlplane.application.projections.list_query'}
    assert imported <= allowed


def _method_def(name):
    tree = ast.parse(QUERIES_PATH.read_text(encoding='utf-8'))
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'PostgresControlQueries')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


@pytest.mark.parametrize('name, spec_name', [('batches', 'BATCHES_SPEC'), ('jobs', 'JOBS_SPEC')])
def test_specs_match_control_api_queries(name, spec_name):
    method = _method_def(name)
    spec_args = [
        arg.id
        for call in ast.walk(method)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'fetch_page'
        for arg in call.args
        if isinstance(arg, ast.Name)
    ]
    assert spec_name in spec_args
    literals = [c.value for c in ast.walk(method) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    assert not any(value.lstrip().startswith('SELECT ') for value in literals)


def test_control_api_queries_imports_fetch_page_and_specs_from_projection_module():
    tree = ast.parse(QUERIES_PATH.read_text(encoding='utf-8'))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == 'controlplane.infrastructure.db.projections.list_queries'
        for alias in node.names
    }
    assert {'fetch_page', 'BATCHES_SPEC', 'JOBS_SPEC'} <= imported


def test_control_api_queries_has_no_limit_100_and_no_offset():
    text = QUERIES_PATH.read_text(encoding='utf-8')
    assert 'LIMIT 100' not in text
    assert re.search(r'\bOFFSET\b', text, re.IGNORECASE) is None


def test_qr_perf_005_page_fetch_is_single_bounded_keyset_query():
    first = FakeConnection([job_row(i) for i in range(11)])
    deep = FakeConnection([job_row(i) for i in range(11)])
    fetch_page(first, JOBS_SPEC, make_query(limit=10), workspace_id=WORKSPACE)
    fetch_page(deep, JOBS_SPEC, make_query(limit=10, cursor=CURSOR), workspace_id=WORKSPACE)
    for connection in (first, deep):
        assert len(connection.calls) == 1
        sql, params = connection.calls[0]
        assert sql.endswith(' LIMIT %s')
        assert params[-1] == 11
        assert 'OFFSET' not in sql.upper()
    assert '(created_at, job_id) < (%s, %s)' in deep.calls[0][0]
    assert '(created_at, job_id)' not in first.calls[0][0]
    assert first.calls[0][0].split(' ORDER BY ')[1] == deep.calls[0][0].split(' ORDER BY ')[1]

def operation_row(index):
    return (f'10000000-0000-0000-0000-{index:012d}', f'cmd-{index:02d}', f'20000000-0000-0000-0000-{index:012d}', 'accepted', None, f'2026-01-01T00:00:{index:02d}+00:00', None, None, None)


def config_row(index):
    return (f'30000000-0000-0000-0000-{index:012d}', 'workspace', 'ws-1', index + 1, 1, 'a' * 64, 'PUBLISHED', f'2026-01-01T00:00:{index:02d}+00:00')


LIST_CASES = {
    'operations': {'sort': 'accepted_at', 'row': operation_row, 'id_field': 'receipt_id', 'id_index': 2, 'keyset': '(r.accepted_at, r.receipt_id)', 'order': 'r.accepted_at {d}, r.receipt_id {d}'},
    'configs': {'sort': 'created_at', 'row': config_row, 'id_field': 'config_revision_id', 'id_index': 0, 'keyset': '(c.created_at, c.config_revision_id)', 'order': 'c.created_at {d}, c.config_revision_id {d}'},
}


def run_list(name, query, rows=()):
    connection = FakeConnection(rows)
    page = getattr(PostgresControlQueries(connection), name)(workspace_id=WORKSPACE, query=query)
    sql, params = connection.calls[0]
    return page, ' '.join(sql.split()), params


@pytest.mark.parametrize('name', ['operations', 'configs'])
@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [None, CURSOR])
def test_operations_configs_sql_is_parameterized_keyset(name, direction, cursor):
    case = LIST_CASES[name]
    query = make_query(sort_key=case['sort'], direction=direction, cursor=cursor)
    _, sql, params = run_list(name, query)
    operator = '>' if direction == 'asc' else '<'
    assert sql.endswith('ORDER BY ' + case['order'].format(d=direction.upper()) + ' LIMIT %s')
    assert 'LIMIT 100' not in sql and 'OFFSET' not in sql.upper()
    assert sql.count('%s') == len(params) and sql.count('%') == sql.count('%s')
    if cursor is None:
        assert params == (WORKSPACE, 51)
        assert '(%s, %s)' not in sql
    else:
        assert f"{case['keyset']} {operator} (%s, %s) ORDER BY" in sql
        assert params == (WORKSPACE, *CURSOR, 51)


@pytest.mark.parametrize('name', ['operations', 'configs'])
def test_operations_configs_cursor_values_only_travel_in_params(name):
    query = make_query(sort_key=LIST_CASES[name]['sort'], cursor=(EVIL, EVIL))
    _, sql, params = run_list(name, query)
    assert 'DROP' not in sql and EVIL not in sql
    assert params == (WORKSPACE, EVIL, EVIL, 51)


@pytest.mark.parametrize('name', ['operations', 'configs'])
@pytest.mark.parametrize('overrides, code', [
    ({'sort_key': 'status'}, 'column_not_allowed'),
    ({'filters': (('status', 'x'),)}, 'column_not_allowed'),
    ({'direction': 'DESC'}, 'direction_invalid'),
    ({'limit': 0}, 'limit_invalid'),
    ({'limit': True}, 'limit_invalid'),
])
def test_operations_configs_reject_bad_query_before_touching_connection(name, overrides, code):
    connection = FakeConnection()
    query = make_query(**{'sort_key': LIST_CASES[name]['sort'], **overrides})
    with pytest.raises(ValueError, match='^' + code + '$'):
        getattr(PostgresControlQueries(connection), name)(workspace_id=WORKSPACE, query=query)
    assert connection.calls == []


@pytest.mark.parametrize('name', ['operations', 'configs'])
def test_operations_configs_next_cursor_only_with_extra_row(name):
    case = LIST_CASES[name]
    rows = [case['row'](i) for i in range(3)]
    page, _, params = run_list(name, make_query(sort_key=case['sort'], limit=2), rows)
    assert params[-1] == 3 and len(page.items) == 2
    assert page.items[1][case['id_field']] == rows[1][case['id_index']]
    assert decode_cursor(page.next_cursor) == ('2026-01-01T00:00:01+00:00', rows[1][case['id_index']])
    full, _, _ = run_list(name, make_query(sort_key=case['sort'], limit=3), rows)
    assert len(full.items) == 3 and full.next_cursor is None
    empty, _, _ = run_list(name, make_query(sort_key=case['sort']), [])
    assert empty.items == () and empty.next_cursor is None


def test_batches_and_jobs_delegate_to_fetch_page_with_specs():
    jobs_connection = FakeConnection([job_row(i) for i in range(3)])
    jobs_page = PostgresControlQueries(jobs_connection).jobs(workspace_id=WORKSPACE, query=make_query())
    assert jobs_connection.calls == [build_list_sql(JOBS_SPEC, make_query(), workspace_id=WORKSPACE)]
    assert len(jobs_page.items) == 3 and jobs_page.next_cursor is None
    rows = [(f'b-{i}', 'CREATED', 5, f'2026-01-01T00:00:0{i}+00:00') for i in range(3)]
    batches_connection = FakeConnection(rows)
    batches_page = PostgresControlQueries(batches_connection).batches(workspace_id=WORKSPACE, query=make_query(limit=2))
    assert batches_connection.calls == [build_list_sql(BATCHES_SPEC, make_query(limit=2), workspace_id=WORKSPACE)]
    assert len(batches_page.items) == 2 and batches_page.next_cursor is not None


ORIGIN = 'https://localhost:8443'
READ_HEADERS = {'Cookie': 'cp_session=valid'}
IDENTITY = {'workspace_id': WORKSPACE, 'actor_id': 'actor-1', 'session_id': 'session-1'}
LIST_ROUTES = {
    '/v1/operations': ('operations', 'accepted_at'),
    '/v1/batches': ('batches', 'created_at'),
    '/v1/jobs': ('jobs', 'created_at'),
    '/v1/configs': ('configs', 'created_at'),
}


class FakeManager:
    @contextmanager
    def borrow_connection(self):
        yield object()

    def unit_of_work(self):
        raise RuntimeError('kh\u00f4ng d\u00f9ng trong test danh s\u00e1ch')


class FakeSessions:
    def resolve(self, *, connection, token):
        if token == 'valid':
            return IDENTITY
        raise PermissionError('invalid session token')


class RecordingQueries:
    def __init__(self, page):
        self.page = page
        self.calls = []

    def _list(self, name, workspace_id, query):
        self.calls.append((name, workspace_id, query))
        return self.page

    def operations(self, *, connection, workspace_id, query):
        return self._list('operations', workspace_id, query)

    def batches(self, *, connection, workspace_id, query):
        return self._list('batches', workspace_id, query)

    def jobs(self, *, connection, workspace_id, query):
        return self._list('jobs', workspace_id, query)

    def configs(self, *, connection, workspace_id, query):
        return self._list('configs', workspace_id, query)


def make_client(page=None):
    app = create_app(manager=FakeManager(), allowed_origins={ORIGIN})
    app.state.session_service = FakeSessions()
    queries = RecordingQueries(page if page is not None else Page(items=(), next_cursor=None))
    app.state.query_service = queries
    return TestClient(app, base_url=ORIGIN, raise_server_exceptions=False), queries


@pytest.mark.parametrize('path', list(LIST_ROUTES))
def test_list_route_defaults_to_newest_first_limit_50_and_empty_page_shape(path):
    client, queries = make_client()
    response = client.get(path, headers=READ_HEADERS)
    assert response.status_code == 200
    assert response.json() == {'items': [], 'next_cursor': None}
    name, sort = LIST_ROUTES[path]
    assert queries.calls == [(name, WORKSPACE, make_query(limit=50, sort_key=sort, direction='desc'))]


@pytest.mark.parametrize('path', list(LIST_ROUTES))
def test_list_route_returns_next_cursor_from_page(path):
    client, _ = make_client(Page(items=({'k': 1},), next_cursor='abc'))
    assert client.get(path, headers=READ_HEADERS).json() == {'items': [{'k': 1}], 'next_cursor': 'abc'}


@pytest.mark.parametrize('path', list(LIST_ROUTES))
def test_list_route_forwards_limit_direction_and_cursor(path):
    client, queries = make_client()
    params = {'limit': '25', 'direction': 'asc', 'cursor': encode_cursor(*CURSOR)}
    assert client.get(path, params=params, headers=READ_HEADERS).status_code == 200
    name, sort = LIST_ROUTES[path]
    assert queries.calls == [(name, WORKSPACE, make_query(limit=25, sort_key=sort, direction='asc', cursor=CURSOR))]


BAD_PARAMS = [
    {'cursor': '***'}, {'limit': '0'}, {'limit': '101'}, {'limit': 'abc'},
    {'direction': 'up'}, {'sort': 'status'}, {'workspace_id': 'other'},
]


@pytest.mark.parametrize('params', BAD_PARAMS)
@pytest.mark.parametrize('path', list(LIST_ROUTES))
def test_list_route_rejects_bad_params_with_422(path, params):
    client, queries = make_client()
    response = client.get(path, params=params, headers=READ_HEADERS)
    assert response.status_code == 422
    assert queries.calls == []


@pytest.mark.parametrize('path', list(LIST_ROUTES))
def test_list_route_accepts_limit_100(path):
    client, queries = make_client()
    assert client.get(path, params={'limit': '100'}, headers=READ_HEADERS).status_code == 200
    assert queries.calls[0][2].limit == 100


@pytest.mark.parametrize('path, params, filters', [
    ('/v1/jobs', {'status': 'RUNNING', 'batch_id': 'b-1'}, (('batch_id', 'b-1'), ('status', 'RUNNING'))),
    ('/v1/batches', {'status': 'CREATED'}, (('status', 'CREATED'),)),
])
def test_list_route_forwards_allowed_filters(path, params, filters):
    client, queries = make_client()
    assert client.get(path, params=params, headers=READ_HEADERS).status_code == 200
    assert queries.calls[0][2].filters == filters


@pytest.mark.parametrize('path, params', [
    ('/v1/operations', {'status': 'x'}),
    ('/v1/configs', {'status': 'x'}),
    ('/v1/batches', {'batch_id': 'b-1'}),
])
def test_list_route_rejects_unlisted_filter_with_422(path, params):
    client, queries = make_client()
    assert client.get(path, params=params, headers=READ_HEADERS).status_code == 422
    assert queries.calls == []


def test_control_route_source_has_no_literal_next_cursor_none():
    text = CONTROL_PATH.read_text(encoding='utf-8')
    assert '"next_cursor": None' not in text and "'next_cursor': None" not in text
    assert 'parse_list_query' in text
