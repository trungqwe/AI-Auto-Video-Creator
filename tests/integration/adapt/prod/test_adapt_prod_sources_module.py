"""Kiểm ADAPT-PROD-FIX1: service nguồn của A gắn vào module_services['sources'] (F1 của M3-MILESTONE-CLOSE)"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from controlplane.api.routes.modules.metadata_update import RevisionConflictError as RouteRevisionConflictError
from controlplane.api.wiring.production import SourceModuleService, compose_sources_module
from controlplane.application.projections.list_query import ListQuery, decode_cursor
from controlplane.domain.concurrency import RevisionConflictError
from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.domain.source import SourcePolicy

ROOT = Path(__file__).resolve().parents[4]
WORKSPACE, OTHER, ACTOR = str(uuid.uuid4()), str(uuid.uuid4()), 'actor-1'
POLICY = SourcePolicy('profile-1', frozenset({'rss_feed'}), frozenset({'tier_1', 'tier_2', 'tier_3'}), frozenset())
ROW_KEYS = {'source_id', 'name', 'tier', 'topic_tags', 'notes', 'enabled', 'status', 'revision', 'updated_at'}


def resolver(host):
    return ('93.184.216.34',)


class Env:
    def __init__(self):
        self.store, self.tick, self.factory_calls = InMemoryUnitOfWork(), 0, 0
        self.handler = SourceCommandHandler(uow=self.store, policy_provider=lambda ws: POLICY, resolver=resolver, recovery_epoch='test-1', clock=self.clock)
        self.service = SourceModuleService(uow_factory=self.factory, policy_provider=lambda ws: POLICY, resolver=resolver, recovery_epoch='test-1')

    def clock(self):
        self.tick += 1
        return datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc) + timedelta(minutes=self.tick)

    def factory(self):
        self.factory_calls += 1
        return self.store

    def add(self, code, *, tier='tier_1', topics=('news',), enabled=True, workspace=WORKSPACE):
        result = self.handler.register_source(workspace_id=workspace, idempotency_key='seed:' + code, actor=ACTOR, correlation_id='seed', locator=f'https://news.example.com/{code}.xml', name=code, source_kind='rss_feed', tier=tier, topics=topics, notes='', collection_enabled=enabled)
        return result.receipt.aggregate_ref

    def remove(self, source_id, revision=1):
        self.handler.remove_source(workspace_id=WORKSPACE, idempotency_key='rm:' + source_id, actor=ACTOR, correlation_id='c', source_id=source_id, expected_revision=revision)


def request():
    return SimpleNamespace(state=SimpleNamespace(identity={'workspace_id': WORKSPACE, 'actor_id': ACTOR}, correlation_id='corr-1'))


def page(env, *, limit=50, cursor=None, sort='updated_at', direction='asc', filters=()):
    return env.service.fetch_page(request(), WORKSPACE, ListQuery(limit=limit, cursor=cursor, sort_key=sort, direction=direction, filters=tuple(filters)))


def names(result):
    return [row['name'] for row in result.items]


def test_row_shape_and_workspace_isolation():
    env = Env()
    source_id = env.add('a', topics=('b', 'a'))
    env.add('z', workspace=OTHER)
    result = page(env)
    assert names(result) == ['a'] and result.next_cursor is None
    row = result.items[0]
    assert set(row) == ROW_KEYS and row['source_id'] == source_id
    assert row['topic_tags'] == ['a', 'b'] and row['enabled'] is True and row['status'] == 'ACTIVE'
    assert row['revision'] == 1 and row['updated_at'].endswith('Z')
    assert env.service.fetch_one(request(), WORKSPACE, source_id) == row
    assert env.service.fetch_one(request(), OTHER, source_id) is None


def test_removed_sources_hidden_unless_status_filter():
    env = Env()
    env.add('a')
    gone = env.add('b')
    env.remove(gone)
    assert names(page(env)) == ['a']
    assert names(page(env, filters=[('status', 'REMOVED_TOMBSTONE')])) == ['b']
    assert env.service.fetch_one(request(), WORKSPACE, gone) is None
    assert env.service.fetch_one(request(), WORKSPACE, 'missing') is None


def test_filters_by_tier_topic_and_status():
    env = Env()
    env.add('a', tier='tier_1', topics=('news',))
    env.add('b', tier='tier_2', topics=('news', 'ai'), enabled=False)
    assert names(page(env, filters=[('tier', 'tier_2')])) == ['b']
    assert names(page(env, filters=[('topic', 'ai')])) == ['b']
    assert names(page(env, filters=[('status', 'DISABLED')])) == ['b']
    assert names(page(env, filters=[('status', 'ACTIVE')])) == ['a']
    assert page(env, filters=[('topic', 'none')]).items == ()


def test_sort_and_keyset_pagination():
    env = Env()
    for code in ('c', 'a', 'b'):
        env.add(code)
    assert names(page(env)) == ['c', 'a', 'b']
    assert names(page(env, direction='desc')) == ['b', 'a', 'c']
    first = page(env, limit=2, sort='name')
    assert names(first) == ['a', 'b'] and first.next_cursor is not None
    second = page(env, limit=2, sort='name', cursor=decode_cursor(first.next_cursor))
    assert names(second) == ['c'] and second.next_cursor is None
    first = page(env, limit=2, sort='name', direction='desc')
    assert names(first) == ['c', 'b'] and first.next_cursor is not None
    second = page(env, limit=2, sort='name', direction='desc', cursor=decode_cursor(first.next_cursor))
    assert names(second) == ['a'] and second.next_cursor is None


def update(env, source_id, changes, *, revision=1, key='k-1'):
    return env.service.apply_update(request=request(), item_id=source_id, expected_revision=revision, changes=changes, idempotency_key=key)


def test_update_maps_columns_and_replay_does_not_bump_revision():
    env = Env()
    source_id = env.add('a')
    changes = {'topic_tags': ['y', 'x'], 'enabled': False, 'notes': 'n', 'tier': 'tier_2'}
    row = update(env, source_id, changes)
    assert set(row) == ROW_KEYS and row['revision'] == 2
    assert row['topic_tags'] == ['x', 'y'] and row['enabled'] is False and row['status'] == 'DISABLED'
    assert row['notes'] == 'n' and row['tier'] == 'tier_2'
    assert update(env, source_id, changes) == row
    assert env.service.fetch_one(request(), WORKSPACE, source_id)['revision'] == 2


def test_update_maps_errors_to_route_contract():
    env = Env()
    source_id = env.add('a')
    update(env, source_id, {'notes': 'x'})
    with pytest.raises(RevisionConflictError):
        update(env, source_id, {'notes': 'y'}, revision=1, key='k-2')
    with pytest.raises(ValueError, match='IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'):
        update(env, source_id, {'notes': 'z'})
    with pytest.raises(LookupError):
        update(env, 'missing', {'notes': 'x'}, key='k-3')
    for bad in ({'tier': 'tier_9'}, {'topic_tags': []}, {'topic_tags': 'news'}, {'enabled': 'yes'}, {'notes': 5}, {'notes': None}):
        with pytest.raises(ValueError):
            update(env, source_id, bad, revision=2, key='bad-' + str(sorted(bad)))


def test_update_of_removed_source_is_revision_conflict():
    env = Env()
    source_id = env.add('a')
    env.remove(source_id)
    with pytest.raises(RouteRevisionConflictError):
        update(env, source_id, {'notes': 'x'}, revision=2, key='k-9')


def test_compose_sources_module_uses_fake_services_and_profile_policy():
    env = Env()
    profile = SimpleNamespace(revision=3, collection=SimpleNamespace(source_kinds=('rss_feed',)), parameters={'collection.tiers': {'tier_1': 'a', 'tier_2': 'b'}})
    config = SimpleNamespace(production_parts=lambda: (profile, None))
    service = compose_sources_module({'collection': SimpleNamespace(uow_factory=env.factory)}, config)
    assert isinstance(service, SourceModuleService)
    source_id = env.add('a')
    calls = env.factory_calls
    row = service.apply_update(request=request(), item_id=source_id, expected_revision=1, changes={'tier': 'tier_2'}, idempotency_key='c-1')
    assert row['tier'] == 'tier_2' and env.factory_calls == calls + 2
    with pytest.raises(ValueError):
        service.apply_update(request=request(), item_id=source_id, expected_revision=2, changes={'tier': 'tier_3'}, idempotency_key='c-2')


def test_production_module_wires_sources_without_forbidden_text():
    text = (ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'production.py').read_text(encoding='utf-8')
    assert "module_services['sources']" in text
    for banned in ('import os', 'os.environ', 'getenv', 'import psycopg', 'INSERT INTO', 'application.test_driver'):
        assert banned not in text, banned
