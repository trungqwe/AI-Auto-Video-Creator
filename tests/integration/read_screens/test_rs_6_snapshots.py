"""RS-6: PostgreSQL tests for the read-only snapshots service (module D)."""
from __future__ import annotations

import ast
import itertools
import json
import uuid
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from controlplane.application.projections.list_query import ListQuery, Page, parse_list_query
from controlplane.infrastructure.read_screens.snapshots import SnapshotModuleService
from creative.domain.analysis import parse_content_analysis
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.snapshot import build_production_snapshot
from creative.persistence.repositories import PostgresAnalysisRepository, PostgresSnapshotRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'read_screens' / 'snapshots.py'
ROW_KEYS = {'snapshot_id', 'job_id', 'model', 'prompt_ref', 'config_revision_ref', 'created_at'}
FORBIDDEN_KEYS = {'source_refs', 'index_revision_refs', 'recent_variant_exclusions', 'workspace_id', 'payload', 'source_set_fingerprint'}
FORBIDDEN_FRAGMENTS = ('insert into', 'update controlplane', 'delete from', 'from src.', 'os.environ', 'source_refs')
CANARIES = ('CANARY-SOURCE', 'CANARY-INDEX', 'CANARY-EXCLUSION', 'CANARY-FACT')
# (key, snapshot_id, video_job_ref, [(analysis_id, revision, model, prompt ref_id, prompt revision_id)])
SPEC = [
    ('s1', 'snap-a-1', 'job-1', [('an-1', 1, 'model-old', 'prompt-old', 'rev-old'), ('an-1', 2, 'model-new', 'prompt-new', 'rev-new')]),
    ('s2', 'snap-a-2', 'job-2', []),
    ('s3', 'snap-a-3', None, [('an-3', 1, 'model-three', 'prompt-three', 'rev-three')]),
    ('s4', 'snap-a-4', 'job-1', []),
    ('s5', 'snap-a-5', 'job-2', [('an-5', 1, 'model-five', 'prompt-five', 'rev-five')]),
]
OTHER_SPEC = [
    ('w1', 'snap-b-1', 'job-1', [('an-w1', 1, 'model-other', 'prompt-other', 'rev-other')]),
    ('w2', 'snap-b-2', None, []),
]
# An analysis of the other workspace that names a snapshot of this workspace must never show up.
LEAK_SPEC = ('an-leak', 1, 'model-leak', 'prompt-leak', 'rev-leak')
# s4 and s5 share one transaction, so they share created_at and are ordered by snapshot id.
GROUPS = [SPEC[0:1], SPEC[1:2], SPEC[2:3], SPEC[3:5]]
OTHER_GROUPS = [OTHER_SPEC[0:1], OTHER_SPEC[1:2]]
ASC = [entry[0] for entry in SPEC]
DESC = list(reversed(ASC))
IDS = {entry[0]: entry[1] for entry in (*SPEC, *OTHER_SPEC)}
EXPECTED = {
    's1': ('job-1', 'model-new', 'prompt-new@rev-new'),
    's2': ('job-2', None, None),
    's3': (None, 'model-three', 'prompt-three@rev-three'),
    's4': ('job-1', None, None),
    's5': ('job-2', 'model-five', 'prompt-five@rev-five'),
    'w1': ('job-1', 'model-other', 'prompt-other@rev-other'),
    'w2': (None, None, None),
}
COUNTER = itertools.count(1)


def seed_snapshot(connection: Any, workspace_id: str, snapshot_id: str, job_ref: str | None) -> Any:
    number = next(COUNTER)
    snapshot = build_production_snapshot(
        snapshot_id=snapshot_id,
        production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': f'CANARY-SOURCE-{number}', 'revision_id': 'rev-1'}],
        index_revision_refs=[{'ref_type': 'index', 'ref_id': f'CANARY-INDEX-{number}', 'revision_id': 'rev-1'}],
        configuration_revision_refs=[{'ref_type': 'config_bundle', 'ref_id': f'cfg-{number}', 'revision_id': 'rev-1'}],
        content_ref_types=['article'],
        eligibility_reason='eligible',
        snapshot_timestamp='2026-10-01T00:00:00+00:00',
        video_job_ref=job_ref,
        recent_variant_exclusions=[f'CANARY-EXCLUSION-{number}'],
    )
    PostgresSnapshotRepository(lambda: connection, workspace_id).add(snapshot)
    return snapshot


def make_analysis(workspace_id: str, snapshot: Any, spec: tuple[Any, ...]) -> Any:
    analysis_id, revision, model, prompt_id, prompt_revision = spec
    source = dict(snapshot.source_refs[0])
    prompt = {'workspace_id': workspace_id, 'ref_type': 'prompt_revision', 'ref_id': prompt_id, 'revision_id': prompt_revision}
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
        'trace': {'provider': 'fake-provider', 'model': model, 'prompt_ref': prompt, 'policy_revision': 'pol-1'},
    }
    return parse_content_analysis(raw, snapshot, resolver)


