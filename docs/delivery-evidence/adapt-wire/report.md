# Báo cáo bằng chứng chuyển giao: ADAPT-WIRE

## 1. Phạm vi thực hiện
Các tệp đã được tạo mới trong phạm vi quyền sở hữu (`owned paths`):
- `src/controlplane/api/wiring/production_profile.py`: Đọc cấu hình có kiểu từ `tools/launcher/prod/profile.json` (78 tham số bắt buộc, không default ẩn, ném `ProductionProfileError(parameter, reason)`), kèm `ProductionRuntime` và `WiringConfig`.
- `src/controlplane/api/wiring/_shared.py`: Quản lý `PooledReservationStore` và `PooledCostLedger` dùng chung qua connection pool của `TransactionManager` (`manager.borrow_connection()`), cùng hàm phân giải đường dẫn an toàn `resolve_under_root`.
- `src/controlplane/api/wiring/collection.py`: Cung cấp hàm `build_collection_services(manager, config)` cho Phân hệ A (`source_ingestion`).
- `src/controlplane/api/wiring/creative.py`: Cung cấp hàm `build_creative_services(manager, config)` cho Phân hệ D (`creative`).
- `src/controlplane/api/wiring/voice.py`: Cung cấp hàm `build_voice_services(manager, config)` cho Phân hệ E (`voice`).
- `src/controlplane/api/wiring/render.py`: Cung cấp hàm `build_render_services(manager, config)` cho Phân hệ F (`render`).
- `src/controlplane/api/wiring/storage.py`: Cung cấp hàm `build_storage_services(manager, config)` cho Phân hệ I (`storage`).
- `src/controlplane/api/wiring/config_security.py`: Cung cấp hàm `build_config_security_services(manager, config)` cho Phân hệ J (`config_security`).
- `tests/integration/adapt/wire/test_adapt_wire_services.py`: Bộ kiểm thử tích hợp 105 test cases trên PostgreSQL 18.6 disposable database.
- `docs/delivery-evidence/adapt-wire/report.md`: Báo cáo bằng chứng thực thi này.

## 2. Sai lệch tiền đề
Sai lệch tiền đề: CP-4-WIRING không tạo mô-đun build_<phân hệ>_services nào (tìm def build_.*_services trong wiring/ ban đầu không có kết quả; completion.py chỉ có build_completion_service), nên ADAPT-WIRE tạo mới sáu mô-đun, không có mô-đun trùng; B, C, G, H chưa có adapter thật theo acceptance nên không có mô-đun.

## 3. Bằng chứng RED hợp lệ (Bước 9)
Khi chạy kiểm thử lần đầu tại Bước 9 trước khi cài đặt các mô-đun wiring, test suite đã ghi nhận oracle RED hợp lệ: `AssertionError` từ `test_wiring_builder_inventory` do chưa có các hàm builder theo yêu cầu:
```text
FAILED tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory
FAILED tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_sources_have_no_forbidden_text
FAILED tests/integration/adapt/wire/test_adapt_wire_services.py::test_no_cross_subsystem_wiring_import
104 failed, 1 passed in 8.64s
```
Oracle RED xác thực: `AssertionError` tại `test_wiring_builder_inventory` (`assert found == {k: [v] for k, v in EXPECTED_BUILDERS.items()}`).

## 4. Bằng chứng GREEN và kết quả các lệnh kiểm tra
- **Kiểm tra định dạng diff (`git diff --check`):**
  - Lệnh: `git diff --check`
  - Exit code: 0
  - Kết quả: PASS, không có lỗi khoảng trắng thừa hay lệch định dạng.
- **Bước 22 (`test_adapt_wire_services.py`):**
  - Lệnh: `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `105 passed in 7.72s` (toàn bộ 105 test cases PASS, bao gồm 78 test xóa từng leaf parameter của profile và 6 test khóa tokenization).
- **Bước 23 (probe tĩnh `real_`, không có `application.test_driver` hay `from src.`):**
  - Lệnh: `python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert 'application.test_driver' not in t and 'from src.' not in t and 'real_' in t, 'wiring'"`
  - Exit code: 0
  - Kết quả: PASS, không có lỗi assertion.
- **Bước 24 (probe tĩnh không chứa chuỗi cấm):**
  - Lệnh: `python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); bad = [s for s in ['import psycopg', 'INSERT INTO', 'PostgresIdempotencyRepository', 'PostgresOutboxRepository', 'os.environ', 'getenv', 'mock-9router', 'sqlite3', 'import os'] if s in t]; assert not bad, bad"`
  - Exit code: 0
  - Kết quả: PASS, danh sách bad rỗng.
- **Bước 25 (probe tĩnh không import chéo adapter giữa các phân hệ):**
  - Lệnh: `python -c "import ast, pathlib; own = {'collection': 'source_ingestion', 'creative': 'creative', 'voice': 'voice', 'render': 'render'}; subs = {'source_ingestion', 'creative', 'voice', 'render', 'ingestion', 'catalog'}; w = pathlib.Path('src/controlplane/api/wiring'); bad = []; [bad.append((f.name, m)) for f in w.glob('*.py') if f.stem != 'completion' for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) for m in ([a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module] if isinstance(n, ast.ImportFrom) and n.module else [])) if m.split('.')[0] in subs and own.get(f.stem) != m.split('.')[0]]; assert not bad, bad"`
  - Exit code: 0
  - Kết quả: PASS, danh sách bad rỗng.
