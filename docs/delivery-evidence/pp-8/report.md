# Báo cáo bằng chứng chuyển giao: PP-8

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới và triển khai trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/infrastructure/production_ports/assembly.py`: Lắp ráp tám giá trị cổng cho `ProductionRuntime` và mô tả cổng chỉ đọc (CT-SEC-001, INV-012, ADR-0006):
  * `build_production_ports(profile, *, vault_dir, staging_dir, state_dir, oauth_client_secrets_path, ports_config, http_factory=None)`: Khởi tạo và đấu nối các adapter PP-1 đến PP-7 từ hồ sơ production và cấu hình ports. Trả về đúng từ điển 8 khóa: `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`, `drive_placement`, `drive_fallback_parent_id`. Mọi ngoại lệ cổng (`DrivePlacementError`, `DriveTokenError`, `ProviderCredentialError`, `ValueError`) được giữ nguyên loại và không bị nuốt bởi try/except; bootstrap Drive placement được thực hiện cuối cùng để lỗi cấu hình báo lỗi ngay trước khi có bất kỳ cuộc gọi mạng nào.
  * `describe_runtime_ports(*, vault_dir, staging_dir, state_dir, oauth_client_secrets_path, ports_config)`: Trả về danh sách 7 bộ giá trị `(tên_cổng, sẵn_sàng, lý_do)` theo thứ tự: `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`, `drive_placement`. Chỉ kiểm tra sự tồn tại của bí danh qua `store.current_version`, tệp OAuth client, thư mục staging và tệp trạng thái placement; tuyệt đối không giải mã (`export_vault`), không kết nối mạng và không để lộ bí mật/canary.
  * `__all__ = ['build_production_ports', 'describe_runtime_ports']`.
- `tests/integration/prod_ports/test_pp_8_assembly.py`: Bộ kiểm thử tích hợp 15 ca kiểm thử bao quát toàn diện:
  * Máy chủ loopback `TokenServer` và `DriveServer` trên `127.0.0.1` với token canary, client secret canary và router key canary; không gọi dịch vụ thật Google hay 9Router.
  * Kiểm tra trả về đủ 8 khóa và `ProductionRuntime` khởi tạo thành công (xác thực qua `__post_init__`).
  * Kiểm tra tên thư mục Drive theo đúng `profile.parameters['drive.folders']` và `ports_config.drive.artifact_namespaces`.
  * Kiểm tra `LocalGpuLease` nhận số slot từ `profile.parameters['gpu.slots']` và TTL tính bằng `ceil(profile.render.timeout_seconds) + grace_seconds`.
  * Kiểm tra các adapter AI tuân thủ `profile.ai.route_endpoint` và `profile.ai.route_model_refs`.
  * Kiểm tra lần dựng thứ hai tái sử dụng tệp trạng thái placement, phát sinh 0 lượt POST tạo thư mục.
  * Kiểm tra lỗi cổng: thiếu refresh token ném `DrivePlacementError` không tạo placement, Drive lỗi dùng retry của profile, `ValueError` giữ nguyên trước mạng, thiếu khóa router giữ nguyên lỗi credential.
  * Kiểm tra 4 ca mô tả cổng `describe_runtime_ports`: báo đủ 7 mục, sẵn sàng sau lần dựng, báo thiếu thành phần, không giải mã, không mở kết nối socket và không rò rỉ canary.
  * Kiểm tra tĩnh mã nguồn AST và văn bản không chứa các chuỗi cấm, không import `launcher`, `tools.*` hay `src.`.
- `docs/delivery-evidence/pp-8/report.md`: Báo cáo bằng chứng chuyển giao này.

## 2. Bằng chứng RED hợp lệ
Tại Bước 10, sau khi tạo khung tạm (stub) ném `NotImplementedError('PP-8')` tại `assembly.py` và hoàn thiện bộ kiểm thử `test_pp_8_assembly.py`, lệnh pytest được thực thi bằng Python interpreter đã khóa của lane để chứng kiến oracle RED hợp lệ:
```text
14 failed, 1 passed in 14.72s
```
- **Exit Code:** `1`
- **5 tên test FAILED đầu tiên:**
  1. `tests/integration/prod_ports/test_pp_8_assembly.py::test_build_returns_exactly_the_eight_keys_and_runtime_accepts_them`
  2. `tests/integration/prod_ports/test_pp_8_assembly.py::test_drive_folders_follow_profile_and_ports_config`
  3. `tests/integration/prod_ports/test_pp_8_assembly.py::test_gpu_lease_uses_profile_slots_and_ttl`
  4. `tests/integration/prod_ports/test_pp_8_assembly.py::test_gpu_lease_changes_with_the_profile_values`
  5. `tests/integration/prod_ports/test_pp_8_assembly.py::test_ai_adapters_follow_profile_route_endpoint_and_model_refs`
- **Xác thực Oracle RED:**
  * 14 ca kiểm thử thất bại hoàn toàn do `NotImplementedError: PP-8`.
  * 1 ca kiểm thử duy nhất đạt là `test_source_is_clean_and_keeps_the_launcher_boundary` (kiểm tra ranh giới tĩnh của stub).
  * Hoàn toàn không có lỗi collection, `ImportError` hay `ModuleNotFoundError`.

## 3. Bằng chứng GREEN và kết quả các lệnh kiểm
Bảng tổng hợp kết quả thực thi các lệnh kiểm tra bắt buộc:

| Bước / Lệnh | Lệnh thực thi | Exit Code | Dòng tóm tắt nguyên văn |
| :--- | :--- | :--- | :--- |
| Lệnh kiểm 1 (Bước 16) | `git diff --check` | 0 | Thoát 0, không có cảnh báo khoảng trắng thừa hay lỗi định dạng dòng |
| Lệnh kiểm 2 (Bước 14) | `python -m pytest tests/integration/prod_ports/test_pp_8_assembly.py -q -p no:cacheprovider` | 0 | `15 passed in 14.49s` |
| Lệnh kiểm 3 (Bước 15) | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/production_ports/assembly.py').read_text(encoding='utf-8').lower(); assert 'build_production_ports' in t and 'describe_runtime_ports' in t and 'from src.' not in t and 'import launcher' not in t and 'from tools' not in t and 'mock' not in t and 'fake' not in t and 'os.environ' not in t, 'PP-8'"` | 0 | Thoát 0, probe tĩnh đạt chuẩn, không có AssertionError |

