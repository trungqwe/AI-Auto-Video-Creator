# Báo cáo bằng chứng chuyển giao: ADAPT-LAUNCH

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `tools/launcher/docker-compose.yml`: Ngăn xếp Docker Compose định nghĩa 3 dịch vụ (`postgres`, `temporal-schema`, `temporal`). Cả 3 dịch vụ đều được ghim cứng theo mã băm SHA-256 đối chiếu khớp 100% với `tools/runtime/runtime.lock.json` (`pins.postgresql_image.sha256` và `pins.temporal_server_binary.sha256`). Mọi cổng dịch vụ đều bind duy nhất trên giao diện loopback `127.0.0.1` (`127.0.0.1:57028:5432` và `127.0.0.1:7233:7233`), sử dụng thể tích lưu trữ đặt tên `aiavc_pgdata`, không bind mount ổ đĩa máy chủ, không mở giao diện web Temporal UI hay cổng HTTP ngoại lai, và không chứa chuỗi ký tự `0.0.0.0`.
- `tools/launcher/launcher.py`: Công cụ CLI quản lý vòng đời và vận hành hệ thống. Ở cấp độ module chỉ import các thư viện thuộc chuẩn Python stdlib. Bao gồm đầy đủ 7 lệnh quản lý công khai (`start`, `stop`, `down`, `status`, `backup`, `restore`, `oauth`) và 1 lệnh nội bộ phục vụ ngầm (`_serve`). Cơ chế bảo mật tuyệt đối không in mật khẩu, DSN, hoặc URL capability ra console hay nhật ký. Lệnh `stop` chỉ báo dừng worker và không chạm vào Docker; lệnh `down` gỡ container nhưng giữ nguyên dữ liệu volume; lệnh `backup` dùng `pg_dump` qua `docker exec` kèm tệp sidecar sha256; lệnh `restore` tạo CSDL mới với recovery epoch mới mà không xóa CSDL cũ; lệnh `oauth` hướng dẫn người dùng từng bước bằng tiếng Việt và lưu trữ token an toàn vào kho DPAPI.
- `docs/runbook/runbook-v1.md`: Tài liệu hướng dẫn vận hành chuẩn phiên bản v1 bằng tiếng Việt có dấu đầy đủ, gồm 6 mục đánh số chuẩn xác (`Khởi động`, `Dừng`, `Tiếp tục`, `Sao lưu`, `Khôi phục`, `Xử lý lỗi`) kèm phụ lục đối soát đầy đủ 45 tham số mang nhãn `CONSERVATIVE_DEFAULT` từ `profile.json` và 3 tham số launcher cần đo đạc ở mốc CP7.
- `tests/integration/adapt/launch/test_adapt_launch_cli.py`: Bộ kiểm thử tích hợp 29 test cases bao quát toàn diện các kịch bản của compose, cấu trúc module, layout ngoài cây Git, quản lý mật khẩu, các lệnh vòng đời, xử lý chứng chỉ TLS tự ký và runbook. Toàn bộ lệnh shell/docker được cô lập qua `subprocess` giả lập an toàn (không gọi Docker thật).
- `docs/delivery-evidence/adapt-launch/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ (Bước 7)
Tại Bước 7, sau khi hoàn thành `docker-compose.yml`, khung skeleton `launcher.py` và bộ kiểm thử `test_adapt_launch_cli.py`, kiểm thử được thực thi với Python interpreter đã khóa để chứng kiến oracle RED hợp lệ:
```text
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_layout_outside_git_tree
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_password_created_once_and_private
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_start_orders_steps_and_hides_secret
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_start_fails_closed_when_compose_fails
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_start_is_noop_when_worker_running
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_stop_only_signals_worker_never_docker
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_stop_without_worker
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_stop_reports_failure_when_worker_does_not_exit
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_down_stops_worker_then_compose_down_keeps_volumes
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_status_prints_state_without_secrets
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_backup_uses_pg_dump_via_docker_exec
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_backup_failure_removes_partial_file
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_restore_creates_new_database_and_new_recovery_epoch
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_restore_refuses_bad_inputs
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_restore_failure_drops_only_new_database
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_oauth_prints_vietnamese_steps_then_calls_flow
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_oauth_missing_client_file
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_oauth_failure_does_not_echo_exception
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_serve_issues_one_time_capability_and_opens_launch_url
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_serve_blocked_ports_message
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_make_self_signed_cert_has_loopback_san
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_pid_alive_current_process
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_runbook_has_six_numbered_sections
FAILED tests/integration/adapt/launch/test_adapt_launch_cli.py::test_main_dispatch_and_usage
24 failed, 5 passed in 1.78s
```
- **Xác thực Oracle RED:**
  * 5 test kiểm tra tĩnh về Docker compose và cấu trúc hằng của launcher PASS ngay từ đầu (`test_compose_images_pinned_by_lock_digest`, `test_compose_ports_loopback_only`, `test_compose_named_volume_and_no_secret`, `test_launcher_top_level_imports_stdlib_only`, `test_commands_are_the_seven`).
  * 23 test hành vi FAILED do `NotImplementedError` từ khung hàm của `launcher.py`.
  * 1 test runbook FAILED do `AssertionError` vì tệp `docs/runbook/runbook-v1.md` chưa được tạo.
  * Hoàn toàn không có lỗi collection hoặc lỗi import nào.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 24) | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa hay định dạng |
| Lệnh kiểm 2 (Bước 20) | `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | `29 passed in 0.39s` |
| Lệnh kiểm 3 (Bước 21) | `python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runbook/runbook-v1.md').read_text(encoding='utf-8'); assert '@sha256:' in c and '127.0.0.1:' in c and '0.0.0.0' not in c and r.count(chr(10) + '## ') >= 6, 'launch'"` | 0 | Probe tĩnh đạt chuẩn, không có lỗi assertion |
| Lệnh kiểm 4 (Bước 23) | `python -c "import pathlib; a = pathlib.Path('docs/runbook/runbook-v1.md').read_text(encoding='utf-8'); b = pathlib.Path('docs/delivery-evidence/adapt-launch/report.md').read_text(encoding='utf-8'); assert all(chr(7903) in t and chr(273) in t and chr(63) * 3 not in t for t in (a, b)), 'diacritics'"` | 0 | Tiếng Việt có dấu nguyên vẹn trên cả runbook và báo cáo |
## 4. Đối chiếu ba yêu cầu nghiệm thu

