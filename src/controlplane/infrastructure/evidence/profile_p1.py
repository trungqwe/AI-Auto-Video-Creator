"""Fail-closed semantic profile for the M2-P1 evidence package.

The profile deliberately owns the P1-specific identity and regression checks while
the generic validator remains responsible for the package schema and hash-DAG
integrity.  All counts are read from artifacts; values in ``status.json`` are
accepted only after they match those artifacts.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from controlplane.infrastructure.evidence.evaluator import (
    JUnitSummary,
    PackageSemanticProfile,
    SemanticEvaluationError,
    parse_junit_xml,
    parse_secret_scan_json,
    verify_package_provenance,
)
from controlplane.infrastructure.evidence.validator import (
    parse_hashes_sha256,
    sha256_file,
)


MANDATORY_P1_TESTS: tuple[str, ...] = (
    "test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db",
    "test_tst_m2_p1_002_migration_checksum_tamper_rejected",
    "test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected",
    "test_tst_m2_p1_004_bounded_advisory_lock_and_timeout",
    "test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback",
    "test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement",
    "test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented",
    "test_tst_m2_p1_008_destructive_guard_rejects_non_test_db",
    "test_tst_m2_p1_009_applied_migration_file_missing_rejected",
    "test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record",
    "test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool",
)

_P1_FILE = "tests/m2/test_p1_db_and_workspace.py"
MANDATORY_P1_IDENTITIES = frozenset(f"{_P1_FILE}::{name}" for name in MANDATORY_P1_TESTS)


FROZEN_P0_IDENTITIES = frozenset(
    {
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase",
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_domain_rejects_fastapi_import",
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_domain_rejects_psycopg_import",
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_rejects_m1proof_prototype_import",
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_rejects_src_m1proof_prefix_import",
        "tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_domain_rejects_outer_layer_import",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_accepts_valid_package",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_rejects_tampered_hash",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_rejects_self_referential_hash",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_rejects_schema_mismatch",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_rejects_failing_gate_with_pass_status",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_evidence_validator_rejects_untracked_extra_file",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_junit_failures",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_skipped_tests",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_m1_count_mismatch",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_dirty_secret_scan",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_failed_txt_reports",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_live_p0_evidence_is_valid",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_unknown_package_or_profile",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_dispatches_registered_p1_sample_profile",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_blocks_cross_package_profile_spoofing",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_provenance_run_id_mismatch",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_provenance_timestamp_drift",
        "tests/m2/test_p0_evidence_validator.py::test_tst_m2_p0_002_semantic_evaluator_rejects_missing_run_id_in_status",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_controlplane_import_without_syspath_hack",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_no_syspath_hacks_in_controlplane_source",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_pyproject_and_build_lock_metadata",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_backend_dependency_graph_and_build_lock",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_frozen_project_environment_install",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_fresh_environment_wheel_build_and_install",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_003_frozen_install_rejects_mutated_lock_mismatch",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_004_frontend_toolchain_exact_pins_and_runtime_manifest",
        "tests/m2/test_p0_packaging.py::test_tst_m2_p0_005_skeleton_interfaces_raise_not_implemented",
    }
)


P1_TRACEABILITY: dict[str, tuple[str, ...]] = {
    "test_tst_m2_p1_001_migration_forward_and_rollback_on_disposable_db": (
        "ARCH-002",
        "ADR-0002",
        "QR-MNT-002",
    ),
    "test_tst_m2_p1_002_migration_checksum_tamper_rejected": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_003_migration_version_gap_and_duplicate_rejected": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_004_bounded_advisory_lock_and_timeout": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_005_uow_transaction_atomicity_and_rollback": ("ARCH-002", "QR-MNT-002"),
    "test_tst_m2_p1_006_workspace_isolation_and_composite_fk_enforcement": (
        "ADR-0002",
        "CT-API-001 (workspace persistence/binding foundation only)",
    ),
    "test_tst_m2_p1_007_cross_workspace_read_and_status_mutation_prevented": (
        "CT-API-001 (workspace persistence/binding foundation only)",
        "CT-API-010 (AuthSession persistence foundation only)",
        "ADR-0009",
    ),
    "test_tst_m2_p1_008_destructive_guard_rejects_non_test_db": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_009_applied_migration_file_missing_rejected": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_010_sql_migration_failure_rolls_back_without_applied_record": ("ADR-0002", "QR-MNT-002"),
    "test_tst_m2_p1_011_uow_rollback_returns_clean_connection_to_pool": ("ARCH-002", "QR-MNT-002"),
}


def _normalise_test_file(classname: str) -> str:
    """Convert pytest's dotted classname to the repository-relative test path."""
    path = classname.replace(".", "/")
    if not path.endswith(".py"):
        path += ".py"
    return path