## 4. Ánh xạ yêu cầu nghiệm thu

### Yêu cầu 1: build_production_ports trả đúng tám khóa và ProductionRuntime dựng được với chúng
- **Yêu cầu:** `build_production_ports(profile, *, vault_dir, staging_dir, state_dir, oauth_client_secrets_path, ports_config, http_factory=None)` trả đúng tám khóa `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease`, `drive_placement`, `drive_fallback_parent_id`: `LocalGpuLease` với slot từ `profile.parameters['gpu.slots']` và TTL `ceil(profile.render.timeout_seconds) + grace_seconds`; `DrivePlacementBootstrap` với tên gốc từ `profile.parameters['drive.folders']` và retry từ `profile.drive.retry`; các adapter PP-2 đến PP-7 với `profile.ai.route_endpoint` và `profile.ai.route_model_refs`.
- **Các test chứng minh:**
  * `test_build_returns_exactly_the_eight_keys_and_runtime_accepts_them`: Xác nhận trả về đúng tập hợp 8 khóa, đúng kiểu của từng cổng, và `ProductionRuntime(...)` khởi tạo thành công với các giá trị trả về (`runtime.gpu_lease is ports['gpu_lease']`, `runtime.drive_fallback_parent_id == 'folder-1'`, `runtime.drive_placement`).
  * `test_drive_folders_follow_profile_and_ports_config`: Tên thư mục Drive tạo mới theo đúng thư mục gốc trong `profile.parameters['drive.folders']['root']` và các namespace trong `ports_config.drive.artifact_namespaces`.
  * `test_gpu_lease_uses_profile_slots_and_ttl`: Xác nhận số slot cấp phát theo cấu hình profile và TTL tính bằng `ceil(profile.render.timeout_seconds) + grace_seconds`.
  * `test_gpu_lease_changes_with_the_profile_values`: Kiểm tra giá trị slot và TTL phản ứng chính xác khi thay đổi cấu hình profile.
  * `test_ai_adapters_follow_profile_route_endpoint_and_model_refs`: Kiểm tra `vision_route.endpoint` theo `profile.ai.route_endpoint`, `route_catalog` khớp các `route_model_refs`, credentials acquire đúng key, artifact source mở tệp từ thư mục staging.
  * `test_second_build_reuses_state_file_without_creating_folders`: Lần dựng thứ hai tái sử dụng tệp trạng thái `drive-placement.json`, chỉ thực hiện GET kiểm tra và không phát sinh POST tạo thư mục mới (0 lần tạo thư mục).
