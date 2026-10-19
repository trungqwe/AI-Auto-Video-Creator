# Báo cáo bằng chứng E-14

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: df699e2d86efeff98f7214fac6cdb40420440ca5
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-14 trong docs/implementation/e/slices.md; binding j-provider-route và fixture payloads.json.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider (chạy trên khung RED bước 1-3 trước khi thay bản thật)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 64 failed, 15 passed in 1.24s
- Danh sách test FAILED rút gọn kèm loại lỗi:
  - test_binding_constants_match_binding: AssertionError (diff ở index 0)
  - test_fixture_invalid_case_returns_expected_issue (4 cases: missing_data_sensitivity, api_key_leaked, missing_route_revision, fallback_order_as_string): AssertionError
  - test_each_missing_required_field_is_reported: AssertionError (len(mappingproxy({})) == 0)
  - test_field_counterexamples_are_wrong_type (12 cases): AssertionError
  - test_non_mapping_payload_is_wrong_type: AssertionError
  - test_decision_forbidden_fields_rejected_at_every_depth: AssertionError (len(ROUTE_DECISION_FORBIDDEN) == 0)
  - test_decision_constructor_rejects_nested_api_key: Failed: DID NOT RAISE RouteContractViolation
  - test_decision_rejects_invalid_fixture_cases_and_bad_values: Failed: DID NOT RAISE RouteContractViolation
  - test_record_field_set_and_frozen: Failed: DID NOT RAISE TypeError
  - test_record_payload_is_complete_and_json_safe: AssertionError
  - test_record_rejects_invalid_values (20 cases): Failed: DID NOT RAISE ValueError
  - test_record_usage_metrics_rules: Failed: DID NOT RAISE TypeError
  - test_error_record_rules: Failed: DID NOT RAISE ValueError
  - test_provider_error_carries_code_retryable_and_redacted_message: AssertionError
  - test_redact_error_masks_secret_shapes: AssertionError
  - test_input_fingerprint_is_deterministic_and_binding_checked: AssertionError
  - test_fake_route_returns_valid_decision_counts_and_rejects_invalid_request: Failed: DID NOT RAISE RouteContractViolation
  - test_engine_raises_timeout_and_rate_limit_as_retryable_redacted_errors: AssertionError
  - test_attempt_policy_requires_both_limits_from_input: Failed: DID NOT RAISE VoiceTrackRejected
  - test_plan_provider_path_follows_decision_order_within_allowed: AssertionError
  - test_provider_outside_allowed_fallbacks_is_rejected: Failed: DID NOT RAISE FallbackNotAllowed
  - test_first_attempt_success_records_route_voice_and_fingerprints: AssertionError
  - test_outcome_requires_exactly_one_of_synthesis_or_error: Failed: DID NOT RAISE ValueError
  - test_retryable_error_retries_same_provider_then_succeeds: TtsProviderError
  - test_non_retryable_error_moves_to_next_fallback_in_order: TtsProviderError
  - test_per_provider_limit_then_fallback: TtsProviderError
  - test_budget_exhausted_returns_last_error_without_more_calls: TtsProviderError
  - test_retry_is_bounded_by_policy: TtsProviderError
  - test_missing_policy_or_bad_binding_makes_zero_calls: Failed: DID NOT RAISE VoiceTrackRejected
  - test_unexpected_engine_behaviour_is_not_swallowed: Failed: DID NOT RAISE TypeError
  - test_canary_never_reaches_record_error_or_outcome_surfaces: TtsProviderError
- Xác nhận không có ImportError, ModuleNotFoundError, NameError, SyntaxError hay lỗi collection; toàn bộ lỗi đều là assertion/behavior oracle.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 79 passed in 0.23s

## Ánh xạ coveredIds

