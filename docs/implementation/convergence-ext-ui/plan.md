# Kế hoạch hội tụ mở rộng — IMPL-PLAN-CONVERGENCE-EXT-UI

- **Mã gói**: IMPL-PLAN-CONVERGENCE-EXT-UI (planning_package)
- **Ngày lập**: 20/10/2026
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026; AI PM tự mở gói sau Auditor PASS của IMPL-PLAN-CONVERGENCE.
- **Trạng thái**: kế hoạch; `PRODUCTION_ACTIVATION_BLOCKED` vẫn hiệu lực. Không push, không merge, không chạm main hay backup.
- **Cơ sở**: HEAD `d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7`; trong cây này migration mới có `0001`..`0008` (`CP-3-MIGRATIONS` tạo `0009`..`0018`); chưa có `src/main.py`; `create_app` ở `src/controlplane/api/main.py` mới mount router `session`, `sse`, `control`.
- **Mở rộng**: `docs/implementation/convergence/plan.md`, giữ nguyên mọi cạnh phụ thuộc ở mục 11 và 11.1 của kế hoạch đó.
- **Slice**: `docs/implementation/convergence-ext-ui/slices.md`. **Bằng chứng**: `docs/delivery-evidence/impl-plan-convergence-ext-ui/report.md`.

## 1. Phạm vi và nguyên tắc

Kế hoạch lập bốn slice cho bốn việc nằm ngoài phong bì của IMPL-PLAN-CONVERGENCE (mục 12.1): BL-CV-02, BL-CV-12, BL-CV-05, BL-CV-07. Việc thứ năm của mục đó, BL-CV-13, vẫn BLOCKED (mục 5).

1. Mỗi slice chỉ sửa trong `ownedPaths` của nó và giữ `LOCK-CONVERGENCE`, nên bốn slice chạy tuần tự, mỗi lúc một owner.
2. Không bỏ hay đổi cạnh nào của kế hoạch hội tụ; bốn slice chỉ thêm cạnh: sau `CP-4-WIRING` (hai slice đầu), sau chín cổng `GATE-PERSIST-*` (slice query), sau `CP-4B-UI-SHELL` và `USER-CKPT-D9-D10` (slice màn hình).
3. Test ghim của H được sửa để mở rộng, không làm yếu (mục 4).
4. Không tuyên bố điều chưa làm: màn hình chỉ chuyển sang `available` khi route GET có test; chưa có query thì giữ `pending_module`.
5. Không thêm thư viện, không gọi dịch vụ thật, không sửa `docs/09-contracts/**`, kế hoạch phân hệ A đến J hay `docs/milestones/**/evidence/**`. Import root là `src/`, không tiền tố `src.`.
6. Slice không tự đóng cổng ở mục 12.1 của kế hoạch hội tụ; Control xác nhận phong bì policy cho các đường dẫn của slice rồi mới dispatch.

## 2. Ánh xạ BL-CV sang slice

| Mã | Việc (mục 12.1 của kế hoạch hội tụ) | Slice | Cổng ở mục 12.1 (giữ nguyên) |
| --- | --- | --- | --- |
| BL-CV-02 | Đăng ký event kind: `event_catalog.py` (`BASE_STREAM_EVENT_KINDS`) và danh mục phía client | `CP-4-EVENT-KINDS` | Control mở rộng ownedPaths kèm khóa của owner đường dẫn hoặc mở slice riêng; gói này chính là slice riêng đó. PENDING tới khi Control xác nhận phong bì |
| BL-CV-12 | Bỏ `LIMIT 100` ở `control_api_queries.py` và `next_cursor: None` ở `control.py`, thay bằng phân trang keyset | `CP-4-PAGINATION` | Test PostgreSQL thật trên `PostgresControlQueries` và probe đọc tệp; cần index keyset của migration `0018` (CP-3). PENDING |
| BL-CV-05 | Query CT-API-002 còn thiếu: sources, articles, events, media, hooks, stage runs, sessions, logs, capabilities | `CP-4-QUERIES` | `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` đạt Auditor PASS (chín cổng `GATE-PERSIST-*`); route chỉ gọi service qua port. PENDING |
| BL-CV-07 | Màn hình module trên shell: `backendStatus` khỏi `pending_module`, dựng lại `ui/dist` | `CP-4B-UI-SCREENS` | `CP-4-WIRING` PASS, runtime Node sau `USER-CKPT-D9-D10`; màn hình chưa có route giữ `pending_module`. PENDING |
| BL-CV-13 | Gỡ hoặc khóa `handleTriggerTestError` và `/test-driver` | không có slice | BLOCKED theo quyết định, chờ PUC-H-06 và CP7-H-05; gói này không chạm `components/Header.tsx`, `/test-driver` hay năm spec M2 |

