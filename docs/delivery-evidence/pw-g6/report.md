# Báo cáo PW-G6

## 1. Phạm vi
Thực hiện trong bốn tệp thuộc owned paths của nhiệm vụ PW-G6:
- `src/controlplane/infrastructure/db/orchestration/outbox_relay.py`: tạo mới lớp `OutboxRelay`, `NoActiveAppSessionError` và các hằng liên quan.
- `tests/integration/prod_wiring/test_pw_g6_outbox_relay.py`: tạo mới test bộ chuyển tiếp outbox trên PostgreSQL 18.6 thật và máy chủ test temporalio.
- `tests/integration/persistence/g/test_persist_g_postgres.py`: mở hai token `.commit(` và `.rollback(` cho duy nhất `outbox_relay.py` trong test khóa cấu trúc và bổ sung các ca kiểm thử ràng buộc.
- `docs/delivery-evidence/pw-g6/report.md`: tạo mới báo cáo nghiệm thu này.

Không sửa bất kỳ tệp nào ngoài owned paths, không sửa `tests/integration/convergence/test_cp5_completion_uow.py` (do PW-G1 sở hữu).

## 2. Thiết kế
- `OutboxRelay`:
  - Trong một giao dịch kết nối CSDL (bắt buộc `autocommit=False`), thực hiện `SELECT event_id, payload FROM controlplane.cp_outbox_events WHERE workspace_id = %s AND published = false AND event_name = %s ORDER BY recorded_at, event_id LIMIT %s FOR UPDATE SKIP LOCKED` với `event_name = 'production_batch.start_accepted'`.
  - Trước khi đánh dấu published, gọi client temporal: `client.start_workflow('ProductionBatchWorkflow', request, id=batch_id, task_queue='control-workflows', id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)`.
  - Payload khởi tạo bao gồm `batch_id`, `target_videos` (trích từ `target_count`), `jobs=[]`, `settings` định dạng `WorkflowSettings.to_payload()` (đọc lại được bằng `WorkflowSettings.from_payload`), và `worker_lease_id` là `session_ref` của phiên `AppSession` ACTIVE gần nhất.
  - Xử lý ngoại lệ `WorkflowAlreadyStartedError`: xem như khởi tạo thành công để tiếp tục ack sự kiện, đảm bảo tính lũy đẳng (idempotent).
  - Chỉ sau khi khởi tạo workflow thành công mới gọi `UPDATE controlplane.cp_outbox_events SET published = true, published_at = %s WHERE event_id = %s AND published = false` và `connection.commit()`.
  - Nếu có bất kỳ ngoại lệ nào xảy ra giữa chừng, toàn bộ giao dịch sẽ được `connection.rollback()`, toàn bộ sự kiện vẫn giữ `published = false` để chu kỳ kế tiếp thử lại.
  - Sự kiện khác tên bị bỏ qua không chọn và không bị ack; sự kiện payload sai định dạng (thiếu `batch_id`, rỗng, hoặc `target_count` không hợp lệ) bị bỏ qua có ghi log cảnh báo, không ack.
  - Nếu không có phiên `AppSession` ACTIVE cho workspace, raise `NoActiveAppSessionError` và rollback, không khởi tạo workflow hay ack.
  - Kết nối CSDL bật autocommit sẽ bị từ chối ngay từ đầu bằng `ValueError`.
  - Các lệnh I/O PostgreSQL đồng bộ được điều phối qua `asyncio.to_thread`.
  - `run_forever(stop_event, interval_seconds)`: chạy chu kỳ liên tục trong tiến trình worker và dừng êm ngay khi `stop_event` được set (kể cả khi interval lớn nhờ `asyncio.wait_for(stop_event.wait(), timeout=...)`), bắt ngoại lệ từng chu kỳ để không làm sập vòng lặp worker.

