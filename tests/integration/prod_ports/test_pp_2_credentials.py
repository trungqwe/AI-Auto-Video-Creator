"""PP-2: ports.json loader, RouterKeyCredentials, router key entry and set_router_key.py."""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import json
import logging
import pathlib

import pytest

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.infrastructure.production_ports.credentials import ProviderCredentialError, RouterKeyCredentials
from controlplane.infrastructure.production_ports.ports_config import PortsConfig, load_ports_config
from controlplane.infrastructure.production_ports.router_key_entry import run, store_router_key
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.secret_redaction import REDACTED

ROOT = pathlib.Path(__file__).resolve().parents[3]
PORTS_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'ports.json'
SCRIPT_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'set_router_key.py'
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
PKG_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports'
CANARY = 'sk-pp2-canary-0123456789abcdef'
ACCOUNT = 'router-primary'
SECRET = 'router-primary-api-key'
SAVED = 'Đã lưu khóa 9Router qua kho DPAPI: ' + SECRET + ' (v1)'
DELETE = object()
BS = chr(92)


def mutated(tmp_path: pathlib.Path, keys: tuple, value: object) -> pathlib.Path:
    data = json.loads(PORTS_PATH.read_text(encoding='utf-8'))
    node = data
    for key in keys[:-1]:
        node = node[key]
    if value is DELETE:
        del node[keys[-1]]
    else:
        node[keys[-1]] = value
    target = tmp_path / 'ports.json'
    target.write_text(json.dumps(data), encoding='utf-8')
    return target

MISSING = [('revision',), ('router',), ('router', 'account_ref'), ('router', 'secret_ref'), ('gpu_lease',), ('gpu_lease', 'grace_seconds'), ('gpu_lease', 'wait_seconds'), ('drive',), ('drive', 'placement_state_file'), ('drive', 'artifact_namespaces')]
BAD = (
    [(('revision',), v) for v in (0, -1, True, '1', 1.5, None)]
    + [(('router', 'account_ref'), v) for v in ('', '  ', 7, None)]
    + [(('router', 'secret_ref'), v) for v in ('', '  ', 7, None)]
    + [(('gpu_lease', 'grace_seconds'), v) for v in (0, -1, True, '60', 60.5, None)]
    + [(('gpu_lease', 'wait_seconds'), v) for v in (0, -1, True, '180', 180.5, None)]
    + [(('drive', 'placement_state_file'), v) for v in ('', 7, 'a/b', 'a' + BS + 'b', '..', None)]
    + [(('drive', 'artifact_namespaces'), v) for v in ([], 'original', ['original', 'original'], ['original', ''], [1], None)]
    + [(('router',), v) for v in ([], 'x', None)]
    + [(('extra',), 1), (('router', 'extra'), 1)]
)


def test_real_ports_json_loads_with_expected_values() -> None:
    config = load_ports_config(PORTS_PATH)
    assert isinstance(config, PortsConfig)
    assert config.revision == 2
    assert (config.router.account_ref, config.router.secret_ref) == (ACCOUNT, SECRET)
    assert config.gpu_lease.grace_seconds == 60
    assert config.gpu_lease.wait_seconds == 180
    assert config.drive.placement_state_file == 'drive-placement.json'
    assert config.drive.artifact_namespaces == ('original', 'reusable', 'output')
    assert config.router.secret_ref != 'drive-primary-oauth'
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.revision = 2


def test_ports_json_is_utf8_without_bom() -> None:
    raw = PORTS_PATH.read_bytes()
    assert not raw.startswith(bytes([0xEF, 0xBB, 0xBF]))
    raw.decode('utf-8')


@pytest.mark.parametrize('keys', MISSING)
def test_missing_key_is_rejected(tmp_path, keys) -> None:
    with pytest.raises(ValueError):
        load_ports_config(mutated(tmp_path, keys, DELETE))


@pytest.mark.parametrize('keys, value', BAD)
def test_wrong_type_or_value_is_rejected(tmp_path, keys, value) -> None:
    with pytest.raises(ValueError):
        load_ports_config(mutated(tmp_path, keys, value))


@pytest.mark.parametrize('text', ['', '[]', '{', chr(0xFEFF) + '{}'])
def test_non_object_or_invalid_json_is_rejected(tmp_path, text) -> None:
    target = tmp_path / 'ports.json'
    target.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        load_ports_config(target)

@pytest.fixture
def store(tmp_path):
    return DpapiSecretStore(tmp_path / 'vault')


def make(store, value=CANARY):
    store_router_key(store, SECRET, lambda: value)
    return RouterKeyCredentials(store, ACCOUNT, SECRET)


def test_acquire_is_contextmanager_returning_stored_key(store) -> None:
    credentials = make(store)
    assert hasattr(RouterKeyCredentials.acquire, '__wrapped__')
    with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT) as key:
        assert key == CANARY and type(key) is str


def test_stored_key_is_stripped(store) -> None:
    credentials = make(store, '  ' + CANARY + chr(10))
    with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT) as key:
        assert key == CANARY


@pytest.mark.parametrize('method, account', [('oauth', ACCOUNT), ('', ACCOUNT), (CREDENTIAL_METHOD, 'drive-primary'), (CREDENTIAL_METHOD, ''), (CREDENTIAL_METHOD, None)])
def test_unknown_method_or_account_raises_value_error(store, method, account) -> None:
    credentials = make(store)
    with pytest.raises(ValueError) as info:
        with credentials.acquire(method, account):
            pytest.fail('must not yield')
    assert CANARY not in str(info.value) + repr(info.value)


def test_missing_alias_raises_provider_credential_error(store) -> None:
    credentials = RouterKeyCredentials(store, ACCOUNT, SECRET)
    with pytest.raises(ProviderCredentialError):
        with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT):
            pytest.fail('must not yield')


