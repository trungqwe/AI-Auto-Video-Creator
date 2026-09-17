"""Create one immutable-source, fail-closed M2-P7B GREEN evidence run."""

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
import tempfile
import xml.etree.ElementTree as ET

from controlplane.infrastructure.evidence.evaluator import register_semantic_profile
from controlplane.infrastructure.evidence.profile_p7b import (
    M2P7BImplementationSemanticProfile, ORACLE_NAMES, P7A_ORACLE,
    P7A_ORACLE_SHA, P7B_ORACLE, P7B_ORACLE_SHA, SUITES, hardening_names,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError, validate_package_evidence,
)
from controlplane.infrastructure.security.secret_scanner import scan_file


ROOT = Path(__file__).parents[4]
EVIDENCE_ROOT = ROOT / "docs/milestones/m2-control-plane/evidence/m2-p7b"
M1_MUTABLE = ROOT / "docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json"
SUITE_PATHS = {
    "p7b-oracle": [P7B_ORACLE],
    "p7b-hardening": ["tests/m2/test_p7b_hardening.py"],
    "p7a-oracle": [P7A_ORACLE],
    "p7a-hardening": ["tests/m2/test_p7a_hardening.py"],
    "p6-regression": ["tests/m2/test_p6_orchestration_shell.py"],
    "p5b-regression": ["tests/m2/test_p5b_artifact_metadata.py"],
    "p5a-regression": ["tests/m2/test_p5a_config_and_secrets.py"],
    "p4-regression": ["tests/m2/test_p4_statemachines.py"],
    "p3-regression": ["tests/m2/test_p3_outbox_and_projections.py"],
    "p2-regression": ["tests/m2/test_p2_envelopes_and_idempotency.py"],
    "p1-regression": ["tests/m2/test_p1_db_and_workspace.py"],
    "p0-regression": ["tests/m2/test_p0_architecture_rules.py",
                      "tests/m2/test_p0_evidence_validator.py",
                      "tests/m2/test_p0_packaging.py"],
    "architecture": ["tests/m2/test_p0_architecture_rules.py"],
    "m1-regression": ["tests/m1"],
}
PROBE_ARTIFACTS = (
    "runtime-and-static.json", "pre-index-absent-explain.json",
    "pre-index-resume-explain.json", "post-index-absent-explain.json",
    "post-index-resume-explain.json", "index-catalog.json",
    "tracker-forward.json", "tracker-rollback.json", "tracker-reapply.json",
    "rollback-preservation.json",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _json(path: Path, content: object) -> None:
    _write(path, json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def _hashes(directory: Path) -> None:
    _write(directory / "hashes.sha256", "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != "hashes.sha256"
    ))


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def _sanitize(value: str, dsn: str) -> str:
    return re.sub(r"postgres(?:ql)?://[^\s'\"]+", "[REDACTED_DSN]",
                  value.replace(dsn, "[REDACTED_DSN]"), flags=re.IGNORECASE)


def _cases(path: Path) -> tuple[str, ...]:
    return tuple(node.attrib["name"] for node in ET.parse(path).iter("testcase"))


def _move_generated(package: Path, temporary: Path) -> None:
    for name in ("build", "controlplane.egg-info"):
        target = package / name
        if target.exists():
            if not target.is_dir() or _git("ls-files", "--", str(target.relative_to(ROOT))).stdout.strip():
                raise RuntimeError(f"generated tree is not disposable: {name}")
            if not target.resolve().is_relative_to(ROOT.resolve()):
                raise RuntimeError("generated tree outside workspace")
            shutil.move(str(target), str(temporary / name))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sha")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    source = args.source_sha
    if (_git("rev-parse", "HEAD").stdout.strip() != source
            or _git("status", "--porcelain").stdout.strip()):
        raise RuntimeError("fresh GREEN requires clean immutable source/tooling HEAD")
    for path, expected in ((P7A_ORACLE, P7A_ORACLE_SHA), (P7B_ORACLE, P7B_ORACLE_SHA)):
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"accepted oracle drift: {path}")
    dsn = os.environ.get("M2_TEST_PG_DSN")
    if not dsn:
        raise RuntimeError("M2_TEST_PG_DSN unavailable")
    run_id = args.run_id or "run-m2-p7b-green-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out = EVIDENCE_ROOT / run_id
    out.mkdir(parents=True, exist_ok=False)
    api_python = str(ROOT / ".local-tools/temp/p7a-locked-venv/Scripts/python.exe")
    root_python = str(ROOT / ".venv/Scripts/python.exe")
    uv = str(ROOT / ".local-tools/uv/uv.exe")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    records: list[dict[str, object]] = []

    def record(stage: str, artifacts: list[str], *, argv: list[str] | None = None,
               exit_code: int | None = None, reason: str | None = None,
               timestamp: str | None = None) -> None:
        item: dict[str, object] = {
            "run_id": run_id, "sequence_idx": len(records) + 1,
            "timestamp_utc": timestamp or _stamp(), "cwd": str(ROOT),
            "stage": stage, "created_artifacts": artifacts,
            "source_commit_sha": source, "executed": argv is not None,
        }
        if argv is None:
            item["reason"] = reason or "in-process policy/artifact step"
        else:
            item["argv"] = argv
            item["exit_code"] = exit_code
        records.append(item)

    def execute(stage: str, argv: list[str], artifacts: list[str]) -> None:
        result = subprocess.run(argv, cwd=ROOT, env=env, text=True,
                                capture_output=True, check=False)
        stdout = f"{stage}-stdout.txt"
        _write(out / stdout, _sanitize(result.stdout + result.stderr, dsn))
        record(stage, [stdout, *artifacts], argv=argv, exit_code=result.returncode)
        if result.returncode:
            raise RuntimeError(f"{stage} failed with exit code {result.returncode}")

    execute("collect-p7b", [api_python, "-m", "pytest", P7B_ORACLE,
                            "--collect-only", "-q"], [])
    execute("collect-hardening", [api_python, "-m", "pytest",
                                  "tests/m2/test_p7b_hardening.py", "--collect-only", "-q"], [])
    if ("5 tests collected" not in (out / "collect-p7b-stdout.txt").read_text(encoding="utf-8")
            or "38 tests collected" not in (out / "collect-hardening-stdout.txt").read_text(encoding="utf-8")):
        raise RuntimeError("P7B exact collect count mismatch")
    package = ROOT / "src/controlplane"
    with tempfile.TemporaryDirectory(prefix="p7b_generated_") as generated_temp:
        for filename in SUITES:
            stage = filename.removesuffix(".xml")
            runtime = root_python if stage == "m1-regression" else api_python
            original_m1 = M1_MUTABLE.read_bytes() if stage == "m1-regression" else None
            try:
                execute(stage, [runtime, "-m", "pytest", *SUITE_PATHS[stage],
                                "-q", "--tb=short", "--disable-warnings",
                                f"--junitxml={out / filename}"], [filename])
            finally:
                if original_m1 is not None and M1_MUTABLE.read_bytes() != original_m1:
                    M1_MUTABLE.write_bytes(original_m1)
                    record("restore-m1-test-side-effect", [],
                           reason="exact in-memory byte restoration after live M1 test")
                if stage == "p0-regression":
                    _move_generated(package, Path(generated_temp))
        if _cases(out / "p7b-oracle.xml") != ORACLE_NAMES:
            raise RuntimeError("P7B oracle testcase identity mismatch")
        names = hardening_names((ROOT / "tests/m2/test_p7b_hardening.py").read_bytes())
        if _cases(out / "p7b-hardening.xml") != names:
            raise RuntimeError("H01-H38 identity mismatch")
        execute("runtime-static-migration", [api_python, "-m",
            "controlplane.infrastructure.evidence.probe_p7b", source,
            "--output-dir", str(out)], list(PROBE_ARTIFACTS))
        execute("quality-ruff", ["ruff", "check",
            "src/controlplane/api/main.py", "src/controlplane/api/sse",
            "src/controlplane/application/sse", "src/controlplane/infrastructure/db/sse",
            "src/controlplane/infrastructure/db/projections/postgres.py",
            "src/controlplane/infrastructure/evidence/probe_p7b.py",
            "src/controlplane/infrastructure/evidence/profile_p7b.py",
            "src/controlplane/infrastructure/evidence/synthesizer_p7b.py",
            "tests/m2/test_p7a_hardening.py", "tests/m2/test_p7b_hardening.py"], [])
        execute("quality-lock", [uv, "lock", "--project", "src/controlplane", "--check"], [])
        if (package / "build").exists() or (package / "controlplane.egg-info").exists():
            raise RuntimeError("fresh locked wheel build requires absent generated trees")
        try:
            with tempfile.TemporaryDirectory(prefix="p7b_locked_wheel_") as temporary:
                temporary_path = Path(temporary)
                wheel_dir = temporary_path / "dist"
                execute("quality-build", [uv, "build", "--wheel", "--project",
                    "src/controlplane", "--out-dir", str(wheel_dir)], [])
                wheels = list(wheel_dir.glob("controlplane-0.2.0-*.whl"))
                if len(wheels) != 1:
                    raise RuntimeError("fresh wheel missing or ambiguous")
                wheel_env = temporary_path / "venv"
                execute("quality-wheel-venv", [uv, "venv", str(wheel_env),
                    "--python", "3.13.15"], [])
                wheel_python = str(wheel_env / "Scripts/python.exe")
                execute("quality-wheel-locked-deps", [uv, "pip", "install", "--python",
                    wheel_python, "--offline", "--requirement",
                    "src/controlplane/requirements.lock"], [])
                execute("quality-wheel-install", [uv, "pip", "install", "--python",
                    wheel_python, "--no-deps", str(wheels[0])], [])
                execute("quality-wheel-import", [wheel_python, "-I", "-c",
                    "import controlplane.api.main; import controlplane.api.sse.stream; "
                    "import controlplane.application.sse.stream; "
                    "import controlplane.infrastructure.db.sse.postgres; "
                    "print('P7B_WHEEL_IMPORT=PASS')"], [])
        finally:
            _move_generated(package, Path(generated_temp))
    lock = (package / "uv.lock").read_text(encoding="utf-8")
    if re.search(r'(?m)^name = "mypy"$', lock):
        execute("quality-mypy", [api_python, "-m", "mypy",
                                 "src/controlplane/api/sse", "src/controlplane/application/sse"], [])
        mypy_status = "PASS"
    else:
        mypy_status = "SKIP_UNAVAILABLE_NOT_IN_LOCK"
        record("quality-mypy", [], reason="mypy absent from locked toolchain")
    _json(out / "quality-status.json", {
        "ruff": "PASS", "uv_lock_check": "PASS", "wheel_build": "PASS",
        "wheel_import": "PASS", "mypy": mypy_status,
        "build_backend_locked": True,
    })
    record("quality-status", ["quality-status.json"], reason="in-process synthesis")
    _json(out / "hardening-catalogue.json", {
        "count": 38, "identities": names, "verdict": "PASS",
        "source_commit_sha": source,
    })
    record("hardening-catalogue", ["hardening-catalogue.json"], reason="derived from JUnit and committed test AST")
    _write(out / "observations.md", "# M2-P7B GREEN — quan sát\n\n"
        "P7B oracle 5/5, H01–H38 38/38 và các suite hồi quy độc lập đạt trên runtime thật. "
        "Migration 0008 hỗ trợ workspace-scoped bounded SSE read; H16 P7A là ngoại lệ "
        "compatibility được duyệt, không viết lại acceptance lịch sử. "
        "P7B chỉ READY_FOR_REVIEW, chưa accepted/closed; P8/P9, M3/Phân hệ A vẫn khóa.\n")
    _write(out / "status.md", f"# M2-P7B implementation ready for review\n\n"
           f"Source/tooling `{source}`; oracle 5/5; hardening 38/38; regressions GREEN.\n")
    _write(out / "verify-only-stdout.txt", "PENDING\n")
    _write(out / "negative-verifier-stdout.txt", "PENDING\n")
    status = {
        "schema_version": "m2_package_status_v1", "milestone": "M2", "package": "M2-P7B",
        "semantic_profile": "m2-p7b-implementation", "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P7B_IMPLEMENTATION_READY_FOR_REVIEW", "run_id": run_id,
        "source_commit_sha": source, "oracle_sha256": P7B_ORACLE_SHA,
        "gates": [
            {"gate_id": "P7B-GREEN", "status": "PASS", "evidence_files": [
                "p7b-oracle.xml", "p7b-hardening.xml", "hardening-catalogue.json"]},
            {"gate_id": "REGRESSIONS", "status": "PASS", "evidence_files": [
                name for name in SUITES if name not in {"p7b-oracle.xml", "p7b-hardening.xml"}]},
            {"gate_id": "MIGRATION-H18", "status": "PASS", "evidence_files": [
                *PROBE_ARTIFACTS]},
            {"gate_id": "QUALITY-SECURITY", "status": "PASS", "evidence_files": [
                "quality-status.json", "secret-scan.json"]},
            {"gate_id": "INTEGRITY", "status": "PASS", "evidence_files": [
                "verify-only-stdout.txt", "negative-verifier-stdout.txt"]},
        ],
    }
    _json(out / "status.json", status)
    record("evidence-synthesis", ["status.json", "status.md", "observations.md"],
           reason="in-process manifest synthesis")
    record("tamper-negative", ["negative-verifier-stdout.txt"],
           reason="in-process verifier negative test")
    record("verify-only", ["verify-only-stdout.txt"],
           reason="in-process verifier")
    record("hash-verification", ["hashes.sha256"],
           reason="in-process acyclic hash DAG")
    _write(out / "commands.jsonl", "".join(json.dumps(item, sort_keys=True) + "\n"
                                           for item in records))
    changed = _git("diff", "--name-only", "2c0a371fcfe5ea6d1c6e97fa1f7c9983a16c82f8",
                   source, "--", "src/controlplane", "tests/m2").stdout.splitlines()
    scan_paths = [ROOT / relative for relative in changed] + list(out.iterdir())
    findings = [finding for path in scan_paths if path.is_file()
                for finding in scan_file(path)]
    if findings:
        raise RuntimeError("P7B secret scan detected findings")
    scan_time = _stamp()
    _json(out / "secret-scan.json", {
        "schema_version": "m2_secret_scan_v1", "run_id": run_id,
        "timestamp_utc": scan_time, "verdict": "CLEAN",
        "total_findings": 0, "files_scanned": len(scan_paths),
    })
    _write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record("secret-scan", ["secret-scan.json", "secret-scan-stdout.txt"],
           reason="in-process scanner", timestamp=scan_time)
    _write(out / "commands.jsonl", "".join(json.dumps(item, sort_keys=True) + "\n"
                                           for item in records))
    register_semantic_profile(M2P7BImplementationSemanticProfile(), allow_override=True)
    _hashes(out)
    with tempfile.TemporaryDirectory(prefix="p7b_green_tamper_") as temporary:
        copied = Path(temporary) / run_id
        shutil.copytree(out, copied)
        _write(copied / "hardening-catalogue.json", "TAMPERED\n")
        try:
            validate_package_evidence(copied, True)
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
    print(f"P7B_GREEN_EVIDENCE=PASS RUN_ID={run_id} SOURCE={source}")


if __name__ == "__main__":
    main()
