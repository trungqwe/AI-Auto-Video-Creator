# M1-P5 — Compatibility Smoke Status

**Ngày hoàn thành:** 13-09-2026  
**Trạng thái Work Package:** `PASS_M1_SCOPE`  
**Phạm vi áp dụng:** Compatibility smoke cho tập phiên bản M1-R1 trên môi trường thực tế máy trạm Windows 10 x64.

## 1. Kết quả kiểm thử (Acceptance Proof)

| Test ID | Nội dung kiểm thử | Kết quả | Ghi chú & Bằng chứng |
|---|---|---|---|
| `TST-M1-P5-001` | Exact Python, uv & frozen `uv.lock` integrity | **PASS** | CPython `3.13.15`, uv `0.12.13`, đối soát mã băm SHA-256 của `uv.lock` thành công, toàn bộ dependencies được sync frozen. |
| `TST-M1-P5-002` | PostgreSQL connect, rollback & UTF-8 tiếng Việt | **PASS** | PostgreSQL 18.6 kết nối qua psycopg 3.3.5, kiểm tra rollback thành công, đối soát chuỗi tiếng Việt phức tạp giữ nguyên vẹn 100%. |
| `TST-M1-P5-003` | Temporal SDK ↔ Server handshake & replay smoke | **PASS** | Temporal SDK `1.32.0` tương thích môi trường Server `1.31.2`, xác thực hỗ trợ replay lịch sử xác định qua `workflow.patched()`. |
| `TST-M1-P5-004` | Google client boundaries & credential classification | **PASS** | Khởi tạo an toàn các client Google Drive/OAuth, phân loại đúng lỗi thiếu credential mà không rò rỉ secret/token trong exception hay trace. |
| `TST-M1-P5-005` | FFmpeg version, buildconf & safe argument-array probe | **PASS** | Binary FFmpeg thực tế (`C:\ffmpeg\bin\ffmpeg.exe`, SHA-256: `f845a09b...`), cấu hình đầy đủ codec (`--enable-libx264`, `--enable-libmp3lame`), thực thi probe an toàn không dùng shell interpolation. |
| `TST-M1-P5-006` | Evidence hash mismatch & unsupported version detector | **PASS** | Detector phát hiện và từ chối fail-closed mọi artifact có mã băm sai lệch hoặc phiên bản không thuộc danh sách M1-R1 được phép. |

- Tổng số test M1 hiện hành: **69/69 PASSED** (thời gian chạy ~12.64s).
- Tổng độ bao phủ mã nguồn (Coverage): **89%**.

## 2. Giới hạn & Quyết định kiến trúc

1. **Phạm vi hoàn tất:**
   - Xác nhận tất cả các thành phần thuộc version-set M1-R1 thực sự cùng khởi động và giao tiếp thành công trên môi trường Windows x64.
   - Thư viện FFmpeg sẵn có trên máy trạm đáp ứng đầy đủ các cờ biên dịch codec cần thiết cho xử lý video ngắn.
2. **Giới hạn chuyển giao:**
   - Kết quả này là **Compatibility Smoke trong phạm vi M1**; tuyệt đối không nâng giả mạo thành G07 Production PASS (pipeline render hàng loạt ở quy mô lớn thuộc trách nhiệm các milestone sau).
   - Work package tiếp theo là **M1-P6 (Evidence synthesis & Audit)**.
   - Tiếp tục khóa toàn bộ M2, M3 và Phân hệ A (`NOT AUTHORIZED`).
