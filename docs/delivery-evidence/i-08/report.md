# Báo cáo bằng chứng I-08

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `68e2ae94f4aafb49345a02583208516271e7e05e`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-08, CT-STO-007/008, INV-009.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `55 failed, 12 passed in 0.30s`
- Chi tiết các test FAILED kèm thông điệp lỗi nguyên văn:
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[output not cloud verified]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('DURABLE_COPY_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[original not cloud verified]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('DURABLE_COPY_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[reusable not cloud verified]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('DURABLE_COPY_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[unknown retention is durable]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('DURABLE_COPY_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[cloud verified None is not True]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('DURABLE_COPY_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[cloud storage class]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('NOT_LOCAL_STAGING',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[empty storage class]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('NOT_LOCAL_STAGING',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[stale epoch]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('STALE_RECOVERY_EPOCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[active lease]`: `AssertionError: assert ('eligible', ()) == ('deferred', ('ACTIVE_LEASE',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[no evidence refs]`: `AssertionError: assert ('eligible', ()) == ('deferred', ('NO_COMPLETION_EVIDENCE',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[blank completion ref]`: `AssertionError: assert ('eligible', ()) == ('deferred', ('NO_COMPLETION_EVIDENCE',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[both deferred reasons]`: `AssertionError: assert ('eligible', ()) == ('deferred', ('ACTIVE_LEASE', 'NO_COMPLETION_EVIDENCE'))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[forbidden wins over deferred]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('NOT_LOCAL_STAGING',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_table[all forbidden reasons in order]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('NOT_LOCAL_STAGING', 'LOCATION_NOT_VERIFIED', 'DURABLE_COPY_NOT_VERIFIED', 'STALE_RECOVERY_EPOCH'))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[DECLARED]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[MATERIALIZING]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[AVAILABLE_UNVERIFIED]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[VERIFYING]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[CORRUPT]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[MISSING]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[OUTCOME_UNKNOWN]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[CLEANUP_AUTHORIZED]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_evaluate_cleanup_forbids_every_other_location_state[DELETED]`: `AssertionError: assert ('eligible', ()) == ('forbidden', ('LOCATION_NOT_VERIFIED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[other location]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_MISMATCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[other version]`: `AssertionError: assert (True, ()) == (False, ('ARTIFACT_VERSION_MISMATCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[authorization hash differs]`: `AssertionError: assert (True, ()) == (False, ('HASH_MISMATCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[location hash differs]`: `AssertionError: assert (True, ()) == (False, ('HASH_MISMATCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[location hash missing]`: `AssertionError: assert (True, ()) == (False, ('HASH_MISMATCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[active lease]`: `AssertionError: assert (True, ()) == (False, ('ACTIVE_LEASE',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[now equals expiry]`: `AssertionError: assert (True, ()) == (False, ('EXPIRED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[now after expiry]`: `AssertionError: assert (True, ()) == (False, ('EXPIRED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[now equals expiry in +07:00]`: `AssertionError: assert (True, ()) == (False, ('EXPIRED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[expiry with offset reached]`: `AssertionError: assert (True, ()) == (False, ('EXPIRED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[stale epoch]`: `AssertionError: assert (True, ()) == (False, ('STALE_RECOVERY_EPOCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[int epoch stale]`: `AssertionError: assert (True, ()) == (False, ('STALE_RECOVERY_EPOCH',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[path outside staging]`: `AssertionError: assert (True, ()) == (False, ('PATH_OUTSIDE_STAGING',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_check_cleanup_authorization_table[all failures in order]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_MISMATCH', 'HASH_MISMATCH', 'ACTIVE_LEASE', 'EXPIRED', 'PATH_OUTSIDE_STAGING'))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[DECLARED]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[MATERIALIZING]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[AVAILABLE_UNVERIFIED]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[VERIFYING]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[VERIFIED]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[CORRUPT]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[MISSING]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[OUTCOME_UNKNOWN]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[CLEANUP_ELIGIBLE]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_location_must_be_cleanup_authorized[DELETED]`: `AssertionError: assert (True, ()) == (False, ('LOCATION_NOT_AUTHORIZED',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[not-a-date]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[None]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[12345]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[2026-10-18T10:00:00]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expires_at_fails_closed_without_raising[2026-10-18]`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_naive_now_fails_closed_without_raising`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
  - `FAILED tests/unit/storage/test_storage_cleanup_evaluation.py::test_invalid_expiry_wins_over_other_failures`: `AssertionError: assert (True, ()) == (False, ('INVALID_EXPIRY',))`
- Xác nhận: Toàn bộ lỗi FAILED đều là AssertionError do stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (các test fixture, frozen và happy path eligible/check ban đầu đạt PASS).

## GREEN / Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` | 0 | `67 passed in 0.06s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Thay đổi

- `src/controlplane/application/storage_meta/cleanup_evaluation.py`: Định nghĩa các hằng số, dataclass frozen `CleanupEvaluationRequest` và `CleanupEvaluation`, các helper an toàn `_has_ref`, `_is_aware`, `_parse_expiry`, hàm `evaluate_cleanup` (CT-STO-007) kiểm tra storage class, location state, retention class / cloud copy verification (INV-009), stale recovery epoch, active lease và completion/superseded evidence, và hàm `check_cleanup_authorization` (CT-STO-008) kiểm tra đối sánh location_id, artifact_version_id, observed_hash, trạng thái CLEANUP_AUTHORIZED, active lease, hạn expiry theo múi giờ nhận thức, recovery epoch và path trong staging, fail-closed an toàn với INVALID_EXPIRY khi thời gian không hợp lệ mà không raise exception.
- `tests/unit/storage/test_storage_cleanup_evaluation.py`: Bộ kiểm thử đơn vị bao quát toàn bộ 20 case bảng cho `evaluate_cleanup`, kiểm tra cấm mọi location state khác ngoài VERIFIED và CLEANUP_ELIGIBLE, kiểm tra fixture SHA256 và recovery_epoch từ `payloads.json`, tính chất frozen của request/result, 18 case bảng cho `check_cleanup_authorization` với nhiều múi giờ khác nhau (+00:00, +07:00), kiểm tra location state phải là CLEANUP_AUTHORIZED, các trường hợp expires_at không hợp lệ và now naive fail-closed trả về INVALID_EXPIRY mà không raise exception.
- `docs/delivery-evidence/i-08/report.md`: Báo cáo bằng chứng thực thi I-08 ghi nhận môi trường, kết quả RED/GREEN, các quyết định D8, danh sách chờ và giới hạn kiểm thử.

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: `CleanupEvaluationRequest` có 9 trường `storage_class`, `location_state`, `retention_class`, `cloud_copy_verified`, `active_lease`, `completion_ref`, `superseded_ref`, `request_recovery_epoch`, `current_recovery_epoch`.
2. GIẢ ĐỊNH: Theo D8-I-06 chỉ `per_video` và `temporary` không cần cloud copy, retention lạ coi là durable (fail-closed), `cloud_copy_verified` phải đúng `True`.
3. GIẢ ĐỊNH: `earliest_cleanup_at` luôn `None` vì thời hạn retention chờ PUC-I-01.
4. GIẢ ĐỊNH: `forbidden` thắng `deferred`, mã lý do theo thứ tự cố định (`NOT_LOCAL_STAGING`, `LOCATION_NOT_VERIFIED`, `DURABLE_COPY_NOT_VERIFIED`, `STALE_RECOVERY_EPOCH` đối với forbidden; `ACTIVE_LEASE`, `NO_COMPLETION_EVIDENCE` đối với deferred), `INVALID_EXPIRY` trả riêng một mã độc lập.
5. GIẢ ĐỊNH: Hash đối sánh với `location.observed_hash`, mã lý do authorization theo thứ tự: `LOCATION_MISMATCH`, `ARTIFACT_VERSION_MISMATCH`, `HASH_MISMATCH`, `LOCATION_NOT_AUTHORIZED`, `ACTIVE_LEASE`, `EXPIRED`, `STALE_RECOVERY_EPOCH`, `PATH_OUTSIDE_STAGING`.
6. GIẢ ĐỊNH: 'cleanup authorization candidate' của CT-STO-007 không thuộc acceptance nên không triển khai.

## Danh sách chờ user (pendingUserCheckpoint)

- PUC-I-01: Chính sách retention chi tiết và tính toán thời hạn cleanup tự động.
- PUC-I-06: Quy trình backup/restore và khôi phục recovery epoch.
- Ghi rõ: Không mục nào trong danh sách trên được coi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa `__init__.py` P5B, statemachine, fixture, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài thư viện chuẩn.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay `__init__.py` trong tests/.
- Không commit secret.
