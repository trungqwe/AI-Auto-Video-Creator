# Báo cáo bằng chứng G-10

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline HEAD: 5c8e6691fb622d08054ca24cca359cf4f5f302b5
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-10.

## RED

- Lệnh thực thi: python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 60 failed, 2 passed in 0.56s
- Chi tiết các dòng FAILED tiêu biểu:
  - FAILED tests/integration/orchestration/test_g_commit_completion.py::test_execute_completes_everything_in_one_committed_unit_of_work
  - FAILED tests/integration/orchestration/test_g_commit_completion.py::test_ledger_is_a_valid_binding_entry_with_non_request_fields_from_context
  - FAILED tests/integration/orchestration/test_g_commit_completion.py::test_write_order_puts_outbox_after_usage_and_every_state_write
  - FAILED tests/integration/orchestration/test_g_commit_completion.py::test_repeat_same_input_five_times_counts_once
  - FAILED tests/integration/orchestration/test_g_commit_completion.py::test_failure_at_any_step_rolls_back_everything[before:insert_ledger]
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test hợp lệ (test_store_port_has_no_delete_or_media_usage_operation và test_module_has_no_io_clock_or_delete_names) đã PASS ngay ở RED do tính thuần của cấu trúc port và module. Tất cả 60 test thất bại đều là AssertionError, KeyError hoặc DID NOT RAISE do khung execute ban đầu chỉ trả CompletionResult('COMPLETED', {}) mà chưa thực hiện quy trình ghi unit of work nào.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 62 passed in 0.10s

## Thay đổi

- 3 tệp thuộc owned paths:
  - src/controlplane/application/orchestration/commit_completion.py: Triển khai lớp CommitVideoCompletion.execute(request, context) chạy trong một unit of work theo CT-ORC-008: cổng G-09 (check_completion), tạo ledger duy nhất qua _build_ledger với 19 trường, transition_job READY_FOR_COMPLETION -> COMPLETED, convert capacity reservation và VariantReservation sang CONVERTED, tăng revision registry, tăng bộ đếm batch đúng một lần, gọi MediaUsagePort.record(manifest) (G không ghi bảng C), ghi outbox VideoCompleted (từ build_g_event của G-13) trong cùng unit of work chỉ sau các bước trên, và tạo cleanup eligibility dạng bản ghi, không phát bất kỳ lệnh xóa nào. Lỗi ở bất kỳ bước nào rollback toàn bộ. Lặp cùng input trả ALREADY_COMPLETED với ledger cũ và rollback không ghi gì. Định nghĩa JobRecord, CompletionContext, CompletionResult, CompletionRejectedError, CompletionStorePort, MediaUsagePort, CompletionUnitOfWork.
  - tests/integration/orchestration/test_g_commit_completion.py: Bộ kiểm thử tích hợp toàn diện gồm 62 test cases với fake IUnitOfWork có snapshot/rollback (FakeUow, FakeStore, FakeMediaUsage, Recorder, World): kiểm tra đường thành công A (hoàn tất trong một UoW, ledger binding hợp lệ, thứ tự ghi outbox sau usage và mọi write state, outbox VideoCompleted từ G-13 builder, cleanup eligibility bản ghi); nhóm B (lặp 5 lần cùng input count=1 và idempotency, CONFLICT cho 8 trường so sánh khác input); nhóm C (lỗi tiêm ở 19 điểm trước/sau từng thao tác ghi và trước commit đều rollback toàn bộ trạng thái trước=sau, outbox không bao giờ được thử khi bước trước lỗi, retry sau rollback hoàn tất đúng 1 lần); nhóm D1 (stale registry 3 giá trị không ghi gì và KEEP_WAITING, 8 ca từ chối của cổng không thay đổi trạng thái và không ghi gì); nhóm D2 (kiểm tra TypeError khi context sai kiểu, CompletionStorePort không có thao tác xóa hoặc media usage, module không có import I/O/clock hoặc tên lệnh xóa).
  - docs/delivery-evidence/g-10/report.md: Báo cáo bằng chứng nghiệm thu ghi lại chi tiết môi trường, RED, GREEN, thay đổi, lệnh kiểm, quyết định D8, ánh xạ phản ví dụ, coveredIds, pendingUserCheckpoint và giới hạn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider | 0 | 62 passed in 0.10s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. G-10 tự định nghĩa CompletionStorePort, MediaUsagePort, CompletionUnitOfWork, CompletionContext, JobRecord vì chưa có nguồn thật, nối thật ở gói hội tụ YC-HT-G-01/YC-HT-G-02.
2. Trường ledger ngoài request (completion_id, batch_ref, session_ref, cloud_location_ref, preset_revision_ref, output_naming_metadata, cost_usage_summary, audit_actor, cleanup_policy_ref, completed_at) và FencingDecision lấy từ CompletionContext theo D8-G-14.
3. Từ chối của cổng (kể cả CONFLICT, VARIANT_REGISTRY_STALE→KEEP_WAITING, VARIANT_CONFLICT_FINAL→FAIL_JOB_RELEASE) ném CompletionRejectedError không ghi gì, việc fail job và release thuộc luồng khác, G-10 không thực hiện.
4. Lặp cùng input trả CompletionResult('ALREADY_COMPLETED', ledger cũ) và rollback không ghi.
5. expected_revision của transition_job lấy từ revision đọc trong cùng unit of work.
6. Revision registry mới = revision hiện tại + 1.
7. Payload VideoCompleted gồm completion_id, video_job_id, variant_registry_revision, aggregate_revision là revision job sau chuyển.
8. Thứ tự outbox rồi cleanup eligibility theo CT-ORC-008 bước 7–8; cổng ghi không có thao tác xóa.

## Ánh xạ phản ví dụ

- Ledger commit nhưng MediaUsage mất: Loại trừ bởi test_failure_at_any_step_rolls_back_everything (lỗi tại record_usage hoặc trước commit đều rollback toàn bộ trạng thái) và test_write_order_puts_outbox_after_usage_and_every_state_write.
- Completion lặp tăng count hai lần: Loại trừ bởi test_repeat_same_input_five_times_counts_once (gọi 5 lần cùng input count batch chỉ tăng đúng 1 lần, chỉ 1 ledger, 1 outbox, 1 usage, 1 cleanup record).
- VideoCompleted phát khi unit of work rollback: Loại trừ bởi test_outbox_is_never_attempted_when_an_earlier_step_fails (outbox không bao giờ được gọi khi bước trước lỗi) và test_failure_at_any_step_rolls_back_everything.
- Completion phát lệnh xóa local trực tiếp: Loại trừ bởi test_cleanup_eligibility_is_a_record_and_no_delete_command_is_issued, test_store_port_has_no_delete_or_media_usage_operation và test_module_has_no_io_clock_or_delete_names.

## coveredIds

- CT-ORC-008
- INV-010
- INV-017
- TST-WF-INV-010 (mức logic)
- TST-WF-INV-017 (mức logic)

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật D5
- YC-HT-G-01 migration cột ledger
- YC-HT-G-02 wiring composition root và MediaUsageRecorder của C

## Giới hạn

- Không chạy full suite, không PostgreSQL thật, TST-WF-INV-017 chỉ mức logic với fake.
- Chỉ dùng thư viện chuẩn Python (stdlib) và các gói nội bộ controlplane.
- Không phát lệnh xóa file thật; cleanup eligibility chỉ lưu bản ghi theo chính sách.
