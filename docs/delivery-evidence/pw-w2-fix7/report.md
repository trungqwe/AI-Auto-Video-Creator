# PW-W2-FIX7: QC production đo AUDIO_MIX_QUALITY thật (loudness, true peak), chỉ cảnh báo (nhóm lỗi R39, OI-PW-F2-03)

## Nhóm lỗi

Nhóm lỗi R39, RG-09 thật của CP7-10 ngày 31/10/2026: QC của ba job `0f1a5b7c:video:0`, `7c25d280:video:2`, `fea412ea:video:2` có warnings `AUDIO_MIX_QUALITY:not_evaluated`.

- Gốc: `quality_inputs` trong `src/controlplane/api/wiring/render.py` không trả `warning_results`, nên `quality_report` ghi `not_evaluated` với lý do `INPUT_NOT_READY`.
- `audio_mix_result` và `measure_loudness` trước đây chỉ được gọi trong test PW-F2; ngưỡng đã được seed vào QualityPolicy.
- Số đo ba mp4 do Control cung cấp trong đề bài (không phải Worker đo): -22,2 / -22,0 / -21,9 LUFS; true peak -3,0 / -3,3 / -3,6 dBTP.

## Tệp đã sửa

- `src/render/adapters/audio_mix_gate.py` (mới)
- `src/render/application/inspect_output.py`
- `src/controlplane/api/wiring/render.py`
- `tests/integration/render/test_f19_inspect_output_pipeline.py`
- `tests/integration/prod_wiring/test_pw_w2_fix7_audio_mix.py` (mới)
- `tests/integration/prod_wiring/test_pw_e2e_batch_video.py`
- `docs/delivery-evidence/pw-w2-fix7/report.md` (mới)

## Thay đổi

- `AudioMixGate`: đọc ngưỡng từ `policy.thresholds['AUDIO_MIX_QUALITY']`, thiếu hoặc không phải số thì trả `()`; ref tương đối giải theo `staging_root`; `verify_ffmpeg_pin` rồi `measure_loudness`; `FfmpegPinRejected` thì `LoudnessStats()` (kết quả `not_evaluated`, `loudness_not_measured`, không ném); trả đúng một `audio_mix_result`.
- `OutputPipeline.warning_gates`: gọi đúng một lần trong `_build_report` với `(output_ref, package, policy)`; phát lại theo `operation_key` không gọi; phần tử không phải `GateResult` của cổng WARNING thì `ValueError`; cổng đã có trong `command.warning_results` thì bỏ kết quả đo (bên gọi thắng).
- `render_activity_deps` truyền `warning_gates=AudioMixGate(...)` với bốn từ khoá; không đọc DB lúc dựng.
- Không đổi ngưỡng, profile, QualityPolicy, seed, đồ thị âm thanh; `report.passed` không đổi vì cổng là WARNING.

## Lệnh kiểm đã chạy

