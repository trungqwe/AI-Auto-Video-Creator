# Báo cáo bằng chứng A-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4035610fa62c04ebcd7bc774b4a9e4ed68c5ad1a`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-03 trong docs/implementation/a/slices.md; coveredIds: CT-STATE-001, A-RULE-003.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` (chạy trên stub chữ ký đầy đủ với thân cố ý sai)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `34 failed, 11 passed in 0.23s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `SUBFAILED(collection_enabled=True) tests/unit/collection/test_a03_source_lifecycle.py::SourceShapeTests::test_register_records_revision_actor_time_and_initial_status`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, 0, 'policy-r1') != (<SourceStatus.ACTIVE: 'ACTIVE'>, 1, 'policy-r1')`
  - `SUBFAILED(collection_enabled=False) tests/unit/collection/test_a03_source_lifecycle.py::SourceShapeTests::test_register_records_revision_actor_time_and_initial_status`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, 0, 'policy-r1') != (<SourceStatus.DISABLED: 'DISABLED'>, 1, 'policy-r1')`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_active_and_disabled_transition_both_ways`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, 0) != (<SourceStatus.DISABLED: 'DISABLED'>, 'maintenance', 2)`
  - `SUBFAILED(command='enable_active') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_edges_outside_the_state_graph_are_forbidden`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='disable_disabled') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_edges_outside_the_state_graph_are_forbidden`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='restore_active') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_edges_outside_the_state_graph_are_forbidden`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='restore_disabled') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_edges_outside_the_state_graph_are_forbidden`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(previous=<SourceStatus.ACTIVE: 'ACTIVE'>) tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_remove_from_active_or_disabled_creates_tombstone`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, 0) != (<SourceStatus.REMOVED_TOMBSTONE: 'REMOVED_TOMBSTONE'>, <SourceStatus.ACTIVE: 'ACTIVE'>, 2)`
  - `SUBFAILED(previous=<SourceStatus.DISABLED: 'DISABLED'>) tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_remove_from_active_or_disabled_creates_tombstone`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, 0) != (<SourceStatus.REMOVED_TOMBSTONE: 'REMOVED_TOMBSTONE'>, <SourceStatus.DISABLED: 'DISABLED'>, 2)`
  - `SUBFAILED(disallowed='tier') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_restore_falls_back_to_disabled_with_reason_when_policy_disallows`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, 'policy-r1') != (<SourceStatus.DISABLED: 'DISABLED'>, 'RESTORE_POLICY_DISALLOWED', 'policy-r2')`
  - `SUBFAILED(disallowed='source_kind') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_restore_falls_back_to_disabled_with_reason_when_policy_disallows`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, 'policy-r1') != (<SourceStatus.DISABLED: 'DISABLED'>, 'RESTORE_POLICY_DISALLOWED', 'policy-r2')`
  - `SUBFAILED(previous=<SourceStatus.ACTIVE: 'ACTIVE'>) tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_restore_returns_to_status_before_remove_when_policy_allows`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, None, 0) != (<SourceStatus.ACTIVE: 'ACTIVE'>, None, None, 3)`
  - `SUBFAILED(previous=<SourceStatus.DISABLED: 'DISABLED'>) tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_restore_returns_to_status_before_remove_when_policy_allows`: `AssertionError: Tuples differ: (<SourceStatus.ACTIVE: 'ACTIVE'>, None, None, 0) != (<SourceStatus.DISABLED: 'DISABLED'>, None, None, 3)`
  - `SUBFAILED(command='enable') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_tombstone_leaves_only_through_restore`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='disable') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_tombstone_leaves_only_through_restore`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='remove') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_tombstone_leaves_only_through_restore`: `AssertionError: ForbiddenTransitionError not raised`
  - `SUBFAILED(command='update') tests/unit/collection/test_a03_source_lifecycle.py::LifecycleTests::test_tombstone_leaves_only_through_restore`: `AssertionError: ForbiddenTransitionError not raised`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_every_mutation_increments_revision_and_records_actor_time`: `AssertionError: Tuples differ: (0, 'user-a', ...) != (1, 'user-1', ...)`
  - `SUBFAILED(command='update') tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(command='disable') tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(command='enable') tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(command='remove') tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: RevisionConflictError not raised`
  - `SUBFAILED(command='restore') tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: RevisionConflictError not raised`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::RevisionTests::test_stale_expected_revision_raises_shared_conflict_error`: `AssertionError: Tuples differ: ('', 0) != ('fresh', 2)`
  - `SUBFAILED(case='actor') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_mutations_require_actor_and_timezone_aware_time`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='naive_time') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_mutations_require_actor_and_timezone_aware_time`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='source_kind') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_register_checks_source_kind_and_tier_against_policy_values`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='tier') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_register_checks_source_kind_and_tier_against_policy_values`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_register_checks_source_kind_and_tier_against_policy_values`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_update_changes_only_published_metadata`: `AssertionError: Tuples differ: ('T1', frozenset({'tech'}), '', <SourceStatus.ACTIVE: 'ACTIVE'>, ()) != ('T2', frozenset({'ai', 'tech'}), 'checked', <SourceStatus.DISABLED: 'DISABLED'>, (('owner_team', 'news'),))`
  - `SUBFAILED(case='tier') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_update_validates_values_against_supplied_policy`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='admin_key') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_update_validates_values_against_supplied_policy`: `AssertionError: ValueError not raised`
  - `SUBFAILED(case='empty') tests/unit/collection/test_a03_source_lifecycle.py::UpdateAndPolicyTests::test_update_validates_values_against_supplied_policy`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/collection/test_a03_source_lifecycle.py::RetentionTests::test_remove_and_restore_keep_source_record_fields`: `AssertionError: Tuples differ: (None, <SourceStatus.ACTIVE: 'ACTIVE'>) != ('retired', <SourceStatus.ACTIVE: 'ACTIVE'>)`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (3 test PASS ngay ở RED: test_source_is_frozen_dataclass_with_three_statuses, test_module_reuses_shared_conflict_error_and_defines_no_error_class, test_module_hard_codes_no_policy_values; 13 test còn lại FAILED vì sai oracle AssertionError).

## Thay đổi

- `src/source_ingestion/domain/source.py`:
  - `SourceStatus`: StrEnum với 3 trạng thái ACTIVE, DISABLED, REMOVED_TOMBSTONE.
  - `SourcePolicy`: frozen dataclass quản lý tập giá trị cấu hình động (policy_revision, source_kinds, tiers, admin_metadata_keys), không hard-code giá trị trong module.
  - `Source`: aggregate frozen dataclass theo CT-STATE-001 và CT-SRC-001..003.
  - Các hàm nghiệp vụ mutation thuần domain:
    - `register_source`: kiểm tra policy, khởi tạo revision=1, status theo collection_enabled, ghi nhận actor/created_at/updated_at.
    - `update_source_metadata`: kiểm expected revision, cấm trên tombstone, chỉ cho phép cập nhật tier/topics/notes/admin_metadata/bật-tắt, kiểm tra theo policy, tăng revision và cập nhật policy_revision.
    - `enable_source`: kiểm expected revision, chỉ cho phép chuyển từ DISABLED sang ACTIVE, tăng revision.
    - `disable_source`: kiểm expected revision, chỉ cho phép chuyển từ ACTIVE sang DISABLED, lưu lý do (status_reason), tăng revision.
    - `remove_source`: kiểm expected revision, chuyển từ ACTIVE hoặc DISABLED sang REMOVED_TOMBSTONE, lưu previous_status và status_reason, tăng revision.
    - `restore_source`: kiểm expected revision, chỉ cho phép từ REMOVED_TOMBSTONE; phục hồi về previous_status nếu source_kind và tier còn nằm trong policy; nếu không hợp lệ thì chuyển về DISABLED kèm lý do `RESTORE_POLICY_DISALLOWED`.
    - `RESTORE_POLICY_DISALLOWED`: hằng số lý do khi phục hồi không thỏa mãn policy hiện hành.
    - Tái sử dụng `RevisionConflictError` từ `controlplane.domain.concurrency` và `ForbiddenTransitionError` từ `controlplane.domain.statemachine`, không định nghĩa lớp exception riêng.
- `tests/unit/collection/test_a03_source_lifecycle.py`:
  - Docstring module khai báo `coveredIds: CT-STATE-001, A-RULE-003`.
  - 5 lớp kiểm thử, 17 test methods (50 subtests):
    - `SourceShapeTests` (2 test): kiểm Source là frozen dataclass với 3 status hợp lệ; register ghi nhận revision=1, actor, thời gian, previous_status=None.
    - `LifecycleTests` (6 test): kiểm hai chiều ACTIVE↔DISABLED; remove từ ACTIVE/DISABLED sang REMOVED_TOMBSTONE; restore về đúng previous_status khi policy cho phép (loại trừ phản ví dụ 'restore luôn về ACTIVE'); fallback DISABLED kèm RESTORE_POLICY_DISALLOWED khi policy không cho phép; tombstone chỉ rời bằng restore; các cạnh ngoài đồ thị ném ForbiddenTransitionError (loại trừ phản ví dụ 'thiếu cạnh DISABLED→ACTIVE').
    - `RevisionTests` (3 test): mỗi mutation tăng revision đúng 1 và ghi actor/thời điểm; expected revision cũ ném RevisionConflictError đúng revision hiện tại (loại trừ phản ví dụ 'revision cũ ghi đè im lặng'); module tái sử dụng shared conflict error và không định nghĩa lớp lỗi riêng.
    - `UpdateAndPolicyTests` (5 test): update chỉ thay đổi các metadata quản trị được công bố; kiểm tra giá trị update theo policy; register kiểm tra source_kind và tier theo policy (loại trừ phản ví dụ 'source_kind hard-code trong module'); module không chứa chuỗi literal fixture nào; mutation yêu cầu actor không rỗng và timezone-aware datetime.
    - `RetentionTests` (1 test): remove và restore giữ nguyên toàn bộ trường định danh và nội dung của Source record để dữ liệu thu thập luôn có thể truy vết (A-RULE-003).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` | 0 | 17 passed, 50 subtests passed in 0.04s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.03s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. status là nguồn sự thật duy nhất cho bật/tắt thu thập; `collection_enabled` của register/update ánh xạ sang ACTIVE/DISABLED, không có field riêng.
