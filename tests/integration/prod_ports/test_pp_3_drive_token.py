"""PP-3: VaultAccountStatusPort and build_drive_token_broker over the DPAPI vault (CT-SEC-001, INV-012).

Loopback token server only; no Google call, no real secret."""
from __future__ import annotations

import json
import logging
import pathlib
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

if sys.platform != 'win32':
    pytest.skip('DpapiSecretStore dùng DPAPI của Windows; bỏ qua trên nền tảng không phải win32', allow_module_level=True)

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.production_ports.drive_token import VaultAccountStatusPort, build_drive_token_broker
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import DriveAccessTokenBroker, DriveTokenDeniedError, DriveTokenRefreshError
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF, SECRET_REF
from controlplane.infrastructure.security.secret_redaction import SecretValue, find_canaries

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'drive_token.py'
REFRESH = 'CANARY-PP3-REFRESH-5e1a'
CLIENT_ID = 'pp3-client.apps.test'
CLIENT_SECRET = 'CANARY-PP3-CLIENT-SECRET-7c2d'
ACCESS_PREFIX = 'CANARY-PP3-ACCESS-'
ERRBODY = 'CANARY-PP3-ERRBODY-3b8f'


class TokenServer:
    def __init__(self) -> None:
        self.status = 200
        self.expires_in = 3600
        self.calls = 0
        self._lock = threading.Lock()
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                size = int(self.headers.get('Content-Length', '0'))
                form = urllib.parse.parse_qs(self.rfile.read(size).decode('utf-8'))
                with srv._lock:
                    srv.calls += 1
                    number = srv.calls
                ok = srv.status == 200 and form.get('grant_type') == ['refresh_token'] and form.get('refresh_token') == [REFRESH]
                body = {'access_token': ACCESS_PREFIX + str(number), 'expires_in': srv.expires_in, 'token_type': 'Bearer'} if ok else {'error': 'invalid_grant', 'error_description': ERRBODY}
                self.send_response(200 if ok else 400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(body).encode('utf-8'))

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def token_uri(self) -> str:
        return f'http://127.0.0.1:{self.server.server_port}/token'

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')


@pytest.fixture
def server():
    srv = TokenServer()
    try:
        yield srv
    finally:
        srv.close()


@pytest.fixture
def client_file(tmp_path: pathlib.Path, server: TokenServer) -> pathlib.Path:
    folder = tmp_path / 'secrets'
    folder.mkdir()
    target = folder / 'oauth-client.json'
    installed = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'auth_uri': server.token_uri, 'token_uri': server.token_uri, 'redirect_uris': ['http://127.0.0.1']}
    target.write_text(json.dumps({'installed': installed}), encoding='utf-8')
    return target


@pytest.fixture
def store(tmp_path: pathlib.Path) -> DpapiSecretStore:
    return DpapiSecretStore(tmp_path / 'vault')


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def make(client_file, store, clock, max_ttl=60, seed=True):
    if seed:
        store.put(SECRET_REF, SecretValue(REFRESH))
    return build_drive_token_broker(client_file, max_ttl, store, clock)


def token(broker) -> str:
    with broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as value:
        return value


class OnlyVersion:
    def __init__(self, version) -> None:
        self.version = version
        self.asked = []

    def current_version(self, secret_ref):
        self.asked.append(secret_ref)
        return self.version


def test_status_is_enabled_when_account_matches_and_alias_exists(store) -> None:
    store.put(SECRET_REF, SecretValue(REFRESH))
    assert VaultAccountStatusPort(store).account_status(ACCOUNT_REF) is ExternalAccountStatus.ENABLED


def test_status_is_revoked_when_alias_is_missing(store) -> None:
    assert VaultAccountStatusPort(store).account_status(ACCOUNT_REF) is ExternalAccountStatus.REVOKED


def test_status_is_revoked_after_alias_revoke(store) -> None:
    version = store.put(SECRET_REF, SecretValue(REFRESH))
    store.revoke(SECRET_REF, version)
    assert VaultAccountStatusPort(store).account_status(ACCOUNT_REF) is ExternalAccountStatus.REVOKED


@pytest.mark.parametrize('ref', ['other-account', '', 'router-primary', 'DRIVE-PRIMARY'])
def test_status_is_revoked_for_other_account_even_with_alias(store, ref) -> None:
    store.put(SECRET_REF, SecretValue(REFRESH))
    assert VaultAccountStatusPort(store).account_status(ref) is ExternalAccountStatus.REVOKED


