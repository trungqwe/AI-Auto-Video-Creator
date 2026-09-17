"""Fail-closed semantic profile for immutable M2-P7B GREEN evidence."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from controlplane.infrastructure.evidence.evaluator import (
    PackageSemanticProfile, SemanticEvaluationError, parse_junit_xml,
    verify_package_provenance,
)
from controlplane.infrastructure.evidence.validator import parse_hashes_sha256, sha256_file


ROOT = Path(__file__).parents[4]
P7A_ACCEPTED = "6c3a52bde905ee5e71e12334da1873ed20f5c5db"
P7A_ORACLE = "tests/m2/test_p7a_control_api_security.py"
P7A_ORACLE_SHA = "63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035"
P7B_ORACLE = "tests/m2/test_p7b_sse_stream.py"
P7B_ORACLE_SHA = "d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738"
ORACLE_NAMES = (
    "test_tst_m2_p7b_000_stream_cursor_commit_order_concurrent_writers",
    "test_tst_m2_p7b_001_sse_stream_format_and_headers",
    "test_tst_m2_p7b_002_sse_reconnect_with_cursor_delivers_missed_events",
    "test_tst_m2_p7b_003_sse_cursor_expired_triggers_resync_required",
    "test_tst_m2_p7b_004_sse_session_workspace_isolation",
)
SUITES = {
    "p7b-oracle.xml": 5,
    "p7b-hardening.xml": 38,
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
PLAN_FILES = (
    "pre-index-absent-explain.json", "pre-index-resume-explain.json",
    "post-index-absent-explain.json", "post-index-resume-explain.json",
)
MIGRATION_FILES = (
    "index-catalog.json", "tracker-forward.json", "tracker-rollback.json",
    "tracker-reapply.json", "rollback-preservation.json",
)
SOURCE_TOOLING = (
    "src/controlplane/infrastructure/evidence/probe_p7b.py",
    "src/controlplane/infrastructure/evidence/profile_p7b.py",
    "src/controlplane/infrastructure/evidence/synthesizer_p7b.py",
)


def hardening_names(source: bytes) -> tuple[str, ...]:
    tree = ast.parse(source.decode("utf-8"))
    names = tuple(node.name for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name.startswith("test_h"))
    if len(names) != 38 or any(
        re.fullmatch(rf"test_h{index:02d}_[a-z0-9_]+", name) is None
        for index, name in enumerate(names, 1)
    ) or len(set(names)) != 38:
        raise SemanticEvaluationError("H01-H38 identity catalogue mismatch")
    return names


def _cases(directory: Path, filename: str) -> tuple[str, ...]:
    return tuple(case.attrib["name"] for case in ET.parse(directory / filename).iter("testcase"))


def _post_plan(raw: object, expected: int) -> None:
    if not isinstance(raw, list) or len(raw) != 1:
        raise SemanticEvaluationError("post-index EXPLAIN shape mismatch")
    plan = raw[0]["Plan"]
    scan = plan["Plans"][0]
    if (plan["Node Type"] != "Limit" or scan["Node Type"] != "Index Scan"
            or scan["Index Name"] != "cp_operation_stream_workspace_cursor_idx"
            or "workspace_id =" not in scan["Index Cond"]
            or "stream_event_id >" not in scan["Index Cond"]
            or scan.get("Rows Removed by Filter", 0) != 0
            or scan["Actual Rows"] != expected):
        raise SemanticEvaluationError("composite-index bounded plan mismatch")


class M2P7BImplementationSemanticProfile(PackageSemanticProfile):
    @property
    def profile_id(self) -> str:
        return "m2-p7b-implementation"

    @property
    def target_package(self) -> str:
        return "M2-P7B"

    def evaluate(self, directory: Path, status: dict[str, Any]) -> dict[str, Any]:
        if (status.get("status"), status.get("lifecycle")) != (
            "READY_FOR_REVIEW", "M2-P7B_IMPLEMENTATION_READY_FOR_REVIEW"
        ):
            raise SemanticEvaluationError("P7B GREEN lifecycle mismatch")
        source = status.get("source_commit_sha")
        if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{40}", source):
            raise SemanticEvaluationError("immutable source SHA missing")
        if subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"],
                          cwd=ROOT, capture_output=True).returncode:
            raise SemanticEvaluationError("source ancestry mismatch")
        for relative, expected in ((P7A_ORACLE, P7A_ORACLE_SHA),
                                   (P7B_ORACLE, P7B_ORACLE_SHA)):
            committed = subprocess.check_output(["git", "show", f"{source}:{relative}"], cwd=ROOT)
            if hashlib.sha256(committed).hexdigest() != expected:
                raise SemanticEvaluationError(f"accepted oracle drift: {relative}")
        if status.get("oracle_sha256") != P7B_ORACLE_SHA:
            raise SemanticEvaluationError("P7B oracle status mismatch")
        for relative in SOURCE_TOOLING:
            committed = subprocess.check_output(["git", "show", f"{source}:{relative}"], cwd=ROOT)
            if (ROOT / relative).read_bytes() != committed:
                raise SemanticEvaluationError("source/tooling differs from pin")
        for filename, expected in SUITES.items():
            result = parse_junit_xml(directory / filename)
            if (result.total, result.passed, result.failures, result.errors,
                    result.skipped) != (expected, expected, 0, 0, 0):
                raise SemanticEvaluationError(f"suite mismatch: {filename}")
        if _cases(directory, "p7b-oracle.xml") != ORACLE_NAMES:
            raise SemanticEvaluationError("P7B oracle testcase identities mismatch")
        committed_hardening = subprocess.check_output(
            ["git", "show", f"{source}:tests/m2/test_p7b_hardening.py"], cwd=ROOT)
        if _cases(directory, "p7b-hardening.xml") != hardening_names(committed_hardening):
            raise SemanticEvaluationError("P7B H01-H38 JUnit identity mismatch")
        runtime = json.loads((directory / "runtime-and-static.json").read_text(encoding="utf-8"))
        required = {
            "source_commit_sha": source, "python": "3.13.15",
            "psycopg": "3.3.5", "psycopg_pool": "3.3.1",
            "postgresql": "18.6", "createdb": True, "m2_orphan_count": 0,
            "uv_runtime_observed": "0.12.13", "uv_lock_version": "0.12.13",
            "unexpected_scope_paths": [], "source_scope_exact_pass": True,
            "source_scope_negative_probe_pass": True,
            "p3_append_body_only": True, "p7a_h16_body_only": True,
            "p7a_historical_source_sha": P7A_ACCEPTED,
            "p7a_behavioral_oracle_sha256": P7A_ORACLE_SHA,
            "p7b_behavioral_oracle_sha256": P7B_ORACLE_SHA,
            "application_to_infrastructure_imports": 0,
            "domain_to_application_imports": 0,
            "api_sse_infrastructure_imports": 0,
            "migration_runner_unchanged": True, "migration_0009_absent": True,
            "historical_evidence_preserved": True,
            "runtime_stream_writers": ["src/controlplane/infrastructure/db/projections/postgres.py"],
            "one_statement_fence_before_allocation": True,
            "migration_0008_exact_ddl": True,
        }
        if any(runtime.get(key) != value for key, value in required.items()):
            raise SemanticEvaluationError("runtime/static/scope mismatch")
        if runtime.get("p7a_hardening_sha256") != hashlib.sha256(subprocess.check_output(
            ["git", "show", f"{source}:tests/m2/test_p7a_hardening.py"], cwd=ROOT,
        )).hexdigest() or len(runtime.get("p7a_hardening_identities", [])) != 36:
            raise SemanticEvaluationError("P7A H16 compatibility provenance mismatch")
        catalog = json.loads((directory / "index-catalog.json").read_text(encoding="utf-8"))
        if (catalog.get("method"), catalog.get("unique"), catalog.get("keys"),
                catalog.get("key_count"), catalog.get("attribute_count"),
                catalog.get("no_predicate"), catalog.get("no_expression")) != (
            "btree", False, ["workspace_id", "stream_event_id"], 2, 2, True, True,
        ):
            raise SemanticEvaluationError("0008 index catalog mismatch")
        for filename, expected in (("tracker-forward.json", list(range(1, 9))),
                                   ("tracker-rollback.json", list(range(1, 8))),
                                   ("tracker-reapply.json", list(range(1, 9)))):
            if json.loads((directory / filename).read_text(encoding="utf-8")) != expected:
                raise SemanticEvaluationError(f"migration tracker mismatch: {filename}")
        preserved = json.loads((directory / "rollback-preservation.json").read_text(encoding="utf-8"))
        if preserved != {"stream_rows": 100000, "workspace_rows": 100,
                         "watermark_rows": 1, "p7a_auth_sessions_table": True,
                         "p7a_technical_details_table": True}:
            raise SemanticEvaluationError("targeted rollback preservation mismatch")
        _post_plan(json.loads((directory / "post-index-absent-explain.json").read_text(encoding="utf-8")), 0)
        _post_plan(json.loads((directory / "post-index-resume-explain.json").read_text(encoding="utf-8")), 100)
        pre = json.loads((directory / "pre-index-absent-explain.json").read_text(encoding="utf-8"))
        if pre[0]["Plan"]["Plans"][0]["Plans"][0].get("Rows Removed by Filter", 0) < 100000:
            raise SemanticEvaluationError("pre-index blocker not reproduced")
        quality = json.loads((directory / "quality-status.json").read_text(encoding="utf-8"))
        if any(quality.get(key) != "PASS" for key in
               ("ruff", "uv_lock_check", "wheel_build", "wheel_import")):
            raise SemanticEvaluationError("mandatory quality gate mismatch")
        if quality.get("mypy") not in {"PASS", "SKIP_UNAVAILABLE_NOT_IN_LOCK"}:
            raise SemanticEvaluationError("mypy policy mismatch")
        secret = json.loads((directory / "secret-scan.json").read_text(encoding="utf-8"))
        if secret.get("verdict") != "CLEAN" or secret.get("total_findings") != 0:
            raise SemanticEvaluationError("secret scan mismatch")
        records = [json.loads(line) for line in
                   (directory / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
        actual = [record for record in records if record.get("executed") is True]
        if any(not record.get("argv") or record.get("exit_code") != 0
               or record.get("source_commit_sha") != source for record in actual):
            raise SemanticEvaluationError("command provenance mismatch")
        if any(record.get("executed") is False and "argv" in record for record in records):
            raise SemanticEvaluationError("policy record contains fabricated argv")
        for record in actual:
            if any(not (directory / artifact).is_file()
                   for artifact in record.get("created_artifacts", [])):
                raise SemanticEvaluationError("command artifact missing")
        required_stages = {name.removesuffix(".xml") for name in SUITES}
        required_stages |= {"runtime-static-migration", "quality-ruff", "quality-lock",
                            "quality-build", "quality-wheel-import", "secret-scan",
                            "tamper-negative", "verify-only"}
        if not required_stages <= {record.get("stage") for record in records}:
            raise SemanticEvaluationError("command stages missing")
        if "EXPECTED_REJECTION=PASS" not in (directory / "negative-verifier-stdout.txt").read_text(encoding="utf-8"):
            raise SemanticEvaluationError("tamper-negative proof missing")
        provenance = verify_package_provenance(directory, status)
        hashes = parse_hashes_sha256(directory / "hashes.sha256")
        files = {path.name for path in directory.iterdir()
                 if path.is_file() and path.name != "hashes.sha256"}
        if set(hashes) != files or any(sha256_file(directory / name) != digest
                                      for name, digest in hashes.items()):
            raise SemanticEvaluationError("hash DAG mismatch")
        return {"profile": self.profile_id, "semantic_verdict": "PASS",
                "provenance": provenance, "hashed_artifacts": len(hashes)}
