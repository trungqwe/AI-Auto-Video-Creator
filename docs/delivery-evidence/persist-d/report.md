# Báo cáo chuyển giao: PERSIST-D

## 1. Phạm vi và tệp đã tạo

Nhiệm vụ PERSIST-D cài đặt adapter PostgreSQL cho bounded context creative (phân hệ D) trên các bảng được tạo bởi migration 0015_creative, tuân thủ hoàn toàn hợp đồng src/creative/ports/repositories.py và kiến trúc Unit of Work dùng chung kết nối với outbox giao dịch.

Các tệp đã tạo thuộc owned paths:
- src/creative/persistence/__init__.py: xuất 14 biểu tượng công khai của gói adapter.
- src/creative/persistence/codec.py: mã hóa và giải mã JSON/JSONB cho các dataclass phân hệ D.
- src/creative/persistence/repositories.py: cài đặt PostgresSnapshotRepository, PostgresAppendOnlyRepository (7 kho con) và PostgresReceiptStore.
- src/creative/persistence/outbox.py: cài đặt PostgresCreativeOutboxWriter ghi cp_outbox_events trên cùng kết nối giao dịch.
- src/creative/persistence/uow.py: cài đặt PostgresCreativeUnitOfWork mượn một kết nối duy nhất qua manager.borrow_connection().
- tests/integration/persistence/d/test_persist_d_postgres.py: 22 ca kiểm thử tích hợp trên PostgreSQL 18.6 thật.
- docs/delivery-evidence/persist-d/report.md: báo cáo nghiệm thu này.

Không có tệp nào ngoài owned paths bị chỉnh sửa.

## 2. RED trước implementation

Lệnh kiểm thử RED chạy tại bước 13 với stub rỗng:
- Lệnh: `python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider`
- Exit code: `1`
- Kết quả: `21 failed, 1 passed in 9.21s`
- Không có lỗi ImportError hay lỗi thu thập test (collection error). Ca kiểm duy nhất đạt là test_uow_exposes_ports_and_interfaces kiểm tra cấu trúc cổng Protocol. Toàn bộ 21 ca kiểm nghiệp vụ đều thất bại do assertion logic hoặc DID NOT RAISE đúng theo oracle:

Trích nguyên văn phần tóm tắt ngắn của bước 13:
```
FAILED tests/integration/persistence/d/test_persist_d_postgres.py::test_tables_and_columns_exist_in_the_real_schema
FAILED tests/integration/persistence/d/test_persist_d_postgres.py::test_snapshot_round_trip_and_immutability
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[analyses]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[angle_sets]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[scripts]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[plans]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[variant_validations]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[output_metadata]
FAILED tests/integration/persistence/d/test_append_round_trip_keeps_every_field[invocations]
FAILED tests/integration/persistence/d/test_angle_rows_are_indexed_per_set
FAILED tests/integration/persistence/d/test_append_accepts_only_latest_plus_one
FAILED tests/integration/persistence/d/test_record_id_is_unique_per_workspace[angle_sets]
FAILED tests/integration/persistence/d/test_record_id_is_unique_per_workspace[scripts]
FAILED tests/integration/persistence/d/test_record_id_is_unique_per_workspace[plans]
FAILED tests/integration/persistence/d/test_receipt_store_is_unique_and_workspace_scoped
FAILED tests/integration/persistence/d/test_history_tables_reject_update_and_delete
FAILED tests/integration/persistence/d/test_commit_writes_records_and_outbox_on_one_connection
FAILED tests/integration/persistence/d/test_rollback_discards_records_and_outbox
FAILED tests/integration/persistence/d/test_outbox_deduplicates_and_stays_in_workspace
FAILED tests/integration/persistence/d/test_uow_state_machine_and_workspace_validation
FAILED tests/integration/persistence/d/test_adapter_source_has_no_ddl_and_no_src_prefix
```

## 3. GREEN sau implementation

Tất cả các lệnh kiểm tra bắt buộc và hồi quy đều đạt exit code 0:

### Bước 20: Kiểm thử tích hợp PostgreSQL của adapter D
- Lệnh: `python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider`
- Exit code: `0`
- Kết quả nguyên văn:
```
......................                                                   [100%]
22 passed in 9.03s
```

### Bước 21: Quét mã nguồn adapter D cấm DDL và tiền tố 'src.'
- Lệnh: `python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter D'"`
- Exit code: `0`
- Kết quả: Không có lỗi, xác nhận không có CREATE TABLE, ALTER TABLE hay from src. trong src/creative/persistence.

