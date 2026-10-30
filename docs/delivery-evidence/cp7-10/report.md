# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc f0c621e.

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (lượt ngăn xếp thật của vòng 2, đúng một lần): 8 passed, 11 errors tại fixture batch_run, exit 1, 301,95 giây; driver đã tạo 2 lô 1 video.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Thông điệp BLOCKED nguyên văn: `BLOCKED: job kết thúc ở FAILED_FINAL stage=media_select status=FAILED_FINAL code=INPUT_NOT_READY sau 2 lần tạo lô`. Lô 1 hỏng ở stage script với mã `ai_output_schema_violation` nên driver tự tạo lô 2 theo `should_retry_batch`; ở lô 2 stage script đã qua nhưng stage `media_select` kết thúc FAILED_FINAL với mã `INPUT_NOT_READY` (chưa có đầu vào media sẵn sàng), mã này không thuộc RETRY_CODES nên driver dừng, không có plan, render, QC, Drive, completion.

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

- blocker: số lần tạo lô = 2 (tối đa 3); lô 1 FAILED_FINAL ở stage=script code=ai_output_schema_violation, lô 2 FAILED_FINAL ở stage=media_select code=INPUT_NOT_READY.
- blocker: stage script của lô 2 đã vượt qua, nên lỗi schema AI chập chờn đã được driver xử lý bằng lô mới; lỗi còn lại INPUT_NOT_READY thuộc dữ liệu đầu vào media (ảnh seed, tài sản) do gói chủ phía trước CP7-4..CP7-7 cung cấp, ngoài owned paths.
- unit: tám test_unit_* thuần đạt (8 passed, 0 failed) khi chạy bằng `-k test_unit`, gồm test_unit_should_retry_batch.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job vẫn FAILED_FINAL sau 2 lần tạo lô; driver đã thử lại lô theo `should_retry_batch` với lỗi schema ở lô 1, lỗi sau đó đổi sang stage=media_select code=INPUT_NOT_READY; driver không hạ ngưỡng, không dựng dữ liệu giả, không UPDATE DB, không sửa src;
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ được ghi như số đo, driver không UPDATE DB;
3. no_fake_adapters được thiết kế kiểm bằng duyệt đồ thị đối tượng của composition do launcher.load_app dựng trong tiến trình test; kết quả chưa ghi thành PASS vì fixture dừng ở BLOCKED trước khi test chạy;
4. Số lời gọi AI và chi phí chưa đo vì fixture không trả kết quả nên không có dòng budget;
5. `problem` của stage chỉ lưu mã nên driver không thấy field lỗi cụ thể; cần gói chủ xem dữ liệu đầu vào media (INPUT_NOT_READY ở media_select) rồi chạy lại đúng lệnh pytest bắt buộc;
6. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Chi phí: không đo được từ fixture (không có dòng budget); lượt chạy 301,95 giây; không đọc Credentials/; không có bí mật.
