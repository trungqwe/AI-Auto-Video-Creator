"""PP-7: RouterVisionRoute against a loopback HTTP server that plays 9Router (CT-AI-ROUTE-001, INV-012, QR-SEC-009)."""
from __future__ import annotations

import ast
import base64
import contextlib
import json
import logging
import pathlib
import socket
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.config.adapter import UnapprovedEndpointError
from controlplane.infrastructure.production_ports.credentials import ProviderCredentialError, RouterKeyCredentials
from controlplane.infrastructure.production_ports.router_key_entry import store_router_key
from controlplane.infrastructure.production_ports.vision_route import (
    MAX_RESPONSE_BYTES,
    RouterVisionRoute,
    VisionRouteError,
    VisionRouteTimeoutError,
)
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from voice.adapters.real_llm_image_safety import DEFAULT_CATEGORIES, parse_vision_output
from voice.domain.image_safety import DetectionStatus

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'vision_route.py'
ACCOUNT = 'router-primary'
SECRET = 'router-primary-api-key'
CANARY = 'sk-pp7-canary-0123456789abcdef'
MODEL_REFS = {'image_safety': 'profile-model-image-safety', 'script': 'profile-model-script'}
INSTRUCTIONS = 'Classify the image for safety. Answer with one JSON object only.'
IMAGE_B64 = base64.b64encode(bytes(range(32))).decode('ascii')
MEDIA_TYPE = 'image/png'
REGION = {'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
VERDICT = json.dumps({'confidence': 0.9, 'detections': [{'category': 'weapon', 'confidence': 0.8, 'region': REGION}]})
EMPTY_VERDICT = json.dumps({'confidence': 0.95, 'detections': []})


def reply_ok(content: str = VERDICT) -> bytes:
    return json.dumps({'choices': [{'message': {'role': 'assistant', 'content': content}}]}).encode('utf-8')


def leaks(exc: BaseException, secret: str = CANARY) -> bool:
    shown = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return secret in shown + repr(exc) + str(exc) + repr(exc.args)


class SpyCredentials:
    def __init__(self, key: str = CANARY) -> None:
        self.key = key
        self.calls = []

    @contextlib.contextmanager
    def acquire(self, credential_method, account_ref):
        self.calls.append((credential_method, account_ref))
        yield self.key


def route_for(url, credentials, suffix='/v1', model_refs=MODEL_REFS):
    return RouterVisionRoute(url + suffix, model_refs, credentials, ACCOUNT)


def call(route, role='image_safety', timeout=5.0):
    return route.invoke_vision(role, INSTRUCTIONS, IMAGE_B64, MEDIA_TYPE, timeout)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length)
        server = self.server
        server.hits.append({
            'method': self.command,
            'path': self.path,
            'authorization': self.headers.get('Authorization'),
            'content_type': self.headers.get('Content-Type'),
            'body': body,
        })
        if server.hang:
            server.release.wait(3)
            return
        self.send_response(server.status)
        for name, value in server.extra_headers.items():
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(server.reply)))
        self.end_headers()
        with contextlib.suppress(OSError):
            self.wfile.write(server.reply)

    def log_message(self, format, *args) -> None:
        pass


@pytest.fixture
def serve():
    servers = []

    def start(status=200, reply=b'', headers=None, hang=False):
        server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        server.daemon_threads = True
        server.hits = []
        server.status = status
        server.reply = reply
        server.extra_headers = dict(headers or {})
        server.hang = hang
        server.release = threading.Event()
        server.url = 'http://127.0.0.1:' + str(server.server_address[1])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.release.set()
        server.shutdown()
        server.server_close()


@pytest.fixture
def credentials(tmp_path):
    vault = DpapiSecretStore(tmp_path / 'vault')
    store_router_key(vault, SECRET, lambda: CANARY)
    return RouterKeyCredentials(vault, ACCOUNT, SECRET)


