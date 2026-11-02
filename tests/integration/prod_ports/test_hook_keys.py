"""HOOK-KEYS: khoá Pixabay và Freesound vào kho DPAPI của launcher, không bao giờ in hay nhận qua đối số.

coveredIds: CT-SEC-001
"""
from __future__ import annotations

import importlib.util
import io
import logging
import pathlib

import pytest

from controlplane.infrastructure.production_ports.stock_key_entry import (
    STOCK_SECRET_REFS,
    StockKeyCredentials,
    StockKeyError,
    StockKeyMissing,
    key_versions,
    read_key_file,
    run,
    store_stock_key,
)
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'tools' / 'launcher' / 'prod' / 'set_stock_key.py'
CANARY = 'Zq7canaryKEY0123456789abcdef'


def load_script():
    spec = importlib.util.spec_from_file_location('hook_keys_set_stock_key', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def store(tmp_path):
    return DpapiSecretStore(tmp_path / 'vault')


@pytest.fixture
def data_dir(tmp_path):
    path = tmp_path / 'data'
    path.mkdir()
    return path


def test_both_providers_have_distinct_vault_aliases() -> None:
    assert sorted(STOCK_SECRET_REFS) == ['freesound', 'pixabay']
    assert len(set(STOCK_SECRET_REFS.values())) == 2


@pytest.mark.parametrize('provider', ['pixabay', 'freesound'])
def test_stored_key_is_read_back_stripped_through_acquire(store, provider) -> None:
    assert store_stock_key(store, provider, lambda: '  ' + CANARY + chr(10)) == 1
    with StockKeyCredentials(store).acquire(provider) as key:
        assert key == CANARY
    assert key_versions(store)[provider] == 1


@pytest.mark.parametrize('value', ['', '   ', 'two words', 'x' * 257, 'tab' + chr(9) + 'inside', None])
def test_bad_key_is_rejected_and_nothing_is_stored(store, value) -> None:
    with pytest.raises(StockKeyError) as raised:
        store_stock_key(store, 'pixabay', lambda: value)
    assert store.current_version(STOCK_SECRET_REFS['pixabay']) is None
    if isinstance(value, str) and value.strip():
        assert value.strip() not in str(raised.value)


def test_unknown_provider_is_rejected(store) -> None:
    with pytest.raises(StockKeyError):
        store_stock_key(store, 'pexels', lambda: CANARY)


def test_missing_or_revoked_key_raises_without_value(store) -> None:
    credentials = StockKeyCredentials(store)
    with pytest.raises(StockKeyMissing):
        with credentials.acquire('freesound'):
            pass
    store_stock_key(store, 'freesound', lambda: CANARY)
    store.revoke(STOCK_SECRET_REFS['freesound'], 1)
    with pytest.raises(StockKeyMissing) as raised:
        with credentials.acquire('freesound'):
            pass
    assert CANARY not in str(raised.value)


def test_key_file_must_hold_exactly_one_line(tmp_path) -> None:
    good = tmp_path / 'good.txt'
    good.write_bytes(b'\xef\xbb\xbf' + CANARY.encode() + b'\r\n')
    assert read_key_file(good) == CANARY
    two = tmp_path / 'two.txt'
    two.write_text('client-id-value\n' + CANARY + '\n', encoding='utf-8')
    with pytest.raises(StockKeyError) as raised:
        read_key_file(two)
    assert CANARY not in str(raised.value)
    with pytest.raises(StockKeyError):
        read_key_file(tmp_path / 'missing.txt')


def test_run_prints_alias_and_version_never_the_value(store, tmp_path, capsys, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    lines: list[str] = []
    assert run(tmp_path / 'vault', 'pixabay', lambda: CANARY, lines.append) == 1
    assert lines == ['Đã lưu khoá pixabay qua kho DPAPI: ' + STOCK_SECRET_REFS['pixabay'] + ' (v1)']
    seen = capsys.readouterr()
    assert CANARY not in seen.out + seen.err + caplog.text + repr(StockKeyCredentials(store))


def test_script_reads_the_named_file_and_stdin(data_dir, tmp_path) -> None:
    script = load_script()
    key_file = tmp_path / 'pixabay.txt'
    key_file.write_text(CANARY + '\n', encoding='utf-8')
    out: list[str] = []
    env = {'AIAVC_DATA_DIR': str(data_dir)}
    assert script.main(['pixabay', '--from-file', str(key_file)], environ=env, out=out.append, err=out.append) == 0
    assert script.main(['freesound', '--stdin'], environ=env, stdin=io.StringIO(CANARY + 'fs\n'), out=out.append, err=out.append) == 0
    vault = DpapiSecretStore(data_dir / 'vault')
    with StockKeyCredentials(vault).acquire('pixabay') as key:
        assert key == CANARY
    with StockKeyCredentials(vault).acquire('freesound') as key:
        assert key == CANARY + 'fs'
    assert all(CANARY not in line for line in out)
    status: list[str] = []
    assert script.main(['--status'], environ=env, out=status.append, err=status.append) == 0
    assert status == ['freesound: ' + STOCK_SECRET_REFS['freesound'] + ' v1', 'pixabay: ' + STOCK_SECRET_REFS['pixabay'] + ' v1']


def test_script_uses_getpass_by_default(data_dir) -> None:
    script = load_script()
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return CANARY

    out: list[str] = []
    assert script.main(['freesound'], environ={'AIAVC_DATA_DIR': str(data_dir)}, ask=ask, out=out.append, err=out.append) == 0
    assert len(prompts) == 1 and CANARY not in prompts[0]
    assert out == ['Đã lưu khoá freesound qua kho DPAPI: ' + STOCK_SECRET_REFS['freesound'] + ' (v1)']


@pytest.mark.parametrize('argv', [['pixabay', CANARY], [CANARY], ['pixabay', '--key', CANARY], ['pixabay', '--from-file'], []])
def test_script_never_takes_or_echoes_a_key_from_argv(data_dir, argv) -> None:
    script = load_script()
    lines: list[str] = []
    assert script.main(argv, environ={'AIAVC_DATA_DIR': str(data_dir)}, out=lines.append, err=lines.append) == script.EXIT_USAGE
    assert lines and all(CANARY not in line for line in lines)
    assert key_versions(DpapiSecretStore(data_dir / 'vault')) == {'freesound': None, 'pixabay': None}


def test_script_reports_a_bad_file_without_its_content(data_dir, tmp_path) -> None:
    script = load_script()
    bad = tmp_path / 'bad.txt'
    bad.write_text('client id ' + CANARY + '\n', encoding='utf-8')
    lines: list[str] = []
    assert script.main(['pixabay', '--from-file', str(bad)], environ={'AIAVC_DATA_DIR': str(data_dir)}, out=lines.append, err=lines.append) == 1
    assert lines and all(CANARY not in line for line in lines)
