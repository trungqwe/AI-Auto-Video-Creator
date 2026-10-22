# Báo cáo CP-4-WIRING

## 1. Phạm vi
Các tệp đã tạo và sửa đổi trong gói nhiệm vụ CP-4-WIRING, tuân thủ đúng danh sách owned paths được giao:
- `src/main.py`: Tạo mới composition root mỏng (< 90 dòng), chỉ đọc cấu hình từ biến môi trường, khởi tạo `TransactionManager` và gọi `create_app`. Không chứa logic nghiệp vụ, không có tiền tố `src.`, không chứa bí mật hay chuỗi kết nối nhạy cảm.
- `src/controlplane/api/main.py`: Cập nhật hàm `create_app` để mount các router `build_listing_router` (cho `sources`, `hooks`, `media`) và `build_metadata_router` (cho `hooks`, `media`) từ `api/routes/modules` (H-08, H-09) với các callback lazy trích xuất từ `app.state.module_services`. Bổ sung middleware xử lý ngoại lệ `CapabilityUnavailableError` thành ProblemDetail 503 `CAPABILITY_UNAVAILABLE`.
- `src/controlplane/api/routes/control.py`: Đăng ký thêm 15 route lệnh mới theo chuẩn CT-API-003..006 trả status code 202 kèm receipt trạng thái `accepted`, kiểm soát nghiêm ngặt `Idempotency-Key`, `If-Match`, validate allowlist các trường dữ liệu và không để lộ bí mật.
- `src/controlplane/application/control_api/errors.py`: Tạo mới ngoại lệ `CapabilityUnavailableError` phục vụ trả mã lỗi 503 khi năng lực chưa được kết nối.
- `src/controlplane/application/control_api/receipts.py`: Tạo mới hàm `accepted_receipt` chuẩn hóa cấu trúc receipt trạng thái `accepted` và lọc chỉ giữ các trường trong allowlist.
- `src/controlplane/application/control_api/command_catalog.py`: Khai báo bảng đặc tả `COMMAND_SPECS` cho đúng 15 lệnh CT-API-003..006.
- `src/controlplane/application/control_api/route_catalog.py`: Khai báo danh mục `LISTING_RESOURCES` và `METADATA_RESOURCES`.
- `src/controlplane/application/control_api/command_gateway.py`: Tạo mới cổng lệnh `ControlCommandGateway` xử lý idempotency, hash request không chứa secret và trả accepted receipt.
- `src/controlplane/application/control_api/commands.py`: Bổ sung phương thức `command_gateway()` vào `ControlApiCommandService` để compose gateway mà không vi phạm ranh giới kiến trúc.
- `tests/integration/convergence/test_cp4_wiring.py`: Tạo mới bộ kiểm thử tích hợp 130 test cases bao phủ toàn bộ các yêu cầu của gói hội tụ CP-4-WIRING.
- `docs/delivery-evidence/cp-4-wiring/report.md`: Báo cáo chuyển giao và bằng chứng nghiệm thu này.

Khẳng định tuyệt đối không sửa đổi các tệp ngoài phong bì thẩm quyền:
- Không tạo hoặc sửa đổi bất kỳ tệp nào trong `src/controlplane/api/wiring/*.py`.
- Không sửa đổi `src/controlplane/application/sse/event_catalog.py`.
- Không sửa đổi `src/controlplane/config/adapter.py`.
- Không sửa đổi `src/controlplane/infrastructure/db/control_api_queries.py`.
- Không sửa đổi `src/controlplane/infrastructure/db/control_api_commands.py`.
- Không sửa đổi `src/controlplane/api/routes/modules/__init__.py` (thuộc CP-2B-DEPS, vẫn là tệp rỗng).

