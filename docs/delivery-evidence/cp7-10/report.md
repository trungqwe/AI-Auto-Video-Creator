# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026. Lane `lane-cp7-10`, interpreter khoá `.local-tools\runtime\8715e538\venv\Scripts\python.exe`. HEAD nền khi chạy là `3b495cd` (kèm thay đổi chưa commit của lượt này trong driver và test).

## Lệnh đã chạy

- Commit trước: `3b495cd`. Lần chạy ngăn xếp thật ở commit đó đã BLOCKED vì không bắt được URL /launch (launcher start exit 0 nhưng không có URL). Lượt này là lần chạy đúng một lần mới.
- Thay đổi lượt này: thêm `format_start_output` (BLOCKED nêu đuôi stdout đã che của `launcher start`, nhãn `worker_already_running`); gọi `stop_until_exited()` trước lần start đầu trong `run_batch` và ghi `pre_stop_attempts`; thêm hai test thuần mới; thêm dòng emit `pre_stop_attempts`.
- `git diff --check` (trước khi chạy ngăn xếp thật): exit 0.
- Test thuần (`-k unit`, không chạm ngăn xếp): 19 passed, 11 deselected, exit 0.
- `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (ngăn xếp thật, đúng một lần): 19 passed, 0 failed, 11 errors, exit code 1. Cả 11 error là lỗi setup của fixture `batch_run` cùng một nguyên nhân. Thời gian chạy: không ghi lại được (dòng đo thời gian bị cắt khỏi output của công cụ); không chạy lại để đo.

## Trạng thái

0/10 PASS. Lần này đã qua được bước start và seed, job chạy tới stage `tts` rồi FAILED_FINAL, nên không mục RG-09 nào được chứng minh.

## Kết quả

RG-09.stages_succeeded: BLOCKED
RG-09.no_fake_adapters: BLOCKED
RG-09.qc_hard_gates: BLOCKED
RG-09.cloud_verified_before_count: BLOCKED
RG-09.cleanup_after_verify: BLOCKED
RG-09.plan_unchanged: BLOCKED
RG-09.resume_300s: BLOCKED
RG-09.no_rerun_completed: BLOCKED
RG-09.trace_complete: BLOCKED
RG-09.secret_scan: BLOCKED

## Chi tiết đo

Blocker nguyên văn (đã che): `BLOCKED: job kết thúc ở FAILED_FINAL stage=tts status=FAILED_FINAL activity=CreateVoiceTrack code=voice_duration_out_of_range field_errors={}; không thử lại, không tạo lô khác; render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED] launcher_seed=[Đã nạp bộ media seed (idempotent).] seed_counts={"hooks": 10, "media_assets": 411, "sources": 7} job=FAILED_FINAL job_wait=None stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=FAILED_FINAL/voice_duration_out_of_range]`.

- stage=tts, activity=CreateVoiceTrack, code=voice_duration_out_of_range, field_errors rỗng.
- stage đã SUCCEEDED: analyze, script, media_select, plan (mỗi stage 1 attempt).
- launcher_seed: `Đã nạp bộ media seed (idempotent).`; seed_counts: hooks=10, media_assets=411, sources=7.
- render_config: ba scope (preset/bold-yellow, preset/output-profile, policy/quality) đều PUBLISHED.
- serve_log_tail: Kokoro tạo audio dài 24,82 giây cho 419 phoneme (RTF 0,16) ngay trước khi job fail.
- pre_stop_attempts: fixture BLOCKED nên dòng `- start: pre_stop_attempts=` không được in; giá trị cụ thể chưa đo. Việc `launcher start` cấp được URL /launch và job được tạo cho thấy `stop_until_exited()` đã thoát thành công.
- Các dòng `- ...` khác của fixture (elapsed, md5/sha256, ledger, resume ready_seconds, budget): không được in vì fixture BLOCKED.
- Driver đã xác nhận bằng test canh: không còn `ensure_voice_staging`, `ensure_seed_media`, `staging_voice`, `seed_import`; `session.post_batch(1)` đúng một lần; không có lô thứ hai.

Nguyên nhân gốc của `voice_duration_out_of_range`: chưa xác định. Evidence chỉ cho thấy audio 24,82 giây được tạo, chưa cho biết ngưỡng độ dài mà CreateVoiceTrack áp dụng; việc kiểm tra thuộc production, ngoài owned paths.

## Open item

- OI-RG09-LAUNCH-URL-01: đã giải quyết trong lần chạy này (có URL /launch, lô được tạo) nhờ stop trước start.
- OI-RG09-TTS-DURATION-01: stage tts FAILED_FINAL với `voice_duration_out_of_range`; cần Control xác định ngưỡng và nguyên nhân (production, ngoài owned paths).
- OI-PW-E2E-01 (writer CREATED→RUNNING): job đã chạy qua bốn stage đầu, chưa chạm render nên chưa kết luận hoàn toàn theo stages_succeeded.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09, không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi, không sửa `src/**`, không dữ liệu giả, không đọc `Credentials/`.
- Không có capability, cookie, token hay file ID trong tệp này.
- Chạy ngăn xếp thật đúng một lần, một lô.
- Driver không còn làm thay production; chỉ dùng launcher stop/start sẵn có.
