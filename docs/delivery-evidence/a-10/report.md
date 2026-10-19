# Báo cáo bằng chứng A-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `3529edc34d9444d9629a3191c34dc07ab72a2d07`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS và slice A-10 trong `docs/implementation/a/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider`
- Trạng thái mô phỏng RED: test hoàn chỉnh, `candidate_registration.py` là stub.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `27 failed, 2 passed in 0.52s`
- Test FAILED tiêu biểu:
  - `FAILED tests/integration/collection/test_a10_candidate_registration.py::EvaluateTests::test_new_locator_becomes_ready_with_receipt_and_discovered_event` (AssertionError: None is not an instance of <class 'source_ingestion.application.candidate_registration.CandidateCommandResult'>)
  - `FAILED tests/integration/collection/test_a10_candidate_registration.py::PolicyRevisionTests::test_production_default_keeps_auto_registration_not_ready` (AssertionError: Tuples differ: ('UNIMPLEMENTED', 'UNIMPLEMENTED') != ('NOT_READY', 'READY'))
  - `FAILED tests/integration/collection/test_a10_candidate_registration.py::SafetyAndLayerTests::test_module_reuses_controlplane_types_and_respects_layers` (AssertionError: False is not true)
- Xác nhận: 0 error, không có ImportError, ModuleNotFoundError hay collection error; lỗi RED hoàn toàn là AssertionError sai oracle.

## Thay đổi

- `src/source_ingestion/application/candidate_registration.py`: triển khai lớp `CandidateRegistrationHandler` với hai phương thức lệnh `evaluate_source_candidate` và `register_source_candidate`, hàm chính sách mặc định `no_tier_policy`, hàm tính mức độ sẵn sàng `auto_registration_readiness`, các ngoại lệ `CandidateNotFoundError`, `PolicyRevisionMismatchError`, DTO `CandidateCommandResult`, và protocol `CandidateUnitOfWork`.
- `tests/integration/collection/test_a10_candidate_registration.py`: bộ kiểm thử tích hợp gồm 23 test case chia thành 7 nhóm (`CandidateTestCase`, `EvaluateTests`, `RaceExistingSourceTests`, `RaceRemoveTests`, `PolicyWaitingTests`, `PolicyRevisionTests`, `ReplayAtomicityTests`, `SafetyAndLayerTests`), docstring khai báo coveredIds `TST-SRC-RACE-001..004`, `TST-INT-INV-015`, `A-RULE-002`.
- `docs/delivery-evidence/a-10/report.md`: báo cáo bằng chứng thực thi chi tiết, môi trường, RED, GREEN, ánh xạ kiểm thử, phản ví dụ, quyết định D8, pendingUserCheckpoint và giới hạn.

## Ánh xạ yêu cầu → test

| Yêu cầu | Test tương ứng |
|---|---|
| RACE-001: Nguồn được đăng ký trước thì candidate trùng khớp existing source | `test_race_001_source_registered_first_matches_existing` |
| RACE-002: Hai thứ tự commit tuần tự giữa register và remove | `test_race_002_register_wins_then_remove_keeps_tombstone`, `test_race_002_remove_wins_blocks_registration_and_terminal_stays_closed` |
| RACE-003: Thiếu policy hoặc policy không đầy đủ/cấm, revision cũ xung đột | `test_race_003_missing_policy_waits_without_receipt_or_resolved`, `test_race_003_incomplete_policies_never_register`, `test_race_003_forbidding_policy_rejects_without_source`, `test_race_003_stale_revision_conflict_changes_nothing`, `test_changed_policy_revision_is_not_silently_replaced` |
| RACE-004: Mất ACK gửi lại trả receipt đã commit không tạo nguồn trùng | `test_race_004_lost_ack_retry_returns_committed_receipt` |
| INV-015: Tái khám phá locator đã tombstone bị chặn (BLOCKED_TOMBSTONE) | `test_inv_015_rediscovery_of_removed_source_is_blocked` |
| A-RULE-002: Không trùng canonical locator trong workspace | `test_two_ready_candidates_for_same_locator_create_one_source`, các test trong `EvaluateTests` |
| Atomic rollback: Lỗi outbox rollback toàn bộ candidate, source và receipt | `test_outbox_failure_rolls_back_candidate_source_and_receipt` |
| Identity rechecked: Kiểm tra lại identity ngay bên trong registration UoW | `test_identity_is_rechecked_inside_the_registration_uow` |
| Auto-registration mặc định NOT_READY khi chưa có Tier policy | `test_production_default_keeps_auto_registration_not_ready` |
| Event an toàn: Event chỉ mang ref, revision, disposition và reason cố định | `test_events_carry_only_refs_revision_disposition_and_reason` |

