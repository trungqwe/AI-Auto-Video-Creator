# PW-F1-FIX1 — THUMBNAIL so khung output với đúng khung của hook clip

## Nhóm lỗi

- Mã gói: `PW-F1-FIX1`
- Nhóm lỗi: `R10` (phân giải hook, thumbnail)
- Chi tiết lỗi: `_thumbnail` so khung output ở `time_ms` với khung đầu của asset (`right_ms=None`); thumbnail của production là khung của visual hook (`creative/adapters/thumbnail_candidates.py:43-50`) nên với hook clip có chuyển động gate `THUMBNAIL` bị FAIL oan dù video kết xuất hoàn toàn chính xác.

## Cách sửa

- Khi đường dẫn asset của `thumbnail_ref` trùng asset của `visual_hook_ref`: seek asset ở `min(time_ms - hook_time_range.start_ms, độ dài clip - 1 frame)` (độ dài clip đo bằng `FrameProbe.duration_ms` của inspector; khớp overlay `eof_action=repeat` của F-10-FIX2, clip ngắn hơn cửa sổ hook giữ khung cuối).
- Thêm hằng `HOOK_CLIP_LAST_FRAME_GUARD_MS = 34` ms (tương ứng 1 frame tại profile 30 fps; giữ seek trong khung cuối của clip hook).
- Thêm phương thức `_thumbnail_asset_seek_ms(self, package: RenderPackageRecord, asset: Path, time_ms: int) -> int | None` vào class `RealOutputInspector`.
- Trong `_thumbnail`, truyền `right_ms = self._thumbnail_asset_seek_ms(package, asset, time_ms)` vào đối số vị trí thứ 5 của `ssim_between`.
- Ảnh tĩnh và asset thumbnail khác hook giữ nguyên `right_ms=None`.
- `_visual_hook`, `ssim_between`, các ngưỡng và mọi hàm khác trong `real_output_inspector.py` giữ nguyên không đổi.

## Tệp đã sửa

1. `src/render/adapters/real_output_inspector.py`
2. `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`
3. `docs/delivery-evidence/pw-f1-fix1/report.md`

## Lệnh kiểm đã chạy

- **Bước RED (trước khi sửa mã production):**
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider`
  - Mã thoát: `1`
  - 3 test fail do gate THUMBNAIL:
    - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py::test_pw_f1_thumbnail_hook_clip_same_asset_passes`
    - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py::test_pw_f1_thumbnail_hook_clip_offset_uses_hook_start`
    - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py::test_pw_f1_thumbnail_short_clip_holds_last_frame_passes`
  - Dòng tổng kết pytest nguyên văn:
    ```
    3 failed, 14 passed in 7.13s
    ```

- **Bước GREEN (sau khi sửa mã production):**
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider`
  - Mã thoát: `0`
  - Dòng tổng kết pytest nguyên văn:
    ```
    17 passed in 5.99s
    ```

- **Kiểm tra định dạng và khoảng trắng:**
  - Lệnh: `git diff --check`
  - Mã thoát: `0`

- **Kiểm tra probe báo cáo (chỉ đọc):**
  - Lệnh: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f1-fix1/report.md').read_text(encoding='utf-8'); assert 'PW-F1-FIX1' in t and 'R10' in t, 'report'"`
  - Mã thoát: `0`

## Phản ví dụ đã loại trừ

- Không so với ảnh thumbnail vừa trích từ chính output.
- Không hạ ngưỡng `thumbnail_min_ssim`.
- Không seek khi asset là ảnh tĩnh (kiểm chứng bằng test `test_pw_f1_thumbnail_same_still_image_keeps_first_frame`: ảnh tĩnh giữ `right_ms=None`).
- Không chấp nhận asset thumbnail khác clip hook (kiểm chứng bằng test `test_pw_f1_thumbnail_other_clip_is_asset_mismatch`: trả về `thumbnail_asset_mismatch`).

## Giới hạn

- Gói chỉ sửa nhóm lỗi R10 (phân giải hook, thumbnail) theo đúng chỉ đạo của Control. Nhóm lỗi R9 (lệnh render) và các hành vi khác không thuộc phạm vi gói này.