- **Phản ví dụ đã loại trừ:** Đổi `ProductionRuntime`; sửa `docker-compose.yml`; placement giả khi Drive lỗi.

### Yêu cầu 2: describe_runtime_ports kiểm tra sự sẵn sàng chỉ đọc, không giải mã, không mạng
- **Yêu cầu:** `describe_runtime_ports(...)` trả danh sách (tên, sẵn sàng, lý do) chỉ kiểm sự tồn tại của alias, tệp OAuth client, thư mục staging và tệp trạng thái placement; không giải mã, không mạng.
- **Các test chứng minh:**
  * `test_describe_lists_the_seven_ports_before_the_first_build`: Trả về danh sách 7 cổng theo thứ tự chuẩn, 6 cổng đầu sẵn sàng, `drive_placement` chưa sẵn sàng khi chưa có tệp trạng thái, lý do bằng chuỗi mô tả rõ ràng.
  * `test_describe_reports_every_port_ready_after_a_build`: Sau lần dựng đầu tiên, cả 7 cổng đều báo cáo trạng thái sẵn sàng (`True`).
  * `test_describe_reports_missing_pieces`: Báo cáo chính xác cổng nào thiếu khi đường dẫn vault rỗng, thiếu staging hoặc thiếu tệp OAuth client.
  * `test_describe_decrypts_nothing_opens_no_connection_and_leaks_no_secret`: Kiểm tra nghiêm ngặt khi monkeypatch chặn gọi `export_vault` và `socket.connect`: hàm vẫn chạy bình thường, không mở kết nối mạng, không gọi giải mã, và không làm rò rỉ bất kỳ canary nào (`REFRESH`, `CLIENT_SECRET`, `ROUTER_KEY`, `ACCESS_PREFIX`) trong chuỗi kết quả.
- **Phản ví dụ đã loại trừ:** In hay trả bí mật từ `describe_runtime_ports`; gọi mạng khi mô tả.

### Yêu cầu 3: Lỗi cổng giữ nguyên loại, không nuốt lỗi, không trả placement giả
- **Yêu cầu:** Lỗi cổng (`DrivePlacementError`, `DriveTokenError`, `ProviderCredentialError`, `ValueError`) được để nguyên loại, không nuốt, để gói đấu nối launcher đổi thành `LauncherError` bắt đầu `BLOCKED:`; thiếu refresh token thì ném lỗi cổng gốc (`DriveTokenError` hoặc `DrivePlacementError`) và không trả placement giả.
- **Các test chứng minh:**
  * `test_missing_refresh_token_raises_the_port_error_and_returns_no_placement`: Khi thu hồi refresh token Drive, ném `DrivePlacementError`, không gửi request loopback, không tạo tệp trạng thái, không để lộ canary.
  * `test_drive_failure_is_not_swallowed_and_uses_profile_retry`: Khi Drive trả HTTP 503, ném `DrivePlacementError`, áp dụng chính xác số lần thử lại từ `profile.drive.retry`.
  * `test_value_error_of_a_port_is_kept_before_any_network`: Khi truyền đường dẫn staging tương đối, ném `ValueError` ngay từ hàm dựng của adapter trước khi có bất kỳ yêu cầu mạng nào.
  * `test_missing_router_key_does_not_block_build_and_credentials_keep_their_error`: Thiếu khóa 9Router không chặn quá trình lắp ráp cổng; khi acquire khóa sau đó, `ProviderCredentialError` được giữ nguyên.
