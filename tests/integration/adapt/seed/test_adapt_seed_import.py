from __future__ import annotations

'''ADAPT-SEED: kiểm sinh media seed và nhập nguồn, hook, tài sản qua dịch vụ ứng dụng trên PostgreSQL 18.6 dùng một lần.'''

import ast
from decimal import Decimal
import hashlib
import importlib.util
import json
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
from controlplane.application.storage_meta.handlers import STAGED_HOOK_EXTENSIONS, verified_version_for_sha
from controlplane.infrastructure.db.uow import TransactionManager
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork

ROOT = Path(__file__).resolve().parents[4]
PROD = ROOT / 'tools' / 'launcher' / 'prod'
SEED_TOOLS = PROD / 'seed'
PROFILE_PATH = PROD / 'profile.json'
PW_CONFTEST = ROOT / 'tests' / 'integration' / 'prod_wiring' / 'conftest.py'
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


def load_pw_harness():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location('adapt_seed_pw_harness', PW_CONFTEST)
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
def pw_database():
    with load_pw_harness().pw_temp_database() as harness_db:
        yield harness_db


@pytest.fixture
def database(pw_database):
    return (pw_database.dsn, pw_database.workspace_id)


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


BACKGROUNDS = [item['file_name'] for item in HOOKS['background_images']]
ARTIFACT_COUNT_SQL = {'versions': 'cp_artifact_versions', 'locations': 'cp_artifact_locations'}


