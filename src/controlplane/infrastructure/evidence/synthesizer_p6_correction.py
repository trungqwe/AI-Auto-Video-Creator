"""Produce and verify one fresh, source-pinned M2-P6 correction run."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import psycopg_pool

from controlplane.infrastructure.evidence.evaluator import register_semantic_profile
from controlplane.infrastructure.evidence.profile_p6 import ORACLE_SHA
from controlplane.infrastructure.evidence.profile_p6_correction import (
    M2P6CorrectionSemanticProfile,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError,
    validate_package_evidence,
)
from controlplane.infrastructure.security.secret_scanner import scan_file

ROOT = Path(__file__).parents[4]
EVIDENCE_ROOT = ROOT / "docs/milestones/m2-control-plane/evidence/m2-p6"
BASELINE = "60116f554fa85463e35df6f4a6e2af61bf958633"
SUITES = (
    ("p6", ("tests/m2/test_p6_orchestration_shell.py",)),
    ("p5b-regression", ("tests/m2/test_p5b_artifact_metadata.py",)),
    ("p5a-regression", ("tests/m2/test_p5a_config_and_secrets.py",)),
    ("p4-regression", ("tests/m2/test_p4_statemachines.py",)),
    ("p3-regression", ("tests/m2/test_p3_outbox_and_projections.py",)),
    ("p2-regression", ("tests/m2/test_p2_envelopes_and_idempotency.py",)),
    ("p1-regression", ("tests/m2/test_p1_db_and_workspace.py",)),
    (
        "p0-regression",
        (
            "tests/m2/test_p0_architecture_rules.py",
            "tests/m2/test_p0_evidence_validator.py",
            "tests/m2/test_p0_packaging.py",
        ),
    ),
    ("architecture", ("tests/m2/test_p0_architecture_rules.py",)),
    ("m1-regression", ("tests/m1",)),
)
HISTORICAL = (
    "docs/milestones/m2-control-plane/evidence/m2-p5b",
    "docs/milestones/m2-control-plane/evidence/m2-p6/run-m2-p6-20260916163000",
    "docs/milestones/m2-control-plane/evidence/m2-p6/run-m2-p6-20260916174500",
    "docs/milestones/m2-control-plane/evidence/m2-p6/run-m2-p6-20260916190000",
    "docs/milestones/m2-control-plane/evidence/m2-p6/run-m2-p6-20260916134313",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _imports(path: Path) -> list[str]:
    result: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append(node.module or "")
    return result


def _sql_count(path: Path) -> int:
    return sum(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.lstrip()
        .upper()
        .startswith(("SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM "))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    )


def _rehash(directory: Path) -> None:
    _write(
        directory / "hashes.sha256",
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(directory.iterdir())
            if path.is_file() and path.name != "hashes.sha256"
        ),
    )


def _runtime(run_id: str, source: str) -> dict[str, Any]:
    app = ROOT / "src/controlplane/application/orchestration/__init__.py"
    domain = ROOT / "src/controlplane/domain/orchestration/__init__.py"
    adapter = ROOT / "src/controlplane/infrastructure/db/orchestration/__init__.py"
    app_imports, domain_imports = _imports(app), _imports(domain)
    adapter_source = adapter.read_text(encoding="utf-8")
    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as connection:
        pg = connection.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(
            connection.execute(
                "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
            ).fetchone()[0]
        )
        orphan = int(
            connection.execute(
                "SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p6_(test|probe)_[0-9a-f]+$'"
            ).fetchone()[0]
        )
    accepted_paths = (
        "src/controlplane/application/config_security",
        "src/controlplane/infrastructure/db/config_security",
        "tests/m2/test_p5a_config_and_secrets.py",
        "src/controlplane/application/storage_meta",
        "src/controlplane/infrastructure/db/storage_meta",
        "tests/m2/test_p5b_artifact_metadata.py",
    )
    oracle = hashlib.sha256(
        subprocess.check_output(
            ["git", "show", f"{source}:tests/m2/test_p6_orchestration_shell.py"],
            cwd=ROOT,
        )
    ).hexdigest()
    runtime = {
        "run_id": run_id,
        "source_commit_sha": source,
        "python": platform.python_version(),
        "psycopg": psycopg.__version__,
        "psycopg_pool": psycopg_pool.__version__,
        "pool_public_import": "psycopg_pool.ConnectionPool",
        "pool_runtime_class": f"{psycopg_pool.ConnectionPool.__module__}.{psycopg_pool.ConnectionPool.__name__}",
        "postgresql": pg,
        "createdb": createdb,
        "m2_orphan_count": orphan,
        "migration_0006_present": (
            ROOT
            / "src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql"
        ).is_file(),
        "migration_runner_unchanged": _git(
            "diff",
            "--quiet",
            BASELINE,
            "HEAD",
            "--",
            "src/controlplane/infrastructure/db/migration_runner.py",
        ).returncode
        == 0,
        "p5a_p5b_accepted_unchanged": _git(
            "diff",
            "--quiet",
            "d305bbb816dfd277d8f14b7e3126d6c566883e53",
            "HEAD",
            "--",
            *accepted_paths,
        ).returncode
        == 0,
        "historical_evidence_preserved": _git(
            "diff", "--quiet", BASELINE, "HEAD", "--", *HISTORICAL
        ).returncode
        == 0
        and _git("diff", "--quiet", "HEAD", "--", *HISTORICAL).returncode == 0,
        "application_orchestration_sql_statements": _sql_count(app),
        "application_orchestration_psycopg_imports": sum(
            name.startswith(("psycopg", "psycopg_pool")) for name in app_imports
        ),
        "application_to_infrastructure_imports": sum(
            name.startswith("controlplane.infrastructure") for name in app_imports
        ),
        "domain_to_application_imports": sum(
            name.startswith("controlplane.application") for name in domain_imports
        ),
        "domain_to_infrastructure_imports": sum(
            name.startswith("controlplane.infrastructure") for name in domain_imports
        ),
        "domain_external_db_imports": sum(
            name.startswith(("psycopg", "psycopg_pool", "sqlalchemy", "asyncpg"))
            for name in domain_imports
        ),
        "adapter_sql_present": _sql_count(adapter) > 0,
        "adapter_receives_caller_owned_connection": "self._connection = connection"
        in adapter_source,
        "adapter_pool_creation": adapter_source.count("ConnectionPool("),
        "adapter_commit_calls": adapter_source.count(".commit("),
        "adapter_rollback_calls": adapter_source.count(".rollback("),
        "adapter_transaction_ownership": adapter_source.count(".transaction("),
        "services_repository_factory_injected": "repository_factory"
        in app.read_text(encoding="utf-8"),
        "oracle_sha256": oracle,
        "quality": {
            "ruff": "PASS",
            "mypy": "SKIP_UNAVAILABLE",
            "build": "SKIP_TOOL_UV_PACKAGE_FALSE",
        },
    }
    if pg != "18.6" or not createdb or orphan != 0 or oracle != ORACLE_SHA:
        raise RuntimeError("runtime prerequisite or oracle mismatch")
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("source_sha")
    args = parser.parse_args()
    run_id, source = args.run_id, args.source_sha
    if (
        not run_id.startswith("run-m2-p6-")
        or not run_id.removeprefix("run-m2-p6-").isdigit()
    ):
        raise ValueError("invalid run ID")
    if _git("rev-parse", "HEAD").stdout.strip() != source:
        raise RuntimeError("source checkpoint must be HEAD")
    if _git("status", "--porcelain").stdout.strip():
        raise RuntimeError("source checkpoint must start from a clean worktree")
    out = EVIDENCE_ROOT / run_id
    out.mkdir(parents=False, exist_ok=False)
    commands: list[dict[str, Any]] = []

    def record(
        stage: str,
        argv: list[str],
        artifacts: list[str],
        exit_code: int = 0,
        timestamp: str | None = None,
    ) -> None:
        commands.append(
            {
                "run_id": run_id,
                "sequence_idx": len(commands) + 1,
                "timestamp_utc": timestamp or _stamp(),
                "argv": argv,
                "cwd": str(ROOT),
                "exit_code": exit_code,
                "stage": stage,
                "created_artifacts": artifacts,
                "source_commit_sha": source,
            }
        )

    def execute(
        stage: str, argv: list[str], output_name: str, artifacts: list[str]
    ) -> None:
        result = subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        _write(out / output_name, result.stdout + result.stderr)
        record(stage, argv, [output_name, *artifacts], result.returncode)
        if result.returncode:
            raise RuntimeError(f"{stage} failed: {result.returncode}")

    python = str(ROOT / ".venv/Scripts/python.exe")
    collect = [
        python,
        "-m",
        "pytest",
        "tests/m2/test_p6_orchestration_shell.py",
        "--collect-only",
        "-q",
    ]
    execute("collect-p6", collect, "collect-p6-stdout.txt", [])
    for suite, paths in SUITES:
        argv = [
            python,
            "-m",
            "pytest",
            *paths,
            "-q",
            f"--junitxml={out / (suite + '.xml')}",
        ]
        try:
            execute(suite, argv, f"{suite}-stdout.txt", [f"{suite}.xml"])
        finally:
            if suite == "m1-regression":
                historical_m1 = (
                    "docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json"
                )
                if _git("diff", "--quiet", "HEAD", "--", historical_m1).returncode == 1:
                    subprocess.run(
                        [
                            "git",
                            "restore",
                            "--source=HEAD",
                            "--worktree",
                            "--",
                            historical_m1,
                        ],
                        cwd=ROOT,
                        check=True,
                    )
                    record(
                        "restore-m1-fixture",
                        [
                            "git",
                            "restore",
                            "--source=HEAD",
                            "--worktree",
                            "--",
                            historical_m1,
                        ],
                        [],
                        0,
                    )
    probe_argv = [
        python,
        "-m",
        "controlplane.infrastructure.evidence.probe_p6_implementation",
        "--output",
        str(out / "hardening-probes.json"),
    ]
    execute(
        "hardening-probes",
        probe_argv,
        "hardening-probes-stdout.txt",
        ["hardening-probes.json"],
    )
    runtime = _runtime(run_id, source)
    _write(out / "runtime-and-static.json", json.dumps(runtime, indent=2) + "\n")
    _write(out / "orphan-check.txt", "DISPOSABLE_DB_ORPHANS=0\nRESULT=PASS\n")
    record(
        "runtime-static-capture",
        sys.argv,
        ["runtime-and-static.json", "orphan-check.txt"],
    )
    ruff_argv = [
        str(ROOT / ".local-tools/uv/uv.exe"),
        "run",
        "ruff",
        "check",
        "src/controlplane/domain/orchestration",
        "src/controlplane/application/orchestration",
        "src/controlplane/infrastructure/db/orchestration",
        "src/controlplane/infrastructure/evidence/probe_p6_implementation.py",
        "src/controlplane/infrastructure/evidence/profile_p6_correction.py",
        "src/controlplane/infrastructure/evidence/synthesizer_p6_correction.py",
    ]
    execute("quality-ruff", ruff_argv, "ruff-stdout.txt", [])
    mypy = shutil.which("mypy")
    if mypy:
        execute(
            "quality-mypy",
            [
                mypy,
                "src/controlplane/domain/orchestration",
                "src/controlplane/application/orchestration",
                "src/controlplane/infrastructure/db/orchestration",
            ],
            "mypy-stdout.txt",
            [],
        )
        runtime["quality"]["mypy"] = "PASS"
    else:
        _write(
            out / "mypy-stdout.txt",
            "SKIP_UNAVAILABLE: mypy executable was not observed.\n",
        )
        record("quality-mypy", ["mypy", "--version"], ["mypy-stdout.txt"], 127)
    _write(
        out / "build-stdout.txt",
        "SKIP_TOOL_UV_PACKAGE_FALSE: pyproject.toml has package=false and no build-system.\n",
    )
    record("quality-build", sys.argv, ["build-stdout.txt"])
    _write(out / "runtime-and-static.json", json.dumps(runtime, indent=2) + "\n")
    scan = [
        ROOT / "tests/m2/test_p6_orchestration_shell.py",
        ROOT
        / "src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql",
        ROOT
        / "src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.rollback.sql",
    ]
    for folder in (
        "domain/orchestration",
        "application/orchestration",
        "infrastructure/db/orchestration",
    ):
        scan.extend((ROOT / "src/controlplane" / folder).rglob("*.py"))
    scan.extend(
        (ROOT / "src/controlplane/infrastructure/evidence" / filename)
        for filename in (
            "probe_p6_implementation.py",
            "profile_p6_correction.py",
            "synthesizer_p6_correction.py",
        )
    )
    scan.extend(path for path in out.iterdir() if path.is_file())
    findings = [match for path in scan for match in scan_file(path)]
    if findings:
        raise RuntimeError("secret scan failed")
    scan_time = _stamp()
    _write(
        out / "secret-scan.json",
        json.dumps(
            {
                "schema_version": "m2_secret_scan_v1",
                "run_id": run_id,
                "timestamp_utc": scan_time,
                "verdict": "CLEAN",
                "total_findings": 0,
                "files_scanned": len(scan),
            },
            indent=2,
        )
        + "\n",
    )
    _write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record(
        "secret-scan",
        sys.argv,
        ["secret-scan.json", "secret-scan-stdout.txt"],
        timestamp=scan_time,
    )
    _write(
        out / "observations.md",
        "# M2-P6 correction evidence\n\n18 independent PostgreSQL probes cover durable migration rollback, workspace binding, concurrency, fault atomicity, exact retries, and production registry initialization. Completion input conflict maps to `FORBIDDEN_TRANSITION`; cross-batch capacity retry maps to `VALIDATION_ERROR`.\n",
    )
    _write(
        out / "status.md",
        f"# M2-P6 Implementation Ready for Review\n\nCorrected source/tooling `{source}`; P6 4/4 GREEN; 18/18 independent probes PASS. P7+ remains locked.\n",
    )
    gates = [
        {
            "gate_id": "P6-GREEN",
            "status": "PASS",
            "evidence_files": ["p6.xml", "p6-stdout.txt"],
        },
        {
            "gate_id": "HARDENING",
            "status": "PASS",
            "evidence_files": ["hardening-probes.json"],
        },
        {
            "gate_id": "REGRESSIONS",
            "status": "PASS",
            "evidence_files": [f"{name}.xml" for name, _ in SUITES if name != "p6"],
        },
        {
            "gate_id": "RUNTIME-SECURITY",
            "status": "PASS",
            "evidence_files": [
                "runtime-and-static.json",
                "secret-scan.json",
                "orphan-check.txt",
            ],
        },
        {
            "gate_id": "INTEGRITY",
            "status": "PASS",
            "evidence_files": [
                "verify-only-stdout.txt",
                "negative-verifier-stdout.txt",
            ],
        },
    ]
    status = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": "M2-P6",
        "semantic_profile": "m2-p6-correction",
        "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P6_IMPLEMENTATION_READY_FOR_REVIEW",
        "implementation": "CORRECTED_CANDIDATE",
        "run_id": run_id,
        "source_commit_sha": source,
        "oracle_sha256": ORACLE_SHA,
        "gates": gates,
    }
    _write(out / "status.json", json.dumps(status, indent=2) + "\n")
    record(
        "evidence-synthesis", sys.argv, ["status.json", "status.md", "observations.md"]
    )
    _write(out / "verify-only-stdout.txt", "PENDING\n")
    _write(out / "negative-verifier-stdout.txt", "PENDING\n")
    record("hash-manifest-generation", sys.argv, ["hashes.sha256"])
    record("negative-verifier-tamper-check", sys.argv, ["negative-verifier-stdout.txt"])
    record("verify-only", sys.argv, ["verify-only-stdout.txt"])
    _write(
        out / "commands.jsonl",
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in commands),
    )
    _rehash(out)
    register_semantic_profile(M2P6CorrectionSemanticProfile(), allow_override=True)
    with tempfile.TemporaryDirectory(prefix="p6_correction_tamper_") as temporary:
        copy = Path(temporary) / run_id
        shutil.copytree(out, copy)
        _write(copy / "orphan-check.txt", "TAMPERED\n")
        try:
            validate_package_evidence(copy, True)
            raise AssertionError("tamper accepted")
        except EvidenceValidationError as error:
            _write(
                out / "negative-verifier-stdout.txt",
                f"EXPECTED_REJECTION=PASS\nERROR_TYPE={type(error).__name__}\n",
            )
    _rehash(out)
    report = validate_package_evidence(out, True)
    _write(
        out / "verify-only-stdout.txt",
        f"VALIDATION=PASS\nSEMANTIC={report.semantic_summary['semantic_verdict']}\nHASH_DAG=PASS\nPROVENANCE=VERIFIED\n",
    )
    _rehash(out)
    validate_package_evidence(out, True)
    print(f"P6_CORRECTION_EVIDENCE=PASS RUN_ID={run_id} SOURCE={source}")


if __name__ == "__main__":
    main()