def test_posts_openai_body_with_bearer_canary_and_returns_content(serve, credentials) -> None:
    server = serve(reply=reply_ok())
    assert call(route_for(server.url, credentials)) == VERDICT
    assert len(server.hits) == 1
    hit = server.hits[0]
    assert hit['method'] == 'POST' and hit['path'] == '/v1/chat/completions'
    assert hit['authorization'] == 'Bearer ' + CANARY
    assert hit['content_type'] == 'application/json'
    assert CANARY.encode('utf-8') not in hit['body']
    body = json.loads(hit['body'].decode('utf-8'))
    assert body['model'] == MODEL_REFS['image_safety']
    assert len(body['messages']) == 1 and body['messages'][0]['role'] == 'user'
    assert body['messages'][0]['content'] == [
        {'type': 'text', 'text': INSTRUCTIONS},
        {'type': 'image_url', 'image_url': {'url': 'data:' + MEDIA_TYPE + ';base64,' + IMAGE_B64}},
    ]


def test_model_follows_role(serve, credentials) -> None:
    server = serve(reply=reply_ok('{}'))
    assert call(route_for(server.url, credentials), 'script') == '{}'
    assert json.loads(server.hits[0]['body'].decode('utf-8'))['model'] == MODEL_REFS['script']


def test_credentials_are_acquired_with_method_and_account(serve) -> None:
    spy = SpyCredentials()
    server = serve(reply=reply_ok())
    call(route_for(server.url, spy))
    assert spy.calls == [(CREDENTIAL_METHOD, ACCOUNT)]
    assert server.hits[0]['authorization'] == 'Bearer ' + CANARY


@pytest.mark.parametrize('suffix, expected', [('/v1', '/v1'), ('/v1/', '/v1'), ('', '')])
def test_endpoint_is_normalized_and_path_appended(serve, credentials, suffix, expected) -> None:
    server = serve(reply=reply_ok())
    route = route_for(server.url, credentials, suffix)
    assert route.endpoint == server.url + expected
    call(route)
    assert server.hits[0]['path'] == expected + '/chat/completions'


def test_content_goes_through_parse_vision_output(serve, credentials) -> None:
    server = serve(reply=reply_ok())
    detection, regions = parse_vision_output(call(route_for(server.url, credentials)), DEFAULT_CATEGORIES)
    assert detection.status == DetectionStatus.COMPLETED
    assert detection.categories == ('weapon',) and detection.confidence == 0.8
    assert len(regions) == 1 and regions[0].category == 'weapon'


def test_empty_and_fenced_content_are_parsed(serve, credentials) -> None:
    fenced = '```json' + chr(10) + EMPTY_VERDICT + chr(10) + '```'
    server = serve(reply=reply_ok(fenced))
    detection, regions = parse_vision_output(call(route_for(server.url, credentials)), DEFAULT_CATEGORIES)
    assert detection.status == DetectionStatus.COMPLETED
    assert detection.categories == () and detection.confidence == 0.95 and regions == ()


def test_proxy_environment_is_ignored(serve, credentials, monkeypatch) -> None:
    for name in ('http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        monkeypatch.setenv(name, 'http://127.0.0.1:9')
    for name in ('no_proxy', 'NO_PROXY'):
        monkeypatch.delenv(name, raising=False)
    server = serve(reply=reply_ok())
    assert call(route_for(server.url, credentials)) == VERDICT
    assert len(server.hits) == 1


@pytest.mark.parametrize('role', ['image_unknown', '', None, 7])
def test_unknown_role_is_rejected_before_network(serve, role) -> None:
    server = serve(reply=reply_ok())
    spy = SpyCredentials()
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, spy), role)
    assert info.value.code == 'unknown_role'
    assert server.hits == [] and spy.calls == []


BAD_ARGS = [
    ('instructions', ''), ('instructions', '   '), ('instructions', 7),
    ('image_base64', ''), ('image_base64', 'not base64!'), ('image_base64', 7),
    ('media_type', ''), ('media_type', 'text/plain'), ('media_type', 'image/'),
    ('media_type', 'image/png; x=1'), ('media_type', 7),
    ('timeout', 0), ('timeout', -1), ('timeout', True), ('timeout', '5'), ('timeout', None),
    ('timeout', float('nan')), ('timeout', float('inf')),
]


