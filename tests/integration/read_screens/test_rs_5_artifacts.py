"""RS-5: PostgreSQL tests for the read-only artifacts service (module I)."""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import uuid
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, Page, parse_list_query
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.read_screens.artifacts import ArtifactModuleService

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'artifacts.py'
ROW_KEYS = {'artifact_id', 'version', 'state', 'kind', 'created_at'}
FORBIDDEN_KEYS = {'sha256_hash', 'owner_ref', 'provider_object_ref', 'logical_locator', 'verification_evidence_ref', 'artifact_version_id', 'workspace_id'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'provider_object_ref', 'logical_locator', 'sha256_hash', 'owner_ref', 'verification_evidence_ref')
CANARIES = ('CANARY-LOCATOR', 'CANARY-OBJECT', 'CANARY-OWNER', 'CANARY-EVIDENCE')
LO_ID = '00000000-0000-4000-8000-0000000000a1'
HI_ID = 'ffffffff-0000-4000-8000-0000000000a2'
TIE_1 = '00000000-0000-4000-8000-0000000000f1'
TIE_2 = '00000000-0000-4000-8000-0000000000f2'
# (key, artifact_id, kind, fixed version id, [(location state, pinned updated_at, fixed location id)])
SPEC = [
    ('v1', 'art-alpha', 'rendered_video', None, [('CORRUPT', '2026-10-02T00:00:00Z', None), ('VERIFIED', '2026-10-01T00:00:00Z', None)]),
    ('v2', 'art-alpha', 'rendered_video', None, [('DECLARED', '2026-10-01T00:00:00Z', None), ('VERIFIED', '2026-10-03T00:00:00Z', None)]),
    ('v3', 'art-bravo', 'thumbnail', None, [('VERIFIED', '2026-10-02T00:00:00Z', None)]),
    ('v4', 'art-charlie', 'subtitle', None, []),
    ('v5', 'art-delta', 'rendered_video', None, [('AVAILABLE_UNVERIFIED', '2026-10-04T00:00:00Z', HI_ID), ('MATERIALIZING', '2026-10-04T00:00:00Z', LO_ID)]),
    ('v6', 'art-echo', 'thumbnail', TIE_1, [('VERIFIED', '2026-10-05T00:00:00Z', None)]),
    ('v7', 'art-foxtrot', 'rendered_video', TIE_2, []),
]
OTHER_SPEC = [
    ('w1', 'art-alpha', 'rendered_video', None, [('VERIFIED', '2026-10-06T00:00:00Z', None)]),
    ('w2', 'art-zulu', 'thumbnail', None, []),
]
# v6 and v7 share one transaction, so they share created_at and are ordered by version id.
GROUPS = [SPEC[0:1], SPEC[1:2], SPEC[2:3], SPEC[3:4], SPEC[4:5], SPEC[5:7]]
OTHER_GROUPS = [OTHER_SPEC[0:1], OTHER_SPEC[1:2]]
ASC = [entry[0] for entry in SPEC]
DESC = list(reversed(ASC))
STATE = {'v1': 'CORRUPT', 'v2': 'VERIFIED', 'v3': 'VERIFIED', 'v4': None, 'v5': 'AVAILABLE_UNVERIFIED', 'v6': 'VERIFIED', 'v7': None, 'w1': 'VERIFIED', 'w2': None}
META = {entry[0]: (entry[1], entry[2]) for entry in (*SPEC, *OTHER_SPEC)}


COUNTER = itertools.count(1)


def add_location(repository: Any, connection: Any, workspace_id: str, version_id: str, number: int, state: str, updated_at: str, fixed_id: str | None) -> None:
    location = repository.insert_location(
        fixed_id or str(uuid.uuid4()),
        {
            'workspace_id': workspace_id,
            'artifact_version_id': version_id,
            'backend_ref': 'local-disk',
            'provider_namespace_ref': 'ns-rs5',
            'provider_object_ref': f'CANARY-OBJECT-{number}',
            'logical_locator': f'loc/CANARY-LOCATOR-{number}',
        },
    )
    assert location is not None
    if state != 'DECLARED':
        location = repository.update_location(location, location.revision, ArtifactLocationState(state), 'CANARY-EVIDENCE')
        assert location is not None and location.state.value == state
    connection.execute(
        'UPDATE controlplane.cp_artifact_locations SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND location_id = %s::uuid',
        (updated_at, workspace_id, location.location_id),
    )


