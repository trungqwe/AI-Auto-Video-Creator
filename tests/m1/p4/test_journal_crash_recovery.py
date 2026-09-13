"""Tests for crash recovery and lost-ACK reconciliation in local journal (TST-M1-P4-001..003)."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from m1proof.local_journal import (
    AtomicFileWriter,
    LocalJournalDB,
    LocalRecoveryEngine,
)

def test_tst_m1_p4_001_crash_after_artifact_complete_resends_operation(
    staging_env: dict[str, Path],
    journal_db: LocalJournalDB,
    cloud_verifier: Any,
):
    """TST-M1-P4-001: Crash after local artifact completes before receipt ACK; restart resends operation."""
    writer = AtomicFileWriter()
    target_file = staging_env["staging"] / "artifact_p4_001.mp4"
    test_data = b"M1_P4_VIDEO_ARTIFACT_PAYLOAD_FOR_CRASH_TEST_001"
    expected_hash = hashlib.sha256(test_data).hexdigest()

    # 1. Ghi file hoàn tất vào local
    size, actual_hash = writer.write_file_atomic(target_file, test_data, expected_hash)
    assert size == len(test_data)
    assert actual_hash == expected_hash

    # 2. Ghi journal entry ở trạng thái COMPLETED_LOCALLY (mô phỏng tiến trình crash trước khi gửi lên cloud)
    entry_id = journal_db.record_entry(
        operation_key="op_crash_resend_001",
        artifact_id="art_001",
        version_hash=expected_hash,
        local_path=str(target_file),
        stage="RENDER",
        recovery_epoch=1,
        generation=1,
        status="COMPLETED_LOCALLY",
    )

    # 3. Khởi động lại engine và thực hiện startup reconciliation
    engine = LocalRecoveryEngine(journal_db, cloud_verifier, active_epoch=1)
    reconcile_result = engine.reconcile_startup()

    # Oracle: phát hiện entry cần gửi lại, file trên đĩa hợp lệ, không tái tạo lại artifact
    assert "pending_resend" in reconcile_result
    resend_keys = [e["operation_key"] for e in reconcile_result["pending_resend"]]
    assert "op_crash_resend_001" in resend_keys
    assert reconcile_result["corrupt_or_missing"] == []


def test_tst_m1_p4_002_crash_during_write_or_rename_rejects_partial_byte(
    staging_env: dict[str, Path],
):
    """TST-M1-P4-002: Crash or failure during write/rename rejects partial byte; does not promote to complete."""
    writer = AtomicFileWriter()
    target_file = staging_env["staging"] / "artifact_p4_002.mp4"
    valid_data = b"M1_P4_COMPLETE_PAYLOAD_002"
    valid_hash = hashlib.sha256(valid_data).hexdigest()

    # Thử ghi dữ liệu không khớp expected_hash (giả lập partial byte bị corrupt hoặc cắt ngắn)
    corrupted_data = b"M1_P4_PARTIAL"
    with pytest.raises(ValueError, match="Hash mismatch"):
        writer.write_file_atomic(target_file, corrupted_data, expected_hash=valid_hash)

    # Oracle: file đích không được tạo hoặc không chứa partial data
    assert not target_file.exists(), "Target file must not exist if atomic write fails!"

    # Không để sót lại tệp tạm không được dọn dẹp
    temp_files = list(staging_env["staging"].glob("*.tmp"))
    assert len(temp_files) == 0, "Dangling .tmp files should be cleaned up on failure!"


def test_tst_m1_p4_003_lost_ack_reconciles_existing_cloud_receipt(
    staging_env: dict[str, Path],
    journal_db: LocalJournalDB,
    cloud_verifier: Any,
):
    """TST-M1-P4-003: Lost ACK after cloud commit reconciles existing receipt without duplicate commit."""
    writer = AtomicFileWriter()
    target_file = staging_env["staging"] / "artifact_p4_003.mp4"
    test_data = b"M1_P4_PAYLOAD_FOR_LOST_ACK_TEST_003"
    expected_hash = hashlib.sha256(test_data).hexdigest()

    writer.write_file_atomic(target_file, test_data, expected_hash)

    op_key = "op_lost_ack_003"
    entry_id = journal_db.record_entry(
        operation_key=op_key,
        artifact_id="art_003",
        version_hash=expected_hash,
        local_path=str(target_file),
        stage="UPLOAD",
        recovery_epoch=1,
        generation=1,
        status="SUBMITTED",
    )

    # Cloud thực tế đã commit thành công và có receipt P1
    cloud_verifier.register_receipt(
        operation_key=op_key,
        status="COMMITTED",
        receipt_id="rcpt_cloud_003",
        artifact_id="art_003",
    )

    # Khởi động engine để đối soát
    engine = LocalRecoveryEngine(journal_db, cloud_verifier, active_epoch=1)
    reconcile_result = engine.reconcile_startup()

    # Oracle: Phát hiện cloud đã commit, chuyển journal sang COMMITTED_ON_CLOUD
    # Không đưa vào pending_resend (không lặp lại mutation)
    assert op_key in [e["operation_key"] for e in reconcile_result["reconciled_with_cloud"]]
    updated_entry = journal_db.get_entry(entry_id)
    assert updated_entry["status"] == "COMMITTED_ON_CLOUD"
