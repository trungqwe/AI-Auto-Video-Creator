"""RS-4: PostgreSQL tests for the read-only media service (module C)."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from catalog.domain.identity import CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus
from catalog.persistence.assets import PostgresMediaAssetRepository
from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.projections.list_query import ListQuery, Page, parse_list_query
from controlplane.infrastructure.read_screens.media import MediaModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'media.py'
ROW_KEYS = {'media_id', 'kind', 'rights_status', 'status', 'revision', 'updated_at'}
FORBIDDEN_KEYS = {'fingerprint', 'discovery_id', 'discovery_ids', 'provenance', 'original_locator', 'payload', 'rights'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'original_locator')
CANARY_LOCATOR = 'https://canary.example/CANARY-LOCATOR'
CANARIES = (CANARY_LOCATOR, 'CANARY-LOCATOR', 'CANARY-DISCOVERY', 'CANARY-SOURCE-REF', 'CANARY-EVIDENCE')
SPEC = {
    'alpha': ('image', True, 'known', 1, '2026-10-03T00:00:00.000000Z'),
    'bravo': ('clip', True, 'unknown', 2, '2026-10-01T00:00:00.000000Z'),
    'charlie': ('audio', False, 'disputed', 1, '2026-10-05T00:00:00.123456Z'),
    'delta': ('image', False, 'unknown', 3, '2026-10-02T00:00:00.000000Z'),
    'echo': ('clip', True, 'known', 1, '2026-10-02T00:00:00.000000Z'),
    'foxtrot': ('image', True, 'disputed', 4, '2026-10-04T00:00:00.000000Z'),
}
OTHER_SPEC = {
    'alpha': ('clip', True, 'unknown', 7, '2026-10-04T12:00:00.000000Z'),
    'zulu': ('audio', False, 'known', 2, '2026-10-06T00:00:00.000000Z'),
}
UPDATED_ASC = ['bravo', 'delta', 'echo', 'alpha', 'foxtrot', 'charlie']
UPDATED_DESC = list(reversed(UPDATED_ASC))
NAME_ASC = sorted(SPEC)
NAME_DESC = list(reversed(NAME_ASC))
ORDERS = {('updated_at', 'asc'): UPDATED_ASC, ('updated_at', 'desc'): UPDATED_DESC, ('name', 'asc'): NAME_ASC, ('name', 'desc'): NAME_DESC}

def fingerprint_of(workspace_id: str, asset_id: str) -> str:
    return hashlib.sha256(f'{workspace_id}/{asset_id}'.encode('utf-8')).hexdigest()


def save_asset(manager: Any, workspace_id: str, asset_id: str, spec: tuple[Any, ...]) -> None:
    kind, fingerprinted, rights, revision, updated_at = spec
    entry = ProvenanceEntry(source_ref='CANARY-SOURCE-REF', article_ref=None, event_ref=None, original_locator=CANARY_LOCATOR, observed_at='2026-10-20T00:00:00Z', relation=ProvenanceRelation.HERO_IMAGE)
    asset = MediaAsset(
        media_asset_id=asset_id,
        kind=MediaKind(kind),
        fingerprint=CanonicalFingerprint(fingerprint_of(workspace_id, asset_id)) if fingerprinted else None,
        provenance=(entry,),
        rights=RightsAssessment(RightsStatus(rights), ('CANARY-EVIDENCE',)),
        index_revision=revision,
    )
    with manager.borrow_connection() as connection:
        PostgresMediaAssetRepository(connection, workspace_id).save(asset, discovery_id=f'CANARY-DISCOVERY-{asset_id}')
        connection.execute(
            'UPDATE controlplane.cp_media_assets SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND media_asset_id = %s',
            (updated_at, workspace_id, asset_id),
        )


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: MediaModuleService


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        for asset_id, spec in SPEC.items():
            save_asset(manager, workspace_id, asset_id, spec)
        for asset_id, spec in OTHER_SPEC.items():
            save_asset(manager, other_workspace_id, asset_id, spec)
        yield Env(manager, workspace_id, other_workspace_id, MediaModuleService(manager.borrow_connection))


def make_row(asset_id: str, spec: tuple[Any, ...]) -> dict[str, Any]:
    kind, fingerprinted, rights, revision, updated_at = spec
    return {'media_id': asset_id, 'kind': kind, 'rights_status': rights, 'status': 'CATALOGED' if fingerprinted else 'DISCOVERED', 'revision': revision, 'updated_at': updated_at}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['updated_at', 'name'], allowed_filters={'kind', 'status'}, default_limit=20, max_limit=100)


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


def ids(page: Page) -> list[str]:
    return [item['media_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [media_id for page in pages for media_id in ids(page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids(page) == UPDATED_DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['media_id']: item for item in page.items} == {key: make_row(key, spec) for key, spec in SPEC.items()}


def test_asset_without_fingerprint_is_discovered(env):
    rows = {item['media_id']: item for item in get_page(env, {}).items}
    assert rows['charlie']['status'] == 'DISCOVERED' and rows['delta']['status'] == 'DISCOVERED'
    assert rows['alpha']['status'] == 'CATALOGED' and rows['bravo']['status'] == 'CATALOGED'
    assert rows['alpha']['rights_status'] == 'known' and rows['charlie']['rights_status'] == 'disputed'


def test_default_direction_is_desc_and_explicit_direction_is_honoured(env):
    assert ids(get_page(env, {})) == UPDATED_DESC
    assert ids(get_page(env, {'sort': 'name'})) == NAME_DESC
    for (sort, direction), expected in ORDERS.items():
        assert ids(get_page(env, {'sort': sort, 'direction': direction})) == expected


def test_name_sort_follows_media_asset_id_not_updated_at(env):
    assert NAME_ASC != UPDATED_ASC
    assert ids(get_page(env, {'sort': 'name', 'direction': 'asc'})) == ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot']


@pytest.mark.parametrize('sort', ['updated_at', 'name'])
@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, sort, direction, limit):
    pages = walk(env, {'sort': sort, 'direction': direction}, limit)
    expected = ORDERS[(sort, direction)]
    assert all_ids(pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 2)
    assert len(pages) == 3
    assert all_ids(pages) == UPDATED_DESC


@pytest.mark.parametrize(
    'params, expected',
    [
        ({'kind': 'image'}, ['foxtrot', 'alpha', 'delta']),
        ({'kind': 'clip'}, ['echo', 'bravo']),
        ({'kind': 'audio'}, ['charlie']),
        ({'status': 'CATALOGED'}, ['foxtrot', 'alpha', 'echo', 'bravo']),
        ({'status': 'DISCOVERED'}, ['charlie', 'delta']),
        ({'kind': 'image', 'status': 'DISCOVERED'}, ['delta']),
        ({'kind': 'audio', 'status': 'CATALOGED'}, []),
        ({'kind': 'video'}, []),
        ({'kind': 'IMAGE'}, []),
        ({'kind': ''}, []),
        ({'status': 'FAILED'}, []),
        ({'status': 'cataloged'}, []),
        ({'status': ''}, []),
    ],
)
def test_filters_are_exact_and_unknown_value_is_empty(env, params, expected):
    page = get_page(env, params)
    assert ids(page) == expected
    assert page.next_cursor is None


def test_filter_paginates_with_name_sort(env):
    pages = walk(env, {'kind': 'image', 'sort': 'name', 'direction': 'asc'}, 2)
    assert len(pages) == 2
    assert all_ids(pages) == ['alpha', 'delta', 'foxtrot']


@pytest.mark.parametrize('name', ['tag', 'availability', 'source_id', 'rights_status'])
def test_unsupported_filter_name_raises_value_error(env, name):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=((name, 'x'),))
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_unsupported_sort_key_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='revision', direction='desc', filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_fetch_one_returns_row_or_none(env):
    assert get_one(env, 'alpha') == make_row('alpha', SPEC['alpha'])
    assert get_one(env, 'charlie') == make_row('charlie', SPEC['charlie'])
    assert get_one(env, 'nope') is None
    assert get_one(env, 'zulu') is None


def test_workspaces_are_isolated(env):
    assert ids(get_page(env, {})) == UPDATED_DESC
    theirs = get_page(env, {}, env.other_workspace_id)
    assert ids(theirs) == ['zulu', 'alpha']
    assert theirs.items[1] == make_row('alpha', OTHER_SPEC['alpha'])
    assert get_one(env, 'alpha')['kind'] == 'image'
    assert get_one(env, 'alpha', env.other_workspace_id)['kind'] == 'clip'
    assert get_one(env, 'zulu') is None
    assert get_one(env, 'bravo', env.other_workspace_id) is None
    assert ids(get_page(env, {'kind': 'clip'}, env.other_workspace_id)) == ['alpha']
    assert ids(get_page(env, {'kind': 'image'}, env.other_workspace_id)) == []
    assert all_ids(walk(env, {'sort': 'name', 'direction': 'asc'}, 1, env.other_workspace_id)) == ['alpha', 'zulu']
    assert 'zulu' not in all_ids(walk(env, {'sort': 'name'}, 1))


def snapshot(env: Env) -> tuple[list[tuple[Any, ...]], int]:
    with env.manager.borrow_connection() as connection:
        assets = connection.execute(
            'SELECT workspace_id::text, media_asset_id, fingerprint, discovery_id, status, revision, payload::text, search_text, updated_at '
            'FROM controlplane.cp_media_assets ORDER BY workspace_id, media_asset_id'
        ).fetchall()
        provenance = connection.execute('SELECT count(*) FROM controlplane.cp_media_provenance').fetchone()[0]
    return (assets, provenance)


def test_reads_do_not_change_source_tables(env):
    before = snapshot(env)
    assert len(before[0]) == 8
    assert before[1] == 8
    get_page(env, {})
    walk(env, {'sort': 'name', 'direction': 'asc'}, 2)
    get_one(env, 'alpha')
    get_one(env, 'nope')
    assert snapshot(env) == before


@pytest.mark.parametrize('item_id', ['alpha', 'charlie', 'nope', 'zulu'])
def test_apply_update_raises_capability_unavailable_and_changes_nothing(env, item_id):
    before = snapshot(env)
    request = rs_support.FakeRequest(env.workspace_id)
    for key in (None, 'k-1'):
        with pytest.raises(CapabilityUnavailableError) as raised:
            env.service.apply_update(request=request, item_id=item_id, expected_revision=1, changes={'notes': 'x'}, idempotency_key=key)
        assert raised.value.capability == 'media'
    with pytest.raises(CapabilityUnavailableError) as raised:
        env.service.apply_update(request=request, item_id=item_id, expected_revision=1, changes={'tags': ['x']})
    assert raised.value.capability == 'media'
    assert snapshot(env) == before


def test_apply_update_signature_matches_route_contract():
    parameters = inspect.signature(MediaModuleService.apply_update).parameters
    assert list(parameters) == ['self', 'request', 'item_id', 'expected_revision', 'changes', 'idempotency_key']
    assert all(parameters[name].kind is inspect.Parameter.KEYWORD_ONLY for name in list(parameters)[1:])
    assert parameters['idempotency_key'].default is None


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize(
    'sort_key, cursor',
    [
        ('updated_at', ('not-a-time', 'alpha')),
        ('updated_at', ('', 'alpha')),
        ('updated_at', ('2026-13-45T01:02:03Z', 'alpha')),
        ('updated_at', ('2026-10-25', 'alpha')),
        ('name', ('2026-10-01T00:00:00.000000Z', 'alpha')),
        ('name', ('alpha', 'bravo')),
        ('name', ('', 'alpha')),
    ],
)
def test_foreign_cursor_raises_value_error(env, direction, sort_key, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key=sort_key, direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        for sort in ('updated_at', 'name'):
            rows.extend(get_page(env, {'sort': sort}, workspace_id).items)
        rows.extend(get_one(env, asset_id, workspace_id) for asset_id in ('alpha', 'charlie'))
    rows = [row for row in rows if row is not None]
    text = json.dumps(rows)
    fingerprints = [fingerprint_of(owner, asset_id) for owner, specs in ((env.workspace_id, SPEC), (env.other_workspace_id, OTHER_SPEC)) for asset_id in specs]
    assert rows
    assert not [token for token in (*CANARIES, *fingerprints) if token in text]
    assert all(not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'capabilityunavailableerror' in lowered
    assert 'cp_media_assets' in lowered
    assert not [fragment for fragment in ('cp_media_provenance', 'm.fingerprint', 'discovery_id') if fragment in lowered]
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert 'controlplane.application.control_api.errors' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
