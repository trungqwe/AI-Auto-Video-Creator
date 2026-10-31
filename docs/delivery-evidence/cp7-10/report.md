# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc 41c0b0d (đã rebase lên 33ad9ba; bản này đã gỡ vòng tạo lại lô, kết quả lần mở trước không còn dùng).

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (ngăn xếp thật, đúng một lần): 11 passed, 0 failed, 11 errors tại fixture batch_run, exit 1, 333,47 giây (pytest) / 334,4 giây (tường). Kiểm tĩnh bằng ast và `git diff --check` trước khi chạy: exit 0.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Fixture batch_run lỗi vì job của lô 1 video kết thúc FAILED_FINAL ở stage tts.

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

- blocker: `BLOCKED: job kết thúc ở FAILED_FINAL stage=tts status=FAILED_FINAL activity=CreateVoiceTrack code=staging_missing field_errors={}; không thử lại, không tạo lô khác; job=FAILED_FINAL job_wait=None stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=FAILED_FINAL/staging_missing] seed=[sources_registered=0 sources_replayed=0 sources_existing=7 hooks_imported=0 hooks_existing=10 assets_new=0 assets_existing=22 article_image_rights_status=UNVERIFIED]` (đã che bí mật; đuôi serve.log chỉ là cảnh báo asyncio "Task was destroyed but it is pending" khi tiến trình dừng).
- job hỏng được đếm trong phép đo: không thử lại, không có lô thứ hai (`session.post_batch(1)` gọi đúng một lần).
- tiến triển: analyze, script, media_select, plan đạt SUCCEEDED; tts (activity CreateVoiceTrack) FAILED_FINAL với code staging_missing, field_errors rỗng. Các stage align, render, upload Drive, verify, completion không được chạy.
- seed_import: sources_existing=7, hooks_existing=10, assets_existing=22, article_image_rights_status=UNVERIFIED (seed có sẵn, không nhập mới).
- ready_seconds, ai_calls, spent_usd, drive_bytes, elapsed_s: không đo được từ fixture vì fixture không trả kết quả (không có dòng budget).
- unit: 11 test_unit_* thuần đạt (11 passed, 0 failed), gồm test_unit_no_batch_retry_loop và test_unit_format_failed_stage.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job FAILED_FINAL; không hạ ngưỡng, không nâng trần 25 lời gọi AI hay 3 USD, không SQL ghi, không sửa src, không dựng dữ liệu giả;
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ là số đo, driver không UPDATE DB;
3. ba bản sửa production đã gộp (D-15-FIX1, PW-G2-FIX1, PW-G4-FIX1) có hiệu lực trên mã này; PW-G4-FIX1 làm job lỗi tới FAILED_FINAL thay vì treo, nên blocker được báo ngay;
4. RG-09 chạy đúng một lô 1 video; lỗi `staging_missing` ở stage tts thuộc production (ngoài owned paths), cần Control giao gói sửa; ngăn xếp thật không được chạy lần hai trong lượt này;
5. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Không đo được từ fixture (không có dòng budget); lượt chạy 334,4 giây; không đọc Credentials/; không có bí mật.