- **Bước 26 (hồi quy `test_cp4_wiring.py`):**
  - Lệnh: `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider`
  - Exit code: 0
  - Dòng tóm tắt nguyên văn: `133 passed, 28 skipped, 1 warning in 1.92s`
- **Bước 27 (hồi quy `test_cp5_completion_uow.py`):**
  - Lệnh: `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider`
  - Exit code: 1
  - Dòng tóm tắt nguyên văn: `1 failed, 35 passed in 3.74s`
  - Chi tiết lỗi: `FAILED tests/integration/convergence/test_cp5_completion_uow.py::test_adapter_placement_and_packaging`
  - Vị trí: dòng 579: `assert sorted(p.name for p in WIRING.parent.glob('*.py')) == ['__init__.py', 'completion.py']`
  - Nguyên nhân: Tệp test này thuộc gói sở hữu `CP-5-COMPLETION` (ngoài `owned paths` của `ADAPT-WIRE`). Test này giả định cứng thư mục `src/controlplane/api/wiring/` chỉ được phép chứa đúng hai tệp `__init__.py` và `completion.py`, dẫn đến xung đột trực tiếp khi `ADAPT-WIRE` thêm các mô-đun wiring theo đúng tiêu chí nghiệm thu bắt buộc.
  - Xử lý: Worker tuân thủ nghiêm ngặt phân quyền single-writer, fail-closed, không sửa tệp ngoài owned paths và báo cáo `BLOCKED` với khối `blocked-manifest` theo quy chuẩn `DEPENDENCY_GAP`.

## 5. Bảng tổng hợp mô-đun wiring đã xây dựng
| Phân hệ | Hàm build | Adapter thật ở production | Adapter giả ở test | Kho dữ liệu PostgreSQL |
|---|---|---|---|---|
| A (`collection`) | `build_collection_services` | `RealHttpTransport`, `RealFeedSource` (rss_feed, atom_feed), `RealMediaFetcher` | `FakeHttpTransport`, `FakeFeedSource`, `FakeMediaFetcher` | `PostgresSourceIngestionUnitOfWork` (qua TransactionManager) |
| D (`creative`) | `build_creative_services` | `RoutedAIInvocation` (trên `RoutedInvocationService` + `NineRouterExecutor`) | `FakeAIInvocation` | `PostgresCreativeUnitOfWork`, `PooledReservationStore`, `PooledCostLedger` (qua TransactionManager) |
| E (`voice`) | `build_voice_services` | `RealKokoroTts`, `RealWhisperAligner`, `RealFfmpegMediaTool`, `LlmImageSafetyDetector` factory | `FakeTts`, `FakeAligner`, `FakeMediaTool`, `FakeSafetyDetector` | `PostgresVoiceUnitOfWork` (qua TransactionManager) |
| F (`render`) | `build_render_services` | `RealFfmpegRenderer`, `RealFfprobeProbe` | `FakeRenderer`, `FakeProbe` | `PostgresRenderUnitOfWork` (qua TransactionManager) |
| I (`storage`) | `build_storage_services` | `DriveObjectStore` | `InMemoryCloudObjectStore` | `PostgresStorageMetaRepository` factory (qua TransactionManager) |
| J (`config_security`) | `build_config_security_services` | `DpapiSecretStore`, `DriveAccessTokenBroker`, `DriveOAuthConfig` | `InMemorySecretStore`, `InMemoryReservationStore`, `InMemoryCostLedger` | `PostgresAccountStatusPort`, `PooledReservationStore`, `PooledCostLedger` (qua TransactionManager) |

## 6. GIẢ ĐỊNH và các mục mở (Tất cả được ghi nhận rõ là GIẢ ĐỊNH, không phải quyết định)
GIẢ ĐỊNH và mục mở (ghi rõ là GIẢ ĐỊNH, không phải quyết định): (a) sáu cổng được tiêm qua ProductionRuntime (route_catalog, provider_credentials, vision_route, artifact_source, drive_token_broker, gpu_lease) chưa có adapter thật, chủ sở hữu ADAPT-PROD hoặc gói J, G, I; (b) tham số ngoài profile.json lấy từ ProductionRuntime không default: oauth_consent_timeout_seconds, tokenization (revision, unicode_form, casefold, edge_strip_categories, gap_tolerance_ms, min_confidence), route_cost_per_request, drive_placement, drive_fallback_parent_id, đề xuất ADAPT-CONFIG bổ sung; (c) D: capacities trả None, intent_policy bảo thủ, units 1, desktop_online True, max_retries bằng max_attempts trừ 1; (d) staging con 'voice' và 'media', ref artifact là đường dẫn tương đối dưới staging root; (e) trạng thái tài khoản thiếu dòng thì REVOKED; (f) endpoint 9Router giữ dạng có /v1 theo profile, xác nhận ở CP7 (OI-ADAPT-05).

## 7. Giới hạn (Limitations)
Giới hạn: không gọi dịch vụ thật, không đo, không đóng cổng sản xuất; src/main.py chưa gọi các hàm build (thuộc ADAPT-PROD).
