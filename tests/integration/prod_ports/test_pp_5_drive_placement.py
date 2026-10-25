"""PP-5, máy chủ Drive loopback, không gọi Google thật, không bí mật thật."""
from __future__ import annotations

import ast
import contextlib
import dataclasses
import http.server
import json
import os
import pathlib
import threading
import urllib.parse
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httplib2
import pytest

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF
from controlplane.infrastructure.storage.drive_object_store import (
    DriveObjectStore,
    DriveObjectStoreError,
    DriveStoreConfig,
)
from controlplane.infrastructure.production_ports.drive_placement import (
    DrivePlacement,
    DrivePlacementBootstrap,
    DrivePlacementError,
)

SOURCE = Path(__file__).resolve().parents[3] / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'drive_placement.py'
TOKEN = 'CANARY-PP5-ACCESS-4d2e'
FOLDER = 'application/vnd.google-apps.folder'
ROOT_NAME = 'AI-Auto-Video-Creator'
NAMESPACES = ('original', 'reusable', 'output')


class DriveServer:
    def __init__(self) -> None:
        self.folders: dict[str, dict[str, object]] = {}
        self.requests: list[dict[str, object]] = []
        self.faults: list[int] = []
        self.always: int | None = None
        self.created: int = 0
        self.lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                server._handle(self, 'GET')

            def do_POST(self) -> None:
                server._handle(self, 'POST')

        self._httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        port = self._httpd.server_port
        self.base = f'http://127.0.0.1:{port}'
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def _handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        length_header = handler.headers.get('Content-Length')
        length = int(length_header) if length_header and length_header.isdigit() else 0
        raw_body = handler.rfile.read(length) if length > 0 else b''
        body_obj = json.loads(raw_body.decode('utf-8')) if raw_body else None
        split = urllib.parse.urlsplit(handler.path)
        req = {
            'method': method,
            'path': split.path,
            'query': urllib.parse.parse_qs(split.query),
            'auth': handler.headers.get('Authorization'),
            'body': body_obj,
        }

        def send_json(status: int, payload: dict[str, object]) -> None:
            resp_bytes = json.dumps(payload).encode('utf-8')
            handler.send_response(status)
            handler.send_header('Content-Type', 'application/json')
            handler.send_header('Content-Length', str(len(resp_bytes)))
            handler.end_headers()
            handler.wfile.write(resp_bytes)

        def send_error(status: int) -> None:
            send_json(status, {'error': {'code': status, 'message': 'loopback', 'errors': []}})

        with self.lock:
            self.requests.append(req)
            auth = handler.headers.get('Authorization')
            if auth != 'Bearer ' + TOKEN:
                send_error(401)
                return
            if self.faults:
                send_error(self.faults.pop(0))
                return
            if self.always is not None:
                send_error(self.always)
                return
            if method == 'POST' and split.path == '/drive/v3/files':
                self.created += 1
                folder_id = f'folder-{self.created}'
                b = body_obj or {}
                self.folders[folder_id] = {
                    'name': b.get('name'),
                    'mimeType': b.get('mimeType', FOLDER),
                    'parents': b.get('parents', []),
                    'trashed': False,
                }
                send_json(200, {'id': folder_id})
                return
            if method == 'GET' and split.path == '/drive/v3/files/generateIds':
                send_json(200, {'kind': 'drive#generatedIds', 'space': 'drive', 'ids': ['gen-1']})
                return
            if method == 'GET' and split.path.startswith('/drive/v3/files/'):
                folder_id = split.path[len('/drive/v3/files/'):]
                if folder_id in self.folders:
                    item = self.folders[folder_id]
                    send_json(200, {
                        'id': folder_id,
                        'trashed': item.get('trashed', False),
                        'mimeType': item.get('mimeType', FOLDER),
                    })
                    return
                send_error(404)
                return
            send_error(501)

    def posts(self) -> list[dict[str, object]]:
        with self.lock:
            return [r for r in self.requests if r['method'] == 'POST']

    def gets(self) -> list[dict[str, object]]:
        with self.lock:
            return [r for r in self.requests if r['method'] == 'GET' and r['path'] != '/drive/v3/files/generateIds']

    def clear(self) -> None:
        with self.lock:
            self.requests.clear()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


