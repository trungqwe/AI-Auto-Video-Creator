# Báo cáo bằng chứng J-12

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 484661bdbbb463a98e7e8ab3609a9555e3c52892
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-12 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider (chạy khi capacity_reservation.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 64 failed, 2 passed in 0.64s
- Các test FAILED kèm thông điệp nguyên văn (NotImplementedError):
  - 	ests/unit/config/test_j_capacity_reservation.py::test_reservation_has_six_fields_in_spec_order_and_is_frozen FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_reserve_sets_expiry_from_ttl_and_known_confidence FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[-1] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[True] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[False] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[1.0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[1] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_must_be_positive_int[None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[-5] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[True] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[False] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[1.5] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[60] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_ttl_seconds_must_be_positive_int_and_representable[1000000000000] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_now_must_be_timezone_aware_datetime[now0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_now_must_be_timezone_aware_datetime[2026-10-20T10:30:00+00:00] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_now_must_be_timezone_aware_datetime[None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[-domain_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[-operation_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[   -domain_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[   -operation_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[None-domain_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[None-operation_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[5-domain_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_keys_must_be_non_empty_strings[5-operation_key] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_domain_capacity_must_be_domain_capacity_of_same_domain[capacity0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_domain_capacity_must_be_domain_capacity_of_same_domain[cap] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_domain_capacity_must_be_domain_capacity_of_same_domain[4] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_same_operation_key_returns_same_reservation_without_second_entry FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_replay_returns_old_reservation_even_if_remaining_no_longer_fits FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_same_operation_key_with_other_units_or_domain_conflicts[3-gemini/proj-a/flash] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_same_operation_key_with_other_units_or_domain_conflicts[2-gemini/proj-b/flash] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_operation_key_is_forgotten_after_expiry_and_after_release FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_two_accounts_of_same_quota_domain_share_one_remaining_budget FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_four_accounts_do_not_multiply_the_domain_budget FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_exact_fit_is_granted_and_one_more_unit_is_refused FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_above_remaining_are_refused_on_empty_book[4-5] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_units_above_remaining_are_refused_on_empty_book[0-1] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_no_capacity_error_carries_code_domain_and_retry_after_from_reset_at FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[reset_at0-expected0] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[2026-10-20T12:00:00Z-expected1] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[None-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[2026-10-20T09:00:00+00:00-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[2026-10-20T10:30:00+00:00-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[bad-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_retry_after_is_future_aware_reset_at_or_none[2026-10-20T12:00:00-None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_unknown_remaining_is_granted_as_uncertain_without_summing[None] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_unknown_remaining_is_granted_as_uncertain_without_summing[capacity1] FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_expired_snapshot_gives_uncertain_reservation FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_reservations_of_other_domains_do_not_consume_this_domain FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_expired_reservation_does_not_hold_capacity FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_expire_releases_only_expired_reservations_and_returns_their_refs FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_expire_requires_timezone_aware_now FAILED (NotImplementedError: J-12 expire)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_release_frees_capacity_and_is_idempotent FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_release_rejects_blank_reference[] FAILED (NotImplementedError: J-12 release)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_release_rejects_blank_reference[  ] FAILED (NotImplementedError: J-12 release)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_release_rejects_blank_reference[None] FAILED (NotImplementedError: J-12 release)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_release_rejects_blank_reference[3] FAILED (NotImplementedError: J-12 release)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_book_uses_injected_store_port FAILED (NotImplementedError: J-12 reserve)
  - 	ests/unit/config/test_j_capacity_reservation.py::test_port_declares_five_methods_and_default_store_works FAILED (NotImplementedError: J-12 reserve)
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED hợp lệ do NotImplementedError.

## Thay đổi

- src/controlplane/application/config_security/capacity_reservation.py: Module triển khai quản lý giữ trước capacity (reservation) trong bộ nhớ theo quota domain (provider/project/model), bao gồm dataclass frozen Reservation (6 trường theo thứ tự spec), Protocol ReservationStorePort cùng cài đặt mặc định InMemoryReservationStore, ngoại lệ ReservationConflictError và CapacityUnavailableError (code NO_CAPACITY, thuộc tính retry_after tính từ reset_at hợp lệ trong tương lai), và lớp nghiệp vụ CapacityReservationBook với các phương thức:
eserve kiểm tra nghiêm ngặt kiểu/giá trị đầu vào (units, ttl_seconds > 0, now aware, key không rỗng, domain_capacity khớp domain_key), expire tự động, bảo đảm tính idempotent theo operation_key (tái sử dụng trả bản cũ không kiểm lại quota, sai units/domain báo conflict), tính tổng giữ trước theo domain độc lập tài khoản người dùng, cấp UNCERTAIN khi remaining_requests None, và ném ngoại lệ khi vượt hạn mức;
elease giải phóng tài nguyên idempotent; expire dọn dẹp các reservation đã hết hạn (now >= expires_at). Module hoàn toàn pure-domain: không đọc đồng hồ hệ thống, không sleep, không retry, không dùng thread/asyncio.
- 	ests/unit/config/test_j_capacity_reservation.py: Bộ kiểm thử 66 test cases bao phủ toàn diện tính bất biến của Reservation, chữ ký không mặc định/không tham số account, xác thực nghiêm ngặt đầu vào (units, ttl, now aware, keys, domain_capacity), tính idempotent và phát hiện xung đột theo operation_key, hạn mức dùng chung giữa nhiều tài khoản trong cùng quota domain (không nhân bội hạn mức), cơ chế báo lỗi NO_CAPACITY kèm retry_after, cấp UNCERTAIN khi thiếu dữ liệu quota, tính độc lập giữa các domain khác nhau, dọn dẹp hết hạn và giải phóng idempotent, cơ chế tiêm phụ thuộc ReservationStorePort và kiểm tra tĩnh mã nguồn không đọc đồng hồ hay sleep; docstring chứa dòng coveredIds: CT-CAP-002, RM-RISK-007.
- docs/delivery-evidence/j-12/report.md: Báo cáo bằng chứng thực thi RED/GREEN, các quyết định D8 và danh sách chờ user của task J-12.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider | 0 | 66 passed in 0.09s |
| 2 | git diff --check | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. reserve validate trước rồi gọi expire(now) rồi tra operation_key; operation_key của reservation đã hết hạn hoặc đã release bị quên nên gọi lại tạo reservation mới.
2. replay cùng operation_key trả bản cũ, không gia hạn TTL, không kiểm lại capacity.
3. retry_after là datetime có múi giờ lấy từ reset_at khi reset_at nằm sau now, ngược lại None.
4. hết hạn khi now >= expires_at (khớp J-07).
5. confidence_flag là 'KNOWN' khi biết remaining_requests, 'UNCERTAIN' khi None (hint, không phải cam kết provider).
6. domain_capacity.domain_key phải trùng domain_key.
7. release trả bool, expire trả tuple ref.
8. ref mặc định
es-<uuid4 hex>, test tiêm ref_factory xác định.
9. reservation chỉ tính theo domain_key, không có tham số account.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
- Chưa nối vào application/infrastructure (J-13 sẽ dùng).
- Không sleep/retry (G xử lý backoff).
