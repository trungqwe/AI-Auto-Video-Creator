# Báo cáo chuyển giao CP-4-QUERIES: Triển khai truy vấn danh sách Control API (M7)

## 1. Phạm vi thực hiện
Đã thực hiện triển khai gói công việc `CP-4-QUERIES` đúng và đủ theo phạm vi 7 tệp thuộc quyền sở hữu (`owned paths`):
1. `src/controlplane/infrastructure/db/control_api_queries.py`: bổ sung `STAGE_RUNS_SPEC`, `LIST_SPECS`, `BLOCKED_LIST_RESOURCES`, phương thức `stage_runs` và 8 phương thức chỉ ném `CapabilityUnavailableError`. Không có chuỗi cấm `LIMIT 100`, `OFFSET`, `payload`, `secret`, `article_body`.
2. `src/controlplane/application/control_api/query_ports.py`: bổ sung 9 phương thức danh sách chỉ đọc vào `ControlQueryPort` và `ControlApiQueryService`.
3. `src/controlplane/api/routes/control.py`: bổ sung `QueryListing`, `QUERY_LISTINGS` và hàm `build_query_listing_routers()` mount duy nhất GET `/v1/stage-runs` qua `build_listing_router`.
4. `src/controlplane/api/main.py`: mount router từ `build_query_listing_routers()` một lần duy nhất trong `_mount_module_routers`.
5. `tests/integration/convergence/test_cp4_queries_routes.py`: kiểm thử tích hợp route, xác thực schema phản hồi, bộ lọc whitelist, từ chối không có phiên hợp lệ và kiểm kê route.
6. `tests/integration/convergence/test_cp4_queries_postgres.py`: kiểm thử tích hợp trên PostgreSQL 18.6 thật qua `PostgresControlQueries`, duyệt trang keyset đầy đủ không lặp không sót trên 230 dòng workspace A và 130 dòng workspace B, cô lập workspace và kiểm tra information_schema.
7. `docs/delivery-evidence/cp-4-queries/report.md`: tài liệu báo cáo nghiệm thu và evidence.

Cam kết tuân thủ ranh giới:
- Không sửa `src/controlplane/infrastructure/db/control_api_commands.py`.
- Không thêm bất kỳ tệp migration nào, không sửa migration hiện có.
- Không thêm route ghi (POST/PATCH/PUT/DELETE) hay route chi tiết (fetch_one) cho `stage-runs`.
- Không phát event nào ra outbox hay event stream.
- Không tuyên bố đã làm các lệnh `CT-API-003..006`.
- Không import bất kỳ adapter hay mã nguồn từ các phân hệ ngoài (`source_ingestion`, `ingestion`, `catalog`, `creative`, `voice`, `render`).

## 2. Bằng chứng kiểm thử RED (Bước 5)
Lệnh thực thi trước khi sửa mã nguồn ứng dụng:
```bash
python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p no:cacheprovider
```
Kết quả kiểm thử ghi nhận RED hợp lệ (Exit code: 1):
Ba dòng FAILED đầu tiên:
```
FAILED tests/integration/convergence/test_cp4_queries_routes.py::test_stage_runs_page_shape
FAILED tests/integration/convergence/test_cp4_queries_routes.py::test_asc_override_and_cursor_condition
FAILED tests/integration/convergence/test_cp4_queries_routes.py::test_filters_whitelisted
```
Dòng tóm tắt nguyên văn:
```
24 failed, 6 passed, 1 warning in 4.21s
```
Oracle RED xác nhận route trả về 404 do chưa mount, `ControlApiQueryService` và `PostgresControlQueries` chưa có các phương thức truy vấn mới và `control_api_queries` chưa có `LIST_SPECS`. Cả hai tệp thu thập test thành công, không gặp lỗi collection error.

## 3. Bằng chứng kiểm thử GREEN (Bước 10–15)
- **Bước 10:** Chạy lại hai bộ kiểm thử tích hợp convergence
  - Lệnh: `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p no:cacheprovider`
  - Exit code: `0`
  - Tóm tắt: `30 passed, 1 warning in 3.97s`