### Bước 22: Hồi quy kiểm thử đơn vị của creative (kể cả test_d01 cấm import psycopg)
- Lệnh: `python -m pytest tests/unit/creative -q -p no:cacheprovider`
- Exit code: `0`
- Kết quả nguyên văn:
```
732 passed, 188 subtests passed in 1.85s
```

### Bước 23: Hồi quy kiểm thử tích hợp của creative (pipeline D-14, D-15, D-16)
- Lệnh: `python -m pytest tests/integration/creative -q -p no:cacheprovider`
- Exit code: `0`
- Kết quả nguyên văn:
```
97 passed in 0.40s
```

### Bước 25: Kiểm tra khoảng trắng thừa
- Lệnh: `git diff --check`
- Exit code: `0`
- Kết quả: Sạch, không có khoảng trắng thừa hay lỗi định dạng diff.

## 4. Quyết định thiết kế và GIẢ ĐỊNH (D8)

1. PostgresCreativeUnitOfWork nhận thêm workspace_id (bắt buộc dạng keyword-only), correlation_id và actor tùy chọn, vì schema bảng migration 0015 có cột workspace_id NOT NULL trong khi giao diện port không mang workspace_id.
2. Cột angle_id của bảng cp_story_angles được lưu dưới dạng '<set_id>:<angle_id>' vì khóa chính của bảng là (workspace_id, angle_id), trong khi angle_id do mô hình sinh nội bộ có thể lặp lại giữa các bộ góc nhìn (story angle sets). Payload JSONB vẫn lưu giữ nguyên bản angle_id gốc.
3. PostgresCreativeOutboxWriter thực hiện INSERT trực tiếp vào bảng controlplane.cp_outbox_events trên cùng kết nối giao dịch của UoW thay vì gọi PostgresOutboxRepository, và gói adapter không import psycopg hay controlplane.infrastructure để thỏa mãn ràng buộc kiến trúc được kiểm tra bởi tests/unit/creative/test_d01_package_layout.py. Kết nối được lấy qua manager.borrow_connection() theo duck typing.
4. Cột event_id của sự kiện outbox được tạo xác định bằng uuid5(NAMESPACE_URL, deduplication_id). aggregate_revision được trích xuất từ phần sau dấu hai chấm cuối của chuỗi deduplication_id. Cột recovery_epoch ghi NULL theo quyết định OI-PERSIST-03. Cột schema_version ghi giá trị số chính 1 từ SCHEMA_VERSION.
5. Mọi thao tác INSERT trong các kho lưu trữ đều được bọc trong PostgreSQL SAVEPOINT (creative_insert), đảm bảo nếu xảy ra vi phạm ràng buộc duy nhất (mã lỗi SQL 23505) thì chỉ savepoint bị rollback và giải phóng, giao dịch chính của kết nối không bị đưa vào trạng thái hỏng (InFailedSqlTransaction).
6. Phương thức list_snapshots sắp xếp bản ghi theo created_at ASC, snapshot_id ASC để đảm bảo tính xác định vì bảng không có trường số thứ tự chèn riêng.
7. PostgresReceiptStore và PostgresCreativeOutboxWriter xác thực phạm vi workspace nghiêm ngặt: chỉ cho phép đọc và ghi dữ liệu thuộc workspace của Unit of Work hiện hành.

## 5. Mục mở và backlog (không chặn cổng)

1. Đề xuất Control cân nhắc miễn trừ quy tắc cấm import đối với src/creative/persistence/** trong test_d01_package_layout.py nếu muốn dùng trực tiếp PostgresOutboxRepository tại giai đoạn CP-4-WIRING.
2. Chưa có kịch bản kiểm thử cho tình huống hai kết nối đồng thời cùng ghi một revision (nhánh xử lý lỗi khóa chính đã được cài đặt nhưng chưa có integration test đa luồng riêng).
3. Thứ tự xử lý trường hợp cùng dấu mốc thời gian created_at trong list_snapshots hiện dựa vào snapshot_id.

## 6. Xác nhận phạm vi

- Không sửa đổi migration (src/controlplane/infrastructure/db/migrations/**), không tạo migration mới.
- Không sửa composition root, api wiring, lockfile, hay các tệp trong tests/m2.
- Không thêm bất kỳ thư viện hoặc gói phụ thuộc bên ngoài nào.
- Không chứa câu lệnh DDL (CREATE TABLE, ALTER TABLE, DROP TABLE) trong adapter.
- Toàn bộ thay đổi nằm trọn vẹn trong các đường dẫn được sở hữu (owned paths).