"""PP-8: build_production_ports và describe_runtime_ports; máy chủ loopback cho token và Drive, không gọi Google thật, không bí mật thật."""
from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import socket
import sys
import threading
import urllib.parse
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType

import httplib2
import pytest

if sys.platform != 'win32':
    pytest.skip('DpapiSecretStore dùng DPAPI của Windows; bỏ qua trên nền tảng không phải win32', allow_module_level=True)

from controlplane.api.wiring.production_profile import ProductionRuntime, RenderConfig, RetryValues, load_production_profile
from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
from controlplane.infrastructure.production_ports.assembly import build_production_ports, describe_runtime_ports
from controlplane.infrastructure.production_ports.credentials import ProviderCredentialError, RouterKeyCredentials
from controlplane.infrastructure.production_ports.drive_placement import DrivePlacementError
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from controlplane.infrastructure.production_ports.ports_config import load_ports_config
from controlplane.infrastructure.production_ports.route_catalog import ProfileRouteCatalog
from controlplane.infrastructure.production_ports.vision_route import RouterVisionRoute
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import DriveAccessTokenBroker
from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF as DRIVE_SECRET_REF
from controlplane.infrastructure.security.secret_redaction import SecretValue, find_canaries
from render.ports.lease import GpuLeaseUnavailable

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'assembly.py'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
PORTS_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'ports.json'
REFRESH = 'CANARY-PP8-REFRESH-6b1e'
CLIENT_SECRET = 'CANARY-PP8-CLIENT-SECRET-2d9a'
ROUTER_KEY = 'CANARY-PP8-ROUTER-KEY-8c4f'
ACCESS_PREFIX = 'CANARY-PP8-ACCESS-'
FOLDER = 'application/vnd.google-apps.folder'
WORKSPACE_ID = 'ws-pp8'
PORT_KEYS = {'route_catalog', 'provider_credentials', 'vision_route', 'artifact_source', 'drive_token_broker', 'gpu_lease', 'drive_placement', 'drive_fallback_parent_id'}
NAMES = ['route_catalog', 'provider_credentials', 'vision_route', 'artifact_source', 'drive_token_broker', 'gpu_lease', 'drive_placement']


class LoopbackHttp(httplib2.Http):
    def __init__(self, base: str, timeout: float) -> None:
        super().__init__(timeout=timeout)
        self._base = base

    def request(self, uri: str, *args: object, **kwargs: object) -> tuple[httplib2.Response, bytes]:
        return super().request(uri.replace('https://www.googleapis.com', self._base, 1), *args, **kwargs)


class TokenServer:
    def __init__(self) -> None:
        self.calls = 0
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                size = int(self.headers.get('Content-Length', '0'))
                form = urllib.parse.parse_qs(self.rfile.read(size).decode('utf-8'))
                srv.calls += 1
                ok = form.get('refresh_token') == [REFRESH]
                body = {'access_token': ACCESS_PREFIX + str(srv.calls), 'expires_in': 3600, 'token_type': 'Bearer'} if ok else {'error': 'invalid_grant'}
                self.send_response(200 if ok else 400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(body).encode('utf-8'))

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class DriveServer:
    def __init__(self) -> None:
        self.folders: dict = {}
        self.requests: list = []
        self.always: int | None = None
        self.created = 0
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                srv.handle(self, 'GET')

            def do_POST(self) -> None:
                srv.handle(self, 'POST')

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.base = f'http://127.0.0.1:{self.httpd.server_port}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        size = int(handler.headers.get('Content-Length', '0'))
        body = json.loads(handler.rfile.read(size).decode('utf-8')) if size else None
        path = urllib.parse.urlsplit(handler.path).path
        auth = handler.headers.get('Authorization') or ''
        self.requests.append({'method': method, 'path': path, 'auth': auth, 'body': body})
        status, payload = self.answer(method, path, body or {}, auth)
        raw = json.dumps(payload).encode('utf-8')
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)

    def answer(self, method: str, path: str, body: dict, auth: str) -> tuple[int, dict]:
        if not auth.startswith('Bearer ' + ACCESS_PREFIX):
            return 401, {'error': {'code': 401, 'message': 'loopback'}}
        if self.always is not None:
            return self.always, {'error': {'code': self.always, 'message': 'loopback'}}
        if method == 'POST' and path == '/drive/v3/files':
            self.created += 1
            folder_id = f'folder-{self.created}'
            self.folders[folder_id] = {'name': body.get('name'), 'parents': body.get('parents', [])}
            return 200, {'id': folder_id}
        folder_id = path[len('/drive/v3/files/'):]
        if method == 'GET' and folder_id in self.folders:
            return 200, {'id': folder_id, 'trashed': False, 'mimeType': FOLDER}
        return 404, {'error': {'code': 404, 'message': 'loopback'}}

    def posts(self) -> list:
        return [r for r in self.requests if r['method'] == 'POST']

    def gets(self) -> list:
        return [r for r in self.requests if r['method'] == 'GET']

    def clear(self) -> None:
        self.requests.clear()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@dataclasses.dataclass
