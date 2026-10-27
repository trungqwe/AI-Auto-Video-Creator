# PW-W1: nối G, A, B, C, I vào launcher

Gói công việc PW-W1 hoàn thành việc đấu nối các phân hệ G, A, B, C, I vào launcher và worker: tạo mô-đun đấu nối mới `src/controlplane/api/wiring/ingestion.py` cho phân hệ B (ingestion); bổ sung các hàm dựng handler hoạt động trong `collection.py`, `storage.py`, `completion.py`; hoàn thiện lắp ráp 12 activity production, bọc chuỗi dispatcher theo đúng thứ tự `GrantRevokingDispatcher(ResultRecordingDispatcher(ActivityDispatcher))` với `JobLifecycleListener`, bổ sung probe năng lực thực tế và khởi tạo seed dữ liệu trong `workflow.py`; cập nhật `start_worker` trong `launcher.py` để sử dụng `build_grant_issuer`, `CapabilityReader`, `OutboxRelay`, `CollectionScheduler`, `EnrichmentStarter` và dừng êm; đồng thời nạp 7 nguồn và 6 prompt mặc định khi `launcher start` sau `AppSession` và trước khi spawn worker.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` (Bước 2: RED) | 1 | FAILED `test_wiring_builder_inventory` (1 failed, 110 passed in 8.45s) do chưa có mô-đun `ingestion.py`. |
| `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p no:cacheprovider` (Bước 6: RED) | 1 | FAILED `test_start_worker_binds_every_listed_activity_and_wraps_the_dispatcher` (1 failed in 2.75s) với lỗi `AssertionError: assert 'ActivityDispatcher' == 'GrantRevokingDispatcher'`. |
| `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` (Bước 26: GREEN) | 0 | 186 passed, 1 warning in 30.30s (cả 4 tệp test đều xanh). |
| `python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py tests/integration/prod_wiring/test_pw_g3_grants.py tests/integration/convergence/test_cp4_wiring.py tests/integration/convergence/test_cp5_completion_uow.py tests/integration/prod_ports/test_pp_2_credentials.py -q -p no:cacheprovider` (Bước 27: Hồi quy) | 0 | 326 passed, 28 skipped, 1 warning in 27.15s (các bộ test PW-G1, PW-G3, CP4, CP5, PP2 giữ nguyên trạng thái xanh). |
| `python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'OutboxRelay' in t and 'build_grant_issuer' in t and 'CapabilityReader' in t, 'PW-W1'"` (Bước 28) | 0 | Thành công: `launcher.py` chứa đầy đủ `OutboxRelay`, `build_grant_issuer` và `CapabilityReader`. |
| `python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'handlers={}' not in t and 'NoReturn' not in t, 'PW-W1 stub'"` (Bước 29) | 0 | Thành công: loại bỏ hoàn toàn các stub `handlers={}` và `NoReturn` trong `launcher.py`. |
| `git diff --check` (Bước 31) | 0 | Diff hoàn toàn sạch, không có lỗi khoảng trắng thừa hay kết thúc dòng. |

## Dòng đã đổi trong test_adapt_wire_services.py và lý do

1. **Dòng 1-6 (docstring đầu tệp):** Đặt docstring mô-đun chứa `coveredIds: PW-W1-01` lên trước lệnh `from __future__ import annotations` để đảm bảo docstring mô-đun được Python ghi nhận đúng chuẩn.
2. **Dòng 76 (trong `EXPECTED_BUILDERS`):** Thêm `'ingestion': 'build_ingestion_services'` ngay sau `'creative': 'build_creative_services'`.
3. **Dòng 87 (trong `OWN_SUBSYSTEM`):** Thêm `'ingestion': 'ingestion'` ngay sau `'render': 'render'`.
4. **Cuối tệp (dòng 583-596):** Bổ sung hai test builder ingestion:
   - `test_ingestion_production_uses_postgres_adapters`: kiểm tra cấu hình production dùng `PostgresIngestionUnitOfWork`, `ResolveDepsFactory` và handler `ResolveCollectedDocument`.
   - `test_ingestion_test_profile_uses_in_memory`: kiểm tra cấu hình test dùng `b_memory.InMemoryUnitOfWork` và `resolve_factory is None`.

*Lý do thay đổi:* Việc bổ sung mô-đun đấu nối `src/controlplane/api/wiring/ingestion.py` làm phép kiểm kê builder trong `test_adapt_wire_services.py` phát hiện mô-đun mới chưa được khai báo trong danh mục kỳ vọng; do đó cần cập nhật danh mục và bổ sung test kiểm tra tương ứng theo quy định. Toàn bộ các mục đã có, `SUBSYSTEMS`, `COMPOSITION_MODULES` và các assertion khác được giữ nguyên tuyệt đối. Tệp `tests/integration/adapt/prod/test_adapt_prod_app.py` chỉ được chạy nghiệm thu, không bị chỉnh sửa.

## Quyết định mặc định (D8)

1. **Nhịp tiến trình nền:** Nhịp kiểm tra `OutboxRelay` được ấn định là 2.0 giây (`OUTBOX_RELAY_INTERVAL_SECONDS = 2.0`); nhịp consumer `EnrichmentStarter` là 5.0 giây (`ENRICHMENT_INTERVAL_SECONDS = 5.0`); thời hạn chờ các tác vụ nền dừng khi stop là 10.0 giây (`BACKGROUND_STOP_SECONDS = 10.0`).
2. **Không gian lưu trữ Drive đầu ra:** Namespace Drive cho đầu ra video được định danh cố định là `'output'` (`OUTPUT_NAMESPACE = 'output'`).
3. **Thời hạn cấp quyền (Grant TTL):** Giữ giá trị mặc định theo PW-G3 với `ttl_by_queue=None`.
4. **Khởi tạo dữ liệu mặc định:** `launcher start` gọi `seed_defaults` truyền `recovery_epoch` của AppSession hiện hành để đảm bảo tính nhất quán phiên.
5. **Độc lập dữ liệu mặc định trong kiểm thử:** Hàm `main()` trong `launcher.py` liên kết với hàm `seed_defaults` thật, trong khi cấu trúc `default_deps()` giữ `seed_defaults=None` để các bài test kiểm thử phụ thuộc mặc định (như PW-G1) không tự động ghi dữ liệu vào cơ sở dữ liệu.
6. **Lưu trữ runtime production:** Runtime production được gán vào `app.api_app.state.production_runtime` bên trong `load_app` để `start_worker` có thể truy xuất các đường dẫn thực thi như FFmpeg, khóa GPU và thư mục tạm staging.

## Mục mở

1. Các activity thuộc phân hệ D (creative), E (voice), F (render) hiện chưa được gắn handler thật và giữ trạng thái unbound thuộc phạm vi gói công việc PW-W2.
2. Endpoint `PATCH /v1/media` hiện trả về mã lỗi 503 thuộc phạm vi giải quyết của phân hệ liên quan khác.
