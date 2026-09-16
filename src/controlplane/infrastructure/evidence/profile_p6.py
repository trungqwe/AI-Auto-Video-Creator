"""Fail-closed semantic profile for M2-P6 Behavioral RED."""

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
from controlplane.infrastructure.evidence.validator import (
    parse_hashes_sha256,
    sha256_file,
)

ORACLE_PATH = "tests/m2/test_p6_orchestration_shell.py"
ORACLE_SHA = "e5d2b248481366597a96caee313c46e03238e16369fb48799d6359ad80daccc1"
NAMES = (
    "test_tst_m2_p6_001_execution_grant_stale_epoch_fencing",
    "test_tst_m2_p6_002_variant_reservation_cas_and_conflict",
    "test_tst_m2_p6_003_batch_capacity_reservation_lifecycle",
    "test_tst_m2_p6_004_completion_ledger_unique_job_invariant",
)
FAILURE_MARKERS = (
    "P6-001 execution grant fencing",
    "P6-002 variant reservation CAS",
    "P6-003 batch capacity persistence",
    "P6-004 completion ledger persistence",
)
REGRESSIONS = {
    "p5b-regression.xml": 5,
    "p5a-regression.xml": 5,
    "p4-regression.xml": 9,
    "p3-regression.xml": 11,
    "p2-regression.xml": 11,
    "p1-regression.xml": 11,
    "p0-regression.xml": 33,
    "architecture.xml": 6,
    "m1-regression.xml": 93,
}
STAGES = {
    "collect-p6",
    "red-p6",
    *{x.removesuffix(".xml") for x in REGRESSIONS},
    "runtime-static-capture",
    "orphan-check",
    "secret-scan",
    "evidence-synthesis",
    "hash-manifest-generation",
    "hash-verification",
    "verify-only",
    "negative-verifier-tamper-check",
}


def _metrics(path: Path) -> tuple[int, int, int, int, int]:
    result = parse_junit_xml(path)
    return result.total, result.passed, result.failures, result.errors, result.skipped


class M2P6SemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p6"

    @property
    def target_package(self) -> str:
        return "M2-P6"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (
            status.get("status") != "READY_FOR_REVIEW"
            or status.get("lifecycle") != "M2-P6_BEHAVIORAL_RED_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P6 RED lifecycle mismatch")
        if _metrics(directory / "red-p6.xml") != (4, 0, 4, 0, 0):
            raise SemanticEvaluationError("P6 RED count mismatch")
        cases = list(ET.parse(directory / "red-p6.xml").iter("testcase"))
        if tuple(case.attrib["name"] for case in cases) != NAMES:
            raise SemanticEvaluationError("P6 identity mismatch")
        for case, marker in zip(cases, FAILURE_MARKERS, strict=True):
            failure = case.find("failure")
            if (
                failure is None
                or "NotImplementedError"
                not in (failure.attrib.get("message", "") + (failure.text or ""))
                or marker not in (failure.text or "")
            ):
                raise SemanticEvaluationError("P6 failure classification mismatch")
        for name, count in REGRESSIONS.items():
            if _metrics(directory / name) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"regression mismatch: {name}")
        runtime = json.loads(
            (directory / "runtime-and-static.json").read_text(encoding="utf-8")
        )
        required = {
            "python": "3.13.15",
            "psycopg": "3.3.5",
            "psycopg_pool": "3.3.1",
            "postgresql": "18.6",
            "createdb": True,
            "m2_orphan_count": 0,
            "migration_0006_absent": True,
            "migration_runner_unchanged": True,
            "p5a_p5b_accepted_unchanged": True,
            "p5b_evidence_preserved": True,
        }
        if any(runtime.get(key) != value for key, value in required.items()):
            raise SemanticEvaluationError("runtime/static mismatch")
        source = status.get("source_commit_sha")
        root = Path(__file__).parents[4]
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=root
        ).returncode:
            raise SemanticEvaluationError("invalid source ancestry")
        if (
            hashlib.sha256(
                subprocess.check_output(
                    ["git", "show", f"{source}:{ORACLE_PATH}"], cwd=root
                )
            ).hexdigest()
            != ORACLE_SHA
            or status.get("oracle_sha256") != ORACLE_SHA
        ):
            raise SemanticEvaluationError("oracle drift")
        secret = json.loads(
            (directory / "secret-scan.json").read_text(encoding="utf-8")
        )
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan failed")
        commands = [
            json.loads(line)
            for line in (directory / "commands.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        if not STAGES <= {item.get("stage") for item in commands} or any(
            item.get("run_id") != status.get("run_id")
            or item.get("source_commit_sha") != source
            for item in commands
        ):
            raise SemanticEvaluationError("provenance incomplete")
        if "EXPECTED_REJECTION=PASS" not in (
            directory / "negative-verifier-stdout.txt"
        ).read_text(encoding="utf-8"):
            raise SemanticEvaluationError("negative verifier missing")
        provenance = verify_package_provenance(directory, status)
        hashes = parse_hashes_sha256(directory / "hashes.sha256")
        disk = {
            path.name
            for path in directory.iterdir()
            if path.is_file() and path.name != "hashes.sha256"
        }
        if set(hashes) != disk or any(
            sha256_file(directory / name) != digest for name, digest in hashes.items()
        ):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {
            "profile": self.profile_id,
            "semantic_verdict": "PASS",
            "provenance": provenance,
            "hashed_artifacts": len(hashes),
        }
