"""Versioned semantic profile for the reviewed P6 correction evidence.

The original GREEN profile remains unchanged so the historical candidate run
retains its own verification semantics.
"""

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
from controlplane.infrastructure.evidence.profile_p6_implementation import SUITES
from controlplane.infrastructure.evidence.validator import (
    parse_hashes_sha256,
    sha256_file,
)

PROBES = (
    "migration_forward",
    "migration_rollback_preserves_0001_0005",
    "cross_workspace_binding_rejected",
    "allocation_fault_no_orphan",
    "capacity_last_slot_no_orphan",
    "capacity_cross_batch_retry_rejected",
    "variant_race_one_conflict",
    "stale_variant_zero_reservation",
    "variant_exact_retry_and_changed_expected_rejected",
    "registry_concurrent_first_use",
    "registry_fresh_workspace_initialized",
    "registry_failed_first_use_atomic",
    "second_completion_rejected",
    "artifact_hash_mismatch_rejected",
    "reservation_job_mismatch_rejected",
    "completion_fault_zero_mutation",
    "duplicate_completion_one_identity",
    "different_completion_input_forbidden_unchanged",
)


class M2P6CorrectionSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p6-correction"

    @property
    def target_package(self) -> str:
        return "M2-P6"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (
            status.get("status") != "READY_FOR_REVIEW"
            or status.get("lifecycle") != "M2-P6_IMPLEMENTATION_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P6 lifecycle mismatch")
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
        identities = tuple(
            case.attrib["name"]
            for case in ET.parse(directory / "p6.xml").iter("testcase")
        )
        if identities != NAMES:
            raise SemanticEvaluationError("P6 oracle identity mismatch")
        probes = json.loads(
            (directory / "hardening-probes.json").read_text(encoding="utf-8")
        )
        if (
            probes.get("verdict") != "PASS"
            or probes.get("count") != len(PROBES)
            or tuple(probes.get("checks", {})) != PROBES
            or not all(probes["checks"].values())
            or "oracle_stdout" in probes
            or probes.get("migration_tracker_before_rollback") != [1, 2, 3, 4, 5, 6]
            or probes.get("migration_tracker_after_rollback") != [1, 2, 3, 4, 5]
        ):
            raise SemanticEvaluationError("independent hardening probe mismatch")
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
        commands = [
            json.loads(line)
            for line in (directory / "commands.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        if any(record.get("source_commit_sha") != source for record in commands):
            raise SemanticEvaluationError("command source mismatch")
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
            "hardening_probes": len(PROBES),
        }
