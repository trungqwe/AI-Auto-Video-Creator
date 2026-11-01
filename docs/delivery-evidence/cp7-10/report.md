# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `55bfeac7a16c89fe307d92fecc2bfcc1153ff49c`.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED** (nhánh B, ngăn xếp lên và lô được tạo, nhưng job dừng ở stage qc). Ở HEAD `55bfeac7a16c89fe307d92fecc2bfcc1153ff49c`, `git diff --check` exit 0 và test unit xanh (38 passed, 11 deselected). Lần chạy ngăn xếp thật duy nhất (bắt đầu 2026-11-01T06:08:31Z) khởi động được launcher (token Drive đã được khôi phục, OI-CP7-10-F9 không còn tái hiện), tạo lô B = `0ccb8a77-64ad-4621-80f8-c0670d8a31ca`, job J = `0ccb8a77-64ad-4621-80f8-c0670d8a31ca:job:1`. Các stage analyze, script, media_select, plan, tts, align, process, render đều SUCCEEDED (attempt #1); stage qc kết thúc FAILED_FINAL, code `quality_gates_failed`, activity `inspect_output`, cổng chặn `SUBTITLE_BURNED_IN=failed/subtitle_not_observed`. Do đó job không tới upload Drive, verify và completion; resume, md5 và Drive bytes không đo được. Độ dài kịch bản nằm trong khoảng (147 từ, 136 wpm, est 64852 ms, khoảng 61000-70000 ms); mp4_ms=63893, voice_ms=64853, delta_ms=-960. Sau lượt chạy lô B còn RUNNING (Temporal đang chạy 2 workflow), cần Control terminate. Không hạ ngưỡng và không sửa driver hay test để vượt qua; lỗi cổng `SUBTITLE_BURNED_IN` nằm ở mã sản phẩm ngoài owned paths của lane này.

## Nguyên nhân và sửa

1. F7: record_key của bảng creative là id do D sinh: `plan:<job_id>:r<rev>`, `analysis:<job_id>:r<rev>`, với job_id = `<B>:job:<ordinal>`. Driver trước lọc theo `<ws>:<B>:video:` nên không thấy dòng nào. Đã sửa: `plan_key_prefix(job_id)` và `analysis_key_prefix(job_id)`; `_plan_row`, `build_trace`, `plan_digest`, `collect_script_length`, `collect_qc_evidence` nhận job_id.
2. Đếm lời gọi AI vẫn theo `<ws>:<B>:video:` (`video_key_prefix`, `CostWatch.bind_prefix`) vì operation_key của `cp_ai_invocation_records` bắt đầu bằng workflow_id con `<B>:video:<seq>`.
3. BLOCKED phát sinh sau khi lô đã tạo mang thêm ` run_ids=[batch_id=<B> job_id=<J>]` (`run_batch`, `except BlockedError`), để Control biết lô cần terminate. BLOCKED trước khi có lô giữ nguyên.
4. Lane đã rebase lên `2687822f8841fcda7c38c692cdd997c16494b1a3`; kết quả kiểm của lần mở trước không còn dùng được. Lượt này không đổi mã driver hay test.

## Lệnh đã chạy