### Phản ví dụ bị loại trừ

| Phản ví dụ | Kết quả ngăn chặn | Test chứng minh |
|---|---|---|
| READY đăng ký sau khi nguồn đã tombstone | Chuyển sang `BLOCKED_TOMBSTONE`, không tạo Source | `test_race_002_remove_wins_blocks_registration_and_terminal_stays_closed` |
| Mất ACK gửi lại tạo Source thứ hai | Replay trả lại `CommandReceipt` đã commit, giữ nguyên 1 Source duy nhất | `test_race_004_lost_ack_retry_returns_committed_receipt` |
| Thiếu policy vẫn REGISTERED | Giữ trạng thái `WAITING_POLICY`, không ghi Source/receipt | `test_race_003_missing_policy_waits_without_receipt_or_resolved`, `test_race_003_incomplete_policies_never_register` |
| Phát Resolved khi còn WAITING_POLICY | Không phát `SourceCandidateResolved` khi chưa đạt trạng thái terminal | `test_race_003_missing_policy_waits_without_receipt_or_resolved`, `test_production_default_keeps_auto_registration_not_ready` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider | 0 | 23 passed, 14 subtests passed in 0.12s |
| 2 | git diff --check | 0 | passed (clean, no output) |
| 3 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider | 0 | 23 passed, 14 subtests passed in 0.09s |

## Quyết định mặc định (D8)

1. Evaluate chạy discover, validating, rồi READY/MATCHED_EXISTING/BLOCKED_TOMBSTONE trong một UoW nên candidate ở revision 3; SourceCandidateDiscovered mang revision 1, Resolved chỉ phát khi terminal.
2. WAITING_POLICY và REVISION_CONFLICT không ghi receipt, event hay state, nên retry cùng key sau khi có policy được xử lý như lệnh mới.
3. Retry cùng key trả receipt đã commit và candidate hiện hành theo ref trong receipt (CommandReceipt không lưu disposition); candidate terminal không mở lại nên disposition terminal trùng bản đã commit, riêng READY có thể đã chuyển trạng thái sau đó (giới hạn đã biết).
4. policy_revision đầu vào khác policy hiện hành thì ném PolicyRevisionMismatchError, không dùng policy cũ.
5. Source tạo từ candidate lấy kind/Tier/topics từ RegistrationPolicy, name là host của canonical locator, collection_enabled=True, phát thêm SourceRegistered.
6. reason trong event là mã cố định (IDENTITY_MATCHES_SOURCE, IDENTITY_MATCHES_TOMBSTONE, POLICY_FORBIDS, REGISTERED_BY_POLICY, CANDIDATE_DISCOVERED), không chép policy.reason, evidence hay locator.
7. Provider mặc định no_tier_policy trả None nên auto-registration production giữ NOT_READY tới khi Tier policy được duyệt.
8. Race mô phỏng tuần tự; khóa unique identity của SourceRepository (DuplicateSourceIdentityError) là chốt cuối khi hai UoW chồng nhau, PostgreSQL chờ CONV-A-01.
9. Không thêm thư viện.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- Tier/discovery policy được duyệt trước khi bật auto-registration production
- CONV-A-01
- CONV-A-09

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
- Chưa có PostgreSQL.
