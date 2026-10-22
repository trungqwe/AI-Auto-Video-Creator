'''PERSIST-C-FIX1: kiểm head và list_heads của PostgresHookHistory bằng connection giả, không cần PostgreSQL.'''

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import catalog.domain.hooks as hooks_domain
from catalog.persistence.hooks import PostgresHookHistory

WORKSPACE = '11111111-2222-3333-4444-555555555555'
ICT = timezone(timedelta(hours=7))
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z\Z')
WRITE = re.compile(r'\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b', re.IGNORECASE)


class FakeCursor:
    def __init__(self, connection) -> None:
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, tuple(params)))

    def fetchall(self):
        return list(self.connection.rows)


class FakeConnection:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.calls = []

    def cursor(self, **kwargs):
        return FakeCursor(self)


def make_row(hook_id, revision, kind, tags, enabled, updated_at):
    payload = {
        'kind': kind,
        'tags': list(tags),
        'description': 'Late winner',
        'note': 'check',
        'enabled': enabled,
        'technical_metadata': [['fps', '30']],
        'provenance': 'user_imported',
    }
    return (hook_id, revision, f'av-{hook_id}', payload, updated_at)


ROW_A = make_row('hook-1', 2, 'visual_hook', ['sports', 'goal'], False, datetime(2026, 10, 22, 8, 30, 15, 250000, tzinfo=ICT))
ROW_B = make_row('hook-2', 1, 'audio_hook', ['crowd'], True, datetime(2026, 10, 22, 2, 0, 0, tzinfo=timezone.utc))


def test_list_heads_runs_one_parameterized_select():
    conn = FakeConnection([ROW_A, ROW_B])
    heads = PostgresHookHistory(conn, WORKSPACE).list_heads()
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert sql.lstrip().upper().startswith('SELECT')
    assert WRITE.search(sql) is None
    assert 'cp_hooks' in sql
    assert 'cp_hook_revisions' in sql
    assert 'current_revision' in sql
    assert re.search(r'ORDER BY (?:h\.)?hook_id\s*\Z', sql)
    assert params == (uuid.UUID(WORKSPACE),)
    assert sql.count('%s') == len(params)
    assert WORKSPACE not in sql
    assert len(heads) == 2


def test_list_heads_maps_rows_to_hook_heads():
    conn = FakeConnection([ROW_A, ROW_B])
    heads = PostgresHookHistory(conn, WORKSPACE).list_heads()
    for head in heads:
        assert isinstance(head, hooks_domain.HookHead)
    assert heads[0].revision.hook_id == 'hook-1'
    assert heads[0].revision.revision == 2
    assert heads[0].revision.kind == hooks_domain.HookKind.VISUAL_HOOK
    assert heads[0].revision.artifact_version_ref == 'av-hook-1'
    assert heads[0].revision.tags == ('sports', 'goal')
    assert heads[0].revision.description == 'Late winner'
    assert heads[0].revision.note == 'check'
    assert heads[0].revision.enabled is False
    assert heads[0].revision.technical_metadata == (('fps', '30'),)
    assert heads[0].updated_at == '2026-10-22T01:30:15.250000Z'
    assert heads[1].updated_at == '2026-10-22T02:00:00.000000Z'
    assert STAMP.fullmatch(heads[0].updated_at)
    assert STAMP.fullmatch(heads[1].updated_at)
    assert heads[1].revision.kind == hooks_domain.HookKind.AUDIO_HOOK
    assert heads[1].revision.enabled is True


def test_list_heads_is_empty_when_no_rows():
    conn = FakeConnection([])
    assert PostgresHookHistory(conn, WORKSPACE).list_heads() == []


def test_head_runs_one_parameterized_select():
    conn = FakeConnection([ROW_A])
    head = PostgresHookHistory(conn, WORKSPACE).head('hook-1')
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert sql.lstrip().upper().startswith('SELECT')
    assert WRITE.search(sql) is None
    assert params == (uuid.UUID(WORKSPACE), 'hook-1')
    assert sql.count('%s') == len(params)
    assert 'hook-1' not in sql
    assert WORKSPACE not in sql
    assert 'hook_id = %s' in sql
    assert head.revision.revision == 2
    assert head.updated_at == '2026-10-22T01:30:15.250000Z'


def test_head_of_unknown_hook_raises_key_error():
    conn = FakeConnection([])
    with pytest.raises(KeyError):
        PostgresHookHistory(conn, WORKSPACE).head('missing')
