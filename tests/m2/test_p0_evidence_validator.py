"""Tests for Evidence Validator and Semantic Gate Evaluator (ADR-0001, ADR-0002, PCC-027, PCC-028).

Test oracle:
- Integrity Tier:
  - Positive: Valid status.json and correct non-self-referential hashes.sha256 PASS.
  - Negative: Tampered file content raises EvidenceValidationError.
  - Negative: Self-referential hash in hashes.sha256 raises SelfReferentialHashError.
  - Negative: Invalid schema_version or missing status.json fails closed.
  - Negative: Untracked extra file in evidence dir fails closed.
- Semantic Tier:
  - Negative: Failed tests in JUnit XML fail closed.
  - Negative: Skipped tests in JUnit XML fail closed.
  - Negative: M1 regression count != 93 fails closed.
  - Negative: Self-reported numbers in status.json differing from XML fail closed.
  - Negative: Prohibited failure text in reports fails closed.
  - Negative: Dirty secret scan fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from controlplane.infrastructure.evidence.evaluator import (
    SemanticEvaluationError,
    evaluate_package_semantics,
    parse_junit_xml,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError,
    SelfReferentialHashError,
    sha256_file,
    validate_package_evidence,
    validate_package_integrity,
)


def create_valid_evidence_fixture(target_dir: Path, package_id: str = "M2-P0") -> None:
    """Helper to generate a valid evidence package directory with both integrity and semantic artifacts."""
    target_dir.mkdir(parents=True, exist_ok=True)

    status_data = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": package_id,
        "status": "PASS",
        "gates": [
            {
                "gate_id": "GATE-01",
                "name": "Unit Tests",
                "status": "PASS",
                "evidence_files": ["commands.jsonl", "m2-p0-tests.xml", "m1-regression.xml", "secret-scan.json"],
            }
        ],
        "evidence_summary": {
            "m2_p0_tests": {
                "total": 10,
                "passed": 10,
                "failed": 0,
                "skipped": 0,
            },
            "m1_regression_tests": {
                "total": 93,
                "passed": 93,
                "failed": 0,
                "skipped": 0,
            },
            "secret_scan_violations": 0,
        },
    }
    status_file = target_dir / "status.json"
    status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")

    commands_file = target_dir / "commands.jsonl"
    commands_file.write_text('{"command": "pytest", "exit_code": 0}\n', encoding="utf-8")

    # M2-P0 JUnit XML
    p0_xml = target_dir / "m2-p0-tests.xml"
    p0_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites><testsuite name="m2-p0" tests="10" failures="0" errors="0" skipped="0">\n'
        '</testsuite></testsuites>\n',
        encoding="utf-8",
    )

    # M1 Regression JUnit XML
    m1_xml = target_dir / "m1-regression.xml"
    m1_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites><testsuite name="m1" tests="93" failures="0" errors="0" skipped="0">\n'
        '</testsuite></testsuites>\n',
        encoding="utf-8",
    )

    # Secret Scan JSON
    secret_file = target_dir / "secret-scan.json"
    secret_data = {
        "schema_version": "m2_secret_scan_v1",
        "verdict": "CLEAN",
        "total_files_scanned": 25,
        "total_findings": 0,
        "findings": [],
    }
    secret_file.write_text(json.dumps(secret_data, indent=2), encoding="utf-8")

    # Generate hashes.sha256 excluding itself
    hashes_content = []
    for f in sorted([status_file, commands_file, p0_xml, m1_xml, secret_file]):
        h = sha256_file(f)
        hashes_content.append(f"{h}  {f.name}")

    hash_file = target_dir / "hashes.sha256"
    hash_file.write_text("\n".join(hashes_content) + "\n", encoding="utf-8")


def rehash_fixture(target_dir: Path) -> None:
    """Helper to recalculate hashes.sha256 after editing fixture files."""
    hash_file = target_dir / "hashes.sha256"
    lines = []
    for f in sorted(target_dir.iterdir()):
        if f.is_file() and f.name != "hashes.sha256":
            lines.append(f"{sha256_file(f)}  {f.name}")
    hash_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_tst_m2_p0_002_evidence_validator_accepts_valid_package(tmp_path: Path) -> None:
    """Positive test: valid evidence package passes verification completely."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    report = validate_package_evidence(pkg_dir)
    assert report.is_valid is True
    assert report.package == "M2-P0"
    assert report.status == "PASS"
    assert len(report.verified_files) == 5
    assert report.semantic_summary is not None
    assert report.semantic_summary["semantic_verdict"] == "PASS"


