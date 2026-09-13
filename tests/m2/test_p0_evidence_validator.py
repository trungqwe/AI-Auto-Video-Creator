"""Tests for Evidence Validator (ADR-0001, ADR-0002, PCC-027, PCC-028).

Test oracle:
- Positive: Valid status.json and correct non-self-referential hashes.sha256 PASS.
- Negative: Tampered file content raises EvidenceValidationError.
- Negative: Self-referential hash in hashes.sha256 raises SelfReferentialHashError.
- Negative: Invalid schema_version or missing status.json fails closed.
- Negative: Gate failure with status PASS fails closed.
- Negative: Untracked extra file in evidence dir fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError,
    SelfReferentialHashError,
    sha256_file,
    validate_package_evidence,
)


def create_valid_evidence_fixture(target_dir: Path, package_id: str = "M2-P0") -> None:
    """Helper to generate a valid evidence package directory."""
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
                "evidence_files": ["commands.jsonl", "test_report.txt"],
            }
        ],
        "evidence_summary": {
            "total_tests": 10,
            "passed": 10,
        },
    }
    status_file = target_dir / "status.json"
    status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")

    commands_file = target_dir / "commands.jsonl"
    commands_file.write_text('{"command": "pytest", "exit_code": 0}\n', encoding="utf-8")

    report_file = target_dir / "test_report.txt"
    report_file.write_text("10 passed in 1.2s\n", encoding="utf-8")

    # Generate hashes.sha256 excluding itself
    hashes_content = []
    for f in sorted([status_file, commands_file, report_file]):
        h = sha256_file(f)
        hashes_content.append(f"{h}  {f.name}")

    hash_file = target_dir / "hashes.sha256"
    hash_file.write_text("\n".join(hashes_content) + "\n", encoding="utf-8")


def test_tst_m2_p0_002_evidence_validator_accepts_valid_package(tmp_path: Path) -> None:
    """Positive test: valid evidence package passes verification completely."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    report = validate_package_evidence(pkg_dir)
    assert report.is_valid is True
    assert report.package == "M2-P0"
    assert report.status == "PASS"
    assert len(report.verified_files) == 3


def test_tst_m2_p0_002_evidence_validator_rejects_tampered_hash(tmp_path: Path) -> None:
    """Negative test: tampering with any file must trigger hash mismatch error."""
    pkg_dir = tmp_path / "m2-p0"
    create_valid_evidence_fixture(pkg_dir)

    # Tamper with test_report.txt
    (pkg_dir / "test_report.txt").write_text("Tampered content!\n", encoding="utf-8")

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

    # Update hash for status.json so hash check doesn't trip first
    h = sha256_file(status_file)
    hash_file = pkg_dir / "hashes.sha256"
    lines = [line for line in hash_file.read_text(encoding="utf-8").splitlines() if not line.endswith("status.json")]
    lines.append(f"{h}  status.json")
    hash_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

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

    # Update hash
    h = sha256_file(status_file)
    hash_file = pkg_dir / "hashes.sha256"
    lines = [line for line in hash_file.read_text(encoding="utf-8").splitlines() if not line.endswith("status.json")]
    lines.append(f"{h}  status.json")
    hash_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

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


def test_tst_m2_p0_002_live_p0_evidence_is_valid() -> None:
    """Positive test: live M2-P0 evidence package is fully verified and authoritative."""
    repo_root = Path(__file__).parents[2]
    live_p0_evidence = repo_root / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p0"
    report = validate_package_evidence(live_p0_evidence)
    assert report.is_valid is True
    assert report.milestone == "M2"
    assert report.package == "M2-P0"
    assert report.status == "READY_FOR_REVIEW"
    assert len(report.gates) == 5
    for gate in report.gates:
        assert gate.status == "PASS"