def _junit_test_identities(xml_path: Path) -> tuple[list[str], dict[str, int]]:
    if not xml_path.is_file():
        raise SemanticEvaluationError(f"JUnit XML test report missing: {xml_path}")
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        raise SemanticEvaluationError(f"Malformed JUnit XML at {xml_path}: {exc}") from exc

    cases = list(root.iter("testcase"))
    identities: list[str] = []
    for case in cases:
        name = case.attrib.get("name", "").strip()
        classname = case.attrib.get("file") or case.attrib.get("classname", "").strip()
        if not name or not classname:
            raise SemanticEvaluationError(f"JUnit testcase missing classname/file or name in {xml_path}")
        test_file = classname.replace("\\", "/")
        if "/" not in test_file or not test_file.endswith(".py"):
            test_file = _normalise_test_file(test_file)
        identities.append(f"{test_file}::{name}")

    counts: dict[str, int] = {}
    for identity in identities:
        counts[identity] = counts.get(identity, 0) + 1
    return identities, counts


def _metrics_dict(summary: JUnitSummary) -> dict[str, int]:
    return {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failures,
        "errors": summary.errors,
        "skipped": summary.skipped,
    }


def _assert_status_metrics(status_data: dict[str, Any], key: str, summary: JUnitSummary) -> None:
    reported = status_data.get("evidence_summary", {}).get(key)
    actual = _metrics_dict(summary)
    if reported != actual:
        raise SemanticEvaluationError(f"status.json {key} mismatch: reported {reported} vs actual {actual}")


def _assert_hash_dag(package_dir: Path) -> dict[str, str]:
    expected = parse_hashes_sha256(package_dir / "hashes.sha256")
    disk_files = {entry.name for entry in package_dir.iterdir() if entry.is_file() and entry.name != "hashes.sha256"}
    declared_files = set(expected)
    if declared_files != disk_files:
        raise SemanticEvaluationError(
            f"hash DAG file set mismatch: declared={sorted(declared_files)}, disk={sorted(disk_files)}"
        )
    for relative, digest in expected.items():
        actual = sha256_file(package_dir / relative)
        if actual.lower() != digest.lower():
            raise SemanticEvaluationError(f"hash mismatch for evidence artifact {relative}")
    return expected


def _assert_report_clean(path: Path) -> None:
    if not path.is_file():
        raise SemanticEvaluationError(f"Required execution report missing: {path.name}")
    content = path.read_text(encoding="utf-8", errors="replace")
    if "=== FAILURES ===" in content or "=== SHORT TEST SUMMARY INFO ===" in content and "FAILED " in content:
        raise SemanticEvaluationError(f"Failed test summary detected in {path.name}")