| coveredId | Mô tả | Các test case kiểm chứng |
|---|---|---|
| TST-SEC-INV-012 | Bảo mật gọi TTS: cấm lọt credential/secret/token ở mọi cấp lồng của decision và request; canary secret trong lỗi upstream được redact sạch; fake adapter và route không mở mạng; kiểm tra import allowlist | test_decision_forbidden_fields_rejected_at_every_depth, test_decision_constructor_rejects_nested_api_key, test_route_request_with_secret_key_is_rejected, test_fake_route_returns_valid_decision_counts_and_rejects_invalid_request, test_engine_raises_timeout_and_rate_limit_as_retryable_redacted_errors, test_fakes_open_no_network_when_socket_is_patched, test_redact_error_masks_secret_shapes, test_provider_error_carries_code_retryable_and_redacted_message, test_error_record_rules, test_record_usage_metrics_rules, test_canary_never_reaches_record_error_or_outcome_surfaces, test_sources_stay_inside_import_allowlist, test_test_module_declares_covered_ids |
| CT-AI-ROUTE-001 | VoiceRoutePort, ProviderRouteDecision và ProviderRouteRequest validator theo binding j-provider-route, từ chối forbidden_fields ở mọi cấp lồng, fake route deterministic đếm lượt gọi và reservation | test_binding_constants_match_binding, test_drift_comparison_detects_mutated_binding, test_fixture_has_required_cases, test_fixture_invalid_case_returns_expected_issue, test_fixture_valid_payloads_have_no_issues, test_each_missing_required_field_is_reported, test_field_counterexamples_are_wrong_type, test_optional_nullable_and_unknown_fields_are_accepted, test_non_mapping_payload_is_wrong_type, test_decision_forbidden_fields_rejected_at_every_depth, test_decision_constructor_rejects_nested_api_key, test_route_request_with_secret_key_is_rejected, test_decision_round_trips_fixture_and_is_frozen, test_decision_rejects_invalid_fixture_cases_and_bad_values, test_fakes_satisfy_ports_and_signatures, test_fake_route_returns_valid_decision_counts_and_rejects_invalid_request |
| CT-AI-ROUTE-002 | Fallback order và policy thử: plan_provider_path tuân thủ fallback_order trong allowed_fallbacks; TtsAttemptPolicy nhận max_attempts và max_attempts_per_provider từ input; run_tts_attempts giới hạn retry/fallback, hết budget trả lỗi cuối | test_attempt_policy_requires_both_limits_from_input, test_attempt_limits_have_no_default_in_source, test_plan_provider_path_follows_decision_order_within_allowed, test_provider_outside_allowed_fallbacks_is_rejected, test_first_attempt_success_records_route_voice_and_fingerprints, test_outcome_requires_exactly_one_of_synthesis_or_error, test_retryable_error_retries_same_provider_then_succeeds, test_non_retryable_error_moves_to_next_fallback_in_order, test_per_provider_limit_then_fallback, test_budget_exhausted_returns_last_error_without_more_calls, test_retry_is_bounded_by_policy, test_missing_policy_or_bad_binding_makes_zero_calls, test_unexpected_engine_behaviour_is_not_swallowed |

## Ánh xạ phản ví dụ

- Decision có api_key được chấp nhận: Loại trừ bởi test_decision_forbidden_fields_rejected_at_every_depth (4 tên x 6 vị trí lồng nhau) và test_decision_constructor_rejects_nested_api_key.
- Fallback sang provider ngoài danh sách: Loại trừ bởi test_provider_outside_allowed_fallbacks_is_rejected và test_missing_policy_or_bad_binding_makes_zero_calls (raise FallbackNotAllowed trước mọi lượt gọi engine).
- Fake mở socket: Loại trừ bởi test_fakes_open_no_network_when_socket_is_patched (monkeypatch socket.create_connection và getaddrinfo, 0 lượt gọi mạng khi fake synthesize) và test_sources_stay_inside_import_allowlist.
- Record chứa canary: Loại trừ bởi test_canary_never_reaches_record_error_or_outcome_surfaces (kiểm tra repr, str, to_json, to_payload, asdict của record và outcome), test_error_record_rules và test_provider_error_carries_code_retryable_and_redacted_message.
- Retry vô hạn: Loại trừ bởi test_retry_is_bounded_by_policy, test_budget_exhausted_returns_last_error_without_more_calls và test_attempt_limits_have_no_default_in_source (giới hạn cứng từ policy input).

## Thay đổi

