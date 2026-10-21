# Báo cáo CP-3-MIGRATIONS: migration 0009 đến 0018

## 1. Quy ước viết SQL (Q)

Q1. Mọi tệp migration dùng UTF-8, dòng LF, mỗi câu lệnh kết thúc bằng `;`. Cấm `BEGIN`, `COMMIT` (MigrationRunner đã bọc giao dịch), `CREATE EXTENSION`, `CONCURRENTLY`, `DROP SCHEMA`, `CASCADE` và từ `vector`. Từ khóa SQL viết HOA. Tạo bảng đúng dạng `CREATE TABLE controlplane.<tên> (` (không `IF NOT EXISTS`).
Q2. Mọi đối tượng có tiền tố `controlplane.`; tên bảng, function, trigger, index, constraint bắt đầu bằng `cp_`.
Q3. Cú pháp cột trong lệnh làm việc: `tên`, `tên:KIỂU`, `tên?` (cho phép NULL) hoặc `tên?:KIỂU`. Kiểu mặc định theo tên: `workspace_id` = `UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT`; tên kết thúc `_at` = TIMESTAMPTZ; kết thúc `_date` = DATE; `payload` và tên kết thúc `_refs` hoặc `_json` = JSONB; `revision`, `attempt_index`, `sequence_no`, `units`, `credential_version`, `revocation_version`, `execution_generation` và tên kết thúc `_bytes` = BIGINT; tên bắt đầu `is_` = BOOLEAN; còn lại TEXT. Không có dấu `?` thì NOT NULL. Cột `revision` luôn kèm `CHECK (revision >= 1)`. `DEFAULT x` hoặc `CHECK (...)` ghi trong lệnh làm việc thì chép nguyên văn vào cột đó.
Q4. Mọi bảng mới có thêm `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP` ở cuối; bảng ghi 'mutable' có thêm `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`; không thêm nếu lệnh đã liệt kê cột trùng tên.
Q5. Khóa ngoại chỉ tới `cp_workspaces` và tới đích ghi rõ `FK→`. Không FK chéo phân hệ, không FK giữa các bảng AO; các phân hệ tham chiếu nhau bằng chuỗi.
Q6. Bảng AO (append-only): trong cùng migration tạo một function theo khuôn `cp_reject_artifact_version_mutation` của 0005: `CREATE FUNCTION controlplane.<fn>() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '<thông điệp tiếng Anh không chứa ký tự phần trăm>'; END; $$;`, rồi mỗi bảng AO có `CREATE TRIGGER <bảng>_append_only BEFORE UPDATE OR DELETE ON controlplane.<bảng> FOR EACH ROW EXECUTE FUNCTION controlplane.<fn>();`.
Q7. Rollback chỉ gỡ đối tượng của đúng migration cùng số, theo thứ tự ngược: hoàn nguyên ALTER và DROP INDEX trước, rồi `DROP TABLE IF EXISTS controlplane.<bảng>;` cho từng bảng do chính migration tạo (bảng con trước bảng cha, không CASCADE), cuối cùng `DROP FUNCTION IF EXISTS controlplane.<fn>();`. Không gỡ bảng, cột hay index của migration khác.
Q8. Mẫu RECEIPT: cột `workspace_id`, `idempotency_key`, `request_hash`, `aggregate_ref`, `aggregate_revision:BIGINT CHECK (aggregate_revision >= 1)`; PRIMARY KEY (workspace_id, idempotency_key).
Q9. Mẫu RECORD: cột `workspace_id`, `record_key`, `revision`, `payload`; PRIMARY KEY (workspace_id, record_key, revision). Cột bổ sung của từng bảng ghi sau chữ RECORD+.

## 2. RED trước implementation

Lệnh kiểm đã chạy tại bước 9:
`
python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider
`
Exit code: 1 (thất bại theo đúng kỳ vọng của oracle RED).

Trích nguyên văn các dòng FAILED và assert từ pytest:
`
FFFFFF.F                                                                 [100%]
================================== FAILURES ===================================
___________________________ test_sequence_and_pairs ___________________________

    def test_sequence_and_pairs():
        forward = [p.name for p in MIGRATIONS_DIR.iterdir() if re.fullmatch('[0-9]{4}_[a-z0-9_]+[.]sql', p.name)]
>       assert sorted(int(name[:4]) for name in forward) == list(range(1, 19))
E       assert [1, 2, 3, 4, 5, 6, ...] == [1, 2, 3, 4, 5, 6, ...]
E
E         Right contains 10 more items, first extra item: 9
E         Use -v to get more diff

tests\integration\convergence\test_cp3_migration_sequence.py:158: AssertionError
___________________ test_expected_tables_and_columns_in_sql ___________________

    def test_expected_tables_and_columns_in_sql():
        assert sorted(EXPECTED) == list(range(9, 18))
        for number, tables in EXPECTED.items():
>           sql = strip(sql_of(number))
E       FileNotFoundError: [Errno 2] No such file or directory: '.../0009_config_security_extensions.sql'

tests\integration\convergence\test_cp3_migration_sequence.py:168: FileNotFoundError
__________________ test_postgres_up_down_up_and_constraints ___________________

    def test_postgres_up_down_up_and_constraints():
        name = f'm2_p1_test_{uuid.uuid4().hex[:8]}'
        admin = psycopg.connect(PG_DSN, autocommit=True)
        try:
            assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
            admin.execute(f'CREATE DATABASE {name}')
            dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
            runner = MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name)
            runner.migrate_up()
>           assert_versions(dsn, 18)
...
E       assert [1, 2, 3, 4, 5, 6, ...] == [1, 2, 3, 4, 5, 6, ...]
E
E         Right contains 10 more items, first extra item: 9
E         Use -v to get more diff

tests\integration\convergence\test_cp3_migration_sequence.py:280: AssertionError
=========================== short test summary info ===========================
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_sequence_and_pairs
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_expected_tables_and_columns_in_sql
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_rollback_drops_only_own_objects
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_forbidden_constructs_absent
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_0018_only_keyset_indexes
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_append_only_tables_have_reject_trigger
FAILED tests/integration/convergence/test_cp3_migration_sequence.py::test_postgres_up_down_up_and_constraints
7 failed, 1 passed in 0.72s
`