class M2P1SemanticProfile(PackageSemanticProfile):
    """Semantic policy for PostgreSQL migrations, identity persistence and evidence."""

    @property
    def profile_id(self) -> str:
        return "m2-p1"

    @property
    def target_package(self) -> str:
        return "M2-P1"

    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        if status_data.get("status") != "READY_FOR_REVIEW":
            raise SemanticEvaluationError("M2-P1 evidence must be READY_FOR_REVIEW for semantic PASS")

        expected_gates = {f"GATE-P1-0{i}" for i in range(1, 7)}
        gates = status_data.get("gates")
        actual_gates = {gate.get("gate_id") for gate in gates or []}
        if actual_gates != expected_gates or any(gate.get("status") != "PASS" for gate in gates or []):
            raise SemanticEvaluationError("M2-P1 gates must be exactly GATE-P1-01..06 and all PASS")

        p1_xml = package_dir / "m2-p1-tests.xml"
        p1_metrics = parse_junit_xml(p1_xml)
        identities, counts = _junit_test_identities(p1_xml)
        observed = set(identities)
        missing = MANDATORY_P1_IDENTITIES - observed
        extra = observed - MANDATORY_P1_IDENTITIES
        duplicates = sorted(identity for identity, count in counts.items() if count != 1)
        if missing or extra or duplicates:
            raise SemanticEvaluationError(
                f"P1 testcase identity mismatch: missing={sorted(missing)}, extra={sorted(extra)}, duplicates={duplicates}"
            )
        if p1_metrics.total != 11 or p1_metrics.passed != 11 or p1_metrics.failures or p1_metrics.errors or p1_metrics.skipped:
            raise SemanticEvaluationError(f"P1 mandatory suite is not 11/11 clean: {_metrics_dict(p1_metrics)}")
        _assert_status_metrics(status_data, "p1_tests", p1_metrics)
        _assert_report_clean(package_dir / "m2-p1-tests-report.txt")

        runtime_path = package_dir / "runtime-capability.json"
        if not runtime_path.is_file():
            raise SemanticEvaluationError("runtime-capability.json is missing")
        try:
            runtime_data = json.loads(runtime_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SemanticEvaluationError(f"Malformed runtime capability artifact: {exc}") from exc
        expected_runtime = {
            "python": "3.13.15",
            "psycopg": "3.3.5",
            "psycopg-pool": "3.3.1",
            "actual_pool_implementation": "psycopg_pool.ConnectionPool",
            "postgresql_server": "18.6",
            "createdb_prerequisite": True,
            "disposable_db_orphan_count": 0,
        }
        if runtime_data.get("run_id") != status_data.get("run_id"):
            raise SemanticEvaluationError("runtime-capability.json run_id does not match status.json")
        if {key: runtime_data.get(key) for key in expected_runtime} != expected_runtime:
            raise SemanticEvaluationError(
                "runtime capability does not match the locked Python/driver/pool/PostgreSQL prerequisites"
            )
        if status_data.get("runtime_capability") != runtime_data:
            raise SemanticEvaluationError("status.json runtime_capability does not match runtime-capability.json")

        p0_xml = package_dir / "m2-p0-regression.xml"
        p0_metrics = parse_junit_xml(p0_xml)
        p0_identities, p0_counts = _junit_test_identities(p0_xml)
        p0_observed = set(p0_identities)
        p0_missing = FROZEN_P0_IDENTITIES - p0_observed
        p0_extra = p0_observed - FROZEN_P0_IDENTITIES
        p0_duplicates = sorted(identity for identity, count in p0_counts.items() if count != 1)
        if p0_missing or p0_extra or p0_duplicates:
            raise SemanticEvaluationError(
                f"Frozen P0 testcase identity mismatch: missing={sorted(p0_missing)}, extra={sorted(p0_extra)}, duplicates={p0_duplicates}"
            )
        if p0_metrics.total != 33 or p0_metrics.passed != 33 or p0_metrics.failures or p0_metrics.errors or p0_metrics.skipped:
            raise SemanticEvaluationError(f"Frozen P0 regression is not 33/33 clean: {_metrics_dict(p0_metrics)}")
        _assert_status_metrics(status_data, "m2_p0_regression_tests", p0_metrics)
        _assert_report_clean(package_dir / "m2-p0-regression-report.txt")

        m1_xml = package_dir / "m1-regression.xml"
        m1_metrics = parse_junit_xml(m1_xml)
        if m1_metrics.total != 93 or m1_metrics.passed != 93 or m1_metrics.failures or m1_metrics.errors or m1_metrics.skipped:
            raise SemanticEvaluationError(f"M1 regression is not exactly 93/93 clean: {_metrics_dict(m1_metrics)}")
        _assert_status_metrics(status_data, "m1_regression_tests", m1_metrics)
        _assert_report_clean(package_dir / "m1-regression-report.txt")

        secret_data = parse_secret_scan_json(package_dir / "secret-scan.json")
        if secret_data.get("run_id") != status_data.get("run_id"):
            raise SemanticEvaluationError("secret-scan.json run_id does not match status.json")
        if secret_data.get("verdict") != "CLEAN" or secret_data.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan is not CLEAN with zero findings")
        if status_data.get("evidence_summary", {}).get("secret_scan_violations") != 0:
            raise SemanticEvaluationError("status.json reports secret scan violations")

        commands = package_dir / "commands.jsonl"
        if not commands.is_file():
            raise SemanticEvaluationError("commands.jsonl missing")
        records = [json.loads(line) for line in commands.read_text(encoding="utf-8").splitlines() if line.strip()]
        if any(record.get("exit_code") != 0 for record in records):
            raise SemanticEvaluationError("commands.jsonl contains a non-zero command")
        required_artifacts = {
            "m2-p1-tests.xml",
            "m2-p1-tests-report.txt",
            "m2-p0-regression.xml",
            "m2-p0-regression-report.txt",
            "m1-regression.xml",
            "m1-regression-report.txt",
            "secret-scan.json",
            "runtime-capability.json",
        }
        produced = {artifact for record in records for artifact in record.get("created_artifacts", [])}
        if not required_artifacts.issubset(produced):
            raise SemanticEvaluationError(f"Missing command provenance for artifacts: {sorted(required_artifacts - produced)}")
        runtime_records = [r for r in records if "runtime-capability.json" in r.get("created_artifacts", [])]
        if not runtime_records:
            raise SemanticEvaluationError("No command record produced runtime-capability.json")
        p0_records = [record for record in records if "m2-p0-regression.xml" in record.get("created_artifacts", [])]
        if not p0_records:
            raise SemanticEvaluationError("No command record produced m2-p0-regression.xml")
        p0_command = p0_records[-1].get("command", "").replace("\\", "/")
        for source in (
            "tests/m2/test_p0_architecture_rules.py",
            "tests/m2/test_p0_evidence_validator.py",
            "tests/m2/test_p0_packaging.py",
        ):
            if source not in p0_command:
                raise SemanticEvaluationError(f"Frozen P0 command omitted source suite {source}")

        provenance = verify_package_provenance(package_dir, status_data)
        hashes = _assert_hash_dag(package_dir)
        return {
            "profile": self.profile_id,
            "p1_tests": p1_metrics,
            "m2_p0_regression_tests": p0_metrics,
            "m1_tests": m1_metrics,
            "secret_scan": secret_data.get("verdict"),
            "provenance": provenance,
            "hashed_artifacts": len(hashes),
            "traceability": P1_TRACEABILITY,
            "semantic_verdict": "PASS",
        }
