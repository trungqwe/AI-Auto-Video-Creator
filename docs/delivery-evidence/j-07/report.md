# Báo cáo bằng chứng J-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d83ab6107189a14ba92fb3d8d81789f946b461a8`
- Nguồn quyền: IMPL-PLAN-J-FIX1 Auditor PASS và slice J-07 trong docs/implementation/j/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` (chạy khi capacity_snapshot.py là stub)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `99 failed, 5 passed in 0.66s`
- Các test FAILED kèm thông điệp nguyên văn (AssertionError / DID NOT RAISE / NotImplementedError):
  - `tests/unit/config/test_j_capacity_snapshot.py::test_negative_number_is_rejected[...] FAILED (Failed: DID NOT RAISE ValueError)` (8 trường int/float)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_bool_is_rejected[...] FAILED (Failed: DID NOT RAISE ValueError)` (16 trường hợp True/False)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_non_integer_count_is_rejected[...] FAILED (Failed: DID NOT RAISE ValueError)` (6 trường int)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_non_finite_measure_is_rejected[...] FAILED (Failed: DID NOT RAISE ValueError)` (4 trường hợp nan/inf)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_unknown_confidence_is_rejected[...] FAILED (Failed: DID NOT RAISE ValueError)` (5 giá trị confidence lạ)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_identity_field_must_be_non_empty_string[...] FAILED (Failed: DID NOT RAISE ValueError)` (24 trường hợp rỗng/whitespace/non-str)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_time_field_rejects_non_text_non_datetime[...] FAILED (Failed: DID NOT RAISE ValueError)` (4 trường time)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_quota_domain_key_ignores_account_and_separates_scopes FAILED (NotImplementedError: J-07 quota_domain_key)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_quota_domain_key_is_unambiguous_and_rejects_empty_parts FAILED (NotImplementedError: J-07 quota_domain_key)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_expires_at_none_is_not_expired_and_keeps_confidence FAILED (NotImplementedError: J-07 is_expired)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_aware_expiry_is_compared_against_now[...] FAILED (NotImplementedError: J-07 is_expired)` (7 trường hợp aware expiry)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_naive_or_unparsable_expiry_is_expired_fail_closed[...] FAILED (NotImplementedError: J-07 is_expired)` (4 trường hợp naive/unparsable)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_expired_snapshot_is_unknown_and_has_no_remaining[...] FAILED (NotImplementedError: J-07 effective_confidence)` (2 trường hợp)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_fresh_snapshot_keeps_confidence_and_remaining_per_kind FAILED (NotImplementedError: J-07 effective_confidence)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_remaining_is_none_for_unknown_confidence_even_when_fresh FAILED (NotImplementedError: J-07 remaining)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_remaining_is_none_when_limit_is_none_and_clamped_at_zero FAILED (NotImplementedError: J-07 remaining)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_remaining_rejects_unknown_kind FAILED (NotImplementedError: J-07 remaining)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_naive_now_is_rejected FAILED (Failed: DID NOT RAISE ValueError)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_four_accounts_in_one_domain_do_not_multiply_limit FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_different_project_gives_two_domains FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_latest_observed_at_wins_regardless_of_input_order FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_observed_at_is_compared_as_instants_across_offsets FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_missing_naive_or_unparsable_observed_at_is_oldest[...] FAILED (NotImplementedError: J-07 merge_quota_domain)` (3 trường hợp)
  - `tests/unit/config/test_j_capacity_snapshot.py::test_tie_on_observed_at_takes_later_snapshot_in_input FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_expired_latest_snapshot_gives_unknown_and_no_remaining FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_empty_input_gives_empty_dict FAILED (NotImplementedError: J-07 merge_quota_domain)`
  - `tests/unit/config/test_j_capacity_snapshot.py::test_domain_capacity_has_eight_fields_is_frozen_and_has_no_secret_field FAILED (NotImplementedError: J-07 merge_quota_domain)`
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; RED chạy khi capacity_snapshot.py là stub và fail hợp lệ do NotImplementedError và AssertionError / DID NOT RAISE.

## Thay đổi

- `src/controlplane/domain/config_security/capacity_snapshot.py`: ProviderCapacitySnapshot dataclass frozen 21 trường với validation nghiêm ngặt (__post_init__), quota_domain_key mã hóa percent-encoding theo provider/project/model loại trừ account (ADR-0008), is_expired so sánh thời gian có timezone và fail-closed khi thiếu múi giờ/không phân tích được, effective_confidence trả unknown khi hết hạn, remaining tính số lượng còn lại và trả None khi confidence unknown hoặc limit None, DomainCapacity dataclass frozen 8 trường không chứa secret, merge_quota_domain gom theo quota domain lấy snapshot mới nhất theo observed_at (không nhân limit theo account).
- `tests/unit/config/test_j_capacity_snapshot.py`: 104 test bao phủ toàn bộ 21 trường của ProviderCapacitySnapshot, kiểm tra từ chối số âm, bool, float không nguyên, nan/inf, confidence lạ, identity rỗng; kiểm tra quota_domain_key không chứa account; kiểm tra is_expired với aware datetime, naive/unparsable fail-closed; kiểm tra effective_confidence và remaining theo từng loại quota; kiểm tra merge_quota_domain gom 4 tài khoản không nhân limit, so sánh observed_at giữa các múi giờ, xử lý snapshot hết hạn; docstring có dòng `coveredIds: CT-CAP-001, RM-RISK-007`.
- `docs/delivery-evidence/j-07/report.md`: báo cáo bằng chứng này.

## GREEN và lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` | 0 | `104 passed in 0.12s` |
| 2 | `git diff --check` | 0 | PASS (không output) |

## Quyết định mặc định (D8)

1. D8-J-13 confidence thuộc observed, estimated, unknown; quan sát hết hạn hoặc không phân tích được coi là unknown.
2. D8-J-06 module không đọc đồng hồ, now do caller truyền và phải có múi giờ, now naive raise ValueError; hết hạn khi now >= expires_at.
3. quota domain key là provider/project/model được mã hóa phần trăm từng thành phần, không có account (ADR-0008).
4. số đếm limit/used là int không âm không bool, latency_ms và error_rate là số hữu hạn không âm.
5. merge lấy snapshot mới nhất theo observed_at bất kể capability, hòa thì snapshot đứng sau, observed_at thiếu/naive/không phân tích được là cũ nhất, không cộng limit.
6. chuỗi thời gian không phân tích được vẫn nhận ở constructor và bị coi hết hạn ở is_expired.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- CP7-J-03 quan sát quota thật
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, lockfile, fixture, binding.
- Không gọi dịch vụ thật.
