"""RS-11: PostgreSQL tests for the read-only cost service (module J).

Rows are created through PostgresCostLedger.append; only the ledger writes, the service never does.
"""
from __future__ import annotations

import ast
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, ListQueryError, Page, parse_list_query
from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
from controlplane.infrastructure.db.config_security.stores import PostgresCostLedger
from controlplane.infrastructure.read_screens.cost import CostModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'cost.py'
ROW_KEYS = {'cost_id', 'job_id', 'provider', 'amount', 'currency', 'amount_basis', 'recorded_at'}
FORBIDDEN_KEYS = {'record_id', 'workspace_id', 'service', 'operation_ref', 'job_ref', 'batch_ref', 'quantity', 'unit', 'estimated_cost', 'actual_cost', 'source', 'occurred_at', 'cost_category', 'created_at', 'updated_at'}
FORBIDDEN_FRAGMENTS = ('float(', 'operation_ref', 'batch_ref', 'source', 'insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ')
OPERATION_CANARY = 'CANARY-OPERATION'
BATCH_CANARY = 'CANARY-BATCH'
SOURCE_CANARY = 'CANARY-SOURCE'
SERVICE_CANARY = 'CANARY-SERVICE'
UNIT_CANARY = 'CANARY-UNIT'
CANARIES = (OPERATION_CANARY, BATCH_CANARY, SOURCE_CANARY, SERVICE_CANARY, UNIT_CANARY)

# (record_id, provider, job_ref, estimated_cost, actual_cost, currency, occurred_at). cost-b and cost-d share occurred_at, so they are ordered by id.
W1_COSTS = [
    ('cost-c', 'router', 'job-1', '0.50', '0.40', 'USD', '2026-10-01T08:00:00.123456+00:00'),
    ('cost-a', 'router', 'job-1', '0.200000', None, 'USD', '2026-10-02T08:00:00+00:00'),
    ('cost-b', 'drive', None, '1.25', '1.30', 'VND', '2026-10-03T08:00:00+00:00'),
    ('cost-d', 'drive', 'job-2', '0.000123', None, 'USD', '2026-10-03T08:00:00+00:00'),
    ('cost-e', 'router', 'job-2', '0.05', '0', 'USD', '2026-09-30T08:00:00+00:00'),
    ('cost-f', 'router', None, '12345678901234567890.123456789', None, 'USD', '2026-09-29T08:00:00+00:00'),
    ('cost-g', 'drive', 'job-1', '0.0000001', None, 'USD', '2026-09-28T08:00:00+00:00'),
]
# The other workspace reuses the id cost-a of W1 on purpose.
OTHER_COSTS = [
    ('cost-a', 'router', 'job-1', '9.99', None, 'USD', '2026-10-05T08:00:00+00:00'),
    ('cost-z', 'drive', 'job-9', '3.50', '3.25', 'USD', '2026-10-04T08:00:00+00:00'),
]
# Hand-written oracle: (amount text, amount_basis).
AMOUNTS = {'cost-c': ('0.40', 'actual'), 'cost-a': ('0.200000', 'estimated'), 'cost-b': ('1.30', 'actual'), 'cost-d': ('0.000123', 'estimated'), 'cost-e': ('0', 'actual'), 'cost-f': ('12345678901234567890.123456789', 'estimated'), 'cost-g': ('0.0000001', 'estimated')}
OTHER_AMOUNTS = {'cost-a': ('9.99', 'estimated'), 'cost-z': ('3.25', 'actual')}
EXPECTED = {ref: (provider, job, currency, *AMOUNTS[ref], occurred) for ref, provider, job, _est, _act, currency, occurred in W1_COSTS}
OTHER_EXPECTED = {ref: (provider, job, currency, *OTHER_AMOUNTS[ref], occurred) for ref, provider, job, _est, _act, currency, occurred in OTHER_COSTS}
ASC = ['cost-g', 'cost-f', 'cost-e', 'cost-c', 'cost-a', 'cost-b', 'cost-d']
DESC = list(reversed(ASC))


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: CostModuleService
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


def seed(manager: Any, workspace_id: str, costs: list[Any]) -> None:
    with manager.borrow_connection() as connection:
        ledger = PostgresCostLedger(connection)
        for ref, provider, job, estimated, actual, currency, occurred_at in costs:
            ledger.append(
                workspace_id,
                IncrementalCostRecord(
                    ref,
                    provider,
                    f'{SERVICE_CANARY}-{ref}',
                    f'{OPERATION_CANARY}-{ref}',
                    job,
                    f'{BATCH_CANARY}-{ref}',
                    Decimal('1'),
                    UNIT_CANARY,
                    Decimal(estimated),
                    None if actual is None else Decimal(actual),
                    currency,
                    f'{SOURCE_CANARY}-{ref}',
                    occurred_at,
                    'api_paid',
                ),
            )


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        seed(manager, workspace_id, W1_COSTS)
        seed(manager, other_workspace_id, OTHER_COSTS)
        statements: list[str] = []
        yield Env(manager, workspace_id, other_workspace_id, CostModuleService(lambda: recording_scope(manager, statements)), statements)


