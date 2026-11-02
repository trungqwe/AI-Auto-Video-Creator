# Báo cáo bằng chứng E-16-FIX3

## Môi trường

- Interpreter: `python` (Python 3.13.12), chạy `python -m pytest` từ thư mục worktree lane-e-16-fix3.
- Baseline: 35db23c6313579fa0df42ad0935d4cda5c6e4ca3
- Nguồn quyền: quyết định của user CLOSURE_NOTE CP7/RG-09, giữ mức kẹp 0,85-1,15 và khoảng 61-70 s.

## Lỗi gốc

- Nhóm lỗi: OI-CP7-11-Q3 (lô 71973394, CP7-11 lượt 3).
- Hiện tượng: video 7 và 68 hỏng ở stage tts với `voice_duration_out_of_range`. Lần đọc đầu 54,763 s và 54,443 s; lần đọc lại duy nhất ở mức kẹp 0,85 được 60,715 s và 60,501 s, thiếu 285 ms và 499 ms so với 61 000 ms.
- Control đo trên chính hai take bị loại: thêm im lặng số ở cuối không làm Whisper viết thêm từ, số từ nghe giữ nguyên, align đạt.
- Gốc: ước lượng độ dài kịch bản theo từ, xử lý ở gói D-08-FIX1. Gói này chỉ là lưới an toàn cho đuôi ngắn.

## RED

- Bước 4. Lệnh: `python -m pytest tests/integration/voice/test_e16_fix3_tail_pad.py -q -p no:cacheprovider` (pipeline hoàn nguyên tạm về HEAD, `tail_pad.py` đã có).
  - Exit code: 1
  - Dòng tóm tắt nguyên văn: `1 failed, 4 passed in 0.23s`
  - Loại lỗi: assertion/exception đúng oracle: `test_short_reread_gets_trailing_silence_and_passes` nhận `VoiceDurationRejected: voice_duration_out_of_range: 59620`; không phải lỗi import hay setup.

## GREEN

- Lệnh: `python -m pytest tests/integration/voice/test_e16_fix3_tail_pad.py -q -p no:cacheprovider` — Exit code 0, dòng tóm tắt nguyên văn: `5 passed in 0.09s`
- Lệnh: `python -m pytest tests/integration/voice tests/unit/voice/test_e14_tts_route_invocation.py tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider` — Exit code 0, `244 passed in 2.80s`
- Lệnh: nhóm adapt/wire/PW-E2 voice — Exit code 0, `232 passed, 89 subtests passed in 17.48s`
- Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider` — Exit code 0, `11 passed in 170.08s (0:02:50)`
- Lệnh: `python -m pytest tests/unit -q -p no:cacheprovider` — Exit code 0, `7784 passed, 2561 subtests passed in 23.83s`

## Thay đổi

- `src/voice/domain/tail_pad.py` (mới): `TAIL_PAD_MAX_MS = 1500`, `TAIL_PAD_MARGIN_MS = 100`, `plan_tail_pad`, `pad_wav_tail`; chỉ import `struct`.
- `src/voice/application/voice_pipeline.py`: import, `WARNING_TAIL_PAD_APPLIED = 'tail_pad_applied'` nối sau `speed_fit_applied`, đệm sau lần đọc lại duy nhất trong nhánh speed fit, `usage_metrics` thêm `tail_pad_ms` và `reread_duration_ms`; `_judged` của lần đọc lại ghi `reread_duration_ms`.
- `tests/integration/voice/test_e16_fix3_tail_pad.py` (mới): 5 test.
- `docs/delivery-evidence/e-16-fix3/report.md` (mới): báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | không output |
| 2 | pytest integration/voice + e14 + e20 | 0 | `244 passed in 2.80s` |
| 3 | pytest adapt/e, config, wire, pw_e2_voice_ports, e01 | 0 | `232 passed, 89 subtests passed in 17.48s` |
| 4 | pytest test_pw_e2e_batch_video.py | 0 | `11 passed in 170.08s (0:02:50)` |
| 5 | pytest tests/unit | 0 | `7784 passed, 2561 subtests passed in 23.83s` |
| 6 | probe tail_pad.py, pipeline, profile.json | 0 | không AssertionError |
| 7 | probe tệp test mới | 0 | đạt |
| 8 | probe speed_fit còn nguyên | 0 | đạt |
| 9 | probe PW-E2 | 0 | đạt |
| 10 | probe layout gói và import root | 0 | đạt |
| 11 | probe báo cáo | 0 | đạt |

## Kết quả từng tiêu chí

- Lần đọc đầu và nhánh không có speed fit không được đệm: `test_first_take_and_long_reread_are_never_padded` (take 60 000 ms không speed fit vẫn bị loại, chỉ một lần đọc).
- Giọng quá dài không được đệm: cùng test (base 90 000, vẫn `VoiceDurationRejected`).
- Thiếu hơn 1,5 s không được đệm: `test_shortfall_over_the_cap_is_still_rejected` và `test_plan_tail_pad_only_for_a_short_shortfall`.
- Đệm tối đa 1,5 s, chỉ im lặng số: `test_pad_wav_tail_appends_zero_samples_and_rewrites_sizes` (phần thêm toàn byte 0, ghi lại kích thước RIFF/data, ValueError ngoài (0, 1500]).
- Ca thật: `test_short_reread_gets_trailing_silence_and_passes` (scales [1.0, 0.85], actual 61100, `tail_pad_ms` 1480).
- Không có lần đọc thứ ba: kiểm bằng `engine.scales` chỉ có hai phần tử.
- Khoảng 61-70 s, mức kẹp 0,85-1,15, `profile.json`: không đổi (probe bước 6).
- `tail_pad.py` không I/O (chỉ import `struct`); không sửa test cũ; không thêm thư viện.
- Test mới không DB, không mock, không monkeypatch; fail với mã cũ ở `test_short_reread_gets_trailing_silence_and_passes` (RED ở trên).

## Ghi chú

- Lưới an toàn cho đuôi ngắn; video thêm tối đa 1,5 s cuối không lời.
- `build_gap_report` ghi khoảng im cuối vào `alignment_gaps` (chỉ thông tin).
- Bản ghi `tts_invocation` của lần đọc lại giữ `output_fingerprint` của audio chưa đệm, còn `voice_hash` là của audio đã đệm.
- `pad_wav_tail` ném `ValueError` với WAV không PCM và pipeline không bắt.
- `test_pw_e3_media_inputs` không chạy (cần Postgres, ngoài danh sách lệnh kiểm).

## Mục mở

OI-CP7-11-Q3: lưới đệm đuôi chỉ là biện pháp an toàn; gốc là ước lượng độ dài kịch bản theo từ, xử lý ở gói D-08-FIX1.
