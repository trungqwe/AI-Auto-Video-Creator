# Báo cáo bằng chứng D-15

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: bcda8664b9621875d25ba2359b95d3d0360a36b2
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-15 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider (chạy với khung stub, các hành vi ném NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 24 failed, 3 passed in 0.62s
- Test FAILED tiêu biểu:
  - FAILED tests/integration/creative/test_d15_provider_failure.py::test_failure_kinds_become_redacted_problems_with_recorded_attempt[timeout_record]: NotImplementedError: D-15 RED skeleton
  - FAILED tests/integration/creative/test_d15_provider_failure.py::test_fallback_follows_decision_order_intersected_with_allowed_fallbacks: NotImplementedError: D-15 RED skeleton
  - FAILED tests/integration/creative/test_d15_provider_failure.py::test_attempt_budget_comes_from_policy_and_never_loops[1-1]: NotImplementedError: D-15 RED skeleton
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; các test tĩnh (docstring, chặn mạng, ranh giới nguồn) đã PASS, mọi test gọi hành vi thất bại do khung NotImplementedError.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider (sau khi cài đặt hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 27 passed in 0.12s

## Thay đổi

- src/creative/application/provider_failure.py: cài đặt ProviderFailureHandler.run, ProviderFailurePolicy, ProviderProblem, ProviderCallOutcome, plan_fallback_path, classify_provider_error; mỗi lần thử ghi một AIInvocationRecord (attempt, fallback_path, validation_result) qua UoW và chỉ append; output và lịch sử cũ không bị xoá hay sửa; kết quả WAITING cho G; fallback chỉ theo thứ tự fallback_order của ProviderRouteDecision giao với allowed_fallbacks; fallback đổi intent ngoài policy thì chờ hoặc tạo output revision mới; problem và record được redact.
- tests/integration/creative/test_d15_provider_failure.py: test tích hợp in-process với FakeProviderRoute/ScriptedAI/SpyValidator/InMemoryUnitOfWork, chặn socket.create_connection và socket.getaddrinfo.
- docs/delivery-evidence/d-15/report.md: báo cáo này.

## Ánh xạ phản ví dụ -> test

- Fallback sang provider ngoài danh sách: test_fallback_follows_decision_order_intersected_with_allowed_fallbacks, test_no_fallback_when_allowed_fallbacks_is_empty_or_missing_from_decision.
- Lỗi xoá script cũ (output và lịch sử cũ): test_failures_never_delete_or_edit_old_output_or_history.
- Problem chứa secret chưa redact: test_failure_kinds_become_redacted_problems_with_recorded_attempt, test_known_secret_values_are_redacted_from_problem_and_record.
- Retry vô hạn: test_attempt_budget_comes_from_policy_and_never_loops, test_missing_or_invalid_attempt_policy_is_refused_before_any_route_or_ai_call, test_provider_failure_source_has_no_adapter_clock_network_import_and_no_while_loop.
- Output fallback bỏ qua validator: test_fallback_output_goes_through_the_same_validator_and_records_revisions.
- Fallback đổi intent ngoài policy: test_fallback_changing_intent_waits_without_calling_the_provider, test_fallback_changing_intent_creates_new_output_revision_when_policy_allows.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider | 0 | 27 passed in 0.12s |
| 2 | git diff --check | 0 | PASS |

## Quyết định mặc định (D8)

1. Mỗi provider trong path được thử tối đa một lần mỗi lần run, ngân sách max_attempts là tổng số lần gọi và bắt buộc từ policy (thiếu thì INPUT_NOT_READY missing_attempt_policy trước khi gọi route hoặc AI).
2. Retry hay chờ provider là quyết định của G (kết quả WAITING, G gọi lại cùng idempotency_key thì attempt và revision record tiếp nối).
3. GIẢ ĐỊNH: model_ref và account_ref của decision chính áp dụng cho fallback (CONV-D-11, như run_tts_attempts của E).
4. Lỗi provider đến dưới dạng AIInvocationRecord.error hoặc OSError/TimeoutError, phân loại timeout, rate limit, unreachable, provider_error.
5. Fallback ngoài intent_preserving_providers thì chờ (mặc định) hoặc tạo output revision mới (current_output_revision + 1, không ghi đè).
6. Mọi lần thử, kể cả lỗi, được commit trong một UoW và chỉ append; handler không ghi output, việc lưu output vào repository thuộc command gọi handler (CONV-D-02).

## coveredIds

- CT-AI-ROUTE-002, CT-AI-010

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt
- Mục mở: CONV-D-02 (nối handler vào CreativePipeline, hiện pipeline.py vẫn dùng allowed_fallbacks rỗng) và CONV-D-11 (adapter route J).

## Giới hạn

- Không chạy full suite, không đổi pipeline.py, domain, ports, adapters, pyproject, binding.
- Chỉ stdlib và gói creative, controlplane; không mạng.
