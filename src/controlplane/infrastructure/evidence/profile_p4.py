"""Fail-closed semantic profile for the M2-P4 closure package."""
from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from controlplane.infrastructure.evidence.evaluator import (
    PackageSemanticProfile,
    SemanticEvaluationError,
    parse_junit_xml,
    verify_package_provenance,
)
from controlplane.infrastructure.evidence.profile_p1 import FROZEN_P0_IDENTITIES, MANDATORY_P1_IDENTITIES
from controlplane.infrastructure.evidence.profile_p2 import MANDATORY_P2_IDENTITIES
from controlplane.infrastructure.evidence.profile_p3 import MANDATORY_P3_IDENTITIES
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file


P4_FILE = "tests/m2/test_p4_statemachines.py"
P4_NAMES = (
    "test_tst_m2_p4_001_valid_lifecycle_transitions",
    "test_tst_m2_p4_002_forbidden_transition_completed_to_running_rejected",
    "test_tst_m2_p4_003_operation_execution_to_projection_mapping",
    "test_tst_m2_p4_004_artifact_cleanup_strict_transition_order",
    "test_tst_m2_p4_005_batch_waiting_resume_and_terminal_transitions",
    "test_tst_m2_p4_006_job_waiting_resume_and_completion_admission",
    "test_tst_m2_p4_007_stage_run_reconcile_and_terminal_transitions",
    "test_tst_m2_p4_008_operation_forbidden_transition_classes_rejected",
    "test_tst_m2_p4_009_stale_expected_revision_rejected_without_mutation",
)
MANDATORY_P4_IDENTITIES = frozenset(f"{P4_FILE}::{name}" for name in P4_NAMES)
_SHA = re.compile(r"^[0-9a-f]{40}$")
BEHAVIORAL_SOURCE_SHA = "3225891dc7328603be38002ff2295c4bf3a50b48"


def _metrics(path: Path) -> dict[str, int]:
    summary = parse_junit_xml(path)
    return {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failures,
        "errors": summary.errors,
        "skipped": summary.skipped,
    }


def _identities(path: Path) -> set[str]:
    result: set[str] = set()
    for case in ET.parse(path).iter("testcase"):
        source = (case.attrib.get("file") or case.attrib.get("classname", "")).replace("\\", "/")
        if "/" not in source:
            source = source.replace(".", "/") + ("" if source.endswith(".py") else ".py")
        result.add(f"{source}::{case.attrib['name']}")
    return result


def _assert_suite(package_dir: Path, name: str, identities: frozenset[str], total: int, status: dict[str, Any], key: str) -> None:
    metrics = _metrics(package_dir / name)
    expected = {"total": total, "passed": total, "failed": 0, "errors": 0, "skipped": 0}
    if metrics != expected or _identities(package_dir / name) != identities:
        raise SemanticEvaluationError(f"{name} is not the frozen clean suite")
    if status.get("evidence_summary", {}).get(key) != metrics:
        raise SemanticEvaluationError(f"status summary mismatch for {name}")


def _assert_clean_report(path: Path) -> None:
    if not path.is_file():
        raise SemanticEvaluationError(f"Execution report missing: {path.name}")
    report = path.read_text(encoding="utf-8", errors="replace")
    if "=== FAILURES ===" in report or ("=== SHORT TEST SUMMARY INFO ===" in report and "FAILED " in report):
        raise SemanticEvaluationError(f"Failed execution report: {path.name}")


