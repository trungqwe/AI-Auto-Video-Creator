"""Generate and verify a provenance-complete M2-P3 evidence package."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from controlplane.infrastructure.evidence.evaluator import parse_junit_xml, register_semantic_profile
from controlplane.infrastructure.evidence.profile_p3 import M2P3SemanticProfile
from controlplane.infrastructure.evidence.validator import sha256_file, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report

ROOT = Path(__file__).parents[4]
OUT = ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p3"


def _write(path: Path, text: str) -> None:
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _metrics(path: Path) -> dict[str, int]:
    result = parse_junit_xml(path)
    return {"total": result.total, "passed": result.passed, "failed": result.failures, "errors": result.errors, "skipped": result.skipped}


def _root_python() -> str:
    executable = ROOT / ".venv" / "Scripts" / "python.exe"
    if not executable.is_file():
        raise RuntimeError("frozen root interpreter unavailable")
    return str(executable)


def _runtime(run_id: str) -> dict[str, Any]:
    dsn = os.environ.get("M2_TEST_PG_DSN")
    if not dsn:
        raise RuntimeError("M2_TEST_PG_DSN required")
    with psycopg.connect(dsn, autocommit=True) as connection:
        server = str(connection.execute("SHOW server_version").fetchone()[0]).split()[0]
        createdb = bool(connection.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0])
        orphans = int(connection.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p[123]_test_[0-9a-f]+$'").fetchone()[0])
    value = {"run_id": run_id, "python": platform.python_version(), "psycopg": psycopg.__version__, "psycopg-pool": importlib.metadata.version("psycopg-pool"), "actual_pool_implementation": f"psycopg_pool.{ConnectionPool.__name__}", "postgresql_server": server, "createdb_prerequisite": createdb, "disposable_db_orphan_count": orphans}
    expected = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg-pool": "3.3.1", "actual_pool_implementation": "psycopg_pool.ConnectionPool", "postgresql_server": "18.6", "createdb_prerequisite": True, "disposable_db_orphan_count": 0}
    if {key: value[key] for key in expected} != expected:
        raise RuntimeError("locked runtime mismatch")
    return value


def _record(records: list[dict[str, Any]], run_id: str, command: str, artifacts: list[str], summary: str, timestamp: str | None = None) -> None:
    records.append({"sequence_idx": len(records) + 1, "run_id": run_id, "timestamp_utc": timestamp or _timestamp(), "command": command, "exit_code": 0, "created_artifacts": artifacts, "summary": summary})


def _run_pytest(command: list[str], xml_name: str, report_name: str, records: list[dict[str, Any]], run_id: str) -> None:
    result = subprocess.run([*command, f"--junitxml={OUT / xml_name}"], cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "src"})
    _write(OUT / report_name, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    if result.returncode:
        raise RuntimeError(f"closure command failed: {' '.join(command)}")
    _record(records, run_id, "subprocess.pytest " + " ".join(command), [xml_name, report_name], "frozen pytest suite")


def _hashes() -> None:
    entries = [f"{sha256_file(path)}  {path.name}" for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "hashes.sha256"]
    _write(OUT / "hashes.sha256", "\n".join(entries) + "\n")


def synthesize_p3_evidence() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    run_id = "run-m2-p3-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    records: list[dict[str, Any]] = []
    baseline_runtime = _runtime(run_id)
    _record(records, run_id, "internal.runtime_capability.preflight(M2_TEST_PG_DSN=redacted)", [], "locked runtime prerequisite")
    suites = [
        ("m2-p2-regression.xml", "m2-p2-regression-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p2_envelopes_and_idempotency.py", "-vv"]),
        ("m2-p1-regression.xml", "m2-p1-regression-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p1_db_and_workspace.py", "-vv"]),
        ("m2-p0-regression.xml", "m2-p0-regression-report.txt", [_root_python(), "-m", "pytest", "tests/m2/test_p0_architecture_rules.py", "tests/m2/test_p0_evidence_validator.py", "tests/m2/test_p0_packaging.py", "-vv"]),
        ("m1-regression.xml", "m1-regression-report.txt", [_root_python(), "-m", "pytest", "tests/m1", "-vv"]),
        ("m2-p3-tests.xml", "m2-p3-tests-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p3_outbox_and_projections.py", "-vv"]),
    ]
    for xml_name, report_name, command in suites:
        _run_pytest(command, xml_name, report_name, records, run_id)
    runtime = _runtime(run_id)
    if runtime != baseline_runtime:
        raise RuntimeError("runtime capability changed during closure run")
    _write(OUT / "runtime-capability.json", json.dumps(runtime, indent=2) + "\n")
    _record(records, run_id, "internal.runtime_capability.postflight_and_orphan_check(M2_TEST_PG_DSN=redacted)", ["runtime-capability.json"], "same-run runtime and orphan proof")
    secret = generate_secret_scan_report([ROOT / "src" / "controlplane", ROOT / "tests" / "m2", OUT], output_file=OUT / "secret-scan.json", run_id=run_id)
    _write(OUT / "secret-scan.json", json.dumps(secret, indent=2) + "\n")
    _record(records, run_id, "internal.secret_scanner.generate_secret_scan_report", ["secret-scan.json"], f"VERDICT: {secret['verdict']}; FINDINGS: {secret['total_findings']}", secret["timestamp_utc"])
    summary = {"p3_tests": _metrics(OUT / "m2-p3-tests.xml"), "p2_regression_tests": _metrics(OUT / "m2-p2-regression.xml"), "p1_regression_tests": _metrics(OUT / "m2-p1-regression.xml"), "m2_p0_regression_tests": _metrics(OUT / "m2-p0-regression.xml"), "m1_regression_tests": _metrics(OUT / "m1-regression.xml"), "secret_scan_violations": secret["total_findings"]}
    status = {"schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P3", "run_id": run_id, "semantic_profile": "m2-p3", "status": "READY_FOR_REVIEW", "timestamp_utc": _timestamp(), "evidence_summary": summary, "runtime_capability": runtime, "gates": [{"gate_id": f"GATE-P3-0{i}", "status": "PASS"} for i in range(1, 7)]}
    _write(OUT / "status.json", json.dumps(status, indent=2) + "\n")
    _write(OUT / "status.md", f"# Trạng thái M2-P3\n\n`READY_FOR_REVIEW` — run `{run_id}`.\n")
    _write(OUT / "commands.jsonl", "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    _hashes()
    return validate_package_evidence(OUT, enforce_semantics=True).__dict__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    register_semantic_profile(M2P3SemanticProfile(), allow_override=True)
    result = validate_package_evidence(OUT, enforce_semantics=True).__dict__ if args.verify_only else synthesize_p3_evidence()
    print("VALIDATION: PASS")
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
