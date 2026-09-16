"""Fail-closed semantic profile for intentional M2-P5B Behavioral RED evidence."""
from __future__ import annotations

import hashlib
import json
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
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file


ORACLE_PATH = "tests/m2/test_p5b_artifact_metadata.py"
EXPECTED_NAMES = (
    "test_tst_m2_p5b_001_artifact_version_registration_and_hash_integrity",
    "test_tst_m2_p5b_002_location_state_lifecycle_and_verification",
    "test_tst_m2_p5b_003_cleanup_authorization_requires_verified_location",
    "test_tst_m2_p5b_004_production_0005_forward_rollback_and_constraints",
    "test_tst_m2_p5b_005_workspace_isolation_and_location_revision_conflict",
)
GREEN_SUITES = {
    "p5a-regression.xml": 5, "p4-regression.xml": 9, "p3-regression.xml": 11,
    "p2-regression.xml": 11, "p1-regression.xml": 11, "p0-regression.xml": 33,
    "architecture.xml": 6, "m1-regression.xml": 93,
}
MANDATORY = {
    "commands.jsonl", "collect-p5b-stdout.txt", "p5b-red-stdout.txt", "p5b-red.xml",
    *GREEN_SUITES, *(name.replace(".xml", "-stdout.txt") for name in GREEN_SUITES),
    "drive-e3-fresh.json", "results.json", "runtime-and-static.json", "secret-scan.json",
    "secret-scan-stdout.txt", "orphan-check.txt", "observations.md", "status.json", "status.md",
    "verify-only-stdout.txt", "negative-verifier-stdout.txt", "historical-restoration.txt",
}
REQUIRED_STAGES = {
    "collect-p5b", "p5b-red", "p5a-regression", "p4-regression", "p3-regression",
    "p2-regression", "p1-regression", "p0-regression", "architecture", "m1-regression",
    "runtime-static-capture", "orphan-check", "secret-scan", "evidence-synthesis",
    "hash-manifest-generation", "hash-verification", "verify-only", "negative-verifier-tamper-check",
}


def _metrics(path: Path) -> tuple[int, int, int, int, int]:
    value = parse_junit_xml(path)
    return value.total, value.passed, value.failures, value.errors, value.skipped


def _names(path: Path) -> tuple[str, ...]:
    return tuple(case.attrib["name"] for case in ET.parse(path).iter("testcase"))


class M2P5BRedSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p5b-behavioral-red"

    @property
    def target_package(self) -> str:
        return "M2-P5B"

    def evaluate(self, package_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
        if status.get("status") != "READY_FOR_REVIEW" or status.get("lifecycle") != "M2-P5B_BEHAVIORAL_RED_READY_FOR_REVIEW" or status.get("implementation_authorized") is not False:
            raise SemanticEvaluationError("P5B RED lifecycle/authorization mismatch")
        if _metrics(package_dir / "p5b-red.xml") != (5, 0, 5, 0, 0) or _names(package_dir / "p5b-red.xml") != EXPECTED_NAMES:
            raise SemanticEvaluationError("P5B intentional RED metrics or identities mismatch")
        red_text = (package_dir / "p5b-red-stdout.txt").read_text(encoding="utf-8")
        markers = ("artifact-version store is not implemented", "artifact-location store is not implemented", "cleanup-authorization policy/store is not implemented", "missing production migration 0005")
        if not all(marker in red_text for marker in markers):
            raise SemanticEvaluationError("P5B failure classification mismatch")
        for name, count in GREEN_SUITES.items():
            if _metrics(package_dir / name) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"Regression suite is not clean: {name}")
        runtime = json.loads((package_dir / "runtime-and-static.json").read_text(encoding="utf-8"))
        required = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg_pool": "3.3.1", "postgresql": "18.6", "createdb": True, "m2_orphan_count": 0, "production_0005_absent": True, "migration_runner_unchanged": True, "p5a_source_and_oracle_unchanged": True, "p6_plus_source_absent": True}
        if any(runtime.get(key) != value for key, value in required.items()) or any(runtime.get(key) != 0 for key in ("domain_to_application_imports", "domain_to_infrastructure_imports", "application_to_infrastructure_imports", "domain_psycopg_imports", "application_psycopg_imports")):
            raise SemanticEvaluationError("Runtime/static evidence mismatch")
        secret = json.loads((package_dir / "secret-scan.json").read_text(encoding="utf-8"))
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("Secret scan is not CLEAN")
        root = Path(__file__).parents[4]
        source = status.get("source_commit_sha")
        oracle = status.get("oracle_sha256")
        if subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=root).returncode:
            raise SemanticEvaluationError("Source commit is not immutable ancestry")
        blob = subprocess.check_output(["git", "show", f"{source}:{ORACLE_PATH}"], cwd=root)
        if hashlib.sha256(blob).hexdigest() != oracle or runtime.get("oracle_sha256") != oracle:
            raise SemanticEvaluationError("Oracle SHA does not match source commit")
        commands = [json.loads(line) for line in (package_dir / "commands.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        stages = {record.get("stage") for record in commands}
        if not REQUIRED_STAGES <= stages or any(record.get("run_id") != status.get("run_id") or record.get("source_commit_sha") != source or not isinstance(record.get("exit_code"), int) for record in commands):
            raise SemanticEvaluationError("Command provenance is incomplete or inconsistent")
        if "EXPECTED_REJECTION=PASS" not in (package_dir / "negative-verifier-stdout.txt").read_text(encoding="utf-8"):
            raise SemanticEvaluationError("Negative verifier proof missing")
        provenance = verify_package_provenance(package_dir, status)
        hashes = parse_hashes_sha256(package_dir / "hashes.sha256")
        disk = {path.name for path in package_dir.iterdir() if path.is_file() and path.name != "hashes.sha256"}
        if set(hashes) != disk or not MANDATORY <= disk or any(sha256_file(package_dir / name) != digest for name, digest in hashes.items()):
            raise SemanticEvaluationError("Hash DAG is incomplete or invalid")
        return {"profile": self.profile_id, "semantic_verdict": "PASS", "provenance": provenance, "hashed_artifacts": len(hashes)}
