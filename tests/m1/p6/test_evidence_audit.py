"""Audit, integrity and gate enforcement tests for M1-P6 (TST-M1-P6-001..008)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Dict
import pytest
from m1proof.evidence_manifest import (
    build_m1_evidence_manifest,
    evaluate_milestone_gates,
    parse_package_status_from_evidence,
    scan_secrets_in_directory,
    validate_manifest_artifacts,
    validate_manifest_schema,
)

def test_tst_m1_p6_001_manifest_schema_and_completeness_validation(sample_valid_manifest: Dict[str, Any]):
    """TST-M1-P6-001: Manifest schema rejects incomplete sections and missing mandatory fields."""
    assert validate_manifest_schema(sample_valid_manifest) is True

    # Thiếu trường bắt buộc (ví dụ version_lock)
    invalid_manifest = dict(sample_valid_manifest)
    del invalid_manifest["version_lock"]
    with pytest.raises(ValueError, match="Missing mandatory field: version_lock"):
        validate_manifest_schema(invalid_manifest)

    # Thiếu một package bắt buộc trong packages
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

    # Can thiệp sửa đổi byte tệp (tampering)
    valid_file.write_bytes(b"TAMPERED_MODIFIED_CONTENT")
    res_tampered = validate_manifest_artifacts(manifest, project_root=tmp_path)
    assert res_tampered["valid"] is False
    assert len(res_tampered["tampered"]) == 1

    # Tệp bị xóa hoặc không tồn tại (missing)
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

    # Case C: Có package bị STOPPED
    stopped_manifest = dict(sample_valid_manifest)
    stopped_manifest["packages"] = dict(sample_valid_manifest["packages"])
    stopped_manifest["packages"]["m1-p4"] = {"status": "STOPPED", "evidence_files": []}
    outcome_stopped = evaluate_milestone_gates(stopped_manifest)
    assert outcome_stopped["m1_status"] == "CORRECTION_REQUIRED"

    # Case D: Có package bị FAIL
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

    findings_clean = scan_secrets_in_directory(clean_dir)
    assert findings_clean == []

    dirty_dir = tmp_path / "dirty_evidence"
    dirty_dir.mkdir()
    (dirty_dir / "leaked_log.txt").write_text(
        "Error trace: user authenticated with ghp_1234567890abcdefghijklmnopqrstuvwxyz securely",
        encoding="utf-8"
    )

    findings_dirty = scan_secrets_in_directory(dirty_dir)
    assert len(findings_dirty) >= 1
    assert any("ghp_" in f["pattern"] or "github_token" in f["rule"] for f in findings_dirty)


def test_tst_m1_p6_006_fail_closed_package_status_parser(tmp_path: Path):
    """TST-M1-P6-006: Fail-closed parsing of status.md without hard-coding PASS."""
    # Case A: status.md chứa PASS
    pkg_dir = tmp_path / "pkg_pass"
    pkg_dir.mkdir()
    (pkg_dir / "status.md").write_text("# Status\nTrạng thái: PASS\nAll green.", encoding="utf-8")
    status = parse_package_status_from_evidence(pkg_dir)
    assert status == "PASS"

    # Case B: status.md chứa STOPPED
    pkg_stopped = tmp_path / "pkg_stopped"
    pkg_stopped.mkdir()
    (pkg_stopped / "status.md").write_text("# Status\nTrạng thái: STOPPED\nDependency missing.", encoding="utf-8")
    assert parse_package_status_from_evidence(pkg_stopped) == "STOPPED"

    # Case C: Thiếu status.md -> Fail closed
    pkg_empty = tmp_path / "pkg_empty"
    pkg_empty.mkdir()
    assert parse_package_status_from_evidence(pkg_empty) == "MISSING_STATUS_RECORD"


def test_tst_m1_p6_007_missing_mandatory_evidence_blocks_ready(tmp_path: Path):
    """TST-M1-P6-007: Missing required evidence files (commands.jsonl, hashes.sha256, etc) rejects PASS."""
    fake_root = tmp_path / "repo"
    evidence_dir = fake_root / "docs" / "milestones" / "m1-proof" / "evidence"
    for pkg in ["m1-p0", "m1-p1", "m1-p2", "m1-p3", "m1-p4", "m1-p5"]:
        pdir = evidence_dir / pkg
        pdir.mkdir(parents=True)
        (pdir / "status.md").write_text("Trạng thái: PASS", encoding="utf-8")
        (pdir / "commands.jsonl").write_text("{}", encoding="utf-8")
        (pdir / "hashes.sha256").write_text("hash  status.md", encoding="utf-8")
        (pdir / "red-observations.md").write_text("RED", encoding="utf-8")

    # Tạo file uv.lock giả lập
    (fake_root / "uv.lock").write_text("uv_lock_test_content", encoding="utf-8")

    # Khi đầy đủ -> builder parse ra PASS
    manifest = build_m1_evidence_manifest(fake_root)
    assert manifest["packages"]["m1-p1"]["status"] == "PASS"

    # Xóa file bắt buộc hashes.sha256 của P1 -> Status chuyển sang MISSING_REQUIRED_EVIDENCE
    (evidence_dir / "m1-p1" / "hashes.sha256").unlink()
    manifest_broken = build_m1_evidence_manifest(fake_root)
    assert "MISSING_REQUIRED_EVIDENCE" in manifest_broken["packages"]["m1-p1"]["status"]

    outcome = evaluate_milestone_gates(manifest_broken)
    assert outcome["m1_status"] != "READY_FOR_USER_CHECKPOINT"


def test_tst_m1_p6_008_capability_evidence_fail_closed(tmp_path: Path):
    """TST-M1-P6-008 (R4-04):
    Manifest builder and gate engine must enforce machine-readable capability evidence:
    - REQUIRED_M1_PACKAGES must explicitly include m1-p6.
    - P2 requires temporal_server_evidence.json.
    - P3 requires drive_e3_evidence.json.
    - evidence_classification['m1-p3'] must not claim E3 without drive_e3_evidence.json.
    """
    from m1proof.evidence_manifest import REQUIRED_M1_PACKAGES

    # 1. m1-p6 must be a required milestone package
    assert "m1-p6" in REQUIRED_M1_PACKAGES

    fake_root = tmp_path / "repo_cap"
    evidence_dir = fake_root / "docs" / "milestones" / "m1-proof" / "evidence"
    for pkg in REQUIRED_M1_PACKAGES:
        pdir = evidence_dir / pkg
        pdir.mkdir(parents=True)
        (pdir / "status.md").write_text("Trạng thái: PASS", encoding="utf-8")
        (pdir / "commands.jsonl").write_text("{}", encoding="utf-8")
        (pdir / "hashes.sha256").write_text("hash  status.md", encoding="utf-8")
        (pdir / "red-observations.md").write_text("RED", encoding="utf-8")

    (evidence_dir / "m1-p0" / "bootstrap.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p0" / "environment.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p5" / "compatibility_matrix.json").write_text("{}", encoding="utf-8")
    (fake_root / "uv.lock").write_text("uv_lock_test_content", encoding="utf-8")

    # Khi thiếu temporal_server_evidence.json ở P2 -> Builder báo CAPABILITY_EVIDENCE_MISSING
    manifest = build_m1_evidence_manifest(fake_root)
    assert "CAPABILITY_EVIDENCE_MISSING" in manifest["packages"]["m1-p2"]["status"]
    assert "temporal_server_evidence.json" in manifest["packages"]["m1-p2"]["status"]

    # evidence_classification không được claim E3 nếu thiếu drive_e3_evidence.json
    assert manifest["evidence_classification"]["m1-p3"] != "E3"


def test_tst_m1_p6_009_semantic_capability_validation(tmp_path: Path):
    """TST-M1-P6-009 (R5-04):
    Validator phải kiểm tra sâu ngữ nghĩa machine-readable của capability evidence:
    - P3 không được cấp E3 nếu process_isolated != True hoặc broker_pid == desktop_pid hoặc secure_storage_verified != True.
    - P5 matrix phải bị từ chối nếu có bất kỳ runtime nào FAIL, UNAVAILABLE hoặc null.
    """
    import json
    from m1proof.evidence_manifest import REQUIRED_M1_PACKAGES

    fake_root = tmp_path / "repo_semantic"
    evidence_dir = fake_root / "docs" / "milestones" / "m1-proof" / "evidence"
    for pkg in REQUIRED_M1_PACKAGES:
        pdir = evidence_dir / pkg
        pdir.mkdir(parents=True)
        (pdir / "status.md").write_text("Trạng thái: PASS", encoding="utf-8")
        (pdir / "commands.jsonl").write_text("{}", encoding="utf-8")
        (pdir / "hashes.sha256").write_text("hash  status.md", encoding="utf-8")
        (pdir / "red-observations.md").write_text("RED", encoding="utf-8")

    (fake_root / "uv.lock").write_text("uv_lock_test_content", encoding="utf-8")
    (evidence_dir / "m1-p0" / "bootstrap.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p0" / "environment.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p2" / "temporal_server_evidence.json").write_text(
        json.dumps({"server_version": "1.31.2", "binary_verified": True, "grpc_ready": True}),
        encoding="utf-8",
    )

    # 1. P3 Capability: Vi phạm process isolation (broker_pid == desktop_pid)
    bad_p3_evidence = {
        "status": "PASS_E3_LIVE",
        "sha256_verified": True,
        "process_isolated": False,  # Vi phạm!
        "broker_pid": 1234,
        "desktop_pid": 1234,       # Vi phạm!
        "secure_storage_verified": True,
    }
    (evidence_dir / "m1-p3" / "drive_e3_evidence.json").write_text(
        json.dumps(bad_p3_evidence), encoding="utf-8"
    )

    valid_matrix = {
        "overall_result": "PASS",
        "runtimes": {
            "cpython": {"result": "PASS", "observed": "3.13.15"},
            "postgresql": {"result": "PASS", "observed": "18.6"},
        }
    }
    (evidence_dir / "m1-p5" / "compatibility_matrix.json").write_text(
        json.dumps(valid_matrix), encoding="utf-8"
    )

    manifest1 = build_m1_evidence_manifest(fake_root)
    # Phải từ chối E3 và đánh dấu semantic fail
    assert "E3" not in manifest1["evidence_classification"]["m1-p3"]
    assert "SEMANTIC" in manifest1["packages"]["m1-p3"]["status"]

    # 2. P5 Capability: Ma trận có runtime bị FAIL
    bad_matrix = {
        "overall_result": "FAIL",
        "runtimes": {
            "cpython": {"result": "PASS", "observed": "3.13.15"},
            "postgresql": {"result": "FAIL", "observed": None},  # DB unreachable
        }
    }
    (evidence_dir / "m1-p5" / "compatibility_matrix.json").write_text(
        json.dumps(bad_matrix), encoding="utf-8"
    )

    manifest2 = build_m1_evidence_manifest(fake_root)
    assert "SEMANTIC" in manifest2["packages"]["m1-p5"]["status"]
    outcome = evaluate_milestone_gates(manifest2)
    assert outcome["m1_status"] != "READY_FOR_USER_CHECKPOINT"


def test_tst_m1_p6_010_semantic_capability_negative_fields(tmp_path: Path):
    """TST-M1-P6-010 (R5.1):
    Kiểm tra negative validation từng trường machine-readable trong drive_e3_evidence.json:
    - desktop_vault_access != False
    - broker_owns_oauth_provisioning != True
    - desktop_refresh_token_retained != False
    - encryption_method != 'WINDOWS_DPAPI'
    - broker_boundary != 'HTTP_IPC_SUBPROCESS_BOUNDARY'
    Mỗi trường vi phạm đều phải khiến M1 không thể READY_FOR_USER_CHECKPOINT.
    """
    import json
    from m1proof.evidence_manifest import REQUIRED_M1_PACKAGES

    fake_root = tmp_path / "repo_neg_fields"
    evidence_dir = fake_root / "docs" / "milestones" / "m1-proof" / "evidence"
    for pkg in REQUIRED_M1_PACKAGES:
        pdir = evidence_dir / pkg
        pdir.mkdir(parents=True)
        (pdir / "status.md").write_text("Trạng thái: PASS", encoding="utf-8")
        (pdir / "commands.jsonl").write_text("{}", encoding="utf-8")
        (pdir / "hashes.sha256").write_text("hash  status.md", encoding="utf-8")
        (pdir / "red-observations.md").write_text("RED", encoding="utf-8")

    (fake_root / "uv.lock").write_text("uv_lock_test_content", encoding="utf-8")
    (evidence_dir / "m1-p0" / "bootstrap.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p0" / "environment.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "m1-p2" / "temporal_server_evidence.json").write_text(
        json.dumps({"server_version": "1.31.2", "binary_verified": True, "grpc_ready": True}),
        encoding="utf-8",
    )
    (evidence_dir / "m1-p5" / "compatibility_matrix.json").write_text(
        json.dumps({
            "overall_result": "PASS",
            "runtimes": {
                "cpython": {"result": "PASS", "observed": "3.13.15"},
                "postgresql": {"result": "PASS", "observed": "18.6"},
            }
        }),
        encoding="utf-8",
    )

    valid_base = {
        "status": "PASS_E3_LIVE",
        "sha256_verified": True,
        "process_isolated": True,
        "broker_pid": 49000,
        "desktop_pid": 20000,
        "broker_owns_oauth_provisioning": True,
        "desktop_vault_access": False,
        "desktop_refresh_token_retained": False,
        "secure_storage_verified": True,
        "encryption_method": "WINDOWS_DPAPI",
        "broker_boundary": "HTTP_IPC_SUBPROCESS_BOUNDARY",
    }

    # Negative test mutations
    mutations = [
        {"desktop_vault_access": True},
        {"broker_owns_oauth_provisioning": False},
        {"desktop_refresh_token_retained": True},
        {"encryption_method": "PLAINTEXT"},
        {"broker_boundary": "THREAD_CONTEXT"},
    ]

    for mut in mutations:
        bad_evidence = dict(valid_base)
        bad_evidence.update(mut)
        (evidence_dir / "m1-p3" / "drive_e3_evidence.json").write_text(
            json.dumps(bad_evidence), encoding="utf-8"
        )
        manifest = build_m1_evidence_manifest(fake_root)
        field_name = list(mut.keys())[0]
        assert "E3" not in manifest["evidence_classification"]["m1-p3"], f"Failed to reject invalid {field_name}"
        assert "SEMANTIC" in manifest["packages"]["m1-p3"]["status"], f"Status not SEMANTIC for invalid {field_name}"
        outcome = evaluate_milestone_gates(manifest)
        assert outcome["m1_status"] != "READY_FOR_USER_CHECKPOINT", f"Gate did not reject invalid {field_name}"

