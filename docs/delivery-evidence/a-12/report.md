# Báo cáo bằng chứng A-12

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `f1d4a4c543fb9c14a48c3e44e82c20622d0ddc34`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-12 trong `docs/implementation/a/slices.md`; phụ thuộc A-04 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider`
- Trạng thái mã lúc RED: port hoàn chỉnh; `secure_fetch.py` là khung tối thiểu (`safe_headers` trả nguyên header, `parse_retry_after` trả None, `SecureFetcher.fetch` trả None).
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `37 failed, 22 passed in 0.41s`
- Test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/unit/collection/test_a12_secure_fetch.py::test_missing_policy_is_input_not_ready_without_io` (AssertionError: None)
  - `FAILED tests/unit/collection/test_a12_secure_fetch.py::test_success_pins_validated_addresses_and_records_safe_observation` (AssertionError: assert False where False = isinstance(None, FetchedDocument))
  - `FAILED tests/unit/collection/test_a12_secure_fetch.py::test_safe_headers_drop_credentials_cookies_and_tokens` (AssertionError: assert (('Authorization', 'x'), ...) == (('content-type', 'text/html'), ('etag', '"1"')))
- Xác nhận: 0 error, không có ModuleNotFoundError, ImportError hay collection error; mọi lỗi RED là AssertionError sai oracle.

## Thay đổi

- `src/source_ingestion/ports/source_adapter.py`: `AdapterOperation` (6 operation), `CapabilityUnavailable` (code `CAPABILITY_UNAVAILABLE`, operation, adapter id/version, reason, `retryable=False`), `AdapterDescriptor` (`supports`, `unavailable`; khai báo resume bắt buộc `checkpoint_version`), DTO `ProbeResult`, `CandidateListing`, `FetchObservation`, `FetchedDocument`, `ExtractedCandidate`, Protocol `SourceAdapter` runtime_checkable.
- `src/source_ingestion/adapters/secure_fetch.py`: `FetchPolicy` (không default), `TransportRequest`/`TransportResponse`/`Transport`, `safe_headers`, `parse_retry_after`, `fetch_problem` (dùng `controlplane.domain.common.contracts.ProblemDetail`), `SecureFetcher.fetch`.
- `tests/unit/collection/test_a12_secure_fetch.py`: docstring `coveredIds: A-RULE-013, A-RULE-014`; fixture autouse thay `socket.getaddrinfo`, `socket.create_connection`, `socket.gethostbyname`, `socket.gethostbyname_ex` bằng hàm ném `AssertionError`; transport, resolver, clock giả.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Protocol 6 operation | `test_source_adapter_protocol_declares_six_operations` |
| Năng lực thiếu không trả list rỗng như thành công | `test_missing_capability_is_structured_not_empty_success`, `test_capability_unavailable_requires_operation_and_reason`, `test_descriptor_validates_operations_and_checkpoint_version` |
| Thiếu policy → INPUT_NOT_READY | `test_missing_policy_is_input_not_ready_without_io`, `test_fetch_policy_rejects_invalid_limits` |
| A-04 ở mọi hop, redirect public→127.0.0.1 bị chặn (A-RULE-013) | `test_unsafe_initial_locator_never_reaches_transport`, `test_redirect_to_unsafe_destination_is_not_followed`, `test_redirect_host_is_resolved_and_validated_at_every_hop`, `test_safe_relative_redirect_is_followed_and_chain_recorded`, `test_success_pins_validated_addresses_and_records_safe_observation` |
| Giới hạn và vòng redirect | `test_redirect_loop_is_detected`, `test_redirect_limit_comes_from_policy`, `test_redirect_without_location_is_problem` |
| Body quá giới hạn không đọc hết, MIME | `test_oversized_body_stops_reading_at_policy_limit`, `test_declared_length_over_limit_is_rejected_before_reading`, `test_media_type_outside_policy_is_rejected_without_reading` |
| Thời gian, timeout retryable | `test_transport_timeout_maps_to_retryable_problem`, `test_policy_deadline_bounds_body_read`, `test_redirect_hops_share_one_deadline`, `test_connection_error_maps_to_retryable_problem`, `test_resolution_failure_is_retryable_problem` |
| 429 Retry-After retryable, HTTP status | `test_rate_limit_maps_retry_after_to_retryable_problem`, `test_parse_retry_after`, `test_http_status_problems` |
| Authorization/Cookie/token không vào observation/log (A-RULE-014) | `test_safe_headers_drop_credentials_cookies_and_tokens`, `test_sensitive_headers_never_reach_observation_or_log`, `test_problem_and_log_do_not_echo_credentials` |
| Test không mở socket thật | `test_network_guard_blocks_real_dns_and_connect`, `test_modules_do_not_import_network_stack` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider` | 0 | 59 passed in 0.07s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.07s |
| 3 | `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.09s |
| 4 | `git diff --check` | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. `FetchPolicy` không có giá trị mặc định; giá trị thật chờ MODULE-A-OPEN-009 (đo ở CP7). Thiếu policy trả ProblemDetail `INPUT_NOT_READY`, không gọi resolver hay transport.
2. Mỗi hop, gồm hop đầu, gọi `validate_locator` của A-04 với resolver tiêm vào và truyền địa chỉ đã kiểm cho transport để ghim kết nối; transport không tự theo redirect. HTTP client thật chưa chọn (IMPL-PLAN-A-OPEN-001, TECH-POC-001).
3. Redirect gồm 301/302/303/307/308; `max_redirects` là số redirect được theo; vòng phát hiện bằng locator canonical đã thăm; một deadline tổng `timeout_seconds` cho mọi hop và lúc đọc body, clock monotonic tiêm vào.
4. Problem dùng `ProblemDetail` của controlplane, type `urn:source-ingestion:problem:<code>`; retryable gồm `FETCH_TIMEOUT`, `CONNECTION_FAILED`, `RESOLUTION_FAILED`, `RATE_LIMITED`, `UPSTREAM_ERROR` (408, 5xx); các code còn lại không retryable.
5. `Retry-After` nhận delta-seconds hoặc HTTP-date; không parse được thì `retry_after_seconds = None`, problem vẫn retryable.
6. Header bị loại nếu tên chứa `auth`, `cookie`, `token`, `secret`, `api-key`, `apikey`, `password`, `session`, `signature`; tên header lưu chữ thường. Log chỉ ghi số hop, status và code problem, không ghi locator hay header.
7. Body đọc theo chunk và dừng ngay khi vượt `max_body_bytes`; `Content-Length` vượt giới hạn bị từ chối trước khi đọc; MIME so khớp chính xác `allowed_media_types` sau khi bỏ tham số sau `;`.
8. Không thêm thư viện; chỉ stdlib và module controlplane theo plan §4.

## Mục mở / follow-up

- Query string chứa token trong `redirect_chain` chưa được redact (A-04 chỉ chặn userinfo); đề xuất xử lý ở A-17/CONV-A-08.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- MODULE-A-OPEN-008, MODULE-A-OPEN-009, IMPL-PLAN-A-OPEN-001

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi mạng hay DNS thật; transport thật thuộc CP7.