Slice `CP-4B-UI-SHELL` của kế hoạch hội tụ vẫn làm phần nối shell (`StatusPill`, `screenRegistry`, `streamEventKinds`, `boundedEventDeduper`); `CP-4B-UI-SCREENS` chạy sau và xây màn hình module trên shell đó.

## 3. Bốn slice

Chi tiết `ownedPaths`, `dependsOn`, `bindingRefs`, `acceptance` và `testCommands` nằm ở `slices.md`; bảng tóm tắt khóa, cạnh và cách kiểm. Thứ tự chạy: `CP-4-EVENT-KINDS`, `CP-4-PAGINATION`, `CP-4-QUERIES`, `CP-4B-UI-SCREENS` (tuần tự vì cùng giữ `LOCK-CONVERGENCE`).

| Slice | Tệp chính | Khóa | dependsOn | Cách kiểm |
| --- | --- | --- | --- | --- |
| `CP-4-EVENT-KINDS` | `application/sse/event_catalog.py`, `ui/src/api/streamEventKinds.ts`, ba test H về kind và kiểu | `LOCK-CONTROL-API`, `LOCK-SRC-CONTROL-UI`, `LOCK-CONVERGENCE` | `CP-4-WIRING`, `H-03`, `H-14` | pytest `tests/unit/control_ui`; probe so khớp 48 kind hai phía |
| `CP-4-PAGINATION` | `infrastructure/db/control_api_queries.py`, `application/control_api/query_ports.py`, `api/routes/control.py`, test H SQL, test PostgreSQL mới | `LOCK-CONTROL-API`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE` | `CP-4-WIRING`, `CP-3-MIGRATIONS`, `H-02`, `H-04` | pytest PostgreSQL với hơn 100 receipt, batch, job, config; probe không còn `LIMIT 100` |
| `CP-4-QUERIES` | `control_api_queries.py`, `query_ports.py`, `control.py`, `api/main.py`, hai test mới | `LOCK-CONTROL-API`, `LOCK-COMPOSITION-ROOT`, `LOCK-POSTGRES-TEST-DB`, `LOCK-CONVERGENCE` | `CP-4-PAGINATION`, `CP-4-WIRING`, chín `GATE-PERSIST-*`, `H-08` | create_app với service giả và PostgreSQL thật; probe port có đủ phương thức |
| `CP-4B-UI-SCREENS` | `ui/src/screens/**`, `App.tsx`, `client.ts`, `types/api.ts`, `screenRegistry.ts`, `index.css`, `ui/dist/**`, hai test H | `LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`, `LOCK-M2-REGRESSION`, `LOCK-CONVERGENCE` | `CP-4B-UI-SHELL`, `CP-4-QUERIES`, `CP-4-PAGINATION`, `CP-4-EVENT-KINDS`, `USER-CKPT-D9-D10`, `H-15` | `npm run build`; pytest `tests/unit/control_ui`; probe `dist` và nguồn UI; Control chạy `npm run test:e2e` |

### 3.1. CP-4-EVENT-KINDS (BL-CV-02)

Thêm 38 kind sau mười kind cũ (tổng 48). Kind là tiền tố phân hệ, dấu chấm, tên event của `docs/09-contracts/02-domain-events.md` dạng snake_case; `default_registry` đăng ký từng tiền tố.

| Tiền tố | Phân hệ | Kind mới |
| --- | --- | --- |
| `source` | A (10) | `source.registered`, `source.metadata_updated`, `source.removed`, `source.restored`, `source.candidate_discovered`, `source.candidate_resolved`, `source.collection_run_started`, `source.collected_document_available`, `source.collection_run_completed`, `source.collection_run_failed` |
| `ingestion` | B (4) | `ingestion.article_revision_accepted`, `ingestion.duplicate_document_resolved`, `ingestion.event_link_resolved`, `ingestion.event_update_accepted` |
| `creative` | D (6) | `creative.production_snapshot_committed`, `creative.story_angles_generated`, `creative.script_version_created`, `creative.production_plan_created`, `creative.variant_validated`, `creative.output_metadata_created` |
| `voice` | E (4) | `voice.image_safety_assessed`, `voice.media_processing_completed`, `voice.voice_ready`, `voice.word_timing_ready` |
| `render` | F (2) | `render.render_completed`, `render.output_quality_checked` |
| `orchestration` | G (8) | `orchestration.batch_started`, `orchestration.job_allocated`, `orchestration.stage_state_changed`, `orchestration.job_waiting`, `orchestration.job_failed`, `orchestration.video_completed`, `orchestration.batch_target_reached`, `orchestration.batch_exhausted` |
| `storage` | I (2) | `storage.artifact_location_verified`, `storage.cleanup_completed` |
| `config` | J (2) | `config.revision_published`, `config.credential_changed` |

Bảng resync: `SNAPSHOT_RESOURCES` thêm `source` thành `sources`, `ingestion` thành `articles` và `events`, `orchestration` thành `batches`, `jobs`, `stage-runs`; tiền tố còn lại không có màn hình nên rơi về `ALL_SNAPSHOT_RESOURCES`, nay là `operations, batches, jobs, sources, articles, events, media, hooks, stage-runs, sessions, logs` (ba phần tử cũ giữ thứ tự). Python và TypeScript khớp từng phần tử. Slice chỉ đăng ký tên kind, không phát hành event.

### 3.2. CP-4-PAGINATION (BL-CV-12)

- `PostgresControlQueries.batches` và `jobs` gọi `fetch_page(connection, BATCHES_SPEC hoặc JOBS_SPEC, query, workspace_id=...)` của `infrastructure/db/projections/list_queries.py` (chỉ import, không sửa). `operations` (có `LEFT JOIN LATERAL`) và `configs` (khóa `config_revision_id` là uuid) tự dựng SQL keyset trong `control_api_queries.py`: `ORDER BY r.accepted_at DESC, r.receipt_id DESC LIMIT %s` với điều kiện `(r.accepted_at, r.receipt_id) < (%s::timestamptz, %s::uuid)`; `configs` theo `(created_at, config_revision_id)`. Lấy `limit + 1` dòng, `build_page` cắt và sinh `next_cursor`; mọi giá trị người dùng chỉ đi qua tham số.
- `query_ports.py`: bốn phương thức danh sách của `ControlQueryPort` và `ControlApiQueryService` nhận thêm `query: ListQuery` và trả `Page`; phương thức lấy một bản ghi giữ nguyên.
- `control.py`: bốn route danh sách dùng `parse_list_query` (`default_limit` 50, `max_limit` 100). `parse_list_query` mặc định `direction=asc` còn dữ liệu hiện nay trả mới nhất trước, nên route điền sẵn `direction=desc` khi client không gửi. Bộ lọc cho phép: batches `status`; jobs `batch_id`, `status`; operations và configs không có. `ListQueryError` đổi thành `ValueError` để `create_app` trả 422 `VALIDATION_ERROR`. Phản hồi vẫn `{items, next_cursor}` với `next_cursor` lấy từ `Page`; cấm literal `next_cursor: None` trong `control.py`. Service giả trong `tests/m2` nhận `**kwargs` nên không vỡ.
- Index: migration `0018` có `(workspace_id, created_at DESC, id DESC)` cho batches, jobs và `(workspace_id, accepted_at DESC, receipt_id DESC)` cho receipts; `cp_config_revisions` chưa có index keyset riêng (OI-EXT-UI-03).
- Test PostgreSQL thật `tests/integration/convergence/test_cp4_pagination_postgres.py`: gọi trực tiếp `PostgresControlQueries` (không qua service giả), tạo hơn 100 receipt có `operation_id`, batch, job và config revision; đi hết các trang bằng `next_cursor` ở `limit` 25 và 100: đủ mọi dòng, không lặp, không sót, trang cuối có `next_cursor` là `None`; cursor sai qua `create_app` trả 422.

### 3.3. CP-4-QUERIES (BL-CV-05)

- Chín tài nguyên GET chỉ đọc, có phân trang keyset, dưới `/v1/`: `sources`, `articles`, `events`, `media`, `hooks`, `stage-runs`, `sessions`, `logs`, `capabilities`. Không route chi tiết, không route ghi.
- `query_ports.py` thêm Protocol cho chín query và chín phương thức trong `ControlApiQueryService` (`sources`, `articles`, `events`, `media`, `hooks`, `stage_runs`, `sessions`, `logs`, `capabilities`), nhận `connection`, `workspace_id`, `query: ListQuery`, trả `Page`. `control_api_queries.py` thêm `ListSpec` cho từng tài nguyên và gọi `fetch_page`; chỉ SELECT, không import adapter của phân hệ khác.
- Bảng và cột lấy từ migration thật `0009`..`0018` (Worker mở tệp, test đối chiếu `information_schema`); tên bảng ở mục 5.2 của kế hoạch hội tụ là GIẢ ĐỊNH. Cột chọn đúng `columns` của `screenRegistry.ts`, cộng `revision` ở `sources`, `media`, `hooks` để UI gửi `If-Match`; không bao giờ chọn `article_body`, nội dung `script`, `secret`.
- Thiếu bảng hoặc cột (nhất là `sessions`, `logs`, `capabilities`; OI-EXT-UI-04) thì tài nguyên đó BLOCKED kèm `blocked-manifest` `DEPENDENCY_GAP` (owner `CP-3-MIGRATIONS`); không bịa bảng, không thêm migration; `CP-4B-UI-SCREENS` giữ màn hình đó `pending_module`.
- Route dùng `build_listing_router(prefix, fetch_page, allowed_sorts, allowed_filters, default_limit=50, max_limit=100)` của H, mount trong `create_app`. Nếu `CP-4-WIRING` đã mount một tiền tố thì chỉ cấp `fetch_page` cho mount đó: mỗi tiền tố đúng một lần mount (test đếm `app.routes`). `workspace_id` chỉ lấy từ `request.state.identity`; mặc định mới nhất trước.
- Test: `test_cp4_queries_routes.py` (create_app với service giả) và `test_cp4_queries_postgres.py` (PostgreSQL thật, hơn 100 dòng mỗi tài nguyên có bảng, cô lập theo workspace).

### 3.4. CP-4B-UI-SCREENS (BL-CV-07)

- `screens/ModuleListScreen.tsx`: bảng chỉ đọc dựng từ một `ScreenSpec` (cột theo `columns`), nạp trang qua `fetchModulePage(resourcePath, cursor)`, nút «Tải thêm» khi `next_cursor` khác null; ô hiển thị bằng text của React, không sink HTML. `screens/EditableMetadataScreen.tsx` cho ba màn hình `sources`, `media`, `hooks`: form chỉ hiện trường nằm trong `editableFields`, gửi PATCH đến `resourcePath/{id}` với `If-Match` là `revision` của dòng và `Idempotency-Key` mới mỗi lần Lưu, chỉ gửi trường đã đổi; `REVISION_CONFLICT` (409) thì nạp lại dòng và báo bằng tiếng Việt; `article_body`, `script`, `secret` không bao giờ vào form.
- `client.ts` thêm `fetchModulePage` và `patchModuleItem` (fetch chỉ ở file này, không literal endpoint cấm của guard H-16); `types/api.ts` thêm kiểu trang; `App.tsx` dựng điều hướng từ `SCREEN_REGISTRY`: màn hình `available` có thẻ, `pending_module` bị khóa với nhãn «Chưa có backend» và không fetch. Giữ nguyên bốn thẻ cũ (`tab-operations`, `tab-command`, `tab-batches`, `tab-jobs`) và `onOpenTestError` vì spec M2 cần.
- `screenRegistry.ts`: chỉ chuyển `backendStatus` sang `available` cho tài nguyên mà `CP-4-QUERIES` đã có route và test (mặc định tám: sources, articles, events, media, hooks, stage-runs, sessions, logs); thêm `revision` vào `columns` của `sources`, `media`, `hooks`; giữ nguyên `editableFields`, `readOnly`, 18 id theo thứ tự. Sáu màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost` giữ `pending_module` vì BL-CV-05 không có query cho chúng.
- Dựng lại `ui/dist` sau bản dựng của `CP-4B-UI-SHELL`: `npm run build` trong `src/controlplane/ui`, xóa mọi tệp băm không còn được `index.html` tham chiếu, commit cùng nguồn; `allowLarge: true` chỉ cho `src/controlplane/ui/dist/**`. `npm run test:e2e` do Control chạy.

## 4. Test ghim của H phải sửa cùng lượt

Các test dưới đây ghim trạng thái trước hội tụ nên hỏng khi slice tương ứng chạy. Mỗi test được sửa trong chính slice làm nó hỏng, theo hướng mở rộng: giữ mọi ca kiểm cũ còn đúng, thêm ca cho phần mới, không xóa, không skip, không đổi `==` thành `<=` cho tập đã biết.

1. `tests/unit/control_ui/test_h_stream_event_catalog.py` (`CP-4-EVENT-KINDS`). Ghim: đúng mười kind (`EXPECTED_BASE`, `len == 10`), đúng ba tiền tố, 11 kind sau khi đăng ký `source.registered`, `SNAPSHOT_RESOURCES` đúng ba khóa, `ALL_SNAPSHOT_RESOURCES` đúng ba phần tử, và đọc danh sách `const eventKinds = [` từ `client.ts`. Sửa: `EXPECTED_BASE` thành tiền tố của tuple mới (`BASE_STREAM_EVENT_KINDS[:10]`); thêm `EXPECTED_MODULE` đúng 38 tên và khẳng định đủ 48 kind, không trùng; đúng 11 tiền tố; kind dò `source.registered` đổi thành `source.zz_probe` vì kind cũ nay đã có; `SNAPSHOT_RESOURCES` đúng sáu khóa; `ALL_SNAPSHOT_RESOURCES` đúng 11 phần tử; ca đọc `client.ts` chấp nhận hai dạng (còn danh sách thì phải là tập con của danh mục; đã dùng `STREAM_EVENT_KINDS` thì phải import `streamEventKinds`) vì `CP-4B-UI-SHELL` bỏ danh sách đó.
2. `tests/unit/control_ui/test_h_stream_client_registry.py` (`CP-4-EVENT-KINDS`). Ghim: `len(kinds) == 10` và khóa bảng resync bằng đúng tập tiền tố của kind. Sửa: 48 kind đúng thứ tự `BASE_STREAM_EVENT_KINDS`; khóa bảng bằng khóa Python và là tập con tiền tố; hợp resource bằng `ALL_SNAPSHOT_RESOURCES`. Giữ nguyên ca hàm `snapshotResourcesFor`, deduper, tính thuần, UTF-8.
3. `tests/integration/control_ui/test_h_list_queries_sql.py` (`CP-4-PAGINATION`). Ghim: `test_specs_match_control_api_queries` bắt buộc `LIMIT 100` trong `batches` và `jobs`. Sửa: kiểm AST rằng `batches`, `jobs` gọi `fetch_page` với `BATCHES_SPEC`, `JOBS_SPEC` và không còn chuỗi `LIMIT 100`; thêm ca kiểm SQL của `operations`, `configs` (có `LIMIT %s`, không `OFFSET`, giá trị chỉ ở tham số); giữ nguyên mọi ca khác (builder, whitelist, cursor, QR-PERF-005).
4. `tests/unit/control_ui/test_h_screen_registry.py` (`CP-4B-UI-SCREENS`). Ghim: `AVAILABLE_IDS` bốn màn hình, 14 màn hình còn lại `pending_module`, danh sách GET chỉ đọc từ `control.py`. Sửa: `AVAILABLE_IDS` là tập available thật (mặc định 12), số còn lại bằng 18 trừ số available; thêm ghim sáu màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost` vẫn `pending_module`; `router_get_paths` tính thêm tiền tố `build_listing_router` mount ở `api/main.py`; giữ nguyên ghim allowlist sửa được, trường cấm, 18 id theo thứ tự, endpoint cấm.
5. `tests/unit/control_ui/test_h_ts_contract_types.py` (`CP-4-EVENT-KINDS`, rồi `CP-4B-UI-SCREENS`). Ghim: `test_api_ts_unchanged_in_scope` khẳng định `OperationItem` chưa có `wait_reason`, sẽ hỏng ngay khi `CP-4B-UI-SHELL` mở rộng `OperationItem`. Bước đầu chuyển thành có điều kiện (nếu có thì phải là `wait_reason?:` tùy chọn như `OPTIONAL_FIELDS`; giữ khẳng định `api.ts` không nhắc `operationView`, `listPage`) để xanh cả trước và sau `CP-4B-UI-SHELL`; sau đó `CP-4B-UI-SCREENS` siết lại: `OperationItem` có đủ sáu trường tùy chọn `progress`, `started_at`, `updated_at`, `finished_at`, `wait_reason`, `problem`.

## 5. Phần không làm

1. Phát hành event ở phân hệ (publisher, outbox, `append_event`): ngoài phong bì. BL-CV-02 chỉ đăng ký tên kind; tới khi phân hệ phát, danh mục có kind nhưng chưa có event nào mang kind đó. Không tuyên bố đã phát hành.
2. Lưu receipt cho lệnh CT-API-003..006 ở `src/controlplane/infrastructure/db/control_api_commands.py`: không sửa tệp này; lệnh vẫn thuộc `CP-4-WIRING` và phân hệ chủ sở hữu. Không tuyên bố đã làm lệnh CT-API-003..006.
3. Sáu màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost`: BL-CV-05 không có query tương ứng nên giữ `pending_module`, không route, không fetch.
4. `components/Header.tsx`, `handleTriggerTestError` và đường `/test-driver/issue-capability` (BL-CV-13, BLOCKED theo quyết định); năm spec M2 trong `tests/m2/e2e/` giữ nguyên byte; spec mới `tests/m2/e2e/cp4b-*.spec.ts` do Control.
5. Kế hoạch phân hệ A đến J, `docs/09-contracts/**`, migration, `api/wiring/**`, `config/adapter.py`, adapter `PERSIST-*`, lockfile, `docs/milestones/**/evidence/**`.
6. Route chi tiết `/v1/<tài nguyên>/{id}` cho chín query mới và mọi route ghi.
7. Event của C (chín kind media và hook) chưa đăng ký (OI-EXT-UI-01).

## 6. Chuỗi «nguồn RSS sửa được trên UI»

| Bước | Chủ | Việc |
| --- | --- | --- |
| 1 | `CP-4-WIRING` (kế hoạch hội tụ) | Mount router liệt kê và metadata của H trong `create_app`; PATCH `/v1/sources/{item_id}` qua `build_metadata_router` với allowlist `tier`, `topic_tags`, `notes`, `enabled`; `apply_update` do service của A cấp qua `app.state` |
| 2 | `ADAPT-PROD` (gói riêng, ngoài kế hoạch này) | Gắn service thật của A (kho PostgreSQL của `PERSIST-A`, lệnh nguồn) vào `app.state`; tới đó PATCH chưa ghi được dữ liệu thật |
| 3 | `CP-4-QUERIES` | GET `/v1/sources` có phân trang keyset và cột `revision` |
| 4 | `CP-4B-UI-SCREENS` | Màn hình Nguồn tin: bảng, form sửa bốn trường được phép, PATCH với `If-Match` và `Idempotency-Key`; 409 thì nạp lại; không gửi `article_body`, `script`, `secret` |
| 5 | Control | Chạy `npm run test:e2e`; sửa nguồn RSS bằng dữ liệu thật thuộc CP7 |

Kế hoạch này không tuyên bố nguồn RSS đã sửa được: chỉ khi bốn bước đầu đều PASS và `ADAPT-PROD` đã gắn service thật.

## 7. Mục mở và mặc định đã chọn (D8)

Không mục nào là đã duyệt; mục cần user vẫn nằm ở danh sách chờ của kế hoạch hội tụ.

| Mã | Nội dung | Mặc định | Lý do |
| --- | --- | --- | --- |
| OI-EXT-UI-01 | Event của C (chín kind media, hook) không có trong mục 6 của kế hoạch hội tụ | Chưa đăng ký; màn hình media và hook nạp lại qua resync dự phòng | Không mở rộng phạm vi ngoài danh sách đã duyệt |
| OI-EXT-UI-02 | Tiền tố `ingestion`, `creative`, `voice`, `render`, `orchestration`, `storage`, `config` và tên snake_case là cách đặt tên của kế hoạch này (GIẢ ĐỊNH) | Dùng bảng ở mục 3.1; Control đối chiếu với `02-domain-events.md` khi nghiệm thu | Một tiền tố một phân hệ, dễ kiểm bằng `StreamKindRegistry` |
| OI-EXT-UI-03 | `cp_config_revisions` chưa có index keyset riêng (`0018` chỉ index receipts, batches, jobs) | Chấp nhận ở quy mô v1, ghi backlog; không thêm migration | Bảng nhỏ, không đổi `0018` |
| OI-EXT-UI-04 | Nguồn dữ liệu của `sessions`, `logs`, `capabilities` chưa xác nhận trong migration | Worker đọc `0009`..`0018` thật; thiếu bảng đủ cột thì tài nguyên BLOCKED (`DEPENDENCY_GAP`, `CP-3-MIGRATIONS`) và màn hình giữ `pending_module` | Không bịa bảng; không mở màn hình khi chưa có query |
| OI-EXT-UI-05 | Khoảng trống thứ tự: `CP-4B-UI-SHELL` bỏ danh sách `eventKinds` ở `client.ts` và mở rộng `OperationItem`, làm hỏng hai test H nêu ở mục 4 | Control dispatch `CP-4-EVENT-KINDS` trước `CP-4B-UI-SHELL`; không thêm cạnh vào kế hoạch hội tụ | Giữ nguyên cạnh của kế hoạch hội tụ |
| OI-EXT-UI-06 | `ownership-and-locks.yaml` chưa phủ `application/sse/**`, `application/control_api/**`, `api/routes/**`, `infrastructure/db/control_api_*.py`, `tests/unit/control_ui/**`, `tests/integration/convergence/**` (chỉ `api/main.py` và `ui/**` có owner) | Control xác nhận phong bì kèm khóa `LOCK-CONTROL-API`; gói này không sửa registry (thuộc `CP-2D-REGISTRY`) | Thiếu phủ thì slice BLOCKED, không đổi khóa |

## 8. Kiểm, kích thước và ngoài phạm vi

- Cổng của kế hoạch này là phép kiểm trong `docs/delivery-evidence/impl-plan-convergence-ext-ui/report.md`: `git diff --check` và probe đọc `plan.md`, `slices.md` (đúng bốn slice, mỗi slice đủ `ownedPaths`, `dependsOn`, `bindingRefs`, `testCommands`, `acceptance`, cạnh phụ thuộc đúng).
- `slices.md` có bốn mục, mỗi mục không quá 7000 ký tự, tổng không quá 38000 ký tự để gói biên dịch dưới 60000 ký tự.
- Ngoài phạm vi: mã nguồn `src/**`, migration, sửa kế hoạch phân hệ, sửa `docs/milestones/**/evidence/**`, tài nguyên thật (CP7), kích hoạt sản xuất, push và merge.
