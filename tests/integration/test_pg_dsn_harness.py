import importlib.util
import os
import socket
import subprocess
from pathlib import Path

import psycopg
import pytest

_CONFTEST_PATH = Path(__file__).with_name("conftest.py")


def _load_conftest_module():
    spec = importlib.util.spec_from_file_location("pg_dsn_harness_conftest_under_test", _CONFTEST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m2_test_pg_dsn_points_to_postgres_18_6_with_createdb():
    dsn = os.environ.get("M2_TEST_PG_DSN")
    if not dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; container ai-auto-video-m2-pg is not reachable and no fallback is permitted.")
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as connection:
        version = connection.execute("SHOW server_version").fetchone()[0]
        can_create_db = connection.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user"
        ).fetchone()[0]
    assert version.startswith("18.6")
    assert can_create_db is True


class _FakeConnection:
    def close(self):
        pass


def _stub_tcp(monkeypatch, error=None):
    calls = []

    def _fake_create_connection(address, timeout=None, *args, **kwargs):
        calls.append((address, timeout))
        if error is not None:
            raise error
        return _FakeConnection()

    monkeypatch.setattr(socket, "create_connection", _fake_create_connection)
    return calls


def _stub_docker(monkeypatch, output="", error=None):
    calls = []

    def _fake_check_output(*args, **kwargs):
        calls.append(args)
        if error is not None:
            raise error
        return output

    monkeypatch.setattr(subprocess, "check_output", _fake_check_output)
    return calls


def test_resolve_m2_test_pg_dsn_keeps_preset_value_when_it_accepts_connections(monkeypatch):
    preset = "postgresql://preset:preset@127.0.0.1:1/preset"
    monkeypatch.setenv("M2_TEST_PG_DSN", preset)
    tcp_calls = _stub_tcp(monkeypatch)
    docker_calls = _stub_docker(monkeypatch, error=OSError("docker must not be invoked"))
    module = _load_conftest_module()
    assert module.resolve_m2_test_pg_dsn() == preset
    assert os.environ["M2_TEST_PG_DSN"] == preset
    assert (("127.0.0.1", 1), 2) in tcp_calls
    assert docker_calls == []


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_resolve_m2_test_pg_dsn_rediscovers_port_when_loopback_preset_refuses(monkeypatch, host):
    preset = f"postgresql://alice:s3cret@{host}:1/appdb"
    monkeypatch.setenv("M2_TEST_PG_DSN", preset)
    _stub_tcp(monkeypatch, error=ConnectionRefusedError("refused"))
    docker_calls = _stub_docker(monkeypatch, output="127.0.0.1:5555\n")
    module = _load_conftest_module()
    expected = f"postgresql://alice:s3cret@{host}:5555/appdb"
    assert module.resolve_m2_test_pg_dsn() == expected
    assert os.environ["M2_TEST_PG_DSN"] == expected
    assert docker_calls
    assert docker_calls[0][0] == ["docker", "port", "ai-auto-video-m2-pg", "5432/tcp"]


def test_resolve_m2_test_pg_dsn_keeps_non_loopback_preset_even_when_refused(monkeypatch):
    preset = "postgresql://remote:pw@db.example.test:5432/remote_db"
    monkeypatch.setenv("M2_TEST_PG_DSN", preset)
    _stub_tcp(monkeypatch, error=OSError("refused"))
    docker_calls = _stub_docker(monkeypatch, output="127.0.0.1:5555\n")
    module = _load_conftest_module()
    assert module.resolve_m2_test_pg_dsn() == preset
    assert os.environ["M2_TEST_PG_DSN"] == preset
    assert docker_calls == []


@pytest.mark.parametrize(
    "docker_kwargs",
    [
        {"error": subprocess.CalledProcessError(1, "docker")},
        {"error": OSError("docker missing")},
        {"output": "\n"},
    ],
)
def test_resolve_m2_test_pg_dsn_keeps_preset_when_docker_port_fails(monkeypatch, docker_kwargs):
    preset = "postgresql://alice:s3cret@127.0.0.1:1/appdb"
    monkeypatch.setenv("M2_TEST_PG_DSN", preset)
    _stub_tcp(monkeypatch, error=ConnectionRefusedError("refused"))
    _stub_docker(monkeypatch, **docker_kwargs)
    module = _load_conftest_module()
    assert module.resolve_m2_test_pg_dsn() == preset
    assert os.environ["M2_TEST_PG_DSN"] == preset
