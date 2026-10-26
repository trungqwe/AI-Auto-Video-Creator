"""RS-7: PostgreSQL tests for the read-only story angles service (module D)."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, ListQueryError, Page, parse_list_query
from controlplane.infrastructure.read_screens.story_angles import StoryAngleModuleService
from creative.domain.analysis import parse_content_analysis
from creative.domain.angles import StoryAngle, build_story_angle_set
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.snapshot import build_production_snapshot
from creative.persistence.repositories import PostgresAnalysisRepository, PostgresAngleSetRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'story_angles.py'
ROW_KEYS = {'angle_id', 'snapshot_id', 'title', 'suitability', 'created_at'}
FORBIDDEN_KEYS = {'summary', 'narrative_question', 'evidence_refs', 'focus_entities', 'timeframe', 'workspace_id', 'payload', 'set_id', 'distinction_fingerprint'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'evidence_refs')
CANARIES = ('CANARY-SUMMARY', 'CANARY-QUESTION', 'CANARY-ENTITY', 'CANARY-EVIDENCE', 'CANARY-FACT')
# W1 sets in seeding order: (set_id, analysis_id, analysis_revision, [(angle_id, title, suitability)]); one transaction per set.
SETS = [
    ('set-a', 'an-1', 1, [('a-1', 'Title A1', 'high'), ('a-2', 'Title A2', 'medium')]),
    ('set-b', 'an-2', 1, [('b-1', 'Title B1', 'low')]),
    ('set-c', 'an-leak', 1, [('c-1', 'Title C1', 'high')]),
    ('set-d', 'an-1', 3, [('d-1', 'Title D1', 'medium')]),
]
# The other workspace reuses set id, angle id and analysis id of W1 on purpose.
OTHER_SETS = [('set-a', 'an-1', 1, [('a-1', 'Other A1', 'low')])]
# (owner, analysis_id, revision, snapshot_id): set-b names revision 1 although revision 2 exists; set-c names an analysis that exists only in w2; set-d names a revision that does not exist.
ANALYSES = [
    ('w1', 'an-1', 1, 'snap-1'), ('w1', 'an-2', 1, 'snap-b-old'), ('w1', 'an-2', 2, 'snap-b-new'),
    ('w2', 'an-1', 1, 'snap-w-1'), ('w2', 'an-leak', 1, 'snap-leak'),
]
# set-a:a-1 and set-a:a-2 share one transaction, so they share created_at and are ordered by id.
EXPECTED = {
    'set-a:a-1': ('snap-1', 'Title A1', 'high'),
    'set-a:a-2': ('snap-1', 'Title A2', 'medium'),
    'set-b:b-1': ('snap-b-old', 'Title B1', 'low'),
    'set-c:c-1': (None, 'Title C1', 'high'),
    'set-d:d-1': (None, 'Title D1', 'medium'),
}
OTHER_EXPECTED = {'set-a:a-1': ('snap-w-1', 'Other A1', 'low')}
ASC = ['set-a:a-1', 'set-a:a-2', 'set-b:b-1', 'set-c:c-1', 'set-d:d-1']
DESC = list(reversed(ASC))


def make_analysis(workspace_id: str, snapshot_id: str, analysis_id: str, revision: int) -> Any:
    snapshot = build_production_snapshot(
        snapshot_id=snapshot_id,
        production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': 'art-1', 'revision_id': 'rev-1'}],
        index_revision_refs=[{'ref_type': 'index', 'ref_id': 'idx-1', 'revision_id': 'rev-1'}],
        configuration_revision_refs=[{'ref_type': 'config_bundle', 'ref_id': 'cfg-1', 'revision_id': 'rev-1'}],
        content_ref_types=['article'],
        eligibility_reason='eligible',
        snapshot_timestamp='2026-10-01T00:00:00+00:00',
        video_job_ref=None,
    )
    source = dict(snapshot.source_refs[0])
    prompt = {'workspace_id': workspace_id, 'ref_type': 'prompt_revision', 'ref_id': 'prompt-1', 'revision_id': 'prompt-rev-1'}
    resolver = RefResolver(
        workspace_id=workspace_id,
        allowed_refs=[ResourceRef(workspace_id, source['ref_type'], source['ref_id'], source['revision_id']), ResourceRef(**prompt)],
        allowed_ref_types=['article', 'prompt_revision'],
    )
    raw = {
        'analysis_id': analysis_id, 'revision': revision, 'topic': f'topic of {analysis_id}',
        'entities': [], 'timeline': [], 'locations': [],
        'facts': [{'id': 'f-1', 'text': 'CANARY-FACT', 'evidence_refs': [{'workspace_id': workspace_id, **source}]}],
        'uncertainties': [], 'contradictions': [], 'event_relation': 'standalone', 'update_context': '',
        'risk_flags': [], 'narrative_opportunities': [], 'media_needs': [],
        'trace': {'provider': 'fake-provider', 'model': 'fake-model', 'prompt_ref': prompt, 'policy_revision': 'pol-1'},
    }
    return parse_content_analysis(raw, snapshot, resolver)


def make_angle_set(workspace_id: str, set_id: str, analysis_id: str, analysis_revision: int, specs: list[tuple[str, str, str]]) -> Any:
    ref = ResourceRef(workspace_id, 'article', 'CANARY-EVIDENCE-1', 'rev-1')
    candidates = [
        StoryAngle(
            angle_id=angle_id, title=title, summary=f'CANARY-SUMMARY {angle_id}',
            narrative_question=f'CANARY-QUESTION {set_id} {angle_id}?', focus_entities=[f'CANARY-ENTITY {angle_id}'],
            timeframe='2026-10', evidence_refs=[ref], planned_inference_elements=['inference'],
            planned_creative_elements=['creative'], suitability=suitability, risk_flags=[],
        )
        for angle_id, title, suitability in specs
    ]
    return build_story_angle_set(
        set_id=set_id, analysis_id=analysis_id, analysis_revision=analysis_revision, requested_count=len(candidates),
        candidates=candidates, variation_policy_revision='var-1',
    )


def utc(moment: Any) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def seed_analyses(manager: Any, owner: str, workspace_id: str) -> None:
    for entry_owner, analysis_id, revision, snapshot_id in ANALYSES:
        if entry_owner != owner:
            continue
        analysis = make_analysis(workspace_id, snapshot_id, analysis_id, revision)
        with manager.borrow_connection() as connection:
            PostgresAnalysisRepository(lambda: connection, workspace_id).append(analysis_id, revision, analysis)


def seed_sets(manager: Any, workspace_id: str, sets: list[Any]) -> None:
    for set_id, analysis_id, analysis_revision, specs in sets:
        angle_set = make_angle_set(workspace_id, set_id, analysis_id, analysis_revision, specs)
        with manager.borrow_connection() as connection:
            PostgresAngleSetRepository(lambda: connection, workspace_id).append(set_id, 1, angle_set)


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: StoryAngleModuleService
    created: dict[tuple[str, str], str]


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        seed_analyses(manager, 'w1', workspace_id)
        seed_analyses(manager, 'w2', other_workspace_id)
        seed_sets(manager, workspace_id, SETS)
        seed_sets(manager, other_workspace_id, OTHER_SETS)
        with manager.borrow_connection() as connection:
            stamps = {(owner, angle_id): moment for owner, angle_id, moment in connection.execute('SELECT workspace_id::text, angle_id, created_at FROM controlplane.cp_story_angles').fetchall()}
        ordered = [stamps[(workspace_id, angle_id)] for angle_id in ASC]
        assert ordered == sorted(ordered) and len(set(ordered)) == 4 and ordered[0] == ordered[1]
        created = {key: utc(moment) for key, moment in stamps.items()}
        yield Env(manager, workspace_id, other_workspace_id, StoryAngleModuleService(manager.borrow_connection), created)


def make_row(env: Env, angle_id: str, other: bool = False) -> dict[str, Any]:
    snapshot_id, title, suitability = (OTHER_EXPECTED if other else EXPECTED)[angle_id]
    owner = env.other_workspace_id if other else env.workspace_id
    return {'angle_id': angle_id, 'snapshot_id': snapshot_id, 'title': title, 'suitability': suitability, 'created_at': env.created[(owner, angle_id)]}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['created_at'], allowed_filters=set(), default_limit=20, max_limit=100)


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
    return [item['angle_id'] for item in page.items]


def all_ids(pages: list[Page]) -> list[str]:
    return [angle_id for page in pages for angle_id in ids_of(page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert ids_of(page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {item['angle_id']: item for item in page.items} == {angle_id: make_row(env, angle_id) for angle_id in ASC}


def test_angle_id_keeps_set_id_prefix(env):
    ids = ids_of(get_page(env, {}))
    assert all(':' in angle_id for angle_id in ids)
    assert 'a-1' not in ids and 'set-a:a-1' in ids and 'set-b:b-1' in ids


def test_snapshot_id_follows_exact_analysis_revision_and_is_null_when_link_is_missing(env):
    rows = {item['angle_id']: item for item in get_page(env, {}).items}
    assert rows['set-a:a-1']['snapshot_id'] == rows['set-a:a-2']['snapshot_id'] == 'snap-1'
    assert rows['set-b:b-1']['snapshot_id'] == 'snap-b-old'
    assert rows['set-c:c-1']['snapshot_id'] is None
    assert rows['set-d:d-1']['snapshot_id'] is None
    text = json.dumps(list(rows.values()))
    assert not [token for token in ('snap-b-new', 'snap-leak', 'snap-w-1') if token in text]


def test_each_angle_is_one_row(env):
    ids = ids_of(get_page(env, {'direction': 'asc'}))
    assert len(ids) == len(set(ids)) == len(ASC)
    assert ids == ASC


def test_default_direction_is_desc_and_explicit_direction_is_honoured(env):
    assert ids_of(get_page(env, {})) == DESC
    assert ids_of(get_page(env, {'sort': 'created_at'})) == DESC
    assert ids_of(get_page(env, {'direction': 'asc'})) == ASC
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
    assert len(pages) == 3
    assert all_ids(pages) == DESC


def test_fetch_one_returns_row_or_none(env):
    for angle_id in ASC:
        assert get_one(env, angle_id) == make_row(env, angle_id)
    assert get_one(env, 'set-c:c-1')['snapshot_id'] is None
    for missing in ('a-1', 'set-a', 'set-a:', ':a-1', 'set-a:a-9', 'nope', ''):
        assert get_one(env, missing) is None
    assert get_one(env, 'set-b:b-1', env.other_workspace_id) is None
    assert get_one(env, 'set-a:a-1', env.other_workspace_id) == make_row(env, 'set-a:a-1', other=True)


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    theirs = get_page(env, {}, other)
    assert list(theirs.items) == [make_row(env, 'set-a:a-1', other=True)]
    assert all_ids(walk(env, {'direction': 'asc'}, 1, other)) == ['set-a:a-1']
    assert ids_of(get_page(env, {})) == DESC
    mine = get_one(env, 'set-a:a-1')
    assert mine['snapshot_id'] == 'snap-1' and mine['title'] == 'Title A1'
    text = json.dumps(list(get_page(env, {}).items))
    assert 'Other A1' not in text and 'snap-w-1' not in text and 'snap-leak' not in text


def test_catalog_has_no_filters(env):
    with pytest.raises(ListQueryError):
        make_query({'suitability': 'high'})
    assert ids_of(get_page(env, {'limit': '5'})) == DESC
    for name in ('suitability', 'title', 'snapshot_id', 'workspace_id'):
        query = ListQuery(limit=5, cursor=None, sort_key='created_at', direction='desc', filters=((name, 'x'),))
        with pytest.raises(ValueError):
            env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_unsupported_sort_key_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def table_state(env: Env) -> tuple[list[Any], list[Any], list[Any]]:
    with env.manager.borrow_connection() as connection:
        angles = connection.execute('SELECT workspace_id::text, angle_id, set_id, payload::text, created_at FROM controlplane.cp_story_angles ORDER BY workspace_id, angle_id').fetchall()
        sets = connection.execute('SELECT workspace_id::text, record_key, revision, payload::text, created_at FROM controlplane.cp_story_angle_sets ORDER BY workspace_id, record_key, revision').fetchall()
        analyses = connection.execute('SELECT workspace_id::text, record_key, revision, payload::text, created_at FROM controlplane.cp_content_analyses ORDER BY workspace_id, record_key, revision').fetchall()
    return (angles, sets, analyses)


def test_reads_do_not_change_source_tables(env):
    before = table_state(env)
    assert (len(before[0]), len(before[1]), len(before[2])) == (6, 5, 5)
    get_page(env, {})
    walk(env, {'direction': 'asc'}, 2)
    get_one(env, 'set-a:a-1')
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('set-a:a-1', 'set-a:a-1')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='created_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, angle_id, workspace_id) for angle_id in ASC)
    rows = [row for row in rows if row is not None]
    # distinction_fingerprint is derived in StoryAngle.__post_init__ and is not stored in the payload, so take it from the domain objects that were seeded.
    fingerprints = [angle.distinction_fingerprint for owner, sets in ((env.workspace_id, SETS), (env.other_workspace_id, OTHER_SETS)) for set_id, analysis_id, revision, specs in sets for angle in make_angle_set(owner, set_id, analysis_id, revision, specs).angles]
    text = json.dumps(rows)
    assert rows and len(fingerprints) == 6
    assert not [token for token in (*CANARIES, *fingerprints) if token in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'cp_story_angles g' in lowered and 'cp_story_angle_sets' in lowered and 'cp_content_analyses' in lowered
    assert all(token in lowered for token in ("payload->>'analysis_id'", "payload->>'analysis_revision'", "payload->>'snapshot_id'"))
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
