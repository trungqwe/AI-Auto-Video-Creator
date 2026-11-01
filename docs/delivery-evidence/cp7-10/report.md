# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `4431fe29148680466925db26e1b479dfffc1bf4c`.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED**. Ba nhóm sửa của CTRL-CP7-10-F6 đã làm xong, test unit xanh (37 passed). Lần chạy ngăn xếp thật duy nhất (bước 21) qua được kiểm Temporal (`other_workflows_running` không chặn) và tạo lô, nhưng dừng ở `plan_digest` với `BLOCKED: thiếu khoá plan trong cp_production_plans`: truy vấn `_plan_row` lọc theo `starts_with(record_key, '<ws>:<B>:video:')` không trả dòng nào khi stage `plan` đã SUCCEEDED. Nghĩa là record_key của `cp_production_plans` không bắt đầu bằng tiền tố `<ws>:<B>:video:` như giả định của lệnh làm việc. Không chạy lại, không tạo lô khác. Vì fixture lỗi lúc setup nên 11 test RG-09 chưa chạy (11 errors); không mục RG-09 nào có evidence PASS.

## Nguyên nhân và sửa

1. Kiểm chỉ đọc Temporal giữa stop và start: `require_no_other_workflows` liệt kê workflow RUNNING (`ExecutionStatus = "Running"`, 127.0.0.1:7233, namespace default); có `ProductionBatchWorkflow`, `VideoProductionWorkflow` hay `DebugStageWorkflow` thì BLOCKED `OTHER_WORKFLOWS_RUNNING` kèm id. Driver không cancel, terminate hay signal.
2. Lời gọi AI = số dòng `cp_ai_invocation_records` có record_key bắt đầu `<ws>:<B>:video:` (`ai_invocation_count`, `CostWatch.bind_prefix`); ledger chi phí luôn 0 vì `route_cost_per_request=0`. `drive_bytes` và `locations` lọc theo job J (`owner_ref` hoặc sổ hoàn tất); plan và prompt lọc theo tiền tố record_key của lô B.
3. Report ghi `blocking_gates`, thời lượng mp4 so với giọng (`format_qc_evidence`, `collect_qc_evidence`) và trạng thái lô sau lượt (`collect_batch_running`); thông điệp BLOCKED của job không COMPLETED có đủ các trường này.

## Lệnh đã chạy

1. RED (bước 7): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 1, 12 failed, 25 passed. Hỏng: test_unit_blocked_message_reports_script_length, test_unit_plan_row_filters_by_record_key_prefix, test_unit_locations_and_drive_bytes_filter_by_job, test_unit_build_trace_filters_by_record_key_prefix, test_unit_driver_checks_temporal_between_stop_and_start_read_only (oracle hợp lệ), cùng 7 test dùng ký hiệu mới (AttributeError).
2. Probe bước 18 (không còn lọc theo cửa sổ thời gian): exit 0.
3. GREEN (bước 19): lần 1 exit 1 (1 failed, 36 passed) do `test_unit_cost_watch_counts_ai_calls_from_invocation_records` tự mâu thuẫn thứ tự gọi (trước `bind_prefix` không có truy vấn DB); đã dời assert `db.prefixes` xuống sau `check()` cuối trong chính test mới. Lần 2: exit 0, 37 passed, 11 deselected.
4. `git diff --check` (bước 20): exit 0.
5. Chạy thật (bước 21), đúng một lần: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` — exit 1, `37 passed, 11 errors in 246.12s`, từ 02:47:46Z đến 02:51:54Z.
6. Probe 10 mục RG-09 (bước 23): đỏ như kỳ vọng vì các mục ở dưới là BLOCKED; không chỉnh report để qua probe.
7. `git diff --check` lần cuối (bước 24): exit 0.

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

- Lỗi nguyên văn (đã che): `BLOCKED: thiếu khoá plan trong cp_production_plans`, phát sinh ở `plan_digest(db, job_id, result.record_prefix)` khi stage `plan` đạt SUCCEEDED (tools/real/cp7_batch_driver.py, `_plan_row`).
- Kiểm Temporal trước start: qua (`other_workflows_running` không gây BLOCKED, do đó là 0); driver chỉ đọc.
- Các dòng `- ` (ai_calls, qc_evidence, batch_after_run, elapsed, md5/sha256, ready_seconds) không được phát ra vì fixture lỗi trước khi test RG-09 chạy; không có số đo nào được bịa thêm.
- Id lô B không được in ra trong output của fixture (BlockedError ném trước khi trả kết quả). Lô này có thể còn RUNNING trên Temporal sau lượt: Control cần liệt kê workflow `ProductionBatchWorkflow` mới nhất và xin terminate trước lượt kế (theo quyết định của user ngày 01/11/2026).
- Đề xuất cho Control (không tự sửa vì ngoài lệnh làm việc): kiểm record_key thực của `cp_production_plans` cho lô B, hoặc lọc plan theo `job_id`/snapshot thay cho tiền tố `<ws>:<B>:video:`; rồi cấp lượt mới. Ngoài ra nên cho driver gắn trạng thái lô và id lô vào thông điệp BLOCKED khi lỗi xảy ra trước cổng job FAILED.

## Open item

- OI-PW-E2E-01: lô không rời CREATED nên FinalizeBatch trả FORBIDDEN_TRANSITION; do gói PW-G4-FIX2 sửa, chưa gộp. RG-09 không chấm theo trạng thái dòng lô.
- OI-CP7-10-F7: record_key của `cp_production_plans` không khớp tiền tố `<ws>:<B>:video:` (xem Chi tiết đo); cần quyết định cách lọc plan theo lô.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ giữ nguyên.
- Không SQL ghi; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