## 3. Dòng đã đổi ở test_persist_g_postgres.py
Sau khi thực hiện chỉnh sửa theo lệnh làm việc, các vị trí dòng thật trong `tests/integration/persistence/g/test_persist_g_postgres.py` gồm:
- Dòng 1–4: Docstring cấp module được chuyển thành nhiều dòng, trong đó dòng 3 khai báo `coveredIds: PW-G6-01`.
- Dòng 47–50: Chèn comment căn cứ theo kế hoạch IMPL-PLAN-PROD-WIRING-V4 đã duyệt và hai hằng mới:
  - Dòng 49: `EXT_RELAY_ADAPTER = 'outbox_relay.py'`
  - Dòng 50: `EXT_RELAY_ALLOWED_TOKENS = ('.commit(', '.rollback(')`
  ngay sau `EXT_COMPLETION_ADAPTER = 'postgres_completion.py'` (dòng 46) và trước `BANNED_ADAPTER_TOKENS`.
- Dòng 713, 716–717: Trong hàm `banned_tokens_in`, bổ sung:
  - Dòng 713: `allowed = EXT_RELAY_ALLOWED_TOKENS if name == EXT_RELAY_ADAPTER else ()`
  - Dòng 716–717: bỏ qua kiểm tra nếu token cấm nằm trong danh sách `allowed`.
- Dòng 775–803: Nối thêm bốn hàm test mới (tổng cộng 7 ca kiểm thử):
  - Dòng 775–777: `test_banned_tokens_in_allows_commit_and_rollback_only_in_outbox_relay`
  - Dòng 780–788: `test_banned_tokens_in_still_flags_other_tokens_in_outbox_relay`
  - Dòng 791–797: `test_banned_tokens_in_still_flags_commit_in_other_files_next_to_outbox_relay`
  - Dòng 800–803: `test_relay_exemption_is_exactly_commit_and_rollback`

Lý do thay đổi: Kế hoạch IMPL-PLAN-PROD-WIRING-V4 đã duyệt (docs/implementation/prod-wiring/slices.md, mục PW-G6) giao `outbox_relay.py` tự quản lý giao dịch và thực hiện commit / rollback độc lập trong tiến trình worker; do đó tệp này chỉ được miễn đúng hai token trong `EXT_RELAY_ALLOWED_TOKENS`. Mọi token cấm khác (gồm `connect(`, `TransactionManager`, `CREATE TABLE`, `from src.`) vẫn bị báo lỗi nếu xuất hiện ở `outbox_relay.py`. Các tệp khác cùng thư mục (`grants.py`, `collection_scheduler.py`) nếu chứa `.commit(` vẫn bị báo lỗi. Hằng `BANNED_ADAPTER_TOKENS` và sự miễn trừ toàn bộ tệp của `EXT_COMPLETION_ADAPTER` (`postgres_completion.py`) được giữ nguyên.

## 4. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_g6_outbox_relay.py -q -p no:cacheprovider` (bước 7) | 1 | 11 failed, 3 passed in 40.99s (chứng kiến RED oracle) |
| `python -m pytest tests/integration/prod_wiring/test_pw_g6_outbox_relay.py -q -p no:cacheprovider` (bước 9) | 0 | 14 passed in 7.43s (GREEN sau khi triển khai run_once) |
| `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` (bước 12) | 1 | 7 failed, 16 passed in 4.82s (chứng kiến RED trước khi sửa hàm quét) |
| `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` (bước 14) | 0 | 23 passed in 4.65s (GREEN sau khi sửa hàm quét) |
| `python -m pytest tests/integration/prod_wiring/test_pw_g6_outbox_relay.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider` (bước 15) | 0 | 77 passed in 14.39s (toàn bộ 3 tệp xanh) |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/outbox_relay.py').read_text(encoding='utf-8'); assert 'SKIP LOCKED' in t and 'REJECT_DUPLICATE' in t and 'from src.' not in t, 'PW-G6'"` (bước 16) | 0 | PASS: outbox_relay.py chứa SKIP LOCKED và REJECT_DUPLICATE, không chứa from src. |
| `git diff --check` (bước 18) | 0 | PASS: không có lỗi khoảng trắng |

