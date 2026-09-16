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
HARDENING_NAMES = tuple(f"test_h{number:02d}_" for number in range(1, 37))


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
        if len(hardening) != 36 or any(
            sum(name.startswith(prefix) for name in hardening) != 1
            for prefix in HARDENING_NAMES
        ):
            raise SemanticEvaluationError("H01-H36 identity mismatch")
        checks = json.loads((directory / "p7a-hardening.json").read_text(encoding="utf-8"))
        if (checks.get("verdict") != "PASS" or checks.get("count") != 36
                or tuple(checks.get("checks", {})) != hardening
                or not all(checks["checks"].values())):
            raise SemanticEvaluationError("P7A hardening catalogue mismatch")
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
        commands = [json.loads(line) for line in
                    (directory / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
        stages = {item.get("stage") for item in commands}
        required_stages = {name.removesuffix(".xml") for name in SUITES}
        required_stages.update({"runtime-static", "secret-scan", "hash-verification",
                                "negative-verifier-tamper-check", "verify-only"})
        if not required_stages <= stages or any(item.get("source_commit_sha") != source for item in commands):
            raise SemanticEvaluationError("command provenance mismatch")
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