- **Phản ví dụ đã loại trừ:** Nuốt lỗi rồi trả placement giả.

### Yêu cầu 4: Giữ vững ranh giới launcher và mã nguồn thuần
- **Yêu cầu:** Ranh giới launcher: PP-8 không sở hữu và không sửa `tools/launcher/launcher.py` (tệp của `ADAPT-LAUNCH`); `assembly.py` không import `launcher` hay `tools.*`; hai hàm `build_production_ports` và `describe_runtime_ports` là hợp đồng bàn giao cho gói đấu nối launcher (plan.md mục 5.1). Slice chỉ khai khóa `LOCK-PROD-PORTS`.
- **Các test chứng minh:**
  * `test_source_is_clean_and_keeps_the_launcher_boundary`: Kiểm tra tĩnh cây cú pháp AST và chuỗi mã nguồn xác nhận:
    - Không import các tiền tố bị cấm: `launcher`, `tools`, `src`.
    - Không chứa các chuỗi: `from src.`, `import launcher`, `from tools`, `import tools`, `mock`, `fake`, `os.environ`, `getenv`, `subprocess`, `print(`, `logging`.
    - Chữ ký của `build_production_ports` và `describe_runtime_ports` tuân thủ đúng tham số vị trí / keyword-only theo hợp đồng bàn giao.
  * Probe tĩnh Bước 15 đạt exit code 0.
  * `tools/launcher/launcher.py` và các tệp khác ngoài 3 tệp thuộc owned paths hoàn toàn không bị chỉnh sửa.
- **Phản ví dụ đã loại trừ:** Import `launcher` hay `tools.*` trong `assembly.py`; sửa `tools/launcher/launcher.py`.

## 5. Giới hạn và GIẢ ĐỊNH
- **(a) Timeout của Drive placement:** Theo GIẢ ĐỊNH (D8), các yêu cầu mạng khởi tạo thư mục Drive của `DrivePlacementBootstrap` sử dụng giá trị `profile.drive.chunk_timeout_seconds` làm timeout.
- **(b) Trạng thái sẵn sàng của placement:** Cổng `drive_placement` trong `describe_runtime_ports` báo cáo chưa sẵn sàng (`False`) khi tệp trạng thái `drive-placement.json` chưa tồn tại trên đĩa; việc này báo hiệu cho launcher biết lần dựng đầu tiên sẽ cần quyền mạng để tạo các thư mục Drive cần thiết.
- **(c) Kiểm thử TTL của GPU lease:** Trong test tích hợp, thời gian TTL được xác minh qua thuộc tính nội bộ `_ttl_seconds` của `LocalGpuLease`.
- **(d) Đấu nối Launcher:** Việc tích hợp hai hàm `build_production_ports` và `describe_runtime_ports` vào `tools/launcher/launcher.py` thuộc phạm vi gói công việc độc lập `ADAPT-LAUNCH` theo tài liệu `docs/implementation/convergence/plan.md` mục 5.1; gói PP-8 tuyệt đối không chạm vào `launcher.py`.
- **(e) Không chạy full test suite:** Worker tuân thủ nghiêm ngặt chỉ thị kỷ luật thực thi mục tiêu (`targetedCommand`), chỉ chạy targeted integration test của PP-8, không tự ý chạy full suite nhằm tối ưu thời gian và tài nguyên.
- **(f) Kỷ luật kiểm soát phiên bản:** Không tự ý `git push` hay `git merge`, không tác động lên nhánh `main` hay `backup`. Trạng thái kích hoạt sản xuất thực tế vẫn giữ nguyên ranh giới chặn an toàn (`PRODUCTION_ACTIVATION_BLOCKED`).