### Yêu cầu 1: docker-compose.yml ghim digest và loopback
- **Yêu cầu:** `postgres` và `temporal` theo `image@sha256:<digest>` lấy từ `tools/runtime/runtime.lock.json` (không tag trần), cổng chỉ `127.0.0.1` (PostgreSQL `57028`, Temporal `7233`), volume đặt tên, không mở UI Temporal.
- **Các test chứng minh:**
  * `test_compose_images_pinned_by_lock_digest`: Xác minh mọi dòng `image:` đều ở dạng `repo:tag@sha256:<64hex>`, đối chiếu khớp từng ký tự với lockfile, không dùng `latest`.
  * `test_compose_ports_loopback_only`: Khẳng định chỉ mở hai cổng `127.0.0.1:57028:5432` và `127.0.0.1:7233:7233`, không có cổng Temporal UI (`8233` hay `7243`), không chứa chuỗi `0.0.0.0`.
  * `test_compose_named_volume_and_no_secret`: Kiểm tra volume `aiavc_pgdata`, không bind mount thư mục máy chủ, mật khẩu truyền qua biến môi trường launcher cấp.
- **Phản ví dụ đã loại trừ:** Sử dụng tag trần không digest; bind cổng `0.0.0.0`; mở cổng UI; bind mount đường dẫn Windows máy chủ vào container.

