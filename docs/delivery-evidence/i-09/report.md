# Báo cáo bằng chứng I-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `6cc347b6b1c32c887c6393932f4ffe9b0b4d0c80`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-09, CT-STO-008, ADR-0010, INV-011.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` (chạy với stub ở bước 1)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `19 failed, 2 passed in 0.27s`
- Chi tiết các test FAILED kèm thông điệp lỗi nguyên văn:
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_valid_authorization_deletes_only_target`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...ason_codes=())` (Differing attributes: ['deleted'], deleted: False != True)
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[hash differs]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...H_MISMATCH',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[stale epoch]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...VERY_EPOCH',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[expired]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...=('EXPIRED',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[now equals expiry]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...=('EXPIRED',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[active lease]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...TIVE_LEASE',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[location not authorized]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...AUTHORIZED',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[location mismatch]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...N_MISMATCH',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unauthorized_deletion_keeps_file[invalid expiry]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...LID_EXPIRY',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_path_outside_staging_is_rejected[../outside.bin]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...DE_STAGING',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_path_outside_staging_is_rejected[a/../../outside.bin]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...DE_STAGING',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_path_outside_staging_is_rejected[None]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...DE_STAGING',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_directory_target_is_not_a_file`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...NOT_A_FILE',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_missing_target_is_not_a_file`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...NOT_A_FILE',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_resolve_runs_before_authorization`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...DE_STAGING',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_authorization_runs_before_not_a_file`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...=('EXPIRED',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unreadable_target_fails_closed`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...H_MISMATCH',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unlink_oserror_returns_delete_failed[error0]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...ETE_FAILED',))`
  - `FAILED tests/integration/storage/test_storage_cleanup_executor.py::test_unlink_oserror_returns_delete_failed[error1]`: `AssertionError: assert CleanupResult...ason_codes=()) == CleanupResult...ETE_FAILED',))`
- Xác nhận: Toàn bộ 19 lỗi FAILED đều là AssertionError do chạy trên stub trả `CleanupResult(False, ())`; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError hay lỗi collection. Hai test tĩnh `test_source_has_no_directory_removal` và `test_cleanup_result_is_frozen` đạt PASS.

## GREEN / Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` | 0 | `21 passed in 0.29s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Thay đổi

- `src/controlplane/infrastructure/storage/cleanup_executor.py`: Triển khai `LocalCleanupExecutor` và frozen dataclass `CleanupResult(deleted: bool, reason_codes: tuple[str, ...])`. Thứ tự thực thi gồm 5 bước nghiêm ngặt: (1) `resolve_staging_path` bắt `StagingPathError` trả `PATH_OUTSIDE_STAGING`; (2) `check_cleanup_authorization` với `path_within_staging=True`; (3) kiểm tra `is_file()` trả `NOT_A_FILE` nếu là thư mục hoặc không tồn tại; (4) kiểm tra SHA-256 bằng hàm đọc chunk `_sha256_of` trả `HASH_MISMATCH` khi không khớp hoặc gặp `OSError` (fail-closed); (5) gọi `target.unlink()` bắt `OSError` trả `DELETE_FAILED` mà không raise exception ra ngoài. Tệp hoàn toàn không chứa chuỗi `rmtree` hay `rmdir`, không gọi `os.remove`/`os.unlink`/`shutil`, không ghi state DB.
- `tests/integration/storage/test_storage_cleanup_executor.py`: Bộ kiểm thử tích hợp 21 test bao quát đầy đủ: xoá thành công tệp đích hợp lệ và giữ nguyên các tệp khác trong thư mục; 8 trường hợp authorization không hợp lệ giữ nguyên tệp; 3 trường hợp đường dẫn ngoài staging root; 2 trường hợp đích là thư mục hoặc tệp không tồn tại; 2 test thứ tự fencing (resolve trước authorization, authorization trước not_a_file); fail-closed khi không đọc được tệp; xử lý an toàn lỗi `OSError`/`PermissionError` khi unlink; kiểm tra tĩnh mã nguồn không chứa `rmtree` hay `rmdir`; và kiểm tra `CleanupResult` là frozen dataclass.
- `docs/delivery-evidence/i-09/report.md`: Báo cáo bằng chứng thực thi I-09 ghi nhận môi trường, kết quả RED/GREEN thực tế, các quyết định D8, danh sách chờ user và giới hạn kiểm thử.

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: Khi `resolve_staging_path` phát sinh `StagingPathError`, executor trả duy nhất mã lỗi `PATH_OUTSIDE_STAGING`.
2. GIẢ ĐỊNH: Tệp đích không tồn tại hoặc là thư mục đều được xác định qua `not target.is_file()` và trả về mã lỗi `NOT_A_FILE`.
3. GIẢ ĐỊNH: Lỗi I/O (`OSError`) trong quá trình đọc tệp để tính hàm băm SHA-256 được xử lý fail-closed bằng cách trả về `HASH_MISMATCH` mà không làm crash executor.
4. GIẢ ĐỊNH: So khớp hàm băm thực hiện chính xác giữa chuỗi hex viết thường SHA-256 tính từ nội dung tệp với `authorization.artifact_hash`.
5. GIẢ ĐỊNH: `current_recovery_epoch` được truyền dưới dạng `str` cho `check_cleanup_authorization`.

## Danh sách chờ user (pendingUserCheckpoint)

- PUC-I-01: Chính sách retention chi tiết và tính toán thời hạn cleanup tự động.
- PUC-I-06: Quy trình backup/restore và khôi phục recovery epoch.
- Ghi rõ: Không mục nào trong danh sách trên được coi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa tệp ngoài ba owned paths (`src/controlplane/infrastructure/storage/cleanup_executor.py`, `tests/integration/storage/test_storage_cleanup_executor.py`, `docs/delivery-evidence/i-09/report.md`).
- Không thêm thư viện ngoài thư viện chuẩn.
- Không gọi dịch vụ thật.
- Không ghi state DB hay ledger.
- Không commit secret.