class LoopbackHttp(httplib2.Http):
    def __init__(self, base: str, timeout: float) -> None:
        super().__init__(timeout=timeout)
        self._base = base

    def request(self, uri: str, *args: object, **kwargs: object) -> tuple[httplib2.Response, bytes]:
        return super().request(uri.replace('https://www.googleapis.com', self._base, 1), *args, **kwargs)


class StaticBroker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    @contextmanager
    def acquire(self, credential_method: str, account_ref: str):
        self.calls.append((credential_method, account_ref))
        yield TOKEN


class RefusingBroker:
    @contextmanager
    def acquire(self, credential_method: str, account_ref: str):
        raise RuntimeError('CANARY-PP5-BROKER-7a1c')
        yield


class EmptyBroker:
    @contextmanager
    def acquire(self, credential_method: str, account_ref: str):
        yield ''


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')


@pytest.fixture
def server():
    srv = DriveServer()
    try:
        yield srv
    finally:
        srv.close()


@dataclass
class Rig:
    bootstrap: DrivePlacementBootstrap
    broker: object
    sleeps: list[float]
    timeouts: list[float]
    state_file: Path
    factory: Callable[[float], httplib2.Http]


def make(server: DriveServer, tmp_path: Path, broker: object = None, **overrides: object) -> Rig:
    if broker is None:
        broker = StaticBroker()
    sleeps: list[float] = []
    timeouts: list[float] = []

    def factory(timeout: float) -> LoopbackHttp:
        timeouts.append(timeout)
        return LoopbackHttp(server.base, timeout)

    kwargs: dict[str, object] = {
        'state_file': tmp_path / 'state' / 'drive-placement.json',
        'root_name': ROOT_NAME,
        'namespaces': NAMESPACES,
        'retry_max_attempts': 3,
        'backoff_base_seconds': 0.5,
        'backoff_cap_seconds': 2.0,
        'timeout_seconds': 5.0,
        'http_factory': factory,
        'sleep': sleeps.append,
    }
    kwargs.update(overrides)
    state_file = kwargs.pop('state_file')
    root_name = kwargs.pop('root_name')
    namespaces = kwargs.pop('namespaces')
    bootstrap = DrivePlacementBootstrap(broker, state_file, root_name, namespaces, **kwargs)
    return Rig(bootstrap, broker, sleeps, timeouts, state_file, factory)


def test_first_run_creates_root_then_one_folder_per_namespace(server, tmp_path):
    rig = make(server, tmp_path)
    result = rig.bootstrap.ensure()
    posts = server.posts()
    assert len(posts) == 4
    assert posts[0]['body']['name'] == ROOT_NAME
    assert posts[0]['body']['mimeType'] == FOLDER
    assert 'parents' not in posts[0]['body']
    assert result.fallback_parent_id == 'folder-1'
    for post, ns in zip(posts[1:], NAMESPACES):
        body = post['body']
        assert body['name'] == ns
        assert body['mimeType'] == FOLDER
        assert body['parents'] == ['folder-1']
    assert dict(result.placement) == {ns: f'folder-{i}' for i, ns in enumerate(NAMESPACES, start=2)}
    assert isinstance(result, DrivePlacement)
    with pytest.raises(FrozenInstanceError):
        result.fallback_parent_id = 'x'  # type: ignore[misc]
    assert len(server.requests) == 4
    assert all(r['auth'] == 'Bearer ' + TOKEN for r in server.requests)
    assert rig.broker.calls == [(CREDENTIAL_METHOD, ACCOUNT_REF)] * 4
    assert not any(r['method'] == 'GET' and r['path'] == '/drive/v3/files' for r in server.requests)
    assert set(rig.timeouts) == {5.0}


def test_state_file_has_only_names_and_ids(server, tmp_path):
    rig = make(server, tmp_path)
    rig.bootstrap.ensure()
    state_file = rig.state_file
    assert json.loads(state_file.read_text(encoding='utf-8')) == {
        'root': {'name': ROOT_NAME, 'id': 'folder-1'},
        'namespaces': {'original': 'folder-2', 'reusable': 'folder-3', 'output': 'folder-4'},
    }
    assert TOKEN not in state_file.read_text(encoding='utf-8')
    assert sorted(p.name for p in state_file.parent.iterdir()) == [state_file.name]
    for file_path in tmp_path.rglob('*'):
        if file_path.is_file():
            assert TOKEN.encode('utf-8') not in file_path.read_bytes()


