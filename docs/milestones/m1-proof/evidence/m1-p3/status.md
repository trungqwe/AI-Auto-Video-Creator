# M1-P3 — Google Drive & OAuth G04 Proof Status

**Ngày hoàn thành:** 13-09-2026  
**Trạng thái Work Package:** `PASS_M1_SCOPE`  
**Trạng thái Cổng G04:** `PARTIALLY_PROVEN` (chỉ trong phạm vi proof M1-P3)  
**Phạm vi áp dụng:** Google Drive API v3 + OAuth 2.0 Installed App Flow (Desktop) tương thích với ADR-0009, ADR-0003 và contracts P1.

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
| `E3-LIVE-PROBE` | Live External Verification trên Google Drive thật | **PASS_E3_LIVE** | Xác thực OAuth 2.0 thực tế trên tài khoản Google người dùng, cấp pre-generated ID từ Google Drive API thật, resumable upload 64 bytes, tải về đối soát SHA-256 (`a1489a57bff218ba...`) khớp 100%, dọn dẹp xóa tệp test thành công. |

- Tổng số test M1 hiện hành: **57/57 PASSED** (thời gian chạy ~12.17s).
- Tổng độ bao phủ mã nguồn (Coverage): **91%**.

## 2. Giới hạn & Quyết định kiến trúc

1. **Phạm vi hoàn tất:**
   - Kết quả này xác nhận Google Drive API v3 và OAuth 2.0 Installed App Flow đáp ứng đầy đủ ngữ nghĩa upload an toàn, idempotent với pre-generated ID và kiểm tra toàn vẹn byte cho M1.
   - Thư mục `Credentials/` và token cache được bảo vệ nghiêm ngặt qua `.gitignore` và quy tắc scan secret trước khi ghi log/receipt.
2. **Giới hạn chuyển giao:**
   - Cổng G04 toàn phần được nâng lên `PARTIALLY_PROVEN` (chỉ trong phạm vi proof M1-P3).
   - Việc tích hợp phân quyền multi-user, service account phân tán, quota management quy mô lớn thuộc phạm vi các milestone sản phẩm tiếp theo.
   - Không tự ý mở quyền sang M2, M3 hoặc Phân hệ A.
   - Giữ nguyên ràng buộc: M1 chỉ hoàn thành khi toàn bộ các work packages M1-P0 -> M1-P4 (hoặc tương đương) hoàn tất exit gate.