def test_tst_m2_p0_002_evidence_validator_rejects_tampered_hash(tmp_path: Path) -> None:
    """Negative test: tampering with any file must trigger hash mismatch error."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    # Tamper with commands.jsonl
    (pkg_dir / "commands.jsonl").write_text("Tampered content!\n", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="Hash mismatch"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_evidence_validator_rejects_self_referential_hash(tmp_path: Path) -> None:
    """Negative test: hashes.sha256 containing itself must raise SelfReferentialHashError."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    # Append self-referential hash
    hash_file = pkg_dir / "hashes.sha256"
    hash_file.write_text(
        hash_file.read_text(encoding="utf-8") + "0123456789abcdef  hashes.sha256\n",
        encoding="utf-8",
    )

    with pytest.raises(SelfReferentialHashError, match="Self-referential hash detected"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_evidence_validator_rejects_schema_mismatch(tmp_path: Path) -> None:
    """Negative test: invalid schema_version fails closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    status_file = pkg_dir / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    data["schema_version"] = "invalid_v99"
    status_file.write_text(json.dumps(data), encoding="utf-8")
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Invalid schema_version"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_evidence_validator_rejects_failing_gate_with_pass_status(tmp_path: Path) -> None:
    """Negative test: status claimed PASS but gate is FAIL must fail closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    status_file = pkg_dir / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    data["gates"][0]["status"] = "FAIL"
    data["status"] = "PASS"
    status_file.write_text(json.dumps(data), encoding="utf-8")
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Cannot have status 'PASS' while gate 'GATE-01' is 'FAIL'"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_evidence_validator_rejects_untracked_extra_file(tmp_path: Path) -> None:
    """Negative test: untracked rogue file in evidence directory must fail closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    rogue = pkg_dir / "rogue_log.txt"
    rogue.write_text("I was not declared in hashes.sha256", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="Untracked evidence file found on disk"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_rejects_junit_failures(tmp_path: Path) -> None:
    """Negative test: JUnit XML containing test failures must fail closed even if rehashed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    # Tamper JUnit XML to have 1 failure
    (pkg_dir / "m2-p0-tests.xml").write_text(
        '<testsuite tests="10" failures="1" errors="0" skipped="0"></testsuite>',
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="failures"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_rejects_skipped_tests(tmp_path: Path) -> None:
    """Negative test: JUnit XML containing skipped tests must fail closed per zero-skipped policy."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    (pkg_dir / "m2-p0-tests.xml").write_text(
        '<testsuite tests="10" failures="0" errors="0" skipped="1"></testsuite>',
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="skipped"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_rejects_m1_count_mismatch(tmp_path: Path) -> None:
    """Negative test: M1 regression XML having != 93 tests must fail closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    (pkg_dir / "m1-regression.xml").write_text(
        '<testsuite tests="92" failures="0" errors="0" skipped="0"></testsuite>',
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="M1 regression suite total mismatch"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_rejects_dirty_secret_scan(tmp_path: Path) -> None:
    """Negative test: secret-scan.json with findings must fail closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    (pkg_dir / "secret-scan.json").write_text(
        json.dumps({
            "schema_version": "m2_secret_scan_v1",
            "verdict": "VIOLATIONS_DETECTED",
            "total_findings": 1,
            "findings": [{"pattern_name": "BEARER_TOKEN"}],
        }),
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Secret scan failed"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_rejects_failed_txt_reports(tmp_path: Path) -> None:
    """Negative test: presence of text reports containing failure banners must fail closed."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    (pkg_dir / "old-report.txt").write_text(
        "=== FAILURES ===\nFAILED tests/m2/test_sample.py::test_fail\n",
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Failed test summary detected"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_live_p0_evidence_is_valid() -> None:
    """Positive test: live M2-P0 evidence package is fully verified and authoritative."""
    repo_root = Path(__file__).parents[2]
    live_p0_evidence = repo_root / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p0"
    report = validate_package_evidence(live_p0_evidence, enforce_semantics=True)
    assert report.is_valid is True
    assert report.milestone == "M2"
    assert report.package == "M2-P0"
    assert report.status == "READY_FOR_REVIEW"
    assert len(report.gates) == 6
    for gate in report.gates:
        assert gate.status == "PASS"
    assert report.semantic_summary is not None
    assert report.semantic_summary["p0_tests"].failures == 0
    assert report.semantic_summary["p0_tests"].skipped == 0
    assert report.semantic_summary["m1_tests"].total == 93
    assert report.semantic_summary["m1_tests"].passed == 93


def test_tst_m2_p0_002_semantic_evaluator_rejects_unknown_package_or_profile(tmp_path: Path) -> None:
    """Negative test: unknown package or unregistered semantic profile fails closed (BLOCK)."""
    pkg_dir = tmp_path / "unknown-pkg"
    create_valid_evidence_fixture(pkg_dir, package_id="M2-P99")

    # Update status.json with unknown profile
    status_file = pkg_dir / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    data["package"] = "M2-P99"
    data["semantic_profile"] = "unregistered-profile-v99"
    status_file.write_text(json.dumps(data), encoding="utf-8")
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Unknown or unregistered semantic profile"):
        validate_package_evidence(pkg_dir)


def test_tst_m2_p0_002_semantic_evaluator_dispatches_registered_p1_sample_profile(tmp_path: Path) -> None:
    """Positive test: P1 extension point can register custom semantic profile without modifying validator core."""
    from controlplane.infrastructure.evidence.evaluator import (
        PackageSemanticProfile,
        register_semantic_profile,
    )

    class SampleM2P1Profile(PackageSemanticProfile):
        @property
        def profile_id(self) -> str:
            return "m2-p1"

        @property
        def target_package(self) -> str:
            return "M2-P1"

        def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
            p1_xml = package_dir / "m2-p1-tests.xml"
            if not p1_xml.is_file():
                raise SemanticEvaluationError(f"Missing P1 tests XML: {p1_xml.name}")
            summary = parse_junit_xml(p1_xml)
            if summary.failures > 0 or summary.errors > 0 or summary.skipped > 0:
                raise SemanticEvaluationError("P1 tests failed")
            return {
                "profile": "m2-p1",
                "p1_tests": summary,
                "semantic_verdict": "PASS",
            }

    # Register P1 sample profile via extension point
    register_semantic_profile(SampleM2P1Profile(), allow_override=True)

    # Create P1 evidence fixture
    pkg_dir = tmp_path / "m2-p1"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    status_data = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": "M2-P1",
        "semantic_profile": "m2-p1",
        "status": "PASS",
        "gates": [
            {
                "gate_id": "GATE-P1-01",
                "name": "Database Migrations",
                "status": "PASS",
                "evidence_files": ["m2-p1-tests.xml"],
            }
        ],
        "evidence_summary": {},
    }
    (pkg_dir / "status.json").write_text(json.dumps(status_data, indent=2), encoding="utf-8")
    (pkg_dir / "m2-p1-tests.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuite name="m2-p1" tests="5" failures="0" errors="0" skipped="0"></testsuite>',
        encoding="utf-8",
    )
    rehash_fixture(pkg_dir)

    report = validate_package_evidence(pkg_dir, enforce_semantics=True)
    assert report.is_valid is True
    assert report.package == "M2-P1"
    assert report.semantic_summary is not None
    assert report.semantic_summary["profile"] == "m2-p1"
    assert report.semantic_summary["semantic_verdict"] == "PASS"


def test_tst_m2_p0_002_semantic_evaluator_blocks_cross_package_profile_spoofing(tmp_path: Path) -> None:
    """Negative test: P1 package attempting to declare m2-p0 profile is strictly blocked."""
    pkg_dir = tmp_path / "m2-p1-spoof"
    create_valid_evidence_fixture(pkg_dir, package_id="M2-P1")

    # Tamper status.json to declare package M2-P1 but semantic_profile m2-p0
    status_file = pkg_dir / "status.json"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    data["package"] = "M2-P1"
    data["semantic_profile"] = "m2-p0"
    status_file.write_text(json.dumps(data), encoding="utf-8")
    rehash_fixture(pkg_dir)

    with pytest.raises(EvidenceValidationError, match="Cross-package profile spoofing blocked"):
        validate_package_evidence(pkg_dir)


