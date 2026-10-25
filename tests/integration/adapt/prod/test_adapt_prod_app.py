"""Kiểm ADAPT-PROD: hồ sơ production của src/main.py, ASGI loopback TLS, capability một lần và worker Temporal."""
from __future__ import annotations

import ast
import asyncio
import datetime
from decimal import Decimal
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient
import psycopg
import pytest

from controlplane.domain.orchestration.workflow_catalog import WORKFLOW_NAMES
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).resolve().parents[4]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
MAIN_PATH = ROOT / 'src' / 'main.py'
DIST = ROOT / 'src' / 'controlplane' / 'ui' / 'dist'
ACTOR_ID = '00000000-0000-0000-0000-0000000008a2'
PORT = 8443
BASE = f'https://127.0.0.1:{PORT}'
SERVICE_NAMES = {'collection', 'config_security', 'creative', 'render', 'storage', 'voice'}


def wiring(name: str):
    return importlib.import_module('controlplane.api.wiring.' + name)


def load_main(monkeypatch):
    spec = importlib.util.spec_from_file_location('adapt_prod_src_main', MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def make_runtime(tmp_path):
    pp = wiring('production_profile')
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
        tokenization={
            'revision': 'adapt-wire-test',
            'unicode_form': 'NFC',
            'casefold': True,
            'edge_strip_categories': ('P',),
            'gap_tolerance_ms': 500,
            'min_confidence': 0.5,
        },
        drive_placement={
            'original': 'folder-original',
            'reusable': 'folder-reusable',
            'output': 'folder-output',
        },
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=SimpleNamespace(),
    )


def runtime_factory(tmp_path):
    return lambda profile: make_runtime(tmp_path)


def prod_env(dsn, workspace_id, profile_path=None):
    env = {
        'CONTROLPLANE_DSN': dsn,
        'CONTROLPLANE_PORT': str(PORT),
        'CONTROLPLANE_PROFILE': 'production',
        'CONTROLPLANE_WORKSPACE_ID': workspace_id,
    }
    if profile_path is not None:
        env['CONTROLPLANE_PROFILE_PATH'] = str(profile_path)
    return env


def profile_copy(tmp_path, leaf):
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    parts = leaf.split('.')
    parent = data
    for part in parts[:-1]:
        parent = parent[part]
    del parent[parts[-1]]
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def database():
    dsn = os.environ.get('M2_TEST_PG_DSN', '')
    if not dsn:
        pytest.fail('BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN', pytrace=False)
    name = 'adapt_prod_' + uuid.uuid4().hex[:8]
    admin = psycopg.connect(dsn, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        new_dsn = dsn.rsplit('/', 1)[0] + '/' + name
        MigrationRunner(new_dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        workspace_id = str(uuid.uuid4())
        with psycopg.connect(new_dsn, autocommit=True) as seed:
            seed.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace_id, 'w', 'ACTIVE'))
            seed.execute('INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s, %s, %s, %s, %s)', (ACTOR_ID, workspace_id, 'user', 'prod-test', 'ACTIVE'))
        yield (new_dsn, workspace_id)
    finally:
        try:
            admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        finally:
            admin.close()


@pytest.fixture
def stub_manager():
    created = []

    class StubManager:
        def __init__(self, dsn):
            self.dsn = dsn
            self.closed = False
            created.append(self)

        def unit_of_work(self):
            raise RuntimeError('stub manager has no database')

        def borrow_connection(self):
            raise RuntimeError('stub manager has no database')

        def close(self):
            self.closed = True

    return created, StubManager


@pytest.fixture
def manager(database):
    mgr = TransactionManager(database[0])
    try:
        yield mgr
    finally:
        mgr.close()


@pytest.fixture
def config(database, tmp_path):
    pp = wiring('production_profile')
    return pp.WiringConfig(mode='production', workspace_id=database[1], profile=pp.load_production_profile(PROFILE_PATH), runtime=make_runtime(tmp_path))


@pytest.fixture
def app(manager, config):
    return wiring('production').build_production_app(manager=manager, config=config, port=PORT)


def client(app):
    return TestClient(app, base_url=BASE, follow_redirects=False)