- **Bước 11:** Chạy probe bắt buộc kiểm tra port và từ cấm cơ bản
  - Lệnh: `python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); n = ['sources', 'articles', 'events', 'media', 'hooks', 'stage_runs']; assert all(('def ' + k + '(') in p for k in n), 'port methods'; assert 'LIMIT 100' not in q and 'article_body' not in q, 'no LIMIT 100 and no article_body'"`
  - Exit code: `0`
  - Tóm tắt: `Exit code 0, không AssertionError`
- **Bước 12:** Chạy probe bổ sung kiểm tra đủ 9 phương thức và không có từ cấm
  - Lệnh: `python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); n = ['sources', 'articles', 'events', 'media', 'hooks', 'stage_runs', 'sessions', 'logs', 'capabilities']; assert all(('def ' + k + '(') in p and ('def ' + k + '(') in q for k in n), 'nine methods'; assert not any(w in q.lower() for w in ['limit 100', 'offset', 'payload', 'secret', 'article_body']), 'forbidden words'"`
  - Exit code: `0`
  - Tóm tắt: `Exit code 0, chín phương thức đầy đủ và không chứa từ cấm`
- **Bước 13:** Kiểm tra hồi quy toàn bộ tích hợp và unit control_ui
  - Lệnh: `python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider`
  - Exit code: `0`
  - Tóm tắt: `2493 passed, 35 skipped, 1 warning, 25 subtests passed in 102.56s (0:01:42)`
- **Bước 14:** Kiểm tra hồi quy suite M2 với bài test h36 được hoãn theo quyết định của user
  - Lệnh: `python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression`
  - Exit code: `0`
  - Tóm tắt: `179 passed, 1 deselected, 2 warnings in 200.94s (0:03:20)`
- **Bước 15:** Kiểm tra khoảng trắng và định dạng cuối dòng
  - Lệnh: `git diff --check`
  - Exit code: `0`
  - Tóm tắt: `Exit code 0, không có cảnh báo khoảng trắng hoặc dòng cuối`

## 4. Bảng trạng thái chín tài nguyên danh sách Control API
Dưới đây là bảng trạng thái cho 9 tài nguyên truy vấn danh sách:

| Tài nguyên | Bảng cơ sở dữ liệu | Trạng thái | Lý do / Cột chi tiết |
| --- | --- | --- | --- |
| `stage-runs` | `controlplane.cp_stage_runs` | SẴN SÀNG | Bảng từ migration 0006 và 0011. Khóa sắp xếp keyset: `created_at` (NOT NULL) và `stage_run_id`; cột chọn: `stage_run_id`, `job_id`, `stage_name` (trả về dưới tên `stage`), `status`, `started_at` (có thể NULL), `finished_at`, `created_at`. Bộ lọc cho phép: `job_id`, `status`. Mount route GET `/v1/stage-runs`. |
| `sources` | `controlplane.cp_sources` | BLOCKED | `DEPENDENCY_GAP`: Thiếu các cột `tier`, `topic_tags`, `notes`, `enabled` dưới dạng cột cơ sở dữ liệu riêng biệt (hiện chỉ nằm gói gọn trong trường JSON). Không mount route mới; giữ nguyên mount 503 từ CP-4-WIRING. |
| `articles` | `controlplane.cp_articles` | BLOCKED | `DEPENDENCY_GAP`: Thiếu các cột `source_id`, `title`, `published_at`, `fetch_evidence_ref` ở bảng dữ liệu. Không mount route mới. |
| `events` | `controlplane.cp_events` | BLOCKED | `DEPENDENCY_GAP`: Thiếu các cột `title`, `status`, `source_id`, `fetch_evidence_ref` ở bảng dữ liệu. Không mount route mới. |
| `media` | `controlplane.cp_media_assets` | BLOCKED | `DEPENDENCY_GAP`: Thiếu các cột `kind`, `tags`, `notes` ở bảng dữ liệu `cp_media_assets`. Không mount route mới; giữ nguyên mount 503 từ CP-4-WIRING. |
| `hooks` | `controlplane.cp_hooks` | BLOCKED | `DEPENDENCY_GAP`: Thiếu các cột `tags`, `description`, `notes` ở bảng dữ liệu `cp_hooks`. Không mount route mới; giữ nguyên mount 503 từ CP-4-WIRING. |
| `sessions` | `controlplane.cp_app_sessions` | BLOCKED | `DEPENDENCY_GAP`: Thiếu cột `job_id` ở bảng `cp_app_sessions`. Không mount route mới. |
| `logs` | Không có bảng | BLOCKED | `DEPENDENCY_GAP`: Không có bảng nhật ký trong schema `controlplane` (thiếu `log_id`, `severity`, `message`). Không mount route mới. |
| `capabilities` | Không có bảng | BLOCKED | `DEPENDENCY_GAP`: Không có bảng năng lực và không có định nghĩa cột trong `screenRegistry.ts`. Không mount route mới. |

