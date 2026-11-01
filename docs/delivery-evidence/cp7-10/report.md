# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `6adb5c772ed4979eac69f4a1acba218488921ee7`.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED**. Test unit xanh (38 passed, 11 deselected) và `git diff --check` exit 0. Lần chạy ngăn xếp thật duy nhất (bước 3) dừng ngay ở kiểm chỉ đọc giữa stop và start với `BLOCKED: OTHER_WORKFLOWS_RUNNING count=2 ids=[ProductionBatchWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c, VideoProductionWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c:video:0]`: lô cũ 2a1e2434 vẫn RUNNING trên Temporal tại thời điểm chạy, nên lô đó chưa được terminate trước lượt này. Driver dừng trước khi tạo lô nên không có `run_ids` (không có lô mới của lượt này). Theo lệnh làm việc, không cancel, terminate hay signal workflow và không chạy lại. Chưa kiểm chứng được sửa F7 trên ngăn xếp thật; không mục RG-09 nào có output PASS.

## Nguyên nhân và sửa

1. F7: record_key của bảng creative là id do D sinh: `plan:<job_id>:r<rev>`, `analysis:<job_id>:r<rev>`, với job_id = `<B>:job:<ordinal>`. Driver trước lọc theo `<ws>:<B>:video:` nên không thấy dòng nào. Đã sửa: `plan_key_prefix(job_id)` và `analysis_key_prefix(job_id)`; `_plan_row`, `build_trace`, `plan_digest`, `collect_script_length`, `collect_qc_evidence` nhận job_id.
2. Đếm lời gọi AI vẫn theo `<ws>:<B>:video:` (`video_key_prefix`, `CostWatch.bind_prefix`) vì operation_key của `cp_ai_invocation_records` bắt đầu bằng workflow_id con `<B>:video:<seq>`.
3. BLOCKED phát sinh sau khi lô đã tạo mang thêm ` run_ids=[batch_id=<B> job_id=<J>]` (`run_batch`, `except BlockedError`), để Control biết lô cần terminate. BLOCKED trước khi có lô giữ nguyên.
4. Lượt này không đổi mã; chỉ chạy lại ngăn xếp thật đúng một lần sau khi lô cũ được xử lý.

## Lệnh đã chạy

1. Bước 1: `git diff --check` — exit 0, không output.
2. Bước 2: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `38 passed, 11 deselected in 0.10s`.
3. Bước 3 (đúng một lần): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` — exit 1, `38 passed, 11 errors in 1.73s`. Cả 11 lỗi là `BLOCKED: OTHER_WORKFLOWS_RUNNING` ở fixture `batch_run`.
4. Bước 5: probe 10 mục RG-09 — chạy sau khi ghi report; đỏ đúng kỳ vọng vì các mục là BLOCKED thật (kết quả chính xác nằm trong báo cáo worker_done).
5. Bước 6: `git diff --check` — chạy sau khi ghi report (kết quả trong báo cáo worker_done).

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

- Thông điệp nguyên văn: `BLOCKED: OTHER_WORKFLOWS_RUNNING count=2 ids=[ProductionBatchWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c, VideoProductionWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c:video:0]`.
- Không đo được vì BLOCKED ở kiểm chỉ đọc giữa stop và start (trước khi tạo lô): không có `- budget:`, `- seed:`, `- start:`, `- pre_check:`, `- ai_calls_source:`, `- batch_after_run=[...]`, `- qc_evidence:` (blocking_gates, mp4_ms/voice_ms/delta_ms), md5, ready_seconds. Không số nào được bịa.
- Workflow còn RUNNING: `ProductionBatchWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c` và con `:video:0`.

## Open item

- OI-PW-E2E-01: lô không rời CREATED nên FinalizeBatch trả FORBIDDEN_TRANSITION; do gói PW-G4-FIX2 sửa, chưa gộp. RG-09 không chấm theo trạng thái dòng lô.
- OI-CP7-10-F7: đã sửa trong driver (lọc plan và analysis theo job_id); chưa kiểm chứng trên ngăn xếp thật.
- OI-CP7-10-F8: lô `2a1e2434-456a-42b7-84ad-14e77565736c` (con `:video:0`) vẫn RUNNING trên Temporal chặn pre-check; cần Control xin user terminate rồi cấp lượt mới.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ giữ nguyên.
- Không SQL ghi; không cancel, terminate hay signal workflow; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