def append_analysis(manager: Any, workspace_id: str, snapshot: Any, spec: tuple[Any, ...]) -> None:
    analysis = make_analysis(workspace_id, snapshot, spec)
    with manager.borrow_connection() as connection:
        PostgresAnalysisRepository(lambda: connection, workspace_id).append(spec[0], spec[1], analysis)


def seed_group(manager: Any, workspace_id: str, group: list[Any], snapshots: dict[str, Any]) -> None:
    with manager.borrow_connection() as connection:
        for key, snapshot_id, job_ref, _ in group:
            snapshots[key] = seed_snapshot(connection, workspace_id, snapshot_id, job_ref)
    for key, _, _, analyses in group:
        for spec in analyses:
            append_analysis(manager, workspace_id, snapshots[key], spec)


@dataclass(frozen=True)
class Env:
    manager: Any
    workspace_id: str
    other_workspace_id: str
    service: SnapshotModuleService
    snapshots: dict[str, Any]
    keys: dict[str, str]
    created: dict[str, str]


@pytest.fixture(scope='module')
def env():
    with rs_support.temp_database() as (manager, workspace_id, other_workspace_id):
        snapshots: dict[str, Any] = {}
        for group in GROUPS:
            seed_group(manager, workspace_id, group, snapshots)
        for group in OTHER_GROUPS:
            seed_group(manager, other_workspace_id, group, snapshots)
        append_analysis(manager, other_workspace_id, snapshots['s2'], LEAK_SPEC)
        with manager.borrow_connection() as connection:
            stamps = dict(connection.execute('SELECT snapshot_id, created_at FROM controlplane.cp_production_snapshots').fetchall())
        ordered = [stamps[IDS[key]] for key in ASC]
        assert ordered == sorted(ordered) and len(set(ordered)) == 4 and ordered[3] == ordered[4]
        created = {snapshot_id: moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ') for snapshot_id, moment in stamps.items()}
        yield Env(manager, workspace_id, other_workspace_id, SnapshotModuleService(manager.borrow_connection), snapshots, {snapshot_id: key for key, snapshot_id in IDS.items()}, created)


def make_row(env: Env, key: str) -> dict[str, Any]:
    job_id, model, prompt_ref = EXPECTED[key]
    snapshot = env.snapshots[key]
    return {'snapshot_id': snapshot.snapshot_id, 'job_id': job_id, 'model': model, 'prompt_ref': prompt_ref, 'config_revision_ref': snapshot.configuration_bundle_fingerprint, 'created_at': env.created[snapshot.snapshot_id]}


def make_query(params: dict[str, str]) -> ListQuery:
    return parse_list_query(params, allowed_sorts=['created_at'], allowed_filters={'job_id'}, default_limit=20, max_limit=100)


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
    return [env.keys[item['snapshot_id']] for item in page.items]


def all_keys(env: Env, pages: list[Page]) -> list[str]:
    return [key for page in pages for key in keys_of(env, page)]


def test_rows_have_exact_keys_and_values(env):
    page = get_page(env, {})
    assert keys_of(env, page) == DESC
    assert page.next_cursor is None
    assert all(set(item) == ROW_KEYS for item in page.items)
    assert {env.keys[item['snapshot_id']]: item for item in page.items} == {key: make_row(env, key) for key in ASC}


def test_newest_analysis_revision_is_used(env):
    row = get_one(env, IDS['s1'])
    assert row['model'] == 'model-new' and row['prompt_ref'] == 'prompt-new@rev-new'
    assert 'old' not in json.dumps(row)


def test_each_snapshot_is_one_row_even_with_several_analysis_revisions(env):
    page = get_page(env, {'direction': 'asc'})
    ids = [item['snapshot_id'] for item in page.items]
    assert len(ids) == len(set(ids)) == len(ASC)
    assert keys_of(env, page) == ASC


def test_missing_analysis_gives_null_model_and_prompt_ref(env):
    rows = {env.keys[item['snapshot_id']]: item for item in get_page(env, {}).items}
    for key in ('s2', 's4'):
        assert rows[key]['model'] is None and rows[key]['prompt_ref'] is None
    assert rows['s2']['job_id'] == 'job-2'
    assert rows['s3']['job_id'] is None and rows['s3']['model'] == 'model-three'


def test_config_revision_ref_is_the_configuration_bundle_fingerprint(env):
    rows = {env.keys[item['snapshot_id']]: item for item in get_page(env, {}).items}
    for key in ASC:
        assert rows[key]['config_revision_ref'] == env.snapshots[key].configuration_bundle_fingerprint
    assert len({row['config_revision_ref'] for row in rows.values()}) == len(ASC)


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
    assert len(pages) == 3
    assert all_keys(env, pages) == DESC


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_filtered_pagination_has_no_duplicates_or_gaps(env, direction):
    for job_id, expected in (('job-1', ['s1', 's4']), ('job-2', ['s2', 's5'])):
        pages = walk(env, {'job_id': job_id, 'direction': direction}, 1)
        assert len(pages) == 2
        assert all_keys(env, pages) == (expected if direction == 'asc' else expected[::-1])


@pytest.mark.parametrize(
    'params, expected',
    [
        ({'job_id': 'job-1'}, ['s4', 's1']),
        ({'job_id': 'job-2'}, ['s5', 's2']),
        ({'job_id': 'job-unknown'}, []),
        ({'job_id': 'JOB-1'}, []),
        ({'job_id': ''}, []),
        ({'job_id': 'snap-a-1'}, []),
    ],
)
def test_job_filter_is_exact_and_unknown_value_is_empty(env, params, expected):
    page = get_page(env, params)
    assert keys_of(env, page) == expected
    assert page.next_cursor is None


@pytest.mark.parametrize('name', ['video_job_ref', 'model', 'snapshot_id', 'workspace_id'])
def test_unsupported_filter_name_raises_value_error(env, name):
    query = ListQuery(limit=5, cursor=None, sort_key='created_at', direction='desc', filters=((name, 'x'),))
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_unsupported_sort_key_raises_value_error(env):
    query = ListQuery(limit=5, cursor=None, sort_key='updated_at', direction='desc', filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {}), env.workspace_id, query)


