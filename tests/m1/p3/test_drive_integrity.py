"""TST-M1-P3-003 & TST-M1-P3-004: Drive artifact integrity, byte hash verification, and session reconciliation."""
import hashlib
import pytest
from m1proof.drive_adapter import DriveStorageAdapter

def test_tst_m1_p3_003_byte_integrity_and_sha256_hash_verification():
    """TST-M1-P3-003:
    File cùng tên nhưng byte khác nhau hoặc hash không khớp bắt buộc bị từ chối;
    Không bao giờ nhận artifact là hợp lệ nếu chưa verify đúng byte size và SHA-256.
    """
    adapter = DriveStorageAdapter()
    valid_content = b"GENUINE_ENCODED_VIDEO_PAYLOAD_V1"
    corrupt_content = b"TAMPERED_OR_CORRUPT_VIDEO_PAYLOAD_V2"
    
    expected_size = len(valid_content)
    expected_sha256 = hashlib.sha256(valid_content).hexdigest()

    # Case A: Nội dung khớp hoàn hảo -> PASS
    is_valid = adapter.verify_byte_integrity(
        actual_bytes=valid_content,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
    )
    assert is_valid is True

    # Case B: Nội dung bị lệch mã băm (dù tên tệp có thể giống nhau) -> FAIL
    is_corrupted = adapter.verify_byte_integrity(
        actual_bytes=corrupt_content,
        expected_size=len(corrupt_content),
        expected_sha256=expected_sha256,  # Mong đợi hash của file gốc
    )
    assert is_corrupted is False

    # Case C: Kích thước byte sai lệch -> FAIL
    is_wrong_size = adapter.verify_byte_integrity(
        actual_bytes=valid_content,
        expected_size=expected_size + 10,
        expected_sha256=expected_sha256,
    )
    assert is_wrong_size is False


def test_tst_m1_p3_004_session_expired_or_conflict_reconciliation():
    """TST-M1-P3-004:
    Khi gặp xung đột ID (409 Conflict) hoặc Resumable Session hết hạn (410 Gone):
    - Nếu file trên Drive đã có đúng hash mong đợi -> RECONCILED_MATCH (tận dụng file hiện có).
    - Nếu file trên Drive khác hash -> FATAL_ID_MISMATCH (không ghi đè mù quáng).
    """
    adapter = DriveStorageAdapter()
    expected_bytes = b"MATCHING_PAYLOAD_123"
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    mismatched_bytes = b"DIFFERENT_PAYLOAD_456"

    # Case 1: Xung đột ID nhưng file đã tồn tại trên Drive khớp đúng hash của attempt
    reconcile_match = adapter.reconcile_conflict_or_timeout(
        existing_file_bytes=expected_bytes,
        expected_sha256=expected_hash,
    )
    assert reconcile_match == "RECONCILED_EXISTING_MATCH"

    # Case 2: Xung đột ID nhưng file trên Drive lại mang nội dung khác
    reconcile_mismatch = adapter.reconcile_conflict_or_timeout(
        existing_file_bytes=mismatched_bytes,
        expected_sha256=expected_hash,
    )
    assert reconcile_mismatch == "FATAL_ID_MISMATCH"
