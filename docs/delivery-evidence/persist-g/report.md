# Báo cáo PERSIST-G

## Tệp đã sửa/tạo

- `src/controlplane/infrastructure/db/orchestration/grants.py`
- `src/controlplane/infrastructure/db/orchestration/allocation.py`
- `src/controlplane/infrastructure/db/orchestration/variants.py`
- `src/controlplane/infrastructure/db/orchestration/start_batch.py`
- `src/controlplane/infrastructure/db/orchestration/__init__.py`
- `tests/integration/persistence/g/test_persist_g_postgres.py`
- `docs/delivery-evidence/persist-g/report.md`

## Quyết định thiết kế và mục mở

1. Các kho PostgreSQL (`PostgresGrantStore`, `PostgresRecoveryEpoch`, `PostgresAllocationStore`, `PostgresVariantRegistry`) đều nhận đối tượng connection do caller sở hữu; adapter không tự quản lý giao dịch, không gọi commit hay rollback của kết nối. `PostgresGrantStore` và `PostgresRecoveryEpoch` nhận `(connection, workspace_id)` vì bảng `cp_execution_grants` và `cp_app_sessions` có cột `workspace_id NOT NULL`. `PostgresVariantRegistry` nhận `workspace_id` từ từng tham số lời gọi theo định nghĩa port `VariantRegistryPort`.
2. `RecoveryEpochPort.current` tra cứu `recovery_epoch` từ phiên làm việc (`cp_app_sessions`) có trạng thái `ACTIVE` mới nhất theo `started_at DESC, session_ref DESC LIMIT 1`. Nếu không có phiên nào đang hoạt động, ném `OrchestrationContractError('NOT_FOUND')` theo GIẢ ĐỊNH (mục mở D8), đảm bảo khớp hợp đồng phân hệ.
3. `PostgresGrantStore.active_grant` không lọc theo tham số `now` vì `GrantIssuer` chịu trách nhiệm xét hạn TTL trong bộ nhớ; `insert` không cập nhật `cp_stage_runs.execution_generation` mà kiểm tra đơn điệu bằng cách từ chối `execution_generation` nhỏ hơn hoặc bằng thế hệ hiện tại (`latest_generation`) bằng ngoại lệ `ValueError`; ràng buộc cơ sở dữ liệu (chỉ mục unique và partial index trên `revoked_at IS NULL`) tự động từ chối grant trùng thế hệ hoặc lease thứ hai đang hoạt động bằng lỗi `UniqueViolation`.
4. `PostgresAllocationStore.lock_batch` sử dụng `SAVEPOINT persist_g_lock_batch` kết hợp truy vấn `SELECT target_count ... FOR UPDATE` trên dòng batch. Quyền commit giao dịch thuộc về caller (Unit of Work); nếu có ngoại lệ phát sinh trong khối context manager, khối sẽ thực hiện `ROLLBACK TO SAVEPOINT` và `RELEASE SAVEPOINT` rồi ném tiếp lỗi ra ngoài, đảm bảo dữ liệu outbox và grant cùng rollback đồng bộ trong giao dịch lớn (khác chú thích 'thoát bình thường = commit' của port).
5. Do bảng `cp_video_jobs` trong migration hiện hành không có cột riêng `angle_slot`, giá trị này được mã hoá vào cột `snapshot_ref` dưới dạng tiền tố `allocation:<angle_slot>` theo GIẢ ĐỊNH (khi đọc lại phân tích chuỗi để khôi phục `angle_slot`). Nếu muốn có cột riêng cần chủ migration bổ sung.
6. `VariantReservationRecord.idempotency_key` được lưu trữ tại bảng `cp_orchestration_receipts` với khoá tổng hợp `variant_reservation:<reservation_id>`. `PostgresVariantRegistry.current_revision` tự động khởi tạo bản ghi registry revision bằng 1 nếu chưa tồn tại (`ON CONFLICT DO NOTHING`) để tương thích với `PostgresOrchestrationRepository`.
7. `PostgresStartBatchRepository.stop` cập nhật `stop_reason` và gán `stopped_at = CURRENT_TIMESTAMP` chỉ khi `stop_reason IS NULL` (thực hiện dừng một lần duy nhất, idempotent).
8. Các bảng mới của migration 0011 như `cp_orchestration_receipts`, `cp_cleanup_eligibility`, `cp_app_sessions` đã được kiểm tra khớp schema qua `information_schema.columns`. Phân hệ chưa có port ứng dụng riêng cho `cleanup_eligibility` nên chưa tạo adapter riêng; không tạo `postgres_completion.py` và không cài đặt `CompletionStorePort` (thuộc phạm vi gói CP-5-COMPLETION, BL-CV-11: PENDING).
9. Chưa ghi user checkpoint M2.

## RED trước implementation

Chứng kiến RED hợp lệ tại Bước 13 trên PostgreSQL 18.6 trước khi cài đặt adapter, hoàn toàn bằng `AssertionError` do các hàm stub gây ra; không có lỗi import, lỗi cú pháp hay lỗi setup/fixture:
- Lệnh: `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `10 failed, 2 passed in 6.62s` (exit code 1)
- Danh sách test fail:
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_grant_round_trip_revoke_and_monotonic_generation` (AssertionError: assert None == GrantClaims(...))
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_active_grant_blocks_other_lease_and_epoch_change_supersedes` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_db_rejects_duplicate_generation_and_second_active_lease` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_recovery_epoch_is_text_and_compared_with_str` (AssertionError: assert '0' == '7')
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_grant_and_outbox_roll_back_together` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_allocation_round_trip_and_idempotent_replay` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_allocation_counts_ledger_and_active_and_respects_target` (AssertionError: assert 0 == 1)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_two_parallel_connections_never_exceed_target` (AssertionError: assert ['ok', 'ok', 'ok', 'ok'] == ['full', 'full', 'full', 'ok'])
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_variant_registry_round_trip_conflicts_and_settle` (AssertionError: assert 1 == 2)
  - `FAILED tests/integration/persistence/g/test_persist_g_postgres.py::test_start_batch_repository_records_stop_reason` (AssertionError: assert False is True)

## GREEN sau implementation

Sau khi hoàn tất cài đặt các module trong `src/controlplane/infrastructure/db/orchestration`, toàn bộ 12 test tích hợp chạy trên PostgreSQL 18.6 với cơ sở dữ liệu tạm riêng biệt cho từng bài test đều đạt tuyệt đối:
- Lệnh: `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
- Tóm tắt: `12 passed in 5.92s` (exit code 0)

## Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 13 | `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 1 | 10 failed, 2 passed in 6.62s (AssertionError do stub) |
| 19 | `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | 12 passed in 5.92s (toàn bộ 12 test đạt) |
| 20 | `python -m pytest tests/m2/test_p6_orchestration_shell.py -q -p no:cacheprovider` | 0 | 4 passed in 2.38s |
| 22 | `git diff --check` | 0 | Không có khoảng trắng thừa hoặc lỗi diff |
| 23 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and not (d / 'postgres_completion.py').exists(), 'adapter G'"` | 0 | Probe đạt: không có DDL, không có postgres_completion.py |