def test_revoked_alias_raises_without_value(store) -> None:
    credentials = make(store)
    store.revoke(SECRET, store.current_version(SECRET))
    with pytest.raises(ProviderCredentialError) as info:
        with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT):
            pytest.fail('must not yield')
    assert CANARY not in str(info.value) + repr(info.value)


def test_undecryptable_cipher_raises_without_value(tmp_path) -> None:
    other = DpapiSecretStore(tmp_path / 'vault', entropy=b'pp2-other-entropy')
    store_router_key(other, SECRET, lambda: CANARY)
    credentials = RouterKeyCredentials(DpapiSecretStore(tmp_path / 'vault'), ACCOUNT, SECRET)
    with pytest.raises(ProviderCredentialError) as info:
        with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT):
            pytest.fail('must not yield')
    assert CANARY not in str(info.value) + repr(info.value)
    assert info.value.__cause__ is None


@pytest.mark.parametrize('account, secret', [('', SECRET), ('  ', SECRET), (ACCOUNT, ''), (ACCOUNT, None), (None, SECRET), (7, SECRET)])
def test_constructor_rejects_bad_refs(store, account, secret) -> None:
    with pytest.raises(ValueError):
        RouterKeyCredentials(store, account, secret)


def test_no_canary_in_repr_str_stdout_stderr_or_log(store, capsys, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    credentials = make(store)
    with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT) as key:
        assert key == CANARY
    shown = repr(credentials) + str(credentials)
    out, err = capsys.readouterr()
    assert CANARY not in shown + out + err + caplog.text
    assert REDACTED in repr(credentials)

@pytest.mark.parametrize('value', ['', '   ', chr(9) + chr(13) + chr(10)])
def test_blank_key_is_rejected_and_nothing_stored(store, value) -> None:
    with pytest.raises(ValueError):
        store_router_key(store, SECRET, lambda: value)
    assert store.current_version(SECRET) is None


def test_non_string_key_is_rejected(store) -> None:
    with pytest.raises(ValueError):
        store_router_key(store, SECRET, lambda: None)
    assert store.current_version(SECRET) is None


def test_store_router_key_returns_increasing_versions(store) -> None:
    assert store_router_key(store, SECRET, lambda: CANARY) == 1
    assert store_router_key(store, SECRET, lambda: CANARY + 'x') == 2
    assert store.current_version(SECRET) == 2


def test_run_prints_only_alias_and_version(tmp_path, capsys) -> None:
    vault = tmp_path / 'vault'
    lines = []
    version = run(vault, PORTS_PATH, lambda: ' ' + CANARY + ' ', lines.append)
    assert lines == [SAVED] and version == 1
    out, err = capsys.readouterr()
    assert CANARY not in out + err + ' '.join(lines)
    credentials = RouterKeyCredentials(DpapiSecretStore(vault), ACCOUNT, SECRET)
    with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT) as key:
        assert key == CANARY


def test_run_blank_key_prints_nothing(tmp_path) -> None:
    lines = []
    with pytest.raises(ValueError):
        run(tmp_path / 'vault', PORTS_PATH, lambda: '   ', lines.append)
    assert lines == []


def test_run_asks_for_no_key_when_ports_config_is_invalid(tmp_path) -> None:
    calls = []

    def read_value() -> str:
        calls.append(1)
        return CANARY

    broken = mutated(tmp_path, ('router', 'secret_ref'), DELETE)
    with pytest.raises(ValueError):
        run(tmp_path / 'vault', broken, read_value, lambda line: None)
    assert calls == []

def dotted(node) -> str:
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + '.' + node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ''


def load_script():
    spec = importlib.util.spec_from_file_location('pp2_set_router_key', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_uses_getpass_and_no_command_line_key() -> None:
    text = SCRIPT_PATH.read_text(encoding='utf-8')
    tree = ast.parse(text)
    names = {dotted(n) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert {'getpass.getpass', 'launcher.resolve_layout', 'os.environ'} <= names
    assert 'sys.argv' not in names and 'argv' not in text
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert 'argparse' not in imported


def test_launcher_commands_unchanged() -> None:
    text = LAUNCHER_PATH.read_text(encoding='utf-8')
    assert "COMMANDS = ('start', 'stop', 'down', 'status', 'backup', 'restore', 'oauth')" in text
    assert 'set_router_key' not in text


def test_script_main_stores_key_from_getpass(tmp_path, monkeypatch, capsys) -> None:
    module = load_script()
    monkeypatch.setenv('AIAVC_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('getpass.getpass', lambda *args, **kwargs: ' ' + CANARY + ' ')
    assert module.main() == 0
    out, err = capsys.readouterr()
    assert out == SAVED + chr(10) and err == ''
    credentials = RouterKeyCredentials(DpapiSecretStore(tmp_path / 'data' / 'vault'), ACCOUNT, SECRET)
    with credentials.acquire(CREDENTIAL_METHOD, ACCOUNT) as key:
        assert key == CANARY


def test_script_main_reports_layout_error_without_traceback(monkeypatch, capsys) -> None:
    module = load_script()
    monkeypatch.delenv('AIAVC_DATA_DIR', raising=False)
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    assert module.main() == 1
    out, err = capsys.readouterr()
    assert out == '' and 'AIAVC_DATA_DIR' in err and 'Traceback' not in err


@pytest.mark.parametrize('name', ['credentials.py', 'router_key_entry.py', 'ports_config.py'])
def test_sources_have_no_forbidden_text(name) -> None:
    text = (PKG_DIR / name).read_text(encoding='utf-8').lower()
    for forbidden in ('from src.', 'mock', 'fake', 'os.environ', 'getenv', 'argv', 'subprocess'):
        assert forbidden not in text
