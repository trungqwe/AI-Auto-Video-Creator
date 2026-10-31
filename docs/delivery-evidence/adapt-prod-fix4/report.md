# Báo cáo bằng chứng chuyển giao: ADAPT-PROD-FIX4

## 1. Phạm vi thực hiện

Mã tham chiếu R34 (nêu trong lệnh kiểm của task).

Nguồn quyết định: user 31/10/2026 (CLOSURE_NOTE CP7/RG-10), tối đa 10 luồng video. Không đổi mặc định pool 4 của `TransactionManager`, không thêm khoá profile, không thêm kwarg vào lời gọi `TemporalWorkerGroup` của launcher.

Các tệp đã sửa:
- `src/controlplane/infrastructure/capacity.py` (mới, chỉ import `types`): `MAX_VIDEO_STREAMS = 10`, `DB_POOL_MAX_SIZE`, `ACTIVITY_QUEUE_CAPS`, `ACTIVITY_THREADS`.
- `src/controlplane/infrastructure/db/uow.py`: `TransactionManager` thêm kw `pool_timeout = 30.0` (số hữu hạn dương, không bool, sai thì `ValueError` trước khi mở pool) truyền `ConnectionPool(timeout=...)`; import `DB_POOL_MAX_SIZE` từ capacity và xuất lại qua `__all__`; mặc định pool 4 giữ nguyên.
- `src/main.py`: nhánh production dựng `TransactionManager(config.dsn, pool_max_size=DB_POOL_MAX_SIZE)`; chỉ đổi dòng import uow, không import module mới; nhánh test giữ nguyên.
- `tools/launcher/launcher.py`: thêm `install_activity_executor(loop)` (`ThreadPoolExecutor` `ACTIVITY_THREADS` luồng, tên `aiavc-activity`, import bên trong hàm); `start_worker` gọi ngay sau `asyncio.new_event_loop()` và đóng executor khi luồng worker kết thúc.
- `src/controlplane/api/wiring/production.py`: thêm `capped_worker_factory(worker_cls=Worker)` (chỉ thêm `max_concurrent_activities` cho queue có trần); `TemporalWorkerGroup` có `worker_factory` mặc định `None` nghĩa là `capped_worker_factory()`.
- `tools/launcher/docker-compose.yml`: dịch vụ postgres thêm `command: ["postgres", "-c", "max_connections=200"]`; giữ digest và cổng `127.0.0.1`.
- `src/voice/adapters/real_kokoro_tts.py`, `src/voice/adapters/real_whisper_aligner.py`: `_load_lock = threading.Lock()`, `_load` kiểm hai lần quanh khoá; lỗi nạp nhả khoá nên lượt sau thử lại; không đổi `synthesize`, `align` và chuỗi probe ADAPT-E.
- `docs/runbook/runbook-v1.md`: mục con «Tài nguyên cho tối đa 10 luồng video (ADAPT-PROD-FIX4)».
- Test: `tests/integration/prod_wiring/test_pw_worker_capacity.py` (mới), `tests/integration/adapt/launch/test_adapt_launch_cli.py`, `tests/integration/adapt/e/test_adapt_e_tts_aligner.py`, `tests/integration/adapt/prod/test_adapt_prod_app.py`.

Hằng số của `capacity.py` và lý do:

| Hằng số | Giá trị | Lý do |
| --- | --- | --- |
| `MAX_VIDEO_STREAMS` | 10 | Quyết định user 31/10/2026: tối đa 10 luồng video; CPU 7950X bão hoà ở khoảng 146 video mỗi giờ (tính toán của Control, chưa đo 10 luồng thật). |
| `DB_POOL_MAX_SIZE` | 36 = 2 × 10 + 16 | Mỗi lệnh sáng tạo giữ một kết nối suốt lời gọi 9Router và mượn thêm một kết nối cho ledger/reservation (20); 8 cho API/SSE; 8 cho thu thập/enrichment. Pool 4 cũ cạn khi 4 luồng gọi AI cùng lúc và chờ tới `PoolTimeout`. |
| `ACTIVITY_QUEUE_CAPS` | `cloud-io` 16, `cloud-ai` 8 | Chặn enrichment không trần (100 activity mỗi hàng) chiếm hết executor; queue khác giữ mặc định của SDK. |
| `ACTIVITY_THREADS` | 48 = 10 + 38 | 10 video, 16 cloud-io, 8 cloud-ai, 8 control, 3 nền, 3 dư; executor mặc định cũ là `min(32, cpu + 4)`. |
| `max_connections` (PostgreSQL, compose) | 200 | Pool 36, kết nối trực tiếp của launcher/worker và Temporal dùng chung máy chủ; mặc định 100 quá sát. Chỉ áp khi launcher tạo lại container. |

