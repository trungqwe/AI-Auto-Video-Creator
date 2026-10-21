"""H-08: router liệt kê chỉ đọc, workspace lấy từ identity (CT-API-001, CT-API-002, CT-API-010).

coveredIds: CT-API-001, CT-API-002, CT-API-010
"""
import ast
import inspect
import pathlib

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from controlplane.api.routes.modules.problem_detail import problem_body
from controlplane.api.routes.modules.read_only_listing import build_listing_router
from controlplane.application.projections.list_query import ListQuery, Page, encode_cursor

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'modules' / 'read_only_listing.py'
PREFIX = '/v1/widgets'
WORKSPACE = 'ws-identity-0001'
CORRELATION_ID = 'corr-h08-0001'
ITEM = {'id': 'a', 'name': 'alpha'}


class Recorder:
    def __init__(self, page=None, one=None):
        self.page = Page(items=(dict(ITEM),), next_cursor=None) if page is None else page
        self.one = one
        self.page_calls = []
        self.one_calls = []

    def fetch_page(self, request, workspace_id, query):
        self.page_calls.append((workspace_id, query))
        return self.page

    def fetch_one(self, request, workspace_id, item_id):
        self.one_calls.append((workspace_id, item_id))
        return self.one


def router_kwargs(recorder, **overrides):
    kwargs = {'prefix': PREFIX, 'fetch_page': recorder.fetch_page, 'allowed_sorts': ['name', 'id'], 'allowed_filters': ['status'], 'default_limit': 20, 'max_limit': 100}
    kwargs.update(overrides)
    return kwargs


def make_client(recorder, **overrides):
    app = FastAPI()

    @app.middleware('http')
    async def identity_middleware(request: Request, call_next):
        request.state.identity = {'workspace_id': WORKSPACE, 'actor_id': 'actor-1'}
        request.state.correlation_id = CORRELATION_ID
        return await call_next(request)

    app.include_router(build_listing_router(**router_kwargs(recorder, **overrides)))
    return TestClient(app, raise_server_exceptions=False)


def test_valid_query_calls_fetch_page_once_with_identity_workspace():
    cursor = encode_cursor('beta', 'b')
    recorder = Recorder(page=Page(items=(dict(ITEM),), next_cursor=cursor))
    response = make_client(recorder).get(PREFIX, params={'limit': '5', 'sort': 'name', 'direction': 'desc', 'status': 'active'})
    assert response.status_code == 200
    assert response.json() == {'items': [ITEM], 'next_cursor': cursor}
    assert len(recorder.page_calls) == 1
    workspace_id, query = recorder.page_calls[0]
    assert workspace_id == WORKSPACE
    assert query == ListQuery(limit=5, cursor=None, sort_key='name', direction='desc', filters=(('status', 'active'),))


def test_default_query_uses_defaults_and_null_cursor():
    recorder = Recorder()
    response = make_client(recorder).get(PREFIX)
    assert response.status_code == 200
    assert response.json() == {'items': [ITEM], 'next_cursor': None}
    assert recorder.page_calls == [(WORKSPACE, ListQuery(limit=20, cursor=None, sort_key='name', direction='asc', filters=()))]


def test_cursor_param_is_decoded_into_query():
    recorder = Recorder()
    response = make_client(recorder).get(PREFIX, params={'cursor': encode_cursor('beta', 'b')})
    assert response.status_code == 200
    assert len(recorder.page_calls) == 1
    assert recorder.page_calls[0][1].cursor == ('beta', 'b')


def test_empty_page_returns_empty_items_and_null_cursor():
    recorder = Recorder(page=Page(items=(), next_cursor=None))
    response = make_client(recorder).get(PREFIX)
    assert response.status_code == 200
    assert response.json() == {'items': [], 'next_cursor': None}


def assert_validation_problem(response, field_errors):
    assert response.status_code == 422
    assert response.headers['content-type'].split(';')[0] == 'application/problem+json'
    assert response.json() == problem_body('VALIDATION_FAILED', correlation_id=CORRELATION_ID, field_errors=field_errors)


@pytest.mark.parametrize('params', [{'workspace_id': 'other'}, {'workspace_id': WORKSPACE}, {'actor_id': 'actor-2'}])
def test_identity_fields_in_query_are_rejected_and_fake_not_called(params):
    recorder = Recorder()
    response = make_client(recorder).get(PREFIX, params=params)
    (name,) = params
    assert_validation_problem(response, {name: 'filter_not_allowed'})
    assert recorder.page_calls == []


def test_workspace_filter_is_rejected_even_when_listed_as_allowed():
    recorder = Recorder()
    client = make_client(recorder, allowed_filters=['status', 'workspace_id'])
    assert_validation_problem(client.get(PREFIX, params={'workspace_id': 'other'}), {'workspace_id': 'filter_not_allowed'})
    assert recorder.page_calls == []


