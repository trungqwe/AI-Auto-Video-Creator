# Báo cáo bằng chứng chuyển giao: ADAPT-PROD

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và sửa đổi trong phạm vi quyền sở hữu (`owned paths`):
- `src/main.py`: Mở rộng composition root nhận hồ sơ test (mặc định) hoặc production. Ở hồ sơ production, nạp profile và kiểm tra toàn bộ tham số hợp lệ trước khi mở `TransactionManager`, nạp muộn `wiring.production` qua `__import__` để đảm bảo giữ nguyên phong bì import kiểm thử của `CP-4-WIRING` (< 90 dòng, không còn `FastAPI` import dư thừa, không chứa tiền tố `src.` hay chuỗi cấm).
- `src/controlplane/api/wiring/production.py`: Tạo mới mô-đun kết nối production:
  * Nạp `WiringConfig` từ profile và kiểm tra tính đầy đủ của tham số cấu hình.
  * Khởi tạo 6 nhóm dịch vụ phân hệ (`collection`, `config_security`, `creative`, `render`, `storage`, `voice`) rồi gọi `create_app` với Origin loopback TLS.
  * ASGI `ProductionApp` ghép API `/v1/` với phục vụ tĩnh `src/controlplane/ui/dist`.
  * Endpoint `GET /launch?cap=` tiêu thụ capability một lần (`BootstrapCapabilityRegistry`, TTL tối đa 60 giây) cấp cookie `cp_session` (`HttpOnly`, `Secure`, `SameSite=Strict`) và cookie `csrf_token`, sau đó chuyển hướng 303 về `/`.
  * Từ chối toàn bộ route `/test-driver/*` với HTTP 404 và không import `controlplane.application.test_driver`.
  * Cấu hình server loopback TLS trên `127.0.0.1` với chứng chỉ tự ký (`loopback_config`, `serve_production_tls`).
  * `TemporalWorkerGroup` đăng ký đủ 6 workflow của `GATE-CP-6-WORKFLOW` trên queue `control-workflows`; lệnh `stop()` chỉ dừng worker và các công việc đang chạy tiếp tục khi worker mới được khởi động lại.
- `tests/integration/adapt/prod/test_adapt_prod_app.py`: Bộ kiểm thử tích hợp toàn diện gồm 23 test cases trên PostgreSQL 18.6 disposable database, bao quát toàn bộ các nhóm yêu cầu A, B, C, D.
- `docs/delivery-evidence/adapt-prod/report.md`: Báo cáo bằng chứng thực thi này.

