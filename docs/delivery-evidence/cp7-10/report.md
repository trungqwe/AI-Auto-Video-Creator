# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026. HEAD sau rebase (cơ sở của lần chạy): `7e14c9d8d8e0153f497fcf586e3f04daba9d1153`. Nền: `99315ff6f2831d2017b215daab78d6c9292a14e5`. Interpreter khoá: `.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

Kết luận trung thực: lô 1 video trên ngăn xếp thật BLOCKED ở stage `process` (activity `NormalizeMedia`, code `output_exists`). Không mục RG-09 nào được chứng minh PASS.

## Lệnh đã chạy

1. `git rebase 99315ff6f2831d2017b215daab78d6c9292a14e5`: hoàn tất, 10 commit, exit 0, không xung đột, cây làm việc sạch.
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không cảnh báo.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (chạy thêm cờ `-s` để ghi lại output in ra; không đổi hành vi test): 22 passed, 0 failed, 11 error, exit code 1, thời gian 640,92 giây (0:10:40). Chỉ chạy ngăn xếp thật đúng một lần, một lô 1 video; không thử lại, không tạo lô thứ hai.
4. `git diff --check` sau khi ghi báo cáo: xem kết quả ở lượt báo cáo cuối (exit code ghi trong worker_done).
5. Probe `python -c` 10 mục RG-09: đỏ do các mục BLOCKED (kết quả trung thực, không sửa dòng báo cáo).

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

Fixture `batch_run` fail nên test không in dòng `RG-09.` hay dòng `- ...` nào (không có elapsed, md5/sha256, ledger, ready_seconds, budget, pre_stop_attempts). Thông điệp BLOCKED (đã che sẵn bởi driver):

- Job kết thúc ở FAILED_FINAL: `stage=process status=FAILED_FINAL activity=NormalizeMedia code=output_exists field_errors={}`; không thử lại, không tạo lô khác.
- `render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]`.
- `launcher_seed=[Đã nạp bộ media seed (idempotent).]`, `seed_counts={"hooks": 10, "media_assets": 411, "sources": 7}`.
- `script_length=[segments=5 words=152 wpm=136 est_ms=67058 range_ms=61000-70000 verdict=within_range]`.
- `job=FAILED_FINAL job_wait=None`.
- `stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=SUCCEEDED;process#1=FAILED_FINAL/output_exists]`.
- `serve_log_tail`: dòng DEBUG cuối của TTS (phonemes của kịch bản, kết thúc bằng `Created audio in length`), không chứa lỗi `process`.

Tiến triển so với lần chạy cũ: script 5 đoạn nằm trong khoảng thời lượng giọng đọc, tts và align đã SUCCEEDED; lô dừng ở `process` trước khi tới render, nên chưa kiểm được resume, cloud verify và cleanup.

## Open item

- Stage `process` / `NormalizeMedia` trả `output_exists` (FAILED_FINAL). Nguyên nhân gốc nằm ngoài owned paths (`src/**` hoặc trạng thái thư mục output/staging của ngăn xếp), cần Control quyết định gói chủ xử lý trước khi chạy lại lô.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi; không sửa `src/**`, profile, DB hay launcher; không sửa driver hay test ở lượt này.
- Không đọc `Credentials/`; không có capability, cookie, token hay file ID trong tệp này.
- Ngăn xếp thật chỉ chạy đúng một lần, một lô; không thử lại.
