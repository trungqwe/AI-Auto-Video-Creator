# PW-W2-FIX6: QC production đo VOICE_AUDIBLE thật bằng probe theo package (nhóm lỗi R35, OI-PW-F2-03)

## Nhóm lỗi

Nhóm lỗi R35, RG-09 thật của CP7-10 ngày 31/10/2026:

- Ba job `0f1a5b7c:video:0`, `7c25d280:video:2`, `fea412ea:video:2` FAILED_FINAL ở `qc/inspect_output` với `quality_gates_failed`, `blocking_gates ['VOICE_AUDIBLE']`, `gate_count` 13.
- Gốc: probe QC dựng thiếu `ffmpeg_path` nên không đo `audio_level` và `severe_audio_errors`; `VOICE_AUDIBLE` thành `missing_measurement` với mọi video.
- PW-E2E che lỗi bằng cách gán đè `probe._ffmpeg` và `probe._lock`.
- Control đo lại ba mp4 bằng FFmpeg ghim: -25,2 / -24,8 / -24,9 dB trong cửa sổ lời; ngưỡng là lớn hơn -40,0 dB.

## Tệp đã sửa

- `src/render/application/inspect_output.py` (sửa)
- `src/controlplane/api/wiring/render.py` (sửa)
- `tests/integration/render/test_f19_inspect_output_pipeline.py` (sửa)
- `tests/integration/prod_wiring/test_pw_w2_fix6_qc_probe.py` (mới)
- `tests/integration/prod_wiring/pw_e2e_support.py` (sửa)
- `tests/integration/prod_wiring/test_pw_e2e_batch_video.py` (sửa)
- `docs/delivery-evidence/pw-w2-fix6/report.md` (mới)

## Thay đổi

- `OutputPipeline` nhận thêm tham số từ khoá `probe_for` (mặc định `None`); `_build_report` dùng `probe_for(package)` khi có, ngược lại dùng probe chung. Phát lại theo `operation_key` trả về trước `_build_report` nên không gọi `probe_for`.
- `wiring/render.py`: hàm công khai `build_qc_probe` (FFmpeg ghim, lock, cửa sổ lời) và `qc_probe_for` trong `render_activity_deps`, lấy cửa sổ lời từ `inspector_factory(package).speech_windows(package)`; truyền `probe_for=qc_probe_for` vào `OutputPipeline`. Lúc dựng không đọc DB.
- `pw_e2e_support.py`: xoá hai dòng gán đè `probe._ffmpeg`, `probe._lock`.
- Test mới: ba ca F-19 (bộ nhớ), ba ca `test_pw_w2_fix6_qc_probe.py` (FFmpeg ghim thật, không DB), và kiểm VOICE_AUDIBLE passed (reason None, measured_value là số, báo cáo passed) sau cả hai `quality_report` trong PW-E2E.

## Mức giọng đo được

- Test thật `test_pw_w2_fix6_qc_probe.py` (mẫu lavfi của PW-F2, ngưỡng mẫu `min_voice_level` -31,0 dB): cửa sổ lời `((200, 2500), (3000, 4000))` đo -30,1 dB, VOICE_AUDIBLE passed; đo cả luồng (không cửa sổ) -32,7 dB, failed `voice_below_min_level`.
- Ngưỡng production không đổi: lớn hơn -40,0 dB (`profile.json`); ba mp4 thật do Control đo -25,2 / -24,8 / -24,9 dB.

## Lệnh kiểm đã chạy

| STT | Lệnh | Mã thoát | Dòng tổng kết |
| --- | --- | --- | --- |
| 3 (RED) | pytest F-19 + `test_pw_w2_fix6_qc_probe.py` | 2 | `1 error in 3.98s` (lỗi collect `cannot import name 'build_qc_probe'`) |
| 3 (RED) | pytest riêng F-19 | khác 0 | `35 failed, 3 passed in 0.78s` (`QcRig` truyền `probe_for` nên `TypeError ... unexpected keyword argument 'probe_for'` ở mọi ca dùng rig) |
| 6 (RED) | pytest `test_pw_e2e_batch_video.py` (đã bỏ gán đè, chưa sửa wiring) | khác 0 | `3 failed, 7 passed in 107.47s (0:01:47)` (`qc/inspect_output quality_gates_failed`) |
| 11 | pytest F-19 + fix6 + PW-F2 audio | 0 | `59 passed in 27.15s` |
| 12 | pytest PW-W2, PW-W2-FIX5, ADAPT-WIRE | 0 | `156 passed in 18.60s` |
| 13 | pytest PW-F4, PW-F1 | 0 | `60 passed in 63.97s (0:01:03)` |
| 14 | pytest F-18, F-20, ADAPT-F | 0 | `141 passed in 4.42s` |
| 15 | pytest PW-E2E batch video | 0 | `10 passed in 142.03s (0:02:22)` |
| 16 | pytest `tests/unit` | 0 | `7544 passed, 2561 subtests passed in 28.90s` |
| 18-25 | các probe `python -c` (wiring, inspect_output, e2e, wiring toàn thư mục, waiting_port, rig, package-dir, report) | 0 | không có đầu ra, tất cả assert qua |
| 26 | `git diff --check` | 0 | không cảnh báo |

## Dòng tổng kết nguyên văn của pytest

- Bước 11: `59 passed in 27.15s`
- Bước 12: `156 passed in 18.60s`
- Bước 13: `60 passed in 63.97s (0:01:03)`
- Bước 14: `141 passed in 4.42s`
- Bước 15: `10 passed in 142.03s (0:02:22)`
- Bước 16: `7544 passed, 2561 subtests passed in 28.90s`

## Mục mở

- `AUDIO_MIX_QUALITY` chưa nối `audio_mix_result`.
- Đuôi giọng bị cắt khi timeline ngắn hơn giọng (`render_command.py:360-371, 411-414`).
- Dòng Disclosure tràn mép khung.
- ASS không tìm thấy thì `speech_windows` rỗng và probe đo cả luồng; khi đó SUBTITLE_BURNED_IN cũng hỏng nên báo cáo vẫn không đạt.

## Giới hạn

- Không chạm ngoài bảy owned paths; không monkeypatch mã production; không đổi ngưỡng hay profile.
- RED của `test_pw_w2_fix6_qc_probe.py` là lỗi import `build_qc_probe` (lỗi collect), không phải assert đo âm thanh.
- RED của F-19 làm hỏng cả các ca cũ dùng `QcRig` (vì rig truyền `probe_for`), không chỉ hai ca mới.