RAM: Kokoro và Whisper nạp mô hình đúng một lần cho mỗi tiến trình nhờ `_load_lock`, nên 10 luồng tới TTS hay align đầu tiên không dựng 10 mô hình trong RAM.

## 2. Bằng chứng RED

Trước khi sửa mã production (chỉ có `capacity.py` để test thu thập được).

Bước 6, lệnh `python -m pytest tests/integration/prod_wiring/test_pw_worker_capacity.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider`, exit 1 (mong đợi):
- Dòng tổng kết: `14 failed, 102 passed, 1 warning in 27.98s`.
- FAILED: `test_four_streams_on_a_pool_of_four_hit_pool_timeout`, bảy ca `test_pool_timeout_must_be_a_positive_finite_number`, `test_capped_worker_factory_caps_only_cloud_queues`, `test_worker_factory_default_is_none`, `test_install_activity_executor_gives_the_loop_48_named_threads`, `test_concurrent_first_load_builds_the_kokoro_model_once`, `test_concurrent_first_load_builds_the_whisper_model_once`, `test_builder_failure_closes_manager`.
- Loại lỗi đã đọc trực tiếp: `AssertionError` ở `test_builder_failure_closes_manager` (`assert None == 36`). Các ca còn lại hỏng ở đúng chức năng chưa có (`pool_timeout`, `capped_worker_factory`, `install_activity_executor`, nạp model nhiều lần); bản ghi đầy đủ từng loại lỗi không được lưu lại, chỉ có danh sách ca hỏng và dòng tổng kết ở trên.
- `test_capacity_constants` và ca mượn lồng với pool 36 đạt trước khi sửa, như mong đợi.

## 3. Bằng chứng GREEN

| Bước | Lệnh | Exit | Dòng tổng kết pytest |
| --- | --- | --- | --- |
| 15 | `python -m pytest tests/integration/prod_wiring/test_pw_worker_capacity.py tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` | 0 | `177 passed, 28 skipped, 1 warning in 25.39s` |
| 16 | `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | `62 passed in 12.40s` |
| 17 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | `54 passed, 89 subtests passed in 1.22s` |
| 18 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | `7524 passed, 1 warning, 2561 subtests passed in 22.84s` |
| 19 | `git diff --check` | 0 | (không báo lỗi) |
| 20 | probe `python -c` hằng số capacity | 0 | (không có đầu ra) |

28 ca skipped ở bước 15 nằm trong `test_cp4_wiring.py` (lệnh không yêu cầu If-Match, không có body hoặc không thể đổi payload), có từ trước và không liên quan thay đổi này.

## 4. Mục còn mở

- `max_connections=200` chỉ áp khi launcher tạo lại container `aiavc-postgres`; container đang chạy giữ giá trị cũ.
- Mức 10 luồng chưa đo ở CP7; lần đo đầu là CP7-10 cấp lại hoặc CP7-11.
- Gốc rễ `ProviderFailureHandler.run` giữ UoW qua lời gọi AI chưa tách (backlog, đổi ngữ nghĩa giao dịch); trần `cloud-io` 16 có thể làm stage sync xếp sau enrichment (chậm, không quá hạn).
- Không có user checkpoint nào được ghi là đã duyệt.

Các probe `python -c` còn lại do Control chạy trong phần kiểm.
