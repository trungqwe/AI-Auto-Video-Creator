# Báo cáo Nghiệm thu Phân trang Keyset (CP-4-PAGINATION)

## 1. Phạm vi Thực hiện

Gói công việc CP-4-PAGINATION thay thế chuỗi cứng `LIMIT 100` và literal `"next_cursor": None` bằng phân trang keyset cho bốn danh sách trong Control API (`operations`, `batches`, `jobs`, `configs`).

Danh sách 6 tệp thuộc sở hữu (owned paths) được chỉnh sửa và tạo mới:
- `src/controlplane/infrastructure/db/control_api_queries.py`
- `src/controlplane/application/control_api/query_ports.py`
- `src/controlplane/api/routes/control.py`
- `tests/integration/control_ui/test_h_list_queries_sql.py`
- `tests/integration/convergence/test_cp4_pagination_postgres.py`
- `docs/delivery-evidence/cp-4-pagination/report.md`

Cam kết tuân thủ ranh giới:
- Không sửa đổi `list_queries.py`, `list_query.py`, `control_api_commands.py`.
- Không sửa đổi hoặc thêm mới bất kỳ tệp migration nào.
- Không sửa đổi các tệp trong thư mục `tests/m2`.

## 2. Kết quả Kiểm thử RED (Test-First)

### Bước 9: Kiểm thử unit / AST và route list_queries SQL
- **Lệnh chạy:** `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider`
- **Exit code:** `1`
- **Oracle:** Thất bại đúng kỳ vọng do assertion AST (kiểm `fetch_page`, `BATCHES_SPEC`, `JOBS_SPEC`, không còn `LIMIT 100`), kiểm `next_cursor` literal, lỗi HTTP 500 thay vì 200/422 ở route, và `TypeError` do thiếu tham số `query` ở `operations` và `configs`. Không có lỗi `ImportError` hay lỗi thu thập test (collection error).
- **3 dòng FAILED đầu tiên:**
  ```
  FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_specs_match_control_api_queries[batches-BATCHES_SPEC]
  FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_specs_match_control_api_queries[jobs-JOBS_SPEC]
  FAILED tests/integration/control_ui/test_h_list_queries_sql.py::test_control_api_queries_imports_fetch_page_and_specs_from_projection_module
  ```
- **Dòng tóm tắt:** `77 failed, 98 passed, 1 warning in 1.95s`

### Bước 10: Kiểm thử phân trang trên PostgreSQL 18.6 thật
- **Lệnh chạy:** `python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider`
- **Exit code:** `1`
- **Oracle:** Seed thành công 230 dòng cho mỗi bảng (`cp_command_receipts`, `cp_production_batches`, `cp_video_jobs`, `cp_config_revisions`) trên database tạm thời của PostgreSQL 18.6 thật; thất bại đúng kỳ vọng vì `PostgresControlQueries` chưa nhận tham số `query: ListQuery` (`TypeError: PostgresControlQueries.operations() got an unexpected keyword argument 'query'`). Không gặp lỗi kết nối hay lỗi schema/seed.
- **3 dòng FAILED đầu tiên:**
  ```
  FAILED tests/integration/convergence/test_cp4_pagination_postgres.py::test_walk_returns_every_row_once_newest_first[operations-25]
  FAILED tests/integration/convergence/test_cp4_pagination_postgres.py::test_walk_returns_every_row_once_newest_first[operations-100]
  FAILED tests/integration/convergence/test_cp4_pagination_postgres.py::test_walk_returns_every_row_once_newest_first[batches-25]
  ```
- **Dòng tóm tắt:** `16 failed in 6.65s`

## 3. Kết quả Kiểm thử GREEN

Tất cả các lệnh kiểm tra sau khi hoàn tất cài đặt đều đạt Exit code 0:

- **Bước 19:** `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider`
  - Exit code: `0`
  - Kết quả: `175 passed, 1 warning in 1.04s`

