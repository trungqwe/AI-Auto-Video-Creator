"""CP-4-WIRING-FIX3: mười route đọc của route_catalog, dùng service giả, không cần PostgreSQL."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient
import pytest

from controlplane.api.main import create_app
import controlplane.application.control_api.route_catalog as route_catalog
from controlplane.application.projections.list_query import Page

WORKSPACE = '00000000-0000-0000-0000-0000000004c1'
ORIGIN = 'https://localhost:8443'
READ = {'Cookie': 'cp_session=valid'}
EXPECTED = {
    'articles': (('updated_at',), {'source_id'}),
    'events': (('updated_at',), {'status'}),
    'media': (('updated_at', 'name'), {'kind', 'status'}),
    'artifacts': (('created_at',), {'kind', 'state'}),
    'snapshots': (('created_at',), {'job_id'}),
    'story-angles': (('created_at',), set()),
    'scripts': (('created_at',), {'language'}),
    'sessions': (('started_at',), {'status'}),
    'accounts': (('updated_at',), {'provider', 'status'}),
    'cost': (('recorded_at',), {'provider', 'job_id'}),
}


class FakeUow:
    def __init__(self) -> None:
        self.connection = object()

    def __enter__(self) -> FakeUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeManager:
    def unit_of_work(self) -> FakeUow:
        return FakeUow()

    @contextmanager
    def borrow_connection(self):
        yield object()


class FakeSessionService:
    def resolve(self, *, connection: object, token: str) -> dict[str, str]:
        if token == 'valid':
            return {'workspace_id': WORKSPACE, 'actor_id': '00000000-0000-0000-0000-0000000004c2', 'session_id': '00000000-0000-0000-0000-0000000004c3'}
        raise PermissionError('invalid session token')


class RecordingService:
    def __init__(self, name: str) -> None:
        self.name = name

    def fetch_page(self, request: object, workspace_id: str, query: object) -> Page:
        return Page(items=({'id': 'x1', 'name': self.name},), next_cursor='cur-1')

    def fetch_one(self, request: object, workspace_id: str, item_id: str) -> dict[str, str] | None:
        if item_id == 'missing':
            return None
        return {'id': item_id, 'name': self.name}


def make_client(services: dict[str, object]) -> TestClient:
    app = create_app(manager=FakeManager(), allowed_origins={ORIGIN})
    app.state.session_service = FakeSessionService()
    app.state.module_services = services
    return TestClient(app, base_url=ORIGIN, raise_server_exceptions=False)


def test_catalog_matches_plan_table():
    by_name = {r.name: r for r in route_catalog.LISTING_RESOURCES}
    for name, (sorts, filters) in EXPECTED.items():
        resource = by_name[name]
        assert resource.prefix == f'/v1/{name}'
        assert resource.allowed_sorts == sorts
        assert resource.allowed_filters == frozenset(filters)
        assert (resource.default_limit, resource.max_limit, resource.with_detail) == (50, 100, True)
    assert {r.name for r in route_catalog.METADATA_RESOURCES} == {'sources', 'hooks', 'media'}


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_list_and_detail_with_service(name: str):
    client = make_client({name: RecordingService(name)})
    listing = client.get(f'/v1/{name}', headers=READ)
    assert listing.status_code == 200
    body = listing.json()
    assert set(body) == {'items', 'next_cursor'}
    assert body['items'] == [{'id': 'x1', 'name': name}]
    found = client.get(f'/v1/{name}/x1', headers=READ)
    assert found.status_code == 200
    assert found.json()['id'] == 'x1'
    missing = client.get(f'/v1/{name}/missing', headers=READ)
    assert missing.status_code == 404
    assert missing.json()['code'] == 'NOT_FOUND'


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_without_service_is_503(name: str):
    client = make_client({})
    for path in (f'/v1/{name}', f'/v1/{name}/x1'):
        response = client.get(path, headers=READ)
        assert response.status_code == 503
        assert response.json()['code'] == 'CAPABILITY_UNAVAILABLE'


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_filters_follow_catalog(name: str):
    client = make_client({name: RecordingService(name)})
    for field in sorted(EXPECTED[name][1]):
        assert client.get(f'/v1/{name}?{field}=v', headers=READ).status_code == 200
    assert client.get(f'/v1/{name}?bogus=v', headers=READ).status_code == 422


def test_media_rejects_removed_filters():
    client = make_client({'media': RecordingService('media')})
    for field in ('tag', 'availability'):
        assert client.get(f'/v1/media?{field}=v', headers=READ).status_code == 422


def test_story_angles_has_no_filter():
    client = make_client({'story-angles': RecordingService('story-angles')})
    assert client.get('/v1/story-angles?status=v', headers=READ).status_code == 422


def test_logs_and_capabilities_have_no_route():
    client = make_client({n: RecordingService(n) for n in EXPECTED})
    for path in ('/v1/logs', '/v1/logs/x1', '/v1/capabilities'):
        assert client.get(path, headers=READ).status_code == 404