def launch_path(app, ttl=60):
    return app.launch_url(actor_id=ACTOR_ID, ttl_seconds=ttl)[len(BASE):]


def cookie_value(response, name):
    for header in response.headers.get_list('set-cookie'):
        if header.startswith(name + '='):
            return header.split(';', 1)[0].split('=', 1)[1]
    raise AssertionError('missing cookie ' + name)


LEAVES = ['budget.hard_stop', 'ai.route_endpoint', 'workflow.schedule', 'drive.chunk_bytes', 'collection.fetch_policy.feed']


def patched_main(monkeypatch, stub_manager):
    created, stub = stub_manager
    main = load_main(monkeypatch)
    monkeypatch.setattr(main, 'TransactionManager', stub)
    return main, created


@pytest.mark.parametrize('leaf', LEAVES)
def test_missing_profile_leaf_does_not_start(leaf, tmp_path, monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)
    env = prod_env('postgresql://u@h/d', str(uuid.uuid4()), profile_copy(tmp_path, leaf))
    with pytest.raises(wiring('production_profile').ProductionProfileError) as info:
        main.build_app(env)
    assert info.value.parameter == leaf
    assert created == []


def test_missing_workspace_does_not_start(monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)
    with pytest.raises(wiring('production_profile').ProductionProfileError) as info:
        main.build_app(prod_env('postgresql://u@h/d', ''))
    assert info.value.parameter == 'CONTROLPLANE_WORKSPACE_ID'
    assert created == []


def test_missing_runtime_does_not_start(monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)
    with pytest.raises(wiring('production_profile').ProductionProfileError) as info:
        main.build_app(prod_env('postgresql://u@h/d', str(uuid.uuid4())))
    assert info.value.parameter == 'runtime'
    assert created == []


def test_invalid_workspace_and_runtime_do_not_start(tmp_path, monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)
    error = wiring('production_profile').ProductionProfileError
    with pytest.raises(error) as info:
        main.build_app(prod_env('postgresql://u@h/d', 'not-a-uuid'), runtime_factory=runtime_factory(tmp_path))
    assert info.value.parameter == 'workspace_id'
    with pytest.raises(error) as info:
        main.build_app(prod_env('postgresql://u@h/d', str(uuid.uuid4())), runtime_factory=lambda profile: object())
    assert info.value.parameter == 'runtime'
    assert created == []


def test_test_profile_is_default_and_unknown_profile_is_rejected(monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)
    assert main.read_config({'CONTROLPLANE_DSN': 'postgresql://u@h/d'}).profile == 'test'
    with pytest.raises(ValueError, match='CONTROLPLANE_PROFILE must be test or production'):
        main.read_config({'CONTROLPLANE_DSN': 'postgresql://u@h/d', 'CONTROLPLANE_PROFILE': 'staging'})
    built = main.build_app({'CONTROLPLANE_DSN': 'postgresql://u@h/d'})
    assert built.state.module_services == {}
    assert len(created) == 1


def test_builder_failure_closes_manager(tmp_path, monkeypatch, stub_manager):
    main, created = patched_main(monkeypatch, stub_manager)

    def boom(manager, config):
        raise RuntimeError('builder failed')

    monkeypatch.setattr(wiring('production'), 'build_voice_services', boom)
    with pytest.raises(RuntimeError, match='builder failed'):
        main.build_app(prod_env('postgresql://u@h/d', str(uuid.uuid4())), runtime_factory=runtime_factory(tmp_path))
    assert len(created) == 1 and created[0].closed is True


def test_production_profile_builds_app_on_postgres(database, tmp_path, monkeypatch):
    main = load_main(monkeypatch)
    built = main.build_app(prod_env(database[0], database[1]), runtime_factory=runtime_factory(tmp_path))
    try:
        assert isinstance(built, wiring('production').ProductionApp)
        assert set(built.services) == SERVICE_NAMES
        assert built.services['collection'].mode == 'production'
        assert set(built.api_app.state.module_services) == {'sources', 'hooks'}
        assert built.api_app.state.allowed_origins == {f'https://127.0.0.1:{PORT}', f'https://localhost:{PORT}'}
    finally:
        built.manager.close()


