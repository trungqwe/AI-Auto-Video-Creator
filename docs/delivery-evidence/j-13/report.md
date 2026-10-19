# Báo cáo bằng chứng J-13

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `12c2567e4e67f06ce082696375d9350b6da90092`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-13 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` (chạy khi route_resolver.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `44 failed, 6 passed in 0.65s`
- Danh sách test PASSED kèm lý do (6 passed do stub đã định nghĩa kiểu, giao thức, hằng canary, cấu trúc module):
  - `tests/unit/config/test_j_route_resolver.py::test_module_docstring_declares_covered_ids` (docstring khai báo coveredIds)
  - `tests/unit/config/test_j_route_resolver.py::test_resolver_source_does_not_import_router_or_adapter` (không import router hay adapter)
  - `tests/unit/config/test_j_route_resolver.py::test_route_candidate_is_frozen_with_nine_fields_in_order` (RouteCandidate frozen và đúng thứ tự 9 trường)
  - `tests/unit/config/test_j_route_resolver.py::test_catalog_port_declares_candidates` (RouteCatalogPort khai báo candidates(workspace_id, ai_role))
  - `tests/unit/config/test_j_route_resolver.py::test_constructor_and_resolve_signatures` (chữ ký __init__ và resolve đúng tham số, không có default)
  - `tests/unit/config/test_j_route_resolver.py::test_no_route_error_shape` (NoRouteError đúng cấu trúc Exception, code và rationale_codes)
- Danh sách nhóm test FAILED kèm thông điệp nguyên văn (44 failed):
  - 43 test failed do `NotImplementedError: J-13 ProviderRouteResolver.resolve` khi gọi `resolve(...)`:
    - `test_account_not_enabled_is_excluded` (4 trạng thái: DISABLED, DEGRADED, INVALID, REVOKED)
    - `test_account_without_role_or_in_other_workspace_is_excluded`
    - `test_disabled_account_is_skipped_for_next_candidate`
    - `test_sensitivity_above_candidate_max_is_excluded`
    - `test_unknown_sensitivity_value_is_excluded_fail_closed`
    - `test_cost_above_bound_is_no_route_even_if_sole_candidate`
    - `test_unknown_candidate_cost_is_excluded`
    - `test_unknown_bound_value_excludes_everything`
    - `test_missing_bound_accepts_only_free`
    - `test_local_candidate_excluded_when_desktop_offline`
    - `test_capacity_unavailable_health_or_zero_remaining_is_excluded`
    - `test_two_accounts_in_same_quota_domain_are_one_budget`
    - `test_capacity_taken_by_another_operation_falls_to_next_candidate`
    - `test_unknown_remaining_keeps_candidate_with_quota_uncertain`
    - `test_capacities_is_queried_with_candidate_quota_domain_key`
    - `test_no_candidate_gives_no_route_with_empty_rationale`
    - `test_no_route_rationale_names_the_exclusion_reasons`
    - `test_selects_cheapest_available`
    - `test_tie_on_cost_breaks_by_candidate_ref_ascending`
    - `test_same_input_gives_equal_decision`
    - `test_reserve_is_called_with_operation_key_job_and_role`
    - `test_decision_fields`
    - `test_decision_passes_validate_route_decision_without_forbidden_keys`
    - `test_fixture_valid_request_passes_validate_route_request_and_resolves`
    - `test_fallback_order_contains_only_allowed_remaining_candidates`
    - `test_unknown_fallback_ref_is_ignored`
    - `test_selected_and_ineligible_candidates_are_not_in_fallback_order`
    - `test_request_cannot_inject_ref_outside_catalog`
    - `test_resolve_does_not_mutate_inputs`
    - `test_invalid_inputs_raise_value_error` (10 trường hợp tham số không hợp lệ)
    - `test_invalid_request_type_raises_type_error`
  - 1 test failed do `Failed: DID NOT RAISE ValueError`:
    - `test_empty_route_revision_raises_value_error`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi route_resolver.py là stub và fail hợp lệ do NotImplementedError và DID NOT RAISE đúng oracle.

## Thay đổi

- `src/controlplane/application/config_security/route_resolver.py`: RouteCandidate, RouteCatalogPort, ProviderRouteResolver, NoRouteError, helper kiểm tra đầu vào fail-closed, chọn rẻ nhất theo cost_class rồi candidate_ref, shared quota domain reservation, rationale_codes và fallback_order lọc theo allowed_fallbacks; không import router/adapter, không I/O, không clock.
- `tests/unit/config/test_j_route_resolver.py`: 50 test bao phủ cấu trúc, loại trừ candidate (account, sensitivity, cost bounds, local offline, capacity unavailable), shared quota domain ngân sách đơn, chọn candidate xác định, reservation book gọi đúng operation_key, hợp lệ hóa contract binding J-01, fallback order và kiểm tra đầu vào; docstring coveredIds: CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020.
- `docs/delivery-evidence/j-13/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` | 0 | `50 passed in 0.09s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib, re; t = pathlib.Path('src/controlplane/application/config_security/route_resolver.py').read_text(encoding='utf-8'); assert not re.search('config[.](router|adapter)', t)"` | 0 | PASS (assert qua) |
| 4 | `python -c "import pathlib; t = pathlib.Path('tests/unit/config/test_j_route_resolver.py').read_text(encoding='utf-8'); assert 'coveredIds: CT-AI-ROUTE-001, CT-CAP-001, TST-SEC-INV-020' in t"` | 0 | PASS (assert qua) |

## Quyết định mặc định (D8)

- Thứ tự chi phí `free < low < medium < high` và độ nhạy `public < internal < confidential`; mọi giá trị lạ bị loại bỏ fail-closed (D8-J-04).
- Ràng buộc chi phí thiếu hoặc None chỉ nhận candidate `free`; giá trị bound lạ loại bỏ toàn bộ candidate (D8-J-04).
- Capacity snapshot là None hoặc remaining_requests là None giữ candidate với rationale `QUOTA_UNCERTAIN`, reservation chỉ là hint nội bộ, không phải cam kết của provider (D8-J-13).
- `candidate.roles` là siêu dữ liệu mô tả; danh mục catalog đã lọc theo `ai_role` và thẩm quyền tài khoản do `account_allows_role` thẩm định.
- Khi reserve gặp `CapacityUnavailableError`, resolver tự động thử candidate rẻ kế tiếp và loại candidate thất bại khỏi `fallback_order`; nếu không còn candidate khả dụng thì trả về `NoRouteError` kèm `CAPACITY_UNAVAILABLE`.
- `fallback_order` được sắp xếp theo chi phí tăng dần rồi candidate_ref tăng dần, chỉ chứa các candidate hợp lệ còn lại có mặt trong `allowed_fallbacks`, không theo thứ tự người gọi đưa vào.
- `rationale_codes` của `NoRouteError` liệt kê các mã lý do loại trừ duy nhất theo thứ tự xuất hiện, trả về tuple rỗng nếu danh mục catalog không có candidate.
- `desktop_online` bắt buộc phải là giá trị boolean `True` nguyên bản mới chấp nhận candidate local; các giá trị khác (kể cả truthy như 1) bị từ chối fail-closed.
- `ReservationConflictError` hoặc `ValueError` phát sinh từ `reserve` không bị bắt nuốt (fail-fast để bảo vệ bất biến hệ thống).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Chưa có catalog hay capacity provider thật (thuộc gói hội tụ).