def seed_group(manager: Any, workspace_id: str, group: list[Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    with manager.borrow_connection() as connection:
        repository = PostgresStorageMetaRepository(connection)
        for key, artifact_id, kind, fixed_id, locations in group:
            number = next(COUNTER)
            version_id = fixed_id or str(uuid.uuid4())
            version = repository.insert_version(
                version_id,
                {
                    'workspace_id': workspace_id,
                    'artifact_id': artifact_id,
                    'sha256_hash': hashlib.sha256(f'{workspace_id}/{artifact_id}/{number}'.encode('utf-8')).hexdigest(),
                    'size_bytes': 1024,
                    'mime_type': 'video/mp4',
                    'artifact_kind': kind,
                    'owner_ref': f'CANARY-OWNER-{number}',
                    'retention_ref': 'retention-rs5',
                    'sensitivity_ref': 'internal',
                },
            )
            assert version is not None
            ids[key] = version_id
            for state, updated_at, fixed_location_id in locations:
                add_location(repository, connection, workspace_id, version_id, next(COUNTER), state, updated_at, fixed_location_id)
    return ids


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: ArtifactModuleService
    ids: dict[str, str]
    keys: dict[str, str]
    created: dict[str, str]


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        ids: dict[str, str] = {}
        for group in GROUPS:
            ids.update(seed_group(manager, workspace_id, group))
        for group in OTHER_GROUPS:
            ids.update(seed_group(manager, other_workspace_id, group))
        with manager.borrow_connection() as connection:
            stamps = dict(connection.execute('SELECT artifact_version_id::text, created_at FROM controlplane.cp_artifact_versions').fetchall())
        ordered = [stamps[ids[key]] for key in ASC]
        assert ordered == sorted(ordered) and len(set(ordered)) == 6 and ordered[5] == ordered[6]
        created = {version_id: moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ') for version_id, moment in stamps.items()}
        yield Env(manager, workspace_id, other_workspace_id, ArtifactModuleService(manager.borrow_connection), ids, {version_id: key for key, version_id in ids.items()}, created)


def make_row(env: Env, key: str) -> dict[str, Any]:
    artifact_id, kind = META[key]
    version_id = env.ids[key]
    return {'artifact_id': artifact_id, 'version': version_id, 'state': STATE[key], 'kind': kind, 'created_at': env.created[version_id]}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['created_at'], allowed_filters={'kind', 'state'}, default_limit=20, max_limit=100)


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


def keys_of(env: Env, page: Page) -> list[str]:
    return [env.keys[item['version']] for item in page.items]


def all_keys(env: Env, pages: list[Page]) -> list[str]:
    return [key for page in pages for key in keys_of(env, page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert keys_of(env, page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {env.keys[item['version']]: item for item in page.items} == {key: make_row(env, key) for key in ASC}


def test_each_version_is_one_row_even_with_several_locations(env):
    page = get_page(env, {'direction': 'asc'})
    versions = [item['version'] for item in page.items]
    assert len(versions) == len(set(versions)) == len(ASC)
    assert keys_of(env, page) == ASC
    assert [item['artifact_id'] for item in page.items].count('art-alpha') == 2


def test_state_is_taken_from_the_most_recently_updated_location(env):
    rows = {env.keys[item['version']]: item for item in get_page(env, {}).items}
    assert rows['v1']['state'] == 'CORRUPT'
    assert rows['v2']['state'] == 'VERIFIED'
    assert rows['v5']['state'] == 'AVAILABLE_UNVERIFIED'
    assert rows['v4']['state'] is None and rows['v7']['state'] is None


def test_default_direction_is_desc_and_explicit_direction_is_honoured(env):
    assert keys_of(env, get_page(env, {})) == DESC
    assert keys_of(env, get_page(env, {'sort': 'created_at'})) == DESC
    assert keys_of(env, get_page(env, {'direction': 'asc'})) == ASC
    assert keys_of(env, get_page(env, {'direction': 'desc'})) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, limit):
    pages = walk(env, {'direction': direction}, limit)
    expected = ASC if direction == 'asc' else DESC
    assert all_keys(env, pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 2)
    assert len(pages) == 4
    assert all_keys(env, pages) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_filtered_pagination_has_no_duplicates_or_gaps(env, direction):
    expected = ['v1', 'v2', 'v5', 'v7']
    pages = walk(env, {'kind': 'rendered_video', 'direction': direction}, 1)
    assert len(pages) == 4
    assert all_keys(env, pages) == (expected if direction == 'asc' else expected[::-1])
    pages = walk(env, {'state': 'VERIFIED', 'direction': direction}, 2)
    assert len(pages) == 2
    assert all_keys(env, pages) == (['v2', 'v3', 'v6'] if direction == 'asc' else ['v6', 'v3', 'v2'])


@pytest.mark.parametrize(
    'params, expected',
    [
        ({'state': 'VERIFIED'}, ['v6', 'v3', 'v2']),
        ({'state': 'CORRUPT'}, ['v1']),
        ({'state': 'AVAILABLE_UNVERIFIED'}, ['v5']),
        ({'state': 'DECLARED'}, []),
        ({'state': 'MATERIALIZING'}, []),
        ({'kind': 'rendered_video'}, ['v7', 'v5', 'v2', 'v1']),
        ({'kind': 'thumbnail'}, ['v6', 'v3']),
        ({'kind': 'subtitle'}, ['v4']),
        ({'kind': 'rendered_video', 'state': 'VERIFIED'}, ['v2']),
        ({'kind': 'thumbnail', 'state': 'VERIFIED'}, ['v6', 'v3']),
        ({'kind': 'subtitle', 'state': 'VERIFIED'}, []),
        ({'kind': 'nope'}, []),
        ({'kind': 'RENDERED_VIDEO'}, []),
        ({'kind': ''}, []),
        ({'state': 'verified'}, []),
        ({'state': 'BOGUS'}, []),
        ({'state': ''}, []),
    ],
)
def test_filters_are_exact_and_unknown_value_is_empty(env, params, expected):
    page = get_page(env, params)
    assert keys_of(env, page) == expected
    assert page.next_cursor is None


@pytest.mark.parametrize('name', ['owner_ref', 'artifact_kind', 'sha256_hash', 'artifact_id', 'location'])
def test_unsupported_filter_name_raises_value_error(env, name):
    query = ListQuery(limit=5, cursor=None, sort_key='created_at', direction='desc', filters=((name, 'x'),))
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_unsupported_sort_key_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_fetch_one_returns_row_or_none(env):
    assert get_one(env, env.ids['v1']) == make_row(env, 'v1')
    assert get_one(env, env.ids['v4']) == make_row(env, 'v4')
    assert get_one(env, env.ids['v4'])['state'] is None
    assert get_one(env, str(uuid.uuid4())) is None
    assert get_one(env, 'nope') is None
    assert get_one(env, env.ids['w1']) is None
    assert get_one(env, env.ids['v1'], env.other_workspace_id) is None


def test_workspaces_are_isolated(env):
    assert keys_of(env, get_page(env, {})) == DESC
    theirs = get_page(env, {}, env.other_workspace_id)
    assert keys_of(env, theirs) == ['w2', 'w1']
    assert list(theirs.items) == [make_row(env, 'w2'), make_row(env, 'w1')]
    assert keys_of(env, get_page(env, {'state': 'VERIFIED'}, env.other_workspace_id)) == ['w1']
    assert keys_of(env, get_page(env, {'kind': 'thumbnail'}, env.other_workspace_id)) == ['w2']
    assert keys_of(env, get_page(env, {'kind': 'subtitle'}, env.other_workspace_id)) == []
    assert all_keys(env, walk(env, {'direction': 'asc'}, 1, env.other_workspace_id)) == ['w1', 'w2']
    assert not {'w1', 'w2'} & set(all_keys(env, walk(env, {}, 1)))


def snapshot(env: Env) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    with env.manager.borrow_connection() as connection:
        versions = connection.execute(
            'SELECT workspace_id::text, artifact_version_id::text, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, created_at '
            'FROM controlplane.cp_artifact_versions ORDER BY workspace_id, artifact_version_id'
        ).fetchall()
        locations = connection.execute(
            'SELECT workspace_id::text, location_id::text, artifact_version_id::text, state, revision, verification_evidence_ref, updated_at '
            'FROM controlplane.cp_artifact_locations ORDER BY workspace_id, location_id'
        ).fetchall()
    return (versions, locations)


def test_reads_do_not_change_source_tables(env):
    before = snapshot(env)
    assert len(before[0]) == 9 and len(before[1]) == 9
    get_page(env, {})
    walk(env, {'direction': 'asc'}, 2)
    get_page(env, {'state': 'VERIFIED'})
    get_one(env, env.ids['v1'])
    get_one(env, 'nope')
    assert snapshot(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('v1', 'v1')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='created_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, env.ids[key], workspace_id) for key in ('v1', 'v2', 'v5', 'w1'))
    rows = [row for row in rows if row is not None]
    versions, locations = snapshot(env)
    tokens = [*CANARIES, *(record[3] for record in versions), *(record[7] for record in versions), *(record[1] for record in locations)]
    text = json.dumps(rows)
    assert rows
    assert not [token for token in tokens if token in text]
    assert all(not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'left join lateral' in lowered
    assert 'order by l.updated_at desc, l.location_id desc limit 1' in lowered
    assert 'cp_artifact_versions' in lowered and 'cp_artifact_locations' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
