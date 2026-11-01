# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `f304d747518a8571b2403959ded2a530aed6f2e0` (HEAD ngay sau rebase; lane đã rebase lên `6972626f7a280f69293662f5d1d9446211234e9d`, kết quả kiểm của lần mở trước không còn dùng được). Các thay đổi của lượt này nằm ở cây làm việc, được commit sau HEAD này.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED**: job J đi qua 8 stage đầu (analyze, script, media_select, plan, tts, align, process, render) đều SUCCEEDED/attempt1, nhưng stage `qc` kết thúc `FAILED_FINAL` (`code=quality_gates_failed`) vì cổng chặn `VISUAL_HOOK_PRESENT=failed/visual_hook_similarity_below_threshold`. Job dừng trước `sync` và `complete`, nên không có upload Drive, không có sổ hoàn tất và không đo được các mục phụ thuộc. Lần chạy ngăn xếp thật duy nhất bắt đầu 2026-11-01T17:03:41Z, kết thúc 17:10:41Z (418,17 giây), exit 1, `44 passed, 11 errors in 418.17s (0:06:58)`: 11 test RG-09 đều lỗi ở setup fixture `batch_run` do driver báo BLOCKED. Tôi không nới ngưỡng, không thử lại, không tạo lô khác, không sửa production. Sau lượt chạy lô vẫn RUNNING trên Temporal (xem Open item).

## Nguyên nhân và sửa

1. OI-CP7-10-F11 (lượt trước): driver và test lọc `'drive' in backend_ref`, trong khi production ghi location đám mây với `backend_ref='cloud'` và evidence `drive:<id>:sha256Checksum`. Đã sửa: `is_drive` so `backend_ref` với `CLOUD_BACKEND` (import lazy từ `controlplane.application.storage_meta.handlers`), thêm `DRIVE_EVIDENCE_PREFIX = 'drive:'`, `_drive_verified` đòi state VERIFIED và evidence tiền tố `drive:`, `drive_bytes` lọc `l.backend_ref = 'cloud'`, `ledger_row` đọc thêm `cloud_location_ref` và `cloud_location_verification_ref`, thêm `ordering_proof` (so ref của ledger với location VERIFIED, mốc `completed_at` cắt về giây).
2. `cleanup_after_verify` ghi `cleaned_locations` và lý do khi bằng 0 (production chưa có đường dọn local; ràng buộc chỉ cấm dọn trước VERIFIED).
3. Thêm `collect_media_audio_evidence` (chỉ SELECT, không bao giờ raise) và trường `RunResult.media_audio_evidence`, được `test_rg09_budget_envelope` emit.
4. Bản sửa F11 chưa được kiểm chứng trên ngăn xếp thật vì job không tới được stage sync/complete ở lượt này.
5. Nguyên nhân lượt này: cổng QC `VISUAL_HOOK_PRESENT` fail (`visual_hook_similarity_below_threshold`). Đây là hành vi production/QC ngoài owned paths; cần chủ mã QC/render hoặc Control quyết định.

## Lệnh đã chạy

1. Bước 1: `git rebase 6972626f7a280f69293662f5d1d9446211234e9d` — thành công, không xung đột, cây sạch.
2. Bước 2-8: sửa driver và test theo lệnh làm việc.
3. Bước 9: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `44 passed, 11 deselected in 0.38s` (tăng 6 so với 38).
4. Bước 10: `git diff --check` — exit 0, không output.
5. Bước 11 (đúng một lần, bắt đầu 2026-11-01T17:03:41Z, kết thúc 2026-11-01T17:10:41Z): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (thêm `-rA` để lấy tóm tắt) — exit 1, `44 passed, 11 errors in 418.17s (0:06:58)`.
6. Bước 12: ghi lại report.md này bằng công cụ sửa tệp (UTF-8).
7. Bước 13-14: `git diff --check` và probe 10 mục RG-09 — xem báo cáo worker_done (probe đỏ đúng kỳ vọng vì mục BLOCKED).

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

Cả 10 mục ghi BLOCKED vì fixture `batch_run` lỗi (driver raise BlockedError) nên không test RG-09 nào chạy tới thân test; không có PASS nào được chứng minh trong lượt này.

## Chi tiết đo

- Batch id B: `640438e3-8cb6-43b3-ac55-d645ae25fdfe`. Job id J: `640438e3-8cb6-43b3-ac55-d645ae25fdfe:job:1`. Workflow con: `640438e3-8cb6-43b3-ac55-d645ae25fdfe:video:1`.
- Stage: analyze#1, script#1, media_select#1, plan#1, tts#1, align#1, process#1, render#1 = SUCCEEDED; `qc#1 = FAILED_FINAL/quality_gates_failed` (activity `inspect_output`); sync và complete không chạy.
- QC: `blocking_gates=[VISUAL_HOOK_PRESENT=failed/visual_hook_similarity_below_threshold]`, `duration=[mp4_ms=64260 voice_est_ms=63529 delta_ms=731]`. `voice_est_ms` là `timeline.voice_duration_ms` ước lượng, không đo bằng ffprobe.
- Script: segments=5, words=144, wpm=136, est_ms=63529, khoảng 61000-70000, verdict=within_range.
- Seed: hooks=10, media_assets=432, sources=7; render_config `preset/bold-yellow`, `preset/output-profile`, `policy/quality` đều PUBLISHED. Trước chạy `other_workflows_running=0`.
- Chi phí: ai_calls=6 (trần 25); spent_usd, drive_bytes, elapsed_s của run_batch không đo được vì driver dừng sớm (drive_bytes thực tế 0 do chưa upload; thời gian pytest 418 giây, trần 7200).
- Mục ghi thêm (không chấm RG-09): `media_audio_evidence` (số ảnh bài, an toàn ảnh, bed_kind, mp4 có nhạc), số ảnh bài và seed được chọn (`media_ids`), số từ align được chia — không đo được (driver chỉ thu thập ở nhánh COMPLETED).
- resume_300s (ready_seconds) và no_rerun (completed_before_stop): không đo được ở lượt này vì lỗi xảy ra trước khi test ghi kết quả; trạng thái stop/start trong lượt chạy không được báo cáo.
- md5 và sha256 local/cloud: không đo được (chưa có location Drive).
- Thăm dò `drive_md5_check` lô 8d357809: không chạy được trước lượt thật (lệnh kiểm không cho chạy `python <tệp>.py` hay import driver qua `python -c`); `drive_md5_check` được chạy trong lượt thật qua `batch_run.drive_check` nhưng lượt này chưa tới bước đó.

## Open item

- OI-CP7-10-F11: **giữ mở** — bản sửa driver/test đã có và unit test pass, nhưng `cloud_verified_before_count` chưa được chứng minh trên ngăn xếp thật vì job FAILED_FINAL ở qc trước khi tới sync.
- OI-CP7-10-F12 (mới): cổng QC `VISUAL_HOOK_PRESENT` fail (`visual_hook_similarity_below_threshold`) ở lượt này; ngoài owned paths, cần Control/chủ mã QC xử lý.
- Lô còn RUNNING: `db_status=RUNNING temporal_running=2`, run_ids=[batch_id=640438e3-8cb6-43b3-ac55-d645ae25fdfe job_id=640438e3-8cb6-43b3-ac55-d645ae25fdfe:job:1]. Control cần xin user terminate lô này trước lượt kế.
- OI-PW-E2E-01: giữ nguyên — production chưa có writer CREATED->RUNNING; RG-09 không chấm theo trạng thái dòng lô.
