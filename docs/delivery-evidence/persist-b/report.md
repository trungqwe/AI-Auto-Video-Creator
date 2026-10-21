# Báo cáo chuyển giao: PERSIST-B

## 1. Trạng thái
- Trạng thái: BLOCKED, chưa cài adapter, không đánh dấu PASS.

## 2. Lệnh đã chạy và kết quả kiểm thử
- Lệnh kiểm: `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider`
- Exit code: 1 (RED hợp lệ theo đúng oracle kiểm tra cột dữ liệu)
- Đoạn output thật (đã ẩn DSN và thông tin xác thực):

```text
F                                                                        [100%]
================================== FAILURES ===================================
_________ test_migration_0013_dedup_policy_revision_fits_string_port __________

migrated_dsn = '<redacted_dsn>'

    def test_migration_0013_dedup_policy_revision_fits_string_port(migrated_dsn: str) -> None:
        '''ResolutionRepository.get v\xe0 dedup_evidence nh\u1eadn dedup_policy_revision ki\u1ec3u str (ports.py:27, binding a-b-collected-document.json:151).'''
        with psycopg.connect(migrated_dsn, autocommit=True) as connection:
            types = dict(connection.execute(
                'SELECT table_name, data_type FROM information_schema.columns '
                'WHERE table_schema = %s AND column_name = %s AND table_name IN (%s, %s)',
                ('controlplane', 'dedup_policy_revision', 'cp_collected_document_resolutions', 'cp_dedup_evidence'),
            ).fetchall())
>       assert types == {'cp_collected_document_resolutions': 'text', 'cp_dedup_evidence': 'text'}, types
E       AssertionError: {'cp_collected_document_resolutions': 'bigint', 'cp_dedup_evidence': 'bigint'}
E       assert {'cp_collecte...ce': 'bigint'} == {'cp_collecte...ence': 'text'}
E
E         Differing items:
E         {'cp_dedup_evidence': 'bigint'} != {'cp_dedup_evidence': 'text'}
E         {'cp_collected_document_resolutions': 'bigint'} != {'cp_collected_document_resolutions': 'text'}
E         Use -v to get more diff

tests/integration/persistence/b/test_persist_b_postgres.py:52: AssertionError
=========================== short test summary info ===========================
FAILED tests/integration/persistence/b/test_persist_b_postgres.py::test_migration_0013_dedup_policy_revision_fits_string_port
1 failed in 0.87s
```

## 3. Bằng chứng DEPENDENCY_GAP
- Bằng chứng DEPENDENCY_GAP: src/controlplane/infrastructure/db/migrations/0013_ingestion.sql:36 và :47 khai dedup_policy_revision BIGINT trong cp_collected_document_resolutions và cp_dedup_evidence; src/ingestion/application/ports.py:27 khai dedup_policy_revision: str; docs/parallel-delivery/bindings/a-b-collected-document.json:151 khai type string; giá trị thật là 'dedup-policy-r1' (tests/unit/ingestion/test_ingestion_resolve_document.py:31) và 'dedup-policy-b12-r1' (tests/integration/ingestion/fixtures/ingestion_corpus_v1.json:8); src/ingestion/application/resolve_document.py:332-333 bắt buộc policy_revision là str không rỗng.

## 4. Counterexample
- Counterexample: INSERT giá trị 'dedup-policy-r1' vào cột BIGINT bị PostgreSQL từ chối; mọi phép ánh xạ chuỗi sang BIGINT (băm, lấy chữ số) hoặc không đơn ánh (r1 của hai chính sách khác nhau trùng 1) hoặc là workaround ngoài quyền nên không dùng.

## 5. Mục theo dõi khác cho Control
- Mục theo dõi khác cho Control, chưa phải kết luận chặn của slice: record kind 'article_media_attachment' (src/ingestion/application/resolve_document.py:47, dùng ở dòng 107 và 225) và 'activity_result' (src/ingestion/application/activity_handler.py:30, dùng ở dòng 225 và 236) được use case gọi qua uow.records nhưng 0013 không có bảng cho hai kind này, còn acceptance chỉ cho bốn kind và từ chối kind lạ; cần quyết định ở CP-3-MIGRATIONS trước khi nối wiring.

## 6. Đề xuất cho chủ CP-3-MIGRATIONS
- Đề xuất cho chủ CP-3-MIGRATIONS: đổi dedup_policy_revision của hai bảng sang TEXT NOT NULL trong 0013_ingestion.sql (khóa chính của cp_collected_document_resolutions giữ nguyên ba cột) và quyết định chỗ lưu hai kind còn lại; sau đó mở lại PERSIST-B.

## 7. Phạm vi đã sửa
- Phạm vi đã sửa: chỉ hai tệp trong owned paths. Sau khi ghi, đọc lại tệp và xác nhận chữ có dấu còn nguyên.
