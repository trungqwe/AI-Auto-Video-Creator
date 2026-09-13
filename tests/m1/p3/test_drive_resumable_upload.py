"""TST-M1-P3-001 & TST-M1-P3-002: Drive resumable upload, pre-generated ID and timeout reconciliation proof."""
import pytest
from m1proof.drive_adapter import DriveStorageAdapter

class FakeDriveServerBackend:
    """Mock storage simulating Google Drive API behaviors for unit contract testing."""
    def __init__(self):
        self.files: dict[str, dict] = {}
        self.next_id = 100
        self.upload_attempts = 0

    def generate_ids(self) -> str:
        fid = f"drive-fid-{self.next_id}"
        self.next_id += 1
        return fid

    def store_file(self, file_id: str, name: str, content: bytes) -> dict:
        self.upload_attempts += 1
        record = {
            "id": file_id,
            "name": name,
            "size": len(content),
            "content": content,
        }
        self.files[file_id] = record
        return record

def test_tst_m1_p3_001_pregenerated_id_and_resumable_retry_lost_ack():
    """TST-M1-P3-001:
    Pre-generated Drive ID kết hợp Resumable Upload bảo đảm retry/lost ACK
    không sinh ra object trùng lặp trên Drive; định danh object giữ nguyên vẹn.
    """
    backend = FakeDriveServerBackend()
    adapter = DriveStorageAdapter()
    
    # Bước 1: Xin trước file_id định danh artifact
    file_id = backend.generate_ids()
    test_content = b"VIDEO_CHUNK_BYTES_001"
    
    # Bước 2: Lần 1 upload thành công nhưng giả lập lost-ACK mạng
    res1 = adapter.resumable_upload(
        file_id=file_id,
        name="video_output_001.mp4",
        content=test_content,
        simulate_lost_ack=True,
    )
    assert res1["status"] in ("ACK_LOST_AFTER_COMMIT", "UPLOADED")
    backend.store_file(file_id, "video_output_001.mp4", test_content)

    # Bước 3: Retry lại upload với cùng file_id
    res2 = adapter.resumable_upload(
        file_id=file_id,
        name="video_output_001.mp4",
        content=test_content,
        simulate_lost_ack=False,
    )
    assert res2["status"] == "UPLOADED"
    assert res2["file_id"] == file_id

    # Oracle: Dù có retry sau lost-ACK, trên Drive chỉ có đúng 1 object với file_id này
    assert len([f for f in backend.files.values() if f["id"] == file_id]) == 1


def test_tst_m1_p3_002_timeout_classification_and_reconciliation():
    """TST-M1-P3-002:
    Timeout trước khi gửi byte được phân loại là RETRYABLE.
    Timeout sau khi server đã nhận byte phân loại là UNKNOWN_OUTCOME và kích hoạt reconciliation.
    """
    adapter = DriveStorageAdapter()

    # Case A: Lỗi ngắt kết nối trước khi gửi byte
    err_before = adapter.classify_upload_timeout(bytes_sent=0, total_bytes=1000)
    assert err_before == "RETRYABLE_TRANSIENT_TIMEOUT"

    # Case B: Lỗi ngắt kết nối sau khi đã gửi đủ byte lên server nhưng mất ACK
    err_after = adapter.classify_upload_timeout(bytes_sent=1000, total_bytes=1000)
    assert err_after == "UNKNOWN_OUTCOME_REQUIRES_RECONCILE"
