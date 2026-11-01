# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 01/11/2026. HEAD cơ sở của lần chạy: `82d5c18c98963cce760541396fb6956aae268d64`. Nền: `7a45f6179fe9d2841b458e0176bde7749b78ad5b`. Interpreter khoá: `.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

Kết luận trung thực: lượt này sửa nguyên nhân BLOCKED của lượt trước (id snapshot) và có RED/GREEN thật cho bốn test mới, nhưng lần chạy ngăn xếp thật bị fixture `batch_run` dừng bằng `psycopg.errors.ConnectionTimeout: connection timeout expired` khi driver đọc DB. Vì fixture lỗi nên không mục RG-09 nào có dòng PASS thật, và tất cả được ghi BLOCKED.

## Nguyên nhân và sửa

- Lượt trước BLOCKED vì `build_trace` đọc `cp_production_snapshots` theo `cp_video_jobs.snapshot_ref`. Giá trị đó chỉ là chỗ giữ `allocation:<slot>` do `src/controlplane/infrastructure/db/orchestration/allocation.py:97` ghi khi cấp job, không phải id snapshot sản xuất nên truy vấn trả rỗng.
- Id thật nằm ở `cp_completion_ledger.snapshot_ref` (`src/controlplane/application/orchestration/completion_assembler.py:150`), trùng `production_snapshot_ref` của render package.
- Driver `tools/real/cp7_batch_driver.py` thêm `job_snapshot_id` (chỉ SELECT trên `cp_completion_ledger`) và dùng ở `build_trace`, `render_matches_plan`, `qc_gates`. Không còn chuỗi `SELECT snapshot_ref FROM controlplane.cp_video_jobs` trong driver; `job_for_batch` giữ nguyên.
- RED (bước 2): 3 failed, 1 passed đúng oracle (`BlockedError` thiếu khoá payload trong cp_production_snapshots; `render_matches_plan` trả False; assert `job_snapshot_id(db, job_id)` trong `qc_gates`). GREEN (bước 7): 4 passed.

## Lệnh đã chạy

1. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k snapshot` (RED, trước khi sửa driver): 3 failed, 1 passed, 33 deselected, 0,19 giây.
2. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k snapshot` (GREEN, sau khi sửa driver): 4 passed, 33 deselected, 0,05 giây, exit 0.
3. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không cảnh báo.
4. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (có thêm cờ `-s`, output ra tệp ngoài repo): 26 passed, 0 failed, 11 error, exit code 1, 272,67 giây (0:04:32). Chỉ chạy ngăn xếp thật đúng một lần, một lô 1 video; không thử lại, không tạo lô thứ hai.
5. `git diff --check` sau khi ghi báo cáo và probe `python -c` 10 mục RG-09: xem kết quả trong worker_done.

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

Fixture `batch_run` fail nên 11 test RG-09 ở trạng thái error và không in dòng `RG-09.` hay dòng chi tiết nào (không có elapsed, md5/sha256, ledger, ready_seconds, budget, pre_stop_attempts). Lỗi nguyên văn:

- `psycopg.errors.ConnectionTimeout: connection timeout expired`, phát sinh tại `tools/real/cp7_batch_driver.py` (`db_now` gọi từ `_records`, `spent`, `watch.check` trong `run_batch`), khi kết nối PostgreSQL ở `127.0.0.1` quá hạn `connect_timeout=10`.
- Đây không phải `BlockedError` về snapshot như lượt trước; lần này lỗi nằm ở kết nối DB nên driver chưa tới `build_trace`. Lỗi không nêu stage, activity, code, render_config, script_length hay diag nào của lô.
- Không suy diễn trạng thái stage hay QC từ lần chạy trước. Việc sửa `job_snapshot_id` mới được chứng minh bằng unit test (4 passed), chưa được chứng minh trên ngăn xếp thật.
- 26 test không dùng fixture `batch_run` đều passed.

## Open item

- Cần Control kiểm PostgreSQL của ngăn xếp thật (cổng DB do launcher cấp, `connect_timeout=10`) có còn sống và nhận kết nối khi driver chạy không, rồi mở lượt chạy lại một lô. Chưa thể kết luận stage hay QC của lô này.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi; không sửa `src/**`, profile, DB hay launcher.
- Không đọc `Credentials/`; không có capability, cookie, token, mật khẩu DB hay file ID trong tệp này.
- Ngăn xếp thật chỉ chạy đúng một lần, một lô; không thử lại.
