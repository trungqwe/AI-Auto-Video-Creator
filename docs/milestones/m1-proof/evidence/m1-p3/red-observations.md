# M1-P3 — Bằng chứng quan sát RED (Test-First)

**Ngày ghi nhận:** 13-09-2026  
**Lệnh thực thi:** `py -3.13 -m uv run --frozen pytest tests/m1/p3 -v`  
**Kết quả:** 5 FAILED, 2 PASSED trong 0.37s (exit code 1).

## Chi tiết các ca kiểm thử RED đúng Oracle

1. **`TST-M1-P3-002` (`test_drive_resumable_upload.py`):**
   - **Mục tiêu:** Phân loại timeout mạng trước/sau khi gửi byte (phân biệt `RETRYABLE` vs `UNKNOWN_OUTCOME`).
   - **Hiện tượng RED:** `AttributeError: 'DriveStorageAdapter' object has no attribute 'classify_upload_timeout'`.
   - **Lý do Oracle:** Adapter stub ban đầu chưa cung cấp phương thức phân loại ranh giới ngắt kết nối.

2. **`TST-M1-P3-003` (`test_drive_integrity.py`):**
   - **Mục tiêu:** Xác minh tính toàn vẹn byte và mã băm SHA-256 thực tế, từ chối file cùng tên khác nội dung.
   - **Hiện tượng RED:** `AttributeError: 'DriveStorageAdapter' object has no attribute 'verify_byte_integrity'`.
   - **Lý do Oracle:** Adapter stub chưa cài đặt logic kiểm tra đối chiếu kích thước byte và SHA-256.

3. **`TST-M1-P3-004` (`test_drive_integrity.py`):**
   - **Mục tiêu:** Đối soát khi gặp xung đột ID hoặc hết hạn session resumable upload (`RECONCILED_EXISTING_MATCH` vs `FATAL_ID_MISMATCH`).
   - **Hiện tượng RED:** `TypeError: DriveStorageAdapter.reconcile_conflict_or_timeout() got an unexpected keyword argument 'existing_file_bytes'`.
   - **Lý do Oracle:** Adapter stub chưa cài đặt logic đối soát nội dung tệp đã tồn tại.

4. **`TST-M1-P3-006` (`test_oauth_lifecycle.py`):**
   - **Mục tiêu:** Xử lý HTTP 429 Rate Limit bằng thuật toán exponential backoff có trần bảo vệ (bounded backoff), tránh retry storm.
   - **Hiện tượng RED:** `AttributeError: 'DriveStorageAdapter' object has no attribute 'calculate_exponential_backoff'`.
   - **Lý do Oracle:** Adapter stub chưa cài đặt thuật toán backoff và mô phỏng retry khi gặp 429.

5. **`TST-M1-P3-007` (`test_oauth_lifecycle.py`):**
   - **Mục tiêu:** Rà soát và lọc bỏ token, private key và canary secret khỏi log và receipt của Drive adapter.
   - **Hiện tượng RED:** `AttributeError: 'DriveStorageAdapter' object has no attribute 'log_safe_message'`.
   - **Lý do Oracle:** Adapter stub chưa cài đặt bộ lọc redaction secret cho log/receipt.

---

Bằng chứng RED này chứng minh các bài kiểm thử M1-P3 đã phản ánh đúng các invariant nghiệp vụ trước khi triển khai mã nguồn chính thức.