def test_state_is_written_through_temp_file_and_os_replace(server, tmp_path, monkeypatch):
    real = os.replace
    calls: list[tuple[Path, Path, dict[str, object]]] = []

    def spy(src, dst):
        calls.append((Path(src), Path(dst), json.loads(Path(src).read_text(encoding='utf-8'))))
        real(src, dst)

    monkeypatch.setattr(os, 'replace', spy)
    rig = make(server, tmp_path)
    rig.bootstrap.ensure()
    assert len(calls) == 4
    for src, dst, _ in calls:
        assert dst == rig.state_file
        assert src.parent == rig.state_file.parent
        assert src != dst
        assert not src.exists()
    assert [len(payload['namespaces']) for _, _, payload in calls] == [0, 1, 2, 3]


def test_second_run_verifies_each_id_without_creating(server, tmp_path):
    first = make(server, tmp_path).bootstrap.ensure()
    server.clear()
    second = make(server, tmp_path).bootstrap.ensure()
    assert server.posts() == []
    assert [g['path'] for g in server.gets()] == [
        '/drive/v3/files/folder-1',
        '/drive/v3/files/folder-2',
        '/drive/v3/files/folder-3',
        '/drive/v3/files/folder-4',
    ]
    assert all(g['query']['fields'] == ['id,trashed,mimeType'] for g in server.gets())
    assert dict(second.placement) == dict(first.placement)
    assert second.fallback_parent_id == first.fallback_parent_id
    assert not any(r['path'] == '/drive/v3/files/generateIds' for r in server.requests)


@pytest.mark.parametrize('mode', ['trashed', 'missing', 'not_folder'])
def test_unusable_namespace_folder_is_recreated_alone(server, tmp_path, mode):
    first = make(server, tmp_path).bootstrap.ensure()
    old = first.placement['reusable']
    if mode == 'trashed':
        server.folders[old]['trashed'] = True
    elif mode == 'missing':
        del server.folders[old]
    elif mode == 'not_folder':
        server.folders[old]['mimeType'] = 'text/plain'
    server.clear()
    second = make(server, tmp_path).bootstrap.ensure()
    posts = server.posts()
    assert len(posts) == 1
    assert posts[0]['body']['name'] == 'reusable'
    assert posts[0]['body']['mimeType'] == FOLDER
    assert posts[0]['body']['parents'] == [first.fallback_parent_id]
    assert second.placement['reusable'] != old
    assert second.placement['original'] == first.placement['original']
    assert second.placement['output'] == first.placement['output']
    assert second.fallback_parent_id == first.fallback_parent_id
    assert len(server.gets()) == 4
    state_data = json.loads((tmp_path / 'state' / 'drive-placement.json').read_text(encoding='utf-8'))
    assert state_data['namespaces']['reusable'] == second.placement['reusable']


@pytest.mark.parametrize('mode', ['trashed', 'missing'])
def test_unusable_root_recreates_root_and_every_namespace(server, tmp_path, mode):
    first = make(server, tmp_path).bootstrap.ensure()
    if mode == 'trashed':
        server.folders['folder-1']['trashed'] = True
    elif mode == 'missing':
        del server.folders['folder-1']
    server.clear()
    second = make(server, tmp_path).bootstrap.ensure()
    assert len(server.posts()) == 4
    assert second.fallback_parent_id != first.fallback_parent_id
    assert all(second.placement[ns] != first.placement[ns] for ns in NAMESPACES)
    assert all(post['body']['parents'] == [second.fallback_parent_id] for post in server.posts()[1:])
    assert len(server.gets()) == 1
    state_data = json.loads((tmp_path / 'state' / 'drive-placement.json').read_text(encoding='utf-8'))
    assert state_data['root']['id'] == second.fallback_parent_id