### Yêu cầu 2: launcher.py quản lý vòng đời an toàn
- **Yêu cầu:** `launcher.py` (chỉ stdlib ở cấp module) với 7 lệnh `start`, `stop`, `down`, `status`, `backup`, `restore`, `oauth`: `start` chạy compose, `MigrationRunner`, tạo chứng chỉ TLS ngoài cây Git, khởi worker, phát capability một lần và mở trình duyệt tại `/launch`; `stop` chỉ dừng worker (container và volume giữ nguyên); `oauth` hướng dẫn từng bước bằng tiếng Việt rồi gọi luồng của `ADAPT-J`; không in bí mật.
- **Các test chứng minh:**
  * `test_launcher_top_level_imports_stdlib_only`: Phân tích cây cú pháp AST, xác nhận 100% import ở cấp module thuộc `sys.stdlib_module_names`; các thư viện bên ngoài chỉ import trong thân hàm.
  * `test_commands_are_the_seven`: Khẳng định tập lệnh gồm đúng 7 lệnh công khai.
  * `test_layout_outside_git_tree`: Ngăn chặn đặt thư mục dữ liệu trong cây Git hoặc thư mục có tổ tiên là Git repo.
  * `test_password_created_once_and_private`: Mật khẩu CSDL được tạo một lần với độ dài >= 32 ký tự, cấp quyền đọc hạn chế `0o600`.
  * `test_start_orders_steps_and_hides_secret`: Thứ tự thực thi chuẩn xác, mật khẩu không xuất hiện trong argv của tiến trình con hay console output.
  * `test_start_fails_closed_when_compose_fails`: Thất bại compose up sẽ fail-closed ngay lập tức.
  * `test_start_is_noop_when_worker_running`: Bỏ qua khởi động mới khi worker đang hoạt động.
  * `test_stop_only_signals_worker_never_docker`: `stop` chỉ ghi cờ `stop.request`, không bao giờ gọi lệnh docker nào.
  * `test_stop_without_worker` & `test_stop_reports_failure_when_worker_does_not_exit`: Kiểm soát trạng thái dừng an toàn.
  * `test_down_stops_worker_then_compose_down_keeps_volumes`: `down` dừng worker trước rồi mới compose down, không có bất kỳ cờ xóa volume nào (`-v`, `--volumes`, `--rmi`).
  * `test_status_prints_state_without_secrets`: In trạng thái hệ thống mà không rò rỉ bí mật.
  * `test_backup_uses_pg_dump_via_docker_exec` & `test_backup_failure_removes_partial_file`: Sao lưu qua `pg_dump -Fc` với tệp sidecar sha256; dọn sạch tệp dở nếu thất bại.
  * `test_restore_creates_new_database_and_new_recovery_epoch`, `test_restore_refuses_bad_inputs`, `test_restore_failure_drops_only_new_database`: Khôi phục tạo CSDL mới và cấp recovery epoch mới trước khi chuyển đổi; nếu thất bại chỉ xóa CSDL tạm vừa tạo, giữ nguyên CSDL cũ.
  * `test_oauth_prints_vietnamese_steps_then_calls_flow`, `test_oauth_missing_client_file`, `test_oauth_failure_does_not_echo_exception`: Hướng dẫn tiếng Việt 4 bước, không in ngoại lệ nhạy cảm, lưu token vào DPAPI.
  * `test_serve_issues_one_time_capability_and_opens_launch_url`: Khởi chạy uvicorn TLS loopback, cấp capability một lần và mở trình duyệt mà không in capability ra ngoài.
  * `test_serve_blocked_ports_message`: Báo lỗi fail-closed khi thiếu adapter thực tế.
  * `test_make_self_signed_cert_has_loopback_san`: Chứng chỉ tự ký ECDSA P-256 có SAN `127.0.0.1` và `localhost`, thời hạn không quá 400 ngày.
  * `test_pid_alive_current_process`: Kiểm tra sống/chết của PID trên Windows thông qua `ctypes OpenProcess` và `GetExitCodeProcess`, tuyệt đối không gọi `os.kill(pid, 0)`.
  * `test_main_dispatch_and_usage`: Định tuyến CLI chuẩn xác.
- **Phản ví dụ đã loại trừ:** Lệnh `stop` gọi docker hoặc xóa container; lệnh `down` xóa volume dữ liệu; in mật khẩu hoặc capability ra console/log; gọi `os.kill(pid, 0)` trên Windows (gây chấm dứt tiến trình ngoài ý muốn).

### Yêu cầu 3: Runbook v1 và phụ lục đối soát CP7
- **Yêu cầu:** `docs/runbook/runbook-v1.md` bằng tiếng Việt, sáu mục đánh số (khởi động, dừng, tiếp tục, sao lưu bằng `pg_dump` qua `docker exec`, khôi phục với recovery epoch mới, xử lý lỗi), kèm danh sách giá trị chọn không có căn cứ đo cần đo ở CP7.
- **Các test chứng minh:**
  * `test_runbook_has_six_numbered_sections`: Kiểm tra đúng 6 tiêu đề cấp 2 đánh số từ 1 đến 6 theo thứ tự; chứa các từ khóa kỹ thuật bắt buộc (`pg_dump`, `docker exec`, `recovery epoch`); có tiêu đề phụ lục chứa `CP7`; toàn bộ 45 tham số `CONSERVATIVE_DEFAULT` từ `profile.json` xuất hiện đầy đủ trong bảng phụ lục; không chứa chuỗi chưa hoàn thiện (dấu chấm hỏi chưa điền).