Giải thích: Đây là RED đúng oracle theo yêu cầu kiểm thử chuỗi migration: test suite đã kết nối thành công tới PostgreSQL 18.6 trên container ai-auto-video-m2-pg, tạo database thử nghiệm m2_p1_test_<hex>, thực thi migrate_up qua các migration hiện hành [1..8] và xác nhận chuỗi phiên bản quan sát được là [1..8] so với kỳ vọng [1..18] khi chưa tạo các tệp migration 0009..0018. Lỗi hoàn toàn là AssertionError và FileNotFoundError của migration mới, không phải do thiếu file test, lỗi cú pháp hay ImportError.

## 3. GREEN

Kết quả chạy thành công của các lệnh kiểm bắt buộc:

1. Bước 30: Kiểm thử chuỗi 10 migration mới trên cơ sở dữ liệu PostgreSQL 18.6 dùng một lần:
- Lệnh: python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider
- Exit code: 0
- Kết quả nguyên văn:
`
8 passed in 1.45s
`

2. Bước 31: Kiểm tra cổng M2 regression:
- Lệnh: python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider
- Exit code: 0
- Kết quả nguyên văn:
`
6 passed in 3.00s
`

3. Bước 32: Bộ kiểm thử đơn vị và tích hợp bắt buộc của các phân hệ:
- Lệnh: python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/storage tests/unit/security tests/integration/orchestration tests/integration/control_ui -q -p no:cacheprovider
- Exit code: 0
- Kết quả nguyên văn:
`
5093 passed, 2165 subtests passed in 7.72s
`

4. Bước 33: Kiểm tra định dạng khoảng trắng thừa của git diff:
- Lệnh: git diff --check
- Exit code: 0
- Kết quả nguyên văn: Không có lỗi khoảng trắng thừa, output hoàn toàn sạch.

## 4. Xác nhận tests/m2/test_p9_m2_exit_gate.py

Bộ test cổng thoát M2 tại tests/m2/test_p9_m2_exit_gate.py đạt tuyệt đối 6/6 test PASS:
- test_tst_m2_p9_001_m2_manifest_and_gate_evaluation PASSED
- test_tst_m2_p9_002_artifact_tamper_detection PASSED
- test_tst_m2_p9_003_m1_regression_suite_93_tests PASSED
- test_tst_m2_p9_004_secret_scanner_clean_and_fail_closed_canary PASSED
- test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db PASSED
- test_tst_m2_p9_006_m2_exit_gate_and_audit_report PASSED

Cổng M2 vẫn duy trì màu xanh khi số lượng migration tăng từ 8 lên 18 là nhờ giải pháp CP-2C-M2-REGRESSION: hàm kiểm thử test_tst_m2_p9_005 đếm số migration động trong thư mục src/controlplane/infrastructure/db/migrations và ghim chặt bảng mã băm SHA-256 của các migration gốc 0001..0008, do đó việc mở rộng các migration tiếp theo không phá vỡ tính bất biến của các mốc M2 đã nghiệm thu.

## 5. Quyết định, giả định và việc chuyển giao

(a) Mười cặp tệp migration và rollback 0009..0018 tuân thủ đầy đủ định nghĩa theo bảng plan.md mục 5.2.
(b) Bổ sung bảng cp_source_command_receipts ở migration 0012 phục vụ ReceiptStore của phân hệ PERSIST-A.
(c) Cột khóa phục vụ phân trang keyset của migration 0018 cho cp_production_batches và cp_video_jobs sử dụng batch_id và job_id (không phải id), đồng bộ với schema 0006.
(d) Thiết kế lai: các cột khóa, định danh và trường truy vấn được lưu thành cột riêng biệt kết hợp với cột payload JSONB chứa toàn bộ trường nghiệp vụ còn lại; đây là GIẢ ĐỊNH có hiệu lực cho tới khi các slice PERSIST chi tiết xác nhận.
(e) Cột recovery_epoch tại các bảng cp_cleanup_authorizations (0010), cp_stage_runs (0011) và cp_app_sessions (0011) đã được chuyển thành kiểu TEXT với ràng buộc CHECK (btrim(recovery_epoch) <> ''); riêng cột recovery_epoch tại bảng cp_outbox_events (0003) được giữ nguyên kiểu BIGINT theo quyết định kiến trúc OI-PERSIST-03.
(f) Trong kịch bản rollback của 0010 và 0011, thao tác hoàn nguyên cột recovery_epoch về lại BIGINT sử dụng ép kiểu USING recovery_epoch::bigint, do đó chỉ hoạt động trơn tru khi mọi giá trị đã lưu là chuỗi số (phù hợp với môi trường cơ sở dữ liệu kiểm thử dùng một lần).
(g) Các adapter hiện có trong src/** hiện vẫn ghi hoặc so sánh recovery_epoch dưới dạng kiểu số; việc chuyển sang kiểu chuỗi str() thuộc phạm vi bàn giao của các slice tiếp theo (PERSIST-G và PERSIST-I), slice này tuyệt đối không can thiệp vào các tệp ngoài owned paths.
