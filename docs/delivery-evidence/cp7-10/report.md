# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc 05bdb01 (vòng 3: thêm `ensure_seed_media`).

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (lượt ngăn xếp thật của vòng 3, đúng một lần): 9 passed, 11 errors tại fixture batch_run, exit 1, 192,85 giây (pytest) / 3 phút 13 giây (tường). Kiểm tĩnh trước đó: git diff --check exit 0; `-k test_unit` 9 passed.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Thông điệp BLOCKED nguyên văn: `BLOCKED: job kết thúc ở FAILED_FINAL sau 1 lần tạo lô`. Bước `ensure_seed_media` chạy xong không ném lỗi (không có thông điệp `BLOCKED: nhập media seed thất bại`), rồi driver tạo lô 1; job kết thúc FAILED_FINAL nhưng `db.failed_stage` không trả stage lỗi (chuỗi detail rỗng) nên không có stage/code để ghi; không có plan, render, QC, Drive, completion.

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

- blocker: số lần tạo lô = 1 (tối đa 3); job FAILED_FINAL, `failed_stage` rỗng nên `should_retry_batch` không có mã để thử lại.
- seed_import: `ensure_seed_media` hoàn tất không lỗi; vì fixture thất bại nên trace.json không được ghi, không có số assets_new, hooks_imported, sources_existing để chép (không suy đoán).
- ready_seconds, ai_calls, spent_usd, drive_bytes, elapsed_s: không đo được vì fixture không trả kết quả (không có dòng budget).
- unit: chín test_unit_* thuần đạt (9 passed, 0 failed), gồm test_unit_seed_import_uses_product_tools và test_unit_should_retry_batch.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job vẫn FAILED_FINAL; driver không hạ ngưỡng, không dựng dữ liệu giả, không INSERT/UPDATE/DELETE DB bằng SQL, không sửa src; driver chỉ nhập media seed bằng công cụ sản phẩm ADAPT-SEED (`make_seed_media.generate_seed_media` rồi `import_seed.import_seed`, qua dịch vụ ứng dụng của A và C);
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ được ghi như số đo, driver không UPDATE DB;
3. no_fake_adapters được thiết kế kiểm bằng duyệt đồ thị đối tượng của composition do launcher.load_app dựng trong tiến trình test; chưa ghi PASS vì fixture dừng ở BLOCKED trước khi test chạy;
4. Nguyên nhân FAILED_FINAL lần này chưa xác định: `failed_stage` rỗng và `problem` của stage chỉ lưu mã; cần Orchestrator xem dữ liệu job/stage của lô vừa chạy (hoặc mở rộng đo lỗi trong owned paths) rồi giao bước tiếp, không chạy lại ngăn xếp thật trong lượt này;
5. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Chi phí: không đo được từ fixture (không có dòng budget); lượt chạy 192,85 giây; không đọc Credentials/; không có bí mật.
