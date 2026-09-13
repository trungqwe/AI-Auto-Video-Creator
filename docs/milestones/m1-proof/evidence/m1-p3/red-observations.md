# M1-P3 — Bằng chứng quan sát RED (Test-First)

**Ngày ghi nhận ban đầu:** 13-09-2026  
**Lệnh thực thi ban đầu:** `py -3.13 -m uv run --frozen pytest tests/m1/p3 -v`  
**Kết quả ban đầu:** 5 FAILED, 2 PASSED trong 0.37s (exit code 1).

---

## 1. Chi tiết các ca kiểm thử RED ban đầu (M1-P3 Implementation Phase)

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

## 2. Ghi nhận Độ lệch Lịch sử (Historical Deviation Note)

> [!WARNING]
> **Deviation: `RED_EVIDENCE_MISSING_FOR_R3_REMEDIATION`**  
> Trong đợt kiểm toán độc lập R3, các ca kiểm thử `TST-M1-P3-008..011` đã được phát triển để khắc phục ADR-0009 nhưng chưa lưu tách riêng tệp log stdout của giai đoạn RED trước khi viết mã nguồn. Để tuân thủ nguyên tắc minh bạch tuyệt đối, độ lệch này được ghi nhận công khai và không phục dựng log giả mạo.

---

## 3. Bằng chứng Quan sát RED Đợt Audit R4 (R4-03 Evidence)

Trước khi thực hiện cải tiến R4 (HTTP Process Boundary cho Broker), bài kiểm thử `TST-M1-P3-012` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

- **Lệnh thực thi:** `pytest tests/m1/p3/test_oauth_lifecycle.py -k test_tst_m1_p3_012_broker_http_process_boundary -v`
- **Kết quả:** `FAILED` đúng oracle (exit code 1).
- **Hiện tượng quan sát:** `ImportError: cannot import name 'CloudTokenBrokerServer' from 'm1proof.broker_service'`
- **Tệp bằng chứng thô:** `docs/milestones/m1-proof/evidence/m1-p6/red-r4-stdout.txt`

---

## 4. Bằng chứng Quan sát RED Đợt Audit R5 (R5-01 & R5-02 Evidence)

Trước khi thực hiện cải tiến R5 (Broker Subprocess Isolation & DPAPI Vault), hai bài kiểm thử `TST-M1-P3-013` và `TST-M1-P3-014` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

1. **`TST-M1-P3-013` (Broker Subprocess Isolation - R5-01):**
   - **Mục tiêu:** Khởi chạy Broker trong tiến trình Python OS riêng biệt (`subprocess.Popen`), desktop test process hoàn toàn không import hay truy cập broker state, `broker_pid != desktop_pid`, fail-closed khi broker process bị terminate.
   - **Hiện tượng RED:** `ImportError: cannot import name 'start_broker_subprocess' from 'm1proof.broker_service'`.

2. **`TST-M1-P3-014` (Windows DPAPI Encrypted Vault - R5-02):**
   - **Mục tiêu:** Mã hóa refresh token và client secret bằng Windows native DPAPI (`CryptProtectData`/`CryptUnprotectData`), vault trên đĩa chỉ chứa ciphertext base64, không có byte plaintext token nào tồn tại trên đĩa.
   - **Hiện tượng RED:** `ModuleNotFoundError: No module named 'm1proof.secure_vault'`.

- **Lệnh thực thi:** `pytest tests/m1/p3/test_oauth_lifecycle.py -k "test_tst_m1_p3_013 or test_tst_m1_p3_014" -v`
- **Kết quả:** `2 FAILED` đúng oracle (exit code 1).
- **Tệp bằng chứng thô UTF-8:** `docs/milestones/m1-proof/evidence/m1-p6/red-r5-stdout.txt`.

---

## 5. Bằng chứng Quan sát RED Đợt Audit R5.1 (Broker-Owned Provisioning Evidence)

Trước khi thực hiện cải tiến R5.1 (Broker-Owned OAuth Provisioning), bài kiểm thử `TST-M1-P3-015` đã được tạo lập trước và chứng kiến trạng thái RED đúng oracle:

- **Lệnh thực thi:** `pytest tests/m1/p3/test_oauth_lifecycle.py -k test_tst_m1_p3_015_broker_owned_oauth_provisioning -v`
- **Mục tiêu:** Chứng minh broker subprocess là tiến trình duy nhất mở vault và sở hữu OAuth provisioning; desktop orchestrator không import hay truy cập vault; endpoint `/api/status` trả về `broker_owns_oauth_provisioning: True`, `encryption_method: WINDOWS_DPAPI`, `broker_boundary: HTTP_IPC_SUBPROCESS_BOUNDARY`.
- **Kết quả:** `FAILED` đúng oracle (exit code 1).
- **Hiện tượng RED quan sát:** `AttributeError: 'BrokerProcessHandle' object has no attribute 'base_url'` (hoặc thiếu trường `broker_owns_oauth_provisioning` trong metadata status).
- **Tệp bằng chứng thô UTF-8:** `docs/milestones/m1-proof/evidence/m1-p6/red-r5-1-stdout.txt`.