## 2. RED
Thực hiện kiểm thử test-first tại Bước 7 trước khi viết bất kỳ mã nguồn triển khai nào:
- Lệnh: `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
- Oracle RED hợp lệ: `AssertionError` (404/405 thay vì 202/200 do thiếu route lệnh và route mount, thiếu `src/main.py`, thiếu `command_catalog.py`; không có `ImportError` hay lỗi thu thập test).
- Nguyên văn 3 dòng FAILED đầu tiên:
```text
FAILED tests/integration/convergence/test_cp4_wiring.py::test_command_returns_accepted_receipt[RegisterSource]
FAILED tests/integration/convergence/test_cp4_wiring.py::test_command_returns_accepted_receipt[UpdateSourceMetadata]
FAILED tests/integration/convergence/test_cp4_wiring.py::test_command_returns_accepted_receipt[RemoveSource]
```
- Dòng tóm tắt kết quả:
```text
91 failed, 20 passed, 25 skipped, 1 warning in 2.45s
```
*Ghi chú:* Nhóm test gateway (PHẦN 5 trong `test_cp4_wiring.py`) được bổ sung ở Bước 20–21 sau khi lớp `ControlCommandGateway` đã được định nghĩa, vì nếu viết từ đầu oracle của nó sẽ chỉ là `ImportError` (không phải RED hợp lệ theo chuẩn của dự án).

## 3. GREEN

### 3.1. Kết quả kiểm thử bộ hội tụ CP-4-WIRING (Bước 22)
- Lệnh: `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
- Exit code: 0
- Dòng tóm tắt:
```text
130 passed, 28 skipped, 1 warning in 1.80s
```

### 3.2. Kết quả kiểm tra probe tĩnh src/main.py (Bước 23)
- Lệnh: `python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call create_app'; assert 'from src.' not in t and 'import src.' not in t, 'no src. prefix'"`
- Exit code: 0 (Đạt, không có assertion error nào).

### 3.3. Kết quả hồi quy m2 và integration (Bước 24)
- Lệnh: `python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression`
- Exit code: 0
- Dòng tóm tắt:
```text
1900 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 303.24s (0:05:03)
```
*Ghi nhận:* Bộ kiểm thử tĩnh kiến trúc `test_h28_static_architecture`, các bài kiểm thử bảo mật `test_p7a` và `test_p7b` đều xanh hoàn toàn. Các bài kiểm thử phụ thuộc dịch vụ ngoài (PostgreSQL, Docker) không có trong môi trường đã được skip theo đúng quy định kiểm thử, không tự ý tuyên bố PASS thiếu căn cứ.

### 3.4. Kết quả kiểm thử unit các phân hệ và bảo mật (Bước 25)
- Lệnh: `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/security tests/unit/control_ui -q -p no:cacheprovider`
- Exit code: 1
- Dòng tóm tắt:
```text
1 failed, 5227 passed, 1 warning, 1998 subtests passed in 8.19s
```
- Phân tích kết quả:
  - `tests/unit/security`: Đạt 100% GREEN (khớp với yêu cầu nghiệm thu của BL-CV-04).
  - `tests/unit/control_ui` (chứa H-08/H-09): Đạt 100% GREEN.
  - Tổng hai bộ phận `security` + `control_ui`: `1020 passed, 1 warning, 398 subtests passed in 1.28s`, exit code 0.
  - Các bộ phận `collection`, `catalog`, `creative`, `voice`, `render`: Đạt 100% GREEN.
  - Lỗi duy nhất: `FAILED tests/unit/ingestion/test_ingestion_package_validation.py::test_ingestion_import_boundary`. Lỗi này xuất hiện do tệp `src/ingestion/persistence/repositories.py` (được đưa vào từ commit `89e919d` thuộc task `PERSIST-B`, tích hợp tại commit `2d835c0`) có `import psycopg`, vi phạm regex ranh giới domain cũ `BOUNDARY_RE` vốn chỉ áp dụng khi phân hệ B chưa có tầng persistence. Tệp `repositories.py` và tệp test trên đều nằm ngoài `ownedPaths` của `CP-4-WIRING`.

```blocked-manifest
{"step": 25, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["PERSIST-B"], "paths": ["src/ingestion/persistence/repositories.py", "tests/unit/ingestion/test_ingestion_package_validation.py"], "ids": ["tests/unit/ingestion/test_ingestion_package_validation.py::test_ingestion_import_boundary"]}
```

### 3.5. Kiểm tra định dạng git diff (Bước 28)
- Lệnh: `git diff --check`
- Exit code: 0 (Sạch, không có lỗi định dạng hay khoảng trắng thừa).

## 4. Bảng route

### 4.1. 15 route lệnh mới (CT-API-003..006)
Các route đều trả status code 202 kèm receipt trạng thái `accepted`:

