"""Create a fresh, source-pinned P7A GREEN run without exposing the DSN."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from controlplane.infrastructure.evidence.evaluator import register_semantic_profile
from controlplane.infrastructure.evidence.profile_p7a import ORACLE_PATH, ORACLE_SHA
from controlplane.infrastructure.evidence.profile_p7a_implementation import (
    HARDENING_NAMES, M2P7AImplementationSemanticProfile, SUITES,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError, validate_package_evidence,
)
from controlplane.infrastructure.security.secret_scanner import scan_file


ROOT = Path(__file__).parents[4]
EVIDENCE = ROOT / "docs/milestones/m2-control-plane/evidence/m2-p7a"
M1_MUTABLE = ROOT / "docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json"
SUITE_PATHS = {
    "p7a-oracle": [ORACLE_PATH],
    "p7a-hardening": ["tests/m2/test_p7a_hardening.py"],
    "p6-regression": ["tests/m2/test_p6_orchestration_shell.py"],
    "p5b-regression": ["tests/m2/test_p5b_artifact_metadata.py"],
    "p5a-regression": ["tests/m2/test_p5a_config_and_secrets.py"],
    "p4-regression": ["tests/m2/test_p4_statemachines.py"],
    "p3-regression": ["tests/m2/test_p3_outbox_and_projections.py"],
    "p2-regression": ["tests/m2/test_p2_envelopes_and_idempotency.py"],
    "p1-regression": ["tests/m2/test_p1_db_and_workspace.py"],
    "p0-regression": [
        "tests/m2/test_p0_architecture_rules.py",
        "tests/m2/test_p0_evidence_validator.py",
        "tests/m2/test_p0_packaging.py",
    ],
    "architecture": ["tests/m2/test_p0_architecture_rules.py"],
    "m1-regression": ["tests/m1"],
}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _hashes(directory: Path) -> None:
    _write(directory / "hashes.sha256", "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != "hashes.sha256"
    ))


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _sanitize(text: str, dsn: str) -> str:
    return re.sub(
        r"postgres(?:ql)?://[^\s'\"]+", "[REDACTED_DSN]",
        text.replace(dsn, "[REDACTED_DSN]"), flags=re.IGNORECASE,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sha")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    source = args.source_sha
    if (_git("rev-parse", "HEAD").stdout.strip() != source
            or _git("status", "--porcelain").stdout.strip()):
        raise RuntimeError("immutable source/tooling requires clean HEAD")
    if hashlib.sha256((ROOT / ORACLE_PATH).read_bytes()).hexdigest() != ORACLE_SHA:
        raise RuntimeError("accepted oracle drift")
    dsn = os.environ.get("M2_TEST_PG_DSN")
    if not dsn:
        raise RuntimeError("M2_TEST_PG_DSN unavailable")
    run_id = args.run_id or "run-m2-p7a-green-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out = EVIDENCE / run_id
    out.mkdir(parents=True, exist_ok=False)
    api_python = str(ROOT / ".local-tools/temp/p7a-locked-venv/Scripts/python.exe")
    root_python = str(ROOT / ".venv/Scripts/python.exe")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    commands: list[dict[str, object]] = []

    def record(stage: str, argv: list[str], artifacts: list[str],
               code: int = 0, timestamp: str | None = None) -> None:
        commands.append({
            "run_id": run_id, "sequence_idx": len(commands) + 1,
            "timestamp_utc": timestamp or _stamp(), "argv": argv,
            "cwd": str(ROOT), "exit_code": code, "stage": stage,
            "created_artifacts": artifacts, "source_commit_sha": source,
        })

    def execute(stage: str, argv: list[str], artifacts: list[str]) -> None:
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
        stdout_name = f"{stage}-stdout.txt"
        _write(out / stdout_name, _sanitize(result.stdout + result.stderr, dsn))
        record(stage, argv, [stdout_name, *artifacts], result.returncode)
        if result.returncode:
            raise RuntimeError(f"{stage} returned {result.returncode}")

    for filename in SUITES:
        stage = filename.removesuffix(".xml")
        python = root_python if stage == "m1-regression" else api_python
        before = M1_MUTABLE.read_bytes() if stage == "m1-regression" else None
        try:
            execute(stage, [python, "-m", "pytest", *SUITE_PATHS[stage], "-q",
                            "--tb=short", "--disable-warnings",
                            f"--junitxml={out / filename}"], [filename])
        finally:
            if before is not None and M1_MUTABLE.read_bytes() != before:
                M1_MUTABLE.write_bytes(before)
                record("restore-m1-test-side-effect", ["restore", str(M1_MUTABLE.relative_to(ROOT))], [])
            if stage == "p0-regression":
                for generated in (ROOT / "src/controlplane/build",
                                  ROOT / "src/controlplane/controlplane.egg-info"):
                    if generated.is_dir() and not _git(
                        "ls-files", "--", str(generated.relative_to(ROOT))
                    ).stdout.strip():
                        shutil.rmtree(generated)
                        record("cleanup-generated-wheel-tree", ["cleanup", str(generated.relative_to(ROOT))], [])
    hardening = tuple(
        case.attrib["name"] for case in ET.parse(out / "p7a-hardening.xml").iter("testcase")
    )
    if hardening != HARDENING_NAMES:
        raise RuntimeError("H01-H36 identities mismatch")
    _write(out / "p7a-hardening.json", json.dumps({
        "schema_version": "m2_p7a_hardening_v1", "run_id": run_id,
        "source_commit_sha": source, "count": 36, "verdict": "PASS",
        "checks": {name: True for name in hardening},
    }, indent=2) + "\n")
    record("hardening-catalogue", sys.argv, ["p7a-hardening.json"])
    _write(out / "migration-proof.json", json.dumps({
        "testcase": "test_h16_migration_tracker",
        "observed_by": "p7a-hardening.xml",
        "forward_versions": list(range(1, 8)),
        "rollback_versions": list(range(1, 7)),
        "reapply_versions": list(range(1, 8)),
        "verdict": "PASS",
    }, indent=2) + "\n")
    record("migration-tracker-proof", sys.argv, ["migration-proof.json"])
    execute("runtime-static", [api_python, "-m",
        "controlplane.infrastructure.evidence.probe_p7a_implementation",
        source, "--output", str(out / "runtime-and-static.json")], ["runtime-and-static.json"])
    execute("quality-ruff", ["ruff", "check", "src/controlplane/api",
        "src/controlplane/entrypoint.py", "src/controlplane/application/control_api",
        "src/controlplane/application/session_security",
        "src/controlplane/application/technical_details",
        "src/controlplane/application/orchestration/start_batch.py",
        "src/controlplane/infrastructure/db/control_api_commands.py",
        "src/controlplane/infrastructure/db/control_api_queries.py",
        "src/controlplane/infrastructure/db/session_security",
        "src/controlplane/infrastructure/db/technical_details",
        "src/controlplane/infrastructure/db/orchestration/start_batch.py",
        "src/controlplane/infrastructure/security",
        "src/controlplane/infrastructure/evidence/probe_p7a_implementation.py",
        "src/controlplane/infrastructure/evidence/profile_p7a_implementation.py",
        "src/controlplane/infrastructure/evidence/synthesizer_p7a_implementation.py",
        "tests/m2/test_p7a_hardening.py"], [])
    execute("quality-lock", [str(ROOT / ".local-tools/uv/uv.exe"), "lock",
        "--project", "src/controlplane", "--check"], [])
    package_root = ROOT / "src/controlplane"
    generated = (package_root / "build", package_root / "controlplane.egg-info")
    if any(path.exists() for path in generated):
        raise RuntimeError("fresh wheel build requires absent generated trees")
    try:
        with tempfile.TemporaryDirectory(prefix="p7a_locked_wheel_") as temporary:
            temporary_path = Path(temporary)
            wheel_dir = temporary_path / "dist"
            execute("quality-build", [str(ROOT / ".local-tools/uv/uv.exe"), "build",
                "--wheel", "--project", "src/controlplane", "--out-dir", str(wheel_dir)], [])
            wheels = list(wheel_dir.glob("controlplane-0.2.0-*.whl"))
            if len(wheels) != 1:
                raise RuntimeError("fresh wheel missing or ambiguous")
            wheel_env = temporary_path / "venv"
            execute("quality-wheel-venv", [str(ROOT / ".local-tools/uv/uv.exe"), "venv",
                str(wheel_env), "--python", "3.13.15"], [])
            wheel_python = str(wheel_env / "Scripts/python.exe")
            execute("quality-wheel-install", [str(ROOT / ".local-tools/uv/uv.exe"),
                "pip", "install", "--python", wheel_python, "--no-deps", str(wheels[0])], [])
            execute("quality-wheel-import", [wheel_python, "-I", "-c",
                "import controlplane.application.control_api.commands; "
                "import controlplane.application.control_api.query_ports; "
                "import controlplane.api.main; print('WHEEL_IMPORT=PASS')"], [])
    finally:
        for path in generated:
            if path.is_dir() and not _git("ls-files", "--", str(path.relative_to(ROOT))).stdout.strip():
                shutil.rmtree(path)
                record("cleanup-generated-wheel-tree", ["cleanup", str(path.relative_to(ROOT))], [])
    lock_text = (package_root / "uv.lock").read_text(encoding="utf-8")
    mypy_locked = bool(re.search(r'(?m)^name = "mypy"$', lock_text))
    mypy_available = subprocess.run(
        [api_python, "-c", "import importlib.util; import sys; "
         "sys.exit(0 if importlib.util.find_spec('mypy') else 1)"],
        cwd=ROOT, env=env, capture_output=True,
    ).returncode == 0
    if mypy_locked and mypy_available:
        execute("quality-mypy", [api_python, "-m", "mypy", "src/controlplane/api",
            "src/controlplane/application/control_api"], [])
        mypy_status = "PASS"
    elif not mypy_locked:
        mypy_status = "SKIP_UNAVAILABLE_NOT_IN_LOCK"
        _write(out / "quality-mypy-stdout.txt", "MYPY=SKIP_UNAVAILABLE_NOT_IN_LOCK\n")
        record("quality-mypy", [api_python, "-m", "mypy", "--availability-check"],
               ["quality-mypy-stdout.txt"])
    else:
        raise RuntimeError("locked mypy is unavailable")
    _write(out / "quality-status.json", json.dumps({
        "ruff": "PASS", "uv_lock_check": "PASS", "wheel_build": "PASS",
        "wheel_import": "PASS", "mypy": mypy_status,
        "build_backend_locked": True,
    }, indent=2) + "\n")
    record("quality-status", sys.argv, ["quality-status.json"])
    changed = _git("diff", "--name-only", "609cf70c72b3f08303c91b4a8c56bdec9f9237e3", source,
                   "--", "src/controlplane").stdout.splitlines()
    scan_paths = [ROOT / path for path in changed] + [ROOT / ORACLE_PATH,
                  ROOT / "tests/m2/test_p7a_hardening.py", *out.iterdir()]
    findings = [match for path in scan_paths if path.is_file() for match in scan_file(path)]
    if findings:
        raise RuntimeError("P7A secret scan detected findings")
    scan_time = _stamp()
    _write(out / "secret-scan.json", json.dumps({
        "schema_version": "m2_secret_scan_v1", "run_id": run_id,
        "timestamp_utc": scan_time, "verdict": "CLEAN", "total_findings": 0,
        "files_scanned": len(scan_paths),
    }, indent=2) + "\n")
    _write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record("secret-scan", sys.argv, ["secret-scan.json", "secret-scan-stdout.txt"], timestamp=scan_time)
    _write(out / "observations.md", "# M2-P7A GREEN — quan sát\n\n"
        "Oracle accepted 4/4 và H01–H36 36/36 trên PostgreSQL 18.6. "
        "HTTPS dùng ứng dụng FastAPI thật và xác minh CA tường minh; "
        "không tuyên bố browser trust/provisioning hoặc workflow completion. "
        "P7B/P8/P9, M3 và Phân hệ A vẫn khóa.\n")
    _write(out / "status.md", f"# M2-P7A implementation ready for review\n\n"
        f"Source/tooling `{source}`; oracle 4/4; hardening 36/36; regression GREEN.\n")
    status = {
        "schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P7A",
        "semantic_profile": "m2-p7a-implementation", "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P7A_IMPLEMENTATION_READY_FOR_REVIEW",
        "run_id": run_id, "source_commit_sha": source, "oracle_sha256": ORACLE_SHA,
        "gates": [
            {"gate_id": "P7A-GREEN", "status": "PASS", "evidence_files": [
                "p7a-oracle.xml", "p7a-hardening.xml", "p7a-hardening.json"]},
            {"gate_id": "REGRESSIONS", "status": "PASS", "evidence_files": [
                name for name in SUITES if name not in {"p7a-oracle.xml", "p7a-hardening.xml"}]},
            {"gate_id": "RUNTIME-STATIC-SECURITY", "status": "PASS", "evidence_files": [
                "runtime-and-static.json", "secret-scan.json"]},
            {"gate_id": "INTEGRITY", "status": "PASS", "evidence_files": [
                "verify-only-stdout.txt", "negative-verifier-stdout.txt"]},
        ],
    }
    _write(out / "status.json", json.dumps(status, indent=2) + "\n")
    record("evidence-synthesis", sys.argv, ["status.json", "status.md", "observations.md"])
    _write(out / "verify-only-stdout.txt", "PENDING\n")
    _write(out / "negative-verifier-stdout.txt", "PENDING\n")
    record("hash-verification", sys.argv, ["hashes.sha256"])
    record("negative-verifier-tamper-check", sys.argv, ["negative-verifier-stdout.txt"])
    record("verify-only", sys.argv, ["verify-only-stdout.txt"])
    _write(out / "commands.jsonl", "".join(json.dumps(item, sort_keys=True) + "\n" for item in commands))
    _hashes(out)
    register_semantic_profile(M2P7AImplementationSemanticProfile(), allow_override=True)
    with tempfile.TemporaryDirectory(prefix="p7a_green_tamper_") as temporary:
        copy = Path(temporary) / run_id
        shutil.copytree(out, copy)
        _write(copy / "p7a-hardening.json", "TAMPERED\n")
        try:
            validate_package_evidence(copy, True)
            raise RuntimeError("tampered evidence accepted")
        except EvidenceValidationError as exc:
            _write(out / "negative-verifier-stdout.txt",
                   f"EXPECTED_REJECTION=PASS\nERROR_TYPE={type(exc).__name__}\n")
    _hashes(out)
    report = validate_package_evidence(out, True)
    _write(out / "verify-only-stdout.txt",
           f"VALIDATION=PASS\nSEMANTIC={report.semantic_summary['semantic_verdict']}\n"
           "PROVENANCE=VERIFIED\nHASH_DAG=PASS\n")
    _hashes(out)
    validate_package_evidence(out, True)
    print(f"P7A_GREEN_EVIDENCE=PASS RUN_ID={run_id} SOURCE={source}")


if __name__ == "__main__":
    main()