@pytest.mark.parametrize('name, value', BAD_ARGS)
def test_bad_arguments_are_rejected_before_network(serve, name, value) -> None:
    server = serve(reply=reply_ok())
    spy = SpyCredentials()
    args = {'instructions': INSTRUCTIONS, 'image_base64': IMAGE_B64, 'media_type': MEDIA_TYPE, 'timeout': 5.0}
    args[name] = value
    route = route_for(server.url, spy)
    with pytest.raises(ValueError):
        route.invoke_vision('image_safety', args['instructions'], args['image_base64'], args['media_type'], args['timeout'])
    assert server.hits == [] and spy.calls == []


@pytest.mark.parametrize('endpoint', ['', '   ', 'localhost:8000', 'ftp://127.0.0.1:1', 'http://', 7, None])
def test_constructor_rejects_unapproved_endpoint(endpoint) -> None:
    with pytest.raises(UnapprovedEndpointError):
        RouterVisionRoute(endpoint, MODEL_REFS, SpyCredentials(), ACCOUNT)


BAD_CTOR = [
    ({}, ACCOUNT), ([], ACCOUNT), (None, ACCOUNT), ('x', ACCOUNT),
    ({'': 'm'}, ACCOUNT), ({'r': ''}, ACCOUNT), ({'r': 7}, ACCOUNT), ({7: 'm'}, ACCOUNT),
    (MODEL_REFS, ''), (MODEL_REFS, '  '), (MODEL_REFS, None), (MODEL_REFS, 7),
]


@pytest.mark.parametrize('model_refs, account', BAD_CTOR)
def test_constructor_rejects_bad_arguments(model_refs, account) -> None:
    with pytest.raises(ValueError):
        RouterVisionRoute('http://127.0.0.1:1/v1', model_refs, SpyCredentials(), account)


def test_constructor_rejects_credentials_without_acquire() -> None:
    with pytest.raises(ValueError):
        RouterVisionRoute('http://127.0.0.1:1/v1', MODEL_REFS, object(), ACCOUNT)


def test_model_refs_are_copied_at_construction(serve) -> None:
    server = serve(reply=reply_ok())
    refs = dict(MODEL_REFS)
    route = route_for(server.url, SpyCredentials(), model_refs=refs)
    refs['image_safety'] = 'changed'
    refs['extra'] = 'extra-model'
    call(route)
    assert json.loads(server.hits[0]['body'].decode('utf-8'))['model'] == MODEL_REFS['image_safety']
    with pytest.raises(VisionRouteError):
        call(route, 'extra')
    assert len(server.hits) == 1


def test_revoked_key_stops_before_network(serve, tmp_path) -> None:
    vault = DpapiSecretStore(tmp_path / 'vault')
    store_router_key(vault, SECRET, lambda: CANARY)
    revoked = RouterKeyCredentials(vault, ACCOUNT, SECRET)
    vault.revoke(SECRET, vault.current_version(SECRET))
    server = serve(reply=reply_ok())
    with pytest.raises(ProviderCredentialError) as info:
        call(route_for(server.url, revoked))
    assert server.hits == [] and not leaks(info.value)


def test_account_ref_mismatch_stops_before_network(serve, credentials) -> None:
    server = serve(reply=reply_ok())
    route = RouterVisionRoute(server.url + '/v1', MODEL_REFS, credentials, 'other-account')
    with pytest.raises(ValueError):
        call(route)
    assert server.hits == []


@pytest.mark.parametrize('key', ['bad key', 'a' + chr(13) + chr(10) + 'X-Evil: 1', '', 'k' + chr(233)])
def test_unusable_key_is_rejected_without_leak(serve, key) -> None:
    server = serve(reply=reply_ok())
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, SpyCredentials(key)))
    assert info.value.code == 'bad_credential'
    assert server.hits == []
    if key:
        assert not leaks(info.value, key)


