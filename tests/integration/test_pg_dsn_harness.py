import importlib.util
import os
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


def test_resolve_m2_test_pg_dsn_never_overrides_preset_value(monkeypatch):
    preset = "postgresql://preset:preset@127.0.0.1:1/preset"
    monkeypatch.setenv("M2_TEST_PG_DSN", preset)
    docker_calls = []

    def _record_call(*args, **kwargs):
        docker_calls.append(args)
        raise OSError("docker must not be invoked when M2_TEST_PG_DSN is preset")

    monkeypatch.setattr(subprocess, "check_output", _record_call)
    module = _load_conftest_module()
    assert module.resolve_m2_test_pg_dsn() == preset
    assert os.environ["M2_TEST_PG_DSN"] == preset
    assert docker_calls == []
