# Báo cáo Kiểm toán M1 R5 (Final Independent Audit Remediation & Verification)

**Ngày lập:** 13-09-2026  
**Đánh giá tổng thể:** **READY FOR USER CHECKPOINT**  
**Trạng thái phát hiện:** 0 BLOCKER, 0 MAJOR còn tồn đọng. Toàn bộ các vấn đề từ đợt kiểm toán độc lập trên GitHub HEAD `9167072` (R5-01..R5-05) đã được giải quyết triệt để bằng kiến trúc Broker Subprocess cách ly OS-level, kho bảo mật Windows DPAPI native, ma trận tương thích fail-closed và kiểm tra ngữ nghĩa capability tự động.

---

## 1. Căn cứ và Bối cảnh Kiểm toán R5

Đợt tái kiểm toán độc lập trên GitHub HEAD `916707238daafcde1b1c246a06b84049c337c38c` xác nhận phần lớn các hạng mục đã đạt (P0, P1, Temporal exact-server P2, P4 journal/recovery, FFmpeg probe). Tuy nhiên còn 2 BLOCKER và 1 MAJOR cần xử lý dứt điểm:
1. **R5-01 (BLOCKER) — Broker phải thật sự là process riêng:** Thay thế thread server bằng tiến trình OS riêng biệt (`subprocess.Popen`); Desktop process không import hay truy cập broker state; `broker_pid != desktop_pid`; fail-closed khi broker bị ngắt; live Google Drive E3 verification phải chạy qua ranh giới tiến trình này; lưu `broker_pid`, `desktop_pid`, `process_isolated: true` vào machine-readable evidence.
2. **R5-02 (BLOCKER) — Không lưu plaintext refresh token / client secret trên đĩa:** Thay thế JSON plaintext vault bằng kho mã hóa an toàn sử dụng Windows Data Protection API native (`CryptProtectData` / `CryptUnprotectData` từ `Crypt32.dll`); vault trên đĩa chỉ chứa base64 ciphertext và metadata; cam kết không có byte plaintext token nào tồn tại trên đĩa máy trạm.
3. **R5-03 (MAJOR) — Fail-Closed Dynamic Compatibility Matrix:** Xóa bỏ 100% logic fallback gán giá trị mặc định khi observation lỗi (`except -> 18.6`, missing binary -> `1.31.2`); khi thiếu/lỗi thì `observed = None`, `result = "FAIL"`, `overall_result = "FAIL"`.
4. **R5-04 — P6 Semantic Capability Validation:** Validator P6 kiểm tra sâu cấu trúc machine-readable (P3 E3: `process_isolated == true`, `broker_pid != desktop_pid`, DPAPI secure storage verified; P5: mọi runtime `result == "PASS"`, không null/FAIL/unknown) trước khi cấp `E3` và `READY_FOR_USER_CHECKPOINT`.
5. **R5-05 — Kỷ luật Test-First & Bằng chứng RED R5:** Chứng kiến RED thật cho 4 tests R5 trước implementation và lưu log thô UTF-8 tại `red-r5-stdout.txt`; sau correction chạy toàn bộ test suite (91 tests PASSED, 0 skipped), tái tạo manifest, validate hashes và secret scan sạch 100%.

---

## 2. Chi tiết Kết quả Khắc phục 5 Hạng mục Kiểm toán R5

### 2.1. R5-01 — Broker Subprocess OS Isolation & Live E3 Verification
- **Triển khai kiến trúc:**
  - Hỗ trợ CLI runner cho `m1proof.broker_service` (`python -m m1proof.broker_service --port PORT --vault-path PATH`).
  - Hàm `start_broker_subprocess` spawn tiến trình Python OS riêng biệt qua `subprocess.Popen`, trả về `BrokerSubprocessHandle(pid, port, base_url, process)`.
  - Desktop client chỉ nhận `base_url` (ví dụ `http://127.0.0.1:58432`) và giao tiếp qua REST IPC; hoàn toàn không import hay can thiệp vào bộ nhớ của broker process.
  - Kiểm thử `TST-M1-P3-013`: Xác nhận `broker_pid != desktop_pid`; khi tiến trình broker bị kill (`terminate()`), desktop client fail-closed ngay lập tức.
