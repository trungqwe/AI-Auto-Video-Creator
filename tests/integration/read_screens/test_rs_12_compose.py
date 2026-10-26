"""RS-12: PostgreSQL tests for compose_read_screens (ten read-only services over one connection scope)."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.projections.list_query import Page, parse_list_query
from controlplane.infrastructure.read_screens.accounts import AccountModuleService
from controlplane.infrastructure.read_screens.articles import ArticleModuleService
from controlplane.infrastructure.read_screens.artifacts import ArtifactModuleService
from controlplane.infrastructure.read_screens.compose import compose_read_screens
from controlplane.infrastructure.read_screens.cost import CostModuleService
from controlplane.infrastructure.read_screens.events import EventModuleService
from controlplane.infrastructure.read_screens.media import MediaModuleService
from controlplane.infrastructure.read_screens.scripts import ScriptModuleService
from controlplane.infrastructure.read_screens.sessions import SessionModuleService
from controlplane.infrastructure.read_screens.snapshots import SnapshotModuleService
from controlplane.infrastructure.read_screens.story_angles import StoryAngleModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'compose.py'
PACKAGE = 'controlplane.infrastructure.read_screens'
EXPECTED_KEYS = {'articles', 'events', 'media', 'artifacts', 'snapshots', 'story-angles', 'scripts', 'sessions', 'accounts', 'cost'}
UNKNOWN_ID = '00000000-0000-0000-0000-00000000dead'
# key -> (service class, sort key, sibling module)
SPEC = {
    'articles': (ArticleModuleService, 'updated_at', 'articles'),
    'events': (EventModuleService, 'updated_at', 'events'),
    'media': (MediaModuleService, 'updated_at', 'media'),
    'artifacts': (ArtifactModuleService, 'created_at', 'artifacts'),
    'snapshots': (SnapshotModuleService, 'created_at', 'snapshots'),
    'story-angles': (StoryAngleModuleService, 'created_at', 'story_angles'),
    'scripts': (ScriptModuleService, 'created_at', 'scripts'),
    'sessions': (SessionModuleService, 'started_at', 'sessions'),
    'accounts': (AccountModuleService, 'updated_at', 'accounts'),
    'cost': (CostModuleService, 'recorded_at', 'cost'),
}
KEYS = list(SPEC)


class CountingManager:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.borrows = 0

    def borrow_connection(self) -> Any:
        self.borrows += 1
        return self._inner.borrow_connection()


@dataclass(frozen=True)
class Env:
    counting: CountingManager
    workspace_id: str
    borrows_after_compose: int
    services: dict[str, Any]


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, _other_workspace_id):
        counting = CountingManager(manager)
        services = compose_read_screens(counting)
        yield Env(counting, workspace_id, counting.borrows, services)


def make_query(key: str) -> Any:
    sorts = [SPEC[key][1], 'name'] if key == 'media' else [SPEC[key][1]]
    return parse_list_query({}, allowed_sorts=sorts, allowed_filters=set(), default_limit=20, max_limit=100)


def test_compose_returns_exactly_the_ten_keys(env):
    assert set(env.services) == EXPECTED_KEYS
    assert len(env.services) == 10
    assert 'story_angles' not in env.services


@pytest.mark.parametrize('key', KEYS)
def test_service_type_and_connection_scope(env, key):
    assert key in env.services
    service = env.services[key]
    assert type(service) is SPEC[key][0]
    assert service._connection_scope == env.counting.borrow_connection


def test_composing_opens_no_connection(env):
    assert set(env.services) == EXPECTED_KEYS
    assert env.borrows_after_compose == 0
    stub = CountingManager(None)
    assert len(compose_read_screens(stub)) == 10
    assert stub.borrows == 0


@pytest.mark.parametrize('key', KEYS)
def test_fetch_page_on_empty_database_is_empty(env, key):
    assert key in env.services
    before = env.counting.borrows
    request = rs_support.FakeRequest(env.workspace_id, {})
    page = env.services[key].fetch_page(request, env.workspace_id, make_query(key))
    assert isinstance(page, Page)
    assert list(page.items) == []
    assert page.next_cursor is None
    assert env.counting.borrows == before + 1


@pytest.mark.parametrize('key', KEYS)
def test_fetch_one_unknown_id_is_none(env, key):
    assert key in env.services
    request = rs_support.FakeRequest(env.workspace_id)
    assert env.services[key].fetch_one(request, env.workspace_id, UNKNOWN_ID) is None


def test_only_media_has_apply_update(env):
    assert set(env.services) == EXPECTED_KEYS
    assert [key for key, service in env.services.items() if hasattr(service, 'apply_update')] == ['media']
    request = rs_support.FakeRequest(env.workspace_id)
    with pytest.raises(CapabilityUnavailableError) as raised:
        env.services['media'].apply_update(request=request, item_id=UNKNOWN_ID, expected_revision=1, changes={}, idempotency_key=None)
    assert raised.value.capability == 'media'


def test_source_imports_only_sibling_modules():
    text = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(text)
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Import)]
    modules = sorted(node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    siblings = sorted(f'{PACKAGE}.{spec[2]}' for spec in SPEC.values())
    assert [m for m in modules if m not in ('__future__', 'typing')] == siblings
    lowered = text.lower()
    assert not [frag for frag in ('production', 'controlplane.api', 'from src.', 'os.environ') if frag in lowered]
    literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert 'story-angles' in literals and 'story_angles' not in literals