## 5. Oracle
- Bước 7: Chứng kiến RED trên `tests/integration/prod_wiring/test_pw_g6_outbox_relay.py` khi `OutboxRelay.run_once` là khung stub `return 0`. 11 test failed do assertion nghiệp vụ và kiểm tra mã nguồn tĩnh (không phải lỗi import hay thiếu fixture):
  - `test_run_once_starts_one_workflow_per_batch_and_acks_after_start`: fail do chưa ack và chưa khởi tạo workflow (assert 0 == 1).
  - `test_two_parallel_relays_start_the_batch_once`: fail do không có relay nào xử lý (assert [0, 0] == [0, 1]).
  - `test_start_failure_rolls_back_every_ack_and_the_next_run_recovers`: fail vì chưa gọi client (DID NOT RAISE RuntimeError).
  - `test_already_started_workflow_is_acknowledged`: fail do chưa xử lý ack (assert 0 == 1).
  - `test_events_with_other_names_are_skipped_and_need_no_session`: fail ở lượt gọi relay thứ hai (assert 0 == 1).
  - `test_without_an_active_app_session_nothing_starts_and_nothing_is_acked`: fail vì chưa kiểm tra phiên active (DID NOT RAISE NoActiveAppSessionError).
  - `test_a_malformed_event_is_skipped_without_blocking_the_next_one`: fail vì chưa xử lý batch thật kế tiếp (assert 0 == 1).
  - `test_a_connection_with_autocommit_is_rejected`: fail vì chưa kiểm tra cờ autocommit (DID NOT RAISE ValueError).
  - `test_run_forever_publishes_then_stops_at_once_even_with_a_long_interval`: fail vì sự kiện không được publish trong timeout.
  - `test_run_forever_survives_a_failed_cycle`: fail vì sự kiện không được publish trong timeout.
  - `test_relay_source_uses_skip_locked_reject_duplicate_and_no_stub`: fail vì thiếu các token tĩnh bắt buộc (REJECT_DUPLICATE, to_thread, .commit(, .rollback().
  Sau khi triển khai hoàn chỉnh tại bước 8, toàn bộ 14 test đã chuyển sang GREEN tại bước 9.
- Bước 12: Chứng kiến RED trên `tests/integration/persistence/g/test_persist_g_postgres.py` sau khi thêm bốn test mới nhưng chưa sửa `banned_tokens_in`. 7 test failed do `banned_tokens_in` báo `.commit(` và `.rollback(` trong `outbox_relay.py`:
  - `test_adapter_source_has_no_ddl_completion_store_or_transaction_control`
  - `test_banned_tokens_in_allows_commit_and_rollback_only_in_outbox_relay`
  - `test_banned_tokens_in_still_flags_other_tokens_in_outbox_relay[connection = psycopg.connect(dsn)\n-connect(]`
  - `test_banned_tokens_in_still_flags_other_tokens_in_outbox_relay[from controlplane.infrastructure.db.uow import TransactionManager\n-TransactionManager]`
  - `test_banned_tokens_in_still_flags_other_tokens_in_outbox_relay[SQL = 'CREATE TABLE t (id int)'\n-CREATE TABLE]`
  - `test_banned_tokens_in_still_flags_other_tokens_in_outbox_relay[from src.controlplane import x\n-from src.]`
  - `test_banned_tokens_in_still_flags_commit_in_other_files_next_to_outbox_relay`
  Sau khi sửa `banned_tokens_in` tại bước 13, toàn bộ 23 test đã chuyển sang GREEN tại bước 14.

## 6. Giới hạn
Kết quả chỉ chứng minh trên PostgreSQL 18.6 loopback và máy chủ test time-skipping của temporalio; chưa nối relay vào tiến trình worker và launcher stop vì thuộc các gói khác của milestone; không đóng cổng sản xuất (PRODUCTION_ACTIVATION_BLOCKED).
