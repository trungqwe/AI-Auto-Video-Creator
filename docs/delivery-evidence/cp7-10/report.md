# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `bb8c43b8e637788c1174693c213d8b654b522fb8`.
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED**. Sau rebase lên `2687822f8841fcda7c38c692cdd997c16494b1a3`, `git diff --check` exit 0 và test unit xanh (38 passed, 11 deselected). Lần chạy ngăn xếp thật duy nhất dừng ở `launcher start` (rc=1): `Ứng dụng chưa mở cổng; xem logs/serve.log`. Dòng cuối của `serve.log` ghi `BLOCKED: cổng production chưa sẵn: DrivePlacementError: Drive access token is unavailable`, tức broker không cấp được Drive access token cho tiến trình production. Driver dừng trước khi tạo lô nên không có batch id B, job id J hay `run_ids` của lượt này. Không mục RG-09 nào có số đo; chưa kiểm chứng được sửa F7 trên ngăn xếp thật. Việc cần user hoặc Control xử lý: khôi phục Drive OAuth token trong broker DPAPI của phân hệ J (worker không đọc hay in bí mật).

## Nguyên nhân và sửa

1. F7: record_key của bảng creative là id do D sinh: `plan:<job_id>:r<rev>`, `analysis:<job_id>:r<rev>`, với job_id = `<B>:job:<ordinal>`. Driver trước lọc theo `<ws>:<B>:video:` nên không thấy dòng nào. Đã sửa: `plan_key_prefix(job_id)` và `analysis_key_prefix(job_id)`; `_plan_row`, `build_trace`, `plan_digest`, `collect_script_length`, `collect_qc_evidence` nhận job_id.
2. Đếm lời gọi AI vẫn theo `<ws>:<B>:video:` (`video_key_prefix`, `CostWatch.bind_prefix`) vì operation_key của `cp_ai_invocation_records` bắt đầu bằng workflow_id con `<B>:video:<seq>`.
3. BLOCKED phát sinh sau khi lô đã tạo mang thêm ` run_ids=[batch_id=<B> job_id=<J>]` (`run_batch`, `except BlockedError`), để Control biết lô cần terminate. BLOCKED trước khi có lô giữ nguyên.
4. Lane đã rebase lên `2687822f8841fcda7c38c692cdd997c16494b1a3`; kết quả kiểm của lần mở trước không còn dùng được. Lượt này không đổi mã driver hay test.

## Lệnh đã chạy

1. Bước 1: `git rebase 2687822f8841fcda7c38c692cdd997c16494b1a3` — exit 0, `Successfully rebased and updated refs/heads/trungqwe/lane-cp7-10` (18 commit), HEAD là hậu duệ của đầu tích hợp, cây làm việc sạch.
2. Bước 2: `git diff --check` — exit 0, không output.
3. Bước 3: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `38 passed, 11 deselected in 0.16s`.
4. Bước 4 (đúng một lần, bắt đầu 05:53:15Z): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` — exit 1, `38 passed, 11 errors in 126.37s (0:02:06)`. Cả 11 lỗi là `BLOCKED: launcher start rc=1` ở fixture `batch_run`.
5. Bước 5: ghi lại report.md này bằng công cụ sửa tệp (UTF-8).
6. Bước 6: probe 10 mục RG-09 — đỏ đúng kỳ vọng vì các mục là BLOCKED thật (exit code và danh sách mục đỏ nằm trong báo cáo worker_done).
7. Bước 7: `git diff --check` sau khi ghi report — kết quả nằm trong báo cáo worker_done.

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

- Thông điệp của driver: `BLOCKED: launcher start rc=1`, đầu ra launcher kết thúc bằng `Ứng dụng chưa mở cổng; xem logs/serve.log`.
- Dòng cuối `serve.log` của launcher (thư mục dữ liệu `AIAutoVideoCreator\logs`): `BLOCKED: cổng production chưa sẵn: DrivePlacementError: Drive access token is unavailable`.
- Trước dòng đó launcher đã nạp namespace Temporal, nguồn, prompt mặc định và bộ media seed (idempotent); Kokoro TTS chạy ở giai đoạn khởi tạo cổng production.
- Batch id B, job id J: không có (driver dừng trước khi tạo lô). Không có `run_ids`.
- Không đo được vì BLOCKED trước khi tạo lô: `- budget:`, `- seed:`, `- start:`, `- pre_check:`, `- ai_calls_source:`, `- batch_after_run=[...]`, `- qc_evidence:` (blocking_gates, mp4_ms, voice_ms, delta_ms), ai_calls (trần 25), ledger delta (trần 3 USD), Drive bytes (trần 200 MiB), md5 local và cloud, ready_seconds của resume (ngưỡng 300 giây), attempt trước và sau resume, số từ align được chia. Không số nào được bịa.
- Thời gian chạy của lần pytest duy nhất: 126,37 giây (trần 2 giờ).

## Open item

- OI-PW-E2E-01: lô không rời CREATED nên FinalizeBatch trả FORBIDDEN_TRANSITION; do gói PW-G4-FIX2 sửa, chưa gộp. RG-09 không chấm theo trạng thái dòng lô.
- OI-CP7-10-F7: đã sửa trong driver (lọc plan và analysis theo job_id); chưa kiểm chứng trên ngăn xếp thật.
- OI-CP7-10-F9: broker không cấp được Drive access token (`DrivePlacementError: Drive access token is unavailable`) nên cổng production không mở; cần user hoặc phân hệ J khôi phục OAuth token rồi Control cấp lượt mới.
- Lô cũ: không có lô nào được tạo ở lượt này, nên không có `run_ids` cần terminate.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ, 300 giây resume giữ nguyên.
- Không SQL ghi; không cancel, terminate hay signal workflow; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
