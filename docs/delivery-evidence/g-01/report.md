# Báo cáo bằng chứng G-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `1f6f35d6bfb9063eb24c83d688e22821842c5e67`
- Nguồn quyền: IMPL-PLAN-G Auditor PASS và slice G-01 trong docs/implementation/g/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` (chạy khi activity_binding.py là stub raise NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `39 failed, 4 passed in 0.42s`
- Các test FAILED kèm thông điệp nguyên văn:
  - `test_fixture_valid_payloads_return_no_issues`: NotImplementedError: G-01 validate_activity_request / G-01 validate_activity_result
  - `test_fixture_invalid_payloads_return_expected_error`: NotImplementedError: G-01 validate_activity_request / G-01 validate_activity_result
  - `test_missing_required_and_wrong_type_follow_binding`: NotImplementedError: G-01 validate_activity_request / G-01 validate_activity_result
  - `test_optional_fields_may_be_absent_and_valid_when_typed`: NotImplementedError: G-01 validate_activity_request
  - `test_unknown_fields_are_ignored`: NotImplementedError: G-01 validate_activity_request
  - `test_forbidden_fields_are_rejected_with_any_value`: NotImplementedError: G-01 validate_activity_request
  - `test_integer_rejects_bool_float_and_string`: NotImplementedError: G-01 validate_activity_result
  - `test_recovery_epoch_must_be_string`: NotImplementedError: G-01 validate_activity_result
  - `test_disposition_accepts_only_contract_values`: NotImplementedError: G-01 validate_activity_result
  - `test_datetime_accepts_rfc3339`: NotImplementedError: G-01 validate_activity_result
  - `test_datetime_rejects_non_rfc3339`: NotImplementedError: G-01 validate_activity_result
  - `test_side_effect_requires_execution_grant`: NotImplementedError: G-01 validate_activity_request
  - `test_side_effect_flag_must_be_bool`: NotImplementedError: G-01 validate_activity_request
  - `test_non_object_payload_is_wrong_type`: NotImplementedError: G-01 validate_activity_request / G-01 validate_activity_result
  - `test_issues_are_plain_dicts_in_stable_order_and_payload_is_not_mutated`: NotImplementedError: G-01 validate_activity_request
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED do NotImplementedError/AssertionError.

## Thay đổi

- `src/controlplane/domain/orchestration/activity_binding.py`: hằng bảng trường theo binding, `validate_activity_request`, `validate_activity_result`.
- `tests/unit/orchestration/test_g_activity_binding.py`: test đọc `tests/fixtures/contracts/g-activity-execution/payloads.json` và `docs/parallel-delivery/bindings/g-activity-execution.json`.
- `docs/delivery-evidence/g-01/report.md`: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` (GREEN) | 0 | 43 passed in 0.05s |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. Trường lạ được bỏ qua kể cả ở ActivityResult (kể cả secret_value, raw_blob), vì binding chỉ khai forbidden_fields cho ActivityRequest.
2. Trường có mặt nhưng giá trị None là wrong_type, không phải missing_required.
3. Payload không phải dict trả `[{code: wrong_type, field: '$'}]`.
4. `side_effect` không phải bool thì raise TypeError (fail-closed, tránh chuỗi 'False' bị coi là truthy).
5. datetime là chuỗi RFC 3339 có offset (Z hoặc ±hh:mm), chữ T và Z viết hoa, không nhận giây nhuận :60.
6. Chỉ dùng stdlib (`re`, `datetime`, `types`), không thêm thư viện.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`, fixture hay binding.
- Không gọi dịch vụ thật.