class Rig:
    tokens: TokenServer
    drive: DriveServer
    store: DpapiSecretStore
    profile: object
    ports_config: object
    kwargs: dict

    @property
    def state_file(self) -> Path:
        return self.kwargs['state_dir'] / self.ports_config.drive.placement_state_file

    def build(self, profile: object = None) -> dict:
        return build_production_ports(
            profile or self.profile,
            http_factory=lambda timeout: LoopbackHttp(self.drive.base, timeout),
            **self.kwargs,
        )

    def describe(self) -> list:
        return describe_runtime_ports(**self.kwargs)


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')


@pytest.fixture
def rig(tmp_path: Path):
    tokens = TokenServer()
    drive = DriveServer()
    try:
        ports_config = load_ports_config(PORTS_PATH)
        store = DpapiSecretStore(tmp_path / 'vault')
        store.put(DRIVE_SECRET_REF, SecretValue(REFRESH))
        store.put(ports_config.router.secret_ref, SecretValue(ROUTER_KEY))
        secrets_dir = tmp_path / 'secrets'
        secrets_dir.mkdir()
        client = secrets_dir / 'oauth-client.json'
        uri = f'http://127.0.0.1:{tokens.httpd.server_port}/token'
        installed = {'client_id': 'pp8-client.apps.test', 'client_secret': CLIENT_SECRET, 'auth_uri': uri, 'token_uri': uri, 'redirect_uris': ['http://127.0.0.1']}
        client.write_text(json.dumps({'installed': installed}), encoding='utf-8')
        (tmp_path / 'staging').mkdir()
        kwargs = {'vault_dir': tmp_path / 'vault', 'staging_dir': tmp_path / 'staging', 'state_dir': tmp_path / 'state', 'oauth_client_secrets_path': client, 'ports_config': ports_config}
        yield Rig(tokens, drive, store, load_production_profile(PROFILE_PATH), ports_config, kwargs)
    finally:
        drive.close()
        tokens.close()


def runtime_from(tmp_path: Path, ports: dict) -> ProductionRuntime:
    return ProductionRuntime(
        ffmpeg_path=tmp_path / 'ffmpeg.exe',
        ffprobe_path=tmp_path / 'ffprobe.exe',
        runtime_lock_path=tmp_path / 'runtime.lock.json',
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'secrets' / 'oauth-client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={},
        **ports,
    )


def test_build_returns_exactly_the_eight_keys_and_runtime_accepts_them(rig, tmp_path):
    ports = rig.build()
    assert set(ports) == PORT_KEYS
    assert isinstance(ports['route_catalog'], ProfileRouteCatalog)
    assert isinstance(ports['provider_credentials'], RouterKeyCredentials)
    assert isinstance(ports['vision_route'], RouterVisionRoute)
    assert isinstance(ports['artifact_source'], StagingArtifactSource)
    assert isinstance(ports['drive_token_broker'], DriveAccessTokenBroker)
    assert isinstance(ports['gpu_lease'], LocalGpuLease)
    assert dict(ports['drive_placement']) == {'original': 'folder-2', 'reusable': 'folder-3', 'output': 'folder-4'}
    assert ports['drive_fallback_parent_id'] == 'folder-1'
    runtime = runtime_from(tmp_path, ports)
    assert runtime.gpu_lease is ports['gpu_lease']
    assert runtime.drive_fallback_parent_id == 'folder-1'
    assert dict(runtime.drive_placement) == dict(ports['drive_placement'])


def test_drive_folders_follow_profile_and_ports_config(rig):
    rig.build()
    posts = rig.drive.posts()
    root_name = rig.profile.parameters['drive.folders']['root']
    assert [p['body']['name'] for p in posts] == [root_name, *rig.ports_config.drive.artifact_namespaces]
    assert 'parents' not in posts[0]['body']
    assert all(p['body']['parents'] == ['folder-1'] for p in posts[1:])
    assert all(r['auth'].startswith('Bearer ' + ACCESS_PREFIX) for r in rig.drive.requests)
    assert rig.tokens.calls == 1
    state = json.loads(rig.state_file.read_text(encoding='utf-8'))
    assert state['root'] == {'name': root_name, 'id': 'folder-1'}