def test_state_for_another_root_name_creates_a_new_root(server, tmp_path):
    make(server, tmp_path).bootstrap.ensure()
    server.clear()
    second_rig = make(server, tmp_path, root_name='Other-Root')
    result = second_rig.bootstrap.ensure()
    posts = server.posts()
    assert len(posts) == 4
    assert posts[0]['body']['name'] == 'Other-Root'
    state_data = json.loads((tmp_path / 'state' / 'drive-placement.json').read_text(encoding='utf-8'))
    assert state_data['root']['name'] == 'Other-Root'


@pytest.mark.parametrize('status', [408, 429, 500, 502, 503, 504])
def test_transient_status_is_retried_then_succeeds(server, tmp_path, status):
    server.faults = [status, status]
    rig = make(server, tmp_path)
    result = rig.bootstrap.ensure()
    assert len(server.posts()) == 6
    assert server.created == 4
    assert rig.sleeps == [0.5, 1.0]
    assert result.fallback_parent_id == 'folder-1'


def test_transient_status_gives_up_after_retry_max_attempts(server, tmp_path):
    server.always = 503
    rig = make(server, tmp_path)
    with pytest.raises(DrivePlacementError) as info:
        rig.bootstrap.ensure()
    assert len(server.requests) == 3
    assert rig.sleeps == [0.5, 1.0]
    assert 'HTTP 503' in str(info.value)
    assert TOKEN not in str(info.value)
    assert TOKEN not in repr(info.value)
    assert not rig.state_file.exists()
    assert server.created == 0


def test_backoff_is_capped(server, tmp_path):
    rig = make(server, tmp_path, retry_max_attempts=5, backoff_base_seconds=1.0, backoff_cap_seconds=2.0)
    server.always = 503
    with pytest.raises(DrivePlacementError):
        rig.bootstrap.ensure()
    assert len(server.requests) == 5
    assert rig.sleeps == [1.0, 2.0, 2.0, 2.0]


@pytest.mark.parametrize('status', [400, 401, 403, 404])
def test_non_retryable_status_fails_at_once(server, tmp_path, status):
    server.faults = [status]
    rig = make(server, tmp_path)
    with pytest.raises(DrivePlacementError) as info:
        rig.bootstrap.ensure()
    assert f'HTTP {status}' in str(info.value)
    assert len(server.requests) == 1
    assert rig.sleeps == []
    assert not rig.state_file.exists()
    assert server.created == 0


@pytest.mark.parametrize('broker_cls', [RefusingBroker, EmptyBroker])
def test_missing_or_empty_token_fails_before_any_drive_request(server, tmp_path, broker_cls):
    rig = make(server, tmp_path, broker=broker_cls())
    with pytest.raises(DrivePlacementError) as info:
        rig.bootstrap.ensure()
    assert server.requests == []
    assert rig.sleeps == []
    assert not rig.state_file.exists()
    assert 'CANARY-PP5-BROKER' not in str(info.value)
    assert 'CANARY-PP5-BROKER' not in repr(info.value)


def test_network_error_is_retried_then_fails(server, tmp_path):
    calls: list[str] = []

    class BrokenHttp:
        def request(self, uri: str, *args: object, **kwargs: object) -> tuple[httplib2.Response, bytes]:
            calls.append(uri)
            raise ConnectionRefusedError('refused')

        def close(self) -> None:
            pass

    rig = make(server, tmp_path, http_factory=lambda timeout: BrokenHttp())
    with pytest.raises(DrivePlacementError):
        rig.bootstrap.ensure()
    assert len(calls) == 3
    assert rig.sleeps == [0.5, 1.0]
    assert server.requests == []


STATE_ROOT = {'name': ROOT_NAME, 'id': 'folder-1'}


@pytest.mark.parametrize('content', [
    b'',
    b'{',
    b'[]',
    b'null',
    b'\xff\xfe\x00',
    json.dumps({'root': STATE_ROOT}).encode('utf-8'),
    json.dumps({'root': None, 'namespaces': {}}).encode('utf-8'),
    json.dumps({'root': {'name': ROOT_NAME, 'id': 'folder-1', 'x': 1}, 'namespaces': {}}).encode('utf-8'),
    json.dumps({'root': {'name': ROOT_NAME, 'id': ''}, 'namespaces': {}}).encode('utf-8'),
    json.dumps({'root': STATE_ROOT, 'namespaces': {'original': 5}}).encode('utf-8'),
    json.dumps({'root': STATE_ROOT, 'namespaces': {'original': ''}}).encode('utf-8'),
])
def test_corrupt_state_file_fails_closed(server, tmp_path, content):
    rig = make(server, tmp_path)
    rig.state_file.parent.mkdir(parents=True, exist_ok=True)
    rig.state_file.write_bytes(content)
    with pytest.raises(DrivePlacementError):
        rig.bootstrap.ensure()
    assert server.requests == []
    assert rig.state_file.read_bytes() == content


