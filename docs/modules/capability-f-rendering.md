# Đặc tả Kỹ thuật Capability F: Dựng Video & Kiểm tra Chất lượng (Video Rendering & Quality Control)

> **Mã Capability:** `CAP-F-RENDERING`
> **Chủ quản:** Module F
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-RENDER-QUALITY`, `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability F là khâu hoàn thiện kỹ thuật số của quy trình sản xuất, chịu trách nhiệm kết hợp kịch bản, hình ảnh, video nền, file giọng đọc và dữ liệu word timing để dựng video ngắn hoàn chỉnh độ phân giải 1080p (tỷ lệ 9:16 dọc), áp dụng hiệu ứng chạy chữ karaoke từng từ, tạo thumbnail bắt mắt trong hook và thực thi kiểm tra chất lượng (Quality Control - QC) trước khi xuất xưởng.

### Aggregates do Module F sở hữu độc quyền (Single-Writer):
- `Preset`: Cấu hình phong cách dựng video (font chữ, màu sắc karaoke highlight, bố cục khung hình, hiệu ứng chuyển cảnh).
- `RenderAttempt`: Nhật ký một lần dựng video (thời gian render, tài nguyên GPU sử dụng, log FFmpeg).
- `QualityReport`: Báo cáo thẩm định chất lượng tự động (độ phân giải, fps, bitrate, audio sync, độ dài).
- `VideoOutput`: File video MP4 hoàn chỉnh và metadata đầu ra đã qua thẩm định chất lượng.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Nhận Gói Dựng (Render Package):** Nhận kế hoạch phân cảnh và chỉ dẫn dựng từ Module D qua `CONTRACT-RENDER-QUALITY` (`CT-RND-001`).
- **Port Nhận Audio & Subtitle Timing:** Nhận `VoiceTrack` và `WordTiming` từ Module E qua `CONTRACT-MEDIA-PROCESSING` (`CT-SUB-001`).

### Outbound Ports:
- **Port Bàn giao Video Hoàn tất:** Thông báo hoàn thành render và gửi `QualityReport` cho Orchestration (Module G) và Storage (Module I) qua `CONTRACT-RENDER-QUALITY` (`CT-QC-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability F phải thỏa mãn:
1. `CONTRACT-RENDER-QUALITY` đã được đóng băng phiên bản (`frozen revision`).
2. Môi trường có sẵn binary `ffmpeg` và `ffprobe` chuẩn hóa theo toolchain lock.
3. GPU lease slot (`LOCK-DESKTOP-GPU`) được cấp phát hợp lệ thông qua LeaseManager, không vượt quá hạn ngạch 2 slot đồng thời.
4. Thư mục đầu ra được cô lập riêng trên ổ đĩa, không can thiệp vào thư mục của các module khác.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability F chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. Toàn bộ unit tests và integration render tests đạt `PASS`.
2. Tiêu chuẩn Video MP4 thành phẩm:
   - **Thời lượng:** Nghiêm ngặt từ **61 đến 70 giây**.
   - **Độ phân giải & Tỷ lệ:** Chuẩn 1080x1920 (9:16 dọc), tốc độ khung hình 30fps.
   - **Codec:** Video H.264 / AAC Audio, tương thích tối đa với các nền tảng video ngắn (TikTok, YouTube Shorts, Reels).
3. Karaoke Subtitle: Hiệu ứng chữ đổi màu theo đúng mốc `WordTiming` của từng từ, nằm trong vùng an toàn hiển thị.
4. Thumbnail Hook: File thumbnail JPEG chất lượng cao được trích xuất từ khung hình nằm trong 3 giây đầu tiên.
5. Báo cáo chất lượng `QualityReport` đạt chuẩn (không có dropped frames bất thường, không lệch tiếng quá 50ms).

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-001` (Exact Aspect Ratio & Resolution):** Mọi video xuất xưởng phải có kích thước đúng 1080x1920 (9:16 dọc).
- **`INV-002` (Video Duration Constraint):** Video thành phẩm có độ dài dưới 61 giây hoặc trên 70 giây phải bị loại bỏ tự động tại cổng QC.
- **`INV-009` (Atomic Render Cleanup):** Mọi file tạm (temp clips, audio chunks) phải được xóa sạch sau khi render; chỉ lưu lại file MP4 hoàn chỉnh và thumbnail.
- **`INV-018` (Quality Control Gate):** Video chỉ được chuyển giao sang Storage khi `QualityReport.passed == True`.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/render/**`
  - `tests/unit/render/**`
  - `docs/modules/capability-f-rendering.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/voice/**`
  - `src/controlplane/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Pipeline Dựng:** Sử dụng video/audio fixture ngắn để kiểm tra câu lệnh FFmpeg, tính toán filter complex phụ đề karaoke và trích xuất thumbnail.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi video đầu ra có kích thước 1920x1080 (ngang) hoặc khi phụ đề không hiển thị đúng thời điểm.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/render/test_video_pipeline.py -k test_output_specs_and_karaoke
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu quá trình render bị gián đoạn hoặc thất bại ở cổng QC, hủy bỏ `RenderAttempt`, dọn dẹp toàn bộ file tạm trên đĩa, giải phóng slot GPU `LOCK-DESKTOP-GPU` ngay lập tức và trả mã lỗi chi tiết về Orchestration.
