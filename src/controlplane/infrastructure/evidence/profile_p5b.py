"""Fail-closed semantic profile for M2-P5B implementation closure."""

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

ORACLE_PATH = "tests/m2/test_p5b_artifact_metadata.py"
ORACLE_SHA = "be87c943b9a4a129156b452df70bf55e58b95ea8c418a8822a82100cd9c77030"
NAMES = (
    "test_tst_m2_p5b_001_artifact_version_registration_and_hash_integrity",
    "test_tst_m2_p5b_002_location_state_lifecycle_and_verification",
    "test_tst_m2_p5b_003_cleanup_authorization_requires_verified_location",
    "test_tst_m2_p5b_004_production_0005_forward_rollback_and_constraints",
    "test_tst_m2_p5b_005_workspace_isolation_and_location_revision_conflict",
)
SUITES = {
    "p5b.xml": 5,
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
    "collect-p5b",
    *{x.removesuffix(".xml") for x in SUITES},
    "runtime-static-capture",
    "hardening-probes",
    "orphan-check",
    "secret-scan",
    "evidence-synthesis",
    "hash-manifest-generation",
    "hash-verification",
    "verify-only",
    "negative-verifier-tamper-check",
}


def metrics(path):
    x = parse_junit_xml(path)
    return x.total, x.passed, x.failures, x.errors, x.skipped


class M2P5BSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self):
        return "m2-p5b"

    @property
    def target_package(self):
        return "M2-P5B"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (
            status.get("status") != "READY_FOR_REVIEW"
            or status.get("lifecycle") != "M2-P5B_IMPLEMENTATION_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P5B lifecycle mismatch")
        for name, count in SUITES.items():
            if metrics(directory / name) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"suite mismatch: {name}")
        if (
            tuple(
                c.attrib["name"]
                for c in ET.parse(directory / "p5b.xml").iter("testcase")
            )
            != NAMES
        ):
            raise SemanticEvaluationError("P5B identity mismatch")
        runtime = json.loads(
            (directory / "runtime-and-static.json").read_text(encoding="utf-8")
        )
        probes = json.loads((directory / "hardening-probes.json").read_text(encoding="utf-8"))
        if probes.get("verdict") != "PASS" or not all(probes.get("checks", {}).values()):
            raise SemanticEvaluationError("hardening probes failed")
        required = {
            "python": "3.13.15",
            "psycopg": "3.3.5",
            "psycopg_pool": "3.3.1",
            "postgresql": "18.6",
            "createdb": True,
            "m2_orphan_count": 0,
            "migration_runner_unchanged": True,
            "p5a_source_and_oracle_unchanged": True,
            "historical_corrected_red_preserved": True,
            "migration_0005_present": True,
            "application_storage_meta_sql_statements": 0,
            "infrastructure_storage_meta_sql_present": True,
            "adapter_uses_caller_owned_connection": True,
        }
        if any(runtime.get(k) != v for k, v in required.items()) or any(
            runtime.get(k) != 0
            for k in (
                "domain_to_application_imports",
                "domain_to_infrastructure_imports",
                "application_to_infrastructure_imports",
                "domain_psycopg_imports",
                "application_psycopg_imports",
            )
        ):
            raise SemanticEvaluationError("runtime/static mismatch")
        secret = json.loads(
            (directory / "secret-scan.json").read_text(encoding="utf-8")
        )
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan failed")
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
        commands = [
            json.loads(x)
            for x in (directory / "commands.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if x.strip()
        ]
        if not STAGES <= {x.get("stage") for x in commands} or any(
            x.get("run_id") != status.get("run_id")
            or x.get("source_commit_sha") != source
            for x in commands
        ):
            raise SemanticEvaluationError("provenance incomplete")
        if "EXPECTED_REJECTION=PASS" not in (
            directory / "negative-verifier-stdout.txt"
        ).read_text(encoding="utf-8"):
            raise SemanticEvaluationError("negative verifier missing")
        provenance = verify_package_provenance(directory, status)
        hashes = parse_hashes_sha256(directory / "hashes.sha256")
        disk = {
            p.name
            for p in directory.iterdir()
            if p.is_file() and p.name != "hashes.sha256"
        }
        if set(hashes) != disk or any(
            sha256_file(directory / n) != d for n, d in hashes.items()
        ):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {
            "profile": self.profile_id,
            "semantic_verdict": "PASS",
            "provenance": provenance,
            "hashed_artifacts": len(hashes),
        }
