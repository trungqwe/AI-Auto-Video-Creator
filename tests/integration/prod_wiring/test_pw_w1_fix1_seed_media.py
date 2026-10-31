"""PW-W1-FIX1: launcher start tự sinh và nhập bộ media seed (idempotent); FFmpeg ghim thật, PostgreSQL thật.

coveredIds: PW-W1-FIX1-01
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from controlplane.application.storage_meta.handlers import verified_version_for_sha
from controlplane.infrastructure.db.uow import TransactionManager
from creative.adapters.hook_candidates import PostgresHookCandidates

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
HOOKS = json.loads((ROOT / 'tools' / 'launcher' / 'prod' / 'hooks.json').read_text(encoding='utf-8'))
FFMPEG = Path('C:/ffmpeg/bin/ffmpeg.exe')
NOW = datetime(2026, 10, 31, 1, 2, 3, tzinfo=timezone.utc)
POLICY_REVISION = 'safe-r1'
GROUPS = ('visual_hooks', 'audio_hooks', 'background_images')
SEED_FILES = [item['file_name'] for group in GROUPS for item in HOOKS[group]]
SEED_IDS = ['seed-' + item['id'] for item in HOOKS['background_images']]
SNAPSHOT = SimpleNamespace(snapshot_id='snap-1', source_refs=({'ref_type': 'article_revision', 'ref_id': 'article-1', 'revision_id': 'v1'},))
COUNT_TABLES = ('cp_sources', 'cp_media_assets', 'cp_hooks', 'cp_hook_revisions', 'cp_artifact_versions', 'cp_artifact_locations')


@pytest.fixture(scope='module')
def launcher():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location('pw_w1_fix1_launcher', LAUNCHER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


@pytest.fixture
def pinned_ffmpeg():
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: thiếu ffmpeg đã ghim tại C:/ffmpeg/bin/ffmpeg.exe', pytrace=False)


@pytest.fixture
def manager(pw_database):
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


def environ_for(tmp_path, **extra):
    return {'AIAVC_DATA_DIR': str(tmp_path / 'data'), **extra}


def run_seed_media(launcher, database, environ):
    assert callable(getattr(launcher, 'seed_media', None)), 'launcher.seed_media chưa có'
    layout = launcher.resolve_layout(environ)
    launcher.seed_media(database.dsn, database.workspace_id, layout, environ)
    return layout


def counts(database):
    with database.connect() as connection:
        return {table: connection.execute(f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s', (database.workspace_id,)).fetchone()[0] for table in COUNT_TABLES}


def seed_state(layout):
    seed_dir = layout.data_dir / 'seed'
    return {name: (seed_dir / name).stat().st_mtime_ns for name in (*SEED_FILES, 'seed-manifest.json')}


def seed_shas(layout):
    seed_dir = layout.data_dir / 'seed'
    return {name: hashlib.sha256((seed_dir / name).read_bytes()).hexdigest() for name in SEED_FILES}


def assert_deps_has_seed_media(launcher):
    assert 'seed_media' in {field.name for field in dataclasses.fields(launcher.Deps)}


def spy_deps(launcher, tmp_path, events):
    def note(name):
        def record(*args):
            events.append((name, *args))
        return record

    def spawn(cmd, **kw):
        events.append(('spawn', cmd))
        return SimpleNamespace(pid=4242)

    def make_cert(cert, key):
        events.append(('make_cert',))
        cert.write_bytes(b'CERT')
        key.write_bytes(b'KEY')

    return dataclasses.replace(
        launcher.default_deps({'AIAVC_DATA_DIR': str(tmp_path / 'data')}),
        run=lambda cmd, **kw: SimpleNamespace(returncode=0, stdout='', stderr=''),
        spawn=spawn, out=lambda message: None, ask=lambda prompt='': '', sleep=lambda seconds: None,
        wait_tcp=lambda host, port, timeout: True, pid_alive=lambda pid: False,
        migrate=note('migrate'), ensure_identity=note('identity'), begin_session=note('begin_session'),
        end_session=note('end_session'), max_session_epoch=lambda dsn, workspace_id: 0,
        make_cert=make_cert, open_browser=lambda url: True, now=lambda: NOW,
        ensure_namespace=lambda host, port: 'EXISTS', seed_defaults=note('seed_defaults'), seed_media=note('seed_media'),
    )


def test_start_calls_seed_media_once_after_the_seed_defaults_and_before_the_certificate_and_spawn(launcher, tmp_path):
    assert_deps_has_seed_media(launcher)
    assert launcher.default_deps({'AIAVC_DATA_DIR': str(tmp_path / 'data')}).seed_media is None
    events = []
    deps = spy_deps(launcher, tmp_path, events)
    assert launcher.cmd_start(deps, SimpleNamespace()) == 0
    names = [event[0] for event in events]
    assert names.count('seed_media') == 1
    assert names.index('begin_session') < names.index('seed_defaults') < names.index('seed_media') < names.index('make_cert') < names.index('spawn')
    identity = next(event for event in events if event[0] == 'identity')
    seed = next(event for event in events if event[0] == 'seed_media')
    assert seed[1:3] == (identity[1], identity[2])
    assert seed[3] == launcher.resolve_layout(deps.environ) and seed[4] == deps.environ


def test_a_failed_session_blocks_seed_media(launcher, tmp_path):
    assert_deps_has_seed_media(launcher)
    events = []

    def refuse(*args):
        raise RuntimeError('session refused')

    deps = dataclasses.replace(spy_deps(launcher, tmp_path, events), begin_session=refuse)
    with pytest.raises(RuntimeError):
        launcher.cmd_start(deps, SimpleNamespace())
    assert not any(event[0] in ('seed_media', 'spawn') for event in events)


def test_seed_media_on_an_empty_database_feeds_the_candidate_ports(launcher, pw_database, manager, pinned_ffmpeg, tmp_path):
    workspace_id = pw_database.workspace_id
    layout = run_seed_media(launcher, pw_database, environ_for(tmp_path))
    media = launcher.build_media_candidates(manager, workspace_id=workspace_id, safety_policy_revision=POLICY_REVISION)
    hooks = PostgresHookCandidates(launcher.open_hooks(manager), safety_policy_revision=POLICY_REVISION)
    candidates = media.media_candidates(workspace_id=workspace_id, snapshot=SNAPSHOT)
    assert [item.media_asset_id for item in candidates] == SEED_IDS
    for item in candidates:
        version = verified_version_for_sha(manager, workspace_id=workspace_id, sha256=item.provenance['sha256'])
        assert version is not None and version.artifact_version_id == item.artifact_version_ref
        assert str(uuid.UUID(item.artifact_version_ref)) == item.artifact_version_ref
    visual = hooks.visual_hook_candidates(workspace_id=workspace_id, snapshot_ref='snap-1')
    audio = hooks.audio_hook_candidates(workspace_id=workspace_id, snapshot_ref='snap-1')
    assert [item.hook_id for item in visual] == ['vh-0' + str(n) for n in range(1, 6)]
    assert [item.hook_id for item in audio] == ['ah-0' + str(n) for n in range(1, 6)]
    seed_dir = layout.data_dir / 'seed'
    assert sorted(path.name for path in seed_dir.iterdir()) == sorted([*SEED_FILES, 'seed-manifest.json'])
    assert len(SEED_FILES) == 22
    staged = sorted(path.name for path in (layout.staging_dir / 'media').iterdir())
    assert len(staged) == 22 and not [name for name in staged if name.endswith('.part')]
    assert counts(pw_database)['cp_sources'] == 0


def test_seed_media_reruns_without_regenerating_and_regenerates_a_deleted_file(launcher, pw_database, pinned_ffmpeg, tmp_path):
    environ = environ_for(tmp_path)
    layout = run_seed_media(launcher, pw_database, environ)
    first_state, first_shas, first_counts = seed_state(layout), seed_shas(layout), counts(pw_database)
    assert first_counts == {'cp_sources': 0, 'cp_media_assets': 22, 'cp_hooks': 10, 'cp_hook_revisions': 10, 'cp_artifact_versions': 22, 'cp_artifact_locations': 22}
    run_seed_media(launcher, pw_database, environ)
    assert seed_state(layout) == first_state
    assert counts(pw_database) == first_counts
    victim = layout.data_dir / 'seed' / HOOKS['background_images'][0]['file_name']
    victim.unlink()
    run_seed_media(launcher, pw_database, environ)
    assert victim.is_file()
    assert seed_shas(layout) == first_shas
    assert counts(pw_database) == first_counts
    victim.write_bytes(b'tampered')
    run_seed_media(launcher, pw_database, environ)
    assert seed_shas(layout) == first_shas
    assert counts(pw_database) == first_counts


def test_a_wrong_ffmpeg_pin_fails_with_a_launcher_error_and_writes_nothing(launcher, pw_database, tmp_path):
    assert callable(getattr(launcher, 'seed_media', None)), 'launcher.seed_media chưa có'
    fake = tmp_path / 'fake-ffmpeg.exe'
    fake.write_bytes(b'not the pinned ffmpeg')
    environ = environ_for(tmp_path, AIAVC_FFMPEG_PATH=str(fake))
    layout = launcher.resolve_layout(environ)
    with pytest.raises(launcher.LauncherError) as caught:
        launcher.seed_media(pw_database.dsn, pw_database.workspace_id, layout, environ)
    assert str(caught.value).startswith('Nạp media seed thất bại')
    assert pw_database.dsn not in str(caught.value)
    assert set(counts(pw_database).values()) == {0}
    assert not (layout.data_dir / 'seed').exists()