def test_test_driver_routes_return_404(app):
    c = client(app)
    assert c.get('/test-driver/health').status_code == 404
    assert c.post('/test-driver/issue-capability').status_code == 404
    assert c.post('/test-driver/advance-operation', json={}).status_code == 404


def test_launch_exchanges_capability_once(app):
    path = launch_path(app)
    first = client(app).get(path)
    assert first.status_code == 303 and first.headers['location'] == '/'
    cookies = {h.split('=', 1)[0]: h.lower() for h in first.headers.get_list('set-cookie')}
    assert 'httponly' in cookies['cp_session'] and 'secure' in cookies['cp_session'] and 'samesite=strict' in cookies['cp_session']
    assert 'secure' in cookies['csrf_token']
    assert client(app).get(path).status_code == 403


def test_launch_session_authorizes_v1_requests(app):
    assert client(app).get('/v1/sources?limit=1').status_code == 403
    token = cookie_value(client(app).get(launch_path(app)), 'cp_session')
    headers = {'Cookie': 'cp_session=' + token}
    ok = client(app).get('/v1/sources?limit=1', headers=headers)
    assert ok.status_code == 200 and ok.json() == {'items': [], 'next_cursor': None}
    hooks = client(app).get('/v1/hooks?limit=1', headers=headers)
    assert hooks.status_code == 200 and hooks.json() == {'items': [], 'next_cursor': None}
    media = client(app).get('/v1/media?limit=1', headers=headers)
    assert media.status_code == 503 and media.json()['code'] == 'CAPABILITY_UNAVAILABLE'
    assert client(app).get('/v1/secrets/secret-1', headers=headers).status_code in (404, 405)


def test_sources_listed_and_updated_through_v1_on_postgres(app, config, database):
    production = wiring('production')
    from source_ingestion.application.source_commands import SourceCommandHandler
    policy = production._source_policy(config)
    handler = SourceCommandHandler(uow=app.services['collection'].uow_factory(), policy_provider=lambda workspace_id: policy,
                                   resolver=lambda host: ('93.184.216.34',), recovery_epoch='adapt-prod-test-1')
    handler.register_source(workspace_id=database[1], idempotency_key='seed-1', actor=ACTOR_ID, correlation_id='seed',
                            locator='https://news.example.com/feed.xml', name='feed-1',
                            source_kind=config.profile.collection.source_kinds[0], tier='tier_1', topics=('news',))
    launched = client(app).get(launch_path(app))
    session, csrf = cookie_value(launched, 'cp_session'), cookie_value(launched, 'csrf_token')
    base = {'Cookie': f'cp_session={session}; csrf_token={csrf}', 'X-CSRF-Token': csrf, 'Origin': BASE}
    c = client(app)
    items = c.get('/v1/sources', headers=base).json()['items']
    assert len(items) == 1 and 'canonical_locator' not in items[0] and items[0]['name'] == 'feed-1'
    path = '/v1/sources/' + items[0]['source_id']
    assert c.get(path, headers=base).json() == items[0]
    def patch(body, key, rev, target=path):
        return c.patch(target, json=body, headers={**base, 'Idempotency-Key': key, 'If-Match': str(rev)})
    done = patch({'topic_tags': ['news', 'ai'], 'enabled': False}, 'k-1', 1)
    assert done.status_code == 200 and done.json()['revision'] == 2 and done.json()['enabled'] is False
    assert done.json()['topic_tags'] == ['ai', 'news']
    assert patch({'topic_tags': ['news', 'ai'], 'enabled': False}, 'k-1', 1).json()['revision'] == 2
    assert patch({'notes': 'x'}, 'k-2', 1).status_code == 409
    reused = patch({'notes': 'x'}, 'k-1', 1)
    assert reused.status_code == 409 and reused.json()['code'] == 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
    assert patch({'notes': 'x'}, 'k-3', 1, '/v1/sources/does-not-exist').status_code == 404
    assert patch({'tier': 'tier_9'}, 'k-4', 2).status_code == 422