def test_status_reads_only_current_version_from_the_store() -> None:
    present = OnlyVersion(3)
    assert VaultAccountStatusPort(present).account_status(ACCOUNT_REF) is ExternalAccountStatus.ENABLED
    assert present.asked == [SECRET_REF]
    absent = OnlyVersion(None)
    assert VaultAccountStatusPort(absent).account_status(ACCOUNT_REF) is ExternalAccountStatus.REVOKED
    assert absent.asked == [SECRET_REF]


def test_builder_returns_drive_access_token_broker(server, client_file, store) -> None:
    assert isinstance(make(client_file, store, Clock()), DriveAccessTokenBroker)


def test_second_acquire_within_ttl_reuses_token_then_refreshes_after_ttl(server, client_file, store) -> None:
    clock = Clock()
    broker = make(client_file, store, clock)
    first = token(broker)
    assert first.startswith(ACCESS_PREFIX) and server.calls == 1
    assert token(broker) == first and server.calls == 1
    clock.now += timedelta(seconds=61)
    third = token(broker)
    assert third != first and third.startswith(ACCESS_PREFIX) and server.calls == 2


def test_missing_alias_is_denied_without_server_call(server, client_file, store) -> None:
    broker = make(client_file, store, Clock(), seed=False)
    with pytest.raises(DriveTokenDeniedError):
        token(broker)
    assert server.calls == 0


def test_revoked_alias_is_denied_without_server_call(server, client_file, store) -> None:
    broker = make(client_file, store, Clock())
    store.revoke(SECRET_REF, store.current_version(SECRET_REF))
    with pytest.raises(DriveTokenDeniedError):
        token(broker)
    assert server.calls == 0


def test_server_400_raises_refresh_error_without_secrets(server, client_file, store) -> None:
    server.status = 400
    broker = make(client_file, store, Clock())
    with pytest.raises(DriveTokenRefreshError) as info:
        token(broker)
    assert server.calls == 1
    assert find_canaries([REFRESH, CLIENT_SECRET, ERRBODY], str(info.value), repr(info.value)) == []


@pytest.mark.parametrize('method, account', [('oauth', ACCOUNT_REF), ('', ACCOUNT_REF), ('env_var', ACCOUNT_REF), (CREDENTIAL_METHOD, 'router-primary'), (CREDENTIAL_METHOD, ''), (CREDENTIAL_METHOD, None)])
def test_unknown_method_or_account_raises_value_error(server, client_file, store, method, account) -> None:
    broker = make(client_file, store, Clock())
    with pytest.raises(ValueError) as info:
        with broker.acquire(method, account):
            pytest.fail('must not yield')
    assert find_canaries([REFRESH, CLIENT_SECRET], str(info.value), repr(info.value)) == []
    assert server.calls == 0


@pytest.mark.parametrize('ttl', [0, -5, True, '60'])
def test_builder_rejects_bad_ttl(client_file, store, ttl) -> None:
    with pytest.raises(ValueError):
        build_drive_token_broker(client_file, ttl, store, Clock())


def test_no_canary_in_repr_stdout_stderr_log_or_disk(server, client_file, store, tmp_path, capsys, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    clock = Clock()
    broker = make(client_file, store, clock)
    first = token(broker)
    clock.now += timedelta(seconds=61)
    second = token(broker)
    out, err = capsys.readouterr()
    shown = repr(broker) + str(broker) + repr(VaultAccountStatusPort(store))
    assert find_canaries([REFRESH, CLIENT_SECRET, first, second], shown, out, err, caplog.text) == []
    for path in tmp_path.rglob('*'):
        if path.is_file() and path != client_file:
            data = path.read_bytes()
            assert first.encode('utf-8') not in data and second.encode('utf-8') not in data


def test_source_has_no_forbidden_text() -> None:
    text = SOURCE.read_text(encoding='utf-8').lower()
    for forbidden in ('from src.', 'mock', 'fake', 'os.environ', 'getenv', 'psycopg', 'sqlalchemy', 'subprocess', 'google.auth', 'requests', 'urllib', 'open(', 'write_'):
        assert forbidden not in text
    assert 'driveaccesstokenbroker' in text and 'dpapirefreshtokenreader' in text and 'vaultaccountstatusport' in text