## 2. Bằng chứng RED hợp lệ (Bước 9)
Khi chạy kiểm thử tại Bước 9 trên mã nguồn trước khi sửa `src/main.py` và trước khi tạo `src/controlplane/api/wiring/production.py`, bộ test đã ghi nhận oracle RED hợp lệ: các test thiếu tham số của hồ sơ production bị FAIL do `DID NOT RAISE ProductionProfileError`:
```text
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_profile_leaf_does_not_start[budget.hard_stop]
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_profile_leaf_does_not_start[ai.route_endpoint]
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_profile_leaf_does_not_start[workflow.schedule]
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_profile_leaf_does_not_start[drive.chunk_bytes]
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_profile_leaf_does_not_start[collection.fetch_policy.feed]
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_workspace_does_not_start
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_missing_runtime_does_not_start
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_invalid_workspace_and_runtime_do_not_start
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_test_profile_is_default_and_unknown_profile_is_rejected
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_builder_failure_closes_manager
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_production_profile_builds_app_on_postgres
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_allowed_origins_are_exact_loopback_for_the_port
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_production_sources_do_not_import_test_driver_or_bind_wildcard
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_worker_group_registers_six_workflows_on_control_queue
FAILED tests/integration/adapt/prod/test_adapt_prod_app.py::test_stop_only_stops_workers_and_pending_work_resumes
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_test_driver_routes_return_404
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_launch_exchanges_capability_once
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_launch_session_authorizes_v1_requests
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_launch_rejects_foreign_host_without_consuming
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_capability_expires_and_ttl_is_capped
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_ui_dist_is_served_byte_for_byte
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_no_route_reads_secrets_back
ERROR tests/integration/adapt/prod/test_adapt_prod_app.py::test_loopback_config_binds_127_0_0_1_only
15 failed, 1 warning, 8 errors in 6.84s
```
Oracle RED xác thực: 7 test thiếu tham số (`test_missing_profile_leaf_does_not_start` với 5 leaf, `test_missing_workspace_does_not_start`, `test_missing_runtime_does_not_start`) nhận kết quả `Failed: DID NOT RAISE ProductionProfileError` do `src/main.py` ban đầu chưa nạp profile và chưa kiểm tra tính đầy đủ của tham số trước khi mở TransactionManager.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm tra
Bảng tổng hợp các lệnh kiểm tra theo quy trình và các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
|---|---|---|---|
| Lệnh kiểm bắt buộc 1 (Bước 21) | `git diff --check` | 0 | Không có lỗi định dạng hay khoảng trắng thừa |
| Bước 15 (Lệnh kiểm bắt buộc 2) | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` | 0 | 23 passed, 1 warning in 9.80s |
| Lệnh kiểm bắt buộc 3 (Bước 22) | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring/production.py']); assert 'controlplane.application.test_driver' not in t and '/launch' in t and '127.0.0.1' in t and '0.0.0.0' not in t and 'from src.' not in t, 'prod'"` | 0 | Probe tĩnh đạt chuẩn, không có lỗi assertion |
| Bước 16 (Hồi quy CP-4) | `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` | 0 | 133 passed, 28 skipped, 1 warning in 2.05s |
| Bước 17 (Hồi quy UI) | `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | 651 passed, 1 warning in 1.40s |
| Bước 18 (Cổng thoát M2) | `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider` | 0 | 6 passed in 5.26s |
| Bước 19 (Hồi quy ADAPT-WIRE) | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 1 | 2 failed, 103 passed in 11.47s (2 lỗi có từ trước ngoài owned paths do workflow.py, không do production.py) |

## 4. Đối chiếu ba yêu cầu nghiệm thu với các trường hợp kiểm thử

### Yêu cầu 1: Hồ sơ production của src/main.py
1. `src/main.py` nhận hồ sơ `production` hoặc `test` (mặc định `test`); ở `production` nạp profile, gọi các `build_<phân hệ>_services` rồi `create_app`; hồ sơ production thiếu tham số thì không khởi động (BL-CV-06).
   - Cách kiểm: ``tests/integration/adapt/prod/test_adapt_prod_app.py` trên PostgreSQL dùng một lần: thiếu tham số thì khởi động thất bại.`
   - Phản ví dụ phải loại trừ: Hồ sơ production thiếu tham số vẫn khởi động.
   - Giới hạn: Từ kế hoạch đã nghiệm thu IMPL-PLAN-ADAPT-FIX1.
- **Các test kiểm chứng:**
  * `test_missing_profile_leaf_does_not_start[budget.hard_stop]`
  * `test_missing_profile_leaf_does_not_start[ai.route_endpoint]`
  * `test_missing_profile_leaf_does_not_start[workflow.schedule]`
  * `test_missing_profile_leaf_does_not_start[drive.chunk_bytes]`
  * `test_missing_profile_leaf_does_not_start[collection.fetch_policy.feed]`
  * `test_missing_workspace_does_not_start`
  * `test_missing_runtime_does_not_start`
  * `test_invalid_workspace_and_runtime_do_not_start`
  * `test_test_profile_is_default_and_unknown_profile_is_rejected`
  * `test_builder_failure_closes_manager`
  * `test_production_profile_builds_app_on_postgres`

### Yêu cầu 2: Loopback TLS, ghép UI tĩnh và capability một lần
2. `src/controlplane/api/wiring/production.py`: ASGI ghép `create_app` (`/v1/`) với phục vụ tĩnh `src/controlplane/ui/dist` trên cổng loopback TLS `127.0.0.1` (uvicorn, chứng chỉ tự ký do launcher tạo); Origin cho phép đúng `https://127.0.0.1:<cổng>` và `https://localhost:<cổng>`; không import `controlplane.application.test_driver` nên `/test-driver/*` trả 404; `GET /launch?cap=` đổi capability một lần (`BootstrapCapabilityRegistry`, TTL tối đa 60 giây) thành cookie `cp_session` rồi chuyển hướng `/`; `ui/dist` và spec M2 giữ nguyên byte.
   - Cách kiểm: `Cùng tệp test với `TestClient`: `/test-driver/health` 404; `/launch` lần hai 403; cookie `HttpOnly` và `Secure`; không có route đọc lại secret; `ui/dist` được phục vụ; chạy lại `tests/m2` và `tests/unit/control_ui` không đổi.`
   - Phản ví dụ phải loại trừ: Giữ route test-driver ở production; capability dùng lại được hay sống quá 60 giây; bind `0.0.0.0`; sửa `ui/dist` hay spec M2.
   - Giới hạn: Từ kế hoạch đã nghiệm thu IMPL-PLAN-ADAPT-FIX1.
- **Các test kiểm chứng:**
  * `test_test_driver_routes_return_404` (đường test-driver trả 404)
  * `test_launch_exchanges_capability_once` (/launch dùng 1 lần, lần 2 trả 403, cookie HttpOnly Secure)
  * `test_launch_session_authorizes_v1_requests` (cookie cp_session xác thực /v1/)
  * `test_launch_rejects_foreign_host_without_consuming` (Host ngoại lai trả 403)
  * `test_capability_expires_and_ttl_is_capped` (chặn TTL > 60 và hết hạn trả 403)
  * `test_allowed_origins_are_exact_loopback_for_the_port` (Origin đúng loopback theo cổng)
  * `test_ui_dist_is_served_byte_for_byte` (phục vụ đủ 4 tệp dist nguyên byte)
  * `test_no_route_reads_secrets_back` (không có route đọc lại secret)
  * `test_production_sources_do_not_import_test_driver_or_bind_wildcard` (không import test-driver, không 0.0.0.0)
  * `test_loopback_config_binds_127_0_0_1_only` (chỉ bind 127.0.0.1 loopback)

