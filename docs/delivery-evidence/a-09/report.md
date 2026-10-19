# Báo cáo bằng chứng A-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `d3b0cff0a6c39bb4cce7451ff61435358b50a768`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS và slice A-09 trong `docs/implementation/a/slices.md`; phụ thuộc A-04/A-08 đã tích hợp.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider`
- Trạng thái mô phỏng RED: test hoàn chỉnh, `source_commands.py` là stub.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `33 failed, 1 passed in 0.41s`
- Test FAILED tiêu biểu:
  - `FAILED tests/integration/collection/test_a09_source_commands.py::RegisterSourceTests::test_register_commits_source_receipt_and_event_together` (AssertionError: None is not an instance of <class 'source_ingestion.application.source_commands.CommandResult'>)
  - `FAILED tests/integration/collection/test_a09_source_commands.py::RegisterRejectionTests::test_blank_idempotency_key_is_rejected` (AssertionError: None is not an instance of <class 'source_ingestion.application.source_commands.CommandResult'>)
  - `FAILED tests/integration/collection/test_a09_source_commands.py::EventSafetyTests::test_module_reuses_controlplane_types_and_respects_layers` (AssertionError: False is not true)
- Xác nhận: 0 error, không có ImportError, ModuleNotFoundError hay collection error; lỗi RED hoàn toàn là AssertionError sai oracle.

## Thay đổi

- `src/source_ingestion/application/source_commands.py`: triển khai lớp `SourceCommandHandler` điều phối 4 command (`RegisterSource`, `UpdateSourceMetadata`, `RemoveSource`, `RestoreSource`); mỗi command chạy trong một Unit of Work ghi source revision, `CommandReceipt` (idempotency key theo `request_hash` của controlplane) và outbox event dựng bằng controlplane `DomainEvent`; các lớp ngoại lệ `IdempotencyConflictError`, `TombstoneConflictError`, `SourceAlreadyRegisteredError`, `SourceNotFoundError`; DTO `CommandResult`; protocol `SourceUnitOfWork`.
- `tests/integration/collection/test_a09_source_commands.py`: kiểm thử tích hợp 28 test case chia thành 5 nhóm (`RegisterSourceTests`, `RegisterRejectionTests`, `UpdateSourceMetadataTests`, `RemoveRestoreTests`, `EventSafetyTests`), docstring ghi `coveredIds: A-RULE-001, A-RULE-002, A-RULE-003, A-RULE-014`.
- `docs/delivery-evidence/a-09/report.md`: báo cáo bằng chứng chi tiết, bảng ánh xạ yêu cầu kiểm thử, kết quả RED/GREEN và quyết định kỹ thuật.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Test |
|---|---|
| Replay cùng key và payload trả receipt cũ | `test_same_key_and_payload_returns_original_receipt` |
| Cùng key khác payload hoặc khác command ném IdempotencyConflictError | `test_same_key_with_different_payload_is_idempotency_conflict` |
| Tab sau mang revision cũ không thể ghi đè (RevisionConflictError) | `test_second_tab_with_stale_revision_cannot_overwrite` |
| Lỗi ghi outbox rollback toàn bộ UoW (cả source và receipt) | `test_atomic_rollback_when_outbox_write_fails`, `test_update_rolls_back_when_outbox_write_fails` |
| Gửi lặp locator tạo mới bị xung đột không tạo Source trùng | `test_same_locator_with_new_key_conflicts_with_existing_source` |
| Locator trùng tombstone báo xung đột kèm source ref đã xoá | `test_locator_matching_tombstone_conflicts_with_removed_source_ref` |
| Locator unsafe theo chính sách SSRF (A-04) bị từ chối không tạo Source | `test_unsafe_locators_are_rejected_without_creating_source` |
| Xoá nguồn (remove) không xoá package đã lưu trữ | `test_remove_tombstones_source_and_keeps_stored_package` |
| Workspace khác không thấy hoặc không sửa được nguồn | `test_other_workspace_cannot_see_or_change_source`, `test_same_key_in_other_workspace_is_independent` |
| Event và receipt không chứa secret, locator hay token (A-RULE-014) | `test_events_and_receipts_never_contain_locator_or_secret`, `test_register_event_payload_has_identifiers_only` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider | 0 | 28 passed, 11 subtests passed in 0.08s |
| 2 | git diff --check | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. Receipt dùng `CommandReceipt` của A-08, `request_hash` = controlplane `request_hash` của `{command_name, workspace_id, payload}`, không gồm actor hay thời gian.
2. Event payload chỉ có định danh, trạng thái, tier, kind, policy_revision, changed_fields, không có locator/name/notes/reason để loại token (A-RULE-014).
3. Envelope theo binding domain-event-envelope 1.0.0 (producer `'A'`, schema_version `'1.0.0'`, recovery_epoch do composition root cấp), lưu ý annotation int của controlplane `DomainEvent.schema_version` và recovery_epoch lệch binding, chờ CONV-A-09.
4. Outbox `deduplication_id = workspace:event_name:source_id:revision`.
5. Lỗi idempotency là `IdempotencyConflictError` cục bộ của A.
6. PostgreSQL chờ CONV-A-01, route chờ CONV-A-03, đăng ký event catalog chờ CONV-A-09.
7. Không thêm thư viện.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- CONV-A-01
- CONV-A-03
- CONV-A-09

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
