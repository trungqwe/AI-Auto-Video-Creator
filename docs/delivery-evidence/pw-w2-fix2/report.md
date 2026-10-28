# PW-W2-FIX2: báo cáo nhóm lỗi R4

## 1. Mục tiêu

Hiện thực một hàm định vị tệp media duy nhất (`locate_media_file`) dùng chung cho đầu vào ffmpeg, `read_image` và `verify_media_output` (nhóm lỗi R4):
- UUID version: truy vấn `controlplane.cp_artifact_versions` kết hợp `controlplane.cp_artifact_locations` với trạng thái `VERIFIED`, lấy `artifact_id` và `sha256_hash` rồi gọi `resolve_under_root(staging_root, artifact_id)`, chỉ trả đường dẫn khi sha của tệp khớp chính xác.
- Output dạng `processed:<id>` hoặc `rendition:<id>`: thay dấu `:` bằng `_` và tìm tệp dưới `media/` với đúng một hậu tố duy nhất tồn tại trong tập `png`, `jpg`, `jpeg`, `webp`.
- Tài nguyên nền nhạc dạng `music-<sha>` hoặc `bed-none-<sha>`: định vị tệp `.audio` hoặc `.wav` trong thư mục `audio_library`.

## 2. Các tệp đã sửa

- `src/controlplane/api/wiring/voice.py`:
  - Thêm `locate_media_file(manager, workspace_id, staging_root)` và hàm băm tệp `_file_sha256`.
  - Cập nhật `build_voice_services` dùng chung `locate_media_file` cho `media_tool` và `read_media_image(locate)`.
  - Cập nhật `verify_media_output` và `read_media_image` nhận hàm `locate`.
  - Cập nhật `voice_activity_deps` dùng chung cùng một hàm định vị `locate` cho `read_image` và `verify_output`.
  - Thêm `locate_media_file`, `read_media_image`, `verify_media_output` vào `__all__`.
- `tests/integration/prod_wiring/test_pw_w2_launcher_def.py`:
  - Bổ sung các import cần thiết cho test tích hợp.
  - Thêm fixture `r4` dựng dịch vụ voice production thật với FFmpeg ghim và PostgreSQL `pw_database` (chỉ `vision_route` là adapter biên giả).
  - Thêm 4 test tích hợp production không monkeypatch:
    - `test_pw_w2_r4_probe_assess_normalize_read_the_registered_png`
    - `test_pw_w2_r4_jpg_version_is_normalized_and_its_output_is_verified`
    - `test_pw_w2_r4_locator_returns_a_path_only_when_the_file_matches_the_verified_version`
    - `test_pw_w2_r4_audio_bed_is_found_and_prepare_audio_bed_is_verified`
- `docs/delivery-evidence/pw-w2-fix2/report.md`:
  - Tạo báo cáo nghiệm thu cho gói PW-W2-FIX2.

## 3. Quy tắc định vị tệp media

- **UUID version**: Chỉ chọn `artifact_id` và `sha256_hash` với location `VERIFIED` (cùng điều kiện `postgres_plan_assets.py:18-26`) rồi `resolve_under_root(staging_root, artifact_id)`, chỉ trả đường dẫn khi sha của tệp khớp.
- **Processed và Rendition**: Dưới `media/<ref>` thay `:` bằng `_` với đúng một hậu tố đang tồn tại trong `png`, `jpg`, `jpeg`, `webp`.
- **Music và Bed-none**: Tệp `music-<sha>.audio` và `bed-none-<sha>.wav` trong `audio_library`.

## 4. Lệnh kiểm đã chạy

| STT | Lệnh kiểm | Exit Code | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | Đạt (13 passed in 6.62s) |
| 2 | `git diff --check` | 0 | Đạt (không có lỗi khoảng trắng) |
| 3 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix2/report.md').read_text(encoding='utf-8'); assert 'PW-W2-FIX2' in t and 'R4' in t, 'report'"` | 0 | Đạt (khớp mã gói và nhóm lỗi) |

## 5. Dòng tổng kết nguyên văn của pytest

```
13 passed in 6.62s
```

## 6. Giới hạn

- Chỉ sửa nhóm lỗi R4 theo quy định của Control; không đổi hành vi của các nhóm lỗi khác (R1–R3, R5–R8).
- Không sửa hay tạo tệp ngoài 3 owned paths được giao.
- Test dùng FFmpeg ghim và PostgreSQL `pw_database`, không monkeypatch, chỉ `vision_route` là adapter biên giả.
- Kết quả kiểm thử được chạy thật và ghi lại trung thực.