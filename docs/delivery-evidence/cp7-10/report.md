# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc 6128ef1 (vòng 4: thêm chẩn đoán FAILED_FINAL).

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (lượt ngăn xếp thật của vòng 4, đúng một lần): 10 passed, 11 errors tại fixture batch_run, exit 1, 85,31 giây (pytest) / 86,2 giây (tường). Kiểm tĩnh trước đó: git diff --check exit 0; `-k test_unit` 10 passed, 11 deselected, exit 0.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Fixture batch_run lỗi vì job của lô 1 kết thúc FAILED_FINAL; chẩn đoán mới đã ghi lại hàng stage thực của job.

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

- blocker: `BLOCKED: job kết thúc ở FAILED_FINAL sau 1 lần tạo lô; job=FAILED_FINAL job_wait=None stages=[analyze#1=SUCCEEDED] seed=[sources_registered=0 sources_replayed=0 sources_existing=7 hooks_imported=0 hooks_existing=10 assets_new=0 assets_existing=22 article_image_rights_status=UNVERIFIED] serve_log_tail=[Task was destroyed but it is pending! | task: <Task pending name='Task-535' coro=<to_thread() running at C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\Lib\asyncio\threads.py:26> wait_for=<Future pending cb=[_chain_future.<locals>._call_check_cancel() at C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\Lib\asyncio\futures.py:384, Task.task_wakeup()]>> | Task was destroyed but it is pending! | task: <Task pending name='Task-643' coro=<to_thread() running at C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\Lib\asyncio\t]` (đã che bí mật; chuỗi bị cắt ở giới hạn 600 ký tự của đuôi log).
- nguyen_nhan: chẩn đoán cho thấy chỉ có một hàng stage là analyze#1=SUCCEEDED; không có hàng stage nào FAILED_FINAL hay OUTCOME_UNKNOWN, `job_wait=None`, và không có mã lỗi hay thông điệp stage. Nghĩa là job chuyển FAILED_FINAL ngay sau stage analyze mà không tạo hàng stage tiếp theo (không có stage/mã lỗi nào để nêu). Lý do job chuyển FAILED_FINAL chưa xác định: đoạn trống là hàng stage lỗi và mã lỗi; đuôi serve.log chỉ chứa cảnh báo asyncio "Task was destroyed but it is pending" (xuất hiện khi tiến trình dừng), không chứa lỗi của job.
- seed_import: sources_registered=0, sources_replayed=0, sources_existing=7, hooks_imported=0, hooks_existing=10, assets_new=0, assets_existing=22, article_image_rights_status=UNVERIFIED (seed đã có sẵn từ trước, không nhập mới).
- ready_seconds, ai_calls, spent_usd, drive_bytes, elapsed_s: không đo được vì fixture không trả kết quả (không có dòng budget).
- unit: mười test_unit_* thuần đạt (10 passed, 0 failed), gồm test_unit_format_diagnostic.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job vẫn FAILED_FINAL; driver không hạ ngưỡng, không dựng dữ liệu giả, không INSERT/UPDATE/DELETE DB bằng SQL, không sửa src; driver chỉ nhập media seed bằng công cụ sản phẩm ADAPT-SEED (`make_seed_media.generate_seed_media` rồi `import_seed.import_seed`, qua dịch vụ ứng dụng của A và C);
2. OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ được ghi như số đo, driver không UPDATE DB;
3. no_fake_adapters được thiết kế kiểm bằng duyệt đồ thị đối tượng của composition do launcher.load_app dựng trong tiến trình test; chưa ghi PASS vì fixture dừng ở BLOCKED trước khi test chạy;
4. Lý do job FAILED_FINAL ngay sau analyze vẫn chưa xác định: không có hàng stage lỗi và đuôi serve.log (6 dòng cuối, cắt 600 ký tự) chỉ là cảnh báo asyncio khi dừng; cần Orchestrator đọc log đầy đủ của ứng dụng hoặc giao đo thêm trong owned paths, không chạy lại ngăn xếp thật trong lượt này;
5. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Chi phí: không đo được từ fixture (không có dòng budget); lượt chạy 85,31 giây; không đọc Credentials/; không có bí mật.
