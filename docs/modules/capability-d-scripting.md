# Đặc tả Kỹ thuật Capability D: Sáng tạo Kịch bản & Kế hoạch Sản xuất (Scripting & Production Planning)

> **Mã Capability:** `CAP-D-SCRIPTING`
> **Chủ quản:** Module D
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-CREATIVE-AI`, `CONTRACT-SOURCE-CONTENT`, `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability D là trái tim sáng tạo nội dung của hệ thống, chịu trách nhiệm tiếp nhận bản chụp bài viết (`ArticleSnapshot`) từ Module B, gọi mô hình AI thông qua adapter định tuyến an toàn của Module J, xây dựng các góc kể đa dạng (`StoryAngle`), soạn thảo kịch bản phân cảnh 61–70 giây (`ScriptVersion`), tạo kế hoạch sản xuất chi tiết (`ProductionPlan`) và quản lý dấu vân tay biến thể (`VariantFingerprint`) để đảm bảo không trùng lặp nội dung.

### Aggregates do Module D sở hữu độc quyền (Single-Writer):
- `ProductionSnapshot`: Bản chụp đầu vào gồm nội dung bài viết và các hook được chọn làm căn cứ sinh kịch bản.
- `StoryAngle`: Góc tiếp cận câu chuyện (ví dụ: góc điều tra, góc chuyên gia, góc nhân chứng, góc dòng thời gian).
- `ScriptVersion`: Văn bản kịch bản chi tiết bao gồm lời thoại lồng tiếng, chỉ dẫn hình ảnh, điểm đặt hook và thumbnail.
- `ProductionPlan`: Kế hoạch ghép nối chi tiết giữa lời thoại, visual cue, hiệu ứng chuyển cảnh và preset mẫu.
- `VariantFingerprint`: Dấu vân tay cấu trúc kịch bản dùng để đối chiếu tránh trùng lặp giữa các lần xuất bản.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Tiếp nhận ArticleSnapshot:** Nhận nội dung bài viết sạch từ Module B qua `CONTRACT-SOURCE-CONTENT` (`CT-CNT-002`).
- **Port Định tuyến AI:** Gửi yêu cầu sinh văn bản/kịch bản qua cổng AI Adapter của Module J qua `CONTRACT-CONFIG-SECURITY` (`CT-AI-ROUTE-001`). Module D chỉ dùng secret handle, không giữ API key.

### Outbound Ports:
- **Port Chuyển giao Kịch bản Voice:** Chuyển giao kịch bản kèm đánh dấu nhịp điệu sang Module E qua `CONTRACT-MEDIA-PROCESSING` (`CT-TTS-001`).
- **Port Xuất bản Gói Render (Render Package):** Chuyển giao kế hoạch sản xuất và layout visual sang Module F qua `CONTRACT-RENDER-QUALITY` (`CT-RND-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability D phải thỏa mãn:
1. `CONTRACT-CREATIVE-AI` đã đóng băng phiên bản revision (`frozen revision`).
2. Fixture `ArticleSnapshot` mẫu có đầy đủ dữ liệu thử nghiệm.
3. Stub/Mock AI Adapter của Module J đã sẵn sàng trong test environment để chạy kiểm thử xác định không cần gọi API mạng thật.
4. Ranh giới đường dẫn sở hữu đã được khóa, ngăn chặn việc chỉnh sửa cấu hình prompt ngoài Module D.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability D chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% unit tests và deterministic contract tests đạt `PASS`.
2. Kiểm chứng độ dài kịch bản: Kịch bản được sinh ra phải ước tính thời lượng đọc nằm nghiêm ngặt trong khoảng **61–70 giây** (khoảng 140–165 từ tiếng Anh tùy nhịp độ).
3. Đảm bảo cấu trúc 3 thành phần bắt buộc: Phải chứa Visual Hook (3 giây đầu), Audio Hook mở đầu và Thumbnail Marker nằm **trong hook**.
4. Chống trùng lặp biến thể: Trong cùng một lượt sản xuất, 1–3 video từ cùng một tin phải có góc kể khác biệt; `VariantFingerprint` phải đảm bảo khác biệt ít nhất một yếu tố thực tế so với lịch sử cũ.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-004` (Variant Fingerprint Uniqueness):** Hai video cùng batch hoặc lịch sử gần không được phép có cùng VariantFingerprint.
- **`INV-013` (Model Determinism & Safety):** Lời gọi AI phải có temperature và seed được cấu hình chặt chẽ; kết quả sinh phải được lọc an toàn nội dung.
- **`INV-014` (Duration Constraint 61-70s):** Kịch bản vượt quá hoặc thấp hơn ngưỡng 61–70 giây phải bị loại bỏ tự động ngay tại khâu biên soạn.
- **`INV-020` (Hook & Thumbnail Placement):** Thumbnail của video bắt buộc phải trích xuất từ khung hình nằm trong phân cảnh hook (3 giây đầu).

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/creative/**`
  - `tests/unit/creative/**`
  - `docs/modules/capability-d-scripting.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/controlplane/**`
  - `src/voice/**`
  - `src/render/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Thuật toán Sinh:** Sử dụng fake AI adapter trả về các phản hồi kịch bản mẫu định sẵn để kiểm tra parser phân đoạn kịch bản, bộ đếm từ và thuật toán tính fingerprint.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi kịch bản thiếu visual hook hoặc độ dài ước tính chỉ có 45 giây.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/creative/test_script_generator.py -k test_duration_and_hook_constraints
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu kịch bản sinh ra không đạt tiêu chuẩn độ dài hoặc trùng biến thể, hủy bỏ `ScriptVersion` hiện tại, giải phóng đặt trước biến thể trong Orchestration và kích hoạt fallback sang prompt preset thay thế.
