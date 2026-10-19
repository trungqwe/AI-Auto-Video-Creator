# Báo cáo bằng chứng A-14

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-14 trong `docs/implementation/a/slices.md`; phụ thuộc A-08 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider`
- Trạng thái mã lúc RED: `artifact_handoff.py` chứa khung stub `handoff_raw_snapshot` trả `RawSnapshotHandoff(HandoffStatus.DECLARED, run, operation_key, '', '')` mà không gọi port, không kiểm tra trạng thái run hay policy, không xử lý `TimeoutError`.
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `17 failed, 2 passed in 0.21s`
- Test FAILED tiêu biểu nguyên văn:
  - `FAILED tests/integration/collection/test_a14_artifact_handoff.py::test_declare_request_uses_hash_size_media_type_policy_and_operation_key` (AssertionError: assert [] == [{'artifact_k...s': 104, ...}])
  - `FAILED tests/integration/collection/test_a14_artifact_handoff.py::test_timeout_after_object_creation_is_outcome_unknown_and_run_waits` (AssertionError: assert <HandoffStatus.DECLARED: 'DECLARED'> is <HandoffStatus.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>)
  - `FAILED tests/integration/collection/test_a14_artifact_handoff.py::test_no_blind_retry_before_reconcile` (Failed: DID NOT RAISE ReconciliationPendingError)
- Xác nhận: 0 error, không có lỗi `ModuleNotFoundError`, `ImportError` hay lỗi collection; các ca kiểm thử FAILED đều do `AssertionError`, `KeyError`, `IndexError`, `InvalidTransitionError` hoặc `DID NOT RAISE` đúng oracle.

## Thay đổi

- `src/source_ingestion/application/artifact_handoff.py`:
  - `RawSnapshotPolicy`: Dataclass bất biến chứa `policy_revision`, `artifact_kind`, `retention_class`, `sensitivity_class`, `intended_storage_class`. Hoàn toàn không có giá trị mặc định để Phân hệ A không bao giờ tự ý quyết định chính sách lưu trữ hay retention.
  - `snapshot_operation_key`: Hàm tạo key thao tác tất định bằng uuid5 từ namespace cố định kết hợp `collection_run_id` và `content_sha256`.
  - `handoff_raw_snapshot`: Khai báo phiên bản artifact cho Phân hệ I qua `ArtifactPort` (CT-STO-001). Kiểm tra run `RUNNING` (từ chối `WAITING_RECONCILIATION` bằng `ReconciliationPendingError`, từ chối trạng thái khác bằng `HandoffError`); dựng request đầy đủ trường lấy từ quan sát tài liệu và policy; bắt `TimeoutError` chuyển trạng thái run sang `WAITING_RECONCILIATION` với attempt outcome `OUTCOME_UNKNOWN`; từ chối các reference dạng đường dẫn tệp (`/`, `:`, `\`); trả `RawSnapshotHandoff` chỉ chứa `raw_snapshot_ref` mờ và không lưu bất kỳ đường dẫn lưu trữ nào.
  - `RawSnapshotHandoff`: Dataclass bất biến chứa kết quả bàn giao gồm `status`, `run`, `operation_key`, `content_sha256`, `policy_revision`, `raw_snapshot_ref`, `artifact_id`, `matched_existing`.
- `tests/integration/collection/test_a14_artifact_handoff.py`: Bộ kiểm thử tích hợp mới bao phủ toàn diện 19 ca kiểm thử với docstring ghi rõ `coveredIds: A-RULE-015`, chặn kết nối mạng socket qua fixture autouse, kiểm tra fake I `RecordingArtifactPort` với timeout sau tạo object, kiểm tra ranh giới nhập gói chỉ từ stdlib, `source_ingestion.domain` và `source_ingestion.ports`.
- `docs/delivery-evidence/a-14/report.md`: Báo cáo bằng chứng bàn giao thực thi task A-14.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Request đủ trường (hash, size, media_type, operation_key) và retention lấy từ policy (không mặc định trong A) | `test_declare_request_uses_hash_size_media_type_policy_and_operation_key`, `test_retention_comes_from_policy_not_from_a` |
| Gắn raw_snapshot_ref thành công vào package qua PackageContext và validate_package_schema | `test_success_ref_is_attached_to_collected_document_package` |
| Cùng operation key và hash trả kết quả cũ (matched_existing = True) | `test_same_operation_key_and_hash_returns_previous_result` |
| Operation key có tính tất định theo từng run và hash | `test_operation_key_is_deterministic_per_run_and_hash` |
| A không giữ đường dẫn lưu trữ, từ chối reference dạng đường dẫn | `test_a_keeps_no_storage_path`, `test_path_like_artifact_reference_is_rejected` |
| Timeout sau khi tạo object → OUTCOME_UNKNOWN và run chuyển sang WAITING_RECONCILIATION (A-RULE-015) | `test_timeout_after_object_creation_is_outcome_unknown_and_run_waits` |
| Không retry mù trước reconcile (ReconciliationPendingError) và retry sau reconcile dùng lại operation key nhận matched_existing | `test_no_blind_retry_before_reconcile`, `test_retry_after_reconcile_reuses_operation_key_and_matches_existing` |
| Kiểm tra trạng thái run và ngoại lệ non-timeout | `test_non_running_run_is_rejected_without_declaring`, `test_non_timeout_error_propagates_and_run_is_unchanged`, `test_invalid_port_result_is_rejected` |
| Ranh giới nhập gói: mô-đun chỉ import stdlib, domain và ports | `test_module_imports_only_stdlib_domain_and_ports` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider` | 0 | 19 passed in 0.08s |
| 2 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.07s |
| 3 | `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.08s |
| 4 | `git diff --check` | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. Giá trị `artifact_kind`, `retention_class`, `sensitivity_class`, `intended_storage_class` do caller lấy từ policy và truyền qua `RawSnapshotPolicy` vì `PolicyRevisionRef` chỉ mang revision string; A không gán giá trị mặc định nào.
2. `raw_snapshot_ref` là chuỗi `artifact_version_id` mờ; các giá trị chứa ký tự `/`, `:`, hoặc `\` bị từ chối bằng lỗi `STORAGE_PATH_REFERENCE` để đảm bảo A không lưu trữ đường dẫn tệp cục bộ hay URI tài nguyên vật lý.
3. `owner_resource_ref` lấy từ `run_id` của `CollectionRun`; `lineage_refs` do caller truyền vào, mặc định là danh sách rỗng.
4. Chỉ có `TimeoutError` phát sinh khi gọi port mới được bắt và chuyển thành `OUTCOME_UNKNOWN` kèm trạng thái run `WAITING_RECONCILIATION`; mọi ngoại lệ khác được lan truyền tự nhiên và run giữ nguyên trạng thái.
5. Phân hệ A chỉ thực hiện khai báo (`declare_artifact_version`), việc upload byte nhị phân thực tế do Phân hệ I đảm nhiệm theo thiết kế kiến trúc.
6. Quá trình reconcile sử dụng trực tiếp state machine của A-05 đã có; lần thử lại (retry) sau khi reconcile dùng lại cùng `operation_key` nên Phân hệ I sẽ trả về `matched_existing = True`.

## Mục mở / follow-up

- `MODULE-A-OPEN-007` và `ROADMAP-OPEN-010`: Chính sách và thời hạn retention thực tế do policy/Phân hệ I quy định.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5; CP7-A-03 raw snapshot lên Drive thật qua I)
- MODULE-A-OPEN-007

## Giới hạn

- Không chạy full test suite, `tests/m1` hay `tests/m2`.
- Không thay đổi `pyproject.toml`, `uv.lock` hay cài đặt thêm thư viện ngoài stdlib.
- Không thực hiện bất kỳ cuộc gọi mạng hay DNS thật nào; toàn bộ kiểm thử tích hợp được bảo vệ bằng fixture cô lập mạng socket.
- Chỉ sử dụng fake `ArtifactPort` (`FakeArtifactPort`, `RecordingArtifactPort`).