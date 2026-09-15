"""Generate and fail-closed verify the M2-P4 closure evidence package."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from controlplane.infrastructure.evidence.evaluator import parse_junit_xml, register_semantic_profile
from controlplane.infrastructure.evidence.profile_p4 import BEHAVIORAL_SOURCE_SHA, M2P4SemanticProfile
from controlplane.infrastructure.evidence.validator import sha256_file, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report


ROOT = Path(__file__).parents[4]
OUT = ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p4"


def _write(path: Path, content: str) -> None:
    path.write_bytes(content.replace("\r\n", "\n").encode("utf-8"))


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
        raise RuntimeError("M2_TEST_PG_DSN required; no credential fallback is permitted")
    with psycopg.connect(dsn, autocommit=True) as connection:
        server = str(connection.execute("SHOW server_version").fetchone()[0]).split()[0]
        createdb = bool(connection.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()[0])
        orphans = int(connection.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p[123]_test_[0-9a-f]+$'").fetchone()[0])
    result = {"run_id": run_id, "python": platform.python_version(), "psycopg": psycopg.__version__, "psycopg-pool": importlib.metadata.version("psycopg-pool"), "actual_pool_implementation": f"psycopg_pool.{ConnectionPool.__name__}", "postgresql_server": server, "createdb_prerequisite": createdb, "disposable_db_orphan_count": orphans}
    expected = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg-pool": "3.3.1", "actual_pool_implementation": "psycopg_pool.ConnectionPool", "postgresql_server": "18.6", "createdb_prerequisite": True, "disposable_db_orphan_count": 0}
    if {key: result[key] for key in expected} != expected:
        raise RuntimeError("locked runtime mismatch")
    return result


def _preflight(run_id: str) -> dict[str, Any]:
    """Prove the injected DSN can create and remove an isolated disposable database."""
    runtime = _runtime(run_id)
    dsn = os.environ["M2_TEST_PG_DSN"]
    probe_name = f"m2_p4_probe_{uuid.uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{probe_name}"')
        try:
            with psycopg.connect(dsn, dbname=probe_name) as probe:
                probe.execute("SELECT 1").fetchone()
        finally:
            connection.execute(f'DROP DATABASE "{probe_name}"')
    return runtime


def _domain_dependency_proof() -> str:
    domain = ROOT / "src" / "controlplane" / "domain"
    imports = [path for path in domain.rglob("*.py") if "controlplane.application" in path.read_text(encoding="utf-8")]
    if imports:
        raise RuntimeError("domain-to-application dependency detected")
    from controlplane.application.concurrency import RevisionConflictError as application_error
    from controlplane.domain.concurrency import RevisionConflictError as domain_error
    if application_error is not domain_error:
        raise RuntimeError("RevisionConflictError compatibility identity mismatch")
    return "DOMAIN_APPLICATION_IMPORTS=0\nREVISION_CONFLICT_ERROR_IDENTITY=PASS\n"


def _record(records: list[dict[str, Any]], run_id: str, command: str, artifacts: list[str], summary: str, timestamp: str | None = None) -> None:
    records.append({"sequence_idx": len(records) + 1, "run_id": run_id, "timestamp_utc": timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat(), "command": command, "exit_code": 0, "created_artifacts": artifacts, "summary": summary})


def _run_pytest(command: list[str], xml_name: str, report_name: str, records: list[dict[str, Any]], run_id: str) -> None:
    result = subprocess.run([*command, f"--junitxml={OUT / xml_name}"], cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "src"})
    _write(OUT / report_name, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    if result.returncode:
        raise RuntimeError(f"closure command failed: {' '.join(command)}")
    _record(records, run_id, "subprocess.pytest " + " ".join(command), [xml_name, report_name], "frozen pytest suite")


def _hashes(directory: Path = OUT) -> None:
    entries = [f"{sha256_file(path)}  {path.name}" for path in sorted(directory.iterdir()) if path.is_file() and path.name != "hashes.sha256"]
    _write(directory / "hashes.sha256", "\n".join(entries) + "\n")


def _expect_rejected(directory: Path, label: str) -> str:
    try:
        validate_package_evidence(directory, enforce_semantics=True)
    except Exception as exc:
        return f"- {label}: REJECTED ({type(exc).__name__})"
    raise RuntimeError(f"negative verifier sanity unexpectedly accepted: {label}")


def _negative_sanity() -> str:
    results: list[str] = ["# Negative verifier sanity", ""]
    with tempfile.TemporaryDirectory(prefix="m2_p4_verifier_") as temporary:
        sandbox = Path(temporary) / "m2-p4"
        shutil.copytree(OUT, sandbox)
        (sandbox / "m2-p4-tests-report.txt").unlink()
        results.append(_expect_rejected(sandbox, "missing P4 raw report"))

        shutil.rmtree(sandbox)
        shutil.copytree(OUT, sandbox)
        xml = sandbox / "m2-p4-tests.xml"
        _write(xml, xml.read_text(encoding="utf-8").replace('tests="9"', 'tests="8"', 1))
        _hashes(sandbox)
        results.append(_expect_rejected(sandbox, "mutated P4 JUnit counts"))

        shutil.rmtree(sandbox)
        shutil.copytree(OUT, sandbox)
        status = json.loads((sandbox / "status.json").read_text(encoding="utf-8"))
        status["source_commit_sha"] = "0" * 40
        _write(sandbox / "status.json", json.dumps(status, indent=2) + "\n")
        _hashes(sandbox)
        results.append(_expect_rejected(sandbox, "wrong source commit SHA"))

        shutil.rmtree(sandbox)
        shutil.copytree(OUT, sandbox)
        status = json.loads((sandbox / "status.json").read_text(encoding="utf-8"))
        status["m1_compatibility_evidence_sha"] = "0" * 40
        _write(sandbox / "status.json", json.dumps(status, indent=2) + "\n")
        _hashes(sandbox)
        results.append(_expect_rejected(sandbox, "wrong M1 compatibility evidence SHA"))

        shutil.rmtree(sandbox)
        shutil.copytree(OUT, sandbox)
        secret = json.loads((sandbox / "secret-scan.json").read_text(encoding="utf-8"))
        secret["run_id"] = "mismatched-run"
        secret["verdict"] = "VIOLATIONS_DETECTED"
        _write(sandbox / "secret-scan.json", json.dumps(secret, indent=2) + "\n")
        _hashes(sandbox)
        results.append(_expect_rejected(sandbox, "secret dirty and mismatched run"))

        shutil.rmtree(sandbox)
        shutil.copytree(OUT, sandbox)
        report = sandbox / "m2-p4-tests-report.txt"
        report.write_bytes(report.read_bytes() + b"x")
        results.append(_expect_rejected(sandbox, "hash mutation"))
    return "\n".join(results) + "\n"


def synthesize_p4_evidence() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    run_id = "run-m2-p4-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    source_sha = BEHAVIORAL_SOURCE_SHA
    compatibility_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.run(["git", "merge-base", "--is-ancestor", source_sha, compatibility_sha], cwd=ROOT).returncode:
        raise RuntimeError("M1 compatibility evidence does not descend from the behavioral source checkpoint")
    records: list[dict[str, Any]] = []
    _write(OUT / "source-commit.json", json.dumps({"source_commit_sha": source_sha}, indent=2) + "\n")
    _write(OUT / "m1-compatibility.json", json.dumps({"m1_compatibility_evidence_sha": compatibility_sha}, indent=2) + "\n")
    _record(records, run_id, "git rev-parse HEAD and merge-base source checkpoint", ["source-commit.json", "m1-compatibility.json"], "immutable P4 source and M1 compatibility checkpoints")
    baseline_runtime = _preflight(run_id)
    _write(OUT / "source-preflight.txt", f"SOURCE_COMMIT_SHA={source_sha}\nDSN_REDACTED=true\nPG_CREATE_DROP_PROBE=PASS\n")
    _record(records, run_id, "internal.postgresql_preflight_create_drop_probe(M2_TEST_PG_DSN=redacted)", ["source-preflight.txt"], "locked runtime prerequisite and disposable create/drop proof")
    suites = [
        ("m2-p4-tests.xml", "m2-p4-tests-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p4_statemachines.py", "-vv"]),
        ("m2-p3-regression.xml", "m2-p3-regression-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p3_outbox_and_projections.py", "-vv"]),
        ("m2-p2-regression.xml", "m2-p2-regression-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p2_envelopes_and_idempotency.py", "-vv"]),
        ("m2-p1-regression.xml", "m2-p1-regression-report.txt", [sys.executable, "-m", "pytest", "tests/m2/test_p1_db_and_workspace.py", "-vv"]),
        ("m2-p0-regression.xml", "m2-p0-regression-report.txt", [_root_python(), "-m", "pytest", "tests/m2/test_p0_architecture_rules.py", "tests/m2/test_p0_evidence_validator.py", "tests/m2/test_p0_packaging.py", "-vv"]),
        ("architecture-tests.xml", "architecture-tests-report.txt", [_root_python(), "-m", "pytest", "tests/m2/test_p0_architecture_rules.py", "-vv"]),
        ("m1-regression.xml", "m1-regression-report.txt", [_root_python(), "-m", "pytest", "tests/m1", "-vv"]),
    ]
    for xml, report, command in suites:
        _run_pytest(command, xml, report, records, run_id)
    runtime = _runtime(run_id)
    if runtime != baseline_runtime:
        raise RuntimeError("runtime capability changed during closure run")
    _write(OUT / "runtime-capability.json", json.dumps(runtime, indent=2) + "\n")
    _record(records, run_id, "internal.runtime_capability.postflight_and_orphan_check(M2_TEST_PG_DSN=redacted)", ["runtime-capability.json"], "same-run runtime and orphan proof")
    _write(OUT / "domain-application-scan.txt", _domain_dependency_proof())
    _record(records, run_id, "internal.domain_dependency_direction_scan", ["domain-application-scan.txt"], "domain imports and RevisionConflictError identity")
    _write(OUT / "orphan-check.txt", f"DISPOSABLE_DB_ORPHANS={runtime['disposable_db_orphan_count']}\n")
    _record(records, run_id, "internal.disposable_database_orphan_check(M2_TEST_PG_DSN=redacted)", ["orphan-check.txt"], "accepted disposable database patterns")
    secret = generate_secret_scan_report([ROOT / "src" / "controlplane", ROOT / "tests" / "m2", OUT], output_file=OUT / "secret-scan.json", run_id=run_id)
    _write(OUT / "secret-scan.json", json.dumps(secret, indent=2) + "\n")
    _record(records, run_id, "internal.secret_scanner.generate_secret_scan_report", ["secret-scan.json"], f"VERDICT: {secret['verdict']}; FINDINGS: {secret['total_findings']}", secret["timestamp_utc"])
    summary = {"p4_tests": _metrics(OUT / "m2-p4-tests.xml"), "p3_regression_tests": _metrics(OUT / "m2-p3-regression.xml"), "p2_regression_tests": _metrics(OUT / "m2-p2-regression.xml"), "p1_regression_tests": _metrics(OUT / "m2-p1-regression.xml"), "m2_p0_regression_tests": _metrics(OUT / "m2-p0-regression.xml"), "architecture_tests": _metrics(OUT / "architecture-tests.xml"), "m1_regression_tests": _metrics(OUT / "m1-regression.xml"), "secret_scan_violations": secret["total_findings"]}
    status = {"schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P4", "run_id": run_id, "semantic_profile": "m2-p4", "source_commit_sha": source_sha, "m1_compatibility_evidence_sha": compatibility_sha, "status": "READY_FOR_REVIEW", "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "evidence_summary": summary, "runtime_capability": runtime, "gates": [{"gate_id": f"GATE-P4-0{i}", "status": "PASS"} for i in range(1, 7)]}
    _write(OUT / "status.json", json.dumps(status, indent=2) + "\n")
    _write(OUT / "status.md", f"# Trạng thái M2-P4\n\n`READY_FOR_REVIEW` — run `{run_id}`, source `{source_sha}`, M1 compatibility `{compatibility_sha}`.\n")
    _write(OUT / "commands.jsonl", "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    _hashes()
    _write(OUT / "negative-verifier-sanity.md", _negative_sanity())
    _record(records, run_id, "internal.negative_verifier_sanity(temp-copy)", ["negative-verifier-sanity.md"], "all required negative mutations rejected")
    _write(OUT / "commands.jsonl", "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    _hashes()
    return validate_package_evidence(OUT, enforce_semantics=True).__dict__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    register_semantic_profile(M2P4SemanticProfile(), allow_override=True)
    result = validate_package_evidence(OUT, enforce_semantics=True).__dict__ if args.verify_only else synthesize_p4_evidence()
    print("VALIDATION: PASS")
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
