# Báo cáo IMGGEN-LAUNCH

Mã gói: `IMGGEN-LAUNCH`. Nhóm lỗi: `OI-CP7-11-Q2` (định nghĩa gốc của Q2 không nằm trong repo; theo spec của task, ghi `GIẢ ĐỊNH`).

## Lý do làm lại

Control cấp lại lane ngày 02/11/2026 (đính chính `IMGGEN-LAUNCH-REFERENCE-COPY`), yêu cầu chép nguyên văn `tools/launcher/launcher.py` và `tests/integration/adapt/launch/test_imggen_launch.py` từ bản tham chiếu Control tại `D:/AIAVC_IMGPROTO/ref/imggen-launch/` (đối chiếu mã băm trong `SHA256SUMS`), không tự viết lại mã.

## Tệp

Bảng các tệp trong owned paths: 2 tệp mã nguồn và kiểm thử được chép nguyên văn byte-for-byte từ thư mục tham chiếu `D:/AIAVC_IMGPROTO/ref/imggen-launch/` kèm mã SHA-256 (đã kiểm tra ở bước 4), cùng tệp `docs/delivery-evidence/imggen-launch/report.md` do Worker lập.

| Tệp | SHA-256 | Nguồn / Ghi chú |
| --- | --- | --- |
| `tools/launcher/launcher.py` | `9086a70a4757e95840e4c66dcab2817c84ee869defd921b4e4fbf8b24099649f` | Chép nguyên văn từ tham chiếu Control |
| `tests/integration/adapt/launch/test_imggen_launch.py` | `19e008933ea5e1b0efe5a5b32ac5182bacabaaa06635e788dc757f32afda7d28` | Chép nguyên văn từ tham chiếu Control |
| `docs/delivery-evidence/imggen-launch/report.md` | - | Do Worker tạo, ghi lại bằng chứng thực thi |

## Lệnh kiểm đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| Probe SHA-256 ban đầu của `tools/launcher/launcher.py` (Bước 1) | 0 | `SHA: 22d174a694fb99db30317f7792cb0e99a1befbf153a91b9707e736083798d65f` (bắt đầu bằng `22d174a694fb`) |
| Chép `tools/launcher/launcher.py` từ bản tham chiếu (Bước 2) | 0 | Chép nguyên văn thành công bằng `Copy-Item -LiteralPath ... -Force` |
| Chép `tests/integration/adapt/launch/test_imggen_launch.py` từ bản tham chiếu (Bước 3) | 0 | Chép nguyên văn thành công bằng `Copy-Item -LiteralPath ... -Force` |
| Probe SHA-256 hai tệp tham chiếu sau khi chép (Bước 4) | 0 | Cả hai tệp trùng SHA-256 tham chiếu, danh sách `bad` rỗng |
| `git diff --check` (Bước 5) | 0 | Không có lỗi khoảng trắng |
| `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/launch/test_imggen_launch.py -q -p no:cacheprovider` (Bước 6) | 0 | Dòng tổng kết nguyên văn: `63 passed in 11.82s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p no:cacheprovider` (Bước 7) | 0 | Dòng tổng kết nguyên văn: `35 passed in 11.86s` |
| Probe `Deps.start_imagegen`, `COMMANDS`, hằng số `IMAGEGEN_*`, cấm import ngoài (Bước 8) | 0 | `Deps.start_imagegen` mặc định `None`, đủ 7 lệnh, các hằng số chính xác, không chứa `from tools`, `from src.`, `0.0.0.0` |
| Probe hàm sidecar, thứ tự trong `cmd_serve`, `cmd_status` và `main` (Bước 9) | 0 | Thứ tự `begin_imagegen -> start_worker -> worker.stop -> end_imagegen` chính xác, status và main nối chuẩn |
| Probe dòng lệnh sidecar (`-I`, cờ CLI, biến môi trường, secrets) và dọn dẹp (Bước 10) | 0 | Dòng lệnh đủ cờ cô lập, token bí mật, thứ tự dừng `shutdown -> terminate -> kill` |
| Probe cấu trúc test mới (Bước 11) | 0 | Đủ `coveredIds: OI-CP7-11-Q2`, 23 hàm test (>= 15), đủ các test bắt buộc, không dùng database |
| Probe giữ nguyên LAUNCH-FIX2 (Bước 12) | 0 | Giữ nguyên `build_production_ports`, `load_ports_config`, `ports.json` |
| Probe giữ nguyên PW-W2-FIX5 (Bước 13) | 0 | Giữ nguyên `seed_production_render_config` |
| Probe giữ nguyên PW-W1-FIX1 (Bước 14) | 0 | Giữ nguyên `seed_media`, `import_seed_media`, `generate_seed_media` |
| Probe giữ nguyên `install_activity_executor` và `capped_worker_factory` (Bước 15) | 0 | Giữ nguyên định tuyến activity executor và worker caps |
| Probe giữ nguyên `resolve_documents` và `fallback_candidates` (Bước 16) | 0 | Giữ nguyên logic an toàn ảnh và fallback candidates |
| Probe giữ nguyên PW-W1 (Bước 17) | 0 | Giữ nguyên `OutboxRelay`, `build_grant_issuer`, `CapabilityReader` |
| Probe cấu trúc controlplane, pythonpath pytest và cấm import `src.` (Bước 18) | 0 | Đầy đủ cấu trúc package, pytest pythonpath hợp lệ, không vi phạm import |
| Probe nội dung `report.md` (Bước 20) | 0 | Có mặt chuỗi `IMGGEN-LAUNCH` và `OI-CP7-11-Q2` |
| `git diff --check` lần cuối (Bước 21) | 0 | Hoàn toàn sạch lỗi khoảng trắng |

