"""Fail-closed semantic profile for the M2-P2 evidence package."""
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
from controlplane.infrastructure.evidence.profile_p1 import (
    FROZEN_P0_IDENTITIES,
    MANDATORY_P1_IDENTITIES,
)
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file


MANDATORY_P2_TESTS = (
    "test_tst_m2_p2_001_envelope_required_fields_and_rfc3339_utc",
    "test_tst_m2_p2_002_problem_detail_transport_neutral_safe_contract",
    "test_tst_m2_p2_003_durable_command_receipt_persistence",
    "test_tst_m2_p2_004_same_key_same_canonical_payload_replays_same_receipt",
    "test_tst_m2_p2_005_same_key_different_payload_rejected",
    "test_tst_m2_p2_006_concurrent_same_key_same_payload_one_logical_receipt",
    "test_tst_m2_p2_007_concurrent_same_key_different_payload_rejects_loser",
    "test_tst_m2_p2_008_workspace_scoped_idempotency_isolation_and_restart",
    "test_tst_m2_p2_009_successful_revision_update_increments_exactly_once",
    "test_tst_m2_p2_010_stale_revision_conflict_zero_mutation_and_current_revision",
    "test_tst_m2_p2_011_production_0002_forward_rollback_and_constraints",
)
_P2_FILE = "tests/m2/test_p2_envelopes_and_idempotency.py"
MANDATORY_P2_IDENTITIES = frozenset(f"{_P2_FILE}::{name}" for name in MANDATORY_P2_TESTS)


def _identities(xml_path: Path) -> tuple[set[str], dict[str, int]]:
    if not xml_path.is_file():
        raise SemanticEvaluationError(f"JUnit XML report missing: {xml_path.name}")
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        raise SemanticEvaluationError(f"Malformed JUnit XML {xml_path.name}: {exc}") from exc
    counts: dict[str, int] = {}
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "")
        source = case.attrib.get("file") or case.attrib.get("classname", "")
        source = source.replace("\\", "/")
        if "/" not in source:
            source = source.replace(".", "/") + ("" if source.endswith(".py") else ".py")
        if not name or not source:
            raise SemanticEvaluationError(f"JUnit testcase lacks identity in {xml_path.name}")
        identity = f"{source}::{name}"
        counts[identity] = counts.get(identity, 0) + 1
    return set(counts), counts


def _metrics(summary: JUnitSummary) -> dict[str, int]:
    return {"total": summary.total, "passed": summary.passed, "failed": summary.failures, "errors": summary.errors, "skipped": summary.skipped}


def _assert_suite(package_dir: Path, filename: str, expected: frozenset[str], total: int, status: dict[str, Any], key: str) -> JUnitSummary:
    summary = parse_junit_xml(package_dir / filename)
    observed, counts = _identities(package_dir / filename)
    duplicates = sorted(identity for identity, count in counts.items() if count != 1)
    if observed != expected or duplicates:
        raise SemanticEvaluationError(f"{filename} identity mismatch: missing={sorted(expected - observed)}, extra={sorted(observed - expected)}, duplicates={duplicates}")
    if _metrics(summary) != {"total": total, "passed": total, "failed": 0, "errors": 0, "skipped": 0}:
        raise SemanticEvaluationError(f"{filename} is not exactly {total}/{total} clean: {_metrics(summary)}")
    if status.get("evidence_summary", {}).get(key) != _metrics(summary):
        raise SemanticEvaluationError(f"status.json metrics mismatch for {key}")
    return summary


