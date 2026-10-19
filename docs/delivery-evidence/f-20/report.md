# Báo cáo bằng chứng F-20

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: f563c0ddafa79257ae4afa5171f54e7fc11cbb5a
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-20 trong docs/implementation/f/slices.md.

## RED

- Lệnh: python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider (handler còn stub NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 45 failed, 8 passed in 1.68s
- Test FAILED tiêu biểu:
  - tests/integration/render/test_f20_worker_activity.py::test_resolve_activity_returns_a_succeeded_result_with_the_package_ref: NotImplementedError: F-20 RED stub
  - tests/integration/render/test_f20_worker_activity.py::test_validate_activity_succeeds_on_a_passing_report: NotImplementedError: F-20 RED stub
  - tests/integration/render/test_f20_worker_activity.py::test_render_activity_runs_only_the_render_and_never_the_inspection: NotImplementedError: F-20 RED stub
  - tests/integration/render/test_f20_worker_activity.py::test_stale_grant_is_rejected_before_any_input_lookup_or_commit[old_generation]: NotImplementedError: F-20 RED stub
  - tests/integration/render/test_f20_worker_activity.py::test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error: NotImplementedError: F-20 RED stub
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; mọi test đỏ do NotImplementedError của stub.

## GREEN

- Lệnh: python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 53 passed in 0.27s

## Thay đổi

- src/render/worker/activity_handler.py: handle_activity, validate_activity_request, RenderActivityDeps, ActivityInputPort, InMemoryActivityResultStore; bốn route resolve_render_package, validate_render_package, render_video, inspect_output tới command F-17, F-18, F-19.
- tests/integration/render/test_f20_worker_activity.py: 53 test tích hợp và kiểm AST.
- docs/delivery-evidence/f-20/report.md: báo cáo này.

## Ánh xạ phản ví dụ sang test

- Generation cũ ghi attempt mới: test_stale_grant_cannot_write_a_new_attempt_after_a_current_one_committed và test_stale_grant_is_rejected_before_any_input_lookup_or_commit.
- ActivityResult chứa secret: test_a_renderer_crash_is_a_failed_result_without_output_and_without_the_secret, test_unexpected_exceptions_become_redacted_failed_results, test_handler_never_reads_the_secret_values_of_a_command.
- Handler đăng ký workflow Temporal: test_handler_imports_no_temporalio_ui_api_creative_voice_or_catalog_code và test_handler_registers_no_workflow_or_activity_through_decorators.
- Render xong tự chạy inspect: test_render_activity_runs_only_the_render_and_never_the_inspection và test_a_finished_stage_never_starts_the_next_stage.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider | 0 | 53 passed in 0.27s |
| 2 | git diff --check | 0 | pass, không có lỗi định dạng hay khoảng trắng thừa |

## Quyết định mặc định (D8)

1. activity_name dùng đúng bốn tên snake_case của acceptance: resolve_render_package, validate_render_package, render_video, inspect_output; tên khác (kể cả tên command PascalCase, PrepareOutputReady, ReconcileRender) trả failed kèm problem UNKNOWN_ACTIVITY.
2. GrantCurrencyPort lấy từ render.application.package_pipeline; ActivityInputPort do G hoặc composition root cung cấp để đổi input_refs thành command F.
3. Command phải mang đúng ExecutionGrant của request và đúng operation_key của request; với render_video khoá idempotency là render_attempt_id nên render_attempt_id phải bằng operation_key.
4. Chỉ kết quả succeeded được lưu theo (workspace_id, operation_key); lặp key trả kết quả cũ đóng dấu lại danh tính grant hiện hành; kết quả khác succeeded chạy lại command và dựa vào idempotency của F-17/F-18/F-19.
5. Báo cáo validation hoặc QC không đạt là kết quả đã lưu: activity trả failed, problem package_validation_failed hoặc quality_gates_failed, output_refs vẫn trỏ report đã lưu.
6. Hết slot GPU trả failed, retryable, category capacity, code gpu_lease_unavailable; F không chờ.
7. Attempt FAILED trả failed (retryable); OUTCOME_UNKNOWN hoặc trạng thái chưa kết thúc trả outcome_unknown; output_refs chỉ có render_output khi attempt SUCCEEDED.
8. Problem dùng ProblemDetail với detail cố định và code là token an toàn; không bao giờ lấy text exception hay trường lỗi của attempt.

## Lệch binding (ghi cho CONV-F-05)

- ExecutionGrant của controlplane không có grant_id nên grant_id của ActivityResult là ExecutionGrant.operation_id.
- recovery_epoch của grant là int còn binding là string nên dùng str(recovery_epoch).
- Trường tùy chọn execution_grant của ActivityRequest không dùng; grant truyền riêng.
- capability_requirements (desktop, GPU) do G kiểm và quyết WAITING_CAPABILITY; F không đọc và không chờ.
- Ref_type đầu ra của F: render_package, package_validation_report, render_attempt, render_output, quality_report.
- Open item: attempt STARTED mồ côi sau crash được báo outcome_unknown nhưng ReconcileRender của F-18 chỉ nhận OUTCOME_UNKNOWN; PrepareOutputReady và ReconcileRender chưa là activity của F-20 (ngoài acceptance); G quyết ở CONV-F-05.

## coveredIds

- CT-WF-003, CT-WF-006, TST-E2E-014 (phía F).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9): chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite; không đổi pyproject.toml, lockfile, binding, fixture hay mã controlplane và render.application.
- Chỉ stdlib cùng controlplane.domain và render.application, render.domain.
- Không gọi dịch vụ thật, không đọc bí mật.
