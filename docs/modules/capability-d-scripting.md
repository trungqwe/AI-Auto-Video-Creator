# Đặc tả Kỹ thuật Capability D: Sáng tạo Kịch bản & Kế hoạch Sản xuất (Scripting & Production Planning)

> **Mã Capability:** `CAP-D-SCRIPTING`
> **Chủ quản:** Module D
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-CREATIVE-AI`, `CONTRACT-SOURCE-CONTENT`, `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability D là trái tim sáng tạo nội dung của hệ thống, chịu trách nhiệm tiếp nhận ref revision bài viết (`ArticleRevisionAccepted`) từ Module B, gọi mô hình AI thông qua adapter định tuyến an toàn của Module J, xây dựng các góc kể đa dạng (`StoryAngle`), soạn thảo kịch bản phân cảnh 61–70 giây (`ScriptVersion`), tạo kế hoạch sản xuất chi tiết (`ProductionPlan`) và quản lý dấu vân tay biến thể (`VariantFingerprint`) để đảm bảo không trùng lặp nội dung.

### Aggregates do Module D sở hữu độc quyền (Single-Writer):
- `ProductionSnapshot`: Bản chụp đầu vào gồm nội dung bài viết và các hook được chọn làm căn cứ sinh kịch bản.
- `StoryAngle`: Góc tiếp cận câu chuyện (ví dụ: góc điều tra, góc chuyên gia, góc nhân chứng, góc dòng thời gian).
- `ScriptVersion`: Văn bản kịch bản chi tiết bao gồm lời thoại lồng tiếng, chỉ dẫn hình ảnh, điểm đặt hook và thumbnail.
- `ProductionPlan`: Kế hoạch ghép nối chi tiết giữa lời thoại, visual cue, hiệu ứng chuyển cảnh và preset mẫu.
- `VariantFingerprint`: Dấu vân tay cấu trúc kịch bản dùng để đối chiếu tránh trùng lặp giữa các lần xuất bản.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Tiếp nhận nội dung bài:** Nhận ref revision của Module B qua `ProductionSnapshot` (`CT-AI-001`) và `ArticleRevisionAccepted` (`CT-CNT-003`), binding `b-d-production-snapshot`; không qua `CT-CNT-002` (quy tắc bài đại diện của B).
- **Port Định tuyến AI:** Gửi yêu cầu sinh văn bản/kịch bản qua cổng AI Adapter của Module J qua `CONTRACT-CONFIG-SECURITY` (`CT-AI-ROUTE-001`). Module D chỉ dùng secret handle, không giữ API key.

### Outbound Ports:
- **Port Chuyển giao Kịch bản Voice:** Chuyển giao kịch bản kèm đánh dấu nhịp điệu sang Module E qua `CONTRACT-MEDIA-PROCESSING` (`CT-TTS-001`).
- **Port Cung cấp đầu vào RenderPackage:** D là input_provider của `RenderPackage` (`CT-RND-002`, `CT-RND-003`, binding `f-render-package`); Module F resolve gói, D không phát hành gói render.

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability D phải thỏa mãn:
1. `CONTRACT-CREATIVE-AI` đã đóng băng phiên bản revision (`frozen revision`).
2. Fixture `ProductionSnapshot` mẫu (`tests/fixtures/contracts/b-d-production-snapshot/payloads.json`) có đầy đủ dữ liệu thử nghiệm.
3. Stub/Mock AI Adapter của Module J đã sẵn sàng trong test environment để chạy kiểm thử xác định không cần gọi API mạng thật.
4. Ranh giới đường dẫn sở hữu đã được khóa, ngăn chặn việc chỉnh sửa cấu hình prompt ngoài Module D.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability D chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% unit tests và deterministic contract tests đạt `PASS`.
2. Độ dài kịch bản: ước lượng thời lượng đọc là validator đầu vào cho mục tiêu 61–70 giây, tốc độ đọc lấy từ policy (không có hằng số từ); thời lượng thật kiểm trên video ở Module F (`CT-QC-001` `DURATION_RANGE`).
3. Cấu trúc bắt buộc: Visual Hook, Audio Hook mở đầu và Thumbnail nằm trong time range của hook (`CT-MED-004`, `CT-RND-003` điều kiện 3); không có hằng 3 giây.
4. Chống trùng lặp biến thể: Trong cùng một lượt sản xuất, 1–3 video từ cùng một tin phải có góc kể khác biệt; `VariantFingerprint` phải đảm bảo khác biệt ít nhất một yếu tố thực tế so với lịch sử cũ.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-004`** (`TST-INT-INV-004`): snapshot bất biến, job đã snapshot giữ refs.
- **`INV-013`** (`TST-AI-INV-013`): 1–3 video cùng lượt có StoryAngle khác nhau.
- **`INV-014`** (`TST-AI-INV-014`): tái khai thác không exact duplicate; thời lượng 61–70 giây kiểm trên video thật ở Module F.
- **`INV-020`** (`TST-SEC-INV-020`): dữ liệu không tin cậy (`CT-AI-000`); thumbnail nằm trong time range của hook.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/creative/**`
  - `tests/unit/creative/**`
  - `tests/integration/creative/**`
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
  python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu kịch bản không đạt validation hoặc trùng biến thể, ghi attempt thất bại, không sửa lịch sử `ScriptVersion`; release giữ chỗ biến thể là quyền của Module G (`CT-ORC-012`); fallback prompt chỉ qua revision do Module J định tuyến (`CT-AI-ROUTE-002`), D không tự đổi.