def test_hooks_listed_and_updated_through_v1_on_postgres(app, manager, database):
    from catalog.application.hooks import import_hook
    from catalog.domain.hooks import HookKind
    from catalog.persistence.hooks import PostgresHookHistory
    with manager.unit_of_work() as uow:
        history = PostgresHookHistory(uow.connection, database[1])
        import_hook(history, hook_id='hook-1', kind=HookKind.VISUAL_HOOK, artifact_version_ref='av-1', tags=('sports',), description='d', note='n')
        import_hook(history, hook_id='hook-2', kind=HookKind.AUDIO_HOOK, artifact_version_ref='av-2', tags=(), enabled=False)
    launched = client(app).get(launch_path(app))
    session, csrf = cookie_value(launched, 'cp_session'), cookie_value(launched, 'csrf_token')
    base = {'Cookie': f'cp_session={session}; csrf_token={csrf}', 'X-CSRF-Token': csrf, 'Origin': BASE}
    c = client(app)
    items = c.get('/v1/hooks', headers=base).json()['items']
    assert [i['hook_id'] for i in items] == ['hook-1', 'hook-2']
    assert set(items[0]) == {'hook_id', 'kind', 'tags', 'description', 'enabled', 'notes', 'revision', 'updated_at'}
    assert items[0]['tags'] == ['sports'] and items[0]['notes'] == 'n' and items[1]['tags'] == [] and items[1]['enabled'] is False
    assert [i['hook_id'] for i in c.get('/v1/hooks?kind=audio_hook', headers=base).json()['items']] == ['hook-2']
    assert [i['hook_id'] for i in c.get('/v1/hooks?enabled=true', headers=base).json()['items']] == ['hook-1']
    assert c.get('/v1/hooks?enabled=maybe', headers=base).status_code == 422
    path = '/v1/hooks/hook-1'
    assert c.get(path, headers=base).json() == items[0]
    assert c.get('/v1/hooks/missing', headers=base).status_code == 404
    def patch(body, key, rev, target=path):
        return c.patch(target, json=body, headers={**base, 'Idempotency-Key': key, 'If-Match': str(rev)})
    done = patch({'tags': ['sports', 'goal'], 'notes': 'x'}, 'k-1', 1)
    assert done.status_code == 200 and done.json()['revision'] == 2 and done.json()['tags'] == ['sports', 'goal'] and done.json()['notes'] == 'x'
    replay = patch({'tags': ['sports', 'goal'], 'notes': 'x'}, 'k-1', 1)
    assert replay.status_code == 409 and replay.json()['code'] == 'REVISION_CONFLICT'
    assert patch({'notes': 'y'}, 'k-2', 1).status_code == 409
    assert patch({'notes': 'x'}, 'k-3', 2).status_code == 422
    assert patch({'enabled': 'yes'}, 'k-4', 2).status_code == 422
    assert patch({'notes': 'x'}, 'k-5', 1, '/v1/hooks/does-not-exist').status_code == 404
    assert c.get(path, headers=base).json()['revision'] == 2
    with psycopg.connect(database[0]) as check:
        assert check.execute('SELECT count(*) FROM controlplane.cp_hook_revisions WHERE hook_id = %s', ('hook-1',)).fetchone()[0] == 2


def test_launch_rejects_foreign_host_without_consuming(app):
    path = launch_path(app)
    assert client(app).get(path, headers={'Host': 'evil.example'}).status_code == 403
    assert client(app).get(path).status_code == 303


def test_capability_expires_and_ttl_is_capped(app):
    with pytest.raises(ValueError):
        app.bootstrap_registry.issue(workspace_id=app.workspace_id, actor_id=ACTOR_ID, ttl_seconds=61)
    with pytest.raises(ValueError):
        app.launch_url(actor_id=ACTOR_ID, ttl_seconds=61)
    path = launch_path(app, ttl=1)
    time.sleep(1.2)
    assert client(app).get(path).status_code == 403
    assert client(app).get('/launch').status_code == 403
    assert client(app).get('/launch?cap=not-a-capability').status_code == 403


def test_allowed_origins_are_exact_loopback_for_the_port(manager, config):
    production = wiring('production')
    other = production.build_production_app(manager=manager, config=config, port=9443)
    assert other.api_app.state.allowed_origins == {'https://127.0.0.1:9443', 'https://localhost:9443'}
    with pytest.raises(ValueError):
        production.production_origins(0)


