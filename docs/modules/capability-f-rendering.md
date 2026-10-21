# Đặc tả Kỹ thuật Capability F: Dựng Video & Kiểm tra Chất lượng (Video Rendering & Quality Control)

> **Mã Capability:** `CAP-F-RENDERING`
> **Chủ quản:** Module F
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-RENDER-QUALITY`, `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability F là khâu hoàn thiện kỹ thuật số của quy trình sản xuất, chịu trách nhiệm kết hợp kịch bản, hình ảnh, video nền, file giọng đọc và dữ liệu word timing để dựng video ngắn hoàn chỉnh đầu ra theo `output_profile_revision`, áp dụng hiệu ứng chạy chữ karaoke từng từ, tạo thumbnail bắt mắt trong hook và thực thi kiểm tra chất lượng (Quality Control - QC) trước khi xuất xưởng.

### Aggregates do Module F sở hữu độc quyền (Single-Writer):
- `Preset`: Cấu hình phong cách dựng video (font chữ, màu sắc karaoke highlight, bố cục khung hình, hiệu ứng chuyển cảnh).
- `RenderAttempt`: Nhật ký một lần dựng video (thời gian render, tài nguyên GPU sử dụng, log FFmpeg).
- `QualityReport`: Báo cáo thẩm định chất lượng tự động (độ phân giải, fps, bitrate, audio sync, độ dài).
- `VideoOutput`: File video MP4 hoàn chỉnh và metadata đầu ra đã qua thẩm định chất lượng.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Resolve RenderPackage:** F resolve `RenderPackage` từ ref của C, D, E, I (`CT-RND-002`, binding `f-render-package`); D chỉ là input_provider.
- **Port Nhận Audio & Subtitle Timing:** Nhận `VoiceTrack` và `WordTiming` từ Module E qua `CONTRACT-MEDIA-PROCESSING` (`CT-SUB-001`).

### Outbound Ports:
- **Port Output Ready:** F trả output ready cho G (`CT-RND-005`, binding `f-g-output-ready`); G yêu cầu I đồng bộ và verify (`CT-STO-006`) rồi commit completion (`CT-ORC-008`); F không gửi video thẳng cho I; `CT-QC-001` là `InspectOutput`, không phải cổng bàn giao.

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability F phải thỏa mãn:
1. `CONTRACT-RENDER-QUALITY` đã được đóng băng phiên bản (`frozen revision`).
2. Binary `ffmpeg` và `ffprobe` khóa theo toolchain là việc CONV-F-13 và CP7; slice dùng metadata giả.
3. Slot `LOCK-DESKTOP-GPU` do LeaseManager và G cấp; F chỉ giữ qua port lease và trả khi xong hoặc lỗi.
4. Thư mục đầu ra được cô lập riêng trên ổ đĩa, không can thiệp vào thư mục của các module khác.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability F chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. Toàn bộ unit tests và integration render tests đạt `PASS`.
2. Tiêu chuẩn Video MP4 thành phẩm:
   - **Thời lượng:** gate `DURATION_RANGE` (`CT-QC-001`); khoảng 61–70 giây nằm trong quality policy revision.
   - **Output profile:** theo `output_profile_revision` (ROADMAP-OPEN-007, QUALITY-OPEN-006, TEST-OPEN-005, TECH-OPEN-012); không có hằng 1080x1920, 30 fps, H.264, AAC.
3. Karaoke Subtitle: Hiệu ứng chữ đổi màu theo đúng mốc `WordTiming` của từng từ, nằm trong vùng an toàn hiển thị.
4. Thumbnail Hook: thumbnail nằm trong time range của hook (`CT-RND-003` điều kiện 3, gate `THUMBNAIL_PRESENT`), không cố định 3 giây đầu.
5. `QualityReport` đạt hard gate theo `CT-QC-001`; sai số karaoke là ROADMAP-OPEN-008, QUALITY-OPEN-007, TEST-OPEN-006 chưa chốt; `VISUAL_CONTINUITY` và `AUDIO_MIX_QUALITY` là warning hoặc score.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-001`** (`TST-CTR-INV-001`): idempotency command; **`INV-002`** (`TST-CTR-INV-002`): idempotency event; **`INV-009`** (`TST-E2E-INV-009`): QC pass mà upload chưa verify thì không completion, không xóa local; **`INV-018`** (`TST-WF-INV-018`): allocator.
- Kích thước và thời lượng là gate `OUTPUT_PROFILE_VALID` và `DURATION_RANGE` (`CT-QC-001`); điều kiện chuyển giao là `CT-RND-005`.
- Gate `DURATION_RANGE` fail thì không tạo `VideoOutput` ready; F không tự cắt hay kéo video (`CT-QC-001`).

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/render/**`
  - `tests/unit/render/**`
  - `tests/integration/render/**`
  - `docs/modules/capability-f-rendering.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/voice/**`
  - `src/controlplane/**` (không sửa; F vẫn import module có sẵn ở chế độ chỉ đọc)
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Pipeline Dựng:** Sử dụng video/audio fixture ngắn để kiểm tra câu lệnh FFmpeg, tính toán filter complex phụ đề karaoke và trích xuất thumbnail.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi video đầu ra có kích thước 1920x1080 (ngang) hoặc khi phụ đề không hiển thị đúng thời điểm.
- **Targeted Test Command:**
  ```bash
  python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** RenderAttempt bất biến: lỗi ghi thành attempt thất bại, retry dùng attempt và artifact mới (`CT-RND-004`, `CT-STATE-011`); F không xóa tệp, cleanup thuộc Module I (`CT-STO-007`, `CT-STO-008`) và exit gate M6; F trả slot GPU khi xong hoặc lỗi.
