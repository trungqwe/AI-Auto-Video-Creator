# Báo cáo bằng chứng D-16

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: c25a524c0a8e455495d7214d61bfa09cfaa47f5f
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-16 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider (chạy với khung stub: handle_activity và validate_activity_request ném NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 46 failed, 6 passed in 0.92s
- Test FAILED tiêu biểu (ba dòng thật kèm thông điệp, mỗi dòng một gạch đầu dòng con):
  - test_snapshot_activity_returns_a_succeeded_activity_result: NotImplementedError: D-16 RED skeleton
  - test_supported_activity_names_are_the_eight_d14_commands: AssertionError: assert () == ('BuildProductionSnapshot', ...)
  - test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error: NotImplementedError: D-16 RED skeleton
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; mọi test thất bại đều do khung NotImplementedError hoặc ACTIVITY_NAMES rỗng; các test ast về import đã PASS vì khung chỉ import thư viện chuẩn và controlplane.domain.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider (sau khi cài đặt handler)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 52 passed in 0.15s

## Thay đổi

- src/creative/worker/activity_handler.py: handler activity của D cho G gồm handle_activity, validate_activity_request, CreativeActivityDeps, GrantCurrencyPort, ActivityInputPort, InMemoryActivityResultStore; tám activity_name là tám command D-14 (BuildProductionSnapshot, AnalyzeContent, GenerateStoryAngles, GenerateScript, SelectCreativeAssets, BuildProductionPlan, ValidateVariant, GenerateOutputMetadata), mỗi lần gọi chạy đúng một phương thức CreativePipeline; kiểm grant hiện hành trước mọi tra cứu, đóng gói ProblemDetail đã redact.
- tests/integration/creative/test_d16_worker_activity.py: bộ test tích hợp với CreativePipeline thật, FakeProviderRoute, FakeAIAdapter, InMemoryUnitOfWork, chặn socket, cộng test ast cô lập handler khỏi temporalio, controlplane.ui, controlplane.api, voice, render, creative.adapters.
- docs/delivery-evidence/d-16/report.md: báo cáo này.

## Ánh xạ phản ví dụ sang test

- Generation cũ ghi script mới: test_stale_grant_cannot_write_a_new_script_after_a_current_one_committed, test_stale_grant_is_rejected_before_any_input_lookup_or_commit.
- ActivityResult chứa secret: test_provider_failure_is_a_failed_result_with_a_code_only_problem, test_unexpected_exceptions_become_redacted_failed_results.
- Handler đăng ký workflow Temporal trực tiếp: test_handler_imports_no_temporalio_ui_api_voice_or_render_code, test_handler_registers_no_workflow_or_activity_through_decorators.
- Handler tự chờ capability: test_desktop_capability_is_never_waited_for_by_d, test_handler_never_waits_sleeps_or_opens_io.


## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 0 | 52 passed in 0.15s |
| 2 | git diff --check | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. Mỗi activity_name là tên một command D-14; handler gọi đúng một phương thức CreativePipeline với idempotency_key bằng operation_key của ActivityRequest, không chuyển sang stage kế.
2. GrantCurrencyPort là cổng cục bộ trong handler; ActivityInputPort do G và composition root cung cấp (CONV-D-02, CONV-D-05), trả tham số của command gồm context (EventContext) và không gồm idempotency_key.
3. EventContext phải cùng workspace_id với grant và có recovery_epoch bằng str(grant.recovery_epoch); lệch thì kết quả failed với code GRANT_CONTEXT_MISMATCH trước khi chạy command.
4. output_refs lấy từ receipt D-14 (ref_type theo activity, ref_id là aggregate_ref, revision_id là aggregate_revision dạng chuỗi) nên replay từ receipt không cần output; operation_receipt_ref là receipt:operation_key.
5. InMemoryActivityResultStore chỉ dùng cho fixture, chỉ lưu kết quả succeeded theo (workspace_id, operation_key); lưu bền chờ CONV-D-01 và CONV-D-05. Khi store mất, receipt D-14 chặn ghi lần hai (metrics.replayed là true).
6. Problem dùng ProblemDetail với detail cố định và code chỉ nhận token an toàn, không bao giờ lấy text exception: IdempotencyConflict thành IDEMPOTENCY_CONFLICT; RevisionConflictError và DuplicateRecordError thành COMMAND_CONFLICT; ai_invocation_failed thành dependency không retry (retry và fallback thuộc D-15, J và retry_policy_ref của G); lỗi có code an toàn thành COMMAND_REJECTED; ValueError không code thành INVALID_COMMAND_INPUT; lỗi khác thành ACTIVITY_ABORTED có retry.
7. warnings chỉ có từ ValidateVariant không hợp lệ (dạng variant_invalid cộng reason_code); các command khác trả danh sách rỗng.
8. Activity lạ trả failed kèm problem UNKNOWN_ACTIVITY; request hoặc grant sai cấu trúc ném ActivityRequestError.

## Lệch binding và mục mở (ghi cho CONV-D-05)

- ExecutionGrant của controlplane không có grant_id nên grant_id của ActivityResult là ExecutionGrant.operation_id.
- recovery_epoch của grant là int còn binding là string nên dùng str(recovery_epoch).
- Trường tùy chọn execution_grant trong ActivityRequest không dùng; grant được truyền riêng.
- capability_requirements (ví dụ desktop) do G kiểm WAITING_CAPABILITY trước CT-AI-004 và CT-AI-007; D không đọc giá trị và không chờ.
- SelectCreativeAssets chưa có repository (D-13, CONV-D-01) nên ref selection:fingerprint chưa đọc lại được; BuildProductionPlan cần G hoặc composition root cấp CreativeAssetSelection qua ActivityInputPort.
- Handler chỉ kiểm grant hiện hành trước command; fencing nguyên tử tại thời điểm commit cần G cung cấp (CONV-D-05).
- Ref_type đầu ra của D: production_snapshot, content_analysis, story_angle_set, script_version, creative_asset_selection, production_plan, variant_validation, output_metadata.

## coveredIds

- CT-WF-003, CT-WF-006 (phía D).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9): chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite; không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane hay mã D-14.
- Chỉ dùng thư viện chuẩn, controlplane.domain và creative.application, creative.domain, creative.ports; không gọi dịch vụ thật, không mạng.