@pytest.mark.parametrize(('params', 'field', 'code'), [
    ({'limit': '1000'}, 'limit', 'limit_invalid'),
    ({'limit': '0'}, 'limit', 'limit_invalid'),
    ({'limit': 'abc'}, 'limit', 'limit_invalid'),
    ({'sort': 'secret'}, 'sort', 'sort_not_allowed'),
    ({'direction': 'up'}, 'direction', 'sort_not_allowed'),
    ({'cursor': '!!'}, 'cursor', 'cursor_invalid'),
    ({'unknown': '1'}, 'unknown', 'filter_not_allowed'),
])
def test_invalid_list_params_return_422_problem_without_calling_fake(params, field, code):
    recorder = Recorder()
    response = make_client(recorder).get(PREFIX, params=params)
    assert_validation_problem(response, {field: code})
    assert recorder.page_calls == []


@pytest.mark.parametrize('with_fetch_one', [False, True])
def test_every_route_is_get_only(with_fetch_one):
    recorder = Recorder()
    extra = {'fetch_one': recorder.fetch_one} if with_fetch_one else {}
    router = build_listing_router(**router_kwargs(recorder, **extra))
    expected = [PREFIX, PREFIX + '/{item_id}'] if with_fetch_one else [PREFIX]
    assert [route.path for route in router.routes] == expected
    for route in router.routes:
        assert isinstance(route, APIRoute)
        assert set(route.methods) - {'HEAD'} == {'GET'}


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_write_methods_return_405_without_calling_fakes(method):
    recorder = Recorder(one=dict(ITEM))
    client = make_client(recorder, fetch_one=recorder.fetch_one)
    for path in (PREFIX, PREFIX + '/a'):
        response = client.request(method, path, json={'name': 'x'})
        assert response.status_code == 405
    assert recorder.page_calls == []
    assert recorder.one_calls == []


def test_fetch_one_returns_item_with_identity_workspace_ignoring_query():
    recorder = Recorder(one=dict(ITEM))
    client = make_client(recorder, fetch_one=recorder.fetch_one)
    response = client.get(PREFIX + '/a', params={'workspace_id': 'other'})
    assert response.status_code == 200
    assert response.json() == ITEM
    assert recorder.one_calls == [(WORKSPACE, 'a')]
    assert recorder.page_calls == []


def test_fetch_one_none_returns_404_problem_with_body():
    recorder = Recorder(one=None)
    response = make_client(recorder, fetch_one=recorder.fetch_one).get(PREFIX + '/missing')
    assert response.status_code == 404
    assert response.headers['content-type'].split(';')[0] == 'application/problem+json'
    assert response.content
    assert response.json() == problem_body('NOT_FOUND', correlation_id=CORRELATION_ID)
    assert recorder.one_calls == [(WORKSPACE, 'missing')]


def test_item_route_is_absent_without_fetch_one():
    recorder = Recorder()
    response = make_client(recorder).get(PREFIX + '/a')
    assert response.status_code == 404
    assert recorder.page_calls == []
    assert recorder.one_calls == []


def test_fetch_page_exception_returns_500_without_leaking_detail():
    def boom(request, workspace_id, query):
        raise RuntimeError('secret-detail-h08')

    response = make_client(Recorder(), fetch_page=boom).get(PREFIX)
    assert response.status_code == 500
    assert 'secret-detail-h08' not in response.text
    assert 'Traceback' not in response.text


def test_fetch_one_exception_returns_500_without_leaking_detail():
    def boom(request, workspace_id, item_id):
        raise RuntimeError('secret-detail-h08')

    response = make_client(Recorder(), fetch_one=boom).get(PREFIX + '/a')
    assert response.status_code == 500
    assert 'secret-detail-h08' not in response.text
    assert 'Traceback' not in response.text


@pytest.mark.parametrize('prefix', ['/api/x', '/v2/x', 'v1/x', '/v1', '', '/V1/x', None, 5])
def test_unversioned_prefix_is_rejected(prefix):
    with pytest.raises(ValueError) as excinfo:
        build_listing_router(**router_kwargs(Recorder(), prefix=prefix))
    assert excinfo.value.args == ('prefix_must_be_versioned',)


@pytest.mark.parametrize('overrides', [{'default_limit': 0}, {'default_limit': 200}, {'max_limit': 0}, {'allowed_sorts': []}, {'allowed_sorts': 'name'}, {'allowed_filters': 'status'}])
def test_invalid_listing_config_fails_at_build_time(overrides):
    with pytest.raises(ValueError):
        build_listing_router(**router_kwargs(Recorder(), **overrides))


def test_builder_signature_is_keyword_only():
    params = inspect.signature(build_listing_router).parameters
    assert list(params) == ['prefix', 'fetch_page', 'allowed_sorts', 'allowed_filters', 'default_limit', 'max_limit', 'fetch_one']
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values())
    assert params['fetch_one'].default is None
    for name in list(params)[:-1]:
        assert params[name].default is inspect.Parameter.empty


def test_modules_directory_is_declared_package():
    assert MODULE_PATH.parent.is_dir()
    assert (MODULE_PATH.parent / '__init__.py').is_file()


def test_module_source_has_no_write_route_body_access_or_broad_except():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & {'post', 'put', 'patch', 'delete', 'api_route', 'route', 'websocket', 'body', 'json', 'form', 'stream'}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {'Body', 'Form', 'File', 'UploadFile'}
    methods = [kw.value for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_api_route' for kw in n.keywords if kw.arg == 'methods']
    assert len(methods) == 2
    assert all(ast.literal_eval(m) == ['GET'] for m in methods)
    assert [ast.unparse(n.type) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)] == ['ListQueryError']