2. 'policy cho phép restore' nghĩa là source_kind và tier của Source còn thuộc SourcePolicy truyền vào, ngược lại về DISABLED với reason `RESTORE_POLICY_DISALLOWED`; restore về DISABLED trước đó đặt status_reason None.
3. Cạnh sai dùng lại `controlplane.domain.statemachine.ForbiddenTransitionError`, input sai dùng `ValueError`, revision cũ dùng `controlplane.domain.concurrency.RevisionConflictError`, không tạo lớp lỗi mới.
4. Thời điểm do caller truyền (timezone-aware), domain không đọc đồng hồ.
5. Revision khởi tạo 1, kiểm expected revision trước mọi kiểm tra khác.
6. Metadata quản trị chỉ nhận key trong `admin_metadata_keys` của policy, lưu tuple sắp xếp để giữ bất biến.
7. Update không có thay đổi nào ném ValueError.
8. `rss_feed`, `web_page`, `T1`, `T2`, `owner_team` chỉ là giá trị fixture trong test.

## Danh sách chờ user (pendingUserCheckpoint)

- MODULE-A-OPEN-001 (tập source_kind thật)
- MODULE-A-OPEN-002 (tiêu chí Tier)
- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
(Không ghi nhận bất kỳ mục nào đã được duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Chưa có idempotency key/receipt/outbox/event SourceRegistered… (thuộc A-08/A-09).
- Canonicalization locator và SSRF thuộc A-04.
- Đăng ký transition vào state machine dùng chung thuộc CONV-A-05.
- Không đổi pyproject.toml/uv.lock.
- Không gọi dịch vụ thật.
