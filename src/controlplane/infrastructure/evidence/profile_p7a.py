"""Fail-closed semantic profile for exact-four M2-P7A Behavioral RED."""

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

ROOT = Path(__file__).parents[4]
ORACLE_PATH = "tests/m2/test_p7a_control_api_security.py"
ORACLE_SHA = "63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035"
P6_ORACLE_SHA = "42cf15e9b87e88728aa3d84f633bafc98bb8794c2c4a271d72b74c7258252517"
NAMES = (
    "test_tst_m2_p7a_001_host_header_spoofing_rejected",
    "test_tst_m2_p7a_002_csrf_mutation_without_token_rejected",
    "test_tst_m2_p7a_003_safe_technical_detail_ref_retrieval",
    "test_tst_m2_p7a_004_tls_handshake_verification",
)
MARKERS = (
    "P7A-001 Host validation unimplemented",
    "P7A-002 CSRF protection unimplemented",
    "P7A-003 technical-detail safety/storage unimplemented",
    "P7A-004 local TLS listener/handshake unimplemented",
)
SUITES = {
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


class M2P7ASemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p7a-red"

    @property
    def target_package(self) -> str:
        return "M2-P7A"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (status.get("status"), status.get("lifecycle"), status.get("implementation")) != (
            "READY_FOR_REVIEW", "M2-P7A_BEHAVIORAL_RED_READY_FOR_REVIEW", "LOCKED"
        ):
            raise SemanticEvaluationError("P7A lifecycle mismatch")
        source = status.get("source_commit_sha")
        if not isinstance(source, str) or subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT
        ).returncode:
            raise SemanticEvaluationError("source ancestry mismatch")
        committed_oracle = subprocess.check_output(
            ["git", "show", f"{source}:{ORACLE_PATH}"], cwd=ROOT
        )
        if hashlib.sha256(committed_oracle).hexdigest() != ORACLE_SHA or status.get("oracle_sha256") != ORACLE_SHA:
            raise SemanticEvaluationError("P7A oracle drift")
        collected = (directory / "collect-p7a-stdout.txt").read_text(encoding="utf-8")
        if "4 tests collected" not in collected or any(name not in collected for name in NAMES):
            raise SemanticEvaluationError("P7A collect mismatch")
        red = parse_junit_xml(directory / "red-p7a.xml")
        if (red.total, red.passed, red.failures, red.errors, red.skipped) != (4, 0, 4, 0, 0):
            raise SemanticEvaluationError("P7A RED count mismatch")
        cases = list(ET.parse(directory / "red-p7a.xml").iter("testcase"))
        if tuple(case.attrib["name"] for case in cases) != NAMES:
            raise SemanticEvaluationError("P7A identities mismatch")
        for case, marker in zip(cases, MARKERS, strict=True):
            failure = case.find("failure")
            if failure is None or "NotImplementedError" not in (
                failure.attrib.get("message", "") + (failure.text or "")
            ) or marker not in (failure.text or ""):
                raise SemanticEvaluationError(f"P7A capability marker mismatch: {case.attrib['name']}")
        for filename, count in SUITES.items():
            result = parse_junit_xml(directory / filename)
            if (result.total, result.passed, result.failures, result.errors, result.skipped) != (count, count, 0, 0, 0):
                raise SemanticEvaluationError(f"regression mismatch: {filename}")
        probes = json.loads((directory / "p6-hardening.json").read_text(encoding="utf-8"))
        if probes.get("verdict") != "PASS" or probes.get("count") != 18 or not all(probes.get("checks", {}).values()):
            raise SemanticEvaluationError("P6 hardening mismatch")
        runtime = json.loads((directory / "runtime-and-static.json").read_text(encoding="utf-8"))
        required = {
            "python": "3.13.15", "fastapi": "0.141.1", "uvicorn": "0.52.4", "httpx": "0.28.1",
            "psycopg": "3.3.5", "psycopg_pool": "3.3.1", "postgresql": "18.6",
            "createdb": True, "m2_orphan_count": 0, "migration_0007_absent": True,
            "migrations_0001_0006_pass": True, "migration_runner_unchanged": True,
            "p6_p5b_accepted_source_unchanged": True, "historical_evidence_preserved": True,
            "application_to_infrastructure_imports": 0, "domain_to_application_imports": 0,
            "p6_oracle_sha256": P6_ORACLE_SHA,
        }
        if any(runtime.get(key) != value for key, value in required.items()):
            raise SemanticEvaluationError("runtime/static mismatch")
        tls = json.loads((directory / "tls_handshake_evidence.json").read_text(encoding="utf-8"))
        if tls.get("capability") != "NOT_IMPLEMENTED" or tls.get("phase") != "RED" or tls.get("test_identity") != NAMES[3]:
            raise SemanticEvaluationError("TLS RED evidence mismatch")
        secret = json.loads((directory / "secret-scan.json").read_text(encoding="utf-8"))
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan mismatch")
        commands = [json.loads(line) for line in (directory / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
        required_stages = {"collect-p7a", "red-p7a", "p6-hardening", "secret-scan", "hash-verification", "verify-only", "negative-verifier-tamper-check"}
        required_stages.update(name.removesuffix(".xml") for name in SUITES)
        if not required_stages <= {item.get("stage") for item in commands} or any(item.get("source_commit_sha") != source for item in commands):
            raise SemanticEvaluationError("command provenance mismatch")
        if "EXPECTED_REJECTION=PASS" not in (directory / "negative-verifier-stdout.txt").read_text(encoding="utf-8"):
            raise SemanticEvaluationError("negative tamper proof missing")
        provenance = verify_package_provenance(directory, status)
        hashes = parse_hashes_sha256(directory / "hashes.sha256")
        disk = {path.name for path in directory.iterdir() if path.is_file() and path.name != "hashes.sha256"}
        if set(hashes) != disk or any(sha256_file(directory / name) != digest for name, digest in hashes.items()):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {"profile": self.profile_id, "semantic_verdict": "PASS", "provenance": provenance, "hashed_artifacts": len(hashes)}
