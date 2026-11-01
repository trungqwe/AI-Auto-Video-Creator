# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T21:12:36Z, kết thúc 2026-11-01T21:19:02Z (giờ Việt Nam: 02/11/2026 04:12:36 đến 04:19:02).
- `HEAD`: `1e4186ccd4d0e5673a13ea42d87aab9d02431c44` (đã rebase lên `b2712db8118e2584205541c264b67ddbb6241f0d`, đã có ADAPT-E-FIX5; giữ nguyên mã của lane).
- Interpreter: `python` mặc định trên PATH của phiên làm việc.

## Kết luận trung thực

Lượt này BLOCKED: RG-09 không đạt trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại). 8 trên 11 stage SUCCEEDED ở attempt 1 (analyze, script, media_select, plan, tts, align, process, render); stage `qc` kết thúc `FAILED_FINAL` với `code=quality_gates_failed`, hard gate hỏng là `THUMBNAIL_PRESENT` (`thumbnail_asset_mismatch`); hai stage `sync` và `complete` không chạy. Sau lượt, lô vẫn ở trạng thái `RUNNING` (Temporal còn 2 workflow RUNNING), cần Control terminate. Vì lô không tới `COMPLETED`, test không in các dòng đo `- ` và không có bằng chứng cho cloud verify, cleanup, plan_unchanged, resume, trace, nên cả 10 mục RG-09 ghi BLOCKED, không ghi PASS cho mục nào.

## Lệnh đã chạy

1. `git rebase b2712db8118e2584205541c264b67ddbb6241f0d`: exit 0, rebase 26 commit sạch, không xung đột, working tree sạch.
2. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -s` (đúng một lần; có thêm cờ `-s` để lấy toàn bộ output): bắt đầu 2026-11-01T21:12:36Z, kết thúc 2026-11-01T21:19:02Z, exit code 1, dòng tổng kết `45 passed, 11 errors in 385.06s (0:06:25)`. 11 error đều là lỗi setup của fixture `batch_run` (BLOCKED, xem Chi tiết đo).
3. `git diff --check` sau khi ghi report: exit 0, không output.
4. Probe 10 mục RG-09 (`python -c ...`): exit 1 (AssertionError `failed item`, vì report ghi BLOCKED đúng theo kết quả thật).

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

Các dòng `- ` do test in (nguyên văn): không có. Fixture `batch_run` gọi `pytest.fail` với thông điệp BLOCKED nên 11 test RG-09 dừng ở setup và không in dòng `- ` nào (stages_succeeded, no_fake_adapters, qc_hard_gates, cloud_verified_before_count, cleanup_after_verify, plan_unchanged, resume_300s, no_rerun_completed, trace_complete, secret_scan, budget, seed, start, pre_check, ai_calls_source, batch_after_run, qc_evidence, media_audio_evidence đều không có output lượt này).

Thông điệp BLOCKED thật (rút từ output pytest, đã bỏ phần traceback):

- job kết thúc ở `FAILED_FINAL stage=qc status=FAILED_FINAL activity=inspect_output code=quality_gates_failed field_errors={}`; không thử lại, không tạo lô khác.
- other_workflows_running=0, ai_calls=6.
- blocking_gates=[THUMBNAIL_PRESENT=failed/thumbnail_asset_mismatch]
- duration=[mp4_ms=61265 voice_est_ms=67500 delta_ms=-6235]
- failed_detail=[THUMBNAIL_PRESENT:measured=2000 range=2000-2000 rev=2164b1f9-ec51-45ea-bfeb-78e7be9ea532]
- batch_after_run=[db_status=RUNNING temporal_running=2 ids=['c84aedba-ae26-499d-9914-7798dd4bfb09', 'c84aedba-ae26-499d-9914-7798dd4bfb09:video:1']]
- render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- media_audio_evidence=[media_count=5 media_ids=[ma-4d8,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured]
- launcher_seed=[Đã nạp bộ media seed (idempotent).] seed_counts={"hooks": 10, "media_assets": 455, "sources": 7}
- script_length=[segments=5 words=153 wpm=136 est_ms=67500 range_ms=61000-70000 verdict=within_range]
- stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=SUCCEEDED;process#1=SUCCEEDED;render#1=SUCCEEDED;qc#1=FAILED_FINAL/quality_gates_failed]
- run_ids=[batch_id=c84aedba-ae26-499d-9914-7798dd4bfb09 job_id=c84aedba-ae26-499d-9914-7798dd4bfb09:job:1]

Tổng hợp theo yêu cầu của lệnh làm việc:

- batch_id: `c84aedba-ae26-499d-9914-7798dd4bfb09`; job_id: `c84aedba-ae26-499d-9914-7798dd4bfb09:job:1`.
- Bảng stage (status/attempt): analyze, script, media_select, plan, tts, align, process, render đều SUCCEEDED/attempt 1; qc FAILED_FINAL/attempt 1; sync và complete không chạy (không có dòng trong output).
- qc_evidence: blocking_gates=[THUMBNAIL_PRESENT=failed/thumbnail_asset_mismatch]; failed_detail=[THUMBNAIL_PRESENT:measured=2000 range=2000-2000 rev=2164b1f9-ec51-45ea-bfeb-78e7be9ea532]; mp4_ms=61265, voice_est_ms=67500, delta_ms=-6235.
- media_audio_evidence: media_count=5 (`ma-4d8` và 4 `seed-b`); image_safety, bed_kind, music_cues, mp4_has_music đều `not_measured`.
- Số từ align đã chia: không có, output test không in (script có words=153 trên 5 segment, stage align SUCCEEDED).
- Cloud location VERIFIED và evidence drive: không có (lô chưa tới stage sync, output không in).
- cleanup_after_verify: không có bằng chứng (lô chưa tới sync).
- drive_md5_check (md5_match, sha256_match): không có (lô chưa tới sync).
- Ngân sách: ai_calls=6 (trần 25); ledger_usd, drive_bytes, elapsed_s không được in do test dừng ở BLOCKED; thời gian thực của cả lượt pytest là 385,06 giây (trần 7200).

## Open item

- Lô còn RUNNING sau lượt, Control cần terminate: `batch_id=c84aedba-ae26-499d-9914-7798dd4bfb09`, workflow ids `c84aedba-ae26-499d-9914-7798dd4bfb09` và `c84aedba-ae26-499d-9914-7798dd4bfb09:video:1` (`temporal_running=2`).
- OI-CP7-10-QC-THUMB: gate `THUMBNAIL_PRESENT` hỏng với `thumbnail_asset_mismatch` (`measured=2000 range=2000-2000`) ở stage qc; cần chủ gói của stage render/qc xử lý, lane này không sửa production.
- OI-PW-E2E-01: output lượt này không chứng minh được trạng thái đóng lô; giữ mở.
- OI-CP7-10-F11: output pytest thật không có dòng nào nêu riêng mục này; giữ mở.
- OI-CP7-10-F12: output pytest thật không có dòng nào nêu riêng mục này; giữ mở. Liên quan: `image_safety`, `bed_kind`, `mp4_has_music` đều `not_measured`.
- OI-CP7-10-F13: stage align SUCCEEDED ở attempt 1 trong lượt này (script 153 từ, 5 segment); số từ align đã chia không được output test in nên chưa có số liệu; giữ mở ở phần số liệu.
