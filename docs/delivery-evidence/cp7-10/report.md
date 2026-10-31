# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 01/11/2026. HEAD sau rebase (cơ sở của lần chạy): `aefc5f493589464d4d64e5d4195f9f46854cb8c7`. Nền: `8f042f8afc3b3ef30a8169f179068091f3d46327`. Interpreter khoá: `.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

Kết luận trung thực: lô 1 video trên ngăn xếp thật BLOCKED ở stage `qc` (activity `inspect_output`, code `quality_gates_failed`). Các stage analyze → render đều SUCCEEDED, nhưng cổng QC cứng không đạt nên không mục RG-09 nào được chứng minh PASS.

## Lệnh đã chạy

1. `git rebase 8f042f8afc3b3ef30a8169f179068091f3d46327`: hoàn tất, 11 commit, exit 0, không xung đột, cây làm việc sạch; lane chỉ đổi ba tệp trong owned paths.
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không cảnh báo.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider`: 22 passed, 0 failed, 11 error, exit code 1, thời gian 991,36 giây (0:16:31). Chỉ chạy ngăn xếp thật đúng một lần, một lô 1 video; không thử lại, không tạo lô thứ hai.
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

Fixture `batch_run` fail nên 11 test RG-09 ở trạng thái error và không in dòng `RG-09.` hay dòng chi tiết nào (không có elapsed, md5/sha256, ledger, ready_seconds, budget, pre_stop_attempts). Thông điệp BLOCKED (đã che sẵn bởi driver):

- Job kết thúc ở FAILED_FINAL: `stage=qc status=FAILED_FINAL activity=inspect_output code=quality_gates_failed field_errors={}`; không thử lại, không tạo lô khác.
- `render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]`.
- `launcher_seed=[Đã nạp bộ media seed (idempotent).]`, `seed_counts={"hooks": 10, "media_assets": 411, "sources": 7}`.
- `script_length=[segments=5 words=151 wpm=136 est_ms=66617 range_ms=61000-70000 verdict=within_range]`.
- `job=FAILED_FINAL job_wait=None`.
- `stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=SUCCEEDED;process#1=SUCCEEDED;render#1=SUCCEEDED;qc#1=FAILED_FINAL/quality_gates_failed]`.
- `serve_log_tail`: chỉ là cảnh báo asyncio `Task was destroyed but it is pending` (to_thread), không nêu cổng QC nào hỏng.

Tiến triển so với lần chạy trước: `process` (NormalizeMedia) và `render` đã SUCCEEDED; lô dừng ở `qc`, nên chưa kiểm được upload Drive, verify, resume, cleanup. Thông điệp BLOCKED không nêu cổng QC cụ thể nào không đạt.

## Open item

- Stage `qc` / `inspect_output` trả `quality_gates_failed` (FAILED_FINAL) trên đầu ra render. Cổng QC cụ thể không đạt chưa được driver ghi lại (field_errors rỗng); cần Control xác định gói chủ (src/** của QC hoặc render) và đọc chi tiết kết quả QC của job trước khi chạy lại lô.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; không nâng trần 25 lời gọi AI hay 3 USD.
- Không SQL ghi; không sửa `src/**`, profile, DB hay launcher; không sửa driver hay test ở lượt này.
- Không đọc `Credentials/`; không có capability, cookie, token hay file ID trong tệp này.
- Ngăn xếp thật chỉ chạy đúng một lần, một lô; không thử lại.