HTTP_CASES = [
    (400, 'http_error'), (401, 'unauthorized'), (403, 'unauthorized'), (404, 'http_error'),
    (429, 'rate_limited'), (500, 'server_error'), (502, 'server_error'), (503, 'server_error'),
]


@pytest.mark.parametrize('status, code', HTTP_CASES)
def test_http_error_becomes_safe_exception(serve, credentials, status, code) -> None:
    server = serve(status=status, reply=json.dumps({'error': 'rejected ' + CANARY}).encode('utf-8'))
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, credentials))
    assert info.value.code == code and str(info.value) == code
    assert info.value.__cause__ is None
    assert len(server.hits) == 1
    assert not leaks(info.value)


@pytest.mark.parametrize('status', [301, 302, 303, 307, 308])
def test_redirect_is_not_followed(serve, credentials, status) -> None:
    target = serve(reply=reply_ok())
    server = serve(status=status, headers={'Location': target.url + '/v1/chat/completions'})
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, credentials))
    assert info.value.code == 'http_error'
    assert len(server.hits) == 1 and target.hits == []
    assert not leaks(info.value)


BAD_BODIES = [
    b'not json',
    b'',
    b'[]',
    b'{}',
    b'{"choices": []}',
    b'{"choices": [{}]}',
    b'{"choices": [{"message": {}}]}',
    b'{"choices": [{"message": {"content": null}}]}',
    b'{"choices": [{"message": {"content": 7}}]}',
    b'{"choices": [{"message": {"content": "   "}}]}',
    bytes([0xFF, 0xFE]),
]


@pytest.mark.parametrize('reply', BAD_BODIES)
def test_malformed_response_is_rejected(serve, credentials, reply) -> None:
    server = serve(reply=reply)
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, credentials))
    assert info.value.code == 'bad_response' and not leaks(info.value)


def test_oversized_response_is_rejected(serve, credentials) -> None:
    server = serve(reply=b'a' * (MAX_RESPONSE_BYTES + 1))
    with pytest.raises(VisionRouteError) as info:
        call(route_for(server.url, credentials))
    assert info.value.code == 'bad_response'


def test_timeout_parameter_is_applied(serve, credentials) -> None:
    server = serve(hang=True)
    started = time.monotonic()
    with pytest.raises(VisionRouteTimeoutError) as info:
        call(route_for(server.url, credentials), timeout=0.3)
    assert time.monotonic() - started < 2.5
    assert info.value.code == 'timeout' and isinstance(info.value, TimeoutError)
    assert len(server.hits) == 1 and not leaks(info.value)


def test_connection_refused_is_network_error(credentials) -> None:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    route = RouterVisionRoute('http://127.0.0.1:' + str(port) + '/v1', MODEL_REFS, credentials, ACCOUNT)
    with pytest.raises(VisionRouteError) as info:
        call(route)
    assert info.value.code == 'network_error' and not leaks(info.value)


def test_canary_never_reaches_logs_output_or_repr(serve, credentials, caplog, capsys) -> None:
    caplog.set_level(logging.DEBUG)
    server = serve(status=500, reply=CANARY.encode('utf-8'))
    route = route_for(server.url, credentials)
    with pytest.raises(VisionRouteError):
        call(route)
    out, err = capsys.readouterr()
    assert CANARY not in out + err + caplog.text + repr(route) + str(route)


def test_source_has_no_forbidden_text_and_only_expected_imports() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    low = text.lower()
    for forbidden in ('from src.', 'mock', 'fake', 'os.environ', 'getenv', 'subprocess', 'logging', 'print(', 'import requests', 'httpx', 'socket', 'http://', 'https://'):
        assert forbidden not in low
    assert 'chat/completions' in low and 'authorization' in low
    assert 'ProxyHandler' in text and 'redirect_request' in text
    imported = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert 'urllib.request' in imported
    assert imported <= {
        '__future__', 'collections.abc', 'http.client', 'json', 'math', 're', 'urllib.error', 'urllib.request',
        'controlplane.application.config_security.route_resolver', 'controlplane.config.adapter',
    }