def make_row(ref: str, other: bool = False) -> dict[str, Any]:
    provider, job, currency, amount, basis, occurred = (OTHER_EXPECTED if other else EXPECTED)[ref]
    return {
        'cost_id': ref,
        'job_id': job,
        'provider': provider,
        'amount': amount,
        'currency': currency,
        'amount_basis': basis,
        'recorded_at': utc_of(occurred),
    }


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['recorded_at'], allowed_filters={'provider', 'job_id'}, default_limit=20, max_limit=100)


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
    return [item['cost_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [ref for page in pages for ref in ids_of(page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids_of(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['cost_id']: item for item in page.items} == {ref: make_row(ref) for ref in ASC}


def test_amount_is_exact_decimal_text_with_basis(env):
    rows = {item['cost_id']: item for item in get_page(env, {}).items}
    assert {ref: (rows[ref]['amount'], rows[ref]['amount_basis']) for ref in ASC} == AMOUNTS
    assert all(isinstance(row['amount'], str) and re.fullmatch(r'[0-9]+([.][0-9]+)?', row['amount']) for row in rows.values())
    assert rows['cost-d']['amount'] == '0.000123'
    assert rows['cost-g']['amount'] == '0.0000001'
    assert rows['cost-e']['amount'] == '0' and rows['cost-e']['amount_basis'] == 'actual'
    assert rows['cost-f']['amount'] == '12345678901234567890.123456789'
    assert rows['cost-c']['amount'] == '0.40'
    assert {row['amount_basis'] for row in rows.values()} == {'actual', 'estimated'}


def test_job_id_is_null_without_job_and_time_is_utc_text(env):
    rows = {item['cost_id']: item for item in get_page(env, {}).items}
    assert rows['cost-b']['job_id'] is None
    assert rows['cost-f']['job_id'] is None
    assert rows['cost-c']['job_id'] == 'job-1'
    assert rows['cost-d']['job_id'] == 'job-2'
    assert rows['cost-c']['recorded_at'] == '2026-10-01T08:00:00.123456Z'
    assert rows['cost-a']['recorded_at'] == '2026-10-02T08:00:00.000000Z'
    assert rows['cost-b']['currency'] == 'VND'
    assert rows['cost-a']['currency'] == 'USD'
    assert {row['provider'] for row in rows.values()} == {'drive', 'router'}


def test_order_follows_recorded_at_then_id(env):
    ascending = ids_of(get_page(env, {'direction': 'asc'}))
    assert ascending == ASC
    assert ascending != sorted(ASC)
    assert ids_of(get_page(env, {})) == DESC
    assert ids_of(get_page(env, {'sort': 'recorded_at'})) == DESC
    assert ids_of(get_page(env, {'direction': 'desc'})) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, limit):
    pages = walk(env, {'direction': direction}, limit)
    expected = ASC if direction == 'asc' else DESC
    assert all_ids(pages) == expected
    assert len(pages) == -(-7 // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 3)
    assert len(pages) == 3
    assert all_ids(pages) == DESC


@pytest.mark.parametrize(
    'provider, expected',
    [
        ('router', ['cost-a', 'cost-c', 'cost-e', 'cost-f']),
        ('drive', ['cost-d', 'cost-b', 'cost-g']),
        ('unknown', []),
        ('ROUTER', []),
        ('router ', []),
        ('', []),
    ],
)
def test_provider_filter_exact_match_and_unknown_value_is_empty(env, provider, expected):
    page = get_page(env, {'provider': provider})
    assert ids_of(page) == expected
    assert page.next_cursor is None


@pytest.mark.parametrize(
    'job_id, expected',
    [
        ('job-1', ['cost-a', 'cost-c', 'cost-g']),
        ('job-2', ['cost-d', 'cost-e']),
        ('job-9', []),
        ('JOB-1', []),
        ('job-1 ', []),
        ('', []),
        ('None', []),
    ],
)
def test_job_filter_exact_match_and_unknown_value_is_empty(env, job_id, expected):
    page = get_page(env, {'job_id': job_id})
    assert ids_of(page) == expected
    assert page.next_cursor is None


def test_combined_filters_and_pagination_both_ways(env):
    assert ids_of(get_page(env, {'provider': 'router', 'job_id': 'job-2'})) == ['cost-e']
    assert ids_of(get_page(env, {'provider': 'drive', 'job_id': 'job-1'})) == ['cost-g']
    assert ids_of(get_page(env, {'provider': 'drive', 'job_id': 'job-2'})) == ['cost-d']
    assert ids_of(get_page(env, {'provider': 'router', 'job_id': 'job-9'})) == []
    pages_asc = walk(env, {'provider': 'drive', 'direction': 'asc'}, 1)
    assert len(pages_asc) == 3
    assert all_ids(pages_asc) == ['cost-g', 'cost-b', 'cost-d']
    pages_desc = walk(env, {'provider': 'drive'}, 1)
    assert len(pages_desc) == 3
    assert all_ids(pages_desc) == ['cost-d', 'cost-b', 'cost-g']


def test_fetch_one_returns_row_or_none(env):
    for ref in ASC:
        assert get_one(env, ref) == make_row(ref)
    for missing in ('cost-', 'COST-A', 'cost-a ', 'nope', '', 'cost-z'):
        assert get_one(env, missing) is None
    assert get_one(env, 'cost-c', env.other_workspace_id) is None
    assert get_one(env, 'cost-z', env.other_workspace_id) == make_row('cost-z', other=True)
    assert get_one(env, 'cost-a', env.other_workspace_id) == make_row('cost-a', other=True)


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    theirs = get_page(env, {}, other)
    assert ids_of(theirs) == ['cost-a', 'cost-z']
    assert list(theirs.items) == [make_row('cost-a', other=True), make_row('cost-z', other=True)]
    assert all_ids(walk(env, {'direction': 'asc'}, 1, other)) == ['cost-z', 'cost-a']
    mine = get_page(env, {})
    assert ids_of(mine) == DESC
    assert ids_of(get_page(env, {'provider': 'drive'})) == ['cost-d', 'cost-b', 'cost-g']
    assert ids_of(get_page(env, {'provider': 'drive'}, other)) == ['cost-z']
    assert ids_of(get_page(env, {'job_id': 'job-9'})) == []
    assert ids_of(get_page(env, {'job_id': 'job-9'}, other)) == ['cost-z']
    assert ids_of(get_page(env, {'job_id': 'job-1'}, other)) == ['cost-a']
    assert ids_of(get_page(env, {'job_id': 'job-1'})) == ['cost-a', 'cost-c', 'cost-g']
    assert get_one(env, 'cost-a')['amount'] == '0.200000'
    assert get_one(env, 'cost-a', other)['amount'] == '9.99'
    assert not any(item['amount'] in ('9.99', '3.25') for item in mine.items)


def test_unsupported_filter_and_sort_raise_value_error(env):
    for name in ('cost_id', 'record_id', 'job_ref', 'operation_ref', 'batch_ref', 'status', 'workspace_id'):
        query = ListQuery(limit=5, cursor=None, sort_key='recorded_at', direction='desc', filters=((name, 'x'),))
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    for sort_key in ('occurred_at', 'record_id', 'provider'):
        query = ListQuery(limit=5, cursor=None, sort_key=sort_key, direction='desc', filters=())
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    with pytest.raises(ListQueryError):
        make_query({'job_ref': 'x'})


def table_state(env: Env) -> list[Any]:
    with env.manager.borrow_connection() as connection:
        return connection.execute(
            'SELECT workspace_id::text, record_id, provider, service, operation_ref, job_ref, batch_ref, quantity, unit, estimated_cost, actual_cost, currency, source, occurred_at, cost_category, created_at, updated_at '
            'FROM controlplane.cp_cost_records '
            'ORDER BY workspace_id, record_id'
        ).fetchall()


def test_reads_do_not_change_the_table(env):
    before = table_state(env)
    assert len(before) == 9
    get_page(env, {})
    get_page(env, {'provider': 'drive'})
    get_page(env, {'job_id': 'job-1'})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'cost-a')
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('cost-a', 'cost-a')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='recorded_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, ref, workspace_id) for ref in (*ASC, 'cost-z'))
    rows = [row for row in rows if row is not None]
    text = json.dumps(rows)
    assert rows
    assert not [c for c in CANARIES if c in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_reads_only_the_cost_table_with_workspace_scope(env):
    env.statements.clear()
    get_page(env, {})
    get_page(env, {'provider': 'drive', 'direction': 'asc'})
    get_page(env, {'job_id': 'job-1'})
    walk(env, {}, 1)
    get_one(env, 'cost-a')
    get_one(env, 'nope')
    assert len(env.statements) >= 8
    for statement in env.statements:
        lowered = statement.lower()
        assert lowered.startswith('select ')
        assert 'controlplane.cp_cost_records' in lowered
        assert 'workspace_id = %s::uuid' in lowered
        assert not any(frag in lowered for frag in ('operation_ref', 'batch_ref', 'source', 'service', 'quantity', 'cost_category', 'created_at', 'updated_at'))


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [f for f in FORBIDDEN_FRAGMENTS if f in lowered]
    assert 'cp_cost_records' in lowered and 'job_ref' in lowered and 'occurred_at' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not any(m and (m.startswith('controlplane.api') or m.startswith('src')) for m in modules)