def test_atomic_write_failure_keeps_previous_state(server, tmp_path, monkeypatch):
    rig = make(server, tmp_path)
    rig.bootstrap.ensure()
    before = rig.state_file.read_bytes()
    server.folders['folder-4']['trashed'] = True

    def boom(src, dst):
        raise PermissionError('denied')

    monkeypatch.setattr(os, 'replace', boom)
    with pytest.raises(DrivePlacementError):
        make(server, tmp_path).bootstrap.ensure()
    assert rig.state_file.read_bytes() == before
    assert sorted(p.name for p in rig.state_file.parent.iterdir()) == [rig.state_file.name]


def test_reserve_object_id_receives_its_parent_from_placement(server, tmp_path):
    rig = make(server, tmp_path)
    result = rig.bootstrap.ensure()
    config = DriveStoreConfig(
        chunk_bytes=262144,
        chunk_timeout_seconds=5.0,
        retry_max_attempts=3,
        retry_backoff_base_seconds=0.5,
        retry_backoff_cap_seconds=2.0,
        session_ttl_seconds=60,
        quota_reserve_ratio=0.1,
        placement=result.placement,
        fallback_parent_id=result.fallback_parent_id,
    )
    store = DriveObjectStore(config, StaticBroker(), object(), http_factory=rig.factory, sleep=lambda seconds: None)
    object_id = store.reserve_object_id('output')
    assert object_id == 'gen-1'
    assert store._parents[object_id] == result.placement['output']  # type: ignore[attr-defined]
    with pytest.raises(DriveObjectStoreError):
        store.reserve_object_id('absent')


@pytest.mark.parametrize('override', [
    {'retry_max_attempts': 0},
    {'retry_max_attempts': True},
    {'retry_max_attempts': '3'},
    {'backoff_base_seconds': 0},
    {'backoff_base_seconds': True},
    {'backoff_cap_seconds': 0.1},
    {'timeout_seconds': 0},
    {'timeout_seconds': -1},
    {'root_name': ''},
    {'root_name': '  '},
    {'namespaces': ()},
    {'namespaces': ('a', 'a')},
    {'namespaces': ('a', '')},
    {'namespaces': 'abc'},
    {'state_file': 'drive-placement.json'},
])
def test_constructor_rejects_bad_arguments(server, tmp_path, override):
    with pytest.raises(ValueError):
        make(server, tmp_path, **override)
    assert server.requests == []


def test_source_is_clean_and_uses_required_calls():
    text = SOURCE.read_text(encoding='utf-8').lower()
    for required in [
        'static_discovery=true',
        'cache_discovery=false',
        'os.replace',
        "fields='id,trashed,mimetype'",
        'authorization',
        'bearer',
        'drivetokenbrokerport',
    ]:
        assert required in text, f'Missing required token: {required}'
    for forbidden in [
        'files().list',
        'from src.',
        'mock',
        'fake',
        'os.environ',
        'getenv',
        'subprocess',
        'requests',
        'urllib',
        'brokerhttp',
    ]:
        assert forbidden not in text, f'Forbidden token found: {forbidden}'

    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert not alias.name.startswith('_'), f'Importing private name: {alias.name}'


def test_default_http_is_the_drive_client_that_keeps_308(tmp_path):
    bootstrap = DrivePlacementBootstrap(StaticBroker(), tmp_path / 'state' / 'drive-placement.json', ROOT_NAME, NAMESPACES,
                                        retry_max_attempts=3, backoff_base_seconds=0.5, backoff_cap_seconds=2.0, timeout_seconds=5.0)
    http = bootstrap._http_factory(5.0)
    assert isinstance(http, httplib2.Http) and 308 not in http.redirect_codes
