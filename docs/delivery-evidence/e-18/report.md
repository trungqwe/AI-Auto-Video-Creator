# Báo cáo bằng chứng E-18

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 7622e01f50b6257f93a5c0b90f84880b5c9bf952
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-18 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider (chạy với khung stub ở bước 1 và 4-12)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 38 failed, 6 passed in 0.77s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp:
  - FAILED tests/integration/voice/test_e18_worker_activity.py::test_create_voice_track_activity_returns_a_succeeded_activity_result: NotImplementedError trong handle_activity
  - FAILED tests/integration/voice/test_e18_worker_activity.py::test_stale_grant_is_rejected_before_any_input_lookup_or_commit[old_generation]: NotImplementedError trong handle_activity
  - FAILED tests/integration/voice/test_e18_worker_activity.py::test_supported_activity_names_are_the_e16_and_e17_commands: AttributeError (chưa có ACTIVITY_NAMES)
  - FAILED tests/integration/voice/test_e18_worker_activity.py::test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error: NotImplementedError trong validate_activity_request
  - FAILED tests/integration/voice/test_e18_worker_activity.py::test_invalid_request_raises_before_any_grant_check_lookup_or_write[missing_operation_key]: NotImplementedError trong handle_activity
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 6 test AST cô lập mã nguồn và không import thư viện cấm đã PASS. Tất cả 38 test thất bại đều do method stub ném NotImplementedError hoặc thiếu thuộc tính stub.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider (chạy sau khi cài đặt logic hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 44 passed in 0.17s

## Thay đổi

- Ba tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/worker/activity_handler.py: Cài đặt handler activity của E cho workflow G gồm handle_activity, validate_activity_request, VoiceActivityDeps, GrantCurrencyPort, ActivityInputPort, InMemoryActivityResultStore, các route E-16/E-17, kiểm tra grant hiện hành và đóng gói ProblemDetail đã redact.
  - tests/integration/voice/test_e18_worker_activity.py: Bộ kiểm thử tích hợp 44 test cases bao quát hợp đồng g-activity-execution, xử lý grant cũ (stale), chống lặp với cùng operation_key, redact secret và exception text, từ chối activity lạ, chạy đúng một activity không tự chuyển stage, và các kiểm tra AST cô lập hoàn toàn khỏi temporalio, UI, API, creative, render, catalog.
  - docs/delivery-evidence/e-18/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ sang test:
  - Generation cũ ghi voice mới -> test_stale_grant_cannot_write_a_new_voice_after_a_current_one_committed và test_stale_grant_is_rejected_before_any_input_lookup_or_commit
  - ActivityResult chứa secret -> test_provider_failure_is_a_failed_result_with_a_code_only_problem, test_unexpected_exceptions_become_redacted_failed_results, test_media_receipt_errors_become_code_tokens
  - Handler đăng ký workflow Temporal -> test_handler_imports_no_temporalio_ui_api_creative_render_or_catalog_code và test_handler_registers_no_workflow_or_activity_through_decorators
  - Chạy tiếp stage sau -> test_a_finished_stage_never_starts_the_next_stage và test_media_activity_runs_only_its_own_command

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider | 0 | 44 passed in 0.17s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace) |
| 3 | python -c probe_marker | 0 | PASS (sạch marker stub và NotImplementedError) |

## Quyết định mặc định (D8)

1. Cổng GrantCurrencyPort cục bộ trong handler (không import source_ingestion của A; G cung cấp adapter ở CONV-E-05);
2. ActivityInputPort do G/composition root cung cấp để đổi input_refs thành tham số command (E-18 không đoán ref_type);
3. InMemoryActivityResultStore chỉ dùng cho fixture, lưu bền chờ CONV-E-01/CONV-E-05, chỉ lưu kết quả succeeded;
4. Kết quả lưu được đóng dấu lại danh tính grant hiện hành khi lặp operation_key;
5. Problem dùng controlplane ProblemDetail với detail cố định, code chỉ nhận token an toàn, không bao giờ lấy text exception;
6. Activity lạ trả failed + problem UNKNOWN_ACTIVITY (không raise); request/grant sai cấu trúc raise ActivityRequestError.

## Lệch binding (ghi cho CONV-E-05)

- ExecutionGrant của controlplane không có grant_id nên grant_id = ExecutionGrant.operation_id;
- Recovery_epoch của grant là int còn binding là string nên dùng str(recovery_epoch);
- Trường tùy chọn execution_grant trong ActivityRequest không dùng (grant truyền riêng);
- Capability_requirements (ví dụ desktop) do G kiểm WAITING_CAPABILITY, E không đọc và không chờ;
- Ref_type đầu ra của E: voice_artifact, word_timing_artifact, timing_validation_report, media_artifact.

## coveredIds

- CT-WF-003, CT-WF-006 (phía E), TST-E2E-014 (đoạn E).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) - chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite; không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane.
- Chỉ stdlib + domain/application của voice và controlplane.domain.
- Không gọi dịch vụ thật.