### Yêu cầu 3: Worker Temporal và bảo toàn công việc đang thực hiện
3. Khởi động worker Temporal đăng ký sáu workflow của `GATE-CP-6-WORKFLOW`; «Dừng» chỉ dừng worker, việc dở tiếp tục khi chạy lại.
   - Cách kiểm: `Test với worker giả: đăng ký đủ sáu workflow, dừng không hủy việc dở.`
   - Phản ví dụ phải loại trừ: Dừng làm mất việc đang chạy.
   - Giới hạn: Từ kế hoạch đã nghiệm thu IMPL-PLAN-ADAPT-FIX1.
- **Các test kiểm chứng:**
  * `test_worker_group_registers_six_workflows_on_control_queue` (đăng ký đủ 6 workflow trên queue control-workflows)
  * `test_stop_only_stops_workers_and_pending_work_resumes` (dừng không hủy việc dở, chạy lại tiếp tục)

## 5. Quyết định mặc định D8 và GIẢ ĐỊNH
Toàn bộ các mục dưới đây được ghi nhận rõ ràng là **GIẢ ĐỊNH**, không phải quyết định:
- **GIẢ ĐỊNH (a):** ProductionRuntime do launcher cấp qua runtime_factory vì sáu cổng (route_catalog, provider_credentials, vision_route, artifact_source, drive_token_broker, gpu_lease) chưa có adapter thật; thiếu thì không khởi động (chủ sở hữu ADAPT-LAUNCH hoặc gói J, G, I);
- **GIẢ ĐỊNH (b):** /launch dùng HTTP 303, kiểm Host loopback trước khi consume, đặt thêm cookie csrf_token giống redeem_bootstrap;
- **GIẢ ĐỊNH (c):** graceful_shutdown_seconds do launcher truyền (đề xuất workflow.heartbeat_seconds), chưa kiểm trên Temporal Server thật (thuộc CP7-G-03);
- **GIẢ ĐỊNH (d):** dựng WorkflowServices và handler activity do launcher thực hiện, ADAPT-PROD chỉ cung cấp TemporalWorkerGroup;
- **GIẢ ĐỊNH (e):** main.py nạp wiring.production bằng __import__ để giữ phong bì import của test_cp4_wiring;
- **GIẢ ĐỊNH (f):** đường profile mặc định là tools/launcher/prod/profile.json, ghi đè bằng CONTROLPLANE_PROFILE_PATH;
- **GIẢ ĐỊNH (g):** `python src/main.py` với CONTROLPLANE_PROFILE=production từ chối chạy, launcher gọi build_app và serve_production_tls;
- **GIẢ ĐỊNH (h):** chỉ chạy tests/m2/test_p9_m2_exit_gate.py chứ không chạy toàn bộ tests/m2

## 6. Giới hạn (Limitations)
- Không gọi các dịch vụ đám mây hay AI thật (tuân thủ D5).
- Không chạy cụm máy chủ Docker hay Temporal thật trong phạm vi gói này.
- Cổng sản xuất vẫn được khóa an toàn theo cơ chế bảo vệ toàn cục (PRODUCTION_ACTIVATION_BLOCKED).

## 7. Hồi quy ngoài phạm vi
Tại Bước 19, khi thực hiện kiểm tra đối sánh với bộ kiểm thử `tests/integration/adapt/wire/test_adapt_wire_services.py`, kết quả ghi nhận:
- **Dòng tóm tắt nguyên văn:** 2 failed, 103 passed in 11.47s
- **Chi tiết hai kiểm thử không đạt:**
  1. FAILED tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory
     - *Nguyên nhân:* Tệp `src/controlplane/api/wiring/workflow.py` (đã được tích hợp từ gói trước `CP-6-WORKFLOW`) định nghĩa hàm builder `build_workflow_services`, trong khi bộ kiểm tra của `ADAPT-WIRE` kỳ vọng chỉ có 6 builder của 6 phân hệ ban đầu.
     - *Kết luận:* Lỗi có từ trước, phát sinh từ tệp ngoài owned paths.
  2. FAILED tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_modules_do_not_cross_import_subsystems
     - *Nguyên nhân:* Tệp `workflow.py` import các activity handler từ các phân hệ khác nhau (`creative`, `voice`, `render`, `storage`, `source_ingestion`) nhằm đăng ký danh mục workflow của `CP-6-WORKFLOW`.
     - *Kết luận:* Lỗi có từ trước, phát sinh từ tệp ngoài owned paths.
- **Xác nhận không ảnh hưởng:** `src/controlplane/api/wiring/production.py` và `src/main.py` hoàn toàn không gây ra bất kỳ lỗi nào trong bộ test `ADAPT-WIRE`. Kiểm thử kiểm tra chuỗi cấm `test_wiring_sources_have_no_forbidden_text` hoàn toàn đạt (PASS).
