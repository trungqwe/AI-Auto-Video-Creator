"""CP-4-QUERIES: route danh sách chỉ đọc của Control API, dịch vụ thật trên kết nối giả (không PostgreSQL)."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi.routing import _iter_routes_with_context
from fastapi.testclient import TestClient
import pytest

from controlplane.api.main import create_app
from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.control_api.query_ports import ControlApiQueryService, ControlQueryPort
from controlplane.application.projections.list_query import ListQuery, decode_cursor
from controlplane.infrastructure.db import control_api_queries as queries
from controlplane.infrastructure.db.control_api_queries import PostgresControlQueries

WORKSPACE = '00000000-0000-0000-0000-0000000004b1'
ORIGIN = 'https://localhost:8443'
READ = {'Cookie': 'cp_session=valid'}
NINE = ('sources', 'articles', 'events', 'media', 'hooks', 'stage_runs', 'sessions', 'logs', 'capabilities')
ITEM_KEYS = {'stage_run_id', 'job_id', 'stage', 'status', 'started_at', 'finished_at', 'created_at'}

ROOT = Path(__file__).resolve().parents[3]
QUERIES_PATH = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'control_api_queries.py'
CONTROL_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'control.py'


class FakeResult:
    def __init__(self, rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...]) -> None:
        self._rows = list(rows)

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class FakeConnection:
    def __init__(self, rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...] = ()) -> None:
        self._rows = list(rows)
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> FakeResult:
        self.calls.append((sql, tuple(params)))
        return FakeResult(self._rows)


class FakeUow:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeManager:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def unit_of_work(self) -> FakeUow:
        return FakeUow(self._connection)

    @contextmanager
    def borrow_connection(self):
        yield self._connection


class FakeSessionService:
    def resolve(self, *, connection: object, token: str) -> dict[str, str]:
        if token == 'valid':
            return {
                'workspace_id': WORKSPACE,
                'actor_id': '00000000-0000-0000-0000-0000000000a1',
                'session_id': '00000000-0000-0000-0000-0000000000s1',
            }
        raise PermissionError('invalid session token')


def stage_row(i: int) -> tuple[object, ...]:
    return (
        f'sr-{i:04d}',
        'j-0001',
        'script',
        'RUNNING',
        None,
        None,
        datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc),
    )


def client_for(rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...] = ()):
    connection = FakeConnection(rows)
    app = create_app(manager=FakeManager(connection), allowed_origins={ORIGIN})
    app.state.session_service = FakeSessionService()
    return TestClient(app, base_url=ORIGIN, raise_server_exceptions=False), connection, app


def test_stage_runs_page_shape():
    rows = [stage_row(3), stage_row(2), stage_row(1)]
    client, connection, _ = client_for(rows)
    response = client.get('/v1/stage-runs?limit=2', headers=READ)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'items', 'next_cursor'}
    items = body['items']
    assert len(items) == 2
    assert set(items[0].keys()) == ITEM_KEYS
    assert 'stage_name' not in items[0]
    assert items[0]['stage'] == 'script'
    assert decode_cursor(body['next_cursor']) == (items[1]['created_at'], items[1]['stage_run_id'])
    assert len(connection.calls) == 1
    sql, params = connection.calls[0]
    assert sql.startswith('SELECT')
    assert 'FROM controlplane.cp_stage_runs' in sql
    assert 'ORDER BY created_at DESC, stage_run_id DESC' in sql
    assert params[0] == WORKSPACE
    assert params[-1] == 3


def test_asc_override_and_cursor_condition():
    rows = [stage_row(3), stage_row(2), stage_row(1)]
    client, connection, _ = client_for(rows)
    response_asc = client.get('/v1/stage-runs?direction=asc', headers=READ)
    assert response_asc.status_code == 200
    assert 'ORDER BY created_at ASC' in connection.calls[-1][0]

    res_a = client.get('/v1/stage-runs?limit=2', headers=READ)
    cursor = res_a.json()['next_cursor']
    res_cursor = client.get(f'/v1/stage-runs?cursor={cursor}', headers=READ)
    assert res_cursor.status_code == 200
    assert '(created_at, stage_run_id) < (%s, %s)' in connection.calls[-1][0]


def test_filters_whitelisted():
    client, connection, _ = client_for([])
    response = client.get('/v1/stage-runs?job_id=j-0001&status=RUNNING', headers=READ)
    assert response.status_code == 200
    sql, params = connection.calls[0]
    assert 'job_id = %s' in sql
    assert 'status = %s' in sql
    assert 'j-0001' in params
    assert 'RUNNING' in params


@pytest.mark.parametrize(
    'qs',
    [
        'workspace_id=other',
        'actor_id=x',
        'bogus=1',
        'sort=started_at',
        'limit=101',
        'limit=0',
        'cursor=!!!',
        'direction=sideways',
    ],
)
def test_rejects_out_of_whitelist(qs: str):
    client, connection, _ = client_for([])
    response = client.get(f'/v1/stage-runs?{qs}', headers=READ)
    assert response.status_code == 422
    assert connection.calls == []


def test_missing_session_rejected():
    client, connection, _ = client_for([])
    res_no_cookie = client.get('/v1/stage-runs')
    assert res_no_cookie.status_code == 403
    res_bad_cookie = client.get('/v1/stage-runs', headers={'Cookie': 'cp_session=bad'})
    assert res_bad_cookie.status_code == 403
    assert connection.calls == []


def test_response_has_no_forbidden_columns():
    rows = [stage_row(3), stage_row(2), stage_row(1)]
    client, _, _ = client_for(rows)
    response = client.get('/v1/stage-runs?limit=2', headers=READ)
    text = response.text.lower()
    for forbidden in ('article_body', 'script_text', 'secret', 'payload'):
        assert forbidden not in text


def test_route_inventory():
    _, _, app = client_for([])
    route_pairs: list[tuple[str, str]] = []
    for item in _iter_routes_with_context(app.routes):
        route = item[0] if isinstance(item, tuple) else item
        methods = getattr(route, 'methods', None)
        if methods:
            for m in methods:
                if m not in ('HEAD', 'OPTIONS'):
                    route_pairs.append((m, route.path))

    stage_runs_pairs = {p for p in route_pairs if p[1].startswith('/v1/stage-runs')}
    assert stage_runs_pairs == {('GET', '/v1/stage-runs')}

    for prefix in ('/v1/sources', '/v1/hooks', '/v1/media', '/v1/stage-runs'):
        assert route_pairs.count(('GET', prefix)) == 1

    for name in ('articles', 'events', 'sessions', 'logs', 'capabilities'):
        matching = [p for p in route_pairs if p[1].startswith(f'/v1/{name}')]
        assert matching == []


@pytest.mark.parametrize('name', ['sources', 'hooks', 'media'])
def test_blocked_prefixes_mounted_by_wiring_stay_503(name: str):
    client, connection, _ = client_for([])
    response = client.get(f'/v1/{name}', headers=READ)
    assert response.status_code == 503
    assert response.json()['code'] == 'CAPABILITY_UNAVAILABLE'
    assert connection.calls == []


def test_port_declares_nine_methods():
    for n in NINE:
        assert callable(getattr(ControlApiQueryService, n))
        assert hasattr(ControlQueryPort, n)


def test_blocked_methods_raise_capability_unavailable():
    for n in NINE:
        if n == 'stage_runs':
            continue
        connection = FakeConnection()
        repo = PostgresControlQueries(connection)
        with pytest.raises(CapabilityUnavailableError):
            getattr(repo, n)(
                workspace_id=WORKSPACE,
                query=ListQuery(limit=1, cursor=None, sort_key='created_at', direction='desc', filters=()),
            )
        assert connection.calls == []


def test_registry_accounts_for_nine_resources():
    assert set(queries.LIST_SPECS) == {'stage_runs'}
    assert set(queries.BLOCKED_LIST_RESOURCES) == set(NINE) - {'stage_runs'}
    forbidden_columns = {'payload', 'article_body', 'body', 'script', 'script_text', 'secret', 'secret_value'}
    for spec in queries.LIST_SPECS.values():
        assert not (set(spec.select_columns) & forbidden_columns)


def test_queries_source_is_clean():
    text = QUERIES_PATH.read_text(encoding='utf-8')
    lower_text = text.lower()
    for forbidden in ('limit 100', 'offset', 'payload', 'secret', 'article_body'):
        assert forbidden not in lower_text
    tree = ast.parse(text, filename=str(QUERIES_PATH))
    forbidden_modules = {'source_ingestion', 'ingestion', 'catalog', 'creative', 'voice', 'render'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split('.')[0]
                assert root_module not in forbidden_modules
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_module = node.module.split('.')[0]
            assert root_module not in forbidden_modules
    control_text = CONTROL_PATH.read_text(encoding='utf-8')
    assert re.search(r'query_params[^\n]*workspace_id', control_text) is None