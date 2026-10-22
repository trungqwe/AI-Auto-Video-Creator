from __future__ import annotations

'''ADAPT-SEED: kiểm sinh media seed và nhập nguồn, hook, tài sản qua dịch vụ ứng dụng trên PostgreSQL 18.6 dùng một lần.'''

import ast
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid
import wave

import psycopg
import pytest

from catalog.domain.identity import RightsStatus
from controlplane.api.wiring import production_profile as pp
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork

ROOT = Path(__file__).resolve().parents[4]
PROD = ROOT / 'tools' / 'launcher' / 'prod'
SEED_TOOLS = PROD / 'seed'
PROFILE_PATH = PROD / 'profile.json'
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
FFMPEG = Path('C:/ffmpeg/bin/ffmpeg.exe')
FFPROBE = Path('C:/ffmpeg/bin/ffprobe.exe')
HOOKS = json.loads((PROD / 'hooks.json').read_text(encoding='utf-8'))
SOURCES = json.loads((PROD / 'sources.json').read_text(encoding='utf-8'))['sources']
GROUPS = ('visual_hooks', 'audio_hooks', 'background_images')
SEED_FILES = [item['file_name'] for group in GROUPS for item in HOOKS[group]]
EMPTY_COUNTS = {'sources': 0, 'identities': 0, 'hooks': 0, 'hook_revisions': 0, 'assets': 0, 'provenance': 0}
FULL_COUNTS = {'sources': 7, 'identities': 7, 'hooks': 10, 'hook_revisions': 10, 'assets': 22, 'provenance': 22}


