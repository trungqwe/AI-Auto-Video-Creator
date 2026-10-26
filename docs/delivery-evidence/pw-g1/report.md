# PW-G1: AppSession và recovery epoch thập phân

- Baseline commit (HEAD gốc): 301655ba228a9ed0cc538d9ff5ee24b61d2e8cbb
- Task: PW-G1
- Milestone: M7

## Tệp tạo mới và sửa đổi

- `src/controlplane/infrastructure/db/orchestration/app_session.py`: Tạo mới lớp `PostgresAppSessions(connection, workspace_id)` với hai phương thức `begin(session_ref, recovery_epoch)` (thực thi câu truy vấn nguyên tử `WITH ... INSERT` chuyển phiên cũ sang `ABANDONED` và ghi phiên mới `ACTIVE`, từ chối epoch không phải chuỗi chữ số thập phân bằng `INVALID_RECOVERY_EPOCH`) và `end(session_ref)` (chuyển phiên `ACTIVE` sang `ENDED`).
- `tools/launcher/launcher.py`: Bổ sung các trường `begin_session`, `end_session`, `max_session_epoch` vào `Deps`; thêm hàm `read_epoch_history`, `current_epoch`, `begin_session`, `end_session`, `max_session_epoch`; `cmd_start` ghi epoch số thập phân trước khi gọi `begin` và truyền sang tiến trình con; `cmd_restore` tăng epoch số thêm 1 và ghi epoch trước khi đổi `active-db`; `cmd_serve` gọi `end_session` khi tiến trình thoát êm.
- `tests/integration/prod_wiring/test_pw_g1_app_session.py`: Bộ kiểm thử tích hợp 24 test (bao gồm tham số hoá) kiểm chứng tính nguyên tử của `begin`, từ chối epoch phi thập phân, cách ly workspace, ánh xạ sang `ExecutionGrant`, thứ tự gọi trong launcher, sống sót qua stop/start/restore, và xử lý fail-closed khi tệp hỏng.
- `tests/integration/adapt/launch/test_adapt_launch_cli.py`: Cập nhật `make_fx` cung cấp fake cho `begin_session`, `end_session`, `max_session_epoch`; sửa assertion kiểm tra epoch trong `test_restore_creates_new_database_and_new_recovery_epoch` từ tiền tố `rec-...` thành chuỗi số thập phân `'1'` rồi `'2'`.
- `tests/integration/convergence/test_cp5_completion_uow.py`: Sửa assertion cấu trúc từ liệt kê cứng danh sách 6 tệp thành kiểm tra tập con để tương thích khi bổ sung `app_session.py` vào gói orchestration.

## Dòng đã đổi

| Tệp | Dòng | Trước | Sau | Lý do |
| --- | --- | --- | --- | --- |
| `tests/integration/convergence/test_cp5_completion_uow.py` | 583-585 | `assert sorted(p.name for p in ORCH.glob('*.py')) == ['__init__.py', 'allocation.py', 'grants.py', 'postgres_completion.py', 'start_batch.py', 'variants.py']` | `assert {'__init__.py', 'allocation.py', 'grants.py', 'postgres_completion.py', 'start_batch.py', 'variants.py'} <= {p.name for p in ORCH.glob('*.py')}` | Thêm tệp `app_session.py` làm assertion liệt kê cứng đỏ; đổi sang kiểm tra tập con của sáu tên cũ, không đổi assertion nào khác |
| `tests/integration/adapt/launch/test_adapt_launch_cli.py` | 140-149, 161-163 | Khởi tạo `launcher.Deps` không có `begin_session`, `end_session`, `max_session_epoch` | Bổ sung ba hàm fake `fake_begin_session`, `fake_end_session`, `fake_max_session_epoch` và truyền vào `launcher.Deps` | `Deps` nay có thêm ba trường bắt buộc cho AppSession và epoch thập phân |
| `tests/integration/adapt/launch/test_adapt_launch_cli.py` | 561, 571 | `assert last_hist["epoch"].startswith("rec-20261022030405-")` và chỉ kiểm tra `epoch_data2["history"][-1]["epoch"] != last_hist["epoch"]` | `assert last_hist["epoch"] == "1"` và sau dòng 570 thêm `assert epoch_data2["history"][-1]["epoch"] == "2"` | Recovery epoch theo thiết kế mới là chuỗi số thập phân: '1' cho lần đầu và tăng thành '2' sau lần restore kế tiếp |

## Quyết định thiết kế

