# Báo cáo bằng chứng A-06

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `815bebb15b565c4a750854b4218a3296c7be2904`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-06 trong docs/implementation/a/slices.md, coveredIds A-RULE-009.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `27 failed, 8 passed, 2 subtests passed in 0.14s`
- Chi tiết các test FAILED kèm thông điệp AssertionError nguyên văn của bước 6:
  - `SUBFAILED(overrides={'source_id': ''}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'cursor': ''}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'run_id': ''}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'fingerprint': ''}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'checkpoint_version': 0}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'revision': 0}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'execution_generation': -1}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'execution_generation': True}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'item_ids': ['i-1']}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'item_ids': ('',)}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'item_ids': ('i-1', 'i-1')}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(overrides={'completeness': 'PARTIAL'}) tests/unit/collection/test_a06_checkpoint.py::CheckpointShapeTests::test_invalid_construction_rejected`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::AdvanceDurabilityTests::test_advance_rejects_item_not_durably_committed`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::AdvanceDurabilityTests::test_durable_ids_must_be_a_collection`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::AdvanceDurabilityTests::test_first_checkpoint_requires_durable_items`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::AdvanceDurabilityTests::test_tampered_proposed_is_rejected`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_VERSION_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_advance_rejects_lineage_change`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_ADAPTER_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_advance_rejects_lineage_change`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_SOURCE_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_advance_rejects_lineage_change`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_SOURCE_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_loader_rejects_other_source_adapter_or_tampering`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_ADAPTER_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_loader_rejects_other_source_adapter_or_tampering`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(code='CHECKPOINT_FINGERPRINT_MISMATCH') tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_loader_rejects_other_source_adapter_or_tampering`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::SemanticsVersionTests::test_old_checkpoint_rejected_by_new_adapter_semantics`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(revision=4) tests/unit/collection/test_a06_checkpoint.py::GenerationFencingTests::test_revision_must_follow_current`: `AssertionError: CheckpointRejected not raised`
  - `SUBFAILED(revision=6) tests/unit/collection/test_a06_checkpoint.py::GenerationFencingTests::test_revision_must_follow_current`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::GenerationFencingTests::test_revision_must_follow_current`: `AssertionError: CheckpointRejected not raised`
  - `FAILED tests/unit/collection/test_a06_checkpoint.py::GenerationFencingTests::test_stale_generation_cannot_advance`: `AssertionError: CheckpointRejected not raised`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection nào (5 test đạt gồm test_checkpoint_declares_required_fields, test_fingerprint_is_deterministic_sha256, test_advance_over_durable_items_returns_proposed, test_same_semantics_loads_across_adapter_revisions, test_same_or_newer_generation_advances; tất cả 10 test FAILED đều là AssertionError do khung chưa cài đặt logic kiểm tra).

## Thay đổi

- 2 tệp mới:
  - `src/source_ingestion/domain/checkpoint.py`: cài đặt bản ghi CollectionCheckpoint thuần stdlib (frozen dataclass) cùng các thực thể và hàm hỗ trợ.
  - `tests/unit/collection/test_a06_checkpoint.py`: bộ kiểm thử đơn vị bao phủ các phản ví dụ và ràng buộc bất biến (coveredIds: A-RULE-009).
- Các API và mã lỗi:
  - `CheckpointCompleteness`: Enum gồm PARTIAL và COMPLETE.
  - `CheckpointRejected`: ngoại lệ fail-closed với mã lỗi `code` và chi tiết `detail`.
  - Các mã lỗi:
    - `CHECKPOINT_INVALID`: cấu trúc không hợp lệ (chuỗi rỗng, số âm, kiểu dữ liệu sai, item_ids lặp hoặc không phải tuple, completeness sai).
    - `CHECKPOINT_FINGERPRINT_MISMATCH`: fingerprint sha256 không khớp nội dung.
    - `CHECKPOINT_SOURCE_MISMATCH`: khác source_id.
    - `CHECKPOINT_ADAPTER_MISMATCH`: khác adapter_type.
    - `CHECKPOINT_VERSION_MISMATCH`: khác checkpoint_version (cursor semantics thay đổi).
    - `CHECKPOINT_STALE_GENERATION`: execution_generation của worker đề xuất nhỏ hơn current.
    - `CHECKPOINT_REVISION_CONFLICT`: revision đề xuất không liền kề (expected current.revision + 1, hoặc revision đầu tiên khác 1).
    - `CHECKPOINT_ITEM_NOT_DURABLE`: đề xuất tiến qua item chưa được commit bền vững trong durable_item_ids.
  - `AdapterCheckpointSemantics`: khai báo ngữ nghĩa cursor của adapter.
  - `CollectionCheckpoint`: bản ghi cursor theo source, gồm 14 trường bất biến.
  - `compute_checkpoint_fingerprint`: tính sha256 trên chuỗi JSON canonical của các trường trừ fingerprint.
  - `seal_checkpoint`: đóng dấu fingerprint lên checkpoint.
  - `ensure_checkpoint_loadable`: kiểm tra checkpoint có thể nạp an toàn bởi adapter hay không.
  - `advance_checkpoint`: kiểm tra và tiến checkpoint chỉ qua item đã commit bền vững.
- Ánh xạ 3 phản ví dụ sang các lớp test:
  - Phản ví dụ 1 (Checkpoint vượt item chưa commit): `AdvanceDurabilityTests`
  - Phản ví dụ 2 (Checkpoint cũ nạp vào adapter mới): `SemanticsVersionTests`
  - Phản ví dụ 3 (Worker generation cũ đẩy checkpoint): `GenerationFencingTests`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider` | 0 | 15 passed, 22 subtests passed in 0.03s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.04s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `item_ids` là các item mà revision này đi qua kể từ revision trước, theo thứ tự adapter.
2. `revision` là expected-revision tăng đúng 1, revision đầu tiên là 1.
3. `execution_generation` bằng hoặc lớn hơn current thì được tiến, nhỏ hơn bị từ chối (`CHECKPOINT_STALE_GENERATION`).
4. `checkpoint_version` khác thì từ chối (`CHECKPOINT_VERSION_MISMATCH`), migration nằm ngoài slice; cùng `checkpoint_version` nhưng khác `adapter_revision` thì được nạp.
5. `fingerprint` là sha256 trên JSON canonical (sort_keys, không khoảng trắng) của mọi trường trừ fingerprint.
6. GIẢ ĐỊNH: `source_revision >= 1` và `recorded_at` chỉ kiểm là chuỗi không rỗng, chưa parse thời gian.
7. Chỉ dùng stdlib, không import controlplane, chưa có persistence cho tới CONV-A-01.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
