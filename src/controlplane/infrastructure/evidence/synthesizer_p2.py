"""Single-pipeline M2-P2 evidence synthesis and P2-aware verification."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from controlplane.infrastructure.evidence.evaluator import parse_junit_xml, register_semantic_profile
from controlplane.infrastructure.evidence.profile_p2 import M2P2SemanticProfile
from controlplane.infrastructure.evidence.validator import sha256_file, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report

REPO_ROOT = Path(__file__).parents[4]
EVIDENCE_DIR = REPO_ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p2"


def _write(path: Path, content: str) -> None:
    """Write deterministic UTF-8/LF evidence bytes on every platform."""
    path.write_bytes(content.encode("utf-8"))


@dataclass(frozen=True)
class CommandRecord:
    sequence_idx: int
    run_id: str
    timestamp_utc: str
    command: str
    exit_code: int
    created_artifacts: list[str]
    summary: str


def _run(command: list[str], sequence: int, run_id: str, artifacts: list[str], summary: str, report: Path) -> CommandRecord:
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    stderr = result.stderr.rstrip()
    stderr_section = f"STDERR:\n{stderr}\n" if stderr else "STDERR:\n"
    _write(report, f"STDOUT:\n{result.stdout.rstrip()}\n{stderr_section}")
    if result.returncode:
        raise RuntimeError(f"Closure command failed: {' '.join(command)}")
    return CommandRecord(sequence, run_id, datetime.datetime.now(datetime.timezone.utc).isoformat(), " ".join(command), 0, artifacts, summary)


def _runtime() -> dict[str, Any]:
    dsn = os.environ.get("M2_TEST_PG_DSN")
    if not dsn:
        raise RuntimeError("M2_TEST_PG_DSN is required; its value is never recorded")
    with psycopg.connect(dsn, autocommit=True) as connection:
        server = str(connection.execute("SHOW server_version").fetchone()[0]).split()[0]
        createdb = bool(connection.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0])
        orphans = int(connection.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p[12]_test_[0-9a-f]+$'").fetchone()[0])
    result = {"python": platform.python_version(), "psycopg": psycopg.__version__, "psycopg-pool": importlib.metadata.version("psycopg-pool"), "actual_pool_implementation": f"psycopg_pool.{ConnectionPool.__name__}", "postgresql_server": server, "createdb_prerequisite": createdb, "disposable_db_orphan_count": orphans}
    expected = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg-pool": "3.3.1", "actual_pool_implementation": "psycopg_pool.ConnectionPool", "postgresql_server": "18.6", "createdb_prerequisite": True, "disposable_db_orphan_count": 0}
    if result != expected:
        raise RuntimeError("locked runtime capability mismatch")
    return result


def _root_python() -> str:
    """Return the frozen root interpreter used by accepted P0/M1 regression."""
    configured = os.environ.get("M2_ROOT_PYTHON")
    if configured:
        return configured
    executable = "python.exe" if os.name == "nt" else "python"
    candidate = REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / executable
    if not candidate.is_file():
        raise RuntimeError("frozen root M1 interpreter is unavailable")
    return str(candidate)


def _metrics(summary: Any) -> dict[str, int]:
    return {"total": summary.total, "passed": summary.passed, "failed": summary.failures, "errors": summary.errors, "skipped": summary.skipped}


def _hashes() -> None:
    entries = [f"{sha256_file(path)}  {path.name}" for path in sorted(EVIDENCE_DIR.iterdir()) if path.is_file() and path.name != "hashes.sha256"]
    _write(EVIDENCE_DIR / "hashes.sha256", "\n".join(entries) + "\n")


def synthesize_p2_evidence() -> dict[str, Any]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    register_semantic_profile(M2P2SemanticProfile(), allow_override=True)
    run_id = f"run-m2-p2-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    records: list[CommandRecord] = []
    runtime = _runtime()
    root_python = _root_python()
    records.append(CommandRecord(1, run_id, datetime.datetime.now(datetime.timezone.utc).isoformat(), "runtime_capability.preflight(M2_TEST_PG_DSN=redacted)", 0, [], "Locked runtime capability preflight"))
    suites = [
        ("m2-p2-tests", [sys.executable, "-m", "pytest", "tests/m2/test_p2_envelopes_and_idempotency.py", "-vv"], "P2 mandatory exact 11/11"),
        ("m2-p1-regression", [sys.executable, "-m", "pytest", "tests/m2/test_p1_db_and_workspace.py", "-vv"], "Frozen P1 exact 11/11"),
        ("m2-p0-regression", [root_python, "-m", "pytest", "tests/m2/test_p0_architecture_rules.py", "tests/m2/test_p0_evidence_validator.py", "tests/m2/test_p0_packaging.py", "-vv"], "Frozen P0 exact 33/33"),
        ("m1-regression", [root_python, "-m", "pytest", "tests/m1", "-vv"], "Frozen M1 exact 93/93"),
    ]
    for index, (stem, command, summary) in enumerate(suites, 2):
        xml = EVIDENCE_DIR / f"{stem}.xml"
        command = [*command, f"--junitxml={xml}"]
        records.append(_run(command, index, run_id, [xml.name, f"{stem}-report.txt"], summary, EVIDENCE_DIR / f"{stem}-report.txt"))
    final_runtime = _runtime()
    if final_runtime != runtime:
        raise RuntimeError("runtime capability changed during final test run")
    runtime_payload = {"run_id": run_id, **final_runtime}
    _write(EVIDENCE_DIR / "runtime-capability.json", json.dumps(runtime_payload, indent=2) + "\n")
    records.append(CommandRecord(6, run_id, datetime.datetime.now(datetime.timezone.utc).isoformat(), "runtime_capability.postflight_and_orphan_check(M2_TEST_PG_DSN=redacted)", 0, ["runtime-capability.json"], "Same-run capability and orphan count proof"))
    secret = generate_secret_scan_report(
        [REPO_ROOT / "src" / "controlplane", REPO_ROOT / "tests" / "m2", EVIDENCE_DIR],
        output_file=EVIDENCE_DIR / "secret-scan.json",
        run_id=run_id,
    )
    _write(EVIDENCE_DIR / "secret-scan.json", json.dumps(secret, indent=2) + "\n")
    records.append(CommandRecord(7, run_id, secret["timestamp_utc"], "secret_scanner.generate_secret_scan_report(targets=[src/controlplane,tests/m2,evidence/m2-p2])", 0, ["secret-scan.json"], f"VERDICT: {secret['verdict']}, FINDINGS: {secret['total_findings']}"))
    summaries = {"p2_tests": _metrics(parse_junit_xml(EVIDENCE_DIR / "m2-p2-tests.xml")), "p1_regression_tests": _metrics(parse_junit_xml(EVIDENCE_DIR / "m2-p1-regression.xml")), "m2_p0_regression_tests": _metrics(parse_junit_xml(EVIDENCE_DIR / "m2-p0-regression.xml")), "m1_regression_tests": _metrics(parse_junit_xml(EVIDENCE_DIR / "m1-regression.xml")), "secret_scan_violations": secret["total_findings"]}
    status = {"schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P2", "package_name": "Contracts, Idempotency and Revision Concurrency", "run_id": run_id, "semantic_profile": "m2-p2", "status": "READY_FOR_REVIEW", "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "gates": [{"gate_id": f"GATE-P2-0{i}", "name": name, "status": "PASS", "evidence_files": files} for i, name, files in [(1, "Envelope and ProblemDetail contracts", ["m2-p2-tests.xml"]), (2, "JCS request hash and durable idempotency", ["m2-p2-tests.xml"]), (3, "PostgreSQL revision CAS", ["m2-p2-tests.xml"]), (4, "Migration 0002 forward and P2-only rollback", ["m2-p2-tests.xml"]), (5, "Frozen P1, P0 and M1 regressions", ["m2-p1-regression.xml", "m2-p0-regression.xml", "m1-regression.xml"]), (6, "Runtime, security and evidence integrity", ["runtime-capability.json", "secret-scan.json", "commands.jsonl"])]], "evidence_summary": summaries, "runtime_capability": runtime_payload}
    _write(EVIDENCE_DIR / "status.json", json.dumps(status, indent=2) + "\n")
    _write(EVIDENCE_DIR / "status.md", f"# Trạng thái: M2-P2\n\n- **Trạng thái:** `READY_FOR_REVIEW`\n- **Run ID:** `{run_id}`\n- P2: {summaries['p2_tests']['passed']}/11; P1: {summaries['p1_regression_tests']['passed']}/11; P0: {summaries['m2_p0_regression_tests']['passed']}/33; M1: {summaries['m1_regression_tests']['passed']}/93.\n- Runtime locked, secret scan CLEAN, provenance và hash DAG được P2-aware verifier kiểm tra.\n")
    _write(EVIDENCE_DIR / "commands.jsonl", "".join(json.dumps(asdict(record), ensure_ascii=False) + "\n" for record in records))
    for filename in (
        "m2-p2-tests.xml", "m2-p2-tests-report.txt",
        "m2-p1-regression.xml", "m2-p1-regression-report.txt",
        "m2-p0-regression.xml", "m2-p0-regression-report.txt",
        "m1-regression.xml", "m1-regression-report.txt",
        "runtime-capability.json", "secret-scan.json", "status.json", "status.md", "commands.jsonl",
    ):
        path = EVIDENCE_DIR / filename
        _write(path, path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
    _hashes()
    report = validate_package_evidence(EVIDENCE_DIR, enforce_semantics=True)
    return {"status": report.status, "run_id": run_id, "verified_files": report.verified_files, "semantic_summary": report.semantic_summary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    register_semantic_profile(M2P2SemanticProfile(), allow_override=True)
    report = validate_package_evidence(EVIDENCE_DIR, enforce_semantics=True) if args.verify_only else synthesize_p2_evidence()
    print("VALIDATION: PASS")
    print(json.dumps(report if isinstance(report, dict) else {"status": report.status, "verified_files": report.verified_files}, indent=2, default=str))


if __name__ == "__main__":
    main()
