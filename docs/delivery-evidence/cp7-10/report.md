# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026. Lane `lane-cp7-10`, interpreter khoá `.local-tools\runtime\8715e538\venv\Scripts\python.exe`. Lane đã rebase lên `984946d`; HEAD nền khi chạy là `7f1e349` (kèm thay đổi chưa commit trong driver và test).

## Lệnh đã chạy

- `git rebase 984946d8427b05977fe7700c7635fbc933a5811a`: hoàn tất, không xung đột. `tools/launcher/launcher.py` có `seed_media` (in dòng `Đã nạp bộ media seed (idempotent).`) và `seed_defaults` gọi `seed_production_render_config` trong luồng `start`.
- Kiểm tĩnh bước 8 (ast, tên bị gỡ, `post_batch(1)` đúng một lần, cổng render config trước `post_batch`): exit 0.
- `git diff --check` (trước khi chạy ngăn xếp thật): exit 0.
- Test thuần (`-k unit`, không chạm ngăn xếp): 17 passed.
- `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (ngăn xếp thật, đúng một lần): 17 passed, 0 failed, 11 errors, exit code 1, 181,62 giây. Cả 11 error là lỗi setup của fixture `batch_run` cùng một nguyên nhân.

## Trạng thái

0/10 PASS. Fixture `batch_run` báo BLOCKED trước khi tạo lô: không có lô, job hay stage nào được tạo, nên không mục RG-09 nào được chứng minh.

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

Blocker nguyên văn (đã che): `BLOCKED: không bắt được URL /launch trong 120 giây`, phát sinh tại `start_capturing` (`tools/real/cp7_batch_driver.py`).

- `launcher start` trả exit code 0 (nếu khác 0 driver đã báo `launcher start rc=...`), nhưng tệp bắt URL `/launch` (qua `BROWSER`) không được tạo trong 120 giây.
- stage / activity / code / field_errors: không áp dụng, vì job chưa được tạo (`stage=none`).
- `launcher_seed`: không có số liệu. Lỗi xảy ra trong `start_capturing`, trước khi `run_batch` gán `launcher_seed_line`; stdout của launcher không được đưa vào chuỗi BLOCKED.
- `seed_counts` (sources, hooks, media_assets): không có số liệu, vì `db.seed_counts()` chạy sau `start_capturing`.
- `render_config=[...]`: không đo được, vì `require_render_config` chạy sau `start_capturing`; không có lô nào được tạo.
- Driver đã xác nhận bằng test canh: không còn `ensure_voice_staging`, `ensure_seed_media`, `staging_voice`, `seed_import`; `session.post_batch(1)` xuất hiện đúng một lần; không có lô thứ hai.

Nguyên nhân gốc chưa xác định, và lần chạy này không chứng minh được. Giả thuyết chưa kiểm chứng: `cmd_start` in `Worker đang chạy; bỏ qua khởi động mới.` và thoát 0 khi PID cũ còn sống, nên `on_ready` không mở trình duyệt lần nào. Ngoài ra worker có thể không kế thừa `BROWSER`. Theo quy định "đúng một lần", không chạy lại để kiểm chứng.

## Open item

- OI-RG09-LAUNCH-URL-01: driver không lấy được URL `/launch` sau `launcher start`. Cần Control xác minh trạng thái worker trước lượt chạy (PID còn sống hay không) và cách launcher cấp URL khi worker đã chạy sẵn. Việc sửa thuộc `tools/launcher/**`, ngoài owned paths.
- OI-PW-E2E-01 (writer CREATED→RUNNING): chưa được chứng minh hay bác bỏ bởi lần chạy này.
- Các gói PW-W2-FIX5, ADAPT-E-FIX3, ADAPT-E-FIX4, PW-W1-FIX1 là phần production đã gộp; lần chạy này chưa tới stage nào nên chưa chứng minh hiệu quả của chúng.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09, không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi, không sửa `src/**`, không dữ liệu giả, không đọc `Credentials/`.
- Không có capability, cookie, token hay file ID trong tệp này.
- Chạy đúng một lần, không có lô nào được tạo.
