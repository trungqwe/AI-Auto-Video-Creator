# Báo cáo bằng chứng H-04

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `d6f0c277e1d921c36e0ba0553aca131ca6d991da` (d6f0c27)
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-04 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 8)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `94 failed, 5 passed in 0.70s`
- Chi tiết các dòng FAILED tiêu biểu từ bước 8:
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_workspace_condition_is_first_where_condition - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_batches_sql_matches_existing_query_shape - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_jobs_sql_with_filters_in_query_order - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_malicious_values_only_travel_in_params - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_desc_cursor_uses_less_than - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_asc_cursor_uses_greater_than - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_sort_key_outside_whitelist_is_rejected[created_at; DROP] - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_filter_outside_whitelist_is_rejected[workspace_id] - NotImplementedError: H-04 RED skeleton`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_list_spec_rejects_invalid_identifier[table-t; DROP] - Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_list_spec_rejects_inconsistent_spec[overrides0] - Failed: DID NOT RAISE ValueError`
  - `FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_fetch_page_returns_limit_items_and_next_cursor - NotImplementedError: H-04 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 5 test hợp lệ (`test_list_spec_is_frozen`, `test_shipped_specs_have_expected_shape`, `test_module_has_no_database_driver_and_no_offset`, `test_specs_match_control_api_queries[batches-spec0]`, `test_specs_match_control_api_queries[jobs-spec1]`) đã PASS ngay từ đầu. Tất cả 94 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý hoặc `Failed: DID NOT RAISE ValueError` đối với các validation của spec.

## GREEN

- Lệnh thực thi: `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` (chạy sau khi cài logic ở bước 11)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `99 passed in 0.09s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/infrastructure/db/projections/list_queries.py`: Chứa ListSpec frozen có validation whitelist định danh bảng và cột, build_list_sql sinh câu lệnh SQL tham số hóa an toàn với workspace_id đứng đầu WHERE và keyset cursor, fetch_page ánh xạ kết quả với datetime chuẩn hóa và build_page của H-02, cùng 2 spec định sẵn BATCHES_SPEC và JOBS_SPEC. Không import psycopg hay driver cơ sở dữ liệu, không dùng mệnh đề OFFSET.
  - `tests/integration/control_ui/test_h_list_queries_sql.py`: Bộ kiểm thử tích hợp 99 test cases sử dụng FakeConnection kiểm chứng toàn bộ hành vi SQL, keyset pagination, tham số hóa, ngăn chặn SQL injection, từ chối tham số/spec không hợp lệ, và đối chiếu AST với control_api_queries.py.
  - `docs/delivery-evidence/h-04/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` | 0 | `99 passed in 0.09s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. sort_columns của cả hai spec chỉ là created_at, khớp ORDER BY hiện có của batches()/jobs().
2. Hướng ORDER BY viết hoa ASC/DESC như truy vấn hiện có.
3. ListSpec thêm ValueError('invalid_spec') khi nhóm cột không phải tuple, sort rỗng hoặc id/sort không thuộc select_columns, vì build_page cần các trường đó trong item.
4. build_list_sql thêm ValueError('direction_invalid') và ValueError('limit_invalid') để không nội suy direction lạ và không dùng limit sai kiểu.
5. fetch_page đổi giá trị có isoformat (datetime) sang chuỗi để cursor H-02 (chỉ nhận str) dùng được và khớp _batch_row/_job_row.

## Ánh xạ phản ví dụ

- Nối chuỗi giá trị vào SQL: Đã loại trừ và kiểm chứng qua `test_malicious_values_only_travel_in_params` (giá trị lọc độc hại chỉ nằm trong params).
- Thiếu điều kiện workspace: Đã loại trừ và kiểm chứng qua `test_workspace_condition_is_first_where_condition` (workspace_id = %s luôn đứng đầu mệnh đề WHERE).
- Dùng OFFSET: Đã loại trừ và kiểm chứng qua `test_placeholders_match_params_and_no_offset` và `test_module_has_no_database_driver_and_no_offset` (không có mệnh đề OFFSET trong SQL sinh ra và không có từ khóa OFFSET trong module).
- Cột sort ngoài whitelist chạy được: Đã loại trừ và kiểm chứng qua `test_sort_key_outside_whitelist_is_rejected` và `test_filter_outside_whitelist_is_rejected` (raise ValueError('column_not_allowed')).

## coveredIds

- CT-API-001
- CT-API-002

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- YC-HT-H-04 nối build_list_sql/fetch_page vào control.py và control_api_queries.py thay LIMIT 100

## Giới hạn

- Không sửa postgres.py, control_api_queries.py, control.py, pyproject.toml.
- Không import psycopg; không kết nối PostgreSQL thật; không dùng mock để tuyên bố external gate PASS.
- Không chạy full suite, tests/m1, tests/m2.