## Hành vi của bản tham chiếu

Bản tham chiếu triển khai quản lý vòng đời dịch vụ sidecar sinh ảnh cục bộ `tools/imagegen/server.py` từ bên trong launcher theo đúng thiết kế:
- **Hằng số cấu hình**:
  - `IMAGEGEN_SERVER = ROOT / 'tools' / 'imagegen' / 'server.py'`
  - `IMAGEGEN_SERVICE = 'aiavc-imagegen'`
  - `IMAGEGEN_PORT = 57030`
  - `IMAGEGEN_TOKEN_ENV = 'AIAVC_IMAGEGEN_TOKEN'`
  - `IMAGEGEN_TOKEN_BYTES = 32`
  - `IMAGEGEN_HTTP_TIMEOUT_SECONDS = 2.0`
  - `IMAGEGEN_READY_POLLS = 20`, `IMAGEGEN_READY_POLL_SECONDS = 0.25`
  - `IMAGEGEN_STOP_FILE_WAIT_SECONDS = 3.0`, `IMAGEGEN_STOP_GRACE_SECONDS = 25.0`, `IMAGEGEN_KILL_WAIT_SECONDS = 5.0`
- **Bổ sung layout ứng dụng (`AppLayout`)**: Bổ sung các đường dẫn `hf_hub_dir` (`models/hf-hub`), `imagegen_dir` (`imagegen`), `imagegen_python` (`imagegen/venv/Scripts/python.exe`), `imagegen_out_dir` (`imagegen/out`), `imagegen_endpoint_file` (`imagegen/endpoint.json`), `imagegen_log` (`logs/imagegen.log`).
- **Trường interface `Deps.start_imagegen`**: Khai báo `Callable[[AppLayout, Mapping[str, str]], ImagegenHandle] | None` với giá trị mặc định `None`. `default_deps` giữ `None`; hàm `main()` gắn bản cài đặt thực tế `start_imagegen` cạnh `seed_defaults` và `seed_media`.
- **Hàm `start_imagegen(layout, environ, *, spawn=None)`**:
  - Trả về đối tượng `ImagegenSidecar(process, layout, token, port)`.
  - Kiểm tra điều kiện tiên quyết: nếu thiếu `imagegen_python` thì ném `LauncherError` chứa thông điệp `not provisioned`; nếu thiếu tệp mã nguồn `IMAGEGEN_SERVER` thì ném lỗi tương ứng.
  - Cấu trúc `argv`: `[python, '-I', server, '--port', str(port), '--hub', str(hf_hub_dir), '--out', str(imagegen_out_dir), '--parent-pid', str(os.getpid()), '--stop-file', str(layout.stop_file)]`.
  - Tạo token bí mật ngẫu nhiên `secrets.token_urlsafe(32)` mới cho mỗi lần khởi chạy. Token tuyệt đối không xuất hiện trong `argv` hay nhật ký console.
  - Lọc môi trường con `imagegen_child_env`: sao chép từ môi trường launcher nhưng loại bỏ toàn bộ các biến môi trường bắt đầu bằng tiền tố `CONTROLPLANE_` hoặc `AIAVC_`, loại bỏ `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`; sau đó bổ sung biến môi trường token `AIAVC_IMAGEGEN_TOKEN`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
  - Khởi tạo tiến trình bằng `subprocess.Popen` với cờ `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, `stdin=DEVNULL`, `stdout` ghi nối tiếp vào `logs/imagegen.log`, `stderr` gộp chung vào `stdout`, thư mục làm việc `cwd=ROOT`.
  - Đầu hàm tự động dọn dẹp xóa tệp endpoint cũ `imagegen/endpoint.json`; ngay sau khi spawn tiến trình thành công, ghi lại tệp endpoint mới dạng `{url, token, pid}` để tiến trình ứng dụng kết nối.
- **Kiểm tra sức khỏe `fetch_imagegen_health(port=None, timeout=None)`**: Gửi yêu cầu HTTP loopback `GET /v1/health` bằng `http.client`. Trả về `None` khi không phản hồi, mã trạng thái khác HTTP 200, nội dung không phải đối tượng JSON hoặc trường `service` khác `aiavc-imagegen`.
- **Dừng an toàn nhiều tầng `ImagegenSidecar.stop(*, stop_file_wait, grace, kill_wait)`**:
  - Bước 1: Chờ `stop_file_wait` giây nếu tệp dừng (`layout.stop_file`) tồn tại để tiến trình tự phát hiện.
  - Bước 2: Nếu tiến trình vẫn còn chạy, gửi yêu cầu `POST /v1/shutdown` kèm header xác thực `Authorization: Bearer <token>` và chờ trong khoảng thời gian ân hạn `grace` giây.
  - Bước 3: Nếu vẫn chưa dừng, gọi `terminate()` rồi `kill()` (mỗi lần chờ tối đa `kill_wait` giây).
  - Xóa tệp `imagegen/endpoint.json` nếu token trong tệp còn khớp với token của phiên chạy hiện tại. Phương thức có tính chất idempotent (gọi lại an toàn), trả về mã thoát của tiến trình.
- **Tích hợp trong `cmd_serve`**:
  - Sau khi nạp hoặc tạo định danh (`load_or_create_identity`), gọi `begin_imagegen(deps, layout)` để khởi động sidecar trước khi gọi `deps.start_worker`.
  - Mọi lỗi phát sinh từ `start_imagegen` chỉ in một dòng thông báo ra `deps.out` (lỗi không xác định chỉ in tên lớp ngoại lệ) và không chặn luồng khởi động ứng dụng chính.
  - Hàm `announce_imagegen` thăm dò có giới hạn (`IMAGEGEN_READY_POLLS` lần thăm dò, tối đa 5 giây) rồi ghi một dòng trạng thái duy nhất: thông tin sẵn sàng kèm revision 12 ký tự và hàng đợi; hoặc thông báo `not provisioned` kèm số tệp thiếu và hướng dẫn chạy `provision.py`; hoặc thông báo thoát sớm kèm mã lỗi; hoặc chưa hoàn tất khởi động.
  - Nếu `start_worker` gặp lỗi thì lập tức dừng sidecar; trong khối `finally`: dừng worker trước (`worker.stop()`) sau đó mới dừng sidecar qua `end_imagegen(deps, sidecar)`.
- **Tích hợp trong `cmd_status`**: Khi `Deps.start_imagegen` không phải `None`, hiển thị thêm một dòng trạng thái của sidecar sau ba cổng dịch vụ chính: hiển thị `describe_imagegen_health`, hoặc `not provisioned` khi thiếu python venv của sidecar, hoặc `not running`.

## Giới hạn và GIẢ ĐỊNH

- **Không chạy GPU hay nạp trọng số thật**: Môi trường uv riêng (`imagegen/venv`) và trọng số mô hình do Control cài đặt (`provision.py`); khi thiếu thì launcher chỉ ghi nhận một dòng thông báo `not provisioned` rõ ràng và toàn bộ ứng dụng vẫn hoạt động bình thường mà không bị gián đoạn.
- **Ranh giới tích hợp pipeline**: Gói này chỉ chịu trách nhiệm khởi chạy, giám sát và dừng sidecar; việc nối pipeline thực tế thuộc gói `IMGGEN-PIPE` tiếp theo, vốn sẽ đọc thông tin kết nối `{url, token}` từ tệp `imagegen/endpoint.json`.
- **Bộ kiểm thử tích hợp thực thi an toàn**: Ba test `real_sidecar` trong `test_imggen_launch.py` chạy `server.py` thật bằng chính interpreter khoá của lane (`sys.executable`) với thư mục hub rỗng, qua đó sidecar dừng ở trạng thái `not_provisioned` có kiểm soát, chứng minh chuẩn xác cú pháp dòng lệnh CLI, token bí mật, cơ chế tệp dừng, endpoint shutdown và dọn dẹp tài nguyên mà không cần tải trọng số thật.
- **Trạng thái bộ test nền tảng**: Nhóm test `PW-G1` và `PW-W1` chạy hoàn toàn đạt (35 passed, 0 failed) trong môi trường lane đã được khoá tài nguyên `LOCK-POSTGRES-TEST-DB`.
- **Ghi nhận GIẢ ĐỊNH**: Định nghĩa chi tiết nguyên thuỷ của mã nhóm lỗi `OI-CP7-11-Q2` không nằm trong kho mã nguồn, được ghi nhận dạng `GIẢ ĐỊNH` theo đúng yêu cầu của đặc tả.
