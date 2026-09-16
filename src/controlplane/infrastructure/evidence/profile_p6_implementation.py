"""Fail-closed semantic profile for M2-P6 implementation closure."""

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
from controlplane.infrastructure.evidence.profile_p6 import (
    NAMES,
    ORACLE_PATH,
    ORACLE_SHA,
)
from controlplane.infrastructure.evidence.validator import (
    parse_hashes_sha256,
    sha256_file,
)

SUITES = {
    "p6.xml": 4,
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
PROBES = (
    "migration_forward",
    "migration_rollback_preserves_0001_0005",
    "cross_workspace_binding_rejected",
    "capacity_last_slot_no_orphan",
    "allocation_fault_no_orphan",
    "variant_race_one_conflict",
    "stale_variant_zero_reservation",
    "second_completion_rejected",
    "artifact_hash_mismatch_rejected",
    "reservation_job_mismatch_rejected",
    "completion_fault_zero_mutation",
    "duplicate_completion_one_identity",
)


class M2P6ImplementationSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p6-implementation"

    @property
    def target_package(self) -> str:
        return "M2-P6"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (
            status.get("status") != "READY_FOR_REVIEW"
            or status.get("lifecycle") != "M2-P6_IMPLEMENTATION_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P6 implementation lifecycle mismatch")
        for name, count in SUITES.items():
            result = parse_junit_xml(directory / name)
            if (
                result.total,
                result.passed,
                result.failures,
                result.errors,
                result.skipped,
            ) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"suite mismatch: {name}")
        if (
            tuple(
                case.attrib["name"]
                for case in ET.parse(directory / "p6.xml").iter("testcase")
            )
            != NAMES
        ):
            raise SemanticEvaluationError("P6 identity mismatch")
        probes = json.loads(
            (directory / "hardening-probes.json").read_text(encoding="utf-8")
        )
        if (
            probes.get("verdict") != "PASS"
            or tuple(probes.get("checks", {})) != PROBES
            or not all(probes["checks"].values())
        ):
            raise SemanticEvaluationError("hardening probes failed")
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
            "migration_0006_present": True,
            "migration_runner_unchanged": True,
            "p5a_p5b_accepted_unchanged": True,
            "historical_evidence_preserved": True,
            "application_orchestration_sql_statements": 0,
            "application_orchestration_psycopg_imports": 0,
            "application_to_infrastructure_imports": 0,
            "domain_to_application_imports": 0,
            "domain_to_infrastructure_imports": 0,
            "domain_external_db_imports": 0,
            "adapter_sql_present": True,
            "adapter_receives_caller_owned_connection": True,
            "adapter_pool_creation": 0,
            "adapter_commit_calls": 0,
            "adapter_rollback_calls": 0,
            "adapter_transaction_ownership": 0,
            "services_repository_factory_injected": True,
        }
        if any(runtime.get(key) != value for key, value in required.items()):
            raise SemanticEvaluationError("runtime/static mismatch")
        source = status.get("source_commit_sha")
        root = Path(__file__).parents[4]
        oracle = hashlib.sha256(
            subprocess.check_output(
                ["git", "show", f"{source}:{ORACLE_PATH}"], cwd=root
            )
        ).hexdigest()
        if oracle != ORACLE_SHA or status.get("oracle_sha256") != ORACLE_SHA:
            raise SemanticEvaluationError("oracle drift")
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=root
        ).returncode:
            raise SemanticEvaluationError("invalid source ancestry")
        secret = json.loads(
            (directory / "secret-scan.json").read_text(encoding="utf-8")
        )
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan failed")
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
        if "EXPECTED_REJECTION=PASS" not in (
            directory / "negative-verifier-stdout.txt"
        ).read_text(encoding="utf-8"):
            raise SemanticEvaluationError("negative verifier missing")
        return {
            "profile": self.profile_id,
            "semantic_verdict": "PASS",
            "provenance": provenance,
            "hashed_artifacts": len(hashes),
        }