- **Thực nghiệm E3 trên Google Drive thật qua Subprocess (`drive_live_probe.py`):**
  - Khởi động broker server trong subprocess độc lập (`broker_pid=49052`, `desktop_pid=20320`).
  - Desktop client xin pre-generated ID từ Google Drive API v3: `1zLi2d...HsQD`.
  - Tải lên 64-byte payload bằng Resumable Upload với pre-generated ID.
  - Tải về byte stream, đối soát mã băm SHA-256 (`a1489a57bff218ba...`) khớp 100%.
  - Tự động dọn dẹp xóa tệp test khỏi Google Drive.
  - Xuất tệp bằng chứng máy học: `docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json` ghi nhận:
    * `status`: `PASS_E3_LIVE`
    * `process_isolated`: `true`
    * `broker_pid`: `49052`
    * `desktop_pid`: `20320`
    * `secure_storage_verified`: `true`
    * `desktop_refresh_token_retained`: `false`

### 2.2. R5-02 — Windows Native DPAPI Encrypted Vault
- **Triển khai bảo mật (`src/m1proof/secure_vault.py`):**
  - Sử dụng Windows native Data Protection API qua `ctypes.windll.crypt32.CryptProtectData` và `CryptUnprotectData` với cờ `CRYPTPROTECT_UI_FORBIDDEN = 0x1`.
  - Vault file lưu tại `~/.cloud_token_broker/vault.json` (bên ngoài thư mục workspace).
  - Cấu trúc phong bì lưu trữ thật trên đĩa (schema version 1.0): `version: "1.0"`, `encryption: "WINDOWS_DPAPI"`, `encrypted: true`, `ciphertext: "..."` (Base64), `updated_at: "..."` (ISO UTC timestamp). Không sử dụng các trường ngoài implementation.
  - Quét byte nhị phân trực tiếp trên đĩa: Xác nhận 100% không chứa chuỗi plaintext của `client_secret` hay `refresh_token`.
  - Kiểm thử `TST-M1-P3-014`: Đọc đĩa thấy mã hóa, giải mã DPAPI khôi phục chính xác token gốc trong tiến trình broker; desktop audit quét 0 token trên đĩa máy trạm.

### 2.3. R5-03 — Fail-Closed Dynamic Compatibility Matrix
- **Triển khai fail-closed (`src/m1proof/compatibility.py`):**
  - Xóa bỏ 100% logic fallback gán giá trị mặc định (`18.6` khi PostgreSQL lỗi, `1.31.2` khi Temporal binary missing).
  - Khi quan sát lỗi hoặc thiếu thành phần: `observed = None`, `result = "FAIL"`, và `overall_result = "FAIL"`.
  - Bổ sung tham số tùy chọn (`db_url`, `temporal_binary_path`, `ffmpeg_binary_path`) phục vụ negative testing cô lập.
  - Kiểm thử `TST-M1-P5-009`: Mô phỏng DB unreachable và thiếu temporal binary, ma trận xác nhận `observed is None`, `result == "FAIL"`, `overall_result == "FAIL"`.
  - Sinh lại `docs/milestones/m1-proof/evidence/m1-p5/compatibility_matrix.json` từ runtime thật: Tất cả các thành phần đạt PASS, `overall_result == "PASS"`.

### 2.4. R5-04 — Semantic Capability Validation trong Evidence Manifest
- **Triển khai (`src/m1proof/evidence_manifest.py`):**
  - Validator không chỉ kiểm tra sự tồn tại của tệp mà phân tích sâu cấu trúc machine-readable:
    * **P3 E3 Check:** Yêu cầu `status == "PASS_E3_LIVE"`, `sha256_verified is True`, `process_isolated is True`, `broker_pid != desktop_pid`, `broker_pid > 0`, `desktop_pid > 0`, `broker_owns_oauth_provisioning is True`, `desktop_vault_access is False`, `desktop_refresh_token_retained is False`, `secure_storage_verified is True`, `encryption_method == "WINDOWS_DPAPI"`, `broker_boundary == "HTTP_IPC_SUBPROCESS_BOUNDARY"`. Nếu vi phạm, gán status `CAPABILITY_EVIDENCE_SEMANTIC_FAIL` và từ chối phân loại `E3`.
    * **P5 Matrix Check:** Yêu cầu `overall_result == "PASS"`, tất cả runtimes có `result == "PASS"` và `observed` hợp lệ (không None/unknown/null/rỗng). Nếu có bất kỳ runtime nào lỗi, gán `CAPABILITY_EVIDENCE_SEMANTIC_FAIL`.
  - Kiểm thử `TST-M1-P6-009` và `TST-M1-P6-010`: Xác nhận manifest builder và gate engine từ chối cấp E3 và chặn `READY_FOR_USER_CHECKPOINT` khi dữ liệu capability bị giả mạo, vi phạm ranh giới cách ly, hoặc bất kỳ trường bắt buộc nào sai lệch.

