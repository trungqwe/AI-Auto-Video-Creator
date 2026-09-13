"""Capture the approved M1 bootstrap record as immutable environment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import psycopg_binary


CAPTURED_SECTIONS = ("python", "uv", "project", "postgresql")
EXPECTED_VERSIONS = {
    "python": "3.13.15",
    "uv": "0.12.13",
    "postgresql": "18.6",
}
FORBIDDEN_KEY_PARTS = ("authorization", "credential", "password", "secret", "token")


class EnvironmentProbeError(RuntimeError):
    """A live environment dependency could not be observed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_forbidden_key(value: object, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if any(part in normalized_key for part in FORBIDDEN_KEY_PARTS):
                return f"{path}.{key}"
            found = _find_forbidden_key(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def validate_bootstrap(bootstrap: dict[str, object]) -> None:
    forbidden_path = _find_forbidden_key(bootstrap)
    if forbidden_path is not None:
        raise ValueError(f"forbidden sensitive key at {forbidden_path}")

    for section, expected_version in EXPECTED_VERSIONS.items():
        section_value = bootstrap.get(section)
        if not isinstance(section_value, dict):
            raise ValueError(f"missing {section} section")
        if section_value.get("requested") != expected_version:
            raise ValueError(f"{section} requested version mismatch")
        if section_value.get("observed") != expected_version:
            raise ValueError(f"{section} observed version mismatch")

    project = bootstrap.get("project")
    if not isinstance(project, dict) or project.get("frozen_sync") is not True:
        raise ValueError("project was not synchronized in frozen mode")


def _observe_environment(
    bootstrap: dict[str, object], project_root: Path, postgresql_dsn: str
) -> dict[str, object]:
    uv_executable = Path(str(bootstrap["uv"]["executable"]))
    try:
        uv_output = subprocess.run(
            [str(uv_executable), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise EnvironmentProbeError("uv live probe failed") from error
    uv_version = uv_output.split()[1]
    try:
        subprocess.run(
            [str(uv_executable), "sync", "--frozen", "--check"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EnvironmentProbeError("frozen project sync check failed") from error

    lock_data = tomllib.loads((project_root / "uv.lock").read_text(encoding="utf-8"))
    try:
        with psycopg.connect(postgresql_dsn) as connection:
            server_version_num = int(
                connection.execute("SHOW server_version_num").fetchone()[0]
            )
            utf8_value = "Tiếng Việt"
            utf8_round_trip = connection.execute(
                "SELECT %s::text = %s::text", (utf8_value, utf8_value)
            ).fetchone()[0]
            connection.execute("CREATE TEMP TABLE m1_probe_rollback (id integer)")
            connection.execute("INSERT INTO m1_probe_rollback VALUES (1)")
            connection.rollback()
            rollback_absent = connection.execute(
                "SELECT to_regclass('pg_temp.m1_probe_rollback') IS NULL"
            ).fetchone()[0]
    except psycopg.Error as error:
        raise EnvironmentProbeError("PostgreSQL live probe failed") from error

    base_executable = Path(str(bootstrap["python"]["base_executable"]))
    return {
        "python": {
            "requested": bootstrap["python"]["requested"],
            "observed": platform.python_version(),
            "implementation": platform.python_implementation(),
            "gil": bootstrap["python"].get("gil", "standard"),
            "base_executable": str(base_executable),
            "base_executable_sha256": sha256_file(base_executable),
            "venv_executable": sys.executable,
            "venv_executable_sha256": sha256_file(Path(sys.executable)),
        },
        "uv": {
            "requested": bootstrap["uv"]["requested"],
            "observed": uv_version,
            "executable": str(uv_executable),
            "executable_sha256": sha256_file(uv_executable),
        },
        "project": {
            "pyproject_sha256": sha256_file(project_root / "pyproject.toml"),
            "uv_lock_sha256": sha256_file(project_root / "uv.lock"),
            "frozen_sync": True,
            "resolved_package_count": max(len(lock_data.get("package", [])) - 1, 0),
        },
        "postgresql": {
            "requested": bootstrap["postgresql"]["requested"],
            "observed": f"{server_version_num // 10000}.{server_version_num % 100}",
            "server_version_num": server_version_num,
            "client": "psycopg",
            "client_version": psycopg.__version__,
            "backend": "psycopg-binary",
            "backend_version": psycopg_binary.__version__,
            "image": bootstrap["postgresql"].get("image"),
            "image_digest": bootstrap["postgresql"].get("image_digest"),
            "endpoint": bootstrap["postgresql"]["endpoint"],
            "select_one": True,
            "rollback_absent": rollback_absent,
            "utf8_round_trip": utf8_round_trip,
        },
    }


def capture_environment(
    bootstrap_path: Path,
    output_path: Path,
    *,
    project_root: Path | None = None,
    postgresql_dsn: str | None = None,
) -> dict[str, object]:
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    validate_bootstrap(bootstrap)
    environment: dict[str, object] = {
        "schema_version": "1.0",
        "milestone": "M1",
        "package": "M1-P0",
        "record_kind": "captured_environment",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source_bootstrap_sha256": sha256_file(bootstrap_path),
    }
    observed = _observe_environment(
        bootstrap,
        project_root or Path.cwd(),
        postgresql_dsn or "postgresql://postgres@127.0.0.1:55432/aiavc_m1",
    )
    environment.update(observed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
    return environment


def validate_environment_manifest(
    bootstrap_path: Path,
    environment_path: Path,
    *,
    project_root: Path | None = None,
    postgresql_dsn: str | None = None,
) -> dict[str, object]:
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    validate_bootstrap(bootstrap)
    environment = json.loads(environment_path.read_text(encoding="utf-8"))

    forbidden_path = _find_forbidden_key(environment)
    if forbidden_path is not None:
        raise ValueError(f"forbidden sensitive key at {forbidden_path}")
    if environment.get("source_bootstrap_sha256") != sha256_file(bootstrap_path):
        raise ValueError("bootstrap hash mismatch")
    if environment.get("schema_version") != "1.0":
        raise ValueError("environment schema version mismatch")
    if environment.get("record_kind") != "captured_environment":
        raise ValueError("environment record kind mismatch")

    live_project_root = project_root or Path.cwd()
    if environment.get("project", {}).get("uv_lock_sha256") != sha256_file(
        live_project_root / "uv.lock"
    ):
        raise ValueError("uv.lock live hash mismatch")
    observed = _observe_environment(
        bootstrap,
        live_project_root,
        postgresql_dsn or "postgresql://postgres@127.0.0.1:55432/aiavc_m1",
    )
    for section in CAPTURED_SECTIONS:
        if environment.get(section) != observed.get(section):
            raise ValueError(f"{section} live observation mismatch")
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bootstrap", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    capture_environment(arguments.bootstrap, arguments.output)


if __name__ == "__main__":
    main()
