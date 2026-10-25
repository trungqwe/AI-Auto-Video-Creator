# Kế hoạch nối route chỉ đọc cho các màn hình Dashboard đang khoá — IMPL-PLAN-READ-SCREENS

Nguồn: task `IMPL-PLAN-READ-SCREENS` (planning_package). Slice chi tiết ở `docs/implementation/read-screens/slices.md`. Kế hoạch chỉ là tài liệu: không sửa `src/**`, migration hay `ui/dist`.

## 1. Mục tiêu, phạm vi và nguồn quyền

- Mục tiêu: user nghiệm thu R1–R6 của CP7 (`docs/implementation/cp7/plan.md` mục 5) trên giao diện thật, nên các màn đang `pending_module` phải có route GET chỉ đọc nối dữ liệu thật.
- Phạm vi: mười tài nguyên có bảng sẵn: `articles`, `events`, `media`, `artifacts`, `snapshots`, `story-angles`, `scripts`, `sessions`, `accounts`, `cost`. Riêng `logs` không có bảng riêng; mục 5.11 khảo sát nguồn và kết luận.
- Không thêm migration, không đổi schema, không đổi domain hay repository của phân hệ, không đổi hợp đồng Control API của bảy màn đang `available` (`operations`, `batches`, `jobs`, `configs`, `sources`, `hooks`, `stage-runs`).
- Không đụng `tools/launcher/**` (gói ADAPT-LAUNCH-FIX2) và `src/controlplane/infrastructure/production_ports/**` (kế hoạch prod-ports). Không sửa main hay backup, không đọc hay in bí mật.
- Nguồn quyền: user duyệt Phần B ngày 18/10/2026 và ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`); `PRODUCTION_ACTIVATION_BLOCKED` vẫn hiệu lực. Điều chưa chắc ghi `GIẢ ĐỊNH` ở mục 10, không ghi là đã duyệt.

## 2. Hiện trạng đo thật (25/10/2026)

Đo trên HEAD nhánh tích hợp bằng ứng dụng production dựng qua `build_production_app`:

- Trong 18 màn của `src/controlplane/ui/src/features/screens/screenRegistry.ts` chỉ 7 màn `available`.
- `GET /v1/media` trả 503 `CAPABILITY_UNAVAILABLE`: `media` có trong `LISTING_RESOURCES` (`route_catalog.py:50-58`) nhưng `build_production_app` chỉ gắn `sources` và `hooks` vào `module_services` (`production.py:393-394`).
- `GET /v1/articles`, `events`, `artifacts`, `snapshots`, `story-angles`, `scripts`, `sessions`, `logs`, `accounts`, `cost` trả 404 vì không có route.
- CP-4-QUERIES (`docs/delivery-evidence/cp-4-queries/report.md` mục 4) ghi BLOCKED vì «thiếu cột». Khảo sát mục 3.3 cho thấy dữ liệu có trong cột `payload` JSONB hoặc bảng liên quan. `sources` và `hooks` đã nối bằng service của phân hệ (`SourceModuleService` `production.py:193-250`, `HookModuleService` `production.py:264-307`) mà không cần migration; kế hoạch này làm cùng cách.

## 3. Khảo sát (tệp:dòng, HEAD 2f7f8d9)

### 3.1. Route và wiring Control API

- `src/controlplane/application/control_api/route_catalog.py`: `ListingResource` 13-21; `LISTING_RESOURCES` 31-59 chỉ có `sources` (32-40), `hooks` (41-49), `media` (50-58); `METADATA_RESOURCES` 61-77 có `sources`, `hooks`, `media` (72-76, cho phép `description`, `tags`, `notes`).
- `src/controlplane/api/main.py`: `_module_service` 68-72 (thiếu service thì ném `CapabilityUnavailableError`, middleware đổi thành 503 ở 174-176); `_listing_callbacks` 75-82; `_update_callback` 85-95 (gọi `service.apply_update`); `_mount_module_routers` 98-121 (vòng listing 99-111, metadata 112-119, query router 120-121); `app.state.module_services = {}` ở dòng 139; `ValueError` thành 422 ở dòng 186.
- `src/controlplane/api/routes/control.py`: `QueryListing` 257-263; `QUERY_LISTINGS` 266-268 chỉ có `/v1/stage-runs`; `_query_fetch_page` 271-280 (mặc định `direction=desc` khi request không gửi `direction`); `build_query_listing_routers` 283-291.
- `src/controlplane/api/routes/modules/read_only_listing.py`: `build_listing_router` 19-46; GET danh sách 26-35 trả `{items, next_cursor}`; GET chi tiết `prefix/{item_id}` 38-45, `fetch_one` trả `None` thì 404 `NOT_FOUND`; workspace luôn lấy từ `request.state.identity` (dòng 27 và 39).
- `src/controlplane/application/projections/list_query.py`: `ListQuery` 35-40, `Page` 43-46, `encode_cursor` 49-56, `parse_list_query` 86-143 (filter ngoài danh sách cho phép là `filter_not_allowed`), `build_page` 146-157 (cursor lấy từ `sort_field` và `id_field` của dòng cuối, cả hai phải là chuỗi).
- `src/controlplane/infrastructure/db/control_api_queries.py`: `STAGE_RUNS_SPEC` 21-35; `BLOCKED_LIST_RESOURCES` 38-47; tám phương thức ném `CapabilityUnavailableError` ở 222-244. Kế hoạch KHÔNG sửa tệp này vì hai test ghim khóa của nó: `tests/integration/convergence/test_cp4_queries_postgres.py:239-241` và `test_cp4_queries_routes.py:241`.

### 3.2. Composition root production

- `src/controlplane/api/wiring/production.py`: `_build_services` 87-95; `HookModuleService` 264-307 (`fetch_page` 273-287, `fetch_one` 289-295, `apply_update` 297-307); `compose_hooks_module` 310-318 (mở `manager.unit_of_work()` mỗi lời gọi); `build_production_app` 385-398 với hai dòng gắn service ở 393-394; `__all__` 458-471.
- `src/controlplane/infrastructure/db/uow.py:93-97`: `TransactionManager.unit_of_work()` và `borrow_connection()`. Service đọc mới dùng `borrow_connection()` như `control.py:275`.
- Mẫu nhân rộng: service có `fetch_page(request, workspace_id, query) -> Page` và `fetch_one(request, workspace_id, item_id) -> dict | None`, sắp keyset theo `(sort_field, id_field)`, lọc theo workspace.

### 3.3. Từng bảng: migration, mã đọc sẵn có, khóa payload cho từng cột registry

Migration nằm ở `src/controlplane/infrastructure/db/migrations/`. Số dòng registry là của `screenRegistry.ts`.

| Màn | Bảng và migration | Mã đọc/ghi sẵn có | Cột registry ← nguồn thật |
| --- | --- | --- | --- |
| `articles` (registry 88-98) | `cp_articles` (`0013_ingestion.sql:9-21`: `revision`, `payload`) và `cp_article_revisions` (23-31) | `PostgresArticleRepository` `src/ingestion/persistence/repositories.py:41-153` (`get` 50-68, `save` 102-141) | `article_id`, `revision` ← cột của `cp_articles`; `source_id`, `title`, `published_at` ← khóa cùng tên trong `payload` của bản mới nhất ở `cp_article_revisions` (`ArticleRevision` `src/ingestion/domain/article.py:12-37`); `fetch_evidence_ref` ← khóa `raw_snapshot_ref` (có thể null) |
| `events` (99-109) | `cp_events` (`0013:55-63`: `revision`, `payload`) | `PostgresEventRepository` 198-235; dict sự kiện ở `src/ingestion/application/resolve_event_link.py:111-121` (`event_id`, `status`, `revision`, `topic`, `member_refs`, `effective_time_range`, `created_at`, `updated_at`) | `event_id`, `revision` ← cột; `status` ← khóa `status`; `title`, `source_id`, `fetch_evidence_ref` KHÔNG có trong payload sự kiện, lấy từ bản bài của thành viên đầu `member_refs[0]` (mục 5.2) |
| `media` (110-120) | `cp_media_assets` (`0014_catalog.sql:9-24`: `status`, `revision`, `payload`, `updated_at`) | `PostgresMediaAssetRepository` `src/catalog/persistence/assets.py:40-93`; payload dựng ở `src/catalog/persistence/mapping.py:36-41` (`kind`, `rights.status`, `discovery_ids`) | `media_id` ← `media_asset_id`; `kind` ← khóa `kind`; `status`, `revision` ← cột; `tags` và `notes` KHÔNG tồn tại (`MediaAsset` không có) |
| `artifacts` (132-142) | `cp_artifact_versions` (`0005_artifact_metadata.sql:1-17`, thêm cột ở `0010_storage_meta_extensions.sql:2`) và `cp_artifact_locations` (`0005:30-50`, `0010:3`) | `PostgresStorageMetaRepository` `src/controlplane/infrastructure/db/storage_meta/__init__.py:46-99` (`insert_version` 62-67, `insert_location` 76-81, `update_location` 90-92) | `artifact_id`, `kind` ← `artifact_id`, `artifact_kind`; `version` ← `artifact_version_id`; `created_at` ← cột; `state` ← trạng thái của vị trí mới nhất (bản chưa có vị trí thì null) |
| `snapshots` (143-153) | `cp_production_snapshots` (`0015_creative.sql:9-18`: `payload`, `created_at`) | `PostgresSnapshotRepository` `src/creative/persistence/repositories.py:62-85`; payload là `encode_record(ProductionSnapshot)` (`src/creative/domain/snapshot.py:119-133`) | `snapshot_id`, `created_at` ← cột; `job_id` ← khóa `video_job_ref` (nullable); `config_revision_ref` ← cột `configuration_bundle_fingerprint`; `model`, `prompt_ref` ← bản phân tích mới nhất của snapshot trong `cp_content_analyses` (`0015:20-28`, khóa `trace.model` và `trace.prompt_ref`; `src/creative/domain/analysis.py:84-114`), null nếu chưa có phân tích |
| `story-angles` (154-164) | `cp_story_angles` (`0015:42-51`) và `cp_story_angle_sets` (`0015:30-40`) | `PostgresAppendOnlyRepository.append` `repositories.py:102-137` (ghi bộ góc và từng góc ở 125-129); `StoryAngle` `src/creative/domain/angles.py:72-86` | `angle_id` ← cột (dạng `set_id:angle_id`); `title` ← khóa `title`; `created_at` ← cột; `snapshot_id` ← bộ góc `set_id` → khóa `analysis_id`, `analysis_revision` → `cp_content_analyses.payload.snapshot_id`; `status` KHÔNG có (góc chỉ có `suitability`) |
| `scripts` (165-175) | `cp_script_versions` (`0015:53-63`: khóa `(workspace_id, record_key, revision)`, `script_version_id` duy nhất) | `PostgresScriptRepository` 167-169; `ScriptVersion` `src/creative/domain/script.py:124-135`; ghi ở `src/creative/application/pipeline.py:452` | `script_id` ← `script_version_id`; `revision`, `created_at` ← cột; `snapshot_id` và `status` KHÔNG có trong payload và không có liên kết ngược (`pipeline.py:422-458` không lưu `snapshot_id` vào script) |
| `sessions` (187-197) | `cp_app_sessions` (`0011_orchestration_extensions.sql:60-70`: `session_ref`, `status`, `recovery_epoch`, `started_at`, `ended_at`) | Chỉ đọc `recovery_epoch` ở `src/controlplane/infrastructure/db/orchestration/grants.py:103`; KHÔNG có hàm ghi trong `src/` | `session_id` ← `session_ref`; `status`, `started_at` ← cột; `finished_at` ← `ended_at`; `job_id` KHÔNG có cột (`BLOCKED_LIST_RESOURCES` dòng 44) |
| `accounts` (209-219) | `cp_external_accounts` (`0009_config_security_extensions.sql:12-30`) | Chỉ đọc `status` ở `src/controlplane/api/wiring/config_security.py:88`; KHÔNG có hàm ghi trong `src/` | `account_ref` ← `external_account_id`; `provider`, `account_label`, `status`, `updated_at` ← cột; không trả `capabilities_json`, `credential_*`, `quota_observation_ref`, `project_ref`, `health` |
| `cost` (220-230) | `cp_cost_records` (`0009:61-81`) | `PostgresCostLedger` `src/controlplane/infrastructure/db/config_security/stores.py:67-79` (`append`, `records`) | `cost_id` ← `record_id`; `job_id` ← `job_ref` (nullable); `provider` ← cột; `recorded_at` ← `occurred_at`; `amount` ← `actual_cost` nếu có, không thì `estimated_cost`; thêm `currency` và `amount_basis` (mục 5.10) |

### 3.4. Registry, test và probe đang ghim số màn hoặc danh sách route

- `screenRegistry.ts`: 18 màn; `backendStatus` của mười màn cần nối ở dòng 97 (articles), 108 (events), 119 (media), 141 (artifacts), 152 (snapshots), 163 (story-angles), 174 (scripts), 196 (sessions), 218 (accounts), 229 (cost); `logs` ở 207. `ui/dist` hiện có `index.html`, `assets/index-DDYJZDF1.js`, `.js.map` và `index-DNWUXu2_.css`; `App.tsx:36-51` chỉ mở màn khi `backendStatus === 'available'`.
- `tests/unit/control_ui/test_h_screen_registry.py`: `AVAILABLE_IDS` dòng 32 (bảy màn) và `PENDING_IDS` 33-35; `REVISION_COLUMN_IDS` 38 (có `media`); `EDITABLE_ALLOWLIST` 39-43 (có `media`); `router_get_paths` 112-118 (gom `ListingResource` từ `route_catalog.py` bằng regex, nên mục mới phải giữ dạng `ListingResource("tên", "/v1/tên", ...)`); `test_every_other_screen_is_pending_module` 148-151 (đúng 11 màn); dòng 222 và 324 (ba màn sửa được `hooks`, `media`, `sources`); 280-284 (phân hoạch); `test_media_stays_pending_module_until_backend_has_media_metadata` 314-318 (đọc chuỗi `media.status_code == 503` trong `test_adapt_prod_app.py`).
- `tests/integration/adapt/prod/test_adapt_prod_app.py`: dòng 272 (`module_services` đúng `{'sources', 'hooks'}`), 303-304 (`/v1/media` trả 503), 249 (`create_app` trần có `module_services == {}`, không đổi), 401 (dist được phục vụ nguyên byte).
- `tests/integration/convergence/test_cp4_wiring.py`: 656-662 ghim `METADATA_RESOURCES` đúng ba tên `sources`, `hooks`, `media`. Vì vậy KHÔNG xóa mục metadata của `media`; PATCH `/v1/media` giữ 503 bằng cách service `media` ném `CapabilityUnavailableError` trong `apply_update`.
- `tests/m2/test_p9_m2_exit_gate.py:27`: `BASELINE_PREFIXES` so hash `ui/dist` với blob git tại `M2_ACCEPTED_SHA`, không so với worktree, nên dựng lại `ui/dist` không làm đỏ test này.
- Probe đóng mốc `docs/delivery-evidence/m3-milestone-close/report.md:275` (bước 40) khẳng định `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost` là `pending_module`. Đây là bản ghi lịch sử, không phải test chạy lại; sau khi các màn chuyển `available` mọi lệnh đóng mốc mới sao chép dòng này sẽ đỏ. Probe tương tự ở `docs/delivery-evidence/m5-milestone-close/command-results.md` (dòng 49, 57, 131, tức bước 39, 47, 121) và nhắc ở `docs/delivery-evidence/m6-milestone-close/report.md:235`. Không sửa bằng chứng lịch sử; gói CP-4B-UI-SCREENS-FIX3 ghi chú và Control không dùng các lệnh này cho lệnh đóng mốc mới. Lệnh tìm đủ vị trí: `rg -n "pending_module|screenRegistry" docs/delivery-evidence` (cấm sửa `docs/milestones/**/evidence/**`).

## 4. Thiết kế chung của service đọc

Mọi service nằm ở `src/controlplane/api/wiring/read_screens/` (slice RS-1 đến RS-12), mỗi tài nguyên một mô-đun, cùng chữ ký với `HookModuleService`:

- `fetch_page(request, workspace_id, query) -> Page` và `fetch_one(request, workspace_id, item_id) -> dict | None`. Service nhận `connection_scope` (hàm không đối số trả context manager của một kết nối; production truyền `manager.borrow_connection`), không tự mở pool, không đọc môi trường.
- Mọi câu SQL có `WHERE workspace_id = %s::uuid` với `workspace_id` do router lấy từ `request.state.identity`; `fetch_one` của id thuộc workspace khác trả `None` (404). Không bao giờ đọc `cp_auth_sessions` (có `token_hash`).
- Phân trang keyset trong SQL: `ORDER BY <sort> <dir>, <id> <dir> LIMIT limit+1`, điều kiện cursor `(<sort>, <id>) < hoặc > (%s::timestamptz, %s)`. Giá trị sắp là chuỗi UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`; cursor giải mã được nhưng không phải thời điểm hợp lệ thì ném `ValueError` (middleware đổi thành 422). Hướng mặc định là `desc` khi request không có `direction` (giống `control.py:273-274`), mới nhất trước. Kết quả qua `build_page`.
- Dòng trả về chỉ gồm cột của registry cộng đúng một khóa sắp xếp nếu chưa nằm trong cột (như `updated_at` của hooks). Ánh xạ từng khóa payload tường minh; cấm `SELECT payload` rồi đẩy nguyên ra phản hồi. Không bao giờ trả: nội dung bài (`normalized_text`), URL gốc, `fingerprint`, `discovery_ids`, `original_locator`, đoạn kịch bản (`segments`), `capabilities_json`, `credential_*`, `stack_trace`, bí mật.
- Cột không có dữ liệu thật: hoặc trả `null` có lý do ghi ở mục 5, hoặc bỏ khỏi `columns` bằng CP-4B-UI-SCREENS-FIX3. Không bịa giá trị, không suy ra từ tên.
- Bộ lọc: mọi phần tử của `allowed_filters` trong catalog phải được service xử lý và có test; giá trị lạ (ví dụ `state` không thuộc enum) trả danh sách rỗng, không bỏ qua im lặng.
- Chỉ đọc: service không có `INSERT`, `UPDATE`, `DELETE`; test kiểm bằng probe văn bản và bằng cách đếm hàng bảng nguồn trước và sau.
- Khối payload thiếu khóa (bản ghi cũ hơn domain hiện tại) thì cột tương ứng là `null`, không ném lỗi 500.

## 5. Thiết kế từng màn

Quy ước: «Sắp» là `allowed_sorts` của catalog và cũng là khóa của dòng trả về (cursor lấy từ khóa này); «Lọc» là `allowed_filters`.

### 5.1. `articles` (module B; R1)

- SQL: `cp_articles a` nối `cp_article_revisions r` với `r.workspace_id = a.workspace_id AND r.article_id = a.article_id AND r.revision = a.revision` (`repositories.py:117-141`: `a.revision` bằng số bản mới nhất). Id `a.article_id`; sắp `updated_at` (từ `a.updated_at`); lọc `source_id` (so với khóa `source_id` của bản mới nhất).
- Dòng: `article_id`, `source_id`, `title`, `published_at`, `fetch_evidence_ref`, `revision`, `updated_at`. `published_at` null khi bài không có ngày; `fetch_evidence_ref` là `raw_snapshot_ref`, null khi chưa lưu bản gốc. Không trả `normalized_text`, `requested_url`, `final_url`, `provenance_chain`.

### 5.2. `events` (module B; R1)

- SQL: `cp_events e`; id `event_id`; sắp `updated_at`; lọc `status`.
- Dòng: `event_id`, `title`, `status`, `source_id`, `fetch_evidence_ref`, `revision`, `updated_at`. Quy tắc GIẢ ĐỊNH-RS-01 (mặc định đơn giản theo D8): bài đại diện là phần tử đầu của `payload.member_refs` (bài đầu tiên liên kết vào sự kiện); `title`, `source_id`, `fetch_evidence_ref` lấy từ bản bài đó (`article_id` và `payload->>'article_revision_id'` trong `cp_article_revisions`); không tìm thấy bài thì ba cột là null.

### 5.3. `media` (module C; R2)

- SQL: `cp_media_assets m`; id `media_asset_id`; sắp `updated_at` hoặc `name` (ánh xạ `name` → `media_asset_id`, giữ nguyên catalog hiện có); lọc `kind` (khóa `kind`) và `status` (cột `status`). CP-4-WIRING-FIX3 thu hẹp lọc hiện tại `{kind, tag, availability}` vì không có dữ liệu cho `tag` và `availability`.
- Dòng: `media_id`, `kind`, `rights_status` (khóa `rights.status`; cột mới thay `tags` và `notes` đã bỏ), `status`, `revision`, `updated_at`. Không trả `fingerprint`, `discovery_ids`, provenance (có `original_locator`).
- `apply_update` của service ném `CapabilityUnavailableError('media')` nên `PATCH /v1/media/{id}` vẫn 503. Registry đặt `media` chỉ đọc (`editableFields` rỗng, `readOnly: true`); sửa tags/notes vào backlog BL-RS-03.

### 5.4. `artifacts` (module I; R2)

- SQL: `cp_artifact_versions v` nối `LEFT JOIN LATERAL` lấy `state` của `cp_artifact_locations l` mới nhất theo `ORDER BY l.updated_at DESC, l.location_id DESC LIMIT 1`; id `artifact_version_id::text`; sắp `created_at`; lọc `kind` (`artifact_kind`) và `state` (trạng thái vị trí mới nhất).
- Dòng: `artifact_id`, `version` (= `artifact_version_id`), `state` (null khi chưa có vị trí), `kind`, `created_at`. Không trả `sha256_hash`, `owner_ref`, `provider_object_ref`, `logical_locator`, `verification_evidence_ref`.
- Lưu ý OI-RS-03: `state` là trạng thái vị trí lưu (`DECLARED` … `DELETED`, `0005:42`), chưa phải «năm trạng thái» media của R2 (bản gốc, đã xử lý, không chắc chắn, lỗi, không khả dụng).

### 5.5. `snapshots` (module D; R3)

- SQL: `cp_production_snapshots s` nối `LEFT JOIN LATERAL` lấy bản mới nhất của `cp_content_analyses` có `payload->>'snapshot_id' = s.snapshot_id` (`ORDER BY revision DESC LIMIT 1`); id `snapshot_id`; sắp `created_at`; lọc `job_id` (so với `payload->>'video_job_ref'`).
- Dòng: `snapshot_id`, `job_id` (null khi snapshot chưa gắn job), `model` (`trace.model`), `prompt_ref` (dạng `ref_id@revision_id` của `trace.prompt_ref`, cùng dạng `pipeline.py:227`), `config_revision_ref` (cột `configuration_bundle_fingerprint`), `created_at`. `model` và `prompt_ref` null khi chưa có phân tích. Không trả `source_refs`, `index_revision_refs`, `recent_variant_exclusions`.

### 5.6. `story-angles` (module D; R3)

- SQL: `cp_story_angles g`; id `angle_id` (dạng `set_id:angle_id`, có dấu hai chấm); sắp `created_at`; không có bộ lọc (`frozenset()`). `snapshot_id` qua `LEFT JOIN cp_story_angle_sets` theo `set_id` (`payload.analysis_id`, `payload.analysis_revision`) rồi `cp_content_analyses` (`record_key`, `revision`) lấy `payload->>'snapshot_id'`; null nếu thiếu một mắt xích.
- Dòng: `angle_id`, `snapshot_id`, `title`, `suitability`, `created_at`. CP-4B-UI-SCREENS-FIX3 thay cột `status` bằng `suitability` vì góc không có trạng thái. Không trả `summary`, `narrative_question`, `evidence_refs`.

### 5.7. `scripts` (module D; R3)

- SQL: `cp_script_versions v`; id `script_version_id`; sắp `created_at`; lọc `language` (`payload->>'language'`).
- Dòng: `script_id`, `language`, `estimated_duration_seconds` (số), `revision`, `created_at`. CP-4B-UI-SCREENS-FIX3 bỏ `snapshot_id` và `status` khỏi `columns` vì không có dữ liệu thật; liên kết script → snapshot vào backlog BL-RS-01. Không trả `segments`, `hook_intent`, `pronunciation_hints`.

### 5.8. `sessions` (module G; phụ trợ RG-08)

- SQL: `cp_app_sessions`; id `session_ref`; sắp `started_at`; lọc `status` (`ACTIVE`, `ENDED`, `ABANDONED`; giá trị lạ trả danh sách rỗng).
- Dòng: `session_id`, `status`, `started_at`, `finished_at` (← `ended_at`, null khi còn chạy). Registry bỏ cột `job_id` vì bảng không có. Không trả `recovery_epoch`. Không bao giờ đọc `cp_auth_sessions`.

### 5.9. `accounts` (module J; phụ trợ OAuth Drive)

- SQL: `cp_external_accounts`; id `external_account_id`; sắp `updated_at`; lọc `provider` và `status`.
- Dòng: `account_ref`, `provider`, `account_label`, `status`, `updated_at`. Không trả `capabilities_json`, `credential_version`, `credential_updated_at`, `credential_expires_at`, `quota_observation_ref`, `project_ref`, `health`. Bảng chưa có hàm ghi trong `src/` nên production có thể trả danh sách rỗng 200 (OI-RS-02).

### 5.10. `cost` (module J; R6, G03)

- SQL: `cp_cost_records`; id `record_id`; sắp `recorded_at` (← `occurred_at`, có chỉ mục `cp_cost_records_window_idx` ở `0009:81`); lọc `provider` và `job_id` (← `job_ref`).
- Dòng: `cost_id`, `job_id` (null nếu chi phí không gắn job), `provider`, `amount`, `currency`, `amount_basis`, `recorded_at`. `amount` là chuỗi số thập phân (không dùng float): `actual_cost` nếu có, không thì `estimated_cost`; `amount_basis` là `actual` hoặc `estimated` để không trộn hai loại. `currency` và `amount_basis` là cột mới do CP-4B-UI-SCREENS-FIX3 thêm vào registry. Không trả `operation_ref`, `batch_ref`, `source`.

### 5.11. `logs` — khảo sát nguồn và kết luận (R5)

Nguồn đã khảo sát:

- Không có bảng nhật ký trong các migration (`BLOCKED_LIST_RESOURCES` dòng 45 và `docs/delivery-evidence/cp-4-queries/report.md` mục 4).
- `cp_operation_stream` (`0003_outbox_and_projections.sql:51-63`, có `event_kind`, `summary`, `resource_type`, `resource_id`, `occurred_at`) là nguồn gần nhất, nhưng `summary` mặc định là chuỗi `projection` (`src/controlplane/infrastructure/db/projections/postgres.py:16` và lời gọi `append(event=event)` ở dòng 73), không có cột mức độ; mức `severity` chỉ tồn tại ở view model `ops_read_models.py:36-99`.
- `cp_outbox_events` (`0003:1-25`) chứa payload nghiệp vụ, không phải nội dung để hiển thị. `cp_technical_details` (`0007_technical_details.sql:12-21`) có `stack_trace`, cấm lộ. `cp_audit_records` (`0009:83-97`) là nhật ký kiểm toán không có job và không có mức độ.

Kết luận: chưa có nguồn đọc thật cho `log_id`, `severity`, `message` nên `logs` GIỮ `pending_module`, không có route `/v1/logs` (vẫn 404) và không slice nào nối nó. Lý do ghi vào backlog BL-RS-02 (cần nơi ghi nhật ký có mức độ; thuộc phân hệ G và gói migration, ngoài phạm vi này). R5 vẫn xem được `batches`, `jobs`, `stage-runs`, `operations`; giới hạn thiếu `logs` nêu ở mục 9.

## 6. Chia slice (chi tiết ở `slices.md`)

Mỗi slice chỉ sở hữu tệp MỚI; mọi slice khai khóa `LOCK-READ-SCREENS` (GIẢ ĐỊNH: Control đăng ký khóa này). Test thật trên PostgreSQL thử (`M2_TEST_PG_DSN`, CSDL tạm tạo và xóa), dữ liệu tạo bằng repository của phân hệ; chỉ `sessions` và `accounts` phải INSERT SQL tối thiểu vì `src/` chưa có hàm ghi.

| Slice | Nội dung | Phân hệ | Phục vụ |
| --- | --- | --- | --- |
| `RS-1` | Khung gói, hàm dùng chung `common.py`, hỗ trợ test `rs_support.py` | — | nền cho mọi slice |
| `RS-2` | `articles` | B | R1 |
| `RS-3` | `events` | B | R1 |
| `RS-4` | `media` (chỉ đọc) | C | R2 |
| `RS-5` | `artifacts` | I | R2 |
| `RS-6` | `snapshots` | D | R3 |
| `RS-7` | `story-angles` | D | R3 |
| `RS-8` | `scripts` | D | R3 |
| `RS-9` | `sessions` | G | phụ trợ (RG-08) |
| `RS-10` | `accounts` | J | phụ trợ (OAuth Drive) |
| `RS-11` | `cost` | J | R6 (G03) |
| `RS-12` | Bộ ghép `compose_read_screens` | — | cho ADAPT-PROD-FIX3 |
| `RS-13` | Kiểm đầu cuối trên ứng dụng production | — | R1, R2, R3, R6 |

## 7. Gói sửa của chủ sở hữu

Các chỗ sau nằm trong tệp đã có chủ, KHÔNG thuộc slice RS nào. Control lập các gói này sau khi kế hoạch được Auditor rủi ro duyệt. Khóa tài nguyên theo các kế hoạch hội tụ: `LOCK-CONVERGENCE` cho cả ba; `CP-4B-UI-SCREENS-FIX3` thêm `LOCK-UI-SHELL`, `LOCK-SRC-CONTROL-UI`, `LOCK-M2-REGRESSION` (`docs/implementation/convergence-ext-ui/plan.md:43`).

### 7.1. CP-4-WIRING-FIX3 — `route_catalog.py`

- Tệp: `src/controlplane/application/control_api/route_catalog.py`; test mới `tests/integration/convergence/test_cp4_wiring_fix3.py`.
- Thay đổi chính xác: (1) sau mục `hooks` (dòng 41-49) thêm chín `ListingResource` theo bảng dưới, giữ nguyên dạng literal `ListingResource("tên", "/v1/tên", (sắp), frozenset({lọc}), 50, 100, True)` để regex của `test_h_screen_registry.py:98` còn bắt được; (2) mục `media` (50-58): đổi lọc từ `frozenset({"kind", "tag", "availability"})` thành `frozenset({"kind", "status"})`, giữ sắp và chi tiết; (3) KHÔNG đổi `METADATA_RESOURCES` (`test_cp4_wiring.py:656-662`); (4) cập nhật docstring dòng 1-6; (5) không sửa `main.py`, `control.py`, `control_api_queries.py`.

| Tài nguyên | Sắp | Lọc |
| --- | --- | --- |
| `articles` | `updated_at` | `source_id` |
| `events` | `updated_at` | `status` |
| `media` | `updated_at`, `name` | `kind`, `status` |
| `artifacts` | `created_at` | `kind`, `state` |
| `snapshots` | `created_at` | `job_id` |
| `story-angles` | `created_at` | (rỗng) |
| `scripts` | `created_at` | `language` |
| `sessions` | `started_at` | `status` |
| `accounts` | `updated_at` | `provider`, `status` |
| `cost` | `recorded_at` | `provider`, `job_id` |

- Lệnh kiểm của CP-4-WIRING-FIX3: `git diff --check`; `python -m pytest tests/integration/convergence/test_cp4_wiring.py tests/integration/convergence/test_cp4_wiring_fix3.py tests/unit/control_ui/test_h_screen_registry.py -q`. Test mới dùng service giả như `make_app` (`test_cp4_wiring.py:169-176`): mười tài nguyên có service thì list và detail trả 200 (detail không có thì 404), không có service thì 503 `CAPABILITY_UNAVAILABLE`.
- Phụ thuộc: `RS-12` (khóa tên tài nguyên trùng khóa của bộ ghép). Sau gói này mà chưa có ADAPT-PROD-FIX3, mười route trả 503 thay vì 404; đã rà `tests/` không có test nào ghim 404 của các route này.
- Test đang ghim cần đổi: không có (không test nào đọc số lượng `LISTING_RESOURCES`; `test_cp4_wiring.py:658` chỉ ghim `METADATA_RESOURCES`).

### 7.2. ADAPT-PROD-FIX3 — `production.py` gắn `module_services`

- Tệp: `src/controlplane/api/wiring/production.py`; test `tests/integration/adapt/prod/test_adapt_prod_app.py`.
- Thay đổi chính xác: (1) thêm `from controlplane.api.wiring.read_screens.compose import compose_read_screens`; (2) ngay sau dòng 394 (`api_app.state.module_services['hooks'] = compose_hooks_module(manager)`) thêm `api_app.state.module_services.update(compose_read_screens(manager))`; (3) sửa docstring dòng 5: bỏ câu «media chưa gắn … vẫn trả 503», nêu mười service đọc; (4) không sửa `_build_services`, `SourceModuleService`, `HookModuleService`, `__all__`.
- Test đổi trong `test_adapt_prod_app.py`: dòng 272 thành tập `{'sources', 'hooks'}` hợp mười tên; dòng 303-304 `/v1/media?limit=1` trả 200 với `{'items': [], 'next_cursor': None}`; thêm `PATCH /v1/media/x` trả 503 `CAPABILITY_UNAVAILABLE` và chín tài nguyên còn lại trả 200 rỗng; giữ dòng 249 và 401.
- Lệnh kiểm: `git diff --check`; `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/prod/test_adapt_prod_sources_module.py tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q` (cần `M2_TEST_PG_DSN`).
- Phụ thuộc: `RS-12` và `CP-4-WIRING-FIX3`. Test ghim: `test_h_screen_registry.py:314-318` đọc chuỗi `media.status_code == 503` trong tệp này, nên bước 1 của CP-4B-UI-SCREENS-FIX3 phải gộp TRƯỚC gói này (mục 8).

### 7.3. CP-4B-UI-SCREENS-FIX3 — registry, test H và `ui/dist`

Chia hai bước để không có thời điểm nào test đã nghiệm thu bị đỏ.

**Bước 1 (test, gộp trước ADAPT-PROD-FIX3).** Tệp `tests/unit/control_ui/test_h_screen_registry.py`: thay `test_media_stays_pending_module_until_backend_has_media_metadata` (314-318) bằng test chỉ khẳng định `BY_ID['media']['backendStatus'] == 'pending_module'` và KHÔNG đọc `test_adapt_prod_app.py`. Lệnh kiểm: `python -m pytest tests/unit/control_ui -q`. Không phụ thuộc slice RS.

**Bước 2 (cuối, sau khi RS-13 PASS).**

- Tệp: `src/controlplane/ui/src/features/screens/screenRegistry.ts`, `tests/unit/control_ui/test_h_screen_registry.py`, dựng lại `src/controlplane/ui/dist/**`. Chạy `npm run build` (runtime Node do Control cấp sau `USER-CKPT-D9-D10`, `convergence-ext-ui/plan.md:29`); Control chạy Playwright `npm run test:e2e`.
- `screenRegistry.ts`: đổi `backendStatus` sang `'available'` cho mười màn (dòng 97, 108, 119, 141, 152, 163, 174, 196, 218, 229); `logs` (207) GIỮ `'pending_module'`. Đổi cột: `media` (116-118) thành `columns: ['media_id', 'kind', 'rights_status', 'status', 'revision']`, `editableFields: []`, `readOnly: true`; `story-angles` (160) thành `['angle_id', 'snapshot_id', 'title', 'suitability', 'created_at']`; `scripts` (171) thành `['script_id', 'language', 'estimated_duration_seconds', 'revision', 'created_at']`; `sessions` (193) thành `['session_id', 'status', 'started_at', 'finished_at']`; `cost` (226) thành `['cost_id', 'job_id', 'provider', 'amount', 'currency', 'amount_basis', 'recorded_at']`. Các màn còn lại giữ nguyên cột.
- `test_h_screen_registry.py`: dòng 32-35 thành `AVAILABLE_IDS` mười bảy màn và `PENDING_IDS = ('logs',)`; 38 và 39-43 bỏ `media`; 148-151 đổi thành đúng 1 màn `pending_module` (`logs`); 222 và 324 thành `['hooks', 'sources']`; 280-284 theo hằng; thay test 314-318 bằng test `media` là `available`, `readOnly` và có tệp `tests/integration/read_screens/test_rs_13_prod_e2e.py`; thêm test: mỗi màn mới `available` có tệp `tests/integration/read_screens/test_rs_<n>_*.py` tương ứng (mẫu ở dòng 287-311) và `/v1/logs` không có trong `router_get_paths()`.
- Ghi chú probe lịch sử (mục 3.4): thêm ghi chú vào báo cáo của gói, không sửa bằng chứng cũ. Lệnh tìm: `rg -n "pending_module|screenRegistry" docs/delivery-evidence`.
- Lệnh kiểm: `git diff --check`; `python -m pytest tests/unit/control_ui -q`; `npm run build`; probe `dist` có `index.html` và chuỗi `/v1/articles`.
- Phụ thuộc: `RS-13` PASS (route và service đã gộp và có test) cùng `CP-4-WIRING-FIX3`, `ADAPT-PROD-FIX3`. `backendStatus` chỉ chuyển `available` ở bước này.

## 8. Thứ tự và đồ thị phụ thuộc

1. `RS-1`.
2. `RS-2` đến `RS-11` (độc lập, không chung tệp; chạy tuần tự trong lane hoặc song song).
3. `RS-12` (bộ ghép; phụ thuộc `RS-2` đến `RS-11`).
4. CP-4B-UI-SCREENS-FIX3 bước 1 (chỉ nới test; làm được bất cứ lúc nào trước bước 6).
5. CP-4-WIRING-FIX3 (route trả 503 khi chưa gắn service).
6. ADAPT-PROD-FIX3 (gắn service; `/v1/media` chuyển từ 503 sang 200).
7. `RS-13` (kiểm đầu cuối trên `build_production_app`).
8. CP-4B-UI-SCREENS-FIX3 bước 2 (chuyển `available`, dựng lại `ui/dist`).
9. Chạy lại toàn bộ test ghim ở mục 3.4 trước khi đóng.

Lý do thứ tự: registry chỉ đổi sau khi route và service đã gộp và có test (bước 8 sau bước 7); test đọc chuỗi 503 được nới (bước 4) trước khi hành vi đổi (bước 6); route thêm (bước 5) không làm đỏ test vì chưa có test ghim 404.

## 9. Màn hình phục vụ bước nghiệm thu R của CP7

Theo `docs/implementation/cp7/plan.md` mục 5:

- R1 Content Alpha: `articles` (RS-2) và `events` (RS-3) — truy ngược nguồn, fetch evidence, revision; cùng `sources`, `stage-runs` đã có.
- R2 Media Alpha: `media` (RS-4, chỉ đọc) và `artifacts` (RS-5); cùng `hooks` đã có. Giới hạn: OI-RS-03 (`state` là trạng thái vị trí lưu).
- R3 Creative Alpha: `snapshots` (RS-6), `story-angles` (RS-7), `scripts` (RS-8). Giới hạn: script chưa liên kết ngược tới snapshot (BL-RS-01); snapshot hiển thị model, prompt, config qua bản phân tích.
- R5 Unattended Beta: `batches`, `jobs` đã có; `logs` GIỮ `pending_module` (mục 5.11), user dùng `stage-runs` và `operations` thay thế và ghi giới hạn này ở R5.
- R6 Operational Baseline: `cost` (RS-11, G03); cùng `jobs`, `batches`.
- Phụ trợ, không thuộc bước R nào ở mục 5 của CP7: `sessions` (RS-9, RG-08) và `accounts` (RS-10, OAuth Drive).

Mỗi màn đã nối phải đạt: `GET /v1/<tài nguyên>` trả 200 với dữ liệu thật tạo trong test; detail trả 200 hoặc 404 đúng; không trả workspace khác; không lộ trường bí mật hay payload thô ngoài cột registry; `backendStatus` chuyển `available` chỉ khi route và test đã có.

## 10. Backlog, mục mở và rủi ro (mặc định theo D8; không ghi là đã duyệt)

| Mã | Nội dung | Xử lý mặc định |
| --- | --- | --- |
| BL-RS-01 | Liên kết script → snapshot (và trạng thái script) chưa được lưu; cần thay đổi domain D | Cột bị bỏ khỏi registry; làm bằng slice riêng của phân hệ D |
| BL-RS-02 | `logs` chưa có nguồn có mức độ và thông điệp thật | Giữ `pending_module`; cần nơi ghi nhật ký (phân hệ G, gói migration) |
| BL-RS-03 | Sửa tags/notes của `media` và PATCH `/v1/media` | PATCH vẫn 503; slice riêng sau khi `MediaAsset` có trường này |
| BL-RS-04 | `cp_app_sessions` và `cp_external_accounts` chưa có hàm ghi trong `src/` | Màn trả 200 rỗng ở production tới khi có nơi ghi |
| BL-RS-05 | Tổng hợp chi phí theo job hoặc ngày | Ngoài phạm vi; `cost` chỉ liệt kê bản ghi |
| OI-RS-01 | Quy tắc bài đại diện của `events` (`member_refs[0]`) là GIẢ ĐỊNH | Mặc định đơn giản; ghi rõ trong test |
| OI-RS-02 | `sessions` và `accounts` chuyển `available` dù production có thể rỗng | Mặc định chuyển (UI hiển thị rỗng); Auditor rủi ro có thể yêu cầu giữ `pending_module` |
| OI-RS-03 | `artifacts.state` là trạng thái vị trí lưu, chưa phải năm trạng thái R2 | Ghi ở R2; không bịa ánh xạ |
| OI-RS-04 | Không thêm chỉ mục mới nên truy vấn dựa vào khóa chính và chỉ mục sẵn có | Chấp nhận ở quy mô v1 (100 video mỗi đêm); không thêm migration |
| OI-RS-05 | Thiếu `M2_TEST_PG_DSN` | `BLOCKED_EXTERNAL`, không tuyên bố PASS |

## 11. Đối chiếu counterexample

- Service trả `payload` thô hoặc lộ trường cấm: bị chặn bằng ánh xạ khóa tường minh (mục 4), canary trong test và probe văn bản của từng slice.
- Route lộ dữ liệu workspace khác: mọi SQL có điều kiện `workspace_id`; test cô lập hai workspace ở từng slice và ở RS-13.
- Registry chuyển `available` khi route chưa có: chỉ làm ở bước 8 sau RS-13 (mục 8).
- Test đã nghiệm thu bị đỏ giữa chừng: các test ghim ở mục 3.4 được đổi theo đúng thứ tự mục 8.
- Migration hoặc đổi schema: không có; `logs` giữ `pending_module` thay vì thêm bảng.
- Bịa dữ liệu cho cột không có nguồn: cột bị bỏ khỏi `columns` hoặc trả `null` có lý do (mục 5).
- Đổi hợp đồng bảy màn đã `available`: không sửa `control_api_queries.py`, `control.py`, `SourceModuleService`, `HookModuleService`.
- `PATCH /v1/media` thành 500 vì thiếu `apply_update`: service `media` ném `CapabilityUnavailableError` nên giữ 503.
- Slice sửa tệp đã có chủ: ownedPaths của mọi slice chỉ gồm tệp mới; chỗ cần sửa nằm ở mục 7.

## 12. Giới hạn

Kế hoạch dựa trên mã tại HEAD `2f7f8d9`. Chưa chạy test hay dựng ứng dụng trong task này; số liệu hiện trạng ở mục 2 là phép đo của Control ngày 25/10/2026. Mọi kết luận về kiểm thật nằm ở RS-13 và CP7.
