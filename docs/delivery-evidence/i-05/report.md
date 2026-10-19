# Báo cáo bằng chứng I-05

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4f956426cf8a28182acd5cba47ceebe368f9908f`
- Nguồn quyền: IMPL-PLAN-I Auditor PASS, slice I-05 trong `docs/implementation/i/slices.md`, CT-STO-005, ADR-0006, INV-012.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` (chạy với stub ở bước 7)
- Exit code thực tế: `1`
- Dòng tóm tắt nguyên văn: `19 failed, 2 passed in 0.22s`
- Chi tiết các test FAILED kèm thông điệp lỗi nguyên văn:
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_pragmas_are_wal_and_synchronous_full`: `AssertionError: assert {} == {'journal_mode': 'wal', 'synchronous': 'full'}`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_table_has_ct_sto_005_columns_and_unique_operation_key`: `AssertionError: assert [] == ['device_ref', 'session_ref', ...]`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_entries_survive_close_and_reopen`: `AssertionError: assert [None, None, None] == [JournalEntry(...), ...]`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_round_trip_preserves_none_bool_and_opaque_epoch`: `AssertionError: assert None == JournalEntry(...)`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_record_upserts_by_operation_key`: `AssertionError: assert None == JournalEntry(...)`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_record_with_same_generation_replaces_entry`: `AssertionError: assert None == JournalEntry(...)`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_older_generation_is_rejected_and_never_overwrites`: `Failed: DID NOT RAISE StaleGenerationError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_mark_state_updates_state_checkpoint_and_generation`: `AssertionError: assert None == JournalEntry(...)`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_mark_state_unknown_operation_key_raises_key_error`: `Failed: DID NOT RAISE KeyError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_list_unfinished_excludes_terminal_states`: `AssertionError: assert [] == ['op-a', 'op-d']`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_entries_from_other_epoch_lists_old_epochs_including_terminal`: `AssertionError: assert [] == ['op-old', 'op-old-done']`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_raw_session_uri_is_rejected_and_never_stored[https://upload.example.invalid/session?upload_id=CANARY-SECRET-TOKEN]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_raw_session_uri_is_rejected_and_never_stored[http://upload.example.invalid/session?id=CANARY-SECRET-TOKEN]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_raw_session_uri_is_rejected_and_never_stored[HTTPS://upload.example.invalid/CANARY-SECRET-TOKEN]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_raw_session_uri_is_rejected_and_never_stored[  https://upload.example.invalid/CANARY-SECRET-TOKEN]`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_raw_session_uri_does_not_replace_existing_secret_ref`: `Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_failed_insert_rolls_back_and_leaves_no_entry`: `Failed: DID NOT RAISE Error`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_failed_update_rolls_back_to_previous_entry`: `Failed: DID NOT RAISE Error`
  - `FAILED tests/integration/storage/test_storage_local_journal.py::test_module_source_has_no_delete_no_video_completed_and_only_stdlib_sqlite`: `AssertionError: assert 'sqlite3' in {'__future__', 'dataclasses', 'pathlib'}`
- Xác nhận: Toàn bộ lỗi FAILED đều là AssertionError hoặc Failed: DID NOT RAISE do stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (các test `test_package_init_is_single_line_docstring` và `test_public_api_has_no_delete_function` đạt PASS).

## Thay đổi

- `src/controlplane/infrastructure/storage/__init__.py`: Package init chứa đúng 1 dòng docstring theo chuẩn của I-05.
- `src/controlplane/infrastructure/storage/local_journal.py`: Hiện thực `JournalEntry` (dataclass frozen slots với 16 trường CT-STO-005), `StaleGenerationError`, và `SqliteLocalJournal` sử dụng sqlite3 stdlib với PRAGMA `journal_mode=WAL` và `synchronous=FULL`, tự động tạo bảng `local_journal_entries`, quản lý transaction atomic (`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`), upsert theo `operation_key` có kiểm tra generation fencing, chặn raw session URI (`http://`, `https://`) bằng cả logic Python và CHECK constraint SQLite, lọc `list_unfinished` loại bỏ các trạng thái terminal (`COMPLETED`, `ABANDONED`), truy vấn `entries_from_other_epoch`, hoàn toàn không có hàm xoá và không phát VideoCompleted.
- `tests/integration/storage/test_storage_local_journal.py`: Bộ kiểm thử tích hợp 21 test bao quát toàn bộ hợp đồng CT-STO-005, WAL/synchronous pragmas, 16 cột schema và UNIQUE index, round-trip mở lại journal bền vững, upsert và stale generation fencing, rollback khi gặp lỗi, từ chối URI nhạy cảm, loại trừ trạng thái kết thúc, và AST audit bảo đảm mã nguồn chỉ dùng sqlite3 stdlib, không có từ khoá delete hay event VideoCompleted.
- `docs/delivery-evidence/i-05/report.md`: Báo cáo bằng chứng thực thi I-05 ghi nhận môi trường, kết quả RED/GREEN, các quyết định D8, danh sách chờ và giới hạn kiểm thử.

## GREEN / Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` | 0 | `21 passed in 0.58s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: Trạng thái là chuỗi opaque; `TERMINAL_STATES = frozenset({"COMPLETED", "ABANDONED"})` là mặc định đơn giản, `list_unfinished` loại hai trạng thái này.
2. GIẢ ĐỊNH: Generation bằng nhau thì thay thế, nhỏ hơn thì StaleGenerationError; mark_state nâng generation lên giá trị truyền vào và raise KeyError khi operation_key chưa có.
3. GIẢ ĐỊNH: `observed_at` do caller truyền trong record, mark_state không đọc đồng hồ.
4. GIẢ ĐỊNH: `entries_from_other_epoch` so sánh chuỗi `str()` và trả cả entry ở trạng thái kết thúc để reconcile.
5. GIẢ ĐỊNH: `pragma_settings()` là hàm chỉ-đọc phục vụ kiểm chứng PRAGMA.
6. GIẢ ĐỊNH: Thêm CHECK trong SQLite chặn http(s):// như lớp phòng thủ thứ hai ngoài kiểm tra Python.
7. GIẢ ĐỊNH: `recovery_epoch` là TEXT opaque theo D8-I-04.

## Danh sách chờ user (pendingUserCheckpoint)

- Không phát sinh mục mới; slice không thêm thư viện (không cần USER-CKPT-D9-D10); ghi rõ không mục nào được coi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa migration, pyproject.toml, lockfile, composition root.
- Chỉ dùng sqlite3 stdlib; không phát VideoCompleted; không có hàm xoá entry.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- Không commit secret.
