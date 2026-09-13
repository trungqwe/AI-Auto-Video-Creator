# M1-P4 — Local Journal & Recovery Proof Status

**Ngày hoàn thành:** 13-09-2026  
**Trạng thái Work Package:** `PASS_M1_SCOPE`  
**Phạm vi áp dụng:** SQLite local journal + Atomic file finalization trên Windows + Recovery Epoch & Startup Reconciliation tương thích với CT-STO-005, CT-STO-008, CT-STO-009, ADR-0004, ADR-0006 và ADR-0010.

## 1. Kết quả kiểm thử (Acceptance Proof)

| Test ID | Nội dung kiểm thử | Kết quả | Ghi chú & Bằng chứng |
|---|---|---|---|
| `TST-M1-P4-001` | Crash sau local artifact complete trước gửi receipt | **PASS** | Tệp artifact đã hoàn tất trên đĩa, restart tìm và đưa vào `pending_resend`, gửi lại đúng operation mà không làm lại công việc render. |
| `TST-M1-P4-002` | Crash giữa file write / rename | **PASS** | Sử dụng file tạm `.tmp`, fsync và đối soát SHA-256 trước khi `os.replace`; lỗi hash hoặc dở dang bị từ chối và dọn dẹp, không coi partial byte là artifact hoàn tất. |
| `TST-M1-P4-003` | Cloud đã commit nhưng desktop mất ACK | **PASS** | Startup reconciliation truy vấn port cloud receipt P1, phát hiện trạng thái committed và cập nhật journal thành `COMMITTED_ON_CLOUD`, không commit lặp lần hai (idempotent). |
| `TST-M1-P4-004` | Stale recovery epoch & generation quarantine | **PASS** | Khi chuyển sang recovery epoch mới, các entry từ epoch cũ bị chuyển trạng thái `QUARANTINED`, ngăn chặn mọi mutation hoặc commit trái phép. |
| `TST-M1-P4-005` | Cache eviction protects unsent journal & active refs | **PASS** | Bộ đánh giá dọn dẹp cho phép xóa tệp cache đã sync cloud và hết lease, nhưng bảo vệ tuyệt đối tệp đang có journal reference active hoặc unsent receipt. |
| `TST-M1-P4-006` | Missing file or hash mismatch detected | **PASS** | Tệp vật lý bị xóa hoặc sai lệch mã băm SHA-256 trên đĩa được phát hiện và đánh dấu `CORRUPT_OR_MISSING`, không bao giờ báo success giả mạo. |

- Tổng số test M1 hiện hành: **63/63 PASSED** (thời gian chạy ~12.37s).
- Tổng độ bao phủ mã nguồn (Coverage): **89%**.

## 2. Giới hạn & Quyết định kiến trúc

1. **Phạm vi hoàn tất:**
   - Kết quả này xác nhận `sqlite3` tiêu chuẩn của Python và cơ chế atomic write trên Windows hoàn toàn đáp ứng các bất biến của Local Journal theo ADR-0006 và CT-STO-005/008/009.
   - Journal chỉ lưu trữ references, hash và metadata; không lưu token/credential hay nhúng blob thô, tuân thủ nghiêm ngặt ADR-0009.
2. **Giới hạn chuyển giao:**
   - Không tuyên bố G05 (Full system restore) toàn phần đạt PASS; G05 toàn diện yêu cầu tích hợp toàn bộ pipeline sản phẩm tại các milestone sau.
   - Work package tiếp theo là M1-P5 (Compatibility Smoke: FFmpeg, PostgreSQL, Temporal, Google Client).
   - Tiếp tục khóa toàn bộ M2, M3 và Phân hệ A (`NOT AUTHORIZED`).