def test_gpu_lease_uses_profile_slots_and_ttl(rig):
    lease = rig.build()['gpu_lease']
    slots = rig.profile.parameters['gpu.slots']['slots']
    for index in range(slots):
        lease.acquire(f'owner-{index}')
    with pytest.raises(GpuLeaseUnavailable):
        lease.acquire('one-too-many')
    assert lease._ttl_seconds == 900 + rig.ports_config.gpu_lease.grace_seconds
    assert lease._wait_seconds == rig.ports_config.gpu_lease.wait_seconds


def test_gpu_lease_changes_with_the_profile_values(rig):
    parameters = MappingProxyType({**rig.profile.parameters, 'gpu.slots': {'lock': 'LOCK-DESKTOP-GPU', 'slots': 1}})
    profile = dataclasses.replace(rig.profile, parameters=parameters, render=RenderConfig(timeout_seconds=100.5))
    lease = rig.build(profile)['gpu_lease']
    lease.acquire('first')
    with pytest.raises(GpuLeaseUnavailable):
        lease.acquire('second')
    assert lease._ttl_seconds == 101 + rig.ports_config.gpu_lease.grace_seconds
    assert lease._wait_seconds == rig.ports_config.gpu_lease.wait_seconds


def build_with_wait(rig, wait_seconds, profile=None):
    gpu_lease = dataclasses.replace(rig.ports_config.gpu_lease, wait_seconds=wait_seconds)
    ports_config = dataclasses.replace(rig.ports_config, gpu_lease=gpu_lease)
    kwargs = dict(rig.kwargs, ports_config=ports_config)
    return build_production_ports(profile or rig.profile, http_factory=lambda timeout: LoopbackHttp(rig.drive.base, timeout), **kwargs)


def test_gpu_lease_wait_seconds_is_taken_from_the_ports_config(rig):
    assert rig.build()['gpu_lease']._wait_seconds == rig.ports_config.gpu_lease.wait_seconds == 180
    assert build_with_wait(rig, 7)['gpu_lease']._wait_seconds == 7


@pytest.mark.parametrize('wait_seconds, render_timeout', [(300, 900.0), (299, 900.5), (1200, 1.0)])
def test_assembly_rejects_wait_plus_render_timeout_not_below_start_to_close(rig, wait_seconds, render_timeout):
    profile = dataclasses.replace(rig.profile, render=RenderConfig(timeout_seconds=render_timeout))
    with pytest.raises(ValueError) as caught:
        build_with_wait(rig, wait_seconds, profile)
    message = str(caught.value)
    for name in ('gpu_lease.wait_seconds', 'render.timeout_seconds', 'workflow.start_to_close_seconds'):
        assert name in message
    assert rig.drive.requests == [] and rig.tokens.calls == 0 and not rig.state_file.exists()


def test_assembly_accepts_wait_plus_render_timeout_just_below_start_to_close(rig):
    assert build_with_wait(rig, 299)['gpu_lease']._wait_seconds == 299


def test_ai_adapters_follow_profile_route_endpoint_and_model_refs(rig):
    ports = rig.build()
    refs = rig.profile.ai.route_model_refs
    assert ports['vision_route'].endpoint == rig.profile.ai.route_endpoint
    for role, model_ref in refs.items():
        candidate = ports['route_catalog'].candidates(WORKSPACE_ID, role)[0]
        assert candidate.model_ref == model_ref
        assert candidate.account.status is ExternalAccountStatus.ENABLED
    assert ports['route_catalog'].candidates(WORKSPACE_ID, 'absent-role') == ()
    with ports['provider_credentials'].acquire(CREDENTIAL_METHOD, rig.ports_config.router.account_ref) as key:
        assert key == ROUTER_KEY
    staged = rig.kwargs['staging_dir'] / 'artifact-1.bin'
    staged.write_bytes(b'pp8')
    with ports['artifact_source'].open('artifact-1.bin') as stream:
        assert stream.read() == b'pp8'


def test_second_build_reuses_state_file_without_creating_folders(rig):
    first = rig.build()
    before = rig.state_file.read_bytes()
    created = rig.drive.created
    rig.drive.clear()
    second = rig.build()
    assert rig.drive.posts() == []
    assert rig.drive.created == created
    assert [g['path'] for g in rig.drive.gets()] == [f'/drive/v3/files/folder-{n}' for n in (1, 2, 3, 4)]
    assert dict(second['drive_placement']) == dict(first['drive_placement'])
    assert second['drive_fallback_parent_id'] == first['drive_fallback_parent_id']
    assert rig.state_file.read_bytes() == before


def test_missing_refresh_token_raises_the_port_error_and_returns_no_placement(rig):
    rig.store.revoke(DRIVE_SECRET_REF, rig.store.current_version(DRIVE_SECRET_REF))
    with pytest.raises(DrivePlacementError) as info:
        rig.build()
    assert rig.drive.requests == []
    assert rig.tokens.calls == 0
    assert not rig.state_file.exists()
    assert find_canaries([REFRESH, CLIENT_SECRET, ROUTER_KEY], str(info.value), repr(info.value)) == []


