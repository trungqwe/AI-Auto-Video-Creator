"""H-02: phân trang keyset, lọc và sắp xếp có whitelist.

coveredIds: CT-API-001, CT-API-002, QR-PERF-005
"""
from __future__ import annotations

import ast
import base64
import dataclasses
import json
import pathlib
import string

import pytest

from controlplane.application.projections.list_query import (
    ListQuery,
    ListQueryError,
    Page,
    build_page,
    decode_cursor,
    encode_cursor,
    parse_list_query,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'projections' / 'list_query.py'
ALLOWED_SORTS = ('created_at', 'name')
ALLOWED_FILTERS = frozenset({'status', 'kind'})
VI_TEXT = 'Tiếng Việt: đường dẫn ạ ơ ư – ✓'


def parse(params, **overrides):
    config = {
        'allowed_sorts': ALLOWED_SORTS,
        'allowed_filters': ALLOWED_FILTERS,
        'default_limit': 50,
        'max_limit': 100,
    }
    config.update(overrides)
    return parse_list_query(params, **config)


def error_of(params, **overrides):
    with pytest.raises(ListQueryError) as info:
        parse(params, **overrides)
    return info.value


def raw_token(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def test_defaults_without_params():
    query = parse({})
    assert query == ListQuery(limit=50, cursor=None, sort_key='created_at', direction='asc', filters=())


@pytest.mark.parametrize(('raw', 'expected'), [('1', 1), ('50', 50), ('100', 100), ('007', 7)])
def test_limit_accepts_ascii_digits_within_range(raw, expected):
    assert parse({'limit': raw}).limit == expected


# '５' là chữ số toàn chiều rộng, '²' và '٣' là chữ số Unicode không phải ASCII.
@pytest.mark.parametrize(
    'raw',
    ['0', '101', 'abc', '-1', '+5', '1e2', '1.5', '５', '²', '٣', '', '  ', ' 5', '5 ', '9' * 19, 5, None],
)
def test_limit_rejects_invalid_values(raw):
    error = error_of({'limit': raw})
    assert (error.code, error.field) == ('limit_invalid', 'limit')


def test_max_limit_comes_from_caller():
    assert parse({'limit': '101'}, max_limit=200).limit == 101
    assert error_of({'limit': '201'}, max_limit=200).code == 'limit_invalid'


@pytest.mark.parametrize(
    ('default_limit', 'max_limit'),
    [(101, 100), (0, 100), (-1, 100), (50, 0), (1, -5), (True, 100), (50, True), ('50', 100), (50, '100'), (50.0, 100), (None, 100)],
)
def test_invalid_limit_config_raises_value_error(default_limit, max_limit):
    with pytest.raises(ValueError):
        parse({}, default_limit=default_limit, max_limit=max_limit)


def test_default_equal_to_max_is_allowed():
    assert parse({}, default_limit=7, max_limit=7).limit == 7


@pytest.mark.parametrize('allowed_sorts', [(), [], 'created_at'])
def test_invalid_allowed_sorts_config_raises_value_error(allowed_sorts):
    with pytest.raises(ValueError):
        parse({}, allowed_sorts=allowed_sorts)


def test_allowed_filters_given_as_string_raises_value_error():
    with pytest.raises(ValueError):
        parse({}, allowed_filters='status')


def test_sort_and_direction_whitelist():
    query = parse({'sort': 'name', 'direction': 'desc'})
    assert (query.sort_key, query.direction) == ('name', 'desc')


@pytest.mark.parametrize('raw', ['password', 'CREATED_AT', 'created_at;drop table x', '', ' name', 'id', None, 7])
def test_sort_outside_whitelist_is_rejected(raw):
    error = error_of({'sort': raw})
    assert (error.code, error.field) == ('sort_not_allowed', 'sort')


@pytest.mark.parametrize('raw', ['up', 'ASC', '', 'asc ', None])
def test_direction_outside_whitelist_is_rejected(raw):
    error = error_of({'direction': raw})
    assert (error.code, error.field) == ('sort_not_allowed', 'direction')


def test_allowed_filters_are_returned_sorted_by_name():
    query = parse({'status': 'running', 'kind': 'render', 'limit': '5'})
    assert query.filters == (('kind', 'render'), ('status', 'running'))


@pytest.mark.parametrize('name', ['workspace_id', 'actor_id'])
def test_identity_filters_are_never_allowed(name):
    for allowed in (ALLOWED_FILTERS, ALLOWED_FILTERS | {name}):
        error = error_of({name: 'x'}, allowed_filters=allowed)
        assert (error.code, error.field) == ('filter_not_allowed', name)


def test_unknown_param_is_filter_not_allowed():
    error = error_of({'status': 'running', 'owner': 'x'})
    assert (error.code, error.field) == ('filter_not_allowed', 'owner')


def test_non_string_filter_value_is_rejected():
    error = error_of({'status': ['a', 'b']})
    assert (error.code, error.field) == ('filter_not_allowed', 'status')


def test_error_message_does_not_echo_values():
    error = error_of({'workspace_id': 'secret-canary'})
    assert 'secret-canary' not in str(error)


def test_query_never_carries_identity():
    query = parse({'status': 'running'})
    assert not hasattr(query, 'workspace_id')
    assert not hasattr(query, 'actor_id')
    assert dict(query.filters) == {'status': 'running'}


def test_cursor_param_is_decoded_into_query():
    token = encode_cursor('2026-10-20T00:00:00Z', 'op-1')
    assert parse({'cursor': token}).cursor == ('2026-10-20T00:00:00Z', 'op-1')


@pytest.mark.parametrize('raw', ['', '10', 'MTA', '!!!', 'A' * 513, None, 10])
def test_invalid_cursor_param_is_rejected(raw):
    error = error_of({'cursor': raw})
    assert (error.code, error.field) == ('cursor_invalid', 'cursor')


def test_dataclasses_are_frozen():
    query = parse({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        query.limit = 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        Page(items=(), next_cursor=None).next_cursor = 'x'


@pytest.mark.parametrize(
    ('sort_value', 'row_id'),
    [('a', 'b'), ('', 'id-1'), (VI_TEXT, 'op-Ạ-1'), ('2026-10-20T00:00:00Z', 'op-00042'), ('x' * 7, 'y' * 3)],
)
def test_cursor_round_trip(sort_value, row_id):
    token = encode_cursor(sort_value, row_id)
    assert isinstance(token, str)
    assert '=' not in token
    assert set(token) <= set(string.ascii_letters + string.digits + '-_')
    assert decode_cursor(token) == (sort_value, row_id)


def test_cursor_is_base64url_of_json_pair():
    token = encode_cursor(VI_TEXT, 'op-1')
    padded = token + '=' * (-len(token) % 4)
    assert json.loads(base64.urlsafe_b64decode(padded)) == [VI_TEXT, 'op-1']


def test_cursor_is_not_an_integer_offset():
    assert not encode_cursor('a', 'b').isdigit()


@pytest.mark.parametrize(
    'token',
    [
        '', '!!!', 'abc=', 'AAAA AAAA', 'A' * 5, 'A' * 513,
        raw_token(b'not json'), raw_token(b'\xff\xfe\xfd'),
        raw_token(b'[]'), raw_token(b'["a"]'), raw_token(b'["a","b","c"]'),
        raw_token(b'[1,"a"]'), raw_token(b'["a",2]'), raw_token(b'["a",null]'),
        raw_token(b'[["a"],"b"]'), raw_token(b'{"a":"b"}'), raw_token(b'"ab"'),
        raw_token(b'42'), raw_token(b'null'),
        None, 10, b'abc', ['a', 'b'],
    ],
)
def test_decode_rejects_invalid_cursor(token):
    with pytest.raises(ListQueryError) as info:
        decode_cursor(token)
    assert (info.value.code, info.value.field) == ('cursor_invalid', 'cursor')


def test_decode_enforces_512_character_limit():
    at_limit = raw_token(json.dumps(['a' * 376, 'b'], separators=(',', ':')).encode('ascii'))
    assert len(at_limit) == 512
    assert decode_cursor(at_limit) == ('a' * 376, 'b')
    over = raw_token(json.dumps(['a' * 379, 'b'], separators=(',', ':')).encode('ascii'))
    assert len(over) > 512
    with pytest.raises(ListQueryError) as info:
        decode_cursor(over)
    assert info.value.code == 'cursor_invalid'


def test_encode_refuses_cursor_longer_than_limit():
    assert len(encode_cursor('a' * 376, 'b')) == 512
    with pytest.raises(ValueError):
        encode_cursor('a' * 377, 'b')


@pytest.mark.parametrize(('sort_value', 'row_id'), [(1, 'a'), ('a', 1), (None, 'a'), ('a', None), (b'a', 'b')])
def test_encode_rejects_non_string_values(sort_value, row_id):
    with pytest.raises(ValueError):
        encode_cursor(sort_value, row_id)


ALLOWED_IMPORTS = {'__future__', 'base64', 'collections.abc', 'dataclasses', 'json', 'string'}


def make_rows(count):
    return [{'name': f'item-{index:02d}', 'op_id': f'op-{index:02d}', 'label': VI_TEXT} for index in range(count)]


def make_query(limit):
    return ListQuery(limit=limit, cursor=None, sort_key='name', direction='asc', filters=())


def test_build_page_with_extra_row_has_cursor_of_last_item():
    rows = make_rows(4)
    page = build_page(rows, query=make_query(3), sort_field='name', id_field='op_id')
    assert page.items == tuple(rows[:3])
    assert page.next_cursor is not None
    assert decode_cursor(page.next_cursor) == ('item-02', 'op-02')


@pytest.mark.parametrize('count', [0, 1, 2, 3])
def test_build_page_without_extra_row_has_no_cursor(count):
    rows = make_rows(count)
    page = build_page(rows, query=make_query(3), sort_field='name', id_field='op_id')
    assert page.items == tuple(rows)
    assert page.next_cursor is None


def test_build_page_limit_one():
    rows = make_rows(2)
    page = build_page(rows, query=make_query(1), sort_field='name', id_field='op_id')
    assert page.items == (rows[0],)
    assert decode_cursor(page.next_cursor) == ('item-00', 'op-00')


def test_build_page_does_not_mutate_input_rows():
    rows = make_rows(4)
    snapshot = [dict(row) for row in rows]
    build_page(rows, query=make_query(3), sort_field='name', id_field='op_id')
    assert rows == snapshot


def test_keyset_walk_visits_every_row_once_and_last_page_has_no_cursor():
    rows = make_rows(7)
    limit = 3
    seen = []
    cursor = None
    pages = 0
    while True:
        remaining = [row for row in rows if cursor is None or (row['name'], row['op_id']) > cursor]
        page = build_page(remaining[: limit + 1], query=make_query(limit), sort_field='name', id_field='op_id')
        seen.extend(row['op_id'] for row in page.items)
        pages += 1
        assert pages <= 3
        if page.next_cursor is None:
            break
        cursor = decode_cursor(page.next_cursor)
    assert seen == [row['op_id'] for row in rows]
    assert pages == 3
    assert page.next_cursor is None


def test_module_imports_only_pure_stdlib():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= ALLOWED_IMPORTS
