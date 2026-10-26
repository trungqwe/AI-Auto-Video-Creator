"""RS-8: PostgreSQL tests for the read-only scripts service (module D)."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, ListQueryError, Page, parse_list_query
from controlplane.infrastructure.read_screens.scripts import ScriptModuleService
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.persistence.repositories import PostgresScriptRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'scripts.py'
ROW_KEYS = {'script_id', 'language', 'estimated_duration_seconds', 'revision', 'created_at'}
FORBIDDEN_KEYS = {'segments', 'hook_intent', 'thumbnail_transition', 'pronunciation_hints', 'snapshot_id', 'status', 'speech_rate', 'script_version_id', 'workspace_id', 'payload', 'record_key', 'script_fingerprint'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'segments', 'snapshot_id')
CANARIES = ('CANARY-NARRATION', 'CANARY-HOOK', 'CANARY-THUMBNAIL', 'CANARY-SCENE', 'CANARY-TERM', 'CANARY-SOUND', 'CANARY-DISCLOSURE', 'CANARY-REF')
# W1 seeding groups, one transaction each: (script_version_id, language, estimated_duration_seconds). Creation order differs from id order on purpose; sv-b and sv-d share one transaction, so they share created_at and are ordered by id.
GROUPS = [[('sv-c', 'en', 45.0)], [('sv-a', 'vi', 30.5)], [('sv-b', 'vi', 12.0), ('sv-d', 'en', 60.25)]]
# The other workspace reuses the id sv-a of W1 on purpose.
OTHER_GROUPS = [[('sv-a', 'vi', 99.0)], [('sv-z', 'fr', 20.0)]]
EXPECTED = {key: (language, duration) for group in GROUPS for key, language, duration in group}
OTHER_EXPECTED = {key: (language, duration) for group in OTHER_GROUPS for key, language, duration in group}
ASC = ['sv-c', 'sv-a', 'sv-b', 'sv-d']
DESC = list(reversed(ASC))


def make_script(workspace_id: str, script_id: str, language: str, duration: float) -> ScriptVersion:
    ref = ResourceRef(workspace_id, 'article', 'CANARY-REF', 'rev-1')
    segment = ScriptSegment(
        segment_id=f'seg-{script_id}', order=0, text=f'CANARY-NARRATION {script_id}', claim_mode='inference',
        scene_intent='CANARY-SCENE', source_refs=(ref,), disclosure='CANARY-DISCLOSURE', word_count=2, estimated_seconds=1.0,
    )
    return ScriptVersion(
        script_version_id=script_id, language=language, hook_intent='CANARY-HOOK', thumbnail_transition='CANARY-THUMBNAIL',
        segments=(segment,), pronunciation_hints=({'term': 'CANARY-TERM', 'pronunciation': 'CANARY-SOUND'},),
        speech_rate=2.5, estimated_duration_seconds=duration,
    )


def seed(manager: Any, workspace_id: str, groups: list[Any]) -> None:
    for group in groups:
        with manager.borrow_connection() as connection:
            repository = PostgresScriptRepository(lambda: connection, workspace_id)
            for script_id, language, duration in group:
                repository.append(script_id, 1, make_script(workspace_id, script_id, language, duration))


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: ScriptModuleService
    created: dict[tuple[str, str], str]


def utc(moment: Any) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        seed(manager, workspace_id, GROUPS)
        seed(manager, other_workspace_id, OTHER_GROUPS)
        with manager.borrow_connection() as connection:
            stamps = {(owner, key): moment for owner, key, moment in connection.execute('SELECT workspace_id::text, script_version_id, created_at FROM controlplane.cp_script_versions').fetchall()}
        ordered = [stamps[(workspace_id, key)] for key in ASC]
        assert ordered == sorted(ordered) and len(set(ordered)) == 3 and ordered[2] == ordered[3]
        created = {key: utc(moment) for key, moment in stamps.items()}
        yield Env(manager, workspace_id, other_workspace_id, ScriptModuleService(manager.borrow_connection), created)


def make_row(env: Env, script_id: str, other: bool = False) -> dict[str, Any]:
    language, duration = (OTHER_EXPECTED if other else EXPECTED)[script_id]
    owner = env.other_workspace_id if other else env.workspace_id
    return {'script_id': script_id, 'language': language, 'estimated_duration_seconds': duration, 'revision': 1, 'created_at': env.created[(owner, script_id)]}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['created_at'], allowed_filters={'language'}, default_limit=20, max_limit=100)


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
    return [item['script_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [script_id for page in pages for script_id in ids_of(page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids_of(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['script_id']: item for item in page.items} == {key: make_row(env, key) for key in ASC}


def test_duration_is_a_number_and_revision_is_the_stored_revision(env):
    for item in get_page(env, {}).items:
        assert type(item['estimated_duration_seconds']) is float
        assert item['revision'] == 1 and type(item['revision']) is int
        assert item['created_at'].endswith('Z')


def test_order_follows_created_at_not_record_key(env):
    ascending = ids_of(get_page(env, {'direction': 'asc'}))
    assert ascending == ASC
    assert ascending != sorted(ASC)
    assert ids_of(get_page(env, {})) == DESC
    assert ids_of(get_page(env, {'sort': 'created_at'})) == DESC
    assert ids_of(get_page(env, {'direction': 'desc'})) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('limit', [1, 2, 3])
def test_cursor_pagination_has_no_duplicates_or_gaps(env, direction, limit):
    pages = walk(env, {'direction': direction}, limit)
    expected = ASC if direction == 'asc' else DESC
    assert all_ids(pages) == expected
    assert len(pages) == -(-len(expected) // limit)
    assert all(len(page.items) == limit and page.next_cursor is not None for page in pages[:-1])
    assert pages[-1].next_cursor is None


def test_default_pagination_is_newest_first(env):
    pages = walk(env, {}, 2)
    assert len(pages) == 2
    assert all_ids(pages) == DESC


@pytest.mark.parametrize('language, expected', [('en', ['sv-d', 'sv-c']), ('vi', ['sv-b', 'sv-a']), ('fr', []), ('xx', []), ('', []), ('EN', [])])
def test_language_filter_exact_match_and_unknown_value_is_empty(env, language, expected):
    page = get_page(env, {'language': language})
    assert ids_of(page) == expected
    assert page.next_cursor is None


def test_language_filter_paginates_both_ways(env):
    pages = walk(env, {'language': 'vi', 'direction': 'asc'}, 1)
    assert len(pages) == 2
    assert all_ids(pages) == ['sv-a', 'sv-b']
    pages = walk(env, {'language': 'en'}, 1)
    assert len(pages) == 2
    assert all_ids(pages) == ['sv-d', 'sv-c']


def test_fetch_one_returns_row_or_none(env):
    for key in ASC:
        assert get_one(env, key) == make_row(env, key)
    for missing in ('sv-', 'SV-A', 'sv-a ', 'nope', '', 'sv-z'):
        assert get_one(env, missing) is None
    assert get_one(env, 'sv-c', env.other_workspace_id) is None
    assert get_one(env, 'sv-z', env.other_workspace_id) == make_row(env, 'sv-z', other=True)
    assert get_one(env, 'sv-a', env.other_workspace_id) == make_row(env, 'sv-a', other=True)


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    theirs = get_page(env, {}, other)
    assert ids_of(theirs) == ['sv-z', 'sv-a']
    assert list(theirs.items) == [make_row(env, 'sv-z', other=True), make_row(env, 'sv-a', other=True)]
    assert all_ids(walk(env, {'direction': 'asc'}, 1, other)) == ['sv-a', 'sv-z']
    mine = get_page(env, {})
    assert ids_of(mine) == DESC
    assert not [item for item in mine.items if item['estimated_duration_seconds'] in (99.0, 20.0)]
    assert ids_of(get_page(env, {'language': 'fr'})) == []
    assert ids_of(get_page(env, {'language': 'fr'}, other)) == ['sv-z']
    assert get_one(env, 'sv-a')['estimated_duration_seconds'] == 30.5
    assert get_one(env, 'sv-a', other)['estimated_duration_seconds'] == 99.0


def test_unsupported_filter_and_sort_raise_value_error(env):
    for name in ('status', 'script_id', 'snapshot_id', 'workspace_id'):
        query = ListQuery(limit=5, cursor=None, sort_key='created_at', direction='desc', filters=((name, 'x'),))
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    for sort_key in ('record_key', 'updated_at'):
        query = ListQuery(limit=5, cursor=None, sort_key=sort_key, direction='desc', filters=())
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)
    with pytest.raises(ListQueryError):
        make_query({'status': 'x'})


def table_state(env: Env) -> list[Any]:
    with env.manager.borrow_connection() as connection:
        return connection.execute('SELECT workspace_id::text, record_key, revision, script_version_id, payload::text, created_at FROM controlplane.cp_script_versions ORDER BY workspace_id, record_key, revision').fetchall()


def test_reads_do_not_change_the_table(env):
    before = table_state(env)
    assert len(before) == 6
    get_page(env, {})
    get_page(env, {'language': 'vi'})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'sv-a')
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('sv-a', 'sv-a')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='created_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, key, workspace_id) for key in (*ASC, 'sv-z'))
    rows = [row for row in rows if row is not None]
    # script_fingerprint is derived from the narration and is not a stored column, so take it from the domain objects that were seeded.
    fingerprints = [make_script(owner, key, language, duration).script_fingerprint for owner, groups in ((env.workspace_id, GROUPS), (env.other_workspace_id, OTHER_GROUPS)) for group in groups for key, language, duration in group]
    text = json.dumps(rows)
    assert rows and len(fingerprints) == 6
    assert not [token for token in (*CANARIES, *fingerprints) if token in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'cp_script_versions' in lowered and 'script_version_id' in lowered and "payload->>'language'" in lowered
    assert 'record_key' not in lowered and 'created_at' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
