"""Audit, integrity and gate enforcement tests for M1-P6 (TST-M1-P6-001..005)."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any, Dict
import pytest
from m1proof.evidence_manifest import (
    evaluate_milestone_gates,
    scan_secrets_in_directory,
    validate_manifest_artifacts,
    validate_manifest_schema,
)

def test_tst_m1_p6_001_manifest_schema_and_completeness_validation(sample_valid_manifest: Dict[str, Any]):
    """TST-M1-P6-001: Manifest schema rejects incomplete sections and missing mandatory fields."""
    # Case A: Manifest đầy đủ hợp lệ
    assert validate_manifest_schema(sample_valid_manifest) is True

    # Case B: Thiếu trường bắt buộc (ví dụ version_lock)
    invalid_manifest = dict(sample_valid_manifest)
    del invalid_manifest["version_lock"]
    with pytest.raises(ValueError, match="Missing mandatory field: version_lock"):
        validate_manifest_schema(invalid_manifest)

    # Case C: Thiếu một package bắt buộc trong packages
    invalid_pkg_manifest = dict(sample_valid_manifest)
    invalid_pkg_manifest["packages"] = dict(sample_valid_manifest["packages"])
    del invalid_pkg_manifest["packages"]["m1-p3"]
    with pytest.raises(ValueError, match="Missing required package: m1-p3"):
        validate_manifest_schema(invalid_pkg_manifest)


def test_tst_m1_p6_002_artifact_hash_tampering_and_missing_file_detection(tmp_path: Path):
    """TST-M1-P6-002: Detect modified evidence bytes or non-existent artifact files."""
    valid_file = tmp_path / "valid_artifact.txt"
    test_bytes = b"ORIGINAL_EVIDENCE_CONTENT"
    valid_file.write_bytes(test_bytes)
    original_hash = hashlib.sha256(test_bytes).hexdigest()

    manifest = {
        "artifacts": [
            {"path": str(valid_file), "sha256": original_hash},
        ]
    }

    # Ban đầu hợp lệ
    res = validate_manifest_artifacts(manifest, project_root=tmp_path)
    assert res["valid"] is True
    assert res["tampered"] == []
    assert res["missing"] == []

    # Giả lập can thiệp sửa đổi byte tệp (tampering)
    valid_file.write_bytes(b"TAMPERED_MODIFIED_CONTENT")
    res_tampered = validate_manifest_artifacts(manifest, project_root=tmp_path)
    assert res_tampered["valid"] is False
    assert len(res_tampered["tampered"]) == 1

    # Giả lập tệp bị xóa hoặc không tồn tại (missing)
    missing_manifest = {
        "artifacts": [
            {"path": str(tmp_path / "ghost_file.txt"), "sha256": original_hash},
        ]
    }
    res_missing = validate_manifest_artifacts(missing_manifest, project_root=tmp_path)
    assert res_missing["valid"] is False
    assert len(res_missing["missing"]) == 1


def test_tst_m1_p6_003_milestone_exit_rule_engine_gate_enforcement(sample_valid_manifest: Dict[str, Any]):
    """TST-M1-P6-003: Rule engine blocks M1 PASS if any package is incomplete, blocked, or failed."""
    # Case A: Mọi package P0..P5 đều PASS
    outcome = evaluate_milestone_gates(sample_valid_manifest)
    assert outcome["m1_status"] == "READY_FOR_USER_CHECKPOINT"

    # Case B: Có package bị BLOCKED_EXTERNAL (ví dụ P3)
    blocked_manifest = dict(sample_valid_manifest)
    blocked_manifest["packages"] = dict(sample_valid_manifest["packages"])
    blocked_manifest["packages"]["m1-p3"] = {"status": "BLOCKED_EXTERNAL", "evidence_files": []}

    outcome_blocked = evaluate_milestone_gates(blocked_manifest)
    assert outcome_blocked["m1_status"] == "BLOCKED_EXTERNAL"

    # Case C: Có package bị FAIL
    failed_manifest = dict(sample_valid_manifest)
    failed_manifest["packages"] = dict(sample_valid_manifest["packages"])
    failed_manifest["packages"]["m1-p2"] = {"status": "FAIL", "evidence_files": []}

    outcome_failed = evaluate_milestone_gates(failed_manifest)
    assert outcome_failed["m1_status"] == "FAILED"


def test_tst_m1_p6_004_scoped_gate_boundary_protection(sample_valid_manifest: Dict[str, Any]):
    """TST-M1-P6-004: Prohibit premature full PASS claim for G01, G04, or G07 within M1 scope."""
    # Thử gán G01 = PASS toàn phần trong M1 scope
    illegal_g01 = dict(sample_valid_manifest)
    illegal_g01["gates"] = dict(sample_valid_manifest["gates"])
    illegal_g01["gates"]["G01"] = "PASS"

    with pytest.raises(ValueError, match="G01 cannot claim full PASS in M1"):
        evaluate_milestone_gates(illegal_g01)

    # Thử gán G04 = PASS toàn phần trong M1 scope
    illegal_g04 = dict(sample_valid_manifest)
    illegal_g04["gates"] = dict(sample_valid_manifest["gates"])
    illegal_g04["gates"]["G04"] = "PASS"

    with pytest.raises(ValueError, match="G04 cannot claim full PASS in M1"):
        evaluate_milestone_gates(illegal_g04)


def test_tst_m1_p6_005_secret_and_canary_scanner_fail_closed(tmp_path: Path):
    """TST-M1-P6-005: Secret scanner detects canary tokens and fails closed."""
    clean_dir = tmp_path / "clean_evidence"
    clean_dir.mkdir()
    (clean_dir / "status.md").write_text("# Clean status report\nAll tests passed.", encoding="utf-8")

    # Thư mục sạch -> 0 phát hiện
    findings_clean = scan_secrets_in_directory(clean_dir)
    assert findings_clean == []

    # Tạo tệp chứa canary secret (ví dụ GitHub token hoặc OAuth token)
    dirty_dir = tmp_path / "dirty_evidence"
    dirty_dir.mkdir()
    (dirty_dir / "leaked_log.txt").write_text(
        "Error trace: user authenticated with ghp_1234567890abcdefghijklmnopqrstuvwxyz securely",
        encoding="utf-8"
    )

    findings_dirty = scan_secrets_in_directory(dirty_dir)
    assert len(findings_dirty) >= 1
    assert any("ghp_" in f["pattern"] or "github_token" in f["rule"] for f in findings_dirty)
