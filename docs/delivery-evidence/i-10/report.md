# Báo cáo bằng chứng I-10

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `12409080b2b686d8e7442db0c4e2ecc6f219374c`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-10 trong `docs/implementation/i/slices.md`, CT-STO-009, INV-016, binding `g-c-i-completion`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` (chạy với stub ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `14 failed, 4 passed in 0.12s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_cloud_object_missing`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.CLOUD_OBJECT_MISSING: 'CLOUD_OBJECT_MISSING'>, ref='00000000-0000-4000-8000-000000000080', action=None), ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None))`
  - `SUBFAILED[missing location] tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_completion_without_verified_output`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None),)`
  - `SUBFAILED[different hash] tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_completion_without_verified_output`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None),)`
  - `SUBFAILED[different version] tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_completion_without_verified_output`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None),)`
  - `SUBFAILED[missing version in snapshot] tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_completion_without_verified_output`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None),)`
  - `SUBFAILED[location points to other version] tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_completion_without_verified_output`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None),)`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_duplicate_provider_object_is_reported_not_deleted`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.DUPLICATE_PROVIDER_OBJECT: 'DUPLICATE_PROVIDER_OBJECT'>, ref='drive://obj/out-1', action=None),)`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_hash_mismatch`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, ref='00000000-0000-4000-8000-000000000070', action=None), ReconcileFinding(code=<ReconcileCode.HASH_MISMATCH: 'HASH_MISMATCH'>, ref='00000000-0000-4000-8000-000000000080', action=None))`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_journal_generation_mismatch`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.JOURNAL_GENERATION_MISMATCH: 'JOURNAL_GENERATION_MISMATCH'>, ref='op-1', action=None),)`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_only_stale_finding_carries_reissue_action`: `AssertionError: Items in the second set but not the first: <ReconcileCode.DUPLICATE_PROVIDER_OBJECT: 'DUPLICATE_PROVIDER_OBJECT'>, <ReconcileCode.CLOUD_OBJECT_MISSING: 'CLOUD_OBJECT_MISSING'>, <ReconcileCode.ORPHAN_PROVIDER_OBJECT: 'ORPHAN_PROVIDER_OBJECT'>, <ReconcileCode.HASH_MISMATCH: 'HASH_MISMATCH'>, <ReconcileCode.STALE_EPOCH_ENTRY: 'STALE_EPOCH_ENTRY'>, <ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT: 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'>, <ReconcileCode.JOURNAL_GENERATION_MISMATCH: 'JOURNAL_GENERATION_MISMATCH'>`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_orphan_provider_object`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.ORPHAN_PROVIDER_OBJECT: 'ORPHAN_PROVIDER_OBJECT'>, ref='drive://obj/orphan', action=None),)`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_pure_and_deterministic`: `AssertionError: () is not true`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_stale_epoch_entry_other_generation_is_only_stale`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.STALE_EPOCH_ENTRY: 'STALE_EPOCH_ENTRY'>, ref='op-1', action=<ReconcileAction.REISSUE_UNDER_NEW_EPOCH: 'REISSUE_UNDER_NEW_EPOCH'>),)`
  - `FAILED tests/unit/storage/test_storage_reconciliation.py::ReconcileTests::test_stale_epoch_entry_same_generation_is_stale`: `AssertionError: Tuples differ: () != (ReconcileFinding(code=<ReconcileCode.STALE_EPOCH_ENTRY: 'STALE_EPOCH_ENTRY'>, ref='op-1', action=<ReconcileAction.REISSUE_UNDER_NEW_EPOCH: 'REISSUE_UNDER_NEW_EPOCH'>),)`
- Xác nhận: stub trả () nên mọi FAILED là AssertionError; không có ImportError/ModuleNotFoundError/NameError/TypeError/AttributeError/lỗi collection.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `13 passed, 10 subtests passed in 0.04s`

## Thay đổi

- `src/controlplane/application/storage_meta/reconciliation.py`:
  - Định nghĩa enum `ReconcileCode` gồm đúng 7 mã đối soát: `CLOUD_OBJECT_MISSING`, `HASH_MISMATCH`, `ORPHAN_PROVIDER_OBJECT`, `DUPLICATE_PROVIDER_OBJECT`, `JOURNAL_GENERATION_MISMATCH`, `STALE_EPOCH_ENTRY`, `COMPLETION_WITHOUT_VERIFIED_OUTPUT`.
  - Định nghĩa enum `ReconcileAction` gồm đúng 1 hành động tái phát hành: `REISSUE_UNDER_NEW_EPOCH`.
  - Định nghĩa các dataclass frozen: `VersionRecord`, `CloudLocationRecord`, `CloudObjectObservation`, `JournalEntry`, `CompletionRecord`, `ReconcileSnapshot`, `ReconcileFinding`.
  - Hàm trợ giúp nội bộ:
    - `_matches(version, observed)`: so sánh đối chiếu quan sát cloud với version theo `observed_sha256` và `observed_size_bytes`.
    - `_output_verified(completion, versions, locations, observed)`: kiểm tra tính hợp lệ và toàn vẹn của đầu ra video hoàn thành với vị trí cloud và mọi quan sát tương ứng.
  - Hàm thuần `reconcile(snapshot: ReconcileSnapshot) -> tuple[ReconcileFinding, ...]`:
    - Quy tắc `CLOUD_OBJECT_MISSING`: đối soát vị trí đám mây trong `snapshot.cloud_locations` không có quan sát nào trong `snapshot.cloud_objects` (ref: `location_id`).
    - Quy tắc `HASH_MISMATCH`: đối soát vị trí đám mây có quan sát nhưng `observed_sha256` hoặc `observed_size_bytes` không khớp với `VersionRecord` (ref: `location_id`).
    - Quy tắc `ORPHAN_PROVIDER_OBJECT`: đối soát đối tượng đám mây được quan sát nhưng không được bất kỳ `CloudLocationRecord` nào tham chiếu (ref: `provider_object_ref`).
    - Quy tắc `DUPLICATE_PROVIDER_OBJECT`: đối soát `provider_object_ref` xuất hiện nhiều hơn 1 lần trong `cloud_locations` hoặc nhiều hơn 1 lần trong `cloud_objects` (ref: `provider_object_ref`). Không xoá đối tượng, chỉ báo cáo.
    - Quy tắc `STALE_EPOCH_ENTRY` (INV-016): mọi journal entry có `recovery_epoch` khác với `current_recovery_epoch` đều bị coi là stale bất kể generation trùng hay khác (ref: `operation_key`), luôn kèm hành động `REISSUE_UNDER_NEW_EPOCH`.
    - Quy tắc `JOURNAL_GENERATION_MISMATCH`: journal entry thuộc epoch hiện hành nhưng `generation` không khớp với `snapshot.stage_generations` (hoặc thiếu key trong stage generations) (ref: `operation_key`).
    - Quy tắc `COMPLETION_WITHOUT_VERIFIED_OUTPUT`: hoàn thành video trong `snapshot.completions` không có vị trí hợp lệ hoặc không có đối tượng đám mây được xác minh toàn vẹn (ref: `video_job_id`).
    - Sắp xếp ổn định theo `(code.value, ref, action.value)`.
    - Không mutation, không xoá, không cấp grant, không I/O, không gọi đồng hồ hay ngẫu nhiên.
  - `__all__` xuất khẩu đúng 10 biểu tượng công khai theo thứ tự bảng chữ cái: `CloudLocationRecord`, `CloudObjectObservation`, `CompletionRecord`, `JournalEntry`, `ReconcileAction`, `ReconcileCode`, `ReconcileFinding`, `ReconcileSnapshot`, `VersionRecord`, `reconcile`.
- `tests/unit/storage/test_storage_reconciliation.py`:
  - 13 bài kiểm thử unittest toàn diện:
    1. `test_consistent_snapshot_returns_empty_tuple`: snapshot nhất quán không lệch trả về tuple rỗng.
    2. `test_cloud_object_missing`: thiếu đối tượng đám mây phát hiện `CLOUD_OBJECT_MISSING` và `COMPLETION_WITHOUT_VERIFIED_OUTPUT`.
    3. `test_hash_mismatch`: sai hash hoặc size đối tượng phát hiện `HASH_MISMATCH` và `COMPLETION_WITHOUT_VERIFIED_OUTPUT`.
    4. `test_orphan_provider_object`: đối tượng không được tham chiếu phát hiện `ORPHAN_PROVIDER_OBJECT`.
    5. `test_duplicate_provider_object_is_reported_not_deleted`: đối tượng trùng tham chiếu hoặc trùng quan sát phát hiện `DUPLICATE_PROVIDER_OBJECT`, không xoá và không làm thay đổi snapshot.
    6. `test_journal_generation_mismatch`: lệch generation hoặc thiếu key trong stage generations phát hiện `JOURNAL_GENERATION_MISMATCH`.
    7. `test_stale_epoch_entry_same_generation_is_stale`: epoch cũ cùng generation vẫn bị coi là stale theo INV-016, kèm hành động `REISSUE_UNDER_NEW_EPOCH` và không kèm `JOURNAL_GENERATION_MISMATCH`.
    8. `test_stale_epoch_entry_other_generation_is_only_stale`: epoch cũ khác generation vẫn chỉ báo `STALE_EPOCH_ENTRY`.
    9. `test_completion_without_verified_output`: kiểm tra 5 biến thể thiếu đối tượng/sai hash/sai version/thiếu version trong snapshot/trỏ sai version đều phát hiện `COMPLETION_WITHOUT_VERIFIED_OUTPUT`.
    10. `test_only_stale_finding_carries_reissue_action`: kiểm tra đầy đủ cả 7 loại mã finding; chỉ có `STALE_EPOCH_ENTRY` mang action `REISSUE_UNDER_NEW_EPOCH`.
    11. `test_result_is_sorted_and_input_order_independent`: kết quả được sắp xếp chuẩn xác và không phụ thuộc vào thứ tự phần tử đầu vào snapshot.
    12. `test_pure_and_deterministic`: tính chất thuần túy và đơn định khi gọi nhiều lần cho cùng kết quả và không làm thay đổi đối tượng đầu vào.
    13. `test_finding_is_frozen`: tính bất biến của `ReconcileFinding` ngăn chặn việc gán lại thuộc tính.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` (RED) | 1 | 14 failed, 4 passed in 0.12s |