def test_fetch_one_returns_row_or_none(env):
    assert get_one(env, IDS['s1']) == make_row(env, 's1')
    assert get_one(env, IDS['s2']) == make_row(env, 's2')
    assert get_one(env, IDS['s2'])['model'] is None
    assert get_one(env, 'snap-unknown') is None
    assert get_one(env, 'nope') is None
    assert get_one(env, IDS['w1']) is None
    assert get_one(env, IDS['s1'], env.other_workspace_id) is None
    assert get_one(env, IDS['w1'], env.other_workspace_id) == make_row(env, 'w1')


def test_workspaces_are_isolated(env):
    other = env.other_workspace_id
    assert keys_of(env, get_page(env, {})) == DESC
    theirs = get_page(env, {}, other)
    assert keys_of(env, theirs) == ['w2', 'w1']
    assert list(theirs.items) == [make_row(env, 'w2'), make_row(env, 'w1')]
    assert keys_of(env, get_page(env, {'job_id': 'job-1'}, other)) == ['w1']
    assert keys_of(env, get_page(env, {'job_id': 'job-2'}, other)) == []
    assert all_keys(env, walk(env, {'direction': 'asc'}, 1, other)) == ['w1', 'w2']
    assert not {'w1', 'w2'} & set(all_keys(env, walk(env, {}, 1)))
    assert get_one(env, IDS['s2'])['model'] is None


def table_state(env: Env) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    with env.manager.borrow_connection() as connection:
        snapshots = connection.execute(
            'SELECT workspace_id::text, snapshot_id, source_set_fingerprint, configuration_bundle_fingerprint, payload::text, created_at '
            'FROM controlplane.cp_production_snapshots ORDER BY snapshot_id'
        ).fetchall()
        analyses = connection.execute(
            'SELECT workspace_id::text, record_key, revision, payload::text, created_at '
            'FROM controlplane.cp_content_analyses ORDER BY workspace_id, record_key, revision'
        ).fetchall()
    return (snapshots, analyses)


def test_reads_do_not_change_source_tables(env):
    before = table_state(env)
    assert len(before[0]) == 7 and len(before[1]) == 6
    get_page(env, {})
    walk(env, {'direction': 'asc'}, 2)
    get_page(env, {'job_id': 'job-1'})
    get_one(env, IDS['s1'])
    get_one(env, 'nope')
    assert table_state(env) == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('cursor', [('not-a-time', 'x'), ('', 'x'), ('2026-13-45T01:02:03Z', 'x'), ('2026-10-25', 'x'), ('s1', 's1')])
def test_foreign_cursor_raises_value_error(env, direction, cursor):
    query = ListQuery(limit=2, cursor=cursor, sort_key='created_at', direction=direction, filters=())
    with pytest.raises(ValueError):
        env.service.fetch_page(rs_support.FakeRequest(env.workspace_id, {'direction': direction}), env.workspace_id, query)


def test_forbidden_fields_never_leave_the_service(env):
    rows: list[Any] = []
    for workspace_id in (env.workspace_id, env.other_workspace_id):
        rows.extend(get_page(env, {}, workspace_id).items)
        rows.extend(get_one(env, IDS[key], workspace_id) for key in ('s1', 's2', 's5', 'w1'))
    rows = [row for row in rows if row is not None]
    stored_snapshots, _ = table_state(env)
    tokens = [*CANARIES, *(record[2] for record in stored_snapshots)]
    text = json.dumps(rows)
    assert rows
    assert not [token for token in tokens if token in text]
    assert all(set(row) == ROW_KEYS and not FORBIDDEN_KEYS & set(row) for row in rows)


def test_service_source_is_read_only_and_layered():
    text = SERVICE_SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert not [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    assert 'left join lateral' in lowered
    assert 'order by a.created_at desc, a.revision desc, a.record_key desc limit 1' in lowered
    assert 'cp_production_snapshots' in lowered and 'cp_content_analyses' in lowered
    modules = [node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)]
    assert 'controlplane.infrastructure.read_screens.common' in modules
    assert not [name for name in modules if name and name.startswith(('controlplane.api', 'src'))]
