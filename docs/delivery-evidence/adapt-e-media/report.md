# ADAPT-E-MEDIA: An toàn ảnh bằng LLM thị giác, boxblur và công cụ FFmpeg

## 1. Phạm vi và tệp đã sửa
- `src/voice/adapters/real_ffmpeg_media_tool.py`
- `src/voice/adapters/real_llm_image_safety.py`
- `tests/integration/adapt/e_media/test_adapt_e_media_tools.py`
- `docs/delivery-evidence/adapt-e-media/report.md`

Không sửa bất kỳ tệp nào ngoài 4 tệp thuộc owned paths ở trên (không sửa `src/voice/domain/**`, `src/voice/ports/**`, `src/voice/adapters/__init__.py`, `tools/runtime/runtime.lock.json`, hay `tests/unit/**`).

## 2. Thiết kế và giả định D8
- Pin ffmpeg đọc từ `tools/runtime/runtime.lock.json` (`pins.ffmpeg`), kiểm tra trước MỖI lần chạy (trạng thái `PINNED`, SHA-256 của `ffmpeg.exe` khớp đúng mã băm đã ghim, `ffprobe -version` chứa `archive_name`). Tuyệt đối không tra cứu hay thực thi `ffmpeg` trong `PATH`.
- Mọi lời gọi tiến trình ngoài đều dùng `subprocess.run` với danh sách đối số trực tiếp, `shell=False`, `stdin=subprocess.DEVNULL`, có tham số `timeout`.
- Tệp đầu ra luôn ghi ra tên mới theo quy tắc ref và extension, từ chối thực hiện nếu tệp đầu ra đã tồn tại hoặc trùng với tệp đầu vào, không bao giờ ghi đè lên tệp nguồn. Tệp dở dang do chính lần chạy tạo sẽ bị thu hồi / xoá bỏ (`_discard`) nếu tiến trình bị huỷ hoặc trả mã lỗi khác 0.
- Trường hợp quá hạn (`subprocess.TimeoutExpired`), công cụ trả `ToolOutcome` với trạng thái `OUTCOME_UNKNOWN` và mã lỗi `'ffmpeg_timeout'`.
- Xử lý che vùng nhạy cảm (`transform`) bằng bộ lọc `boxblur` theo danh sách `TransformRegion` với `mask_ref` dạng chuẩn hoá `region:x,y,w,h` trong khoảng 0..1. Bán kính làm mờ tính theo công thức `min(40, min(pw, ph) // 4)` với `luma_power=3`. Hành động khác `blur` (ví dụ `reject`) bị từ chối bằng `FfmpegToolError('unsupported_action')` trước khi gọi FFmpeg.
- Nếu không có hàm tái thẩm định (`reassess`), `post_assessment` trả về `DETECTION_FAILED` kèm cảnh báo `'post_transform_not_reassessed'` (tuyệt đối không tự khai báo `SAFE`).
- Bộ phát hiện an toàn ảnh `LlmImageSafetyDetector` gọi mô hình AI thị giác thông qua cổng `VisionRoutePort` (route J, `ai_role` là `'image_safety'`). Ép đầu ra JSON có kiểu cấu trúc `{confidence, detections[{category, confidence, region}]}`. Độ tin cậy tổng thể của `ImageDetection` lấy giá trị lớn nhất trong các phát hiện (hoặc lấy `confidence` mức đỉnh khi rỗng). Mọi sai lệch cấu trúc JSON, quá hạn thời gian, lỗi route hoặc sai lệch mã băm nội dung ảnh đều dẫn đến `DETECTION_FAILED` theo nguyên tắc fail-closed.
- Tuyệt đối không ghi nhật ký (không import logging), không ghi nội dung hay chuỗi base64 của ảnh vào log hay thông điệp lỗi.
- CÁC GIẢ ĐỊNH D8:
  1. Tham số chuẩn hoá phương tiện: `crop` (toạ độ pixel frame đầu vào), `resize` (kích thước khung hình), `pad` (căn giữa khung hình, màu nền hex), `color_conversion` (định dạng pixel), `transcode` (chỉ chấp nhận codec h264 sang libx264, container xác định phần mở rộng), `audio_normalize` (áp dụng thông số cố định `loudnorm=I=-16:TP=-1.5:LRA=11` từ plan.md mục 7.3, bỏ qua tên preset), `extract_frame` (`at_ms`), `duration_trim` (`start_ms`, `end_ms`).
  2. Việc chuẩn hoá kích thước ảnh đầu vào về cạnh dài 1024 px trước khi gửi tới API thị giác do bên cung cấp `read_image` / tầng tích hợp `ADAPT-WIRE` đảm nhiệm; slice này tập trung vào logic detector fail-closed và routing.

## 3. Lệnh đã chạy
Kết quả thực tế trên worktree (stdout/stderr và exit code):

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| Lệnh 1 | `git diff --check` | 0 | Sạch, không có lỗi khoảng trắng |
| Lệnh 2 | `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider` | 0 | 41 passed in 0.21s |
| Lệnh 3 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_media_tool.py', 'real_llm_image_safety.py']); assert 'boxblur' in t and 'runtime.lock.json' in t and 'shell=True' not in t and 'from src.' not in t, 'adapter E media'"` | 0 | Đạt assertions kiểm tra chuỗi cấm và chuỗi bắt buộc |

## 4. RED/GREEN
Nêu trung thực: Adapter được viết trước test nên không chứng kiến RED hợp lệ theo oracle; không tuyên bố ngược lại.

## 5. Việc còn lại (backlog, không làm trong slice này)
- Kiểm thử với nhị phân FFmpeg và ffprobe thật trên môi trường máy chủ thuộc gói CP7-E-04.
- Đánh giá trên tập dữ liệu ảnh nhạy cảm thật và căn chỉnh ngưỡng phát hiện thuộc gói CP7-E-03.
- Kết nối dây (`ADAPT-WIRE`) nối `VisionRoutePort` vào `RoutedInvocationService` của phân hệ J, cung cấp hàm `read_image` và phân giải đường dẫn lưu trữ `resolve_input` / `resolve_output`.
- Hỗ trợ mã hoá phần cứng NVENC thuộc phạm vi phân hệ F.