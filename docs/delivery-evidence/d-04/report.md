# Báo cáo bằng chứng D-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `170b96b2748929758f96d9b5a54726be29fb7600`
- Nguồn quyền: IMPL-PLAN-D Auditor PASS và slice D-04 trong docs/implementation/d/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `77 failed, 10 passed in 0.94s`
- Danh sách FAILED/DID NOT RAISE rút gọn theo tên test kèm thông điệp nguyên văn:
  - `test_request_constants_match_binding`: `AssertionError: assert ({'ai_role': ...ing'}, {}, ()) == ({}, {}, {}, ())`
  - `test_decision_constants_match_binding`: `AssertionError: assert ({'provider_r...fresh_token')) == ({}, {}, {}, ())`
  - `test_binding_version_constant_matches_binding`: `AssertionError: assert '0.0.0' == '1.0.0'`
  - `test_fixture_invalid_case_returns_expected_issue[ProviderRouteRequest-missing_data_sensitivity]`: `AssertionError: assert [] == [('missing_re...sensitivity')]`
  - `test_fixture_invalid_case_returns_expected_issue[ProviderRouteDecision-api_key_leaked]`: `AssertionError: assert [] == [('forbidden_...', 'api_key')]`
  - `test_fixture_invalid_case_returns_expected_issue[ProviderRouteDecision-missing_route_revision]`: `AssertionError: assert [] == [('missing_re...te_revision')]`
  - `test_fixture_invalid_case_returns_expected_issue[ProviderRouteDecision-fallback_order_as_string]`: `AssertionError: assert [] == [('wrong_type...lback_order')]`
  - `test_each_missing_required_field_is_reported`: `AssertionError: assert 0 > 0 (where 0 = len(mappingproxy({})))`
  - `test_field_counterexamples_are_wrong_type` (16 cases): `AssertionError: assert [] == [('wrong_type', field)]`
  - `test_non_mapping_payload_is_wrong_type`: `AssertionError: assert [] == [('wrong_type', '$')]`
  - `test_forbidden_fields_rejected_at_every_depth`: `AssertionError: assert len(ROUTE_DECISION_FORBIDDEN) == 4 (where 0 == 4)`
  - `test_nested_api_key_decision_is_rejected_everywhere`: `AssertionError: assert [] != []`
  - `test_decision_round_trips_fixture_and_is_frozen`: `AssertionError: assert ProviderRouteDecision.__dataclass_params__.frozen (False)`
  - `test_from_payload_rejects_invalid_fixture_cases`: `Failed: DID NOT RAISE <class 'creative.domain.invocation.RouteContractViolation'>`
  - `test_decision_constructor_rejects_bad_values`: `Failed: DID NOT RAISE <class 'creative.domain.invocation.RouteContractViolation'>`
  - `test_fake_route_returns_valid_decision_and_counts`: `AssertionError: assert 0 == 1 (resolve_calls)`
  - `test_fake_route_rejects_invalid_request_and_still_counts`: `Failed: DID NOT RAISE <class 'creative.domain.invocation.RouteContractViolation'>`
  - `test_adapter_returns_scripted_response_per_role`: `AssertionError: assert '' == 'script A'`
  - `test_unscripted_role_raises_and_counts`: `Failed: DID NOT RAISE <class 'creative.adapters.fake_ai.NoScriptedResponse'>`
  - `test_invoke_rejects_wrong_argument_types_before_counting`: `Failed: DID NOT RAISE <class 'TypeError'>`
  - `test_record_field_set_and_frozen`: `AssertionError: assert AIInvocationRecord.__dataclass_params__.frozen (False)`
  - `test_success_record_pins_route_prompt_config_and_fingerprints`: `AssertionError: assert None == '00000000-0000-4000-8000-0000000101'`
  - `test_record_payload_is_complete_and_json_safe`: `AssertionError: assert set() == RECORD_FIELDS`
  - `test_record_string_fields_reject_invalid` (21 cases): `Failed: DID NOT RAISE <class 'ValueError'>`
  - `test_record_without_prompt_revision_is_rejected`: `Failed: DID NOT RAISE <class 'TypeError'>`
  - `test_record_rejects_invalid_values` (11 cases): `Failed: DID NOT RAISE <class 'ValueError'>`
  - `test_record_and_usage_types`: `Failed: DID NOT RAISE <class 'TypeError'>`
  - `test_record_rejects_unredacted_error`: `Failed: DID NOT RAISE <class 'ValueError'>`
  - `test_redact_error_masks_secret_shapes`: `AssertionError: assert CANARY not in out`
  - `test_canary_in_fake_error_never_reaches_record_surfaces`: `AssertionError: assert ModelOutput(text='', proposed_refs=()) is None`
  - `test_result_requires_output_exactly_when_no_error`: `Failed: DID NOT RAISE <class 'ValueError'>`
  - `test_fingerprints_are_deterministic_and_input_sensitive`: `AssertionError: assert '0'*64 != '0'*64`