### 2.5. R5-05 — Kỷ luật Test-First & Bằng chứng RED R5
- **Bằng chứng RED R5:** Các bài test R5 mới được viết trước mã nguồn và chứng kiến RED thất bại đúng oracle:
  * `test_tst_m1_p3_013_broker_subprocess_isolation`: FAILED (`ImportError: cannot import name 'start_broker_subprocess'`)
  * `test_tst_m1_p3_014_dpapi_encrypted_vault`: FAILED (`ModuleNotFoundError: No module named 'm1proof.secure_vault'`)
  * `test_tst_m1_p5_009_fail_closed_compatibility_matrix`: FAILED (`AssertionError: assert matrix['postgresql']['observed'] is None`)
  * `test_tst_m1_p6_009_semantic_capability_validation`: FAILED (`AssertionError: assert 'E3' not in manifest1['evidence_classification']['m1-p3']`)
- **Tệp log thô UTF-8:** Lưu trữ nguyên vẹn tại `docs/milestones/m1-proof/evidence/m1-p6/red-r5-stdout.txt`.

---

## 3. Tổng hợp Dữ liệu Kiểm thử Toàn bộ Milestone M1

Toàn bộ test suite M1 đạt **93/93 PASSED, 0 SKIPPED, 0 FAILED** (thời gian chạy ~47.10s, độ bao phủ 83%).

| Work Package | Số test | Phân loại Bằng chứng | Trạng thái | Ghi chú & Trọng tâm Kỹ thuật |
|---|---|---|---|---|
| **M1-P0** | 9 | E2-INT | **PASS** | CPython 3.13.15, uv 0.12.13 frozen lock, PostgreSQL 18.6 preflight |
| **M1-P1** | 15 | E2-INT | **PASS** | Contract fencing, Advisory lock CAS, Idempotency receipt, Atomic UoW |
| **M1-P2** | 12 | E2-INT | **PASS** | Temporal Workflow G01, Worker offline/resume, Exact Server 1.31.2 binary |
| **M1-P3** | 16 | **E3** | **PASS** | Google Drive API v3, ADR-0009 Subprocess Broker, Windows DPAPI Vault, Broker-owned provisioning, E3 live probe |
| **M1-P4** | 22 | E2 | **PASS** | SQLite WAL local journal, Windows Atomic Rename & Fsync, Recovery epoch |
| **M1-P5** | 9 | E2-INT | **PASS** | Strict M1-R1 toolchain, Fail-closed dynamic compatibility matrix, FFmpeg probe |
| **M1-P6** | 10 | AUDIT | **PASS** | Dynamic manifest builder, Semantic capability validation & negative fields testing, Secret scanner sạch |
| **TỔNG CỘNG** | **93** | **E2/E3/AUDIT** | **PASS** | **100% Passed, 0 Skipped, 0 Failed, Coverage 83%** |

---

## 4. Ma trận Trạng thái Các Cổng Kiến trúc (Architectural Gates)

| Mã Cổng | Tên Cổng | Phạm vi M1 | Trạng thái Đạt được | Căn cứ Xác nhận |
|---|---|---|---|---|
| **G01** | Temporal Orchestration | Workflow idempotency, exact server binary integration & replay | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` | 12/12 tests P2 pass, `temporal_server_evidence.json` xác thực binary 1.31.2. |
| **G02** | Transaction & CAS Fencing | Database atomic transaction, outbox pattern, lease expiration | `PASS_M1_SCOPE` | 15/15 tests P1 pass, PostgreSQL 18.6 live rollback & concurrent CAS. |
| **G03** | Local Journal & Recovery | Windows crash consistency, atomic file replace, WAL replay | `PASS_M1_SCOPE` | 22/22 tests P4 pass, atomic finalize fsync & quarantine epoch. |
| **G04** | Cloud Storage & OAuth | Drive resumable upload, token broker isolation & external proof | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` | 16/16 tests P3 pass, Subprocess Broker, DPAPI Vault, Broker-owned provisioning, E3 live probe verified. |
| **G05** | Rate Limit & Backoff | Exponential jitter backoff, lost-ACK recovery, timeout classification | `PASS_M1_SCOPE` | P1 + P3 backoff rate limiter, phân loại timeout triệt để. |
| **G06** | Secret & Privacy Boundary | Zero secret in log/receipt/tree, DPAPI storage, canary scanner | `PASS_M1_SCOPE` | DPAPI vault ngoài workspace, scanner quét 0 secret trên toàn repo. |
| **G07** | Local Processing (FFmpeg) | Version probe, codec verification, WAV audio analysis | `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` | 9/9 tests P5 pass, dynamic matrix đo đạc FFmpeg 9.0.1 và ffprobe. |