def artifact_counts(dsn, workspace_id):
    ws = uuid.UUID(workspace_id)
    with psycopg.connect(dsn, autocommit=True) as conn:
        return {key: conn.execute(f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s', (ws,)).fetchone()[0] for key, table in ARTIFACT_COUNT_SQL.items()}


def staged_media(tmp_path):
    return tmp_path / 'staging' / 'media'


def verified_ids(manager, workspace_id, shas):
    found = {}
    for name in BACKGROUNDS:
        version = verified_version_for_sha(manager, workspace_id=workspace_id, sha256=shas[name])
        assert version is not None, name
        found[name] = version.artifact_version_id
    return found


HOOK_FILES = [item['file_name'] for group in ('visual_hooks', 'audio_hooks') for item in HOOKS[group]]
HOOK_FILE_BY_ID = {item['id']: item['file_name'] for group in ('visual_hooks', 'audio_hooks') for item in HOOKS[group]}
STAGED_TOTAL = {'versions': 22, 'locations': 22}


def hook_versions(manager, workspace_id, shas):
    found = {}
    for name in HOOK_FILES:
        version = verified_version_for_sha(manager, workspace_id=workspace_id, sha256=shas[name], extensions=STAGED_HOOK_EXTENSIONS)
        assert version is not None, name
        found[name] = version.artifact_version_id
    return found


def hook_revisions(dsn, workspace_id):
    ws = uuid.UUID(workspace_id)
    with psycopg.connect(dsn, autocommit=True) as conn:
        return conn.execute("SELECT hook_id, revision, artifact_version_ref, payload->'technical_metadata' FROM controlplane.cp_hook_revisions WHERE workspace_id = %s ORDER BY hook_id, revision", (ws,)).fetchall()


def test_background_images_are_staged_and_registered_as_verified_versions(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    run = seed_runs[0]
    assert len(BACKGROUNDS) == 12 and artifact_counts(database[0], database[1]) == {'versions': 0, 'locations': 0}
    import_once(tool, manager, database, tmp_path, run.dir)
    for name in BACKGROUNDS:
        sha = run.shas[name]
        staged = staged_media(tmp_path) / f'{sha}.png'
        assert staged.is_file() and staged.read_bytes() == (run.dir / name).read_bytes()
        version = verified_version_for_sha(manager, workspace_id=database[1], sha256=sha)
        assert version is not None
        assert (version.artifact_id, version.owner_ref, version.retention_ref) == (f'media/{sha}.png', 'adapt-seed', 'durable')
    assert artifact_counts(database[0], database[1]) == STAGED_TOTAL
    assert sorted(p.name for p in staged_media(tmp_path).iterdir()) == sorted(f'{run.shas[n]}{Path(n).suffix.lower()}' for n in SEED_FILES)


def test_rerun_keeps_one_version_and_one_location_per_background_image(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    import_once(tool, manager, database, tmp_path, seed_runs[0].dir)
    first_ids = verified_ids(manager, database[1], seed_runs[0].shas)
    before = artifact_counts(database[0], database[1])
    second = import_once(tool, manager, database, tmp_path, seed_runs[1].dir)
    assert (second.assets_new, second.assets_existing) == (0, 22)
    assert verified_ids(manager, database[1], seed_runs[1].shas) == first_ids
    assert artifact_counts(database[0], database[1]) == before == STAGED_TOTAL
    assert not list(staged_media(tmp_path).glob('*.part'))


def test_rerun_registers_backgrounds_for_assets_that_already_exist(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    run = seed_runs[0]
    tool._import_items(manager, database[1], tool._collect_items(HOOKS, run.dir))
    assert counts(database[0], database[1])['assets'] == 22
    assert artifact_counts(database[0], database[1]) == {'versions': 0, 'locations': 0}
    first = BACKGROUNDS[0]
    assert verified_version_for_sha(manager, workspace_id=database[1], sha256=run.shas[first]) is None
    staged_media(tmp_path).mkdir(parents=True)
    broken = staged_media(tmp_path) / f'{run.shas[first]}.png'
    broken.write_bytes(b'partial')
    report = import_once(tool, manager, database, tmp_path, run.dir)
    assert (report.assets_new, report.assets_existing) == (0, 22)
    assert broken.read_bytes() == (run.dir / first).read_bytes()
    verified_ids(manager, database[1], run.shas)
    assert artifact_counts(database[0], database[1]) == STAGED_TOTAL
    assert counts(database[0], database[1]) == FULL_COUNTS


def test_hooks_are_staged_and_registered_as_verified_versions(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    run = seed_runs[0]
    assert len(HOOK_FILES) == 10 and artifact_counts(database[0], database[1]) == {'versions': 0, 'locations': 0}
    import_once(tool, manager, database, tmp_path, run.dir)
    for name in HOOK_FILES:
        sha = run.shas[name]
        suffix = Path(name).suffix.lower()
        staged = staged_media(tmp_path) / f'{sha}{suffix}'
        assert staged.is_file() and staged.read_bytes() == (run.dir / name).read_bytes()
        version = verified_version_for_sha(manager, workspace_id=database[1], sha256=sha, extensions=STAGED_HOOK_EXTENSIONS)
        assert version is not None, name
        assert (version.artifact_id, version.owner_ref, version.retention_ref) == (f'media/{sha}{suffix}', 'adapt-seed', 'durable')
    assert artifact_counts(database[0], database[1]) == STAGED_TOTAL


def test_rerun_keeps_one_version_and_one_location_per_hook(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    import_once(tool, manager, database, tmp_path, seed_runs[0].dir)
    first_ids = hook_versions(manager, database[1], seed_runs[0].shas)
    before = artifact_counts(database[0], database[1])
    revisions_before = hook_revisions(database[0], database[1])
    second = import_once(tool, manager, database, tmp_path, seed_runs[1].dir)
    assert (second.hooks_imported, second.hooks_existing) == (0, 10)
    assert hook_versions(manager, database[1], seed_runs[1].shas) == first_ids
    assert artifact_counts(database[0], database[1]) == before == STAGED_TOTAL
    assert hook_revisions(database[0], database[1]) == revisions_before
    assert not list(staged_media(tmp_path).glob('*.part'))


def test_rerun_registers_hooks_that_already_exist_without_new_hook_revision(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    run = seed_runs[0]
    tool._import_items(manager, database[1], tool._collect_items(HOOKS, run.dir))
    assert counts(database[0], database[1])['hooks'] == 10
    assert artifact_counts(database[0], database[1]) == {'versions': 0, 'locations': 0}
    first = HOOK_FILES[0]
    assert verified_version_for_sha(manager, workspace_id=database[1], sha256=run.shas[first], extensions=STAGED_HOOK_EXTENSIONS) is None
    revisions_before = hook_revisions(database[0], database[1])
    report = import_once(tool, manager, database, tmp_path, run.dir)
    assert (report.hooks_imported, report.hooks_existing) == (0, 10)
    hook_versions(manager, database[1], run.shas)
    assert artifact_counts(database[0], database[1]) == STAGED_TOTAL
    assert hook_revisions(database[0], database[1]) == revisions_before
    assert counts(database[0], database[1]) == FULL_COUNTS


def test_hook_revisions_keep_artifact_version_ref_and_media_sha256(manager, database, seed_runs, tmp_path):
    tool = load_tool('import_seed')
    run = seed_runs[0]
    import_once(tool, manager, database, tmp_path, run.dir)
    rows = hook_revisions(database[0], database[1])
    assert sorted(row[0] for row in rows) == sorted(HOOK_FILE_BY_ID)
    for hook_id, revision, ref, technical in rows:
        sha = run.shas[HOOK_FILE_BY_ID[hook_id]]
        assert ref == 'seed:' + hook_id + ':sha256:' + sha
        assert {pair[0]: pair[1] for pair in technical}['media_sha256'] == sha


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
    assert HOOKS['rights']['article_images_in_sample_video'] is True
    assert 'pending_user_checkpoint' not in HOOKS['rights']
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
    assert 'register_discovery' in text and 'import_hook' in text and 'register_source' in text and 'register_staged_artifact' in text
    assert 'urllib' not in text and 'INSERT INTO' not in text and 'import psycopg' not in text
    modules = imported_modules(path)
    banned = {'urllib', 'http', 'requests', 'httpx', 'socket', 'fastapi', 'starlette', 'uvicorn'}
    assert not [m for m in modules if m.split('.')[0] in banned]
    assert not [m for m in modules if m.startswith('src.') or 'test_driver' in m]
