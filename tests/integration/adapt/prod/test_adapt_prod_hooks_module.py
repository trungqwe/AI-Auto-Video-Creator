"""Kiểm ADAPT-PROD-FIX2: service hook của C gắn vào module_services['hooks'] (HookModuleService)"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from catalog.application.hooks import HookHistory, import_hook
from catalog.domain.hooks import HookKind
import controlplane.api.wiring.production as production
from controlplane.api.wiring.production import HookModuleService, compose_hooks_module
from controlplane.application.projections.list_query import ListQuery, decode_cursor
from controlplane.domain.concurrency import RevisionConflictError

ROOT = Path(__file__).resolve().parents[4]
WORKSPACE, OTHER, ACTOR = str(uuid.uuid4()), str(uuid.uuid4()), 'actor-1'
ROW_KEYS = {'hook_id', 'kind', 'tags', 'description', 'enabled', 'notes', 'revision', 'updated_at'}


class Env:
    def __init__(self):
        self.tick, self.opened, self.histories = 0, 0, {}
        self.service = HookModuleService(history_scope=self.scope)

    def clock(self):
        self.tick += 1
        return datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc) + timedelta(minutes=self.tick)

    def history(self, workspace):
        return self.histories.setdefault(workspace, HookHistory(clock=self.clock))

    @contextmanager
    def scope(self, workspace_id):
        self.opened += 1
        yield self.history(workspace_id)

    def add(self, hook_id, *, kind=HookKind.VISUAL_HOOK, tags=('sports',), enabled=True, workspace=WORKSPACE):
        import_hook(self.history(workspace), hook_id=hook_id, kind=kind, artifact_version_ref='av-' + hook_id, tags=tags, description='d-' + hook_id, note='n-' + hook_id, enabled=enabled)


def request():
    return SimpleNamespace(state=SimpleNamespace(identity={'workspace_id': WORKSPACE, 'actor_id': ACTOR}, correlation_id='corr-1'))


def page(env, *, limit=50, cursor=None, sort='updated_at', direction='asc', filters=()):
    return env.service.fetch_page(request(), WORKSPACE, ListQuery(limit=limit, cursor=cursor, sort_key=sort, direction=direction, filters=tuple(filters)))


def ids(result):
    return [row['hook_id'] for row in result.items]


def test_row_shape_json_types_and_workspace_isolation():
    env = Env()
    env.add('a', tags=('b', 'a'))
    env.add('e', tags=(), kind=HookKind.AUDIO_HOOK)
    env.add('z', workspace=OTHER)
    result = page(env)
    assert ids(result) == ['a', 'e'] and result.next_cursor is None
    row = result.items[0]
    assert set(row) == ROW_KEYS and row['tags'] == ['b', 'a'] and row['kind'] == 'visual_hook'
    assert row['description'] == 'd-a' and row['notes'] == 'n-a' and row['enabled'] is True
    assert row['revision'] == 1 and row['updated_at'].endswith('Z')
    assert result.items[1]['tags'] == [] and result.items[1]['kind'] == 'audio_hook'
    assert env.service.fetch_one(request(), WORKSPACE, 'a') == row
    assert env.service.fetch_one(request(), OTHER, 'a') is None
    assert env.service.fetch_one(request(), WORKSPACE, 'missing') is None


def test_filters_by_kind_tag_and_enabled():
    env = Env()
    env.add('a', tags=('sports', 'goal'))
    env.add('b', kind=HookKind.AUDIO_HOOK, tags=('crowd',), enabled=False)
    assert ids(page(env, filters=[('kind', 'audio_hook')])) == ['b']
    assert ids(page(env, filters=[('tag', 'goal')])) == ['a']
    assert ids(page(env, filters=[('enabled', 'false')])) == ['b']
    assert ids(page(env, filters=[('enabled', 'true')])) == ['a']
    assert ids(page(env, filters=[('kind', 'visual_hook'), ('tag', 'crowd')])) == []
    for bad in ('True', 'yes', '1', ''):
        with pytest.raises(ValueError):
            page(env, filters=[('enabled', bad)])
    with pytest.raises(ValueError):
        page(Env(), filters=[('enabled', 'maybe')])


def test_sort_and_keyset_pagination():
    env = Env()
    for hook_id in ('c', 'a', 'b'):
        env.add(hook_id)
    assert ids(page(env)) == ['c', 'a', 'b']
    assert ids(page(env, direction='desc')) == ['b', 'a', 'c']
    first = page(env, limit=2, sort='name')
    assert ids(first) == ['a', 'b'] and decode_cursor(first.next_cursor) == ('b', 'b')
    second = page(env, limit=2, sort='name', cursor=decode_cursor(first.next_cursor))
    assert ids(second) == ['c'] and second.next_cursor is None
    first = page(env, limit=2, sort='name', direction='desc')
    assert ids(first) == ['c', 'b']
    assert ids(page(env, limit=2, sort='name', direction='desc', cursor=decode_cursor(first.next_cursor))) == ['a']
    first = page(env, limit=2)
    assert ids(first) == ['c', 'a'] and decode_cursor(first.next_cursor)[1] == 'a'
    assert ids(page(env, limit=2, cursor=decode_cursor(first.next_cursor))) == ['b']


def update(env, hook_id, changes, *, revision=1):
    return env.service.apply_update(request=request(), item_id=hook_id, expected_revision=revision, changes=changes, idempotency_key='k-' + hook_id)


def test_update_maps_fields_and_keeps_old_revision():
    env = Env()
    env.add('a')
    opened = env.opened
    row = update(env, 'a', {'tags': ['y', 'x'], 'description': 'new', 'enabled': False, 'notes': 'nn'})
    assert env.opened == opened + 1
    assert set(row) == ROW_KEYS and row['revision'] == 2 and row['tags'] == ['y', 'x']
    assert row['description'] == 'new' and row['enabled'] is False and row['notes'] == 'nn' and row['kind'] == 'visual_hook'
    assert env.service.fetch_one(request(), WORKSPACE, 'a') == row
    old, new = env.history(WORKSPACE).get('a', 1), env.history(WORKSPACE).get('a', 2)
    assert old.tags == ('sports',) and old.note == 'n-a' and new.note == 'nn'
    assert old.kind is new.kind and old.artifact_version_ref == new.artifact_version_ref == 'av-a'
    assert update(env, 'a', {'notes': ''}, revision=2)['notes'] == ''
    assert update(env, 'a', {'tags': []}, revision=3)['tags'] == []


def test_replay_with_same_if_match_is_conflict_without_new_revision():
    env = Env()
    env.add('a')
    update(env, 'a', {'notes': 'x'})
    with pytest.raises(RevisionConflictError):
        update(env, 'a', {'notes': 'x'})
    assert env.service.fetch_one(request(), WORKSPACE, 'a')['revision'] == 2


def test_update_errors_map_to_route_contract():
    env = Env()
    env.add('a')
    with pytest.raises(LookupError):
        update(env, 'missing', {'notes': 'x'})
    with pytest.raises(RevisionConflictError):
        update(env, 'a', {'notes': 'x'}, revision=5)
    bad_changes = ({'tags': 'news'}, {'tags': [1]}, {'tags': None}, {'description': 5}, {'notes': None}, {'notes': 5}, {'enabled': 'yes'}, {'enabled': 1}, {'kind': 'audio_hook'}, {'artifact_version_ref': 'x'}, {'note': 'x'})
    for bad in bad_changes:
        with pytest.raises(ValueError):
            update(env, 'a', bad)
    assert env.service.fetch_one(request(), WORKSPACE, 'a')['revision'] == 1


def test_update_without_effective_change_is_validation_error():
    env = Env()
    env.add('a')
    for same in ({'notes': 'n-a'}, {'tags': ['sports']}, {'enabled': True, 'description': 'd-a'}):
        with pytest.raises(ValueError):
            update(env, 'a', same)
    assert env.service.fetch_one(request(), WORKSPACE, 'a')['revision'] == 1
    assert update(env, 'a', {'notes': 'n-a', 'enabled': False})['revision'] == 2


class FakeUow:
    def __init__(self, log):
        self.log, self.connection = log, object()

    def __enter__(self):
        self.log.append('enter')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.log.append(('exit', exc_type))
        return False


def test_compose_hooks_module_opens_unit_of_work_per_call(monkeypatch):
    log, built, seeded = [], [], HookHistory()
    import_hook(seeded, hook_id='a', kind=HookKind.VISUAL_HOOK, artifact_version_ref='av-a')
    manager = SimpleNamespace(unit_of_work=lambda: FakeUow(log))

    def factory(connection, workspace_id):
        built.append((connection, workspace_id))
        return seeded

    monkeypatch.setattr(production, 'PostgresHookHistory', factory)
    service = compose_hooks_module(manager)
    assert isinstance(service, HookModuleService)
    assert service.fetch_one(request(), WORKSPACE, 'a')['hook_id'] == 'a'
    assert log == ['enter', ('exit', None)] and built[0][1] == WORKSPACE
    with pytest.raises(LookupError):
        service.apply_update(request=request(), item_id='missing', expected_revision=1, changes={'notes': 'x'}, idempotency_key='k')
    assert log[2:] == ['enter', ('exit', KeyError)] and len(built) == 2 and built[0][0] is not built[1][0]
    assert service.apply_update(request=request(), item_id='a', expected_revision=1, changes={'notes': 'x'}, idempotency_key='k')['revision'] == 2
    assert log[-1] == ('exit', None)


def test_production_module_wires_hooks_without_forbidden_text():
    text = (ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'production.py').read_text(encoding='utf-8')
    assert "module_services['hooks']" in text and "module_services['media']" not in text
    for banned in ('import os', 'os.environ', 'getenv', 'import psycopg', 'INSERT INTO', 'sqlite3', 'PostgresIdempotencyRepository', 'PostgresOutboxRepository', 'application.test_driver'):
        assert banned not in text, banned
