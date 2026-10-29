"""ADAPT-J: one-time loopback OAuth and DPAPI-brokered Drive token (CT-SEC-001, INV-012).

Local fake OAuth server only; no Google call, no real secret.
Real consent belongs to CP7-J-01.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import sys
import threading
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

if sys.platform != 'win32':
    pytest.skip('DpapiSecretStore dùng DPAPI của Windows; bỏ qua trên nền tảng không phải win32', allow_module_level=True)

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.secret_redaction import SecretValue, find_canaries
from controlplane.infrastructure.security.oauth_google_loopback import (
    ACCOUNT_REF,
    SCOPE,
    SECRET_REF,
    DriveOAuthConfig,
    OAuthConsentTimeoutError,
    OAuthFlowError,
    load_client_config,
    require_client_secrets_outside_git,
    run_consent,
)
from controlplane.infrastructure.security.oauth_drive_token import (
    DpapiRefreshTokenReader,
    DriveAccessTokenBroker,
    DriveTokenDeniedError,
    DriveTokenRefreshError,
)

REFRESH = 'CANARY-ADAPT-J-REFRESH-6b1f'
CLIENT_ID = 'adapt-j-client.apps.test'
CLIENT_SECRET = 'CANARY-ADAPT-J-CLIENT-SECRET-2d9a'
ACCESS_PREFIX = 'CANARY-ADAPT-J-ACCESS-'
ERRBODY = 'CANARY-ADAPT-J-ERRBODY-9c4e'


class FakeOAuthServer:
    def __init__(self) -> None:
        self.state_override: str | None = None
        self.granted_scope: str | None = None
        self.issue_refresh_token: bool = True
        self.refresh_error: bool = False
        self.expires_in: int = 3600
        self.requests: list[str] = []
        self.last_auth: dict[str, list[str]] = {}
        self.auth_codes: dict[str, str] = {}
        self._lock = threading.Lock()
        self._auth_counter = 0
        self._token_counter = 0

        srv = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                parsed = urllib.parse.urlsplit(self.path)
                if parsed.path == '/auth':
                    params = urllib.parse.parse_qs(parsed.query)
                    with srv._lock:
                        srv.requests.append('auth')
                        srv.last_auth = dict(params)
                        srv._auth_counter += 1
                        n = srv._auth_counter
                        code = f'code-{n}'
                        code_challenge = params.get('code_challenge', [''])[0]
                        srv.auth_codes[code] = code_challenge

                    redirect_uri = params.get('redirect_uri', [''])[0]
                    state = params.get('state', [''])[0]
                    sent_state = srv.state_override if srv.state_override is not None else state
                    sep = '&' if '?' in redirect_uri else '?'
                    loc = redirect_uri + sep + urllib.parse.urlencode({'code': code, 'state': sent_state})
                    self.send_response(302)
                    self.send_header('Location', loc)
                    self.end_headers()
                else:
                    self.send_error(404)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlsplit(self.path)
                if parsed.path == '/token':
                    content_len = int(self.headers.get('Content-Length', '0'))
                    raw_body = self.rfile.read(content_len).decode('utf-8')
                    form = urllib.parse.parse_qs(raw_body)
                    grant_type = form.get('grant_type', [''])[0]

                    auth_hdr = self.headers.get('Authorization', '')
                    client_id = form.get('client_id', [''])[0]
                    client_secret = form.get('client_secret', [''])[0]
                    if auth_hdr.startswith('Basic '):
                        try:
                            decoded = base64.b64decode(auth_hdr[6:].strip()).decode('utf-8')
                            if ':' in decoded:
                                client_id, client_secret = decoded.split(':', 1)
                        except Exception:
                            pass

                    if grant_type == 'authorization_code':
                        code = form.get('code', [''])[0]
                        code_verifier = form.get('code_verifier', [''])[0]
                        with srv._lock:
                            expected_challenge = srv.auth_codes.get(code)
                        computed_challenge = base64.urlsafe_b64encode(
                            hashlib.sha256(code_verifier.encode('utf-8')).digest()
                        ).decode('utf-8').rstrip('=')

                        valid_pkce = bool(expected_challenge and expected_challenge == computed_challenge)
                        valid_client = (client_id == CLIENT_ID and client_secret == CLIENT_SECRET)
                        if not (code and valid_client and valid_pkce):
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'invalid_grant'}).encode('utf-8'))
                            return

                        with srv._lock:
                            srv.requests.append('code')
                            srv._token_counter += 1
                            token_n = srv._token_counter

                        resp: dict[str, object] = {
                            'access_token': f'{ACCESS_PREFIX}{token_n}',
                            'expires_in': srv.expires_in,
                            'scope': srv.granted_scope if srv.granted_scope is not None else SCOPE,
                            'token_type': 'Bearer',
                        }
                        if srv.issue_refresh_token:
                            resp['refresh_token'] = REFRESH
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(resp).encode('utf-8'))
                    elif grant_type == 'refresh_token':
                        refresh_token = form.get('refresh_token', [''])[0]
                        valid_client = (client_id == CLIENT_ID and client_secret == CLIENT_SECRET)
                        if not (valid_client and refresh_token == REFRESH):
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'invalid_grant'}).encode('utf-8'))
                            return
                        if srv.refresh_error:
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'invalid_grant', 'error_description': ERRBODY}).encode('utf-8'))
                            return

                        with srv._lock:
                            srv.requests.append('refresh')
                            srv._token_counter += 1
                            token_n = srv._token_counter

                        resp = {
                            'access_token': f'{ACCESS_PREFIX}{token_n}',
                            'expires_in': srv.expires_in,
                            'scope': srv.granted_scope if srv.granted_scope is not None else SCOPE,
                            'token_type': 'Bearer',
                        }
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(resp).encode('utf-8'))
                    else:
                        self.send_error(400)
                else:
                    self.send_error(404)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        self.server_port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def auth_uri(self) -> str:
        return f'http://127.0.0.1:{self.server_port}/auth'

    @property
    def token_uri(self) -> str:
        return f'http://127.0.0.1:{self.server_port}/token'

    def count(self, kind: str) -> int:
        with self._lock:
            return self.requests.count(kind)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('OAUTHLIB_INSECURE_TRANSPORT', '1')
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')
    orig_getaddrinfo = socket.getaddrinfo

    def _safe_getaddrinfo(host: str | bytes | None, *args: object, **kwargs: object) -> object:
        host_str = host.decode('utf-8') if isinstance(host, (bytes, bytearray)) else (host or '')
        if host_str not in {'127.0.0.1', 'localhost'}:
            raise AssertionError(f'Attempted network call to {host_str}; only local fake OAuth server is allowed')
        return orig_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', _safe_getaddrinfo)


@pytest.fixture
def server() -> Iterator[FakeOAuthServer]:
    srv = FakeOAuthServer()
    try:
        yield srv
    finally:
        srv.close()


@pytest.fixture
def client_file(tmp_path: Path, server: FakeOAuthServer) -> Path:
    secrets_dir = tmp_path / 'secrets'
    secrets_dir.mkdir(parents=True, exist_ok=True)
    p = secrets_dir / 'client.json'
    data = {
        'installed': {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'auth_uri': server.auth_uri,
            'token_uri': server.token_uri,
            'redirect_uris': ['http://127.0.0.1'],
        }
    }
    p.write_text(json.dumps(data), encoding='utf-8')
    return p


@pytest.fixture
def store(tmp_path: Path) -> DpapiSecretStore:
    return DpapiSecretStore(tmp_path / 'vault')


class Browser:
    def __init__(self) -> None:
        self.follow: bool = True
        self.url: str | None = None
        self.thread: threading.Thread | None = None

    def __call__(self, url: str) -> None:
        self.url = url
        if self.follow:
            def _open() -> None:
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        resp.read()
                except Exception:
                    pass

            self.thread = threading.Thread(target=_open, daemon=True)
            self.thread.start()

    def join(self, timeout: float = 10.0) -> None:
        if self.thread is not None:
            self.thread.join(timeout=timeout)


def _port_of(url: str | None) -> int:
    assert url is not None, 'url cannot be None'
    parsed = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(parsed.query)
    redirect_uri = params.get('redirect_uri', [''])[0]
    redirect_parsed = urllib.parse.urlsplit(redirect_uri)
    assert redirect_parsed.port is not None, f'port missing in redirect_uri {redirect_uri}'
    return redirect_parsed.port


def _closed(port: int) -> None:
    with pytest.raises(OSError):
        s = socket.create_connection(('127.0.0.1', port), timeout=1)
        s.close()


def _run(
    client_file: Path,
    store: DpapiSecretStore,
    browser: Browser,
    timeout: int = 5,
) -> object:
    try:
        return run_consent(DriveOAuthConfig(client_file, timeout), store, present_url=browser)
    finally:
        browser.join()


def test_consent_success_stores_refresh_token_only_in_dpapi(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    handle = _run(client_file, store, Browser())
    assert handle.secret_ref == SECRET_REF == 'drive-primary-oauth'
    assert handle.scope == SCOPE
    assert store.current_version(SECRET_REF) == handle.version == 1
    assert server.count('code') == 1
    assert DpapiRefreshTokenReader(store).read(SECRET_REF).reveal() == REFRESH

    out, err = capsys.readouterr()
    canaries = [REFRESH, CLIENT_SECRET, ACCESS_PREFIX]
    assert find_canaries(canaries, out, err, caplog.text, repr(handle), str(handle)) == []

    vault_dir = store._root
    for p_file in vault_dir.rglob('*'):
        if p_file.is_file():
            assert REFRESH.encode('utf-8') not in p_file.read_bytes()

    assert handle.fingerprint == 'v1'
    assert set(vars(handle).keys()) == {'secret_ref', 'version', 'scope'}


def test_authorization_request_has_state_pkce_exact_scope_loopback(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    browser = Browser()
    _run(client_file, store, browser)
    last_auth = server.last_auth
    assert last_auth.get('scope') == [SCOPE]
    assert last_auth.get('code_challenge_method') == ['S256']
    assert bool(last_auth.get('code_challenge', [''])[0])
    assert bool(last_auth.get('state', [''])[0])
    assert last_auth.get('access_type') == ['offline']
    redirect_uri = last_auth.get('redirect_uri', [''])[0]
    assert redirect_uri.startswith('http://127.0.0.1:')
    port = _port_of(browser.url)
    assert port > 0


def test_wrong_state_is_rejected_and_nothing_stored(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.state_override = 'tampered'
    browser = Browser()
    with pytest.raises(OAuthFlowError):
        _run(client_file, store, browser)
    assert server.count('code') == 0
    assert store.current_version(SECRET_REF) is None
    _closed(_port_of(browser.url))


def test_expired_consent_closes_port(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    browser = Browser()
    browser.follow = False
    with pytest.raises(OAuthConsentTimeoutError):
        _run(client_file, store, browser, timeout=1)
    _closed(_port_of(browser.url))
    assert store.current_version(SECRET_REF) is None


def test_port_closed_after_success(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    browser = Browser()
    _run(client_file, store, browser)
    _closed(_port_of(browser.url))


def test_broader_granted_scope_is_rejected(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.granted_scope = SCOPE + ' https://www.googleapis.com/auth/drive'
    with pytest.raises(OAuthFlowError):
        _run(client_file, store, Browser())
    assert store.current_version(SECRET_REF) is None


def test_missing_refresh_token_is_rejected(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.issue_refresh_token = False
    with pytest.raises(OAuthFlowError):
        _run(client_file, store, Browser())
    assert store.current_version(SECRET_REF) is None


def test_client_secrets_inside_git_tree_is_rejected(tmp_path: Path) -> None:
    repo_dir = tmp_path / 'repo'
    (repo_dir / '.git').mkdir(parents=True)
    bad_client = repo_dir / 'client.json'
    bad_client.write_text(json.dumps({'installed': {'client_secret': CLIENT_SECRET}}), encoding='utf-8')
    with pytest.raises(OAuthFlowError) as exc_info:
        require_client_secrets_outside_git(bad_client)
    assert CLIENT_SECRET not in str(exc_info.value)

    ok_client = tmp_path / 'ok' / 'client.json'
    ok_client.parent.mkdir(parents=True)
    ok_client.write_text(json.dumps({'installed': {'client_secret': CLIENT_SECRET}}), encoding='utf-8')
    res = require_client_secrets_outside_git(ok_client)
    assert res == ok_client.resolve()


def test_invalid_client_file_error_does_not_echo_content(tmp_path: Path) -> None:
    bad_json = tmp_path / 'bad.json'
    bad_json.write_text('not-json ' + CLIENT_SECRET, encoding='utf-8')
    with pytest.raises(OAuthFlowError) as exc_info:
        load_client_config(bad_json)
    assert CLIENT_SECRET not in str(exc_info.value)
    assert CLIENT_SECRET not in repr(exc_info.value)

    missing_secret = tmp_path / 'missing_secret.json'
    missing_secret.write_text(json.dumps({'installed': {'client_id': CLIENT_ID}}), encoding='utf-8')
    with pytest.raises(OAuthFlowError):
        load_client_config(missing_secret)

    non_existent = tmp_path / 'does_not_exist.json'
    with pytest.raises(OAuthFlowError):
        load_client_config(non_existent)


def test_config_requires_explicit_keys_and_positive_timeout(tmp_path: Path) -> None:
    p_file = tmp_path / 'secrets' / 'client.json'
    cfg = DriveOAuthConfig.from_mapping({
        'oauth_client_secrets_path': str(p_file),
        'oauth_consent_timeout_seconds': 30,
    })
    assert cfg.client_secrets_path == Path(p_file)
    assert cfg.consent_timeout_seconds == 30

    with pytest.raises(ValueError):
        DriveOAuthConfig.from_mapping({'oauth_consent_timeout_seconds': 30})

    with pytest.raises(ValueError):
        DriveOAuthConfig.from_mapping({'oauth_client_secrets_path': str(p_file)})

    for bad_t in (0, -1, True, '5'):
        with pytest.raises(ValueError):
            DriveOAuthConfig.from_mapping({
                'oauth_client_secrets_path': str(p_file),
                'oauth_consent_timeout_seconds': bad_t,
            })


def test_client_config_points_only_to_local_fake(
    client_file: Path,
    server: FakeOAuthServer,
) -> None:
    loaded = load_client_config(client_file)['installed']
    assert loaded['auth_uri'].startswith('http://127.0.0.1:')
    assert loaded['token_uri'].startswith('http://127.0.0.1:')
    assert 'accounts.google.com' not in loaded['auth_uri']
    assert 'accounts.google.com' not in loaded['token_uri']


class _Statuses:
    def __init__(self) -> None:
        self.value = ExternalAccountStatus.ENABLED

    def account_status(self, account_ref: str) -> ExternalAccountStatus:
        return self.value


class _Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def _broker(
    client_file: Path,
    store: DpapiSecretStore,
    statuses: _Statuses,
    clock: _Clock,
    max_ttl: int = 60,
) -> DriveAccessTokenBroker:
    store.put(SECRET_REF, SecretValue(REFRESH))
    return DriveAccessTokenBroker(client_file, max_ttl, store, DpapiRefreshTokenReader(store), statuses, clock)


def _token(broker: DriveAccessTokenBroker) -> str:
    with broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as t:
        return t


def test_token_is_cached_within_ttl_then_refreshed_after_expiry(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock, max_ttl=60)

    tok1 = _token(broker)
    assert tok1.startswith(ACCESS_PREFIX)
    assert server.count('refresh') == 1

    tok2 = _token(broker)
    assert tok2 == tok1
    assert server.count('refresh') == 1

    clock.now += timedelta(seconds=61)
    tok3 = _token(broker)
    assert tok3 != tok1
    assert server.count('refresh') == 2


def test_server_short_expiry_wins_over_max_ttl(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.expires_in = 30
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock, max_ttl=3300)

    tok1 = _token(broker)
    assert server.count('refresh') == 1

    clock.now += timedelta(seconds=31)
    tok2 = _token(broker)
    assert tok2 != tok1
    assert server.count('refresh') == 2


def test_server_short_expiry_is_anchored_to_injected_clock_not_real_time(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.expires_in = 30
    statuses = _Statuses()
    clock = _Clock()
    clock.now = datetime.now(timezone.utc) - timedelta(minutes=10)
    broker = _broker(client_file, store, statuses, clock, max_ttl=3300)

    tok1 = _token(broker)
    assert server.count('refresh') == 1

    clock.now += timedelta(seconds=31)
    tok2 = _token(broker)
    assert tok2 != tok1
    assert server.count('refresh') == 2


@pytest.mark.parametrize('status', [
    ExternalAccountStatus.REVOKED,
    ExternalAccountStatus.INVALID,
    ExternalAccountStatus.DISABLED,
])
def test_dead_account_status_is_denied_without_network(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
    status: ExternalAccountStatus,
) -> None:
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock, max_ttl=60)

    tok1 = _token(broker)
    assert server.count('refresh') == 1

    statuses.value = status
    with pytest.raises(DriveTokenDeniedError):
        _token(broker)
    assert server.count('refresh') == 1

    statuses.value = ExternalAccountStatus.ENABLED
    tok2 = _token(broker)
    assert server.count('refresh') == 2


def test_revoked_secret_version_is_denied(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock)
    store.revoke(SECRET_REF, 1)
    with pytest.raises(DriveTokenDeniedError):
        _token(broker)
    assert server.count('refresh') == 0


def test_wrong_credential_method_or_account_is_rejected(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock)

    with pytest.raises(ValueError):
        with broker.acquire('env_var', ACCOUNT_REF):
            pass

    with pytest.raises(ValueError):
        with broker.acquire(CREDENTIAL_METHOD, 'other-account'):
            pass

    assert server.count('refresh') == 0


def test_refresh_failure_is_redacted(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
) -> None:
    server.refresh_error = True
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock)

    with pytest.raises(DriveTokenRefreshError) as ei:
        _token(broker)
    assert find_canaries([REFRESH, CLIENT_SECRET, ERRBODY], str(ei.value), repr(ei.value)) == []


def test_refresh_token_never_leaves_broker(
    client_file: Path,
    server: FakeOAuthServer,
    store: DpapiSecretStore,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    statuses = _Statuses()
    clock = _Clock()
    broker = _broker(client_file, store, statuses, clock, max_ttl=60)

    tok1 = _token(broker)
    clock.now += timedelta(seconds=61)
    tok2 = _token(broker)

    out, err = capsys.readouterr()
    assert find_canaries([REFRESH, CLIENT_SECRET], tok1, tok2, repr(broker), repr(vars(broker)), caplog.text, out, err) == []

    for attr in ('refresh_token', 'get_refresh_token', 'read', 'reveal'):
        assert not hasattr(broker, attr)

    for env_val in os.environ.values():
        assert REFRESH not in env_val


def test_max_ttl_must_be_positive_int(client_file: Path, store: DpapiSecretStore) -> None:
    statuses = _Statuses()
    clock = _Clock()
    reader = DpapiRefreshTokenReader(store)
    for v in (0, -5, True, '60'):
        with pytest.raises(ValueError):
            DriveAccessTokenBroker(client_file, v, store, reader, statuses, clock)


def test_sources_do_not_use_env_or_database() -> None:
    root = Path(__file__).resolve().parents[4]
    assert (root / 'src').is_dir()
    sec_dir = root / 'src' / 'controlplane' / 'infrastructure' / 'security'
    t_loopback = (sec_dir / 'oauth_google_loopback.py').read_text(encoding='utf-8')
    t_token = (sec_dir / 'oauth_drive_token.py').read_text(encoding='utf-8')
    both = t_loopback + ' ' + t_token

    for forbidden in ('os.environ', 'getenv', 'psycopg', 'sqlalchemy', 'from src.'):
        assert forbidden not in both

    assert 'drive.file' in t_loopback
    assert 'SecretStorePort' in t_loopback
    assert 'SecretStorePort' in t_token
