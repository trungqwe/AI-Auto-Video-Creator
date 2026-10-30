# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc b510f96.

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (2 lượt ngăn xếp thật, cả hai: 7 passed, 11 errors tại fixture batch_run).

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Driver tạo lô 1 video qua Control API (phiên từ /launch, TLS kiểm chứng bằng cert của launcher), job được cấp và stage `analyze` SUCCEEDED, nhưng stage `script` kết thúc FAILED_FINAL với mã `ai_output_schema_violation` (đầu ra AI cho kịch bản vi phạm schema, nguồn lỗi nằm ở mã sản phẩm src/creative hoặc prompt/adapter AI, ngoài owned paths của CP7-10). Job chuyển FAILED_FINAL nên chưa có plan, render, QC, Drive, completion; không mục nào trong mười mục có bằng chứng để ghi PASS.

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

- blocker: job FAILED_FINAL ở stage=script code=ai_output_schema_violation (type urn:creative:problem:command_rejected, retryable=False), lặp lại ở cả hai lượt chạy ngăn xếp thật; stage analyze SUCCEEDED attempt 1.
- blocker: lượt 1 chạy khoảng 105 giây, lượt 2 khoảng 88 giây; launcher luôn được dừng ở cuối (finally stop_until_exited).
- unit: bảy test_unit_* thuần đạt (7 passed, 0 failed) khi chạy bằng `-k test_unit`.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì stage script thất bại do mã sản phẩm ngoài owned paths; driver không hạ ngưỡng, không dựng dữ liệu giả, không UPDATE DB, không sửa src;
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ được ghi như số đo (lô vẫn CREATED ở cả hai lượt), driver không UPDATE DB;
3. no_fake_adapters được thiết kế kiểm bằng duyệt đồ thị đối tượng của composition do launcher.load_app dựng trong tiến trình test; bước này dựng được ở cả hai lượt nhưng kết quả chưa được ghi thành PASS vì fixture dừng ở BLOCKED trước khi test chạy;
4. Hai lượt chạy ngăn xếp thật đã dùng hết ngân sách lượt Worker (tối đa 2); số lời gọi AI và chi phí chưa được đo vì không có dòng budget (fixture không trả kết quả);
5. Kết quả bảy test_unit_*: 7 passed;
6. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo;
7. Cần gói sở hữu mã tạo script (src/creative, prompt hoặc adapter AI) sửa lỗi `ai_output_schema_violation`, sau đó chạy lại bằng đúng lệnh pytest bắt buộc để lấy số đo PASS.

## Chi phí

Chi phí: không đo được từ fixture (không có dòng budget); thời gian mỗi lượt dưới 2 phút; không đọc Credentials/; không có bí mật.
