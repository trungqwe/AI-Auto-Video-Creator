# Báo cáo bằng chứng E-16-FIX2

## Môi trường

- Interpreter: C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe (Python 3.13.12), chạy `python -m pytest` từ thư mục worktree lane-e-16-fix2.
- Baseline: 2cafbc8c7144255cccf28b79d7c05d5db48edb58
- Nguồn quyền: quyết định của user ghi trong sổ user_decisions, CLOSURE_NOTE CP7/RG-09 ngày 31/10/2026 (phương án A: E đọc lại đúng một lần với tốc độ khớp, kẹp 0,85-1,15).

## Lỗi gốc

- Nhóm lỗi: R32 (RG-09 thật của CP7-10, 31/10/2026).
- Hiện tượng: job FAILED_FINAL ở stage tts, CreateVoiceTrack báo `voice_duration_out_of_range`.
- Nguyên nhân: Kokoro af_heart đọc script tin ở 128-158 từ/phút trong khi D ước lượng ở 150 từ/phút, nên giọng dài 72-77 s, vượt khoảng 61-70 s; E không có cách nào đưa giọng về khoảng.
- Cách sửa: khi giọng lần đầu lệch khoảng, CreateVoiceTrack đọc lại đúng một lần với hệ số tốc độ do `plan_speed_fit` tính (kẹp theo khoá profile `voice.speed_fit`, 0,85-1,15, duration_slope 0,56 đo trên đường production). Không có lượt ba; lệch lần hai thì `VoiceDurationRejected`.

## RED

- Bước 6. Lệnh: `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py tests/unit/voice/test_e14_tts_route_invocation.py tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider`
  - Exit code: 1
  - Dòng tóm tắt nguyên văn: `8 failed, 141 passed in 2.34s`
  - Loại lỗi: assertion và TypeError do `speed_scale` chưa tồn tại (ví dụ `run_tts_attempts() got an unexpected keyword argument 'speed_scale'`, `FakeTtsEngine.synthesize() got an unexpected keyword argument 'speed_scale'`); không có ImportError hay lỗi collection.
- Bước 7. Lệnh: `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_joins.py -q -p no:cacheprovider`
  - Exit code: 1
  - Dòng tóm tắt nguyên văn: `9 failed, 5 passed in 3.16s`
  - Loại lỗi: TypeError `RealKokoroTts.synthesize() got an unexpected keyword argument 'speed_scale'`; các test joins cũ vẫn pass.

## GREEN

- Bước 14. Lệnh: `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py tests/unit/voice/test_e14_tts_route_invocation.py tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `149 passed in 2.16s`
- Bước 22. Lệnh: `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_joins.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `187 passed in 12.29s`
- Bước 23. Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `19 passed in 121.71s (0:02:01)`

## Thay đổi

