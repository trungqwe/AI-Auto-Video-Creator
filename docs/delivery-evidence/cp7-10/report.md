# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026. Lane `lane-cp7-10`, interpreter khoá `.local-tools\runtime\8715e538\venv\Scripts\python.exe`. HEAD nền khi chạy là `479c1b3` (kèm thay đổi chưa commit của lượt này trong driver và test).

## Lệnh đã chạy

- Commit trước: `479c1b3`. Lần chạy ngăn xếp thật ở commit đó BLOCKED ở stage `tts` (`voice_duration_out_of_range`) mà driver chưa đo độ dài script.
- Thay đổi lượt này: thêm `format_script_length` và `collect_script_length` (chỉ đọc, chỉ SELECT) vào thông điệp BLOCKED của job FAILED_FINAL; thêm ba test thuần mới (`test_unit_format_script_length`, `test_unit_collect_script_length_read_only`, `test_unit_blocked_message_reports_script_length`) và hằng `_PROFILE_VOICE`.
- `git diff --check` (trước khi chạy ngăn xếp thật): exit 0.
- Test thuần (`-k unit`, không chạm ngăn xếp): 22 passed, 11 deselected, exit 0.
- `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (ngăn xếp thật, đây là lần chạy duy nhất của lượt, một lô 1 video): 22 passed, 0 failed, 11 errors, exit code 1, thời gian `521.02s (0:08:41)`. Cả 11 error là lỗi setup của fixture `batch_run` cùng một nguyên nhân.

## Trạng thái

0/10 PASS. Lần này job dừng ở stage `analyze` (không phải `tts` như lần trước), nên không mục RG-09 nào được chứng minh.

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

Blocker nguyên văn (đã che, phần serve_log_tail được cắt ở đuôi): `BLOCKED: job kết thúc ở FAILED_FINAL stage=analyze status=FAILED_FINAL activity=AnalyzeContent code=ai_output_schema_violation field_errors={"field": "root", "reason": "not_json", "attempts": "3"}; không thử lại, không tạo lô khác; render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED] launcher_seed=[Đã nạp bộ media seed (idempotent).] seed_counts={"hooks": 10, "media_assets": 411, "sources": 7} script_length=[segments=5 words=167 wpm=150 est_ms=66800 range_ms=61000-70000 verdict=within_range] job=FAILED_FINAL job_wait=None stages=[analyze#1=FAILED_FINAL/ai_output_schema_violation]`.

- stage=analyze, activity=AnalyzeContent, code=ai_output_schema_violation, field_errors: field=root, reason=not_json, attempts=3 (đầu ra AI ba lần liên tiếp không phải JSON).
- stage đã SUCCEEDED: không có; chỉ `analyze#1` FAILED_FINAL.
- launcher_seed: `Đã nạp bộ media seed (idempotent).`; seed_counts: hooks=10, media_assets=411, sources=7.
- render_config: ba scope (preset/bold-yellow, preset/output-profile, policy/quality) đều PUBLISHED.
- script_length: `segments=5 words=167 wpm=150 est_ms=66800 range_ms=61000-70000 verdict=within_range`. Lưu ý trung thực: job lần này chỉ có stage `analyze` FAILED_FINAL (chưa có stage `script`), nên dòng script_length không chứng minh được script thuộc job này; driver chỉ đọc bản ghi kế hoạch/script mới nhất trong cửa sổ thời gian của lô, nguồn gốc bản ghi đó chưa được xác minh.
- serve_log_tail: đuôi serve.log ghi Kokoro tạo audio 21,70 giây cho 348 phoneme (RTF 0,16). Đây chỉ là một đoạn trong đuôi serve.log, chưa chứng minh là tổng thời lượng giọng; dòng 24,82 giây của lần chạy trước cũng vậy.
- pre_stop_attempts: fixture BLOCKED nên dòng `- start: pre_stop_attempts=` không được in; giá trị chưa đo.
- Các dòng `- ...` khác của fixture (elapsed, md5/sha256, ledger, resume ready_seconds, budget): không được in vì fixture BLOCKED.
- Driver đã được test canh xác nhận: không còn `ensure_voice_staging`, `ensure_seed_media`, `staging_voice`, `seed_import`; `session.post_batch(1)` đúng một lần; không có lô thứ hai.

Kết luận nguyên nhân theo số đo:
- Lỗi lần này (`ai_output_schema_violation`, `not_json` sau 3 lần ở stage analyze) xuất phát từ đầu ra của AI qua 9Router không phải JSON; chưa xác định thêm nguyên nhân gốc. Phần sửa thuộc production (lời gọi AI hay parse đầu ra), ngoài owned paths, Worker không sửa.
- Với `voice_duration_out_of_range` của lần trước: job lần này không tới stage tts nên chưa kiểm chứng lại. Verdict `within_range` đo được (ước lượng theo 150 wpm nằm trong khoảng 61000-70000 ms) kèm lưu ý nguồn bản ghi ở trên; nếu bản ghi đó đúng là script của một job đã tới tts thì tổng thời lượng Kokoro đo thật lệch so với ước lượng, cần Control đo tổng thời lượng giọng. Phần sửa thuộc production (sinh script hay voice policy), ngoài owned paths, Worker không sửa.

## Open item

- OI-RG09-LAUNCH-URL-01: đã giải quyết (có URL /launch, lô được tạo ở cả hai lần chạy gần nhất).
- OI-RG09-TTS-DURATION-01: chưa giải quyết; lần chạy này không tới stage tts. Cần Control đo tổng thời lượng giọng khi job tới tts (verdict script_length đo được là within_range, xem lưu ý nguồn bản ghi).
- OI-RG09-ANALYZE-JSON-01 (mới): stage analyze FAILED_FINAL `ai_output_schema_violation` / `not_json` sau 3 lần; cần Control xem đầu ra AI của AnalyzeContent (production, ngoài owned paths).
- OI-PW-E2E-01 (writer CREATED→RUNNING): job chạy tới stage analyze rồi FAILED_FINAL, chưa chạm các stage sau nên chưa kết luận theo stages_succeeded.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09, không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi, không sửa `src/**`, không sửa profile, không dữ liệu giả, không đọc `Credentials/`.
- Không có capability, cookie, token hay file ID trong tệp này.
- Chạy ngăn xếp thật đúng một lần, một lô, không thử lại.
- Driver không còn làm thay production; chỉ dùng launcher stop/start sẵn có.
