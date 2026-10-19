# Báo cáo bằng chứng J-18

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `798b970838a55784962f38a0225d9ec3f047cbe0`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-18 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` (chạy khi routed_invocation.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `30 failed, 3 passed in 0.39s`
- Danh sách test PASSED kèm lý do vì stub đã định nghĩa kiểu/hằng/cấu trúc (3 passed):
  - `tests/integration/config/test_j_routed_invocation.py::test_module_docstring_declares_covered_ids` (docstring khai báo coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012)
  - `tests/integration/config/test_j_routed_invocation.py::test_source_does_not_import_router_or_adapter` (không import hay nhắc đến config.router hoặc config.adapter)
  - `tests/integration/config/test_j_routed_invocation.py::test_executor_port_takes_no_secret` (ProviderExecutorPort.execute không nhận tham số secret)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (30 failed):
  - 30 test failed do `NotImplementedError: J-18 invoke`:
    - 6 ca parametrize của `test_missing_revision_raises_value_error`: `NotImplementedError: J-18 invoke`
    - `test_success_record_carries_revisions_and_credential_method_only`: `NotImplementedError: J-18 invoke`
    - `test_hard_stop_over_budget_blocks_before_resolve_and_execute`: `NotImplementedError: J-18 invoke`
    - `test_soft_limit_over_budget_still_runs_with_warning_status`: `NotImplementedError: J-18 invoke`
    - `test_warn_80_only_labels_cost_status_even_with_hard_stop`: `NotImplementedError: J-18 invoke`
    - `test_hard_stop_without_configured_limit_never_blocks`: `NotImplementedError: J-18 invoke`
    - `test_under_budget_status_is_ok`: `NotImplementedError: J-18 invoke`
    - `test_positive_usage_cost_is_appended_to_ledger_even_on_failure`: `NotImplementedError: J-18 invoke`
    - `test_budget_is_rechecked_before_each_switch_attempt`: `NotImplementedError: J-18 invoke`
    - `test_rate_limit_then_switch_succeeds_with_two_attempts_carrying_revisions`: `NotImplementedError: J-18 invoke`
    - `test_switch_model_ref_falls_back_to_candidate_ref_without_lookup`: `NotImplementedError: J-18 invoke`
    - 3 ca parametrize của `test_every_candidate_failing_returns_waiting_provider_without_raising`: `NotImplementedError: J-18 invoke`
    - `test_executor_exception_is_recorded_not_raised`: `NotImplementedError: J-18 invoke`
    - `test_fallback_never_leaves_allowed_list`: `NotImplementedError: J-18 invoke`
    - `test_ai_not_required_skips_on_provider_failure`: `NotImplementedError: J-18 invoke`
    - `test_snapshot_committed_without_permission_requires_new_output_revision`: `NotImplementedError: J-18 invoke`
    - `test_snapshot_committed_with_permission_still_switches`: `NotImplementedError: J-18 invoke`
    - 2 ca parametrize của `test_no_eligible_route_never_raises`: `NotImplementedError: J-18 invoke`
    - 2 ca parametrize của `test_canary_in_executor_result_error_is_redacted_everywhere`: `NotImplementedError: J-18 invoke`
    - `test_canary_in_raised_executor_exception_is_redacted`: `NotImplementedError: J-18 invoke`
    - `test_network_primitives_are_blocked_and_unused`: `NotImplementedError: J-18 invoke`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi routed_invocation.py là stub và fail hợp lệ do NotImplementedError đúng oracle.

## Thay đổi

- `src/controlplane/application/config_security/routed_invocation.py`: Tạo mới dịch vụ điều phối gọi AI có định tuyến (RoutedInvocationService) kết hợp resolve (J-13), kiểm soát ngân sách theo chu kỳ (J-08), gọi executor phi tập trung không nhận secret, phân loại và chuyển hướng lỗi/fallback an toàn (J-14), che giấu secret/canary (J-02); định nghĩa ExecutionResult, AttemptRecord, InvocationRecord, ProviderExecutorPort, CostLedgerPort và các hằng outcome; không import hay phụ thuộc router/adapter cũ.
- `tests/integration/config/test_j_routed_invocation.py`: 33 test tích hợp với fake (FakeCatalog, SpyBook, FakeLedger, ScriptedExecutor) kiểm tra toàn diện cấu trúc port không rò secret, xác thực revision, xuất xứ dữ liệu, chặn/cảnh báo ngân sách, ghi ledger khi có chi phí, kịch bản fallback (chuyển provider sau 429, wait khi cạn, bỏ qua khi AI không bắt buộc, bảo vệ snapshot), che giấu canary trong lỗi, chặn triệt để socket mạng; docstring coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012.
- `docs/delivery-evidence/j-18/report.md`: Báo cáo bằng chứng thực thi J-18.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` | 0 | `33 passed in 0.13s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib, re; t = pathlib.Path('src/controlplane/application/config_security/routed_invocation.py').read_text(encoding='utf-8'); assert not re.search('config[.](router|adapter)', t)"` | 0 | PASS (assert qua) |
| 4 | `python -c "import pathlib; t = pathlib.Path('tests/integration/config/test_j_routed_invocation.py').read_text(encoding='utf-8'); assert 'coveredIds: CT-AI-ROUTE-002, CT-COST-001, TST-INT-INV-004, TST-SEC-INV-012' in t"` | 0 | PASS (assert qua) |

## Quyết định mặc định (D8)

- (1) ProviderRouteDecision không mang candidate_ref của route chính nên attempt đầu dùng decision.provider_ref làm candidate_ref và decision.model_ref làm model_ref (GIẢ ĐỊNH; open item: resolver nên công bố candidate_ref đã chọn, thuộc slice khác).
- (2) model_ref của attempt SWITCH lấy từ tham số tùy chọn keyword-only model_ref_for, mặc định bằng candidate_ref.
- (3) request_payload_ref lấy từ request.snapshot_ref.
- (4) ngân sách được đánh giá trước resolve ở lần đầu (không rò reservation khi BUDGET_BLOCKED) và trước mỗi lần switch; additional_estimated = Decimal('0') vì chưa có ước lượng trước lần gọi nên hard_stop chỉ chặn khi spent > monthly_limit.
- (5) NoRouteError trả WAITING_PROVIDER (ai_required True) hoặc SKIPPED_AI_NOT_REQUIRED (False) với route_decision None, không raise.
- (6) ghi cost_ledger cho mọi attempt có usage_cost > 0 kể cả khi lỗi.
- (7) InvocationRecord có thêm trường output_ref và AttemptRecord thêm trường error (đã qua redact_value) để truy vết, bổ sung không phá chữ ký yêu cầu.
- (8) reservation capacity chỉ tạo cho route chính, candidate SWITCH không tạo reservation mới (reservation chỉ là hint, D8-J-13).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Danh mục thư viện đề xuất cố định phiên bản và cách dựng lại runtime.
- CP7: Tài nguyên thật (D5) qua secret broker.
- User checkpoint M2 (P8/P9): Đã triển khai và có Auditor PASS nhưng chưa ghi user checkpoint M2 nên chưa coi là user đã duyệt.

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật hay I/O mạng; fake chỉ chứng minh logic, không trích làm bằng chứng đóng gate AI/Drive/OAuth theo EG-M7-J-5.