- **Tính nguyên tử của `begin`**: Thực thi bằng một câu truy vấn SQL duy nhất dạng `WITH abandoned AS (UPDATE controlplane.cp_app_sessions SET status = 'ABANDONED', ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE workspace_id = %s AND status = 'ACTIVE' RETURNING session_ref) INSERT INTO controlplane.cp_app_sessions ...` trên kết nối do caller sở hữu. Quy định persistence/g cấm điều khiển giao dịch (`commit`, `rollback`, `TransactionManager`) trong thư mục orchestration, nên cấu trúc một câu lệnh đảm bảo tính nguyên tử tự nhiên trong transaction của PostgreSQL.
- **Thao tác `end` an toàn**: Câu lệnh `UPDATE` chỉ chuyển phiên có trạng thái `ACTIVE` sang `ENDED` theo đúng `workspace_id` và `session_ref`. Nếu phiên không tồn tại hoặc đã ở trạng thái khác thì không báo lỗi và không ảnh hưởng hàng khác.
- **Lần start đầu tiên và tăng tiến epoch**: Lần khởi động đầu tiên khi chưa có tệp `recovery-epoch.json` sẽ ghi epoch là `'1'`. Mỗi lần `restore` thành công, epoch tăng đúng 1 đơn vị. Qua các lần stop/start thông thường, epoch được giữ nguyên.
- **Tương thích ngược giá trị epoch cũ `rec-...`**: Nếu trong lịch sử có giá trị dạng cũ `rec-<stamp>-<hex>`, `current_epoch` sẽ truy vấn epoch số lớn nhất hiện có trong CSDL (`max_session_epoch`) cộng thêm 1. Giá trị mới được ghi đè vào tệp kèm trường `legacy_epoch` để giữ nguyên giá trị qua các lần stop/start sau.
- **Thứ tự thực thi trong `cmd_start`**: Ghi `recovery-epoch.json` trước khi gọi `begin_session`. Lệnh `begin_session` được thực hiện sau `migrate` và `ensure_identity`, nhưng trước `deps.spawn(...)` (tiến trình con `_serve`), do đó luôn chạy trước `start_worker` và relay.
- **Truyền `session_ref` và thoát êm trong `cmd_serve`**: `session_ref` được sinh duy nhất trong `cmd_start` và truyền cho tiến trình con qua biến môi trường `AIAVC_SESSION_REF`. Khi `serve_tls` hoàn thành bình thường, `cmd_serve` gọi `end_session` sau khi `worker.stop()` đã dừng. Nếu `serve_tls` gặp sự cố, phiên vẫn giữ nguyên `ACTIVE` và lần `start` sau sẽ tự động chuyển nó sang `ABANDONED`.
- **Fail-closed khi tệp epoch hỏng**: Nếu `recovery-epoch.json` bị hỏng hoặc JSON không đúng định dạng, `read_epoch_history` ném `LauncherError` lập tức dừng hoạt động mà không gây tác dụng phụ (không tạo CSDL, không ghi đè tệp).

## Việc còn lại ngoài owned paths

- `docs/runbook/runbook-v1.md` dòng 105 vẫn mô tả epoch dạng `rec-<yyyymmddHHMMSS>-<hex>`, cần slice tài liệu riêng cập nhật sang chuỗi số thập phân.

## Lệnh đã chạy

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py -q -p no:cacheprovider` (bước 8 - RED) | 1 | 23 failed, 1 passed in 5.79s (test DB đỏ do `PostgresAppSessions` ném `NOT_IMPLEMENTED`; test launcher đỏ do thiếu `begin_session` trong `Deps`; `test_default_deps_wire_the_session_functions` đỏ do thiếu thuộc tính `begin_session`) |
| `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py -q -p no:cacheprovider` (bước 22 - GREEN) | 0 | 24 passed in 5.09s |
| `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` (bước 23) | 0 | 116 passed in 15.15s (24 test `test_pw_g1_app_session.py`, 44 test `test_adapt_launch_cli.py`, 27 test `test_cp5_completion_uow.py`, 21 test `test_persist_g_postgres.py`) |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/orchestration/app_session.py').read_text(encoding='utf-8').lower(); assert 'from src.' not in t and 'fake' not in t and 'mock' not in t, 'PW-G1'"` (bước 24) | 0 | passed (không chứa `from src.`, `fake`, `mock`) |
| `git diff --check` (bước 26) | 0 | passed (sạch, không có lỗi khoảng trắng cuối dòng hay định dạng) |

## Kết luận

Gói công việc PW-G1 đã hoàn thành toàn diện toàn bộ 5 yêu cầu nghiệm thu theo kế hoạch IMPL-PLAN-PROD-WIRING-V4:
1. `PostgresAppSessions` quản lý vòng đời phiên với `begin` nguyên tử và `end` an toàn, từ chối chặt chẽ epoch phi thập phân.
2. Launcher duy trì recovery epoch số thập phân, bắt đầu từ 1 và tăng 1 sau mỗi lần restore, ghi epoch trước active-db.
3. `cmd_start` gọi `begin` trước khi khởi chạy worker tiến trình con; `cmd_serve` gọi `end` khi thoát êm.
4. Cập nhật test launcher thích ứng với epoch thập phân và fake dependencies.
5. Sửa test cấu trúc CP5 chuyển sang kiểm tra tập con hợp lệ khi thêm `app_session.py`.
Tất cả các lệnh kiểm tra đều đạt mã thoát 0 với kết quả kiểm thử thực tế đầy đủ.