---

## 5. Kết luận & Khuyến nghị Bàn giao

1. **Kết luận Kiểm toán:**
   - Đợt kiểm toán độc lập R5 và bổ sung R5.1 ghi nhận toàn bộ các vấn đề (Broker Subprocess OS Isolation, Windows DPAPI Native Vault, Fail-Closed Matrix, Broker-Owned OAuth Provisioning và siết chặt Semantic Capability Validation) đã được khắc phục hoàn toàn với đầy đủ bằng chứng kiểm thử tự động, bằng chứng RED và thực nghiệm live API.
   - Milestone M1 chính thức đủ điều kiện chuyển trạng thái sang **`READY_FOR_USER_CHECKPOINT`**.
2. **Khuyến nghị & Ranh giới:**
   - Trình người dùng phê duyệt Milestone M1 tại User Checkpoint.
   - Tiếp tục tuân thủ tuyệt đối quy định: **KHÔNG MỞ M2, M3 HOẶC PHÂN HỆ A (`NOT AUTHORIZED`)** cho tới khi có văn bản chấp thuận chính thức từ người dùng.

---

## 6. R5.1 Addendum — Broker-Owned Provisioning & Semantic Refinement

Theo kết quả tái kiểm toán độc lập bổ sung trên HEAD `ed0fc83`, mục này ghi nhận hai điểm hoàn thiện kỹ thuật:

### 6.1. Khắc phục Quyền sở hữu OAuth/Vault trong Live E3 Proof
- **Thiết kế ranh giới:**
  - Broker subprocess được spawn trước khi thực hiện bất kỳ thao tác OAuth nào.
  - Broker subprocess là tiến trình DUY NHẤT mở, đọc và giải mã kho DPAPI vault.
  - Broker subprocess là tiến trình DUY NHẤT thực hiện OAuth consent flow và sở hữu refresh token.
  - Proof orchestrator / Desktop process tuyệt đối KHÔNG import `DPAPISecureVault`, KHÔNG gọi `vault.get_account()`, KHÔNG bao giờ chạm tới refresh token hay `client_secret`.
  - Desktop client chỉ biết broker HTTP endpoint và account reference (`m1_drive_account`), xin short-lived access token qua REST IPC.
- **Thực nghiệm E3 Live mới:**
  - Broker PID: `23076`, Desktop PID: `23768` (`broker_pid != desktop_pid`).
  - Pre-generated ID: `1R6D6B...R5Ux`, resumable upload 64 bytes, đối soát SHA-256 khớp 100%, dọn dẹp file test thành công.
  - Bằng chứng máy học `docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json` xác thực `broker_owns_oauth_provisioning = true` và `desktop_vault_access = false`.

### 6.2. Siết chặt Ngữ nghĩa Capability Evidence trong Validator P6
- Validator P6 bắt buộc kiểm tra các trường machine-readable trong `drive_e3_evidence.json`:
  * `desktop_refresh_token_retained == false`
  * `desktop_vault_access == false`
  * `broker_owns_oauth_provisioning == true`
  * `encryption_method == "WINDOWS_DPAPI"`
  * `broker_boundary == "HTTP_IPC_SUBPROCESS_BOUNDARY"`
  * `process_isolated == true`, `broker_pid != desktop_pid`, `sha256_verified == true`.
- Bài kiểm thử `TST-M1-P6-010` thực hiện negative testing thay đổi từng trường trên và xác nhận manifest builder từ chối cấp E3 và chặn `READY_FOR_USER_CHECKPOINT` fail-closed 100%.

### 6.3. Giới hạn Bảo mật DPAPI (Documented Limitation)
> [!NOTE]
> `DPAPI proof runs under one Windows user; OS-account isolation between cloud host and desktop belongs to later deployment validation.`  
> Kiến trúc không tuyên bố DPAPI tự tạo process ACL; DPAPI mã hóa dữ liệu gắn với Windows user account hiện hành. Phân tách multi-user OS account thuộc giai đoạn triển khai production sau M1.

