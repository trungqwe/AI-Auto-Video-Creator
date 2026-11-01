# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `1f872a5d9eec3ae910d5e07a200e644692885a92`.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED**. Sửa F7 đã làm xong và test unit xanh (38 passed). Lần chạy ngăn xếp thật duy nhất (bước 16) dừng ngay ở kiểm chỉ đọc giữa stop và start với `BLOCKED: OTHER_WORKFLOWS_RUNNING count=2`: trên Temporal vẫn còn `ProductionBatchWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c` và `VideoProductionWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c:video:0` đang RUNNING. Đây không phải lô do lượt này tạo (driver dừng trước khi tạo lô); nhiều khả năng là lô B của lượt trước (plan_digest BLOCKED) chưa được terminate. Theo lệnh làm việc, driver không cancel, terminate hay signal workflow và không chạy lại. Không có lô mới, nên chưa kiểm chứng được sửa F7 trên ngăn xếp thật; không mục RG-09 nào có evidence PASS.

## Nguyên nhân và sửa

1. F7: record_key của bảng creative là id do D sinh: `plan:<job_id>:r<rev>`, `analysis:<job_id>:r<rev>`, với job_id = `<B>:job:<ordinal>`. Driver trước lọc theo `<ws>:<B>:video:` nên không thấy dòng nào. Đã sửa: `plan_key_prefix(job_id)` và `analysis_key_prefix(job_id)`; `_plan_row`, `build_trace`, `plan_digest`, `collect_script_length`, `collect_qc_evidence` nhận job_id.
2. Đếm lời gọi AI vẫn theo `<ws>:<B>:video:` (`video_key_prefix`, `CostWatch.bind_prefix`) vì operation_key của `cp_ai_invocation_records` bắt đầu bằng workflow_id con `<B>:video:<seq>`.
3. BLOCKED phát sinh sau khi lô đã tạo mang thêm ` run_ids=[batch_id=<B> job_id=<J>]` (`run_batch`, `except BlockedError`), để Control biết lô cần terminate. BLOCKED trước khi có lô giữ nguyên.

## Lệnh đã chạy

1. RED (bước 6): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 1, 6 failed, 32 passed, 11 deselected. Hỏng: test_unit_plan_row_filters_by_record_key_prefix (oracle tham số truy vấn `('b:job:1',)` khác `('plan:b:job:1:r',)`); test_unit_build_trace_uses_ledger_snapshot_id, test_unit_build_trace_blocks_without_ledger_snapshot, test_unit_build_trace_filters_by_record_key_prefix (TypeError chữ ký, thiếu `prefix`); test_unit_blocked_message_reports_script_length (assert nguồn văn bản); test_unit_creative_key_prefixes_use_job_id (AttributeError ký hiệu mới).
2. GREEN (bước 14): cùng lệnh — exit 0, `38 passed, 11 deselected`.
3. `git diff --check` (bước 15): exit 0, không output.
4. Chạy thật (bước 16), đúng một lần: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -s` — exit 1, `38 passed, 11 errors in 1.95s` (khoảng 3 giây tổng). Mọi lỗi là `BLOCKED: OTHER_WORKFLOWS_RUNNING` ở fixture `batch_run`.
5. Probe 10 mục RG-09 (bước 18): đỏ như kỳ vọng vì các mục là BLOCKED thật; không chỉnh report để qua probe.
6. `git diff --check` lần cuối (bước 19): exit 0.

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
- Không tạo lô mới ở lượt này nên không có `run_ids`; không có số đo ai_calls, qc_evidence, batch_after_run, elapsed, md5, ready_seconds. Không số nào được bịa.
- Workflow còn RUNNING cần Control xin user terminate trước lượt kế: `ProductionBatchWorkflow=2a1e2434-456a-42b7-84ad-14e77565736c` (con `:video:0`). Tiền tố `2a1e2434` khác lô `cc2f3457` đã terminate lúc 02:17Z, nên đây là lô tạo sau đó (lượt Worker trước, BLOCKED ở plan_digest).

## Open item

- OI-PW-E2E-01: lô không rời CREATED nên FinalizeBatch trả FORBIDDEN_TRANSITION; do gói PW-G4-FIX2 sửa, chưa gộp. RG-09 không chấm theo trạng thái dòng lô.
- OI-CP7-10-F7: đã sửa trong driver (lọc plan và analysis theo job_id); chưa kiểm chứng trên ngăn xếp thật.
- OI-CP7-10-F8: lô `2a1e2434-456a-42b7-84ad-14e77565736c` còn RUNNING trên Temporal chặn pre-check; cần terminate (quyết định của user) rồi cấp lượt mới.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ giữ nguyên.
- Không SQL ghi; không cancel, terminate hay signal workflow; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
