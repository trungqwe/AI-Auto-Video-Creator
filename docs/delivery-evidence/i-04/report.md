# Báo cáo bằng chứng I-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `68e2ae94f4aafb49345a02583208516271e7e05e`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-04 trong `docs/implementation/i/slices.md`, binding `docs/parallel-delivery/bindings/i-artifact-version.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `40 failed, 3 passed in 0.40s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `SUBFAILED(grant_ref='') tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_empty_grant_is_rejected`: `AssertionError: PermissionError not raised`
  - `SUBFAILED(grant_ref='   ') tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_empty_grant_is_rejected`: `AssertionError: PermissionError not raised`
  - `SUBFAILED(grant_ref=None) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_empty_grant_is_rejected`: `AssertionError: PermissionError not raised`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_empty_grant_is_rejected`: `AssertionError: Lists differ: ['reserve', 'upload:obj-1', 'save:PREPARED'...] != []`
  - `SUBFAILED(overrides={'content_sha256': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'content_sha256': 'abc'}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'size_bytes': -1}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'size_bytes': True}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'operation_key': ''}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'artifact_version_id': ' '}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'namespace_ref': ''}) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_invalid_input_is_rejected_before_any_side_effect`: `AssertionError: Lists differ: ['reserve', 'upload:obj-1', 'save:PREPARED'...] != []`
  - `SUBFAILED(source_verified=False) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_unverified_source_is_rejected`: `AssertionError: PermissionError not raised`
  - `SUBFAILED(source_verified=None) tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_unverified_source_is_rejected`: `AssertionError: PermissionError not raised`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::GuardTests::test_unverified_source_is_rejected`: `AssertionError: Lists differ: ['reserve', 'upload:obj-1', 'save:PREPARED'...] != []`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_receipt_prepared_is_saved_before_upload`: `AssertionError: Lists differ: ['reserve', 'upload:obj-1', 'save:PREPARED'] != ['reserve', 'save:PREPARED', 'upload:obj-1', 'lookup:obj-1', 'save:VERIFIED']`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_retry_after_verified_does_not_upload_again`: `AssertionError: PersistResult(operation_key='op-1', object_id='obj-2'...) != PersistResult(operation_key='op-1', object_id='obj-1'...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_retry_same_key_reuses_object_id_after_timeout`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(overrides={'content_sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}) tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_same_key_different_content_raises_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'size_bytes': 2049}) tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_same_key_different_content_raises_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(overrides={'artifact_version_id': 'av-2'}) tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_same_key_different_content_raises_value_error`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_same_key_different_content_raises_value_error`: `AssertionError: Lists differ: ['reserve', 'upload:obj-2', 'save:PREPARED'...] != []`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::OrderingAndIdempotencyTests::test_verified_result_carries_lookup_evidence`: `AssertionError: PersistResult(... verification_evidence_ref='stub-evidence') != PersistResult(... verification_evidence_ref='evidence://lookup/obj-1')`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::TimeoutTests::test_lookup_timeout_keeps_outcome_unknown`: `AssertionError: PersistResult(... state=<ArtifactLocationState.VERIFIED: 'VERIFIED'>...) != PersistResult(... state=<ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::TimeoutTests::test_reconcile_after_timeout_finds_exactly_one_object`: `AssertionError: PersistResult(operation_key='op-1', object_id=''...) != PersistResult(operation_key='op-1', object_id='obj-1'...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::TimeoutTests::test_timeout_marks_receipt_outcome_unknown_without_new_id`: `AssertionError: PersistResult(... state=<ArtifactLocationState.VERIFIED: 'VERIFIED'>...) != PersistResult(... state=<ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::TimeoutTests::test_upload_that_never_landed_reconciles_to_missing_then_retry_reuses_id`: `AssertionError: PersistResult(operation_key='op-1', object_id=''...) != PersistResult(operation_key='op-1', object_id='obj-1'...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_already_exists_with_matching_object_is_verified_without_new_object`: `AssertionError: Lists differ: ['reserve', 'upload:obj-1', 'save:PREPARED'] != ['reserve', 'save:PREPARED', 'upload:obj-1', 'lookup:obj-1', 'save:VERIFIED']`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_already_exists_with_other_content_is_corrupt_and_not_overwritten`: `AssertionError: PersistResult(... state=<ArtifactLocationState.VERIFIED: 'VERIFIED'>...) != PersistResult(... state=<ArtifactLocationState.CORRUPT: 'CORRUPT'>...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_decision_uses_evaluate_integrity_from_i03`: `AssertionError: Expected 'evaluate_integrity' to have been called.`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_lookup_without_hash_is_not_verified`: `AssertionError: PersistResult(... state=<ArtifactLocationState.VERIFIED: 'VERIFIED'>...) != PersistResult(... state=<ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>...)`
  - `SUBFAILED(case='absent') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `SUBFAILED(case='no hash') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `SUBFAILED(case='presence unknown') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `SUBFAILED(case='blank evidence') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `SUBFAILED(case='hash mismatch') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `SUBFAILED(case='size mismatch') tests/unit/storage/test_storage_cloud_persist.py::VerifyTests::test_only_verified_observation_carries_evidence`: `AssertionError: Expected 'lookup' to be called once. Called 0 times.`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::ReconcileTests::test_reconcile_looks_up_stored_object_id_only`: `AssertionError: PersistResult(operation_key='op-1', object_id=''...) != PersistResult(operation_key='op-1', object_id='obj-9'...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::ReconcileTests::test_reconcile_object_gone_marks_missing`: `AssertionError: PersistResult(operation_key='op-1', object_id=''...) != PersistResult(operation_key='op-1', object_id='obj-9'...)`
  - `FAILED tests/unit/storage/test_storage_cloud_persist.py::ReconcileTests::test_unknown_operation_key_raises_lookup_error`: `AssertionError: LookupError not raised`
- Xác nhận: Lớp stub cố ý tin response upload và lưu receipt sau upload. Toàn bộ lỗi FAILED/SUBFAILED đều là AssertionError từ stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError, IndexError hay lỗi collection (các test frozen receipt/result và different keys PASS).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `22 passed, 21 subtests passed in 0.05s`

## Thay đổi

- `src/controlplane/application/storage_meta/cloud_persist.py`:
  - Định nghĩa ngoại lệ `ObjectAlreadyExistsError` khi Cloud trả mã lỗi 409 đối với object_id đã tồn tại.
  - Định nghĩa enum `UploadReceiptState` gồm 5 trạng thái: `PREPARED`, `VERIFIED`, `CORRUPT`, `MISSING`, `OUTCOME_UNKNOWN`.
  - Định nghĩa dataclass frozen `UploadReceipt` (các trường `operation_key`, `artifact_version_id`, `content_sha256`, `size_bytes`, `object_id`, `state`, `verification_evidence_ref`).
  - Định nghĩa dataclass frozen `PersistResult` (các trường `operation_key`, `object_id`, `state`, `verification_evidence_ref`).
  - Định nghĩa các protocol `CloudObjectPort` (gồm `reserve_object_id(namespace_ref) -> str`, `upload(object_id, artifact_version_id, content_sha256, size_bytes) -> None`, `lookup(object_id) -> IntegrityObservation`) và `UploadReceiptPort` (gồm `get(operation_key) -> UploadReceipt | None`, `save(receipt: UploadReceipt) -> None`).
  - Hàm trợ giúp nội bộ `_require_text(value, name) -> str` kiểm tra chuỗi không rỗng.
  - Lớp `PersistArtifactToCloud`:
    - Khởi tạo với `CloudObjectPort` và `UploadReceiptPort`.
    - `execute`: Từ chối khi `source_verified` không phải True hoặc `grant_ref` rỗng (báo lỗi `PermissionError` trước mọi tác vụ phụ); kiểm tra hợp lệ các tham số đầu vào và định dạng sha256/size; lưu receipt ở trạng thái `PREPARED` trước khi thực hiện upload; khi retry cùng `operation_key` kiểm tra trùng khớp nội dung (khác nội dung báo lỗi `ValueError`), nếu đã `VERIFIED` thì trả kết quả cũ không upload lại; tái sử dụng `object_id` đã cấp trước; xử lý `TimeoutError` bằng cách cập nhật receipt sang `OUTCOME_UNKNOWN`; bắt `ObjectAlreadyExistsError` (mã 409); luôn gọi `lookup` sau upload và xác minh tính toàn vẹn qua hàm `evaluate_integrity` của I-03; chỉ kết quả `VERIFIED` mới có `verification_evidence_ref`.
    - `reconcile`: Tra cứu receipt theo `operation_key` (nếu không có báo lỗi `LookupError`), sau đó chỉ tra cứu cloud theo đúng `object_id` đã lưu trong receipt để xác minh tính toàn vẹn (không reserve ID mới, không upload).
- `tests/unit/storage/test_storage_cloud_persist.py`:
  - Tạo fake port in-memory: `FakeCloud` (hỗ trợ ghi nhận chuỗi lời gọi, đếm số ID reserved, mô phỏng timeout trước/sau lưu trữ, timeout lookup, ẩn hash) và `FakeReceipts` (lưu trữ và ghi nhận thứ tự lưu receipt).
  - 5 lớp kiểm thử đơn vị:
    - `GuardTests`: Kiểm tra từ chối khi `source_verified` sai/None, `grant_ref` rỗng/None/khoảng trắng, và các trường đầu vào sai định dạng trước mọi tác vụ phụ (calls rỗng).
    - `OrderingAndIdempotencyTests`: Kiểm tra receipt `PREPARED` được lưu trước upload (thứ tự lời gọi chuẩn `HAPPY_CALLS`), kết quả `VERIFIED` mang evidence, retry sau `VERIFIED` không upload lại, retry sau timeout dùng lại `object_id`, cùng key khác nội dung báo `ValueError`, khác key nhận object khác nhau.
    - `TimeoutTests`: Upload timeout đánh dấu `OUTCOME_UNKNOWN` không tạo ID mới, reconcile sau timeout tìm thấy đúng 1 object duy nhất, upload chưa lưu reconcile sang `MISSING` rồi retry dùng lại ID cũ, lookup timeout giữ nguyên `OUTCOME_UNKNOWN`.
    - `VerifyTests`: Mã lỗi 409 khớp nội dung xác minh thành `VERIFIED` đúng 1 object, 409 khác nội dung thành `CORRUPT` không ghi đè, lookup thiếu hash không thành `VERIFIED`, quyết định đi qua `evaluate_integrity` của I-03, kiểm tra bảng quan sát: chỉ quan sát `VERIFIED` mới mang `evidence_ref`.
    - `ReconcileTests`: Key chưa có receipt báo `LookupError`, reconcile chỉ lookup theo `object_id` trong receipt, object biến mất đánh dấu `MISSING`, `UploadReceipt` và `PersistResult` đều là dataclass frozen bất biến.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` (RED) | 1 | 40 failed, 3 passed in 0.40s |
| 2 | `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` (GREEN) | 0 | 22 passed, 21 subtests passed in 0.05s |
| 3 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 4 | `python -c "import pathlib; fs=['src/controlplane/application/storage_meta/cloud_persist.py','tests/unit/storage/test_storage_cloud_persist.py','docs/delivery-evidence/i-04/report.md']; bad=[(f,i) for f in fs for i,l in enumerate(pathlib.Path(f).read_text(encoding='utf-8').splitlines(),1) if l!=l.rstrip()]; assert not bad, bad; print('OK')"` | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: `source_verified` không phải `True` hoặc `grant_ref` rỗng/khoảng trắng/None raise `PermissionError` trước mọi tác vụ phụ (không gọi `reserve_object_id`, không ghi receipt).
2. GIẢ ĐỊNH: `operation_key`, `artifact_version_id`, `namespace_ref` rỗng hoặc `content_sha256`, `size_bytes` sai định dạng raise `ValueError` (kiểm tra sha256/size định dạng qua `evaluate_integrity(..., IntegrityObservation(None, None, None, None))`).
3. GIẢ ĐỊNH: `UploadReceipt` lưu thêm các trường `size_bytes`, `state`, và `verification_evidence_ref` để phục vụ idempotent retry và reconcile.
4. GIẢ ĐỊNH: Retry trên receipt chưa `VERIFIED` sẽ dùng lại `object_id` đã cấp trước và upload lại; nếu gặp 409 (`ObjectAlreadyExistsError`) thì tiếp tục lookup rồi verify; nếu receipt đã `VERIFIED` thì trả lại kết quả cũ ngay lập tức mà không gọi upload.
5. GIẢ ĐỊNH: Lời gọi `lookup` gặp `TimeoutError` sẽ ghi nhận receipt sang `OUTCOME_UNKNOWN` và trả về `PersistResult` với state `OUTCOME_UNKNOWN` và không có `verification_evidence_ref`.
6. GIẢ ĐỊNH: `reconcile(operation_key)` luôn lookup cloud theo đúng `object_id` lưu trong receipt; nếu `operation_key` chưa có receipt trong kho thì raise `LookupError`.
7. GIẢ ĐỊNH: `verification_evidence_ref` chỉ được gán trong kết quả và cập nhật trong receipt khi trạng thái xác minh là `VERIFIED`; các trạng thái khác (`MISSING`, `CORRUPT`, `OUTCOME_UNKNOWN`) đều có evidence ref là `None`.

## Danh sách chờ user (pendingUserCheckpoint)

- PUC-I-01 – ROADMAP-OPEN-010: thời hạn retention (original, reusable, temporary, output, log và evidence) và placement/quota thật của bốn tài khoản Drive. Hạn: trước unattended cleanup.
- PUC-I-02 – ROADMAP-OPEN-004: múi giờ production dùng cho tên folder `YY-MM-DD`. Hạn: trước khi bật lịch production.
- PUC-I-03 – Ngưỡng byte của working set và disk reserve trên máy mục tiêu (đo ở CP7-I-03). Hạn: trước khi nghiệm thu hiệu năng render.
- PUC-I-04 – User duyệt C-I và `R2 Media Alpha` (EG-M4-I-6).
- PUC-I-05 – D5 cho CP7 (tài khoản Drive thật) và USER-CKPT-D9-D10 trước CP-2b.
- PUC-I-06 – ROADMAP-OPEN-012: phạm vi backup/restore (G05). Hạn: trước khi bật writer/cleanup sau restore.

Không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa statemachine, verification.py, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài stdlib.
- Không gọi dịch vụ thật (Google Drive, OAuth, Cloud Object Storage thật).
- Không tạo conftest.py hay __init__.py trong tests/.
- Không thêm recovery edge hay tự gọi apply_integrity_outcome/transition_artifact_location trong cloud_persist.py; không tự đổi hành vi evaluate_integrity của I-03.
- Không sửa bất kỳ tệp nào ngoài 3 owned paths được phân quyền: `src/controlplane/application/storage_meta/cloud_persist.py`, `tests/unit/storage/test_storage_cloud_persist.py`, `docs/delivery-evidence/i-04/report.md`.
