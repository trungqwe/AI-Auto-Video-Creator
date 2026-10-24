import os
import socket
import subprocess
from urllib.parse import urlsplit, urlunsplit

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


def _accepts_tcp(host, port):
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        return False
    return True


def _discover_container_port():
    try:
        output = subprocess.check_output(
            ["docker", "port", "ai-auto-video-m2-pg", "5432/tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        port = output.strip().splitlines()[0].split(":")[-1]
    except Exception:
        return None
    return port if port.isdigit() else None


def _rediscover_loopback_dsn(preset):
    try:
        parts = urlsplit(preset)
        host = parts.hostname
        port = parts.port or 5432
    except ValueError:
        return preset
    if host not in _LOOPBACK_HOSTS or _accepts_tcp(host, port):
        return preset
    new_port = _discover_container_port()
    if new_port is None:
        return preset
    userinfo, at, _ = parts.netloc.rpartition("@")
    netloc = f"{userinfo}{at}{host}:{new_port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def resolve_m2_test_pg_dsn():
    preset = os.environ.get("M2_TEST_PG_DSN")
    if preset:
        os.environ["M2_TEST_PG_DSN"] = _rediscover_loopback_dsn(preset)
    else:
        port = _discover_container_port()
        if port is not None:
            os.environ["M2_TEST_PG_DSN"] = f"postgresql://m2test:m2test@127.0.0.1:{port}/postgres"
    return os.environ.get("M2_TEST_PG_DSN", "")


resolve_m2_test_pg_dsn()