class M2P4SemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p4"

    @property
    def target_package(self) -> str:
        return "M2-P4"

    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        if status_data.get("status") != "READY_FOR_REVIEW":
            raise SemanticEvaluationError("P4 evidence status is not review-ready")
        gates = status_data.get("gates", [])
        if {gate.get("gate_id") for gate in gates} != {f"GATE-P4-0{i}" for i in range(1, 7)} or any(gate.get("status") != "PASS" for gate in gates):
            raise SemanticEvaluationError("P4 gates must be exactly GATE-P4-01..06 and PASS")

        source = status_data.get("source_commit_sha")
        source_record = json.loads((package_dir / "source-commit.json").read_text(encoding="utf-8"))
        compatibility = status_data.get("m1_compatibility_evidence_sha")
        compatibility_record = json.loads((package_dir / "m1-compatibility.json").read_text(encoding="utf-8"))
        if source != BEHAVIORAL_SOURCE_SHA or source_record.get("source_commit_sha") != source:
            raise SemanticEvaluationError("source_commit_sha is missing or inconsistent")
        if not isinstance(compatibility, str) or not _SHA.fullmatch(compatibility) or compatibility_record.get("m1_compatibility_evidence_sha") != compatibility:
            raise SemanticEvaluationError("m1 compatibility evidence SHA is missing or inconsistent")
        if "DSN_REDACTED=true" not in (package_dir / "source-preflight.txt").read_text(encoding="utf-8"):
            raise SemanticEvaluationError("source preflight lacks DSN redaction declaration")
        root = Path(__file__).parents[4]
        if subprocess.run(["git", "merge-base", "--is-ancestor", source, compatibility], cwd=root).returncode or subprocess.run(["git", "merge-base", "--is-ancestor", compatibility, "HEAD"], cwd=root).returncode:
            raise SemanticEvaluationError("evidence does not descend from the source and M1 compatibility checkpoints")

        suites = (
            ("m2-p4-tests.xml", MANDATORY_P4_IDENTITIES, 9, "p4_tests"),
            ("m2-p3-regression.xml", MANDATORY_P3_IDENTITIES, 11, "p3_regression_tests"),
            ("m2-p2-regression.xml", MANDATORY_P2_IDENTITIES, 11, "p2_regression_tests"),
            ("m2-p1-regression.xml", MANDATORY_P1_IDENTITIES, 11, "p1_regression_tests"),
            ("m2-p0-regression.xml", FROZEN_P0_IDENTITIES, 33, "m2_p0_regression_tests"),
        )
        for name, identities, total, key in suites:
            _assert_suite(package_dir, name, identities, total, status_data, key)
        architecture = _metrics(package_dir / "architecture-tests.xml")
        if architecture != {"total": 6, "passed": 6, "failed": 0, "errors": 0, "skipped": 0} or status_data["evidence_summary"].get("architecture_tests") != architecture:
            raise SemanticEvaluationError("architecture suite is not exact 6/6")
        if (package_dir / "domain-application-scan.txt").read_text(encoding="utf-8").strip() != "DOMAIN_APPLICATION_IMPORTS=0\nREVISION_CONFLICT_ERROR_IDENTITY=PASS":
            raise SemanticEvaluationError("domain dependency-direction proof failed")
        if (package_dir / "orphan-check.txt").read_text(encoding="utf-8").strip() != "DISPOSABLE_DB_ORPHANS=0":
            raise SemanticEvaluationError("disposable database orphan proof failed")
        m1 = _metrics(package_dir / "m1-regression.xml")
        if m1 != {"total": 93, "passed": 93, "failed": 0, "errors": 0, "skipped": 0} or status_data["evidence_summary"].get("m1_regression_tests") != m1:
            raise SemanticEvaluationError("M1 is not exact 93/93")
        for name in (
            "m2-p4-tests-report.txt", "m2-p3-regression-report.txt", "m2-p2-regression-report.txt",
            "m2-p1-regression-report.txt", "m2-p0-regression-report.txt", "architecture-tests-report.txt",
            "m1-regression-report.txt",
        ):
            _assert_clean_report(package_dir / name)

        runtime = json.loads((package_dir / "runtime-capability.json").read_text(encoding="utf-8"))
        required_runtime = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg-pool": "3.3.1", "actual_pool_implementation": "psycopg_pool.ConnectionPool", "postgresql_server": "18.6", "createdb_prerequisite": True, "disposable_db_orphan_count": 0}
        if runtime.get("run_id") != status_data.get("run_id") or {key: runtime.get(key) for key in required_runtime} != required_runtime:
            raise SemanticEvaluationError("locked runtime capability mismatch")
        secret = json.loads((package_dir / "secret-scan.json").read_text(encoding="utf-8"))
        if secret.get("run_id") != status_data.get("run_id") or secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan is not CLEAN")

        commands = [json.loads(line) for line in (package_dir / "commands.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        required = {"source-commit.json", "m1-compatibility.json", "source-preflight.txt", "m2-p4-tests.xml", "m2-p4-tests-report.txt", "m2-p3-regression.xml", "m2-p3-regression-report.txt", "m2-p2-regression.xml", "m2-p2-regression-report.txt", "m2-p1-regression.xml", "m2-p1-regression-report.txt", "m2-p0-regression.xml", "m2-p0-regression-report.txt", "architecture-tests.xml", "architecture-tests-report.txt", "domain-application-scan.txt", "m1-regression.xml", "m1-regression-report.txt", "runtime-capability.json", "orphan-check.txt", "secret-scan.json", "negative-verifier-sanity.md"}
        produced = {artifact for command in commands for artifact in command.get("created_artifacts", [])}
        if not commands or any(command.get("run_id") != status_data.get("run_id") or command.get("exit_code") != 0 for command in commands) or not required <= produced:
            raise SemanticEvaluationError("command provenance is incomplete")
        provenance = verify_package_provenance(package_dir, status_data)
        hashes = parse_hashes_sha256(package_dir / "hashes.sha256")
        files = {path.name for path in package_dir.iterdir() if path.is_file() and path.name != "hashes.sha256"}
        if set(hashes) != files or any(sha256_file(package_dir / name) != digest for name, digest in hashes.items()):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {"profile": self.profile_id, "provenance": provenance, "source_commit_sha": source, "semantic_verdict": "PASS", "hashed_artifacts": len(hashes)}
