# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T22:03:01Z, kết thúc 2026-11-01T22:07:50Z (giờ Việt Nam: 02/11/2026 05:03:01 đến 05:07:50).
- `HEAD`: `d1df312cd1158410b27863beb8445f8e0e9633f8` (mã đã rebase lên 4ca228c2e979f3a1638779469582b1353d5956b7; mã chẩn đoán `hook_placement` đã được commit).
- Interpreter: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe` (interpreter khoá của lane).

## Kết luận trung thực

Lượt này KHÔNG đạt RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại): job kết thúc `FAILED_FINAL` ở stage `align` (activity `CreateWordTiming`, code `word_coverage_incomplete`). Chỉ 5 stage SUCCEEDED ở attempt 1 (analyze, script, media_select, plan, tts) trên tổng 11 stage; align FAILED_FINAL nên các stage render, qc, sync, complete không chạy. QC hard gate không đánh giá được (`qc_evidence=[no_render_package]`, `blocking_gates` không có vì chưa có gói render), chưa có cloud verified, chưa đo resume. Pytest kết thúc `48 passed, 11 errors in 288.47s (0:04:48)`, exit code 1; 11 error là fixture `batch_run` ném BLOCKED cho cả 11 test `test_rg09_*`. Lô còn `db_status=RUNNING` với `temporal_running=2`; Control cần terminate các run_ids ở mục Open item. Mười mục RG-09 ghi BLOCKED, không hạ ngưỡng.

## Lệnh đã chạy

1. `git rebase 4ca228c2e979f3a1638779469582b1353d5956b7`: hoàn tất không xung đột (28 commit), HEAD `d1df312cd1158410b27863beb8445f8e0e9633f8`, worktree sạch.
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không output.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần, HEAD `d1df312`): bắt đầu 2026-11-01T22:03:01Z, kết thúc 2026-11-01T22:07:50Z, exit code 1, dòng tổng kết `48 passed, 11 errors in 288.47s (0:04:48)`.
4. `git diff --check` sau khi ghi report: exit 0, không output.
5. Probe 10 mục RG-09 (`python -c ...`): kết quả ghi trong báo cáo worker_done (kỳ vọng đỏ vì kết quả thật BLOCKED).

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

Test không in các dòng `- ` đo vì fixture `batch_run` ném BLOCKED trước khi các test đo chạy. Dữ liệu thật của lượt (từ thông báo BLOCKED, đã lược bỏ log phoneme của serve):

- blocking_gates: không có (`qc_evidence=[no_render_package]`, chưa có gói render nên QC không chạy).
- failed_detail: `job kết thúc ở FAILED_FINAL stage=align status=FAILED_FINAL activity=CreateWordTiming code=word_coverage_incomplete field_errors={}`.
- hook_placement: `[visual=vh-01 thumbnail=thumb:ma same_ref=False hook_range=0-5000 thumbnail_range=1000-3000]`.
- stages: `analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=FAILED_FINAL/word_coverage_incomplete`.
- script_length: `segments=6 words=150 wpm=136 est_ms=66176 range_ms=61000-70000 verdict=within_range`.
- pre_check: `other_workflows_running=0`.
- ai_calls: 6 (trần 25).
- batch_after_run: `db_status=RUNNING temporal_running=2 ids=['7150f8a9-9a01-4252-adc6-16d2dd75d720', '7150f8a9-9a01-4252-adc6-16d2dd75d720:video:1']`.
- render_config: `preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED`.
- media_audio_evidence: `media_count=6 media_ids=[ma-677,seed-b,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured`.
- seed: `seed_counts={"hooks": 10, "media_assets": 455, "sources": 7}`, launcher: Đã nạp bộ media seed (idempotent).
- run_ids: `batch_id=7150f8a9-9a01-4252-adc6-16d2dd75d720 job_id=7150f8a9-9a01-4252-adc6-16d2dd75d720:job:1`.

Tổng hợp theo yêu cầu của lệnh làm việc:

- Bảng stage (status/attempt): analyze, script, media_select, plan, tts = SUCCEEDED/attempt 1; align = FAILED_FINAL/attempt 1 (`word_coverage_incomplete`); process, render, qc, sync, complete không chạy.
- Số từ align đã chia: output không có (stage align hỏng trước khi in).
- media_audio_evidence: như trên (`not_measured` cho image_safety, bed_kind, music_cues, mp4_has_music).
- Cloud location VERIFIED và evidence drive (drive_md5_check): không có, chưa tới stage sync.
- cleanup_after_verify: không đo được.
- Ngân sách: ai_calls=6 (trần 25); chi phí ledger và dung lượng Drive không đo được vì test dừng ở BLOCKED; thời gian chạy 288 giây (trần 7200).

## Open item

- Cần Control terminate lô còn RUNNING: `batch_id=7150f8a9-9a01-4252-adc6-16d2dd75d720`, `job_id=7150f8a9-9a01-4252-adc6-16d2dd75d720:job:1`; Temporal workflow ids: `7150f8a9-9a01-4252-adc6-16d2dd75d720` và `7150f8a9-9a01-4252-adc6-16d2dd75d720:video:1` (`temporal_running=2`).
- OI-CP7-10-ALIGN: stage align FAILED_FINAL `word_coverage_incomplete` ở `CreateWordTiming` (script 150 từ trong khoảng 61000-70000 ms); lane không vá production, cần chủ gói align/TTS chẩn đoán nguyên nhân.
- OI-CP7-10-QC-THUMB: lượt này không tới QC; `hook_placement` cho thấy `same_ref=False hook_range=0-5000 thumbnail_range=1000-3000` (thumbnail lệch hook), giữ mở để chẩn đoán lỗi `thumbnail_asset_mismatch` của lượt trước.
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chấm theo nó.
- OI-CP7-10-F11, OI-CP7-10-F12: giữ mở; `image_safety`, `bed_kind`, `mp4_has_music` vẫn `not_measured`.
- OI-CP7-10-F13: số từ align đã chia chưa có số liệu vì stage align hỏng.