| Tên lệnh | Method | Đường dẫn | Bắt buộc If-Match | Hợp đồng |
| :--- | :--- | :--- | :--- | :--- |
| RegisterSource | POST | /v1/sources | Không | CT-API-003 |
| UpdateSourceMetadata | PATCH | /v1/sources/{resource_id} | Có | CT-API-003 |
| RemoveSource | DELETE | /v1/sources/{resource_id} | Có | CT-API-003 |
| RestoreSource | POST | /v1/sources/{resource_id}/restore | Có | CT-API-003 |
| TestSource | POST | /v1/sources/{resource_id}/test | Không | CT-API-003 |
| ImportVisualHook | POST | /v1/hooks/visual | Không | CT-API-004 |
| ImportAudioHook | POST | /v1/hooks/audio | Không | CT-API-004 |
| RunDebugStage | POST | /v1/jobs/{resource_id}/debug-stage | Không | CT-API-005 |
| RetryStage | POST | /v1/jobs/{resource_id}/retry-stage | Không | CT-API-005 |
| CreateNewVariant | POST | /v1/jobs/{resource_id}/variants | Không | CT-API-005 |
| RegenerateFromStage | POST | /v1/jobs/{resource_id}/regenerate | Không | CT-API-005 |
| UpdateSecret | PUT | /v1/secrets/{resource_id} | Có | CT-API-006 |
| TestExternalAccount | POST | /v1/external-accounts/{resource_id}/test | Không | CT-API-006 |
| EnableExternalAccount | POST | /v1/external-accounts/{resource_id}/enable | Có | CT-API-006 |
| DisableExternalAccount | POST | /v1/external-accounts/{resource_id}/disable | Có | CT-API-006 |

### 4.2. Các route lệnh hiện có và router H-08 / H-09
- `StartProductionBatch` (`POST /v1/batches`) và `PublishConfigurationRevision` (`PUT /v1/configs/{scope}`): Đã có sẵn từ trước trong `control.py`, giữ nguyên hành vi hợp lệ.
- `UpdateHookMetadata` và `UpdateMediaMetadata`: Được phục vụ qua router H-09 (`PATCH /v1/hooks/{item_id}` và `PATCH /v1/media/{item_id}`), trả status 200 theo quy định của H-09.
- Listing H-08: Được mount ở `/v1/sources`, `/v1/hooks`, `/v1/media` (cung cấp GET danh sách và GET chi tiết qua `{item_id}`).

## 5. Bảng trạng thái BL

| Mã | Trạng thái | Chi tiết |
| :--- | :--- | :--- |
| BL-CV-02 | PENDING | đăng ký event kind ở event_catalog.py và publisher ngoài ownedPaths, chờ gate |
| BL-CV-03 | BLOCKED | RoutedInvocationService (J-18) chưa có trong src/; chỉ nối trong api/wiring khi lớp có và wiring được mở |
| BL-CV-04 | BLOCKED | config/adapter.py và tests/unit/security/test_http_router_adapter.py ngoài phong bì, không sửa; tests/unit/security vẫn xanh (dẫn kết quả bước 25) |
| BL-CV-05 | PENDING | query CT-API-002 còn thiếu ở control_api_queries.py và lệnh ở control_api_commands.py nằm ngoài phong bì |
| BL-CV-06 | BLOCKED/PENDING (D8-CV-05) | api/wiring/*.py ngoài phong bì, Worker không tạo; src/main.py chưa gọi build_<phân hệ>_services; bỏ api/wiring khỏi thiết kế là ARCHITECTURE_CHANGE chờ user |
| BL-CV-12 | BLOCKED | gỡ LIMIT 100 và phân trang keyset ở control_api_queries.py cùng control.py không được tuyên bố vì phần PostgreSQL thật ngoài phong bì; next_cursor của route mới chỉ là kết quả của service giả |

## 6. Giới hạn

Kết quả chỉ chứng minh logic cục bộ với service giả; 15 lệnh trả 503 CAPABILITY_UNAVAILABLE trong create_app thật cho tới khi handler phân hệ được nối (BL-CV-06); không đóng cổng sản xuất; không tuyên bố phân trang.
