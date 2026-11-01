# F-10-FIX4 — Render chuẩn hoá âm lượng loudnorm hai lượt về audio.loudness của hồ sơ

Gói: F-10-FIX4 (CP7). Quyết định user 1e4e7932 (01/11/2026): chuẩn hoá âm lượng lúc render bằng loudnorm hai lượt về `audio.loudness` đã duyệt (-16 LUFS, true peak tối đa -1,5 dBTP).

## Nhóm lỗi R40

mp4 render ra -22,2 / -22,0 / -21,9 LUFS và true peak -3,0 / -3,3 / -3,6 dBTP (số đo RG-09 CP7-10, 31/10/2026), thấp hơn mục tiêu -16 LUFS. Nguyên nhân: `render_command.py` trộn giọng và hook bằng `amix normalize=0` rồi ra thẳng `[aout]`; `audio.loudness` (-16 LUFS, tối đa -1,5 dBTP) đã nằm trong `preset.mix_rules.loudness` nhưng không được dùng. Bản sửa lấy I, TP, LRA chỉ từ preset, chèn `loudnorm` và `asetpts=N/SR/TB` sau `amix`, rồi `RealFfmpegRenderer.run` chạy lượt đo trực tiếp trên FFmpeg ghim và áp số đo cùng `linear=true` cho mọi lượt render.

## Các tệp đã sửa

- `src/render/domain/render_command.py`: `_loudness_rule` (kiểm miền loudnorm, mã lỗi `missing_...` / `invalid_...`), `_loudnorm_chain` (loudnorm và asetpts sau amix), tham số `loudnorm` của `_filter_graph`, `details['loudness']` trong fingerprint chỉ khi preset có rule.
- `src/render/adapters/real_ffmpeg_renderer.py`: `measure_loudness`, `build_measure_argv`, `parse_loudness_json`, `apply_measurement`, `LoudnessMeasurement`, `LoudnessMeasureFailed`, `_loudnorm_shape`; nối vào `_run_attempts` (lượt đo chạy trước khi tạo thư mục, không qua `command_prefix`, dùng chung `timeout_seconds`).
- `tests/unit/render/test_f10_render_command_spec.py`: thêm ca loudnorm sau amix, không có rule, khoá thiếu, ngoài miền, không phải mapping, fingerprint, mã nguồn không chứa hằng mục tiêu.
- `tests/integration/render/test_f10_fix4_render_loudness.py` (mới, `coveredIds: CT-RND-004`): test FFmpeg ghim thật, không DB, không monkeypatch.
- `docs/delivery-evidence/f-10-fix4/report.md`: báo cáo này.

## Lệnh kiểm đã chạy

Interpreter khoá của lane; `PYTEST_DEBUG_TEMPROOT` đặt theo chỉ dẫn.

