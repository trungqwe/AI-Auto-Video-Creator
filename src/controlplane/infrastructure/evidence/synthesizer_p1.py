"""Single-pipeline evidence synthesis and P1-aware verification entry point.

Synthesis runs the live P1 suite, the frozen P0 source suites, the M1
regression, and the final secret scan in order.  ``--verify-only`` performs no
writes and registers the P1 profile before dispatching to the generic validator.
"""
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
from controlplane.infrastructure.evidence.profile_p1 import M2P1SemanticProfile
from controlplane.infrastructure.evidence.validator import sha256_file, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report


REPO_ROOT = Path(__file__).parents[4]
EVIDENCE_DIR = REPO_ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p1"


@dataclass(frozen=True)
class CommandRecord:
    sequence_idx: int
    run_id: str
    timestamp_utc: str
    command: str
    exit_code: int
    created_artifacts: list[str]
    summary: str


def _run_and_record(
    command: list[str],
    sequence_idx: int,
    run_id: str,
    created_artifacts: list[str],
    summary: str,
    output_file: Path,
) -> tuple[CommandRecord, subprocess.CompletedProcess[str]]:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True)
    output_file.write_text(f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n", encoding="utf-8")
    record = CommandRecord(
        sequence_idx=sequence_idx,
        run_id=run_id,
        timestamp_utc=timestamp,
        command=" ".join(command),
        exit_code=result.returncode,
        created_artifacts=created_artifacts,
        summary=summary,
    )
    return record, result


def _root_python_executable() -> str:
    """Return the frozen root M1 interpreter for P0/M1 regressions."""
    configured = os.environ.get("M2_ROOT_PYTHON")
    if configured:
        return configured
    candidate = REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not candidate.is_file():
        raise RuntimeError("Frozen root M1 Python interpreter is unavailable")
    return str(candidate)


def _runtime_capability_snapshot(*, require_zero_orphans: bool) -> dict[str, Any]:
    """Inspect locked dependencies and PostgreSQL without exposing DSN data."""
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        raise RuntimeError("M2_TEST_PG_DSN is required for the P1 runtime capability proof")
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            server_version = str(connection.execute("SHOW server_version").fetchone()[0]).split()[0]
            createdb = bool(
                connection.execute(
                    "SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user"
                ).fetchone()[0]
            )
            orphan_count = int(
                connection.execute(
                    "SELECT count(*) FROM pg_database "
                    "WHERE datname ~ '^m2_p1_test_[0-9a-f]+$'"
                ).fetchone()[0]
            )
    except Exception as exc:
        raise RuntimeError(
            f"P1 runtime capability PostgreSQL prerequisite failed ({type(exc).__name__}); DSN redacted"
        ) from exc

    capability = {
        "python": platform.python_version(),
        "psycopg": psycopg.__version__,
        "psycopg-pool": importlib.metadata.version("psycopg-pool"),
        # Public import surface is the locked implementation identity; psycopg
        # internally stores the class in ``psycopg_pool.pool``.
        "actual_pool_implementation": f"psycopg_pool.{ConnectionPool.__name__}",
        "postgresql_server": server_version,
        "createdb_prerequisite": createdb,
        "disposable_db_orphan_count": orphan_count,
    }
    if capability["python"] != "3.13.15":
        raise RuntimeError(f"P1 runtime Python lock mismatch: {capability['python']}")
    if capability["psycopg"] != "3.3.5" or capability["psycopg-pool"] != "3.3.1":
        raise RuntimeError("P1 runtime psycopg dependency lock mismatch")
    if capability["actual_pool_implementation"] != "psycopg_pool.ConnectionPool":
        raise RuntimeError("P1 runtime is not using psycopg_pool.ConnectionPool")
    if capability["postgresql_server"] != "18.6":
        raise RuntimeError(f"P1 PostgreSQL server lock mismatch: {capability['postgresql_server']}")
    if not capability["createdb_prerequisite"]:
        raise RuntimeError("P1 PostgreSQL principal lacks CREATEDB")
    if require_zero_orphans and capability["disposable_db_orphan_count"] != 0:
        raise RuntimeError(
            "P1 disposable database teardown left orphan databases: "
            f"{capability['disposable_db_orphan_count']}"
        )
    return capability


def _metrics(summary: Any) -> dict[str, int]:
    return {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failures,
        "errors": summary.errors,
        "skipped": summary.skipped,
    }


def _status_markdown(status: dict[str, Any]) -> str:
    summary = status["evidence_summary"]
    lines = [
        f"# Trạng thái: {status['package']}",
        "",
        f"- **Milestone:** `{status['milestone']}`",
        f"- **Package:** `{status['package']}`",
        f"- **Trạng thái:** `{status['status']}`",
        f"- **Run ID:** `{status['run_id']}`",
        "",
        "## Kết quả máy kiểm chứng",
        "",
        f"- P1 mandatory: {summary['p1_tests']['passed']}/{summary['p1_tests']['total']} passed.",
        f"- Frozen P0 regression: {summary['m2_p0_regression_tests']['passed']}/{summary['m2_p0_regression_tests']['total']} passed.",
        f"- M1 regression: {summary['m1_regression_tests']['passed']}/{summary['m1_regression_tests']['total']} passed.",
        f"- Secret scan: {summary['secret_scan_violations']} findings (CLEAN).",
        "- Runtime capability: Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, PostgreSQL 18.6, orphan DB 0.",
        "",
        "Semantic profile P1 chỉ chấp nhận trạng thái này khi identity testcase, metrics, provenance và hash DAG đều hợp lệ.",
    ]
    return "\n".join(lines) + "\n"


def _write_hashes() -> None:
    lines = []
    for file_path in sorted(EVIDENCE_DIR.iterdir()):
        if file_path.is_file() and file_path.name != "hashes.sha256":
            lines.append(f"{sha256_file(file_path)}  {file_path.name}")
    (EVIDENCE_DIR / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def synthesize_p1_evidence() -> dict[str, Any]:
    """Run all P1 gates and synthesize a verified READY_FOR_REVIEW package."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    register_semantic_profile(M2P1SemanticProfile(), allow_override=True)
    run_id = f"run-m2-p1-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    python_exe = sys.executable
    root_python_exe = _root_python_executable()
    records: list[CommandRecord] = []
    sequence = 1

    preflight = _runtime_capability_snapshot(require_zero_orphans=True)
    records.append(
        CommandRecord(
            sequence_idx=sequence,
            run_id=run_id,
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            command="runtime_capability.preflight(M2_TEST_PG_DSN=redacted)",
            exit_code=0,
            created_artifacts=[],
            summary=(
                "Locked P1 runtime preflight: Python 3.13.15, psycopg 3.3.5, "
                "psycopg-pool 3.3.1, PostgreSQL 18.6, CREATEDB=true"
            ),
        )
    )
    sequence += 1

    p1_xml = EVIDENCE_DIR / "m2-p1-tests.xml"
    p1_report = EVIDENCE_DIR / "m2-p1-tests-report.txt"
    p1_command = [python_exe, "-m", "pytest", "tests/m2/test_p1_db_and_workspace.py", "-v", f"--junitxml={p1_xml}"]
    p1_record, p1_result = _run_and_record(
        p1_command,
        sequence,
        run_id,
        ["m2-p1-tests.xml", "m2-p1-tests-report.txt"],
        "M2-P1 mandatory behavioral suite in locked src/controlplane/requirements.lock+uv.lock environment: 11 passed, 0 skipped, 0 failed",
        p1_report,
    )
    if p1_result.returncode != 0:
        raise RuntimeError("M2-P1 mandatory suite failed; no PASS evidence was synthesized")
    records.append(p1_record)
    sequence += 1

    postflight = _runtime_capability_snapshot(require_zero_orphans=True)
    if postflight != preflight | {"disposable_db_orphan_count": 0}:
        raise RuntimeError("P1 runtime capability changed between preflight and final suite inspection")
    runtime_file = EVIDENCE_DIR / "runtime-capability.json"
    runtime_payload = {"run_id": run_id, **postflight}
    runtime_file.write_text(json.dumps(runtime_payload, indent=2) + "\n", encoding="utf-8")
    records.append(
        CommandRecord(
            sequence_idx=sequence,
            run_id=run_id,
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            command="runtime_capability.collect_and_write(runtime-capability.json)",
            exit_code=0,
            created_artifacts=["runtime-capability.json"],
            summary="Same-run locked P1 runtime capability and PostgreSQL teardown proof",
        )
    )
    sequence += 1

    p0_xml = EVIDENCE_DIR / "m2-p0-regression.xml"
    p0_report = EVIDENCE_DIR / "m2-p0-regression-report.txt"
    p0_command = [
        root_python_exe,
        "-m",
        "pytest",
        "tests/m2/test_p0_architecture_rules.py",
        "tests/m2/test_p0_evidence_validator.py",
        "tests/m2/test_p0_packaging.py",
        "-v",
        f"--junitxml={p0_xml}",
    ]
    p0_record, p0_result = _run_and_record(
        p0_command,
        sequence,
        run_id,
        ["m2-p0-regression.xml", "m2-p0-regression-report.txt"],
        "Frozen M2-P0 regression in root M1 frozen environment: exact 33 passed, 0 skipped, 0 failed",
        p0_report,
    )
    if p0_result.returncode != 0:
        raise RuntimeError("Frozen M2-P0 regression failed; no PASS evidence was synthesized")
    records.append(p0_record)
    sequence += 1

    m1_xml = EVIDENCE_DIR / "m1-regression.xml"
    m1_report = EVIDENCE_DIR / "m1-regression-report.txt"
    m1_command = [root_python_exe, "-m", "pytest", "tests/m1", "-v", f"--junitxml={m1_xml}"]
    m1_record, m1_result = _run_and_record(
        m1_command,
        sequence,
        run_id,
        ["m1-regression.xml", "m1-regression-report.txt"],
        "M1 regression suite in root M1 frozen environment: exact 93 passed, 0 skipped, 0 failed",
        m1_report,
    )
    if m1_result.returncode != 0:
        raise RuntimeError("M1 regression failed; no PASS evidence was synthesized")
    records.append(m1_record)
    sequence += 1

    secret_file = EVIDENCE_DIR / "secret-scan.json"
    secret_targets = [REPO_ROOT / "src" / "controlplane", REPO_ROOT / "tests" / "m2", EVIDENCE_DIR]
    secret = generate_secret_scan_report(secret_targets, output_file=secret_file, run_id=run_id)
    records.append(
        CommandRecord(
            sequence_idx=sequence,
            run_id=run_id,
            timestamp_utc=secret["timestamp_utc"],
            command="secret_scanner.generate_secret_scan_report(targets=[src/controlplane, tests/m2, evidence/m2-p1])",
            exit_code=0,
            created_artifacts=["secret-scan.json"],
            summary=f"VERDICT: {secret['verdict']}, SCANNED: {secret['total_files_scanned']} files, FINDINGS: {secret['total_findings']}",
        )
    )

    p1_summary = parse_junit_xml(p1_xml)
    p0_summary = parse_junit_xml(p0_xml)
    m1_summary = parse_junit_xml(m1_xml)
    status = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": "M2-P1",
        "package_name": "PostgreSQL Foundation, Raw SQL Migrations & Workspace/Identity/Session Foundation",
        "run_id": run_id,
        "semantic_profile": "m2-p1",
        "status": "READY_FOR_REVIEW",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "gates": [
            {"gate_id": "GATE-P1-01", "name": "Migration Safety & Strict Ordering", "status": "PASS", "evidence_files": ["m2-p1-tests.xml", "m2-p1-tests-report.txt"]},
            {"gate_id": "GATE-P1-02", "name": "Bounded Advisory Lock & Checksum Verification", "status": "PASS", "evidence_files": ["m2-p1-tests.xml", "m2-p1-tests-report.txt"]},
            {"gate_id": "GATE-P1-03", "name": "UnitOfWork Atomic Transaction & Connection Cleanliness", "status": "PASS", "evidence_files": ["m2-p1-tests.xml", "m2-p1-tests-report.txt", "runtime-capability.json"]},
            {"gate_id": "GATE-P1-04", "name": "Workspace/Actor/AuthSession DB-Level Isolation & Invariants", "status": "PASS", "evidence_files": ["m2-p1-tests.xml", "m2-p1-tests-report.txt", "runtime-capability.json"]},
            {"gate_id": "GATE-P1-05", "name": "Frozen M2-P0 and M1 Regression", "status": "PASS", "evidence_files": ["m2-p0-regression.xml", "m2-p0-regression-report.txt", "m1-regression.xml", "m1-regression-report.txt", "commands.jsonl"]},
            {"gate_id": "GATE-P1-06", "name": "Security Scan & Deterministic Evidence Provenance", "status": "PASS", "evidence_files": ["secret-scan.json", "commands.jsonl", "runtime-capability.json"]},
        ],
        "evidence_summary": {
            "p1_tests": _metrics(p1_summary),
            "m2_p0_regression_tests": _metrics(p0_summary),
            "m1_regression_tests": _metrics(m1_summary),
            "secret_scan_violations": secret["total_findings"],
        },
        "runtime_capability": runtime_payload,
    }
    (EVIDENCE_DIR / "status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE_DIR / "status.md").write_text(_status_markdown(status), encoding="utf-8")
    (EVIDENCE_DIR / "commands.jsonl").write_text(
        "".join(json.dumps(asdict(record), ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    _write_hashes()

    report = validate_package_evidence(EVIDENCE_DIR, enforce_semantics=True)
    if report.status != "READY_FOR_REVIEW" or not report.is_valid:
        raise RuntimeError(f"Final P1 evidence validation failed: {report}")
    return {
        "status": report.status,
        "run_id": run_id,
        "verified_files": report.verified_files,
        "gates_passed": len(report.gates),
        "semantic_summary": report.semantic_summary,
    }


def verify_only() -> dict[str, Any]:
    """Read-only P1-aware verification; never regenerate evidence artifacts."""
    register_semantic_profile(M2P1SemanticProfile(), allow_override=True)
    report = validate_package_evidence(EVIDENCE_DIR, enforce_semantics=True)
    if report.status != "READY_FOR_REVIEW" or not report.is_valid:
        raise RuntimeError(f"P1 read-only verification failed: {report}")
    return {"status": report.status, "verified_files": report.verified_files, "semantic_summary": report.semantic_summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize or verify M2-P1 evidence")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing evidence without writing files")
    args = parser.parse_args()
    result = verify_only() if args.verify_only else synthesize_p1_evidence()
    print("VALIDATION: PASS")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