def _assert_clean_report(path: Path) -> None:
    if not path.is_file():
        raise SemanticEvaluationError(f"Execution report missing: {path.name}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if "=== FAILURES ===" in text or ("=== SHORT TEST SUMMARY INFO ===" in text and "FAILED " in text):
        raise SemanticEvaluationError(f"Failed execution report: {path.name}")


def _assert_hash_dag(package_dir: Path) -> int:
    hashes = parse_hashes_sha256(package_dir / "hashes.sha256")
    disk = {path.name for path in package_dir.iterdir() if path.is_file() and path.name != "hashes.sha256"}
    if set(hashes) != disk:
        raise SemanticEvaluationError("hash DAG file set does not match evidence directory")
    for name, digest in hashes.items():
        if sha256_file(package_dir / name).lower() != digest.lower():
            raise SemanticEvaluationError(f"hash mismatch: {name}")
    return len(hashes)


class M2P2SemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p2"

    @property
    def target_package(self) -> str:
        return "M2-P2"

    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        if status_data.get("status") != "READY_FOR_REVIEW":
            raise SemanticEvaluationError("M2-P2 evidence must be READY_FOR_REVIEW")
        gates = status_data.get("gates", [])
        if {gate.get("gate_id") for gate in gates} != {f"GATE-P2-0{i}" for i in range(1, 7)} or any(gate.get("status") != "PASS" for gate in gates):
            raise SemanticEvaluationError("M2-P2 gates must be exactly GATE-P2-01..06 and PASS")

        p2 = _assert_suite(package_dir, "m2-p2-tests.xml", MANDATORY_P2_IDENTITIES, 11, status_data, "p2_tests")
        p1 = _assert_suite(package_dir, "m2-p1-regression.xml", MANDATORY_P1_IDENTITIES, 11, status_data, "p1_regression_tests")
        p0 = _assert_suite(package_dir, "m2-p0-regression.xml", FROZEN_P0_IDENTITIES, 33, status_data, "m2_p0_regression_tests")
        m1 = parse_junit_xml(package_dir / "m1-regression.xml")
        if _metrics(m1) != {"total": 93, "passed": 93, "failed": 0, "errors": 0, "skipped": 0} or status_data.get("evidence_summary", {}).get("m1_regression_tests") != _metrics(m1):
            raise SemanticEvaluationError("M1 regression is not exact 93/93 clean")
        for name in ("m2-p2-tests-report.txt", "m2-p1-regression-report.txt", "m2-p0-regression-report.txt", "m1-regression-report.txt"):
            _assert_clean_report(package_dir / name)

        runtime = json.loads((package_dir / "runtime-capability.json").read_text(encoding="utf-8"))
        required_runtime = {"python": "3.13.15", "psycopg": "3.3.5", "psycopg-pool": "3.3.1", "actual_pool_implementation": "psycopg_pool.ConnectionPool", "postgresql_server": "18.6", "createdb_prerequisite": True, "disposable_db_orphan_count": 0}
        if runtime.get("run_id") != status_data.get("run_id") or {key: runtime.get(key) for key in required_runtime} != required_runtime or status_data.get("runtime_capability") != runtime:
            raise SemanticEvaluationError("locked P2 runtime capability mismatch")
        secret = parse_secret_scan_json(package_dir / "secret-scan.json")
        if secret.get("run_id") != status_data.get("run_id") or secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0 or status_data.get("evidence_summary", {}).get("secret_scan_violations") != 0:
            raise SemanticEvaluationError("secret scan is not CLEAN")
        commands = [json.loads(line) for line in (package_dir / "commands.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        required = {"m2-p2-tests.xml", "m2-p2-tests-report.txt", "m2-p1-regression.xml", "m2-p1-regression-report.txt", "m2-p0-regression.xml", "m2-p0-regression-report.txt", "m1-regression.xml", "m1-regression-report.txt", "runtime-capability.json", "secret-scan.json"}
        produced = {artifact for record in commands for artifact in record.get("created_artifacts", [])}
        if not commands or any(record.get("run_id") != status_data.get("run_id") or record.get("exit_code") != 0 for record in commands) or not required <= produced:
            raise SemanticEvaluationError("commands provenance is incomplete or failing")
        provenance = verify_package_provenance(package_dir, status_data)
        return {"profile": self.profile_id, "p2_tests": p2, "p1_tests": p1, "p0_tests": p0, "m1_tests": m1, "provenance": provenance, "hashed_artifacts": _assert_hash_dag(package_dir), "semantic_verdict": "PASS"}
