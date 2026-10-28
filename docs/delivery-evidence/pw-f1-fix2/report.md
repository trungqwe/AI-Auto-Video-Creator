# PW-F1-FIX2 — INFERENCE_DISCLOSURE_PRESENT đo đúng hàng của style Disclosure trong ASS

## Nhóm lỗi

- Mã gói: `PW-F1-FIX2`
- Nhóm lỗi: `R11`
- Chi tiết lỗi: `_disclosure` so YAVG của |khung giữa cửa sổ − khung baseline| trên cả `settings.disclosure_band` (render/adapters/real_output_inspector.py:588-604; frame_probe.py:57-90 lấy trung bình cả band); band production cố định 0.10–0.25, ngưỡng 5.0 (controlplane/api/wiring/render.py:766-767), trong khi dòng disclosure (ass_manifest.py:104-147, 160-176: Fontsize 40, Alignment 8, MarginV 240 trên PlayResY 1920) chỉ chiếm khoảng 0.125–0.175 chiều cao. Khi nền ở khung mẫu và baseline giống nhau (một ảnh bài lặp qua các segment theo F-10-FIX1, cảnh tĩnh), disclosure đã burn-in chỉ cho 4.40 < 5.0 nên cổng FAIL sai (đo bằng FFmpeg ghim trên output HEAD b8b46c6 dựng từ ASS thật của PW-F3: band 0.10–0.25 = 4.40; band 0.12–0.17 = 12.96, khung không có disclosure 1.31). Đây là nguyên nhân tests/integration/prod_wiring/test_pw_f4_render_worker.py::test_inspect_output_disclosure_gate_follows_the_script_segments hỏng từ F-10-FIX1 (trước đó PASS chỉ nhờ nền chuyển động).

## Cách sửa

- Inspector đọc thêm `[Script Info]` `PlayResY` và dòng `Style: Disclosure` trong `[V4+ Styles]` của chính tệp ASS mà nó đã đọc (`real_output_inspector.py:422`, theo `Format` của section):
  - Với Alignment 7/8/9: `top = MarginV / PlayResY`, `bottom = (MarginV + 2 * (Fontsize + 2 * Outline)) / PlayResY`.
  - Với Alignment 1/2/3: `bottom = 1 - MarginV / PlayResY`, `top = bottom - 2 * (Fontsize + 2 * Outline) / PlayResY`.
  - Cắt về khoảng `[0.0, 1.0]`.
- Thêm hàm thuần `disclosure_band_from_ass(text: str) -> Band | None` và hàm trợ lực `_ass_number(value: str) -> float | None`.
- Thiếu style, thiếu PlayResY, giá trị không phải số, Alignment 4/5/6, hoặc band sau khi cắt không hợp lệ (`top >= bottom`, `Band.__post_init__` ném `ValueError`) thì hàm trả `None` và caller dùng lại `settings.disclosure_band` như cũ.
- Tách phương thức `_ass_text(self, package: RenderPackageRecord) -> str | None` trong `RealOutputInspector` để đọc ASS một lần, tái sử dụng cho cả `_dialogues` và `_disclosure_band`.
- Thêm phương thức `_disclosure_band(self, ass_text: str | None) -> Band` vào `RealOutputInspector`.
- Thêm tham số `band: Band` vào chữ ký của `_disclosure`, và truyền `top=band.top`, `bottom=band.bottom` vào lời gọi `self._probe.band_difference(...)`.
- Xuất 'disclosure_band_from_ass' trong `__all__`.
- Giữ nguyên ngưỡng `disclosure_min_difference`, `baseline_ms`, subtitle và các gate khác; không thêm hằng ngưỡng vào mã.

## Tệp đã sửa

1. `src/render/adapters/real_output_inspector.py`
2. `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py`
3. `docs/delivery-evidence/pw-f1-fix2/report.md`

## Lệnh kiểm đã chạy

- **Bước RED (trước khi sửa mã production):**
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider`
  - Mã thoát: `1`
  - 2 test fail do sai oracle:
    - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py::test_pw_f1_fix2_static_background_disclosure_passes_with_production_band`
    - `tests/integration/prod_wiring/test_pw_f1_inspector_visual.py::test_pw_f1_fix2_disclosure_band_source[style_band_beats_settings_band]`
  - Dòng tổng kết pytest nguyên văn:
    ```
    2 failed, 21 passed in 13.17s
    ```

- **Bước GREEN (sau khi sửa mã production):**
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider`
  - Mã thoát: `0`
  - Dòng tổng kết pytest nguyên văn:
    ```
    44 passed in 10.16s
    ```

- **Lệnh kiểm bắt buộc cả hai tệp (F1 + F4):**
  - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider`
  - Mã thoát: `0`
  - Dòng tổng kết pytest nguyên văn:
    ```
    60 passed in 57.57s
    ```

- **Kiểm tra định dạng và khoảng trắng (bước 13):**
  - Lệnh: `git diff --check`
  - Mã thoát: `0`

- **Kiểm tra probe báo cáo chỉ đọc (bước 14):**
  - Lệnh: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f1-fix2/report.md').read_text(encoding='utf-8'); assert 'PW-F1-FIX2' in t and 'R11' in t, 'report'"`
  - Mã thoát: `0`

## Phản ví dụ đã loại trừ

- Không hạ `disclosure_min_difference`.
- Không đổi nền `testsrc2` của V2 trong test PW-F4 để nền khác nhau.
- Không sửa band cứng trong `render.py` hay `SETTINGS` của test.
- Không đặt hằng band trong inspector.
- Không đo max thay vì sửa band (có ca kiểm chứng `test_pw_f1_fix2_render_without_disclosure_dialogue_fails`: video render từ ASS bỏ dòng Dialogue Disclosure cho `visible=False` và gate FAILED).
- Không bỏ overlay hook của F-10-FIX2.

## Giới hạn

- Gói do Control lập (quyết định user 22/10/2026: việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói). Test đầu-cuối PW-E2E sau đợt sửa 2 tới stage qc thì quality_gates_failed (Worker PW-E2E báo BLOCKED 28/10/2026, candidate c5d235f); bản rà chỉ đọc của Control trên HEAD c5d235f xác định nhóm R9 (lệnh render) và R10 (phân giải hook, thumbnail). Gói này sửa đúng nhóm lỗi R11 được nêu, không đổi hành vi khác.