| STT | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 7 (RED) | pytest nhóm F-19 + fix7 + PW-F2 + FIX6 (trước cài đặt) | 2 | `ModuleNotFoundError: No module named 'render.adapters.audio_mix_gate'` ở collect; `1 error in 3.75s`. Lỗi collect làm dừng cả phiên nên TypeError của F-19 chưa hiện ở lần chạy này |
| 8 (RED) | pytest `test_pw_e2e_batch_video.py` (trước cài đặt) | 1 | `AssertionError: assert 'NOT_EVALUATED' in ('PASSED', 'FAILED')` tại `assert_audio_mix_measured`; `1 failed, 9 passed in 136.45s (0:02:16)` |
| 14 | pytest nhóm F-19 + fix7 + PW-F2 + FIX6 | 0 | `73 passed in 31.46s` |
| 15 | launcher_def + fix5_bootstrap + adapt_wire_services | 0 | `156 passed in 25.30s` |
| 16 | pw_f4_render_worker + pw_f1_inspector_visual | 0 | `60 passed in 66.57s (0:01:06)` |
| 17 | f18 + f20 + adapt_f_render | 0 | `141 passed in 4.44s` |
| 18 | `test_pw_e2e_batch_video.py` | 0 | `10 passed in 182.35s (0:03:02)` |
| 19 | `tests/unit` | 0 | `7572 passed, 2561 subtests passed in 30.49s` |
| 20-23 | bốn probe `python -c` (adapter, wiring, pipeline và e2e, bố cục CP2A-LAYOUT) | 0 | không có đầu ra |
| 25 | probe report | 0 | xem bước 25 trong lệnh kiểm |
| 26 | `git diff --check` | 0 | không cảnh báo (chạy lại sau khi ghi report, trước commit) |
| 27 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_fix7_audio_mix.py tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -rP -p no:cacheprovider` | 0 | `18 passed, 1 warning in 147.41s (0:02:27)`; chạy lại sau khi thêm dòng in AUDIO_MIX_EVIDENCE, khắc phục F1 |
| 28 | `git diff --check` | 0 | không cảnh báo (chạy sau khi sửa report khắc phục F1) |

## Dòng tổng kết nguyên văn của pytest

- Nhóm 2 (bước 14): `73 passed in 31.46s`
- Nhóm 3 (bước 15): `156 passed in 25.30s`
- Nhóm 4 (bước 16): `60 passed in 66.57s (0:01:06)`
- Nhóm 5 (bước 17): `141 passed in 4.44s`
- e2e (bước 18): `10 passed in 182.35s (0:03:02)`
- tests/unit (bước 19): `7572 passed, 2561 subtests passed in 30.49s`

## Bằng chứng số đo AUDIO_MIX_QUALITY (khắc phục F1)

Test fix7 và e2e nay in dòng `AUDIO_MIX_EVIDENCE`; các dòng dưới đây lấy từ lần chạy `-rP` ở bước 4 (mã thoát 0). Chỉ phần đường dẫn thư mục tạm tuyệt đối trong `evidence_ref` được thay bằng `<tmp>`; mọi số và trạng thái giữ nguyên văn.

```text
AUDIO_MIX_EVIDENCE measured integrated_lufs=-28.4 true_peak_dbtp=-26.9
AUDIO_MIX_EVIDENCE gate status=passed reason=None measured_value=-28.4 evidence_ref=<tmp>\test_measured_loudness_inside_0\sample\out\final.mp4:I=-28.4LUFS:TP=-26.9dBTP
AUDIO_MIX_EVIDENCE gate status=failed reason=loudness_out_of_target measured_value=-28.4 evidence_ref=<tmp>\test_loudness_far_from_target_0\sample\out\final.mp4:I=-28.4LUFS:TP=-26.9dBTP
AUDIO_MIX_EVIDENCE gate status=failed reason=true_peak_above_limit measured_value=-28.4 evidence_ref=<tmp>\test_true_peak_above_the_limit0\sample\out\final.mp4:I=-28.4LUFS:TP=-26.9dBTP
AUDIO_MIX_EVIDENCE gate status=passed reason=None measured_value=-28.4 evidence_ref=out/qc-fix7.mp4:I=-28.4LUFS:TP=-26.9dBTP
AUDIO_MIX_EVIDENCE gate status=not_evaluated reason=loudness_not_measured measured_value=None evidence_ref=<tmp>\test_a_wrong_pin_or_a_missing_0\sample\out\final.mp4
AUDIO_MIX_EVIDENCE gate status=not_evaluated reason=loudness_not_measured measured_value=None evidence_ref=<tmp>\test_a_wrong_pin_or_a_missing_0\missing.mp4
AUDIO_MIX_EVIDENCE e2e status=failed reason=loudness_out_of_target measured_value=-17.8 evidence_ref=out/422650a2-eec4-4334-87dd-5f710813dea7_video_0_render_render_video_0_r1.mp4:I=-17.8LUFS:TP=-12.7dBTP
AUDIO_MIX_EVIDENCE e2e status=failed reason=loudness_out_of_target measured_value=-17.8 evidence_ref=out/7ab77e26-cb23-4ca1-982e-615f61308708_video_0_render_render_video_0_r1.mp4:I=-17.8LUFS:TP=-12.7dBTP
```

Mẫu lavfi của test FFmpeg thật đo được -28.4 LUFS và -26.9 dBTP. Trong e2e, `AUDIO_MIX_QUALITY` đo được ở lô 1 và lô 2 đều là failed `loudness_out_of_target` (cảnh báo, -17.8 LUFS, -12.7 dBTP); video vẫn COMPLETED và `qr['passed']` vẫn True vì cổng chỉ là WARNING.

## Mục mở

- Với âm thanh hiện tại, mọi video sẽ ghi `AUDIO_MIX_QUALITY` failed `loudness_out_of_target` (khoảng -22 LUFS), chỉ là cảnh báo.
- Chuẩn hoá âm lượng chờ user quyết.
- Thêm khoảng 0,4 s đo ebur128 cho mỗi video.
- VISUAL_CONTINUITY vẫn `not_evaluated` (ngoài phạm vi).

## Giới hạn

- Không chạm ngoài bảy owned paths; không monkeypatch mã production.
- Không đổi ngưỡng, profile, QualityPolicy, seed hay đồ thị âm thanh.
- RED của `test_pw_w2_fix7_audio_mix.py` là lỗi collect do thiếu adapter; RED assert thật nằm ở e2e (bước 8) và F-19 (chưa quan sát riêng TypeError do lỗi collect chặn phiên ở bước 7).