- **Bước 20:** `python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider`
  - Exit code: `0`
  - Kết quả: `16 passed in 6.41s` (chạy trên PostgreSQL 18.6 thật, 4 tài nguyên x 2 limit 25 & 100 duyệt đủ 230 dòng không trùng lặp, thứ tự asc/desc chuẩn xác, ranh giới trang chuẩn xác, không có test bị skip).

- **Bước 21:** `python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider`
  - Exit code: `0`
  - Kết quả: `826 passed, 1 warning in 1.90s`

- **Bước 22:** `python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression`
  - Exit code: `0`
  - Kết quả: `179 passed, 1 deselected, 2 warnings in 205.74s (0:03:25)` (GET /v1/operations rỗng vẫn giữ nguyên dạng `{"items": [], "next_cursor": None}`).

- **Bước 23:** `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
  - Exit code: `0`
  - Kết quả: `130 passed, 28 skipped, 1 warning in 1.83s`

- **Bước 24:** Probe tĩnh kiểm tra mã nguồn:
  - **Lệnh chạy:** `python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c = pathlib.Path('src/controlplane/api/routes/control.py').read_text(encoding='utf-8'); assert 'LIMIT 100' not in q and 'fetch_page' in q, 'keyset replaces LIMIT 100'; assert chr(34) + 'next_cursor' + chr(34) + ': None' not in c and 'parse_list_query' in c, 'next_cursor from ListQuery'"`
  - Exit code: `0`
  - Kết quả: Không có lỗi assertion, xác nhận sạch hoàn toàn chuỗi `LIMIT 100` và literal `"next_cursor": None`.

- **Bước 26:** `git diff --check`
  - Exit code: `0`
  - Kết quả: Không có cảnh báo khoảng trắng thừa hay lỗi xuống dòng.

## 4. Bảng Trạng thái Phụ thuộc và Mục Mở

| Mã mục | Trạng thái | Chi tiết và Căn cứ |
| --- | --- | --- |
| `BL-CV-12` | **DONE** | Bước 20 đã chạy hoàn toàn xanh trên PostgreSQL 18.6 thật (`16 passed in 6.41s`). Phạm vi sở hữu của gói CP-4-PAGINATION bao phủ cả `control_api_queries.py` và `control.py`. Migration `0018_control_ui_indexes.sql` đã cung cấp đầy đủ các index keyset cần thiết: `cp_production_batches_keyset_idx`, `cp_video_jobs_keyset_idx`, `cp_command_receipts_keyset_idx`. |
| `OI-EXT-UI-03` | **OPEN** | Bảng `cp_config_revisions` chưa có index keyset riêng (migration 0018 chưa có). Gói CP-4-PAGINATION tuân thủ kỷ luật không tự ý tạo migration mới; ghi nhận mở và đề xuất triển khai index này tại một slice migration riêng biệt. |

## 5. Các Mẫu Giữ Nguyên

- **Thứ tự mặc định:** Mới nhất trước (`direction="desc"`). Client không gửi tham số `direction` thì hệ thống luôn trả bản ghi theo thứ tự giảm dần.
- **Giới hạn số lượng bản ghi:** Mặc định `limit=50`, cận trên tối đa `100`.
- **Xử lý tham số lỗi:** Mọi tham số không hợp lệ (sort không được phép, filter ngoài whitelist, limit <= 0 hoặc > 100, cursor hỏng) đều được `parse_list_query` bắt và chuyển thành `ValueError`, dẫn tới phản hồi HTTP `422 Unprocessable Entity` qua middleware.
- **Tính tương thích ngược:** Phản hồi rỗng giữ nguyên khuôn mẫu `{"items": [], "next_cursor": None}`.

## 6. Giới hạn và Điểm Dừng

- Kết quả kiểm thử phân trang đã được chứng minh trực tiếp trên `PostgresControlQueries` với phiên bản PostgreSQL 18.6 thật qua fixture disposable database.
- Cổng sản xuất vẫn duy trì trạng thái khóa (`PRODUCTION_ACTIVATION_BLOCKED`).
- Test `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` được hoãn sang milestone CP7 theo phê duyệt của người dùng ngày 21/10/2026.
