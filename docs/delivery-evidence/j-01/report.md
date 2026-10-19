# Báo cáo bằng chứng J-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `e613e7e1ba9eb7f35f225ff49f972b2836d9173a`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-01 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` (chạy khi route_binding.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `38 failed, 10 passed in 0.38s`
- Các test FAILED kèm thông điệp nguyên văn:
  - `tests/unit/config/test_j_route_binding.py::test_fixture_valid_payloads_return_no_issues[ProviderRouteRequest-0] FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_fixture_valid_payloads_return_no_issues[ProviderRouteDecision-0] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fixture_invalid_payloads_return_expected_error[ProviderRouteRequest-missing_data_sensitivity] FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_fixture_invalid_payloads_return_expected_error[ProviderRouteDecision-api_key_leaked] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fixture_invalid_payloads_return_expected_error[ProviderRouteDecision-missing_route_revision] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fixture_invalid_payloads_return_expected_error[ProviderRouteDecision-fallback_order_as_string] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_missing_required_and_wrong_type_follow_binding[ProviderRouteDecision] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_missing_required_and_wrong_type_follow_binding[ProviderRouteRequest] FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_optional_fields_may_be_absent_and_valid_when_typed FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_unknown_fields_are_ignored[ProviderRouteDecision] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_unknown_fields_are_ignored[ProviderRouteRequest] FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad0] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad1] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad2] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad3] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad4] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_must_be_array_of_strings[bad5] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_accepts_array_of_strings[good0] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_accepts_array_of_strings[good1] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_rationale_codes_accepts_array_of_strings[good2] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fallback_order_must_be_array[gemini] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fallback_order_must_be_array[None] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fallback_order_must_be_array[bad2] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fallback_order_must_be_array[5] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_fallback_order_must_be_array[bad4] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[api_key] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[API_KEY] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[Api_Key] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[secret_value] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[SECRET_VALUE] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[access_token] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[Access_Token] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[refresh_token] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_forbidden_decision_fields_are_rejected_case_insensitively_with_any_value[REFRESH_TOKEN] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_all_forbidden_fields_are_reported_once_in_binding_order FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_non_object_payload_is_wrong_type[ProviderRouteDecision] FAILED (NotImplementedError: J-01 validate_route_decision)`
  - `tests/unit/config/test_j_route_binding.py::test_non_object_payload_is_wrong_type[ProviderRouteRequest] FAILED (NotImplementedError: J-01 validate_route_request)`
  - `tests/unit/config/test_j_route_binding.py::test_issues_are_plain_dicts_in_stable_order_and_payload_is_not_mutated FAILED (NotImplementedError: J-01 validate_route_decision)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED do NotImplementedError.

## Thay đổi

- `src/controlplane/domain/config_security/route_binding.py`: hằng REQUEST_FIELDS, DECISION_FIELDS, DECISION_ARRAY_ITEMS, FORBIDDEN_DECISION_FIELDS; dataclass frozen ProviderRouteRequest (8 trường) và ProviderRouteDecision (10 trường); validate_route_request, validate_route_decision.
- `tests/unit/config/test_j_route_binding.py`: test đọc `tests/fixtures/contracts/j-provider-route/payloads.json` và `docs/parallel-delivery/bindings/j-provider-route.json`; docstring có dòng coveredIds: CT-AI-ROUTE-001, TST-SEC-INV-012.
- `docs/delivery-evidence/j-01/report.md`: báo cáo này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` | 0 | `48 passed in 0.07s` |
| 2 | `git diff --check` | 0 | PASS (không output) |
| 3 | `python -c "import pathlib, re; assert re.search('config[.](router|adapter)', pathlib.Path('src/controlplane/domain/config_security/route_binding.py').read_text(encoding='utf-8')) is None"` | 0 | không có kết quả |

## Quyết định mặc định (D8)

1. Trường lạ được bỏ qua ở cả request và decision; chỉ bốn khóa cấm của decision bị từ chối.
2. Trường có mặt nhưng giá trị None là wrong_type, không phải missing_required.
3. Payload không phải dict trả `[{code: wrong_type, field: '$'}]`.
4. Khóa cấm so khớp không phân biệt hoa thường (casefold), báo bằng tên chuẩn viết thường của binding, mỗi tên một lần theo thứ tự FORBIDDEN_DECISION_FIELDS, bất kể giá trị; không phản chiếu khóa gốc của payload vào lỗi.
5. rationale_codes phải là mảng chuỗi; phần tử sai kiểu cho đúng một lỗi wrong_type trên rationale_codes. Các mảng khác không kiểm phần tử vì binding không khai items.
6. Chuỗi rỗng vẫn là string hợp lệ; ý nghĩa giá trị (thứ tự cost class, độ nhạy) thuộc J-13 theo D8-J-04, không kiểm ở J-01.
7. Chỉ dùng stdlib (`dataclasses`, `types`, `typing`); không import router hay adapter của P1.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, lockfile, fixture hay binding.
- Không gọi dịch vụ thật.