def load_tool(name):
    path = SEED_TOOLS / f'{name}.py'
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(f'adapt_seed_{name}', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def imported_modules(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.fixture(scope='module')
def seed_runs(tmp_path_factory):
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: thiếu ffmpeg đã ghim tại C:/ffmpeg/bin/ffmpeg.exe', pytrace=False)
    tool = load_tool('make_seed_media')
    runs = []
    for label in ('first', 'second'):
        out_dir = tmp_path_factory.mktemp('seed_' + label) / 'seed'
        lines = []
        shas = tool.generate_seed_media(out_dir, FFMPEG, emit=lines.append)
        runs.append(SimpleNamespace(dir=out_dir, shas=shas, lines=lines))
    return runs


@pytest.fixture
def database():
    dsn = os.environ.get('M2_TEST_PG_DSN', '')
    if not dsn:
        pytest.fail('BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN', pytrace=False)
    name = 'adapt_seed_' + uuid.uuid4().hex[:8]
    admin = psycopg.connect(dsn, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        new_dsn = dsn.rsplit('/', 1)[0] + '/' + name
        MigrationRunner(new_dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        workspace_id = str(uuid.uuid4())
        with psycopg.connect(new_dsn, autocommit=True) as seed:
            seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'w', 'ACTIVE'))
        yield (new_dsn, workspace_id)
    finally:
        try:
            admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        finally:
            admin.close()


@pytest.fixture
def manager(database):
    mgr = TransactionManager(database[0])
    try:
        yield mgr
    finally:
        mgr.close()


def make_runtime(tmp_path):
    return pp.ProductionRuntime(
        ffmpeg_path=tmp_path / 'bin' / 'ffmpeg.exe',
        ffprobe_path=tmp_path / 'bin' / 'ffprobe.exe',
        runtime_lock_path=tmp_path / 'runtime.lock.json',
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'model-weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={'revision': 'adapt-seed-test', 'unicode_form': 'NFC', 'casefold': True, 'edge_strip_categories': ('P',), 'gap_tolerance_ms': 500, 'min_confidence': 0.5},
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=SimpleNamespace(),
    )


def prod_config(tmp_path, workspace_id):
    return pp.WiringConfig(mode='production', workspace_id=workspace_id, profile=pp.load_production_profile(PROFILE_PATH), runtime=make_runtime(tmp_path))


class Resolver:
    '''DNS giả trả địa chỉ công khai; ghi lại host để chứng minh không có thao tác mạng nào khác.'''

    def __init__(self):
        self.hosts = []

    def __call__(self, host):
        self.hosts.append(host)
        return ['8.8.8.8']


COUNT_SQL = {
    'sources': 'cp_sources',
    'identities': 'cp_source_identities',
    'hooks': 'cp_hooks',
    'hook_revisions': 'cp_hook_revisions',
    'assets': 'cp_media_assets',
    'provenance': 'cp_media_provenance',
}


def counts(dsn, workspace_id):
    ws = uuid.UUID(workspace_id)
    with psycopg.connect(dsn, autocommit=True) as conn:
        return {key: conn.execute(f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s', (ws,)).fetchone()[0] for key, table in COUNT_SQL.items()}


def import_once(tool, manager, database, tmp_path, seed_dir, resolver=None, **kwargs):
    config = prod_config(tmp_path, database[1])
    return tool.import_seed(manager, config, seed_dir, resolver=resolver or Resolver(), **kwargs)


def test_seed_media_sha256_is_stable_between_runs(seed_runs):
    first, second = seed_runs
    assert sorted(first.shas) == sorted(SEED_FILES) and len(first.shas) == 22
    assert len(set(first.shas.values())) == 22
    assert first.shas == second.shas
    assert first.dir != second.dir
    for run in seed_runs:
        for name, sha in run.shas.items():
            assert hashlib.sha256((run.dir / name).read_bytes()).hexdigest() == sha


def test_seed_media_prints_sha256_per_file(seed_runs):
    first = seed_runs[0]
    printed = {}
    for line in first.lines:
        match = re.fullmatch(r'([0-9a-f]{64})  ([^ ]+)', line)
        assert match, line
        printed[match.group(2)] = match.group(1)
    assert printed == first.shas
    manifest = json.loads((first.dir / 'seed-manifest.json').read_text(encoding='utf-8'))
    assert sorted(manifest) == sorted(item['id'] for group in GROUPS for item in HOOKS[group])


def test_seed_media_formats(seed_runs):
    first = seed_runs[0]
    for item in HOOKS['background_images']:
        data = (first.dir / item['file_name']).read_bytes()
        assert data[:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        assert struct.unpack('>IIBB', data[16:26]) == (1080, 1920, 8, 2)
    for item in HOOKS['audio_hooks']:
        with wave.open(str(first.dir / item['file_name']), 'rb') as handle:
            assert (handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getnframes()) == (1, 2, 24000, 36000)
    for item in HOOKS['visual_hooks']:
        probe = subprocess.run([str(FFPROBE), '-v', 'error', '-print_format', 'json', '-show_streams', str(first.dir / item['file_name'])], capture_output=True, text=True, check=True, timeout=60)
        stream = json.loads(probe.stdout)['streams'][0]
        assert (stream['codec_name'], stream['width'], stream['height'], stream['r_frame_rate']) == ('h264', 1080, 1920, '30/1')
        assert 2.9 <= float(stream['duration']) <= 3.1


def test_make_seed_media_is_stdlib_only_without_network():
    path = SEED_TOOLS / 'make_seed_media.py'
    roots = {name.split('.')[0] for name in imported_modules(path)}
    assert roots <= {'__future__', 'argparse', 'colorsys', 'hashlib', 'json', 'math', 'os', 'pathlib', 'struct', 'subprocess', 'sys', 'wave', 'zlib'}
    assert {'wave', 'zlib'} <= roots
    assert 'lavfi' in path.read_text(encoding='utf-8')


def test_seed_dir_is_outside_git_tree(tmp_path, monkeypatch):
    tool = load_tool('make_seed_media')
    assert HOOKS['storage']['in_git'] is False
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    default = tool.resolve_seed_dir()
    assert default == (tmp_path / 'AIAutoVideoCreator' / 'seed').resolve()
    assert ROOT not in default.parents
    with pytest.raises(tool.SeedError):
        tool.resolve_seed_dir(ROOT / 'tmp-seed-base')
    with pytest.raises(tool.SeedError):
        tool.generate_seed_media(ROOT / 'tmp-seed-out', FFMPEG)
    assert not (ROOT / 'tmp-seed-out').exists()
    leftovers = [p for p in SEED_TOOLS.rglob('*') if p.is_file() and p.suffix.lower() in {'.png', '.wav', '.mp4'}]
    assert leftovers == []


def test_ffmpeg_pin_mismatch_is_rejected_before_any_output(tmp_path):
    tool = load_tool('make_seed_media')
    lock = tmp_path / 'runtime.lock.json'
    lock.write_text(json.dumps({'pins': {'ffmpeg': {'sha256': '0' * 64, 'status': 'PINNED'}}}), encoding='utf-8')
    with pytest.raises(tool.SeedError):
        tool.generate_seed_media(tmp_path / 'seed', FFMPEG, runtime_lock_path=lock)
    assert not (tmp_path / 'seed').exists()


def test_import_seed_twice_does_not_duplicate_rows(manager, database, seed_runs, tmp_path, monkeypatch):
    tool = load_tool('import_seed')

    def refuse(self, request):
        raise AssertionError('feed fetch over the network is forbidden')

    monkeypatch.setattr(RealHttpTransport, 'send', refuse)
    assert counts(database[0], database[1]) == EMPTY_COUNTS
    resolver = Resolver()
    first = import_once(tool, manager, database, tmp_path, seed_runs[0].dir, resolver)
    after_first = counts(database[0], database[1])
    assert after_first == FULL_COUNTS
    assert (first.sources_registered, first.hooks_imported, first.assets_new) == (7, 10, 22)
    second = import_once(tool, manager, database, tmp_path, seed_runs[1].dir, resolver)
    assert counts(database[0], database[1]) == after_first
    assert (second.sources_registered, second.sources_replayed) == (0, 7)
    assert (second.hooks_imported, second.hooks_existing) == (0, 10)
    assert (second.assets_new, second.assets_existing) == (0, 22)
    assert set(resolver.hosts) == {urlsplit(s['url']).hostname for s in SOURCES}


def test_sources_registered_with_tier_and_https(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    import_once(tool, manager, database, tmp_path, seed_runs[0].dir)
    with PostgresSourceIngestionUnitOfWork(manager, workspace_id=database[1]) as uow:
        stored = uow.sources.list_sources(database[1])
    assert len(stored) == 7
    assert all(s.canonical_locator.startswith('https://') for s in stored)
    assert {s.canonical_locator: s.tier for s in stored} == {s['url']: s['tier'] for s in SOURCES}
    assert {s.source_kind for s in stored} == {'rss_feed'}
    assert {s.status.value for s in stored} == {'ACTIVE'}


def test_assets_and_hooks_keep_rights_and_provenance(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    report = import_once(tool, manager, database, tmp_path, seed_runs[0].dir)
    assert report.article_image_rights_status == 'UNVERIFIED'
    assert HOOKS['rights']['article_images_in_sample_video'] is False
    ws = uuid.UUID(database[1])
    with psycopg.connect(database[0], autocommit=True) as conn:
        rows = conn.execute('SELECT payload, discovery_id FROM controlplane.cp_media_assets WHERE workspace_id = %s', (ws,)).fetchall()
        assert {row[0]['rights']['status'] for row in rows} == {RightsStatus.UNKNOWN.value}
        assert sorted(row[0]['kind'] for row in rows) == ['audio'] * 5 + ['clip'] * 5 + ['image'] * 12
        assert {row[1] for row in rows} == {'adapt-seed:' + item['id'] for group in GROUPS for item in HOOKS[group]}
        relations = conn.execute('SELECT DISTINCT relation FROM controlplane.cp_media_provenance WHERE workspace_id = %s', (ws,)).fetchall()
        assert relations == [('user_imported',)]
        kinds = conn.execute('SELECT kind, count(*) FROM controlplane.cp_hooks WHERE workspace_id = %s GROUP BY kind ORDER BY kind', (ws,)).fetchall()
        assert kinds == [('audio_hook', 5), ('visual_hook', 5)]
        refs = conn.execute('SELECT hook_id, artifact_version_ref FROM controlplane.cp_hook_revisions WHERE workspace_id = %s', (ws,)).fetchall()
        assert len(refs) == 10 and all(ref.startswith('seed:' + hook_id + ':sha256:') for hook_id, ref in refs)


def test_http_source_is_rejected_before_any_write(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    bad = tmp_path / 'sources.json'
    bad.write_text(json.dumps({'sources': [{**SOURCES[0], 'url': 'http://feeds.bbci.co.uk/news/world/rss.xml'}]}), encoding='utf-8')
    with pytest.raises(tool.SeedError):
        import_once(tool, manager, database, tmp_path, seed_runs[0].dir, sources_path=bad)
    assert counts(database[0], database[1]) == EMPTY_COUNTS


def test_missing_media_is_rejected_before_any_write(manager, database, tmp_path):
    tool = load_tool('import_seed')
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(tool.SeedError):
        import_once(tool, manager, database, tmp_path, empty)
    assert counts(database[0], database[1]) == EMPTY_COUNTS


def test_non_production_profile_is_rejected(tmp_path):
    tool = load_tool('import_seed')
    config = pp.WiringConfig(mode='test', workspace_id=str(uuid.uuid4()), profile=None, runtime=None)
    with pytest.raises(tool.SeedError):
        tool.import_seed(None, config, tmp_path)


def test_import_seed_uses_application_services_only():
    path = SEED_TOOLS / 'import_seed.py'
    text = path.read_text(encoding='utf-8')
    assert 'register_discovery' in text and 'import_hook' in text and 'register_source' in text
    assert 'urllib' not in text and 'INSERT INTO' not in text and 'import psycopg' not in text
    modules = imported_modules(path)
    banned = {'urllib', 'http', 'requests', 'httpx', 'socket', 'fastapi', 'starlette', 'uvicorn'}
    assert not [m for m in modules if m.split('.')[0] in banned]
    assert not [m for m in modules if m.startswith('src.') or 'test_driver' in m]
