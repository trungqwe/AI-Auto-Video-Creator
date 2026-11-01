# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 01/11/2026. HEAD sau rebase (cơ sở của lần chạy): `90828f8ec1d937b35eb8f4e37c75176fad385f87`. Nền: `7a45f6179fe9d2841b458e0176bde7749b78ad5b`. Interpreter khoá: `.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

Kết luận trung thực: fixture `batch_run` BLOCKED ở bước dựng trace sau lô: `BLOCKED: thiếu khoá payload trong cp_production_snapshots`. Vì fixture fail nên không mục RG-09 nào có dòng PASS thật, và tất cả được ghi BLOCKED.

## Lệnh đã chạy

1. `git rebase 7a45f6179fe9d2841b458e0176bde7749b78ad5b`: hoàn tất, 12 commit, exit 0, không xung đột, cây làm việc sạch; lane chỉ đổi ba tệp trong owned paths.
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không cảnh báo.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (có thêm cờ `-s` chỉ để không chặn stdout, kèm chuyển hướng output ra tệp tạm): 22 passed, 0 failed, 11 error, exit code 1, thời gian 423,33 giây (0:07:03). Chỉ chạy ngăn xếp thật đúng một lần, một lô 1 video; không thử lại, không tạo lô thứ hai.
4. `git diff --check` sau khi ghi báo cáo: xem kết quả trong worker_done.
5. Probe `python -c` 10 mục RG-09: đỏ do các mục BLOCKED (kết quả trung thực, không sửa dòng báo cáo); xem worker_done.

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

Fixture `batch_run` fail nên 11 test RG-09 ở trạng thái error và không in dòng `RG-09.` hay dòng chi tiết nào (không có elapsed, md5/sha256, ledger, ready_seconds, budget, pre_stop_attempts). Thông điệp BLOCKED nguyên văn:

- `BlockedError: BLOCKED: thiếu khoá payload trong cp_production_snapshots`, phát sinh tại `tools/real/cp7_batch_driver.py` trong `build_trace` (gọi từ `run_batch`), tức là sau khi lô đã chạy xong và driver đọc snapshot để dựng trace.
- Thông điệp này không nêu stage, activity, code, render_config, seed_counts, script_length, stages hay serve_log_tail; không có cổng QC cụ thể nào được nêu.
- Trong lần chạy này driver không báo job kết thúc ở stage nào; không suy diễn trạng thái stage hay QC từ lần chạy trước.
- 22 test không dùng fixture `batch_run` đều passed.

## Open item

- `build_trace` đọc `cp_production_snapshots.payload` trả về rỗng/thiếu cho job vừa chạy. Cần Control xác định gói chủ (schema/lưu snapshot ở `src/**` hoặc truy vấn trong driver của CP7-10) và cho biết khoá/bảng đúng của snapshot trước khi chạy lại lô. Chưa thể kết luận stage hay QC của lô này.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi; không sửa `src/**`, profile, DB hay launcher; không sửa driver hay test ở lượt này.
- Không đọc `Credentials/`; không có capability, cookie, token hay file ID trong tệp này.
- Ngăn xếp thật chỉ chạy đúng một lần, một lô; không thử lại.
