# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc 369fea6 (commit của lượt này nằm ngay sau HEAD đó; bản này thêm `ensure_voice_staging`, kết quả các lần mở trước không còn dùng).

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (ngăn xếp thật, đúng một lần): 12 passed, 0 failed, 11 errors tại fixture batch_run, exit 1, 483,84 giây (pytest) / 484,8 giây (tường). Kiểm tĩnh bằng ast và `git diff --check` trước khi chạy: exit 0.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Fixture batch_run lỗi vì job của lô 1 video kết thúc FAILED_FINAL ở stage render (các stage tts, align, process đã SUCCEEDED).

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

- blocker: `BLOCKED: job kết thúc ở FAILED_FINAL stage=render status=FAILED_FINAL activity=resolve_render_package code=ACTIVITY_ABORTED field_errors={}; không thử lại, không tạo lô khác; job=FAILED_FINAL job_wait=None stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=SUCCEEDED;process#1=SUCCEEDED;render#1=FAILED_FINAL/ACTIVITY_ABORTED] seed=[sources_registered=0 sources_replayed=0 sources_existing=7 hooks_imported=0 hooks_existing=10 assets_new=0 assets_existing=22 article_image_rights_status=UNVERIFIED]` (đã che bí mật; đuôi serve.log chỉ có log DEBUG của Kokoro về phoneme và độ dài âm thanh 27,43 giây).
- job hỏng được đếm trong phép đo: không thử lại, không có lô thứ hai (`session.post_batch(1)` gọi đúng một lần).
- tiến triển so với lượt trước: analyze, script, media_select, plan, tts (CreateVoiceTrack), align, process đạt SUCCEEDED; render (activity resolve_render_package) FAILED_FINAL với code ACTIVITY_ABORTED, field_errors rỗng. Các stage upload Drive, verify, completion không được chạy.
- staging_voice: production chưa có mã tạo `<staging>/voice` (RealKokoroTts đòi có sẵn, mã `staging_missing`); driver tạo thư mục rỗng trước khi tạo lô như ADAPT-SEED tạo `staging/media`. Giá trị 'created' hay 'existing' không đọc được từ lượt chạy vì fixture lỗi nên không ghi `trace.json`; việc tts đã SUCCEEDED cho thấy thư mục có mặt khi tts chạy. Open item OI-CP7-STAGING-VOICE: gói sở hữu `src/controlplane/api/wiring/voice.py` hoặc launcher nên tạo thư mục này; CP7-10 không sửa src.
- seed_import: sources_existing=7, hooks_existing=10, assets_existing=22, article_image_rights_status=UNVERIFIED (seed có sẵn, không nhập mới).
- ready_seconds, ai_calls, spent_usd, drive_bytes, elapsed_s: không đo được từ fixture vì fixture không trả kết quả (không có dòng budget).
- unit: 12 test_unit_* thuần đạt (12 passed, 0 failed), gồm test_unit_ensure_voice_staging, test_unit_no_batch_retry_loop và test_unit_format_failed_stage.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job FAILED_FINAL; không hạ ngưỡng, không nâng trần 25 lời gọi AI hay 3 USD, không SQL ghi, không sửa src, không dựng dữ liệu giả;
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ là số đo, driver không UPDATE DB;
3. ba bản sửa production đã gộp (D-15-FIX1, PW-G2-FIX1, PW-G4-FIX1) có hiệu lực trên mã này; PW-G4-FIX1 làm job lỗi tới FAILED_FINAL thay vì treo, nên blocker được báo ngay;
4. OI-CP7-STAGING-VOICE: việc tạo `staging/voice` là chuẩn bị môi trường của driver, không phải sửa production; cần gói sở hữu wiring/launcher xử lý chính thức;
5. RG-09 chạy đúng một lô 1 video; lỗi render `ACTIVITY_ABORTED` ở resolve_render_package thuộc production (ngoài owned paths), cần Control chẩn đoán và giao gói sửa; ngăn xếp thật không được chạy lần hai trong lượt này;
6. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Không đo được từ fixture (không có dòng budget); lượt chạy 484,8 giây; không đọc Credentials/; không có bí mật.