def test_drive_failure_is_not_swallowed_and_uses_profile_retry(rig):
    retry = RetryValues(max_attempts=2, backoff_base_seconds=0.01, backoff_max_seconds=0.02)
    profile = dataclasses.replace(rig.profile, drive=dataclasses.replace(rig.profile.drive, retry=retry))
    rig.drive.always = 503
    with pytest.raises(DrivePlacementError) as info:
        rig.build(profile)
    assert 'HTTP 503' in str(info.value)
    assert len(rig.drive.requests) == 2
    assert not rig.state_file.exists()


def test_value_error_of_a_port_is_kept_before_any_network(rig):
    kwargs = dict(rig.kwargs, staging_dir=Path('relative-staging'))
    with pytest.raises(ValueError):
        build_production_ports(rig.profile, http_factory=lambda timeout: LoopbackHttp(rig.drive.base, timeout), **kwargs)
    assert rig.drive.requests == []
    assert rig.tokens.calls == 0
    assert not rig.state_file.exists()


def test_missing_router_key_does_not_block_build_and_credentials_keep_their_error(rig):
    secret_ref = rig.ports_config.router.secret_ref
    rig.store.revoke(secret_ref, rig.store.current_version(secret_ref))
    ports = rig.build()
    with pytest.raises(ProviderCredentialError):
        with ports['provider_credentials'].acquire(CREDENTIAL_METHOD, rig.ports_config.router.account_ref):
            pytest.fail('must not yield')
    candidate = ports['route_catalog'].candidates(WORKSPACE_ID, 'script')[0]
    assert candidate.account.status is ExternalAccountStatus.REVOKED


def test_describe_lists_the_seven_ports_before_the_first_build(rig):
    rows = rig.describe()
    assert [name for name, _, _ in rows] == NAMES
    assert [ready for _, ready, _ in rows] == [True] * 6 + [False]
    assert all(isinstance(reason, str) and reason for _, _, reason in rows)
    assert not rig.kwargs['state_dir'].exists()


def test_describe_reports_every_port_ready_after_a_build(rig):
    rig.build()
    rows = rig.describe()
    assert [name for name, _, _ in rows] == NAMES
    assert [ready for _, ready, _ in rows] == [True] * 7


def test_describe_reports_missing_pieces(rig, tmp_path):
    empty = dict(rig.kwargs, vault_dir=tmp_path / 'empty-vault', staging_dir=tmp_path / 'no-staging', oauth_client_secrets_path=tmp_path / 'no-client.json')
    ready = {name: ok for name, ok, _ in describe_runtime_ports(**empty)}
    assert ready == {'route_catalog': False, 'provider_credentials': False, 'vision_route': False, 'artifact_source': False, 'drive_token_broker': False, 'gpu_lease': True, 'drive_placement': False}


def test_describe_decrypts_nothing_opens_no_connection_and_leaks_no_secret(rig, monkeypatch):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError('describe_runtime_ports must not read ciphertext or open a connection')

    rig.build()
    rig.drive.clear()
    calls = rig.tokens.calls
    monkeypatch.setattr(DpapiSecretStore, 'export_vault', refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    rows = rig.describe()
    assert find_canaries([REFRESH, CLIENT_SECRET, ROUTER_KEY, ACCESS_PREFIX], repr(rows)) == []
    assert rig.drive.requests == []
    assert rig.tokens.calls == calls


def test_source_is_clean_and_keeps_the_launcher_boundary():
    text = SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    for forbidden in ('from src.', 'import launcher', 'from tools', 'import tools', 'mock', 'fake', 'os.environ', 'getenv', 'subprocess', 'print(', 'logging'):
        assert forbidden not in lowered, forbidden
    for required in ('build_production_ports', 'describe_runtime_ports'):
        assert required in lowered, required
    banned_roots = ('launcher', 'tools', 'src')
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            assert node.module is not None and not node.module.startswith(banned_roots)
            assert all(not alias.name.startswith('_') for alias in node.names)
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith(banned_roots) for alias in node.names)
    parameters = inspect.signature(build_production_ports).parameters
    assert list(parameters) == ['profile', 'vault_dir', 'staging_dir', 'state_dir', 'oauth_client_secrets_path', 'ports_config', 'http_factory']
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for name, p in parameters.items() if name != 'profile')
    assert parameters['http_factory'].default is None
    describe_parameters = inspect.signature(describe_runtime_ports).parameters
    assert list(describe_parameters) == ['vault_dir', 'staging_dir', 'state_dir', 'oauth_client_secrets_path', 'ports_config']
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in describe_parameters.values())