- src/voice/domain/speed_fit.py (mới): `SpeedFitPolicy` (frozen, kw_only, ValueError nêu tên trường) và `plan_speed_fit` thuần, không I/O.
- src/voice/ports/tts.py: `TtsEnginePort.synthesize` thêm `speed_scale` kw-only mặc định 1.0.
- src/voice/adapters/real_kokoro_tts.py: nhận `speed_scale`, tốc độ hiệu dụng `round(config.speed * speed_scale, 4)`, ngoài [0,5; 2,0] thì `speed_out_of_range` không retry và không gọi model; `usage_metrics` thêm `speed` và `speed_scale`; `_revision` không đổi.
- src/voice/adapters/fake_tts.py: nhận `speed_scale`, WAV dài `max(1, round(duration_ms / speed_scale))`, chỉ ghi `speed_scale` vào usage_metrics khi khác 1.0.
- src/voice/domain/tts_invocation.py: `fingerprint_tts_input` và `run_tts_attempts` nhận `speed_scale=None`; None giữ fingerprint cũ và gọi engine đúng 3 đối số vị trí.
- src/voice/application/voice_pipeline.py: `CreateVoiceTrackCommand.speed_fit`, lượt đọc lại một lần, `_judged`, `VoiceDurationRejected.first_finding`, warnings `speed_fit_applied`, usage_metrics `speed_scale` và `first_take_duration_ms`.
- src/voice/adapters/activity_inputs.py: `VoiceSettings.speed_fit` truyền vào command.
- src/controlplane/api/wiring/production_profile.py: `voice.speed_fit` vào REQUIRED_PARAMETERS (84), `VoiceConfig` thêm ba trường, kiểm tra dạng và biên.
- src/controlplane/api/wiring/voice.py: dựng `SpeedFitPolicy` từ ba trường cho `VoiceSettings`.
- tools/launcher/prod/profile.json: thêm `voice.speed_fit` (0.85, 1.15, 0.56, basis DECIDED), `meta.revision` 2 thành 3.
- docs/implementation/e/plan.md: đính chính (n), ghi chú TEST-OPEN-003 và dòng D8 Khớp tốc độ voice.
- tests/integration/voice/test_e16_voice_timing_pipeline.py, tests/unit/voice/test_e14_tts_route_invocation.py, tests/integration/adapt/e/test_adapt_e_tts_joins.py, tests/integration/adapt/config/test_adapt_config_profile.py, tests/integration/adapt/wire/test_adapt_wire_services.py: test mới và test sửa theo yêu cầu.
- docs/delivery-evidence/e-16-fix2/report.md: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | không output |
| 2 | pytest e16 + e14 + e20 (bước 14) | 0 | `149 passed in 2.16s` |
| 3 | pytest joins + aligner + config + wire (bước 22) | 0 | `187 passed in 12.29s` |
| 4 | pytest PW-E3 + PW-E2E (bước 23) | 0 | `19 passed in 121.71s (0:02:01)` |
| 5 | probe `speed_fit.py` có `plan_speed_fit` và `SpeedFitPolicy` | 0 | đạt |
| 6 | probe `voice_pipeline.py` có `speed_fit_applied` và `plan_speed_fit` | 0 | đạt |
| 7 | probe `profile.json` voice.speed_fit đúng giá trị, basis DECIDED | 0 | đạt |
| 8 | probe `plan.md` có `speed_fit`, `0,85`, `1,15` | 0 | đạt |
| 9 | probe test wire không ghim revision 2 hay 3 | 0 | đạt |
| 10 | probe `report.md` có `E-16-FIX2` và `R32` | 0 | đạt |

## Ánh xạ phản ví dụ -> test

- Đọc lại quá một lần: test_speed_fit_second_take_still_out_of_range_is_rejected_after_two_takes
- Tốc độ lấy từ request: test_speed_scale_multiplies_configured_speed_and_keeps_revision
- Kẹp khác 0,85-1,15: test_plan_speed_fit_centres_on_range_and_clamps
- Công thức 1/speed (bỏ duration_slope): test_plan_speed_fit_centres_on_range_and_clamps (so với duration_slope 1.0)
- Đổi `_revision`: test_speed_scale_multiplies_configured_speed_and_keeps_revision
- Ghim cứng revision: test_profile_loads_typed_values
- speed_fit None: test_speed_fit_none_keeps_old_behaviour
- Replay: test_speed_fit_replay_adds_no_engine_call

## Ghi chú

- test_attempt_limits_have_no_default_in_source chỉ miễn đúng tham số kw-only `speed_scale` (mặc định None, không phải giới hạn attempt).
- docs/runbook/runbook-v1.md nằm ngoài owned paths nên không sửa.
- Kẹp 0,85-1,15 cứu được lượt đầu khoảng 55-75,6 s; ngoài đó job vẫn FAILED_FINAL.

## Mục mở

- `duration_slope` 0,56 chỉ đo trên 2 script và giọng af_heart; đổi giọng (hoặc đổi engine) phải đo lại độ dốc rồi cập nhật `voice.speed_fit` bằng revision profile mới.