1. Bước 1: `git diff --check` ở HEAD `55bfeac7a16c89fe307d92fecc2bfcc1153ff49c` (cây sạch) — exit 0, không output.
2. Bước 2: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `38 passed, 11 deselected in 0.08s`.
3. Bước 3 (đúng một lần, bắt đầu 2026-11-01T06:08:31Z): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` — exit 1, `38 passed, 11 errors in 454.14s (0:07:34)`. Cả 11 lỗi là `BLOCKED: job kết thúc ở FAILED_FINAL stage=qc ... SUBTITLE_BURNED_IN=failed/subtitle_not_observed` ở fixture `batch_run`.
4. Bước 4: ghi lại report.md này bằng công cụ sửa tệp (UTF-8).
5. Bước 5: `git diff --check` sau khi ghi report — xem báo cáo worker_done.
6. Bước 6: probe 10 mục RG-09 — xem báo cáo worker_done (đỏ đúng kỳ vọng vì các mục là BLOCKED thật).

## Kết quả

RG-09.stages_succeeded: FAIL
RG-09.no_fake_adapters: BLOCKED
RG-09.qc_hard_gates: FAIL
RG-09.cloud_verified_before_count: BLOCKED
RG-09.cleanup_after_verify: BLOCKED
RG-09.plan_unchanged: BLOCKED
RG-09.resume_300s: BLOCKED
RG-09.no_rerun_completed: BLOCKED
RG-09.trace_complete: BLOCKED
RG-09.secret_scan: BLOCKED

## Chi tiết đo

- Thông điệp của driver: `BLOCKED: job kết thúc ở FAILED_FINAL stage=qc status=FAILED_FINAL activity=inspect_output code=quality_gates_failed field_errors={}`; `other_workflows_running=0` trước khi chạy.
- Batch id B: `0ccb8a77-64ad-4621-80f8-c0670d8a31ca`. Job id J: `0ccb8a77-64ad-4621-80f8-c0670d8a31ca:job:1`. `run_ids`: `0ccb8a77-64ad-4621-80f8-c0670d8a31ca` và `0ccb8a77-64ad-4621-80f8-c0670d8a31ca:video:1`.
- Stage: `analyze#1=SUCCEEDED; script#1=SUCCEEDED; media_select#1=SUCCEEDED; plan#1=SUCCEEDED; tts#1=SUCCEEDED; align#1=SUCCEEDED; process#1=SUCCEEDED; render#1=SUCCEEDED; qc#1=FAILED_FINAL/quality_gates_failed`.
- `- qc_evidence:` blocking_gates=`SUBTITLE_BURNED_IN=failed/subtitle_not_observed`; mp4_ms=63893; voice_ms=64853; delta_ms=-960.
- `- seed:` hooks=10, media_assets=432, sources=7 (`Đã nạp bộ media seed (idempotent).`). `- budget:` render_config `preset/bold-yellow`, `preset/output-profile`, `policy/quality` đều PUBLISHED.
- Độ dài kịch bản: segments=7, words=147, wpm=136, est_ms=64852, khoảng 61000-70000 ms, verdict=within_range.
- Số lời gọi AI: 6 (trần 25). `- batch_after_run=[db_status=RUNNING temporal_running=2 ids=[B, B:video:1]]`.
- Không đo được vì job dừng ở stage qc trước upload: ledger delta (trần 3 USD), Drive bytes (trần 200 MiB), md5 local và cloud, ready_seconds của resume (ngưỡng 300 giây), attempt trước và sau resume, số từ align được chia. Không số nào được bịa; `no_fake_adapters`, `cloud_verified_before_count`, `cleanup_after_verify`, `plan_unchanged`, `resume_300s`, `no_rerun_completed`, `trace_complete`, `secret_scan` ghi BLOCKED vì không có số đo trực tiếp.
- Thời gian chạy của lần pytest duy nhất: 454,14 giây (trần 2 giờ).

## Open item

- OI-PW-E2E-01: lô không rời CREATED nên FinalizeBatch trả FORBIDDEN_TRANSITION; do gói PW-G4-FIX2 sửa, chưa gộp. RG-09 không chấm theo trạng thái dòng lô.
- OI-CP7-10-F7: đã sửa trong driver (lọc plan và analysis theo job_id); lượt này lô chạy qua analyze..render với plan và analysis đọc được, nhưng RG-09 chưa PASS vì qc.
- OI-CP7-10-F9: ngăn xếp lên ở lượt này (launcher start không còn `DrivePlacementError`); coi là đã qua, nhưng upload Drive thật chưa được thử vì job dừng ở qc.
- OI-CP7-10-F10 (mới): cổng QC `SUBTITLE_BURNED_IN` báo `failed/subtitle_not_observed` trên video render (mp4_ms=63893, voice_ms=64853); cần chủ mã render hoặc QC (ngoài owned paths của lane) xác định phụ đề có thật sự được đốt vào mp4 hay bộ dò sai, rồi Control cấp lượt mới.
- Lô cũ: lô B `0ccb8a77-64ad-4621-80f8-c0670d8a31ca` còn RUNNING (Temporal 2 workflow); `run_ids`: `0ccb8a77-64ad-4621-80f8-c0670d8a31ca`, `0ccb8a77-64ad-4621-80f8-c0670d8a31ca:video:1` (job `0ccb8a77-64ad-4621-80f8-c0670d8a31ca:job:1`). Control cần terminate trước lượt sau.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ, 300 giây resume giữ nguyên.
- Không SQL ghi; không cancel, terminate hay signal workflow; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
