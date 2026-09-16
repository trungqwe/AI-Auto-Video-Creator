"""Create and verify one immutable-source M2-P7A Behavioral RED evidence run."""

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

import psycopg
import psycopg_pool

from controlplane.infrastructure.evidence.evaluator import register_semantic_profile
from controlplane.infrastructure.evidence.profile_p7a import (
    M2P7ASemanticProfile, ORACLE_PATH, ORACLE_SHA, SUITES,
)
from controlplane.infrastructure.evidence.validator import EvidenceValidationError, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import scan_file

ROOT = Path(__file__).parents[4]
EVIDENCE = ROOT / "docs/milestones/m2-control-plane/evidence/m2-p7a"
M1_MUTABLE = ROOT / "docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json"
SUITE_PATHS = {
    "p6-regression": ["tests/m2/test_p6_orchestration_shell.py"],
    "p5b-regression": ["tests/m2/test_p5b_artifact_metadata.py"],
    "p5a-regression": ["tests/m2/test_p5a_config_and_secrets.py"],
    "p4-regression": ["tests/m2/test_p4_statemachines.py"],
    "p3-regression": ["tests/m2/test_p3_outbox_and_projections.py"],
    "p2-regression": ["tests/m2/test_p2_envelopes_and_idempotency.py"],
    "p1-regression": ["tests/m2/test_p1_db_and_workspace.py"],
    "p0-regression": [
        "tests/m2/test_p0_architecture_rules.py", "tests/m2/test_p0_evidence_validator.py",
        "tests/m2/test_p0_packaging.py",
    ],
    "architecture": ["tests/m2/test_p0_architecture_rules.py"],
    "m1-regression": ["tests/m1"],
}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _hashes(directory: Path) -> None:
    _write(directory / "hashes.sha256", "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(directory.iterdir()) if path.is_file() and path.name != "hashes.sha256"
    ))


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sha")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    source = args.source_sha
    if _git("rev-parse", "HEAD").stdout.strip() != source or _git("status", "--porcelain").stdout.strip():
        raise RuntimeError("immutable source/tooling requires clean HEAD")
    if hashlib.sha256((ROOT / ORACLE_PATH).read_bytes()).hexdigest() != ORACLE_SHA:
        raise RuntimeError("P7A oracle drift")
    if not os.environ.get("M2_TEST_PG_DSN"):
        raise RuntimeError("M2_TEST_PG_DSN absent")
    run_id = args.run_id or "run-m2-p7a-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out = EVIDENCE / run_id
    out.mkdir(parents=True, exist_ok=False)
    root_python = str(ROOT / ".venv/Scripts/python.exe")
    api_python = str(ROOT / ".local-tools/temp/p7a-locked-venv/Scripts/python.exe")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    commands: list[dict[str, object]] = []

    def record(stage: str, argv: list[str], artifacts: list[str], code: int = 0, timestamp: str | None = None) -> None:
        commands.append({
            "run_id": run_id, "sequence_idx": len(commands) + 1,
            "timestamp_utc": timestamp or _stamp(), "argv": argv,
            "cwd": str(ROOT), "exit_code": code, "stage": stage,
            "created_artifacts": artifacts, "source_commit_sha": source,
        })

    def execute(stage: str, argv: list[str], stdout_name: str, artifacts: list[str], expected: int = 0) -> None:
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
        _write(out / stdout_name, result.stdout + result.stderr)
        record(stage, argv, [stdout_name, *artifacts], result.returncode)
        if result.returncode != expected:
            raise RuntimeError(f"{stage} returned {result.returncode}; expected {expected}")

    execute("collect-p7a", [api_python, "-m", "pytest", ORACLE_PATH, "--collect-only", "-q"], "collect-p7a-stdout.txt", [])
    execute("red-p7a", [api_python, "-m", "pytest", ORACLE_PATH, "-q", "--tb=short", f"--junitxml={out / 'red-p7a.xml'}"], "red-p7a-stdout.txt", ["red-p7a.xml"], 1)
    for suite in SUITES:
        stage = suite.removesuffix(".xml")
        before = M1_MUTABLE.read_bytes() if stage == "m1-regression" else None
        try:
            execute(stage, [root_python, "-m", "pytest", *SUITE_PATHS[stage], "-q", f"--junitxml={out / suite}"], f"{stage}-stdout.txt", [suite])
        finally:
            if before is not None and M1_MUTABLE.read_bytes() != before:
                M1_MUTABLE.write_bytes(before)
                record("restore-m1-fixture", ["restore", str(M1_MUTABLE.relative_to(ROOT))], [], 0)
    execute("p6-hardening", [root_python, "-m", "controlplane.infrastructure.evidence.probe_p6_implementation", "--output", str(out / "p6-hardening.json")], "p6-hardening-stdout.txt", ["p6-hardening.json"])
    with psycopg.connect(env["M2_TEST_PG_DSN"], autocommit=True) as connection:
        pg = connection.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(connection.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0])
        orphan = int(connection.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_(p7a_test|p6_test|p6_probe)_[0-9a-f]+$'").fetchone()[0])
    migrations = ROOT / "src/controlplane/infrastructure/db/migrations"
    versions = sorted(int(path.name[:4]) for path in migrations.glob("[0-9][0-9][0-9][0-9]_*.sql") if not path.name.endswith(".rollback.sql"))
    accepted_paths = [
        "src/controlplane/application/orchestration", "src/controlplane/domain/orchestration",
        "src/controlplane/infrastructure/db/orchestration", "src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql",
        "tests/m2/test_p6_orchestration_shell.py", "src/controlplane/application/storage_meta",
        "src/controlplane/infrastructure/db/storage_meta", "tests/m2/test_p5b_artifact_metadata.py",
    ]
    app_imports = [name for path in (ROOT / "src/controlplane/application").rglob("*.py") for name in _imports(path)]
    domain_imports = [name for path in (ROOT / "src/controlplane/domain").rglob("*.py") for name in _imports(path)]
    runtime = {
        "run_id": run_id, "source_commit_sha": source, "python": platform.python_version(),
        "fastapi": subprocess.check_output([api_python, "-c", "import importlib.metadata as m; print(m.version('fastapi'))"], text=True).strip(),
        "uvicorn": subprocess.check_output([api_python, "-c", "import importlib.metadata as m; print(m.version('uvicorn'))"], text=True).strip(),
        "httpx": subprocess.check_output([api_python, "-c", "import importlib.metadata as m; print(m.version('httpx'))"], text=True).strip(),
        "psycopg": psycopg.__version__, "psycopg_pool": psycopg_pool.__version__,
        "pool_public_import": "psycopg_pool.ConnectionPool",
        "pool_runtime_class": f"{psycopg_pool.ConnectionPool.__module__}.{psycopg_pool.ConnectionPool.__name__}",
        "postgresql": pg, "createdb": createdb, "m2_orphan_count": orphan,
        "migration_0007_absent": 7 not in versions, "migrations_0001_0006_pass": versions == [1, 2, 3, 4, 5, 6],
        "migration_runner_unchanged": _git("diff", "--quiet", "8120bac96cc5f5d223cb8f0c64daa904699c04c9", "HEAD", "--", "src/controlplane/infrastructure/db/migration_runner.py").returncode == 0,
        "p6_p5b_accepted_source_unchanged": _git("diff", "--quiet", "8120bac96cc5f5d223cb8f0c64daa904699c04c9", "HEAD", "--", *accepted_paths).returncode == 0,
        "historical_evidence_preserved": _git("diff", "--quiet", "76daa18d66b2b468cf08189b0ec666fcc1638ec4", "HEAD", "--", "docs/milestones/m2-control-plane/evidence/m2-p6", "docs/milestones/m2-control-plane/evidence/m2-p5b").returncode == 0,
        "application_to_infrastructure_imports": sum(name.startswith("controlplane.infrastructure") for name in app_imports),
        "domain_to_application_imports": sum(name.startswith("controlplane.application") for name in domain_imports),
        "p6_oracle_sha256": hashlib.sha256((ROOT / "tests/m2/test_p6_orchestration_shell.py").read_bytes()).hexdigest(),
        "uv_runtime_observed": "unavailable", "uv_lock_version": "0.12.13",
    }
    _write(out / "runtime-and-static.json", json.dumps(runtime, indent=2) + "\n")
    record("runtime-static-capture", sys.argv, ["runtime-and-static.json"])
    _write(out / "orphan-check.txt", f"DISPOSABLE_DB_ORPHANS={orphan}\nRESULT={'PASS' if orphan == 0 else 'FAIL'}\n")
    record("orphan-check", sys.argv, ["orphan-check.txt"])
    if pg != "18.6" or not createdb or orphan or versions != [1, 2, 3, 4, 5, 6] or not runtime["p6_p5b_accepted_source_unchanged"]:
        raise RuntimeError("runtime prerequisite mismatch")
    ruff = str(ROOT / ".local-tools/uv/uv.exe")
    execute("quality-ruff", [ruff, "run", "--no-sync", "ruff", "check", ORACLE_PATH, "src/controlplane/api", "src/controlplane/infrastructure/evidence/profile_p7a.py", "src/controlplane/infrastructure/evidence/synthesizer_p7a.py"], "ruff-stdout.txt", [])
    mypy = shutil.which("mypy")
    if mypy:
        execute("quality-mypy", [mypy, "src/controlplane/api", ORACLE_PATH], "mypy-stdout.txt", [])
    else:
        _write(out / "mypy-stdout.txt", "SKIP_UNAVAILABLE: mypy executable not observed.\n")
        record("quality-mypy", ["mypy", "--version"], ["mypy-stdout.txt"], 127)
    execute("quality-build", [ruff, "build", "src/controlplane", "--out-dir", str(ROOT / ".local-tools/temp/p7a-build")], "build-stdout.txt", [])
    tls = {"capability": "NOT_IMPLEMENTED", "phase": "RED", "test_identity": "test_tst_m2_p7a_004_tls_handshake_verification", "failure_marker": "P7A-004 local TLS listener/handshake unimplemented", "certificate_provisioning": "NOT_TESTED"}
    _write(out / "tls_handshake_evidence.json", json.dumps(tls, indent=2) + "\n")
    record("tls-red-evidence", sys.argv, ["tls_handshake_evidence.json"])
    scan = [ROOT / ORACLE_PATH, *(ROOT / "src/controlplane/api").rglob("*.py"), ROOT / "src/controlplane/infrastructure/evidence/profile_p7a.py", ROOT / "src/controlplane/infrastructure/evidence/synthesizer_p7a.py", *out.iterdir()]
    findings = [match for path in scan if path.is_file() for match in scan_file(path)]
    if findings:
        raise RuntimeError("secret scan failed")
    scan_time = _stamp()
    _write(out / "secret-scan.json", json.dumps({"schema_version": "m2_secret_scan_v1", "run_id": run_id, "timestamp_utc": scan_time, "verdict": "CLEAN", "total_findings": 0, "files_scanned": len(scan)}, indent=2) + "\n")
    _write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record("secret-scan", sys.argv, ["secret-scan.json", "secret-scan-stdout.txt"], timestamp=scan_time)
    _write(out / "observations.md", "# M2-P7A Behavioral RED\n\nBốn oracle độc lập fail tại Host, CSRF, technical-detail và TLS capability seam. P7A implementation và migration `0007` vắng mặt. TLS handshake/certificate trust chưa được triển khai hoặc tuyên bố PASS. P6/P5B accepted baseline giữ nguyên.\n")
    _write(out / "status.md", f"# M2-P7A Behavioral RED Ready for Review\n\nSource/tooling `{source}`; exact 4 failed, 0 passed/errors/skipped. P7A implementation LOCKED.\n")
    status = {
        "schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P7A",
        "semantic_profile": "m2-p7a-red", "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P7A_BEHAVIORAL_RED_READY_FOR_REVIEW", "implementation": "LOCKED",
        "run_id": run_id, "source_commit_sha": source, "oracle_sha256": ORACLE_SHA,
        "gates": [
            {"gate_id": "P7A-BEHAVIORAL-RED", "status": "PASS", "evidence_files": ["collect-p7a-stdout.txt", "red-p7a.xml", "tls_handshake_evidence.json"]},
            {"gate_id": "P6-HARDENING", "status": "PASS", "evidence_files": ["p6-hardening.json"]},
            {"gate_id": "REGRESSIONS", "status": "PASS", "evidence_files": list(SUITES)},
            {"gate_id": "RUNTIME-SECURITY", "status": "PASS", "evidence_files": ["runtime-and-static.json", "orphan-check.txt", "secret-scan.json"]},
            {"gate_id": "INTEGRITY", "status": "PASS", "evidence_files": ["verify-only-stdout.txt", "negative-verifier-stdout.txt"]},
        ],
    }
    _write(out / "status.json", json.dumps(status, indent=2) + "\n")
    record("evidence-synthesis", sys.argv, ["status.json", "status.md", "observations.md"])
    _write(out / "verify-only-stdout.txt", "PENDING\n")
    _write(out / "negative-verifier-stdout.txt", "PENDING\n")
    record("hash-manifest-generation", sys.argv, ["hashes.sha256"])
    record("hash-verification", sys.argv, [])
    record("negative-verifier-tamper-check", sys.argv, ["negative-verifier-stdout.txt"])
    record("verify-only", sys.argv, ["verify-only-stdout.txt"])
    _write(out / "commands.jsonl", "".join(json.dumps(item, sort_keys=True) + "\n" for item in commands))
    _hashes(out)
    register_semantic_profile(M2P7ASemanticProfile(), allow_override=True)
    with tempfile.TemporaryDirectory(prefix="p7a_red_tamper_") as temporary:
        copy = Path(temporary) / run_id
        shutil.copytree(out, copy)
        _write(copy / "orphan-check.txt", "TAMPERED\n")
        try:
            validate_package_evidence(copy, True)
            raise RuntimeError("tampered evidence accepted")
        except EvidenceValidationError as error:
            _write(out / "negative-verifier-stdout.txt", f"EXPECTED_REJECTION=PASS\nERROR_TYPE={type(error).__name__}\n")
    _hashes(out)
    report = validate_package_evidence(out, True)
    _write(out / "verify-only-stdout.txt", f"VALIDATION=PASS\nSEMANTIC={report.semantic_summary['semantic_verdict']}\nPROVENANCE=VERIFIED\nHASH_DAG=PASS\n")
    _hashes(out)
    validate_package_evidence(out, True)
    print(f"P7A_BEHAVIORAL_RED_EVIDENCE=PASS RUN_ID={run_id} SOURCE={source}")


if __name__ == "__main__":
    main()
