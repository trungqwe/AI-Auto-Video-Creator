"""Fail-closed semantic profile for the M2-P3 closure package."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from controlplane.infrastructure.evidence.evaluator import PackageSemanticProfile, SemanticEvaluationError, parse_junit_xml
from controlplane.infrastructure.evidence.profile_p1 import FROZEN_P0_IDENTITIES, MANDATORY_P1_IDENTITIES
from controlplane.infrastructure.evidence.profile_p2 import MANDATORY_P2_IDENTITIES
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file

P3_FILE = "tests/m2/test_p3_outbox_and_projections.py"
P3_NAMES = tuple(f"test_tst_m2_p3_{index:03d}_{suffix}" for index, suffix in ((1,"production_0003_forward_rollback_and_schema_constraints"),(2,"business_mutation_and_outbox_atomic_commit_rollback"),(3,"at_least_once_dispatch_crash_before_published_ack_redispatch"),(4,"consumer_deduplicates_same_event_id"),(5,"concurrent_consumers_same_event_exactly_one_logical_effect"),(6,"checkpoint_projection_atomic_rollback"),(7,"unsupported_schema_durably_quarantined"),(8,"aggregate_revision_gap_and_out_of_order_blocked"),(9,"stale_recovery_epoch_quarantined"),(10,"operation_stream_monotonic_cursor_under_concurrency"),(11,"operation_stream_safe_projection_and_payload_policy")))
MANDATORY_P3_IDENTITIES = frozenset(f"{P3_FILE}::{name}" for name in P3_NAMES)

def _metrics(path: Path) -> dict[str, int]:
    summary = parse_junit_xml(path)
    return {"total": summary.total, "passed": summary.passed, "failed": summary.failures, "errors": summary.errors, "skipped": summary.skipped}

def _identities(path: Path) -> set[str]:
    import xml.etree.ElementTree as ET
    identities: set[str] = set()
    for case in ET.parse(path).iter("testcase"):
        source = case.attrib.get("file") or case.attrib.get("classname", "")
        source = source.replace("\\", "/")
        if "/" not in source:
            source = source.replace(".", "/") + ("" if source.endswith(".py") else ".py")
        identities.add(f"{source}::{case.attrib['name']}")
    return identities

class M2P3SemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str: return "m2-p3"
    @property
    def target_package(self) -> str: return "M2-P3"
    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        if status_data.get("status") != "READY_FOR_REVIEW": raise SemanticEvaluationError("P3 evidence status is not review-ready")
        gates = status_data.get("gates", [])
        if {gate.get("gate_id") for gate in gates} != {f"GATE-P3-0{i}" for i in range(1, 7)} or any(gate.get("status") != "PASS" for gate in gates):
            raise SemanticEvaluationError("P3 gates must be exactly GATE-P3-01..06 and PASS")
        expected = {"p3_tests": ("m2-p3-tests.xml", MANDATORY_P3_IDENTITIES, 11), "p2_regression_tests": ("m2-p2-regression.xml", MANDATORY_P2_IDENTITIES, 11), "p1_regression_tests": ("m2-p1-regression.xml", MANDATORY_P1_IDENTITIES, 11), "m2_p0_regression_tests": ("m2-p0-regression.xml", FROZEN_P0_IDENTITIES, 33)}
        for key, (name, identities, total) in expected.items():
            if _metrics(package_dir / name) != {"total": total, "passed": total, "failed": 0, "errors": 0, "skipped": 0}: raise SemanticEvaluationError(f"{name} not clean")
            if _identities(package_dir / name) != identities: raise SemanticEvaluationError(f"{name} identity mismatch")
            if status_data["evidence_summary"].get(key) != _metrics(package_dir / name): raise SemanticEvaluationError(f"{name} summary mismatch")
        if _metrics(package_dir / "m1-regression.xml") != {"total":93,"passed":93,"failed":0,"errors":0,"skipped":0} or status_data["evidence_summary"].get("m1_regression_tests") != _metrics(package_dir / "m1-regression.xml"): raise SemanticEvaluationError("M1 not exact 93/93")
        runtime = json.loads((package_dir / "runtime-capability.json").read_text())
        expected_runtime = {"python":"3.13.15","psycopg":"3.3.5","psycopg-pool":"3.3.1","actual_pool_implementation":"psycopg_pool.ConnectionPool","postgresql_server":"18.6","createdb_prerequisite":True,"disposable_db_orphan_count":0}
        if runtime.get("run_id") != status_data.get("run_id") or {key: runtime.get(key) for key in expected_runtime} != expected_runtime: raise SemanticEvaluationError("runtime mismatch")
        secret = json.loads((package_dir / "secret-scan.json").read_text())
        if secret.get("run_id") != status_data.get("run_id") or secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0: raise SemanticEvaluationError("secret scan is not CLEAN")
        commands = [json.loads(line) for line in (package_dir / "commands.jsonl").read_text().splitlines() if line.strip()]
        if len(commands) != 5 or any(command.get("run_id") != status_data.get("run_id") or command.get("exit_code") != 0 for command in commands): raise SemanticEvaluationError("command provenance is incomplete")
        hashes = parse_hashes_sha256(package_dir / "hashes.sha256")
        files = {p.name for p in package_dir.iterdir() if p.is_file() and p.name != "hashes.sha256"}
        if set(hashes) != files or any(sha256_file(package_dir / name) != digest for name, digest in hashes.items()): raise SemanticEvaluationError("hash DAG mismatch")
        return {"profile": self.profile_id, "semantic_verdict": "PASS", "hashed_artifacts": len(hashes)}
