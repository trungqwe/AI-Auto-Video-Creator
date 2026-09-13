# M1-P3 — Google Drive & OAuth G04 Proof Status

**Ngày hoàn thành:** 13-09-2026  
**Trạng thái Work Package:** `PASS_M1_SCOPE`  
**Trạng thái Cổng G04:** `PARTIALLY_PROVEN (PASS_M1_SCOPE)` (chứng minh đầy đủ trong phạm vi M1, bao gồm ADR-0009 Cloud Token Broker HTTP process boundary và live verification E3 trên Google Drive thật)  
**Phân loại Bằng chứng (Evidence Tier):** `E3` (được xác thực bởi `drive_e3_evidence.json`)  
**Phạm vi áp dụng:** Google Drive API v3 + OAuth 2.0 Token Broker kiến trúc ADR-0009, Desktop client cách ly tuyệt đối khỏi refresh token, zero plaintext token trên disk máy trạm.

## 1. Kết quả kiểm thử (Acceptance Proof)

| Test ID | Nội dung kiểm thử | Kết quả | Ghi chú & Bằng chứng |
|---|---|---|---|
| `TST-M1-P3-001` | Pre-generated ID & Resumable retry lost-ACK | **PASS** | Drive API pre-allocated ID ngăn ngừa duplicate file khi retry sau lost-ACK; idempotent upload. |
| `TST-M1-P3-002` | Timeout classification & reconciliation | **PASS** | Phân loại chính xác Connect Timeout (retryable) vs Read Timeout (ambiguous outcome -> reconciliation). |
| `TST-M1-P3-003` | Byte integrity & SHA-256 verification | **PASS** | Xác minh đối soát byte download khớp từng bit với payload gốc (`hashlib.sha256`); phát hiện và từ chối payload hỏng byte. |
| `TST-M1-P3-004` | Resumable session reconciliation | **PASS** | Xử lý HTTP 404/410 của resumable upload URI, tự động thương lượng lại session mới hoặc đánh dấu reconciliation. |
| `TST-M1-P3-005` | OAuth lifecycle & ADR-0009 desktop boundary | **PASS** | Desktop client không lưu refresh token dài hạn không mã hóa trên disk; token hết hạn tự động refresh trong bộ nhớ. |
| `TST-M1-P3-006` | Rate limit HTTP 429 bounded backoff | **PASS** | Tôn trọng `Retry-After` header từ Drive API, áp dụng bounded exponential backoff có jitter, chặn retry bão hòa. |
| `TST-M1-P3-007` | Secret boundary scanning in logs & receipts | **PASS** | Tự động quét và che giấu (redact) `access_token`, `client_secret`, `refresh_token` trong toàn bộ logs, exceptions và receipts. |
| `TST-M1-P3-008` | Desktop client token isolation (ADR-0009) | **PASS** | Desktop client audit quét 0 plaintext refresh token trên disk; credentials chỉ chứa access token ngắn hạn (`refresh_token=None`). |
| `TST-M1-P3-009` | Short-lived access capability refreshed by broker | **PASS** | Desktop client ủy quyền refresh cho CloudTokenBroker; nhận access token mới mà không bao giờ nhận refresh token. |
| `TST-M1-P3-010` | Revocation & token boundary lifecycle | **PASS** | Broker xử lý token revocation an toàn; desktop client thất bại fail-closed khi revoked. |
| `TST-M1-P3-011` | Insufficient scope 403 & secret redaction | **PASS** | Phân loại chính xác HTTP 403 `insufficientPermissions` thành `PERMANENT_SCOPE_REJECTED`; redact hoàn toàn token trong exception message. |
| `TST-M1-P3-012` | CloudTokenBroker HTTP process boundary | **PASS** | `CloudTokenBrokerServer` chạy qua HTTP TCP socket riêng biệt; Desktop giao tiếp qua REST IPC; broker vault đặt ngoài workspace (`~/.cloud_token_broker/vault.json`). |
| `TST-M1-P3-013` | Broker Subprocess Isolation (R5-01) | **PASS** | Broker chạy trong tiến trình Python OS riêng biệt (`subprocess.Popen`); desktop process không import/truy cập broker state; `broker_pid != desktop_pid`; fail-closed khi broker kill. |
| `TST-M1-P3-014` | Windows DPAPI Encrypted Vault (R5-02) | **PASS** | Refresh token và client secret được mã hóa bằng Windows Data Protection API native (`CryptProtectData`/`CryptUnprotectData`); vault lưu ciphertext base64; byte trên đĩa không chứa plaintext token. |
| `TST-M1-P3-015` | Broker-Owned OAuth Provisioning (R5.1) | **PASS** | Broker subprocess sở hữu toàn bộ OAuth provisioning và DPAPI vault; Desktop process không import DPAPISecureVault, không mở vault file, không nhận refresh token hoặc client_secret. |
| `TST-M1-P3-LIVE` | Live External Verification trên Google Drive thật qua Broker HTTP Subprocess boundary | **PASS** | Xác thực E3 thực nghiệm thành công với credential thật qua tiến trình broker riêng biệt (`broker_pid != desktop_pid`): pre-generated ID, resumable upload 64 bytes, download đối soát SHA-256 (`a1489a57...`), dọn dẹp delete, 0 token trên đĩa desktop, `broker_owns_oauth_provisioning=true`, `desktop_vault_access=false`. |

- Tổng số test M1-P3: **16/16 PASSED, 0 SKIPPED** (toàn bộ suite M1: 93 passed, 0 skipped).
- Tổng độ bao phủ mã nguồn (Coverage): **83%**.
- Tệp bằng chứng năng lực thực nghiệm: `docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json`.

## 2. Giới hạn & Quyết định kiến trúc

1. **Phạm vi hoàn tất:**
   - Đã chứng minh triệt để kiến trúc ADR-0009: Refresh token dài hạn thuộc Broker process/vault ngoài workspace; Desktop client kết nối qua HTTP IPC và nhận access token ngắn hạn (`refresh_token is None`); quét đĩa desktop cam kết 0 token vi phạm.
   - Thư mục `Credentials/` nằm trong `.gitignore`; các token tạm trên đĩa đã bị loại bỏ vĩnh viễn; không coi `.gitignore` là cơ chế mã hóa.
   - External Proof E3 đã được thực thi và xác nhận trên Google Drive API v3 thật với đầy đủ chữ ký SHA-256 và pre-generated ID.
2. **Giới hạn chuyển giao & Limitation:**
   - Cổng G04 toàn phần giữ mức `PARTIALLY_PROVEN (PASS_M1_SCOPE)` (chứng minh đầy đủ trong phạm vi proof M1).
   - **Bảo mật DPAPI:** `DPAPI proof runs under one Windows user; OS-account isolation between cloud host and desktop belongs to later deployment validation.` DPAPI không tự tạo process ACL mà mã hóa gắn với Windows user session.
   - Multi-tenant cloud broker phân tán và quản lý quota hàng triệu người dùng thuộc phạm vi M3+.
   - Không tự ý mở quyền sang M2, M3 hoặc Phân hệ A (`NOT AUTHORIZED`).