def test_ui_dist_is_served_byte_for_byte(app):
    c = client(app)
    files = sorted(p for p in DIST.rglob('*') if p.is_file())
    assert len(files) == 4
    for path in files:
        response = c.get('/' + path.relative_to(DIST).as_posix())
        assert response.status_code == 200 and response.content == path.read_bytes()
    assert 'id="root"' in c.get('/').text


def test_no_route_reads_secrets_back(app):
    for sub in (app.api_app, app.web_app):
        for route in sub.routes:
            if 'secret' in getattr(route, 'path', '').lower():
                methods = set(getattr(route, 'methods', None) or set()) - {'HEAD', 'OPTIONS'}
                assert methods <= {'PUT'}, (route.path, methods)


def test_production_sources_do_not_import_test_driver_or_bind_wildcard():
    for rel in ('src/main.py', 'src/controlplane/api/wiring/production.py'):
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert 'controlplane.application.test_driver' not in text and 'from src.' not in text
        assert '0.0.0.0' not in text
        for node in ast.walk(ast.parse(text)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else ([node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            assert not any('test_driver' in n for n in names), (rel, names)


def test_loopback_config_binds_127_0_0_1_only(app, tmp_path):
    production = wiring('production')
    cert, key = tmp_path / 'c.pem', tmp_path / 'k.pem'
    cfg = production.loopback_config(app, port=PORT, certfile=cert, keyfile=key)
    assert cfg.host == '127.0.0.1' and cfg.port == PORT
    assert cfg.ssl_certfile == str(cert) and cfg.ssl_keyfile == str(key)
    assert cfg.timeout_graceful_shutdown == production.GRACEFUL_SHUTDOWN_SECONDS > 0
    for bad in (0, 65536, -1):
        with pytest.raises(ValueError):
            production.loopback_config(app, port=bad, certfile=cert, keyfile=key)


def test_every_uvicorn_config_bounds_graceful_shutdown():
    """Ổn định hoá 25/10/2026 (S4, cả lớp): mọi máy chủ uvicorn trong src có hạn tắt êm, để không tiến trình nào treo vì kết nối mở."""
    calls = []
    for path in sorted((ROOT / 'src').rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'Config' \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'uvicorn':
                calls.append((path.relative_to(ROOT).as_posix(), node.lineno, {k.arg for k in node.keywords}))
    assert calls, 'no uvicorn.Config call found'
    missing = [(f, line) for f, line, keys in calls if 'timeout_graceful_shutdown' not in keys]
    assert not missing, missing
    tls = importlib.import_module('controlplane.api.tls')
    assert wiring('production').GRACEFUL_SHUTDOWN_SECONDS == tls.GRACEFUL_SHUTDOWN_SECONDS > 0


def _self_signed(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    import ipaddress
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, '127.0.0.1')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / 'stream-cert.pem', tmp_path / 'stream-key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


def test_loopback_server_stops_while_a_stream_stays_open(tmp_path):
    """Ổn định hoá 25/10/2026 (S4): tab giao diện giữ một luồng SSE; yêu cầu dừng vẫn kết thúc tiến trình trong hạn tắt êm."""
    import socket
    import ssl
    import threading
    import uvicorn
    production = wiring('production')

    async def streaming_app(scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/event-stream')]})
        while True:
            await send({'type': 'http.response.body', 'body': b': ping\n\n', 'more_body': True})
            await asyncio.sleep(0.2)

    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    cert, key = _self_signed(tmp_path)
    server = uvicorn.Server(production.loopback_config(streaming_app, port=port, certfile=cert, keyfile=key))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    client = ssl._create_unverified_context().wrap_socket(socket.create_connection(('127.0.0.1', port), timeout=10))
    try:
        client.sendall(b'GET /v1/stream HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
        assert b'200' in client.recv(4096)
        stop_at = time.monotonic()
        server.should_exit = True
        thread.join(timeout=production.GRACEFUL_SHUTDOWN_SECONDS + 15)
        assert not thread.is_alive(), 'server still waiting for the open stream'
        assert time.monotonic() - stop_at <= production.GRACEFUL_SHUTDOWN_SECONDS + 10
    finally:
        client.close()


def profile_parameters() -> dict[str, Any]:
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    return {
        'workflow.start_to_close_seconds': data['workflow']['start_to_close_seconds']['value'],
        'workflow.heartbeat_seconds': data['workflow']['heartbeat_seconds']['value'],
        'workflow.retry': data['workflow']['retry']['value'],
        'workflow.schedule': data['workflow']['schedule']['value'],
        'ai.quota_wait_poll_seconds': data['ai']['quota_wait_poll_seconds']['value'],
        'meta.revision': data['meta']['revision']['value'],
    }


def build_registration():
    workflow = wiring('workflow')
    services = workflow.build_workflow_services(
        parameters=profile_parameters(), handlers={},
        clock=lambda: datetime.datetime(2026, 10, 22, tzinfo=datetime.timezone.utc), timezone_approved=False)
    return workflow.build_temporal_registration(services, grant_issuer=lambda *args: None, capability_reader=lambda: {})


class StrictClient:
    def __getattr__(self, name):
        raise AssertionError('worker lifecycle must not touch workflows: ' + name)


class FakeWorker:
    def __init__(self, pending, client, *, task_queue, workflows, activities, graceful_shutdown_timeout):
        self.pending, self.client, self.task_queue = pending, client, task_queue
        self.workflows, self.activities = list(workflows), list(activities)
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self.started, self.resumed, self.shutdown_calls = False, [], 0
        self._stop = asyncio.Event()

    async def run(self):
        self.started = True
        self.resumed = sorted(k for k, v in self.pending.items() if v == 'RUNNING')
        await self._stop.wait()

    async def shutdown(self):
        self.shutdown_calls += 1
        self._stop.set()


def fake_factory(pending, workers):
    def factory(client, **kwargs):
        worker = FakeWorker(pending, client, **kwargs)
        workers.append(worker)
        return worker
    return factory


def test_worker_group_registers_six_workflows_on_control_queue():
    registration, workers = build_registration(), []
    group = wiring('production').TemporalWorkerGroup(StrictClient(), registration, graceful_shutdown_seconds=30, worker_factory=fake_factory({}, workers))
    by_queue = {w.task_queue: w for w in workers}
    assert set(by_queue) == set(registration.activities_by_queue) | {'control-workflows'}
    control = by_queue['control-workflows']
    assert len(control.workflows) == 6 and {c.__name__ for c in control.workflows} == WORKFLOW_NAMES
    assert all(w.workflows == [] for q, w in by_queue.items() if q != 'control-workflows')
    assert all(w.graceful_shutdown_timeout == datetime.timedelta(seconds=30) for w in workers)
    assert group.task_queues == tuple(by_queue)
    for bad in (0, -1, True):
        with pytest.raises(ValueError):
            wiring('production').TemporalWorkerGroup(StrictClient(), registration, graceful_shutdown_seconds=bad, worker_factory=fake_factory({}, []))


def test_stop_only_stops_workers_and_pending_work_resumes():
    registration, workers = build_registration(), []
    pending = {'wf-1': 'RUNNING', 'wf-2': 'RUNNING'}
    production = wiring('production')

    async def settle():
        for _ in range(10):
            await asyncio.sleep(0)

    async def scenario():
        first = production.TemporalWorkerGroup(StrictClient(), registration, graceful_shutdown_seconds=30, worker_factory=fake_factory(pending, workers))
        task = asyncio.create_task(first.run())
        await settle()
        assert all(w.started for w in workers)
        await first.stop()
        await task
        assert all(w.shutdown_calls == 1 for w in workers)
        assert pending == {'wf-1': 'RUNNING', 'wf-2': 'RUNNING'}
        count = len(workers)
        second = production.TemporalWorkerGroup(StrictClient(), registration, graceful_shutdown_seconds=30, worker_factory=fake_factory(pending, workers))
        task = asyncio.create_task(second.run())
        await settle()
        control = next(w for w in workers[count:] if w.task_queue == 'control-workflows')
        assert control.resumed == ['wf-1', 'wf-2'] and len(control.workflows) == 6
        await second.stop()
        await task

    asyncio.run(scenario())
