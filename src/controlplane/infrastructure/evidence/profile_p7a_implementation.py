"""Fail-closed semantic profile for immutable M2-P7A GREEN evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from controlplane.infrastructure.evidence.evaluator import (
    PackageSemanticProfile, SemanticEvaluationError, parse_junit_xml,
    verify_package_provenance,
)
from controlplane.infrastructure.evidence.profile_p7a import NAMES, ORACLE_PATH, ORACLE_SHA
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file


ROOT = Path(__file__).parents[4]
SUITES = {
    "p7a-oracle.xml": 4,
    "p7a-hardening.xml": 36,
    "p6-regression.xml": 4,
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
HARDENING_NAMES = (
    "test_h01_actual_app_host_reject", "test_h02_origin_reject",
    "test_h03_valid_host_origin_success", "test_h04_csrf_missing_reject",
    "test_h05_csrf_mismatch_reject", "test_h06_csrf_match_success",
    "test_h07_session_cookie_flags", "test_h08_client_workspace_ignored",
    "test_h09_session_workspace_binding", "test_h10_detail_cross_workspace_reject",
    "test_h11_problem_detail_safe", "test_h12_detail_durable_row",
    "test_h13_detail_access_audit", "test_h14_migration_forward",
    "test_h15_rollback_preserves_0001_0006", "test_h16_migration_tracker",
    "test_h17_actual_fastapi_tls_request", "test_h18_tls_verification_enabled",
    "test_h19_loopback_only", "test_h20_response_log_redaction",
    "test_h21_idempotency_header_reject", "test_h22_if_match_reject",
    "test_h23_revision_conflict_409", "test_h24_business_validation_422",
    "test_h25_idempotent_replay_one_command", "test_h26_correlation_id",
    "test_h27_accepted_202_not_completion", "test_h28_static_architecture",
    "test_h35_bootstrap_capability_single_use_and_expiry",
    "test_h36_bootstrap_capability_not_leaked",
    "test_h29_start_batch_atomic_commit", "test_h30_start_batch_fault_full_rollback",
    "test_h31_start_batch_duplicate_same_identity", "test_h32_start_batch_key_reuse_conflict",
    "test_h33_config_mutation_atomic_idempotency",
    "test_h34_config_duplicate_no_second_revision",
)


class M2P7AImplementationSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p7a-implementation"

    @property
    def target_package(self) -> str:
        return "M2-P7A"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (status.get("status"), status.get("lifecycle")) != (
            "READY_FOR_REVIEW", "M2-P7A_IMPLEMENTATION_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P7A GREEN lifecycle mismatch")
        source = status.get("source_commit_sha")
        if not isinstance(source, str) or len(source) != 40:
            raise SemanticEvaluationError("immutable source SHA missing")
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT,
            capture_output=True,
        ).returncode:
            raise SemanticEvaluationError("source ancestry mismatch")
        committed_oracle = subprocess.check_output(
            ["git", "show", f"{source}:{ORACLE_PATH}"], cwd=ROOT,
        )
        if (hashlib.sha256(committed_oracle).hexdigest() != ORACLE_SHA
                or status.get("oracle_sha256") != ORACLE_SHA):
            raise SemanticEvaluationError("accepted oracle drift")
        for relative in (
            "src/controlplane/infrastructure/evidence/probe_p7a_implementation.py",
            "src/controlplane/infrastructure/evidence/profile_p7a_implementation.py",
            "src/controlplane/infrastructure/evidence/synthesizer_p7a_implementation.py",
        ):
            committed = subprocess.check_output(["git", "show", f"{source}:{relative}"], cwd=ROOT)
            if (ROOT / relative).read_bytes() != committed:
                raise SemanticEvaluationError("source/tooling differs from immutable SHA")
        for filename, count in SUITES.items():
            result = parse_junit_xml(directory / filename)
            if (result.total, result.passed, result.failures, result.errors,
                    result.skipped) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"suite mismatch: {filename}")
        oracle_cases = tuple(
            case.attrib["name"] for case in ET.parse(directory / "p7a-oracle.xml").iter("testcase")
        )
        if oracle_cases != NAMES:
            raise SemanticEvaluationError("P7A oracle identities mismatch")
        hardening = tuple(
            case.attrib["name"] for case in ET.parse(directory / "p7a-hardening.xml").iter("testcase")
        )
        if hardening != HARDENING_NAMES:
            raise SemanticEvaluationError("H01-H36 identity mismatch")
        checks = json.loads((directory / "p7a-hardening.json").read_text(encoding="utf-8"))
        if (checks.get("verdict") != "PASS" or checks.get("count") != 36
                or tuple(checks.get("checks", {})) != HARDENING_NAMES
                or not all(checks["checks"].values())):
            raise SemanticEvaluationError("P7A hardening catalogue mismatch")
        migration = json.loads((directory / "migration-proof.json").read_text(encoding="utf-8"))
        if (migration.get("testcase") != "test_h16_migration_tracker"
                or migration.get("observed_by") != "p7a-hardening.xml"
                or migration.get("forward_versions") != list(range(1, 8))
                or migration.get("rollback_versions") != list(range(1, 7))
                or migration.get("reapply_versions") != list(range(1, 8))
                or migration.get("verdict") != "PASS"):
            raise SemanticEvaluationError("migration tracker proof mismatch")
        runtime = json.loads((directory / "runtime-and-static.json").read_text(encoding="utf-8"))
        required = {
            "source_commit_sha": source, "python": "3.13.15",
            "fastapi": "0.141.1", "uvicorn": "0.52.4", "httpx": "0.28.1",
            "cryptography": "46.0.5", "psycopg": "3.3.5",
            "psycopg_pool": "3.3.1", "postgresql": "18.6",
            "createdb": True, "m2_orphan_count": 0,
            "uv_runtime_observed": "0.12.13", "uv_lock_version": "0.12.13",
            "migration_0007_present": True,
            "migration_runner_unchanged": True,
            "accepted_oracle_unchanged": True,
            "p1_p6_source_unchanged": True,
            "source_scope_exact_pass": True,
            "source_scope_negative_probe_pass": True,
            "unexpected_scope_paths": [],
            "historical_evidence_preserved": True,
            "application_to_infrastructure_imports": 0,
            "domain_to_application_imports": 0,
            "domain_external_imports": 0,
            "api_sql_statements": 0,
            "api_psycopg_imports": 0,
            "application_command_sql_statements": 0,
            "composite_adapter_transaction_ownership": 0,
        }
        if any(runtime.get(key) != expected for key, expected in required.items()):
            raise SemanticEvaluationError("runtime/static mismatch")
        secret = json.loads((directory / "secret-scan.json").read_text(encoding="utf-8"))
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan mismatch")
        quality = json.loads((directory / "quality-status.json").read_text(encoding="utf-8"))
        if any(quality.get(key) != "PASS" for key in
               ("ruff", "uv_lock_check", "wheel_build", "wheel_import")):
            raise SemanticEvaluationError("mandatory quality stage mismatch")
        if quality.get("build_backend_locked") is not True:
            raise SemanticEvaluationError("locked build backend not proved")
        if quality.get("mypy") not in {"PASS", "SKIP_UNAVAILABLE_NOT_IN_LOCK"}:
            raise SemanticEvaluationError("mypy status missing")
        commands = [json.loads(line) for line in
                    (directory / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
        stages = {item.get("stage") for item in commands}
        required_stages = {name.removesuffix(".xml") for name in SUITES}
        required_stages.update({"runtime-static", "secret-scan", "hash-verification",
                                "negative-verifier-tamper-check", "verify-only",
                                "quality-ruff", "quality-lock", "quality-build",
                                "quality-wheel-import", "quality-mypy", "quality-status",
                                "migration-tracker-proof"})
        if not required_stages <= stages or any(item.get("source_commit_sha") != source for item in commands):
            raise SemanticEvaluationError("command provenance mismatch")
        if any(item.get("exit_code") != 0 for item in commands):
            raise SemanticEvaluationError("quality or command failure recorded")
        if "EXPECTED_REJECTION=PASS" not in (
            directory / "negative-verifier-stdout.txt"
        ).read_text(encoding="utf-8"):
            raise SemanticEvaluationError("tamper-negative proof missing")
        provenance = verify_package_provenance(directory, status)
        hashes = parse_hashes_sha256(directory / "hashes.sha256")
        files = {path.name for path in directory.iterdir()
                 if path.is_file() and path.name != "hashes.sha256"}
        if set(hashes) != files or any(
            sha256_file(directory / name) != digest for name, digest in hashes.items()
        ):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {"profile": self.profile_id, "semantic_verdict": "PASS",
                "provenance": provenance, "hashed_artifacts": len(hashes)}
