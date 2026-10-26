# Báo cáo PW-H0

## 1. Phạm vi
Tạo mới `tests/integration/prod_wiring/conftest.py`, `tests/integration/prod_wiring/pw_support.py`, `tests/integration/prod_wiring/test_pw_h0_harness.py` và báo cáo này. Không sửa `src/**`, migration, lockfile hay tệp ngoài owned paths.

## 2. Thiết kế
- `pw_database`: tạo CSDL tạm `pw_<hex8>` từ `M2_TEST_PG_DSN`, chạy `MigrationRunner(..., is_test_env=True, expected_database_name=...)`, seed một workspace và một actor, `DROP DATABASE ... WITH (FORCE)` trong `finally`. Thiếu DSN hoặc DSN không phải loopback thì `pytest.fail('BLOCKED_EXTERNAL: ...')`, không skip.
- `pw_temporal`: bọc `WorkflowEnvironment.start_time_skipping()` và trả client; test chạy workflow echo ngủ 1 giờ và xong trong vài giây.
- CT-WF-001: test đối chiếu `WORKFLOW_CATALOG` và `WORKFLOW_NAMES` với sáu workflow logic trong `docs/09-contracts/03-workflow-and-execution.md`, rồi chạy sáu workflow echo trên `pw_temporal` theo đúng tên catalog. Sáu class echo khai báo ở cấp module vì temporalio từ chối class cục bộ (`@workflow.run` trên class trong hàm). Docstring test khai báo `coveredIds: PW-H0-01, CT-WF-001`.
- `pw_support.py`: `FakeRouter`, `FakeDrive`, `FakeKokoro`, `FakeAligner`, `FakeGpu` ghi lại mọi lời gọi (kể cả lời gọi lỗi); `assert_no_support_import(root)` quét AST, fail-closed.

## 3. Lệnh đã chạy
| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_h0_harness.py -q -p no:cacheprovider` | 0 | 34 passed in 2.50s |
| probe conftest (`BLOCKED_EXTERNAL` có, `pytest.skip` không) | 0 | PASS: conftest.py chứa BLOCKED_EXTERNAL và không chứa pytest.skip |
| probe không tệp src nào nhắc `pw_support` | 0 | PASS: không có tệp nào dưới src/ chứa tham chiếu pw_support |
| `git diff --check` | 0 | PASS: không phát hiện lỗi khoảng trắng |

Ghi rõ: lần chạy lại `git diff --check` sau khi ghi báo cáo và sau `git add` được nêu trong `worker_done`.

## 4. Oracle
Hai test dùng hai CSDL khác tên và cả hai bị xoá (kiểm bằng `pg_database` ở teardown module); DSN không loopback bị từ chối mà không lộ mật khẩu; `assert_no_support_import` đỏ trên 8 biến thể import trong `tmp_path` và xanh trên `src/` thật. Ghi rõ đây là slice harness nên RED nằm trong chính các test phản ví dụ (import giả định trong tmp_path), không có RED trước-triển-khai riêng.

## 5. Giới hạn
Kết quả chỉ chứng minh khung kiểm thử trên PostgreSQL 18.6 loopback và máy chủ test time-skipping của temporalio; các fake chưa trả dữ liệu miền nào ngoài giá trị do test cấu hình; không đóng cổng sản xuất.
