# Báo cáo bằng chứng A-07

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `815bebb15b565c4a750854b4218a3296c7be2904`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-07 trong docs/implementation/a/slices.md; contract CT-SRC-003A, CT-STATE-002A.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `41 failed, 9 passed, 8 subtests passed in 0.21s` (11 test methods failed/subfailed, 3 passed thuộc TransitionTableTests)
- Chi tiết các test FAILED/SUBFAILED kèm AssertionError nguyên văn:
  - `FAILED tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_discovered_moves_to_validating`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1, 1) != ('VALIDATING', <CandidateStatus.VALIDATING: 'VALIDATING'>, 2, 2)`
  - `FAILED tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_rejection_requires_reason`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_tombstone_takes_precedence`: `AssertionError: <CandidateStatus.DISCOVERED: 'DISCOVERED'> != <CandidateStatus.BLOCKED_TOMBSTONE: 'BLOCKED_TOMBSTONE'>`
  - `SUBFAILED(expected='READY_FOR_REGISTRATION') tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_validation_outcomes`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1) != ('READY_FOR_REGISTRATION', <CandidateStatus.READY_FOR_REGISTRATION: 'READY_FOR_REGISTRATION'>, 2)`
  - `SUBFAILED(expected='MATCHED_EXISTING') tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_validation_outcomes`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1) != ('MATCHED_EXISTING', <CandidateStatus.MATCHED_EXISTING: 'MATCHED_EXISTING'>, 2)`
  - `SUBFAILED(expected='BLOCKED_TOMBSTONE') tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_validation_outcomes`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1) != ('BLOCKED_TOMBSTONE', <CandidateStatus.BLOCKED_TOMBSTONE: 'BLOCKED_TOMBSTONE'>, 2)`
  - `SUBFAILED(expected='REJECTED') tests/unit/collection/test_a07_source_candidate.py::ValidationTests::test_validation_outcomes`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1) != ('REJECTED', <CandidateStatus.REJECTED: 'REJECTED'>, 2)`
  - `FAILED tests/unit/collection/test_a07_source_candidate.py::RegistrationTests::test_inv015_removed_source_rediscovered_is_blocked_not_registered`: `AssertionError: <CandidateStatus.DISCOVERED: 'DISCOVERED'> != <CandidateStatus.BLOCKED_TOMBSTONE: 'BLOCKED_TOMBSTONE'>`
  - `SUBFAILED(policy='...') tests/unit/collection/test_a07_source_candidate.py::RegistrationTests::test_missing_policy_keeps_ready_with_waiting_policy`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', 1) != ('WAITING_POLICY', 1)`
  - `FAILED tests/unit/collection/test_a07_source_candidate.py::RegistrationTests::test_ready_registers_with_policy_classification`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1, 'discovery-worker') != ('REGISTERED', <CandidateStatus.REGISTERED: 'REGISTERED'>, 2, 'registrar')`
  - `SUBFAILED(...) tests/unit/collection/test_a07_source_candidate.py::RegistrationTests::test_ready_terminal_outcomes_do_not_register`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', <CandidateStatus.DISCOVERED: 'DISCOVERED'>, 1) != ('MATCHED_EXISTING', <CandidateStatus.MATCHED_EXISTING: 'MATCHED_EXISTING'>, 2)`
  - `SUBFAILED(...) tests/unit/collection/test_a07_source_candidate.py::ConcurrencyAndTerminalTests::test_out_of_order_transitions_are_rejected`: `AssertionError: CandidateTransitionError not raised`
  - `SUBFAILED(...) tests/unit/collection/test_a07_source_candidate.py::ConcurrencyAndTerminalTests::test_stale_expected_revision_returns_conflict_without_state_change`: `AssertionError: Tuples differ: ('UNIMPLEMENTED', 1) != ('REVISION_CONFLICT', 1)`
  - `SUBFAILED(...) tests/unit/collection/test_a07_source_candidate.py::ConcurrencyAndTerminalTests::test_terminal_candidates_are_not_reopened`: `AssertionError: CandidateTransitionError not raised`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection (RED do stub trả code 'UNIMPLEMENTED' và resolve_identity trả NO_MATCH).

## Thay đổi

- Tệp `src/source_ingestion/domain/source_candidate.py` định nghĩa các public symbols:
  - `CandidateStatus`
  - `TERMINAL_STATUSES`
  - `ALLOWED_TRANSITIONS`
  - `WAITING_POLICY`
  - `REVISION_CONFLICT`
  - `CandidateTransitionError`
  - `IdentityMatchKind`
  - `IdentityMatch`
  - `NO_MATCH`
  - `RegistrationPolicy`
  - `SourceCandidate`
  - `CandidateDecision`
  - `discover_candidate`
  - `begin_validation`
  - `complete_validation`
  - `register_candidate`
  - `resolve_identity`
- Tệp kiểm thử `tests/unit/collection/test_a07_source_candidate.py` (4 class, 14 test) với ánh xạ yêu cầu:
  - Bảng chuyển trạng thái → `TransitionTableTests`, `ValidationTests`, `RegistrationTests`
  - `WAITING_POLICY` giữ nguyên `READY_FOR_REGISTRATION` → `test_missing_policy_keeps_ready_with_waiting_policy`
  - `REVISION_CONFLICT` trả candidate nguyên vẹn → `test_stale_expected_revision_returns_conflict_without_state_change`
  - Terminal candidate không mở lại → `test_terminal_candidates_are_not_reopened`
  - Tombstone ưu tiên cao nhất → `test_tombstone_takes_precedence`, `test_inv015_removed_source_rediscovered_is_blocked_not_registered`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider` | 0 | 14 passed, 44 subtests passed in 0.03s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.04s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. `REVISION_CONFLICT` và `WAITING_POLICY` trả `CandidateDecision` có code và giữ nguyên object candidate (không tăng revision, không phát terminal event) theo CT-SRC-003A, thay vì ném RevisionConflictError.
2. Kiểm expected revision trước, rồi kiểm trạng thái; candidate terminal ném `CandidateTransitionError` — replay idempotent theo receipt thuộc A-10.
3. Ưu tiên tombstone > source hiện có > validation/policy (A-RULE-002, TST-INT-INV-015 mức domain).
4. Identity so khớp chính xác canonical_locator do caller chuẩn hoá (A-04), domain không import slice song song.
5. Policy thiếu source kind/topic/Tier → `WAITING_POLICY`, không lấy từ classification candidate và không mặc định.
6. Chỉ stdlib, không thêm thư viện ngoài.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Tier/discovery policy được duyệt trước khi bật auto-registration production.

## Giới hạn

- Chỉ mức domain; atomic recheck, receipt, outbox và race thuộc A-10 (TST-SRC-RACE-001..004).
- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