- **Phản ví dụ đã loại trừ:** Runbook thiếu mục đánh số; tiêu đề sai thứ tự; thiếu tham số cấu hình cần đo; thiếu phụ lục CP7.

## 5. GIẢ ĐỊNH và mục mở
Toàn bộ các nội dung dưới đây được xác định rõ ràng là **GIẢ ĐỊNH** kỹ thuật phục vụ tích hợp, không phải quyết định thay cho người dùng hay Control:
- **GIẢ ĐỊNH (a):** Sáu cổng của `ProductionRuntime` (`route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`) và cơ chế định vị thư mục Drive chưa có adapter thật trong repository. Do đó, hàm `_load_runtime_ports` được thiết kế fail-closed chủ động ném lỗi `LauncherError('BLOCKED: thiếu adapter thật...')`. Đây là trách nhiệm thuộc về các gói tiếp theo (gói J, G, I hoặc CP7).
- **GIẢ ĐỊNH (b):** Dịch vụ `temporal-schema` chạy một lần và việc Docker image của Temporal tự động gán `BIND_ON_IP` theo hostname chưa được xác minh trên môi trường Docker thật của máy trạm; nội dung này được kiểm chứng tại mốc `CP7-ADAPT-08`.
- **GIẢ ĐỊNH (c):** Danh mục workflow activity handlers được khởi tạo rỗng; `grant_issuer` và `capability_reader` được cấu hình fail-closed; tham số `timezone_approved=True` áp dụng theo quyết định múi giờ `Asia/Ho_Chi_Minh` của Control; thời gian dừng mềm `graceful_shutdown_seconds` lấy theo `workflow.heartbeat_seconds` từ profile.
- **GIẢ ĐỊNH (d):** Recovery epoch được sinh và truyền qua biến môi trường `AIAVC_RECOVERY_EPOCH` cho tiến trình con. Việc các bộ ghi dữ liệu kiểm tra epoch này chưa được tích hợp hoàn toàn trong gói launcher và sẽ được các phân hệ hoàn thiện. Quy trình khôi phục luôn tạo CSDL mới và bảo toàn CSDL cũ.
- **GIẢ ĐỊNH (e):** Đường dẫn `oauth_client_secrets_path` và thời gian chờ `oauth_consent_timeout_seconds` sử dụng hằng số an toàn của launcher (300 giây) do `profile.json` nằm ngoài phạm vi `owned paths` của gói.
- **GIẢ ĐỊNH (f):** Tác vụ nạp dữ liệu ban đầu `import_seed` chưa được tự động kích hoạt trong lệnh `start` và sẽ được thực hiện độc lập theo kịch bản của gói sau.
- **GIẢ ĐỊNH (g):** Hàm kiểm tra tiến trình `pid_alive` trên nền tảng Windows sử dụng Windows API `OpenProcess` và `GetExitCodeProcess` thông qua thư viện `ctypes`, tuyệt đối tránh `os.kill(pid, 0)` vốn có hành vi kết thúc tiến trình trên Windows.
- **GIẢ ĐỊNH (h):** Toàn bộ import các thư viện bên thứ ba (`cryptography`, `psycopg`, `temporalio`, `uvicorn`, `controlplane`) được đặt nghiêm ngặt bên trong thân hàm; cấp độ module của `launcher.py` chỉ sử dụng thư viện chuẩn của Python.

## 6. Giới hạn (Limitations)
- Không chạy Docker daemon, PostgreSQL hay Temporal server thật trong quá trình kiểm thử (toàn bộ lệnh shell được cô lập qua subprocess giả lập).
- Không thực hiện gọi ra mạng ngoài, dịch vụ Google Cloud, Drive hay 9Router.
- Cổng kích hoạt sản xuất thực tế vẫn duy trì trạng thái khóa an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
