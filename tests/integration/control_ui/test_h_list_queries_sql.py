"""H-04: SQL keyset tham số hóa cho danh sách (connection giả).

coveredIds: CT-API-001, CT-API-002
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
from datetime import datetime, timezone

import pytest

from controlplane.application.projections.list_query import ListQuery, decode_cursor
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


def select_statements():
    tree = ast.parse(QUERIES_PATH.read_text(encoding='utf-8'))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ('batches', 'jobs'):
            literals = [c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            found[node.name] = next(value for value in literals if value.startswith('SELECT '))
    return found


@pytest.mark.parametrize('name, spec', [('batches', BATCHES_SPEC), ('jobs', JOBS_SPEC)])
def test_specs_match_control_api_queries(name, spec):
    statement = select_statements()[name]
    pattern = (
        r'SELECT (?P<cols>.+?) FROM (?P<table>\S+) WHERE workspace_id = %s '
        r'ORDER BY (?P<sort>\w+) DESC, (?P<id>\w+) DESC LIMIT 100'
    )
    match = re.fullmatch(pattern, statement)
    assert match is not None
    assert match['table'] == spec.table
    assert tuple(column.strip() for column in match['cols'].split(',')) == spec.select_columns
    assert match['id'] == spec.id_column
    assert match['sort'] in spec.sort_columns
