"""Read-only P7A runtime and architecture probe; never emits the DSN."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess

import psycopg
import psycopg_pool

from controlplane.infrastructure.evidence.profile_p7a import ORACLE_PATH, ORACLE_SHA


ROOT = Path(__file__).parents[4]
BASE = "609cf70c72b3f08303c91b4a8c56bdec9f9237e3"
HISTORICAL_CHECKPOINT = "adb56ad8dd46a1d3a58fb989b099b4e868cad94b"
ALLOWED_SOURCE = {
    "src/controlplane/api/security.py", "src/controlplane/api/technical_details.py",
    "src/controlplane/api/tls.py", "src/controlplane/entrypoint.py",
    "src/controlplane/pyproject.toml", "src/controlplane/requirements.lock",
    "src/controlplane/uv.lock",
}
ALLOWED_PREFIXES = (
    "src/controlplane/api/main.py", "src/controlplane/api/routes/",
    "src/controlplane/application/control_api/",
    "src/controlplane/application/orchestration/start_batch.py",
    "src/controlplane/application/session_security/",
    "src/controlplane/application/technical_details/",
    "src/controlplane/infrastructure/db/control_api_",
    "src/controlplane/infrastructure/db/orchestration/start_batch.py",
    "src/controlplane/infrastructure/db/session_security/",
    "src/controlplane/infrastructure/db/technical_details/",
    "src/controlplane/infrastructure/db/migrations/0007_technical_details",
    "src/controlplane/infrastructure/evidence/probe_p7a_implementation.py",
    "src/controlplane/infrastructure/evidence/profile_p7a_implementation.py",
    "src/controlplane/infrastructure/evidence/synthesizer_p7a_implementation.py",
    "src/controlplane/infrastructure/security/loopback_certificate.py",
    "src/controlplane/infrastructure/security/redaction.py",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _sql_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        isinstance(node, ast.Constant) and isinstance(node.value, str)
        and any(verb in node.value.upper() for verb in
                ("SELECT ", "INSERT INTO ", "UPDATE CONTROLPLANE", "DELETE FROM "))
        for node in ast.walk(tree)
    )


def collect(source_sha: str) -> dict[str, object]:
    if not os.environ.get("M2_TEST_PG_DSN"):
        raise RuntimeError("M2_TEST_PG_DSN unavailable")
    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as connection:
        pg = connection.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(connection.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0])
        orphan = int(connection.execute(
            "SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p7a_(test|hardening|smoke)_[0-9a-f]+$'"
        ).fetchone()[0])
    source = ROOT / "src/controlplane"
    app_imports = [name for path in (source / "application").rglob("*.py")
                   for name in _imports(path)]
    domain_imports = [name for path in (source / "domain").rglob("*.py")
                      for name in _imports(path)]
    api_paths = list((source / "api").rglob("*.py"))
    adapter_paths = [
        source / "infrastructure/db/control_api_commands.py",
        source / "infrastructure/db/orchestration/start_batch.py",
        source / "infrastructure/db/technical_details/__init__.py",
        source / "infrastructure/db/session_security/__init__.py",
    ]
    changed = _git("diff", "--name-only", BASE, source_sha, "--", "src/controlplane").stdout.splitlines()
    unexpected = [path for path in changed if path not in ALLOWED_SOURCE
                  and not path.startswith(ALLOWED_PREFIXES)]
    uv = subprocess.check_output([str(ROOT / ".local-tools/uv/uv.exe"), "--version"], text=True).split()[1]
    return {
        "source_commit_sha": source_sha, "python": platform.python_version(),
        "fastapi": metadata.version("fastapi"), "uvicorn": metadata.version("uvicorn"),
        "httpx": metadata.version("httpx"), "cryptography": metadata.version("cryptography"),
        "psycopg": psycopg.__version__, "psycopg_pool": psycopg_pool.__version__,
        "pool_public_import": "psycopg_pool.ConnectionPool",
        "pool_runtime_class": f"{psycopg_pool.ConnectionPool.__module__}.{psycopg_pool.ConnectionPool.__name__}",
        "borrowed_connection_class": "psycopg.Connection",
        "postgresql": pg, "createdb": createdb, "m2_orphan_count": orphan,
        "uv_runtime_observed": uv, "uv_lock_version": "0.12.13",
        "migration_0007_present": (source / "infrastructure/db/migrations/0007_technical_details.sql").is_file(),
        "migration_runner_unchanged": _git("diff", "--quiet", BASE, source_sha, "--",
                                           "src/controlplane/infrastructure/db/migration_runner.py").returncode == 0,
        "accepted_oracle_unchanged": hashlib.sha256((ROOT / ORACLE_PATH).read_bytes()).hexdigest() == ORACLE_SHA,
        "p1_p6_source_unchanged": not unexpected,
        "historical_evidence_preserved": _git(
            "diff", "--quiet", HISTORICAL_CHECKPOINT, source_sha, "--",
            "docs/milestones/m2-control-plane/evidence"
        ).returncode == 0,
        "application_to_infrastructure_imports": sum(
            name.startswith("controlplane.infrastructure") for name in app_imports
        ),
        "domain_to_application_imports": sum(
            name.startswith("controlplane.application") for name in domain_imports
        ),
        "domain_external_imports": sum(
            name.split(".")[0] in {"fastapi", "starlette", "uvicorn", "psycopg", "psycopg_pool", "httpx"}
            for name in domain_imports
        ),
        "api_sql_statements": sum(_sql_count(path) for path in api_paths),
        "api_psycopg_imports": sum(
            name.startswith("psycopg") for path in api_paths for name in _imports(path)
        ),
        "application_command_sql_statements": _sql_count(source / "application/control_api/commands.py"),
        "composite_adapter_transaction_ownership": sum(
            any(token in path.read_text(encoding="utf-8") for token in
                (".commit(", ".rollback(", "ConnectionPool(", "unit_of_work(", "borrow_connection("))
            for path in adapter_paths
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.source_sha)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("P7A_RUNTIME_STATIC=CAPTURED")


if __name__ == "__main__":
    main()