- Xác nhận: Toàn bộ lỗi đều là `AssertionError` hoặc pytest.raises `DID NOT RAISE`, không có `ImportError`, `ModuleNotFoundError`, `AttributeError`, `NameError`, `TypeError` hay lỗi collection nào; RED chạy trên stub import được, hành vi cho phép mọi thứ.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `87 passed in 0.14s`

## Ánh xạ coveredIds

| coveredId | Mô tả | Các test case kiểm chứng |
|---|---|---|
| `CT-AI-ROUTE-001` | Ranh giới ProviderRoutePort, ProviderRouteRequest/Decision validator theo binding j-provider-route, từ chối forbidden_fields, fake route deterministic | `test_request_constants_match_binding`, `test_decision_constants_match_binding`, `test_binding_version_constant_matches_binding`, `test_drift_comparison_detects_mutated_binding`, `test_fixture_has_valid_and_invalid_cases`, `test_fixture_valid_payloads_have_no_issues`, `test_fixture_invalid_case_returns_expected_issue`, `test_each_missing_required_field_is_reported`, `test_field_counterexamples_are_wrong_type`, `test_optional_fields`, `test_unknown_field_is_ignored`, `test_non_mapping_payload_is_wrong_type`, `test_forbidden_fields_rejected_at_every_depth`, `test_nested_api_key_decision_is_rejected_everywhere`, `test_decision_round_trips_fixture_and_is_frozen`, `test_from_payload_rejects_invalid_fixture_cases`, `test_decision_constructor_rejects_bad_values`, `test_fakes_satisfy_ports_and_signatures`, `test_fake_route_returns_valid_decision_and_counts`, `test_fake_route_rejects_invalid_request_and_still_counts` |
| `CT-AI-010` | AIInvocationRecord frozen lưu trữ refs/revisions/fingerprints/usage/latency/attempt/fallback_path/validation_result/redacted error; FakeAIAdapter theo ai_role | `test_fakes_satisfy_ports_and_signatures`, `test_adapter_returns_scripted_response_per_role`, `test_scripted_tool_fields_are_ignored`, `test_unscripted_role_raises_and_counts`, `test_invoke_rejects_wrong_argument_types_before_counting`, `test_record_field_set_and_frozen`, `test_success_record_pins_route_prompt_config_and_fingerprints`, `test_record_payload_is_complete_and_json_safe`, `test_record_string_fields_reject_invalid`, `test_record_without_prompt_revision_is_rejected`, `test_record_rejects_invalid_values`, `test_record_and_usage_types`, `test_record_rejects_unredacted_error`, `test_redact_error_masks_secret_shapes`, `test_result_requires_output_exactly_when_no_error`, `test_fingerprints_are_deterministic_and_input_sensitive` |
| `TST-SEC-INV-012` | Bảo mật gọi AI: cấm lọt credential/secret/token ở mọi cấp lồng của decision; canary secret trong lỗi upstream được redact sạch; fake adapter và route không mở kết nối mạng | `test_forbidden_fields_rejected_at_every_depth`, `test_nested_api_key_decision_is_rejected_everywhere`, `test_no_network_when_socket_is_patched`, `test_record_rejects_unredacted_error`, `test_redact_error_masks_secret_shapes`, `test_canary_in_fake_error_never_reaches_record_surfaces`, `test_sources_stay_inside_import_allowlist`, `test_test_module_declares_covered_ids` |

## Thay đổi