Ghi chú về route:
- Tám tài nguyên bị chặn hoàn toàn không được bổ sung route mới.
- Ba tài nguyên `sources`, `hooks`, `media` giữ nguyên router do CP-4-WIRING mount trước đó (trả về lỗi 503 `CAPABILITY_UNAVAILABLE`).
- Các tài nguyên `articles`, `events`, `sessions`, `logs`, `capabilities` không có route nào trong `app.routes`.
- Tổng số route trong `app.routes` khớp chính xác danh sách tài nguyên sẵn sàng (được kiểm chứng qua `test_route_inventory`).

## 5. Danh sách Blocked Manifests
```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0012_source_ingestion.sql"], "ids": ["sources.tier", "sources.topic_tags", "sources.notes", "sources.enabled"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0012_source_ingestion.sql"], "ids": ["articles.source_id", "articles.title", "articles.published_at", "articles.fetch_evidence_ref"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0013_ingestion.sql"], "ids": ["events.title", "events.status", "events.source_id", "events.fetch_evidence_ref"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0010_storage_meta_extensions.sql", "src/controlplane/infrastructure/db/migrations/0017_render.sql"], "ids": ["media.kind", "media.tags", "media.notes"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0015_creative.sql"], "ids": ["hooks.tags", "hooks.description", "hooks.notes"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql"], "ids": ["sessions.job_id"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": ["src/controlplane/infrastructure/db/migrations/0009_config_security_extensions.sql", "src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql"], "ids": ["logs.log_id", "logs.severity", "logs.message"]}
```

```blocked-manifest
{"step": 16, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["CP-3-MIGRATIONS"], "paths": [], "ids": ["capabilities.table_missing"]}
```

## 6. Trạng thái BL-CV-05
- **Trạng thái:** `IN_PROGRESS`
- **Kết quả nghiệm thu danh sách:** 1/9 tài nguyên sẵn sàng (`stage-runs`), 8/9 tài nguyên bị chặn (`BLOCKED` do `DEPENDENCY_GAP`).
- **Xác nhận cổng:** Các cổng `GATE-PERSIST-A`, `GATE-PERSIST-B`, `GATE-PERSIST-C`, `GATE-PERSIST-D`, `GATE-PERSIST-E`, `GATE-PERSIST-F`, `GATE-PERSIST-G`, `GATE-PERSIST-I`, `GATE-PERSIST-J` đã được Control xác nhận tính hợp lệ khi điều phối gói công việc này. Worker tuân thủ ranh giới quyền hạn, không tự kiểm Auditor PASS hay đọc lại báo cáo audit ngoài phạm vi được giao.
- **Ranh giới ADAPT-PROD:** Việc gắn kết các dịch vụ thật của Phân hệ A vào `app.state.module_services` thuộc gói công việc `ADAPT-PROD`, không nằm trong phạm vi của gói `CP-4-QUERIES` này.

## 7. Giới hạn kỹ thuật và Mục mở
1. Phân trang keyset của `stage-runs` sắp xếp theo `created_at` kết hợp `stage_run_id` làm tie-breaker. Bảng `controlplane.cp_stage_runs` hiện chưa có index phức hợp riêng cho bộ đôi này vì gói công việc không được phép bổ sung hay sửa đổi file migration.
2. Việc mở khóa 8 tài nguyên danh sách còn lại phụ thuộc vào gói `CP-3-MIGRATIONS` bổ sung các cột dữ liệu quan hệ tương ứng hoặc người dùng phê duyệt phương án trích xuất trực tiếp từ các trường JSON hiện có.
3. Chỉ duy nhất `stage-runs` đạt trạng thái sẵn sàng phục vụ truy vấn danh sách chỉ đọc qua endpoint `/v1/stage-runs`.