| Bước | Lệnh | Mã thoát | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 8 (RED, trên mã src chưa sửa) | `pytest tests/unit/render/test_f10_render_command_spec.py tests/integration/render/test_f10_fix4_render_loudness.py tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 1 | `43 failed, 259 passed in 17.76s` |
| 13 (sau bản sửa) | cùng lệnh bước 8 | 0 | `302 passed in 23.86s` |
| 14 | `pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q -p no:cacheprovider` | 0 | `60 passed in 53.96s` |
| 15 | `pytest tests/integration/prod_wiring/test_f10_fix3_render_length.py tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p no:cacheprovider` | 0 | `49 passed in 24.69s` |
| 16 | `pytest tests/integration/render/test_f18_render_video_pipeline.py tests/integration/render/test_f20_worker_activity.py tests/integration/render/test_f09_fix1_ass_wrap.py -q -p no:cacheprovider` | 0 | `94 passed in 3.03s` |
| 17 | `pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` | 0 | `10 passed, 1 warning in 124.60s (0:02:04)` |
| 18 | `pytest tests/unit -q -p no:cacheprovider` | 0 | `7607 passed, 1 warning, 2561 subtests passed in 22.53s` |
| 19 | probe `render_command.py` | 0 | không áp dụng |
| 20 | probe `real_ffmpeg_renderer.py` | 0 | không áp dụng |
| 21 | probe hai tệp test | 0 | không áp dụng |
| 22 | probe đóng gói và import không tiền tố `src.` | 0 | không áp dụng |
| 25 | `git diff --check` | 0 | không áp dụng |

Số ca hỏng trên HEAD trước bản sửa (bước 8): 43 ca (33 ở `test_f10_render_command_spec.py`, 10 ở `test_f10_fix4_render_loudness.py`); số ca đạt sau bản sửa (bước 13): 302 trên 302. Lý do hỏng ở bước 8: các ca đo mp4 hỏng bằng AssertionError về LUFS (đo -38,6 so với -16, tức mã cũ không chuẩn hoá) hoặc ca bản trộn im lặng nhận SUCCEEDED thay vì FAILED; các ca gọi `measure_loudness`, `build_measure_argv`, `parse_loudness_json` hỏng bằng AttributeError vì hàm chưa có; các ca spec hình dạng sai hỏng vì đồ thị cũ chưa có loudnorm; các ca đơn vị hỏng vì đồ thị chưa có loudnorm hoặc chưa kiểm miền loudness.

## Bằng chứng FFmpeg thật

Số đo lấy bằng `measure_loudness` của `real_ffprobe_probe` trên mp4 render thật (FFmpeg ghim, preset bold-yellow dựng bằng `load_production_profile` và `render_config_payloads`):

- Giọng tổng hợp 4,0 s đo -38,6 LUFS. Không có rule loudness (như mã cũ): mp4 giữ -38,6 LUFS, true peak -38,2 dBTP. Có rule: mp4 đạt -16,0 LUFS, true peak -15,9 dBTP, nằm trong ±1,5 LU của -16 và dưới trần -1,5 dBTP.
- Log của `command_prefix` chỉ có đúng một lệnh (lượt render, đích `.part`, `-f mp4`), mang `measured_I/TP/LRA/thresh`, `offset` trùng số của `measure_loudness` và `linear=true`; không có `print_format`; không lệnh `null` nào đi qua prefix.
- Prefix bỏ stderr của tiến trình con (như KILL_WRAPPER) vẫn đo được và mp4 đạt mục tiêu.
- Giọng 8,008 s: 377 gói AAC, chỉ gói cuối có duration 383, mọi gói còn lại 1024; phần cuối audio kết thúc ở 8,00798 s so với giọng 8,008 s; không có lỗ im trong lời. Độ dài mp4 / video / audio là 8,008 / 8,0 / 8,008 s, bằng bản không chuẩn hoá (8,008 / 8,0 / 8,008 s). Số gói AAC khác 1024: 1 (gói cuối).
- Giọng có đỉnh (tuyến tính vượt TP): đầu vào -35,88 LUFS, true peak -6,02 dBTP; mp4 ra -16,5 LUFS, true peak -4,3 dBTP, tăng 19,4 LU (>= 10) và dưới trần.
- Hai attempt cùng spec cho cùng fingerprint, cùng số đo và PCM trùng byte; độ dài video, audio và container của cả ba mp4 trong ±0,05 s của 8,008 s.
- Preset không có rule chạy một lệnh, không có loudnorm trong đồ thị, giữ mức (trong ±2 LU của -38,6 LUFS).
- Bản trộn im lặng: FAILED `loudness_measure_failed`, prefix không chạy lệnh nào, thư mục out rỗng. Hai loudnorm, loudnorm ngoài chuỗi âm thanh, nhãn không được map: FAILED `spec_shape_invalid`, không lệnh nào chạy. JSON hỏng hoặc số -inf/nan/ngoài miền: `LoudnessMeasureFailed`. Hạn quá ngắn: `RendererTimeout`, prefix không chạy lệnh nào.

## Ghi chú lệch so với gói

Hằng tín hiệu giọng có đỉnh trong test được chỉnh (chỉ trong tệp test): `PEAKY_BASE` 0,004 thành 0,01 và `PEAKY_PEAK` 0,7 thành 0,5, `BURST_SAMPLES` giữ 96. Với bộ gốc, tiền điều kiện đạt nhưng loudnorm dynamic chỉ tăng 7,85 LU (-29,15 thành -21,3 LUFS); bộ mới tăng 19,4 LU và vẫn thoả tiền điều kiện (gain tuyến tính vượt TP + 3 dB). Ngoài ra không có lệch nào.

## Backlog ngoài phạm vi

- Đo lại RG-09 thật (CP7-10) sau khi gói được tích hợp.
- Cổng AUDIO_MIX_QUALITY vẫn là cảnh báo (`warn_only`), không đổi phép đo hay ngưỡng.
- Không chuẩn hoá hậu kỳ trên mp4 (không mã hoá AAC lần hai).
