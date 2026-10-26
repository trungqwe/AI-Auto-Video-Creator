"""PW-G1: PostgresAppSessions, epoch thập phân và thứ tự begin/end của launcher.

coveredIds: PW-G1-01..06, CT-WF-004
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import psycopg.errors
import pytest

from controlplane.application.orchestration.workflows.activities import to_execution_grant
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.grants import PostgresRecoveryEpoch

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
APP_SESSION_SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'orchestration' / 'app_session.py'
NOW = datetime(2026, 10, 22, 3, 4, 5, tzinfo=timezone.utc)
LEGACY_EPOCH = 'rec-20261001000000-0a1b2c3d'


def rows(connection, workspace_id):
    return connection.execute(
        'SELECT session_ref, status, recovery_epoch, ended_at FROM controlplane.cp_app_sessions WHERE workspace_id = %s ORDER BY session_ref',
        (workspace_id,),
    ).fetchall()


def short(result):
    return [(row[0], row[1], row[2]) for row in result]


def test_begin_twice_leaves_exactly_one_active_session(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        sessions = PostgresAppSessions(conn, ws)
        sessions.begin('ses-1', '1')
        sessions.begin('ses-2', '2')
        result = rows(conn, ws)
    assert short(result) == [('ses-1', 'ABANDONED', '1'), ('ses-2', 'ACTIVE', '2')]
    assert result[0][3] is not None and result[1][3] is None


@pytest.mark.parametrize('epoch', ['rec-1-ab', LEGACY_EPOCH, '', ' 1', '1\n', '-1', '1.5', '١٢', 1])
def test_begin_rejects_non_decimal_epoch_and_writes_nothing(pw_database, epoch):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        sessions = PostgresAppSessions(conn, ws)
        sessions.begin('ses-1', '1')
        with pytest.raises(OrchestrationContractError) as info:
            sessions.begin('ses-2', epoch)
        assert info.value.code == 'INVALID_RECOVERY_EPOCH'
        assert short(rows(conn, ws)) == [('ses-1', 'ACTIVE', '1')]


def test_begin_is_atomic_when_the_insert_fails(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        sessions = PostgresAppSessions(conn, ws)
        sessions.begin('ses-1', '1')
        with pytest.raises(psycopg.errors.UniqueViolation):
            sessions.begin('ses-1', '2')
        assert short(rows(conn, ws)) == [('ses-1', 'ACTIVE', '1')]


def test_end_marks_only_the_active_session_ended(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        sessions = PostgresAppSessions(conn, ws)
        sessions.begin('ses-1', '1')
        sessions.begin('ses-2', '2')
        sessions.end('ses-1')
        sessions.end('ses-absent')
        sessions.end('ses-2')
        result = rows(conn, ws)
    assert short(result) == [('ses-1', 'ABANDONED', '1'), ('ses-2', 'ENDED', '2')]
    assert result[1][3] is not None


def test_begin_never_touches_another_workspace(pw_database):
    ws = pw_database.workspace_id
    other = str(uuid.uuid4())
    with pw_database.connect() as conn:
        conn.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (other, 'pw-other', 'ACTIVE'))
        PostgresAppSessions(conn, ws).begin('ses-a', '1')
        PostgresAppSessions(conn, other).begin('ses-a', '5')
        PostgresAppSessions(conn, other).begin('ses-b', '6')
        assert short(rows(conn, ws)) == [('ses-a', 'ACTIVE', '1')]
        assert short(rows(conn, other)) == [('ses-a', 'ABANDONED', '5'), ('ses-b', 'ACTIVE', '6')]


def test_current_epoch_is_decimal_text_accepted_by_to_execution_grant(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        PostgresAppSessions(conn, ws).begin('ses-1', '7')
        current = PostgresRecoveryEpoch(conn, ws).current()
    assert current == '7'
    claims = GrantClaims(grant_id='g-1', stage_run_id='st-1', execution_generation=1, recovery_epoch=current, worker_lease_id='l-1', issued_at='2026-10-22T08:00:00Z', expires_at='2026-10-22T09:00:00Z', allowed_operation='render', input_fingerprint='fp')
    grant = to_execution_grant(claims, workspace_id=ws, job_id='job-1')
    assert grant.recovery_epoch == 7 and type(grant.recovery_epoch) is int


def test_app_session_source_has_no_forbidden_words():
    text = APP_SESSION_SOURCE.read_text(encoding='utf-8').lower()
    assert 'from src.' not in text and 'fake' not in text and 'mock' not in text


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('pw_g1_launcher', LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_deps(launcher, tmp_path, events, **over):
    def run(cmd, **kw):
        events.append(('run', cmd))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def spawn(cmd, **kw):
        events.append(('spawn', cmd, kw))
        return SimpleNamespace(pid=4242)

    def note(name):
        def record(*args):
            events.append((name, *args))
        return record

    def start_worker(app, layout):
        events.append(('start_worker',))
        return SimpleNamespace(stop=lambda: events.append(('worker_stopped',)))

    def make_cert(cert, key):
        cert.write_bytes(b'CERT')
        key.write_bytes(b'KEY')

    def load_app(env, layout):
        return SimpleNamespace(launch_url=lambda actor_id, ttl_seconds=60: 'https://127.0.0.1:8443/launch?cap=PW-G1')

    def serve_tls(app, *, port, certfile, keyfile, on_ready, should_stop):
        events.append(('serve_tls', port))

    deps = dataclasses.replace(
        launcher.default_deps({'AIAVC_DATA_DIR': str(tmp_path / 'data')}),
        run=run, spawn=spawn, out=lambda message: None, ask=lambda prompt='': '', sleep=lambda seconds: None,
        wait_tcp=lambda host, port, timeout: True, pid_alive=lambda pid: False,
        migrate=note('migrate'), ensure_identity=note('identity'),
        begin_session=note('begin_session'), end_session=note('end_session'),
        max_session_epoch=lambda dsn, workspace_id: 0,
        make_cert=make_cert, open_browser=lambda url: True,
        load_app=load_app, start_worker=start_worker, serve_tls=serve_tls,
        now=lambda: NOW, ensure_namespace=lambda host, port: 'EXISTS',
    )
    return dataclasses.replace(deps, **over) if over else deps


def layout_of(launcher, deps):
    layout = launcher.resolve_layout(deps.environ)
    layout.ensure_dirs()
    return layout


def epochs_of(layout):
    return [item['epoch'] for item in json.loads(layout.epoch_file.read_text(encoding='utf-8'))['history']]


def begun_epochs(events):
    return [event[4] for event in events if event[0] == 'begin_session']


def restore_args(layout):
    dump = layout.backups_dir / 'test.dump'
    dump.write_bytes(b'PGDMP-pw')
    return SimpleNamespace(file=str(dump), yes=True)


def write_legacy(layout):
    entry = {'epoch': LEGACY_EPOCH, 'restored_at': '2026-10-01T00:00:00+00:00', 'database': 'controlplane_20261001000000', 'source_sha256': 'x'}
    layout.epoch_file.write_text(json.dumps({'history': [entry]}), encoding='utf-8')


def test_start_begins_session_before_worker_and_serve_ends_it(launcher, tmp_path):
    events = []
    deps = build_deps(launcher, tmp_path, events)
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    env = next(event[2]['env'] for event in events if event[0] == 'spawn')
    assert launcher.cmd_serve(dataclasses.replace(deps, environ=env), SimpleNamespace()) == 0
    names = [event[0] for event in events]
    assert names.index('migrate') < names.index('identity') < names.index('begin_session') < names.index('spawn') < names.index('start_worker')
    assert names.index('serve_tls') < names.index('worker_stopped') < names.index('end_session')
    begin = next(event for event in events if event[0] == 'begin_session')
    end = next(event for event in events if event[0] == 'end_session')
    assert begin[1:] == (env['CONTROLPLANE_DSN'], env['CONTROLPLANE_WORKSPACE_ID'], env['AIAVC_SESSION_REF'], '1')
    assert end[1:] == begin[1:4]
    assert env['AIAVC_RECOVERY_EPOCH'] == '1'


def test_serve_keeps_session_active_when_serve_tls_fails(launcher, tmp_path):
    events = []

    def failing_serve(app, *, port, certfile, keyfile, on_ready, should_stop):
        raise RuntimeError('serve_tls failed')

    deps = build_deps(launcher, tmp_path, events, serve_tls=failing_serve)
    env = {**deps.environ, 'CONTROLPLANE_DSN': 'postgresql://u:p@127.0.0.1:1/db', 'CONTROLPLANE_WORKSPACE_ID': str(uuid.uuid4()), 'AIAVC_SESSION_REF': 'ses-x'}
    with pytest.raises(RuntimeError):
        launcher.cmd_serve(dataclasses.replace(deps, environ=env), SimpleNamespace())
    names = [event[0] for event in events]
    assert 'worker_stopped' in names and 'end_session' not in names


def test_restore_epoch_is_decimal_and_increments_by_one(launcher, tmp_path):
    events = []
    deps = build_deps(launcher, tmp_path, events)
    layout = layout_of(launcher, deps)
    args = restore_args(layout)
    seen = []
    for _ in range(3):
        assert launcher.cmd_restore(deps, args) == 0
        seen.append(epochs_of(layout)[-1])
    assert seen == ['1', '2', '3']


def test_restore_writes_epoch_before_switching_active_db(launcher, tmp_path, monkeypatch):
    events = []
    deps = build_deps(launcher, tmp_path, events)
    layout = layout_of(launcher, deps)
    args = restore_args(layout)
    written = []
    original = launcher.atomic_write_text

    def spy(path, text):
        written.append(Path(path).name)
        original(path, text)

    monkeypatch.setattr(launcher, 'atomic_write_text', spy)
    assert launcher.cmd_restore(deps, args) == 0
    assert written.index('recovery-epoch.json') < written.index('active-db')


def test_epoch_survives_stop_start_and_follows_restore(launcher, tmp_path):
    events = []
    deps = build_deps(launcher, tmp_path, events)
    layout = layout_of(launcher, deps)
    args = restore_args(layout)
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    assert launcher.cmd_restore(deps, args) == 0
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    assert begun_epochs(events) == ['1', '1', '2']
    assert epochs_of(layout) == ['1', '2']


def test_legacy_epoch_is_read_as_max_session_epoch_plus_one_on_start(launcher, tmp_path):
    events = []
    calls = []

    def max_epoch(dsn, workspace_id):
        calls.append(workspace_id)
        return 4

    deps = build_deps(launcher, tmp_path, events, max_session_epoch=max_epoch)
    layout = layout_of(launcher, deps)
    write_legacy(layout)
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    assert begun_epochs(events) == ['5', '5']
    assert len(calls) == 1
    last = json.loads(layout.epoch_file.read_text(encoding='utf-8'))['history'][-1]
    assert last['epoch'] == '5' and last['legacy_epoch'] == LEGACY_EPOCH


def test_legacy_epoch_is_read_as_max_session_epoch_plus_one_on_restore(launcher, tmp_path):
    events = []
    deps = build_deps(launcher, tmp_path, events, max_session_epoch=lambda dsn, workspace_id: 4)
    layout = layout_of(launcher, deps)
    write_legacy(layout)
    assert launcher.cmd_restore(deps, restore_args(layout)) == 0
    assert epochs_of(layout) == [LEGACY_EPOCH, '6']


def test_corrupt_epoch_file_fails_closed_without_side_effects(launcher, tmp_path):
    events = []
    deps = build_deps(launcher, tmp_path, events)
    layout = layout_of(launcher, deps)
    args = restore_args(layout)
    layout.epoch_file.write_text('{', encoding='utf-8')
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_restore(deps, args)
    assert not any(event[0] == 'run' and 'createdb' in event[1] for event in events)
    assert not layout.active_db_file.exists()
    with pytest.raises(launcher.LauncherError):
        launcher.cmd_start(deps, SimpleNamespace())
    assert not any(event[0] in ('begin_session', 'spawn') for event in events)
    assert layout.epoch_file.read_text(encoding='utf-8') == '{'


def test_default_deps_wire_the_session_functions(launcher):
    deps = launcher.default_deps({'AIAVC_DATA_DIR': 'x'})
    assert deps.begin_session is launcher.begin_session
    assert deps.end_session is launcher.end_session
    assert deps.max_session_epoch is launcher.max_session_epoch
