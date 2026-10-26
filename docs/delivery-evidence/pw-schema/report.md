# PW-SCHEMA: Migration 0019 cho nối dây

- Baseline commit (HEAD gốc): 4bfbcce95629061ae2625ecbd24c38587942ec72
- Task: PW-SCHEMA
- Milestone: M7

## Tệp tạo mới

- `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql`: Migration 0019 bỏ ràng buộc NOT NULL ở cột `job_id`, bổ sung cột `workflow_id TEXT NULL` và ràng buộc `CHECK (job_id IS NOT NULL OR workflow_id IS NOT NULL)` trên bảng `cp_stage_runs`; tạo ba bảng mới `cp_job_candidates`, `cp_creative_selections`, `cp_source_cycle_marks`.
- `src/controlplane/infrastructure/db/migrations/0019_prod_wiring.rollback.sql`: Migration rollback 0019 xoá ba bảng mới, xoá ràng buộc CHECK, xoá cột `workflow_id` và khôi phục `job_id SET NOT NULL` trên bảng `cp_stage_runs` đưa CSDL về 0018 sạch đối xứng.
- `tests/integration/prod_wiring/test_pw_schema_migration.py`: Bộ kiểm thử tích hợp 4 test kiểm chứng sự tồn tại tệp, tính hợp lệ của schema forward/rollback, ràng buộc khoá chính, duy nhất và CHECK trên CSDL PostgreSQL tạm.

## Dòng đã đổi

| Tệp | Dòng | Trước | Sau | Lý do |
| --- | --- | --- | --- | --- |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 1 | `'''CP-3-MIGRATIONS: kiểm chuỗi migration 0009..0018 (tĩnh và trên PostgreSQL 18.6 dùng một lần).'''` | `'''CP-3-MIGRATIONS: kiểm chuỗi migration 0009..0019 (tĩnh và trên PostgreSQL 18.6 dùng một lần).'''` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 22 | `18: '0018_control_ui_indexes'}` | `18: '0018_control_ui_indexes', 19: '0019_prod_wiring'}` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 158 | `assert sorted(int(name[:4]) for name in forward) == list(range(1, 19))` | `assert sorted(int(name[:4]) for name in forward) == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 162 | `assert len(list(MIGRATIONS_DIR.glob('*.rollback.sql'))) == 18` | `assert len(list(MIGRATIONS_DIR.glob('*.rollback.sql'))) == 19` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 330 | `assert_versions(dsn, 18)` | `assert_versions(dsn, 19)` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/convergence/test_cp3_migration_sequence.py` | 336 | `assert_versions(dsn, 18)` | `assert_versions(dsn, 19)` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/a/test_persist_a_postgres.py` | 236 | `assert versions == list(range(1, 19))` | `assert versions == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/b/test_persist_b_postgres.py` | 63 | `assert versions == list(range(1, 19)), f'unexpected applied migrations: {versions}'` | `assert versions == list(range(1, 20)), f'unexpected applied migrations: {versions}'` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/d/test_persist_d_postgres.py` | 75 | `assert [row[0] for row in versions] == list(range(1, 19))` | `assert [row[0] for row in versions] == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/d/test_persist_d_postgres.py` | 306 | `assert len(forward) == 18` | `assert len(forward) == 19` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/e/test_persist_e_postgres.py` | 96 | `assert versions == list(range(1, 19))` | `assert versions == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/f/test_persist_f_postgres.py` | 68 | `assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 19))` | `assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/g/test_persist_g_postgres.py` | 144 | `assert [r[0] for r in rows] == list(range(1, 19))` | `assert [r[0] for r in rows] == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/i/test_persist_i_postgres.py` | 95 | `assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 19))` | `assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |
| `tests/integration/persistence/j/test_persist_j_postgres.py` | 89 | `assert versions == list(range(1, 19))` | `assert versions == list(range(1, 20))` | Migration 0019 làm dãy từ 18 thành 19; không đổi tên hàm, không xoá test, không nới oracle |

Ghi chú: `tests/integration/persistence/c` không sửa vì không khoá số migration.

## Thiết kế và quyết định mặc định (D8)

- Ràng buộc khoá ngoại ghép `(workspace_id, job_id)` của bảng `cp_stage_runs` được giữ nguyên nguyên trạng; theo chuẩn PostgreSQL `MATCH SIMPLE`, khi `job_id` là NULL thì ràng buộc không kiểm tra bảng `cp_video_jobs`.
- Ba bảng mới (`cp_job_candidates`, `cp_creative_selections`, `cp_source_cycle_marks`) chỉ có ràng buộc khoá ngoại tới bảng `cp_workspaces`, không tạo khoá ngoại tới `cp_video_jobs` và không tạo khoá chính riêng cho cột `selection_id` vì acceptance criteria chỉ quy định các khoá đã nêu.
- File rollback không có lệnh `DELETE` hay `UPDATE`: nếu còn bản ghi `cp_stage_runs` chỉ có `workflow_id` mà `job_id` là NULL thì câu lệnh `ALTER COLUMN job_id SET NOT NULL` sẽ tự động thất bại (thiết kế fail-closed an toàn, không tự ý xoá dữ liệu).

## Lệnh đã chạy

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_schema_migration.py -q -p no:cacheprovider` (bước 5 - RED) | 1 | 4 failed (`test_files_exist_and_sequence_is_nineteen`, `test_stage_run_accepts_workflow_only_and_rejects_neither`, `test_new_tables_have_exact_columns_and_keys`, `test_rollback_restores_0018_and_forward_reapplies`) |
| `python -m pytest tests/integration/prod_wiring/test_pw_schema_migration.py -q -p no:cacheprovider` (bước 8 - GREEN) | 0 | 4 passed in 1.36s |
| `python -m pytest tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider` (bước 18) | 0 | 12 passed in 2.52s |
| `python -m pytest tests/integration/persistence -q -p no:cacheprovider` (bước 19) | 0 | 167 passed in 67.73s |
| `python -c "import pathlib, re; ps = sorted(pathlib.Path('tests/integration/persistence').glob('*/test_persist_*_postgres.py')); assert len(ps) == 9, ps; bad = [str(p) for p in ps if re.search('range[(]1, ?19[)]|len[(]forward[)] == 18', p.read_text(encoding='utf-8'))]; assert not bad, bad"` (bước 20) | 0 | passed (đủ 9 tệp, không còn `range(1, 19)` hay `len(forward) == 18`) |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/migrations/0019_prod_wiring.sql').read_text(encoding='utf-8').lower(); assert 'cp_job_candidates' in t and 'cp_creative_selections' in t and 'cp_source_cycle_marks' in t and 'workflow_id' in t, 'PW-SCHEMA'"` (bước 21) | 0 | passed (chứa đủ 3 bảng mới và cột `workflow_id`) |
| `git diff --check` (bước 23) | 0 | passed (sạch, không có lỗi whitespace hay định dạng) |

## Kết luận

Gói công việc PW-SCHEMA đã hoàn thành đầy đủ toàn bộ 5 yêu cầu nghiệm thu theo đúng kế hoạch IMPL-PLAN-PROD-WIRING-V4: migration 0019 và rollback 0018 đối xứng được tạo và kiểm thử hợp lệ; toàn bộ test chuỗi migration và test persistence được nâng từ 18 lên 19; tất cả các lệnh kiểm tra đều đạt mã thoát 0 mà không nới lỏng oracle hay xoá test.