- `src/creative/domain/invocation.py`: Định nghĩa hằng binding mirror `j-provider-route.json` (`BINDING_VERSION='1.0.0'`, `ROUTE_REQUEST_REQUIRED`, `ROUTE_DECISION_REQUIRED`, `ROUTE_DECISION_FORBIDDEN`), `ValidationIssue`, các hàm `validate_provider_route_request`, `validate_provider_route_decision` kiểm tra trường và quét case-insensitive mọi cấp lồng để phát hiện `forbidden_field`. Lớp ngoại lệ `RouteContractViolation` chỉ chứa mã lỗi và tên trường, không bao giờ chứa giá trị. Dataclass frozen `ProviderRouteDecision` với `from_payload`/`to_payload`. Dataclass frozen `InvocationUsage`. Các hàm pure domain `redact_error` (che giấu mẫu bí mật và known_secrets bằng `[REDACTED]`), `fingerprint_envelope` và `fingerprint_output` sinh SHA-256 canonical JSON. Dataclass frozen `AIInvocationRecord` (16 trường, thẩm định chặt chẽ, từ chối error chưa redact) và `AIInvocationResult`.
- `src/creative/ports/ai.py`: Định nghĩa hai `Protocol` runtime-checkable: `ProviderRoutePort` (`resolve(self, request) -> ProviderRouteDecision`) và `AIInvocationPort` (`invoke(self, decision, envelope) -> AIInvocationResult`). Chỉ import thư viện chuẩn và domain nội bộ.
- `src/creative/adapters/fake_ai.py`: Định nghĩa in-memory fakes `FakeProviderRoute` (thẩm định request theo binding, đếm lượt gọi `resolve_calls`, cấp `ProviderRouteDecision` và lưu reservation) và `FakeAIAdapter` (đếm `invoke_calls` và `calls_by_role`, trả phản hồi định sẵn theo `ai_role` lấy từ reservation, ghi danh sách `AIInvocationRecord`, tự động redact lỗi upstream qua `redact_error`). Không import bất kỳ thư viện mạng/tiến trình/I/O nào.
- `tests/unit/creative/test_d04_ai_route_invocation.py`: Bộ kiểm thử đơn vị với docstring chứa `coveredIds: CT-AI-010, CT-AI-ROUTE-001, TST-SEC-INV-012`, bao phủ 87 test case kiểm tra hằng binding, phát hiện drift, fixture valid/invalid, missing/wrong type, forbidden fields mọi cấp lồng, fake route/adapter, socket monkeypatching không mở mạng, fingerprint, redact canary secret và import allowlist.
- `docs/delivery-evidence/d-04/report.md`: Báo cáo bằng chứng thực thi D-04 với đầy đủ môi trường, RED/GREEN, ánh xạ coveredIds, thay đổi chi tiết, bảng lệnh kiểm tra, quyết định mặc định và danh sách chờ user.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 87 passed in 0.14s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace) |
| 3 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 9 passed, 46 subtests passed in 0.07s |
| 4 | `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider` | 0 | 11 passed, 13 subtests passed in 0.04s |

## Quyết định mặc định (D8)

1. Chỉ sử dụng thư viện tiêu chuẩn Python (stdlib: `__future__`, `collections.abc`, `copy`, `dataclasses`, `hashlib`, `json`, `re`, `types`, `typing`), không thêm bất kỳ thư viện ngoài nào.
2. `ProviderRoutePort.resolve` nhận payload `Mapping` đã được validate theo binding `j-provider-route`; `ProviderRouteDecision` là dataclass frozen tự validate trong `__post_init__` nên không thể chứa `api_key`, `secret_value`, `access_token`, hay `refresh_token` ở bất kỳ cấp lồng nào.
3. `ProviderRouteDecision` không mang trường `ai_role` theo contract binding; `FakeAIAdapter` tra `ai_role` an toàn thông qua `capacity_reservation_ref` do `FakeProviderRoute` cấp.
4. `fingerprint` được tính bằng hàm băm SHA-256 từ chuỗi JSON chuẩn tắc (sorted keys, không khoảng trắng phân tách dư thừa) qua thư viện `hashlib` để đảm bảo độc lập và không phụ thuộc slice D-02.
5. Lỗi upstream được redact bằng regex nhận diện các dạng khoá nhạy cảm kết hợp danh sách `known_secrets`; `AIInvocationRecord` fail-closed từ chối mọi trường `error` chưa được redact sạch.
6. `validation_result` của record tạo bởi fake adapter được đặt mặc định là `'not_run'`, việc thẩm định nội dung output của model thuộc về tầng application nghiệp vụ.
7. `latency_ms`, `attempt`, và `usage` của fake adapter nhận tham số cấu hình xác định, không đọc đồng hồ hệ thống để đảm bảo tính tất định thuần túy trong môi trường kiểm thử.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Phê duyệt danh mục thư viện bổ sung cho Phân hệ D trước CP-2b.
- CP7 tài nguyên thật (D5): Sử dụng tài nguyên/tài khoản thật thông qua secret broker của Phân hệ J sau khi được người dùng phê duyệt.
- User checkpoint M2 (P8/P9): Đã triển khai và có Auditor PASS nhưng chưa ghi nhận checkpoint phê duyệt của người dùng.

## Giới hạn

- Không chạy full test suite, `tests/m1`, `tests/m2`.
- Không chỉnh sửa `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật hay mở kết nối mạng.
- Không đưa secret hay chuỗi canary thật vào báo cáo.