| 2 | `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` (GREEN) | 0 | 13 passed, 10 subtests passed in 0.04s |
| 3 | `python -c "import pathlib; fs=['src/controlplane/application/storage_meta/reconciliation.py','tests/unit/storage/test_storage_reconciliation.py']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; print('OK')"` | 0 | OK (UTF-8 không BOM, LF, không trailing whitespace) |
| 4 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: epoch so bằng str() theo D8-I-04;
2. GIẢ ĐỊNH: location trỏ version không có trong snapshot thì không báo HASH_MISMATCH vì không có mã tương ứng;
3. GIẢ ĐỊNH: observed_sha256/observed_size_bytes None hoặc khác kỳ vọng được coi là lệch hash;
4. GIẢ ĐỊNH: DUPLICATE_PROVIDER_OBJECT khi một provider_object_ref có >1 cloud location hoặc >1 quan sát;
5. GIẢ ĐỊNH: completion được coi verified khi location đúng location_id, cùng artifact_version_id, version.content_sha256 == output_sha256 và mọi quan sát của object khớp hash/size version;
6. GIẢ ĐỊNH: thiếu key trong stage_generations coi là lệch generation;
7. GIẢ ĐỊNH: finding được dedupe và không có field detail.

## Danh sách chờ user (pendingUserCheckpoint)

- Không phát sinh mục chờ user mới; không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa __init__.py, statemachine, verification.py, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib.
- Không gọi dịch vụ thật (Google Drive, OAuth, Cloud Object Storage thật).
- Không tạo conftest.py hay __init__.py trong tests/.
- Không thêm mutation đầu vào, không xoá, không cấp grant, không I/O, không gọi đồng hồ hay ngẫu nhiên trong reconcile.
- Chỉ sửa đúng 3 owned paths được phân quyền:
  - `src/controlplane/application/storage_meta/reconciliation.py`
  - `tests/unit/storage/test_storage_reconciliation.py`
  - `docs/delivery-evidence/i-10/report.md`