- src/voice/ports/tts.py: Định nghĩa 2 Protocol runtime_checkable VoiceRoutePort và TtsEnginePort thuần khai báo, không I/O, E không giữ secret.
- src/voice/domain/tts_invocation.py: Validator route J theo binding j-provider-route (bản E-local), RouteContractViolation, ProviderRouteDecision frozen, redact_error, fingerprint_tts_input, TtsProviderError, UsageMetrics bất biến, TtsSynthesis, TtsInvocationRecord frozen đủ 15 trường, TtsAttemptPolicy, FallbackNotAllowed, plan_provider_path và run_tts_attempts.
- src/voice/adapters/fake_tts.py: Fake in-memory FakeVoiceRoute (thẩm định request, cấp reservation, đếm resolve_calls) và FakeTtsEngine (kiểm tra kiểu, binding, reservation trước khi đếm synthesize_calls; sinh WAV bằng wave đúng thời lượng; mô phỏng timeout/rate limit dạng TtsProviderError có retryable).
- tests/unit/voice/test_e14_tts_route_invocation.py: Bộ 79 unit test kiểm tra toàn diện binding, validator, drift, forbidden fields, record, error redact, fake adapter, policy retry/fallback, canary masking và ranh giới import.
- docs/delivery-evidence/e-14/report.md: Báo cáo bằng chứng thực thi E-14 đầy đủ các mục theo quy định.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider | 0 | 79 passed in 0.23s |
| 2 | git diff --check | 0 | PASS (không có output, không có khoảng trắng cuối dòng) |
| 3 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 9 passed, 49 subtests passed in 0.08s |
| 4 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.08s |

## Quyết định mặc định (D8)

1. Bản sao validator route E-local: Do test ranh giới gói E-01 nghiêm cấm import từ src/creative hay creative.*, các logic thẩm định ProviderRouteRequest và ProviderRouteDecision được nhân bản độc lập tại src/voice/domain/tts_invocation.py.
2. Request cũng từ chối secret key theo INV-012: validate_provider_route_request kiểm tra và từ chối các trường nhạy cảm trong ROUTE_DECISION_FORBIDDEN ở mọi cấp lồng để đảm bảo an toàn fail-closed.
3. Policy thử có hai input bắt buộc: parse_attempt_policy yêu cầu cả max_attempts và max_attempts_per_provider từ input; thiếu một trong hai sẽ raise VoiceTrackRejected(INPUT_NOT_READY, missing_attempt_policy); tuyệt đối không có số lần thử mặc định trong mã nguồn.
4. Fake timeout và rate limit có retryable=True: FakeFailure của timeout và rate limit mặc định retryable=True; lỗi không retryable (như upstream rejected) lập tức chuyển sang provider fallback kế tiếp.
5. model_ref/account_ref của decision áp dụng cho lượt thử fallback: Đây là GIẢ ĐỊNH tạm thời cho slice E-14 thuần domain; Phân hệ J sẽ cấp decision riêng cho từng provider ở CONV-E-11.
6. run_tts_attempts là hàm domain thuần: Quyết định điều phối retry/fallback ở mức hệ thống phân tán thực tế thuộc về Phân hệ G (CONV-E-05).
7. ai_role voice_synthesis là GIẢ ĐỊNH: ai_role chính thức sẽ do Phân hệ J đăng ký tại CONV-E-11.
8. usage_metrics là UsageMetrics bất biến: Kế thừa Mapping, từ chối mọi key cấm trong ROUTE_DECISION_FORBIDDEN và yêu cầu dữ liệu có thể serialize JSON.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10: Phê duyệt danh mục thư viện bổ sung cho phân hệ trước CP-2b.
- CP7 tài nguyên thật (D5): Sử dụng tài khoản/dịch vụ TTS thật thông qua secret broker của Phân hệ J sau khi được người dùng phê duyệt.
- TECH-OPEN-004: Lựa chọn danh sách nhà cung cấp TTS chính thức (primary/fallback).
- CONV-E-07 và CONV-E-11: Hội tụ hợp đồng đọc văn bản kịch bản và đăng ký ai_role/decision với Phân hệ J.
- User checkpoint M2 (P8/P9): Đã triển khai và có Auditor PASS nhưng chưa ghi nhận checkpoint phê duyệt của người dùng.

## Giới hạn

- Không chạy full test suite, tests/m1, tests/m2.
- Không chỉnh sửa pyproject.toml, uv.lock.
- Không gọi mạng hay dịch vụ TTS thật.
- Không đưa secret hay chuỗi canary thật vào báo cáo.
- SHA commit được báo cáo trong worker_done, không ghi cố định trong tệp này.
