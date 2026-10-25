# Slice nối route chỉ đọc cho các màn hình Dashboard — IMPL-PLAN-READ-SCREENS

Nguồn: `docs/implementation/read-screens/plan.md`. Mười ba slice `RS-1` đến `RS-13`, tất cả là `work_package_slice`. Mỗi slice chỉ sở hữu tệp MỚI: service đọc ở `src/controlplane/infrastructure/read_screens/**`, test ở `tests/integration/read_screens/**`, bằng chứng ở `docs/delivery-evidence/rs-*/**`. Chỗ phải sửa trong tệp đã có chủ nằm ở mục «Gói sửa của chủ sở hữu» của plan.md (CP-4-WIRING-FIX3, ADAPT-PROD-FIX3, CP-4B-UI-SCREENS-FIX3), không nằm ở đây. `src/controlplane/api/wiring/**` là COMPOSITION-ROOT nên không slice nào đặt tệp ở đó. Chạy tuần tự trong một lane; mọi slice khai khóa `LOCK-READ-SCREENS` (GIẢ ĐỊNH: Control đăng ký khóa này).

## Quy tắc chung cho mọi slice

- Chỉ tạo tệp trong `ownedPaths`; không sửa tệp đã có (kể cả mọi tệp dưới `src/controlplane/api/wiring/**` là COMPOSITION-ROOT, `production.py`, `route_catalog.py`, `screenRegistry.ts`, migration, `tests/m1`, `tests/m2`, `tests/integration/adapt/**`, `tests/integration/convergence/**`, `tests/unit/control_ui/**`, `ui/dist`, `docs/milestones/**/evidence/**`). Không thêm thư viện, không migration, không đổi domain hay repository của phân hệ, không đụng `tools/launcher/**` và `src/controlplane/infrastructure/production_ports/**`.
- Import theo gốc `src/` (không tiền tố `src.`). Không `os.environ` trong mã service; không `mock` hay `fake` trong mã service.
- Test chạy trên PostgreSQL thử: biến `M2_TEST_PG_DSN`, CSDL tạm tạo và xóa theo mẫu `tests/integration/adapt/prod/test_adapt_prod_app.py:114-135`; `docs/parallel-delivery/ownership-and-locks.yaml:221-222` (`MigrationRunner.migrate_up`, seed `cp_workspaces`). Thiếu DSN thì `pytest.fail('BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN')`, không skip. Dữ liệu tạo bằng repository hoặc dịch vụ ứng dụng của phân hệ; chỉ RS-9 và RS-10 được INSERT SQL tối thiểu vì `src/` chưa có hàm ghi (ghi rõ trong test).
- Mỗi test của slice kiểm: (a) `fetch_page` trả dữ liệu thật vừa tạo đúng tập khóa của dòng; (b) phân trang cursor từ hai trang trở lên, không trùng không sót, cả `asc` và `desc`, hướng mặc định `desc`; (c) `fetch_one` có, không có, và id của workspace khác trả `None`; (d) cô lập workspace; (e) canary trong payload hoặc cột cấm không xuất hiện trong `json.dumps(dòng)`; (f) từng bộ lọc của catalog, giá trị lạ trả rỗng; (g) chỉ đọc: số hàng bảng nguồn không đổi; (h) cursor không phải thời điểm hợp lệ ném `ValueError`.
- Tên test duy nhất `test_rs_<số>_<tên>.py`; `tests/integration/read_screens/` không có `__init__.py` và không có `conftest.py`; mô-đun hỗ trợ duy nhất là `rs_support.py` (RS-1).
- Test-first: thấy RED do assertion đúng oracle (thiếu hành vi), không phải lỗi import hay thiếu binary, rồi mới implement tới GREEN; ghi vào báo cáo.
- Bằng chứng ở `docs/delivery-evidence/rs-<số>/report.md`: lệnh đã chạy, mã thoát, số test pass; không ghi bí mật. Mọi `testCommands` chạy bằng interpreter khóa của lane.

### RS-1: Khung gói read_screens, hàm dùng chung và hỗ trợ test PostgreSQL

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/__init__.py`
  - `src/controlplane/infrastructure/read_screens/common.py`
  - `tests/integration/read_screens/rs_support.py`
  - `tests/integration/read_screens/test_rs_1_common.py`
  - `docs/delivery-evidence/rs-1/report.md`
- dependsOn: `IMPL-PLAN-READ-SCREENS`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/application/projections/list_query.py:35-157`; `src/controlplane/api/wiring/production.py:264-295`; `src/controlplane/api/routes/control.py:271-280`; `src/controlplane/infrastructure/db/uow.py:93-97`; `tests/integration/adapt/prod/test_adapt_prod_app.py:114-135`
- acceptance:
  - requirement: (1) `__init__.py` chỉ có docstring. (2) `common.py`: `ConnectionScope = Callable[[], ContextManager[Any]]`; `utc_text(moment)` trả `YYYY-MM-DDTHH:MM:SS.ffffffZ` UTC (như `production.py:104`); `parse_cursor_time(value)` trả `datetime` hoặc ném `ValueError` khi không phải thời điểm RFC 3339; `effective_direction(request, query)` trả `desc` khi `request.query_params` không có `direction`, ngược lại `query.direction`; `keyset(query, *, sort_sql, id_sql)` trả `(where_sql, params, order_sql)` với điều kiện `(sort, id)` so với `(%s::timestamptz, %s)` theo hướng và `ORDER BY` cùng hướng (`id_sql` ép `::text`); `page_of(rows, query, sort_field, id_field)` bọc `build_page`; `pick(payload, *keys)` đọc khóa lồng nhau và trả `None` nếu thiếu. (3) `rs_support.py`: `temp_database()` là context manager tạo CSDL tạm từ `M2_TEST_PG_DSN`, chạy `MigrationRunner.migrate_up`, seed hai workspace, trả `(manager, workspace_id, other_workspace_id)`, xóa CSDL khi thoát kể cả khi test lỗi; `FakeRequest(workspace_id, params)` có `state.identity` và `query_params`. (4) `common.py` không import `production`; `os.environ` chỉ xuất hiện trong `rs_support.py` để đọc `M2_TEST_PG_DSN`.
    instrument: test thuần cho `utc_text`, `parse_cursor_time` (chuỗi rác và rỗng thì `ValueError`), `effective_direction`, `keyset` (asc, desc, có và không có cursor), `pick`; test PostgreSQL xác nhận `temp_database` migrate được, seed đúng hai workspace và xóa CSDL.
    counterexample: cursor không phải thời điểm làm SQL lỗi 500; hướng mặc định `asc`; hàm dùng chung đọc `os.environ`; CSDL tạm không bị xóa khi test lỗi.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_1_common.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/common.py').read_text(encoding='utf-8').lower(); assert 'os.environ' not in t and 'from src.' not in t and 'production' not in t and 'insert into' not in t, 'RS-1'"`

### RS-2: Service articles (module B)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/articles.py`
  - `tests/integration/read_screens/test_rs_2_articles.py`
  - `docs/delivery-evidence/rs-2/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0013_ingestion.sql:9-31`; `src/ingestion/persistence/repositories.py:41-153`; `src/ingestion/domain/article.py:12-37`; `src/controlplane/api/wiring/production.py:264-295`
- acceptance:
  - requirement: (1) `ArticleModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL nối `cp_articles` với `cp_article_revisions` theo `r.revision = a.revision`; id `article_id`; sắp `updated_at`; lọc `source_id`. (3) Dòng có đúng khóa `article_id`, `source_id`, `title`, `published_at`, `fetch_evidence_ref`, `revision`, `updated_at`; `fetch_evidence_ref` là `raw_snapshot_ref` (null khi thiếu); `published_at` null khi bài không có ngày. (4) Không trả `normalized_text`, `requested_url`, `final_url`, `provenance_chain`.
    instrument: tạo bài bằng `PostgresArticleRepository(connection_getter, workspace_id).save(Article(...))` với ít nhất ba bài, một bài hai revision (dòng hiển thị title và revision mới nhất), một bài không có `published_at` và `raw_snapshot_ref`, một bài của workspace khác; canary trong `normalized_text` và `final_url` không xuất hiện trong dòng.
    counterexample: dòng trả revision cũ; `SELECT payload` đẩy nguyên ra; bài workspace khác lọt vào danh sách hay detail; N+1 truy vấn theo số bài.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_2_articles.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/articles.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'normalized_text' not in t, 'RS-2'"`

### RS-3: Service events (module B)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/events.py`
  - `tests/integration/read_screens/test_rs_3_events.py`
  - `docs/delivery-evidence/rs-3/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0013_ingestion.sql:55-63`; `src/ingestion/persistence/repositories.py:198-235`; `src/ingestion/application/resolve_event_link.py:111-121`
- acceptance:
  - requirement: (1) `EventModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_events`; id `event_id`; sắp `updated_at`; lọc `status`. (3) Dòng có đúng khóa `event_id`, `title`, `status`, `source_id`, `fetch_evidence_ref`, `revision`, `updated_at`; ba cột `title`, `source_id`, `fetch_evidence_ref` lấy từ bản bài của `member_refs[0]` (GIẢ ĐỊNH-RS-01), null khi không tìm thấy bài. (4) Không trả `member_refs`, `effective_time_range`, `topic` thô.
    instrument: tạo bài bằng `PostgresArticleRepository.save` và sự kiện bằng `PostgresEventRepository.save(event)` theo dạng dict ở `resolve_event_link.py:111-121`; sự kiện có bài đại diện, sự kiện có `member_refs` trỏ tới bài không tồn tại (ba cột null), sự kiện hai thành viên (dùng thành viên đầu), sự kiện của workspace khác; lọc `status`.
    counterexample: lấy thành viên cuối thay vì đầu; ném lỗi 500 khi thiếu bài; lộ `member_refs`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_3_events.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/events.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'normalized_text' not in t, 'RS-3'"`

### RS-4: Service media chỉ đọc (module C)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/media.py`
  - `tests/integration/read_screens/test_rs_4_media.py`
  - `docs/delivery-evidence/rs-4/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0014_catalog.sql:9-24`; `src/catalog/persistence/assets.py:40-93`; `src/catalog/persistence/mapping.py:32-41`; `src/controlplane/api/main.py:85-95`; `src/controlplane/application/control_api/errors.py` (`CapabilityUnavailableError`)
- acceptance:
  - requirement: (1) `MediaModuleService(connection_scope)` có `fetch_page`, `fetch_one` và `apply_update(*, request, item_id, expected_revision, changes, idempotency_key=None)` luôn ném `CapabilityUnavailableError('media')`. (2) SQL trên `cp_media_assets`; id `media_asset_id`; sắp `updated_at` hoặc `name` (`name` ánh xạ `media_asset_id`); lọc `kind` (khóa `kind`) và `status` (cột). (3) Dòng có đúng khóa `media_id`, `kind`, `rights_status`, `status`, `revision`, `updated_at`; `rights_status` ← `rights.status`. (4) Không trả `fingerprint`, `discovery_ids`, provenance và `original_locator`.
    instrument: tạo tài sản bằng `PostgresMediaAssetRepository(connection, workspace_id).save(MediaAsset(...))` với tài sản đã có fingerprint, tài sản chưa có (`status` DISCOVERED) và tài sản của workspace khác; provenance có `original_locator` canary không xuất hiện trong dòng; `apply_update` ném đúng loại lỗi; sắp theo `name` và `updated_at` cả hai hướng.
    counterexample: `apply_update` thiếu làm PATCH thành 500; trả fingerprint hay `original_locator`; lọc `tag` vẫn được chấp nhận ngầm.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_4_media.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/media.py').read_text(encoding='utf-8').lower(); assert 'capabilityunavailableerror' in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'original_locator' not in t, 'RS-4'"`

### RS-5: Service artifacts (module I)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/artifacts.py`
  - `tests/integration/read_screens/test_rs_5_artifacts.py`
  - `docs/delivery-evidence/rs-5/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0005_artifact_metadata.sql:1-50`; `src/controlplane/infrastructure/db/migrations/0010_storage_meta_extensions.sql:2-3`; `src/controlplane/infrastructure/db/storage_meta/__init__.py:46-99`
- acceptance:
  - requirement: (1) `ArtifactModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_artifact_versions v` với `LEFT JOIN LATERAL` lấy `state` của vị trí mới nhất (`ORDER BY l.updated_at DESC, l.location_id DESC LIMIT 1`); id `artifact_version_id::text`; sắp `created_at`; lọc `kind` và `state`. (3) Dòng có đúng khóa `artifact_id`, `version`, `state`, `kind`, `created_at`; `version` là `artifact_version_id`; `state` null khi chưa có vị trí. (4) Không trả `sha256_hash`, `owner_ref`, `provider_object_ref`, `logical_locator`, `verification_evidence_ref`.
    instrument: tạo bằng `PostgresStorageMetaRepository(connection).insert_version`, `insert_location` và `update_location`; bản có hai vị trí (hiển thị trạng thái vị trí cập nhật gần nhất), bản không có vị trí (`state` null), bản của workspace khác; lọc `state=VERIFIED` và `kind`; canary trong `logical_locator` và `provider_object_ref` không xuất hiện.
    counterexample: một bản hiện nhiều dòng vì nối thường thay vì LATERAL; lộ `logical_locator`; lọc `state` so với vị trí cũ.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_5_artifacts.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/artifacts.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'provider_object_ref' not in t and 'logical_locator' not in t, 'RS-5'"`

### RS-6: Service snapshots (module D)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/snapshots.py`
  - `tests/integration/read_screens/test_rs_6_snapshots.py`
  - `docs/delivery-evidence/rs-6/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0015_creative.sql:9-28`; `src/creative/persistence/repositories.py:62-85`; `src/creative/domain/snapshot.py:119-147`; `src/creative/domain/analysis.py:84-114`; `src/creative/application/pipeline.py:197-205`
- acceptance:
  - requirement: (1) `SnapshotModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_production_snapshots s` với `LEFT JOIN LATERAL` lấy bản mới nhất của `cp_content_analyses` có `payload->>'snapshot_id' = s.snapshot_id`; id `snapshot_id`; sắp `created_at`; lọc `job_id` (so với `payload->>'video_job_ref'`). (3) Dòng có đúng khóa `snapshot_id`, `job_id`, `model`, `prompt_ref`, `config_revision_ref`, `created_at`; `prompt_ref` dạng `ref_id@revision_id`; `config_revision_ref` là `configuration_bundle_fingerprint`; `model` và `prompt_ref` null khi chưa có phân tích. (4) Không trả `source_refs`, `index_revision_refs`, `recent_variant_exclusions`.
    instrument: tạo snapshot bằng `PostgresSnapshotRepository(connection_source, workspace_id).add(...)` (dựng bằng hàm của domain ở `snapshot.py:198`) và phân tích bằng `PostgresAnalysisRepository.append` (dựng bằng hàm của domain ở `analysis.py:209`); snapshot có phân tích hai revision (dùng revision mới), snapshot chưa có phân tích (hai cột null), snapshot không gắn job (`job_id` null), snapshot của workspace khác; lọc `job_id`.
    counterexample: hiển thị model của revision cũ; ném lỗi khi thiếu phân tích; lộ `source_refs`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_6_snapshots.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/snapshots.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'source_refs' not in t, 'RS-6'"`

### RS-7: Service story-angles (module D)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/story_angles.py`
  - `tests/integration/read_screens/test_rs_7_story_angles.py`
  - `docs/delivery-evidence/rs-7/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0015_creative.sql:20-51`; `src/creative/persistence/repositories.py:102-137,162-164`; `src/creative/domain/angles.py:72-86,147-172`
- acceptance:
  - requirement: (1) `StoryAngleModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_story_angles g`; id `angle_id` (dạng `set_id:angle_id`); sắp `created_at`; không có bộ lọc; `snapshot_id` qua `cp_story_angle_sets` (`payload.analysis_id`, `payload.analysis_revision`) rồi `cp_content_analyses` lấy `payload->>'snapshot_id'`, null khi thiếu mắt xích. (3) Dòng có đúng khóa `angle_id`, `snapshot_id`, `title`, `suitability`, `created_at`. (4) Không trả `summary`, `narrative_question`, `evidence_refs`.
    instrument: tạo bộ góc bằng `PostgresAngleSetRepository.append(set_id, 1, bộ góc dựng bằng build_story_angle_set)` kèm phân tích qua `PostgresAnalysisRepository.append`; bộ có hai góc, bộ có phân tích tương ứng và bộ không có, bộ của workspace khác; detail theo id có dấu hai chấm; canary trong `summary` không xuất hiện.
    counterexample: id cắt mất phần `set_id`; `snapshot_id` bịa khi thiếu phân tích; lộ `evidence_refs`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_7_story_angles.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/story_angles.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'evidence_refs' not in t, 'RS-7'"`

### RS-8: Service scripts (module D)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/scripts.py`
  - `tests/integration/read_screens/test_rs_8_scripts.py`
  - `docs/delivery-evidence/rs-8/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0015_creative.sql:53-63`; `src/creative/persistence/repositories.py:102-137,167-169`; `src/creative/domain/script.py:124-135`; `src/creative/application/pipeline.py:422-458`
- acceptance:
  - requirement: (1) `ScriptModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_script_versions`; id `script_version_id`; sắp `created_at`; lọc `language` (`payload->>'language'`). (3) Dòng có đúng khóa `script_id`, `language`, `estimated_duration_seconds`, `revision`, `created_at`; `estimated_duration_seconds` là số. (4) Không trả `segments`, `hook_intent`, `thumbnail_transition`, `pronunciation_hints` (văn bản kịch bản); không có `snapshot_id` hay `status` vì không có dữ liệu thật (BL-RS-01).
    instrument: tạo bằng `PostgresScriptRepository.append(script_version_id, 1, ScriptVersion)` (dựng bằng constructor của domain `script.py:124-135`); ba kịch bản hai ngôn ngữ, một của workspace khác; lọc `language`; canary trong văn bản đoạn kể không xuất hiện trong `json.dumps(dòng)`.
    counterexample: lộ lời kể; trả `snapshot_id` bịa; sắp theo `record_key` thay vì `created_at`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_8_scripts.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/scripts.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'segments' not in t and 'snapshot_id' not in t, 'RS-8'"`

### RS-9: Service sessions (module G)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/sessions.py`
  - `tests/integration/read_screens/test_rs_9_sessions.py`
  - `docs/delivery-evidence/rs-9/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0011_orchestration_extensions.sql:60-70`; `src/controlplane/infrastructure/db/orchestration/grants.py:103`; `src/controlplane/infrastructure/db/control_api_queries.py:44`
- acceptance:
  - requirement: (1) `SessionModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_app_sessions`; id `session_ref`; sắp `started_at`; lọc `status` (`ACTIVE`, `ENDED`, `ABANDONED`; giá trị lạ trả danh sách rỗng). (3) Dòng có đúng khóa `session_id`, `status`, `started_at`, `finished_at` (← `ended_at`, null khi còn chạy). (4) Không trả `recovery_epoch`; mã không tham chiếu `cp_auth_sessions` hay `token_hash`.
    instrument: `src/` chưa có hàm ghi nên test INSERT SQL tối thiểu vào `cp_app_sessions` (ghi rõ trong test); ba phiên đủ ba trạng thái, một phiên của workspace khác; canary trong `recovery_epoch` không xuất hiện; hàng của `cp_auth_sessions` không bao giờ được đọc.
    counterexample: trả `recovery_epoch`; đọc `cp_auth_sessions`; `finished_at` là chuỗi rỗng khi chưa kết thúc.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_9_sessions.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/sessions.py').read_text(encoding='utf-8').lower(); assert 'cp_auth_sessions' not in t and 'token_hash' not in t and 'recovery_epoch' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-9'"`

### RS-10: Service accounts (module J)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/accounts.py`
  - `tests/integration/read_screens/test_rs_10_accounts.py`
  - `docs/delivery-evidence/rs-10/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0009_config_security_extensions.sql:12-30`; `src/controlplane/api/wiring/config_security.py:88`
- acceptance:
  - requirement: (1) `AccountModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_external_accounts`; id `external_account_id`; sắp `updated_at`; lọc `provider` và `status`. (3) Dòng có đúng khóa `account_ref`, `provider`, `account_label`, `status`, `updated_at`. (4) Không trả `capabilities_json`, `credential_version`, `credential_updated_at`, `credential_expires_at`, `quota_observation_ref`, `project_ref`, `health`.
    instrument: `src/` chưa có hàm ghi nên test INSERT SQL tối thiểu vào `cp_external_accounts` (ghi rõ trong test); ba tài khoản hai nhà cung cấp, đủ trạng thái, một tài khoản của workspace khác; canary đặt vào `capabilities_json`, `project_ref` và `health` không xuất hiện trong dòng; lọc `provider` và `status`.
    counterexample: trả cột `credential_*`; lọc `status` không theo enum bị bỏ qua; tài khoản workspace khác lọt vào.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_10_accounts.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/accounts.py').read_text(encoding='utf-8').lower(); assert 'capabilities_json' not in t and 'credential_' not in t and 'project_ref' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-10'"`

### RS-11: Service cost (module J)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/cost.py`
  - `tests/integration/read_screens/test_rs_11_cost.py`
  - `docs/delivery-evidence/rs-11/report.md`
- dependsOn: `RS-1`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/infrastructure/db/migrations/0009_config_security_extensions.sql:61-81`; `src/controlplane/infrastructure/db/config_security/stores.py:63-79`
- acceptance:
  - requirement: (1) `CostModuleService(connection_scope)` có `fetch_page` và `fetch_one`. (2) SQL trên `cp_cost_records`; id `record_id`; sắp `recorded_at` (← `occurred_at`); lọc `provider` và `job_id` (← `job_ref`). (3) Dòng có đúng khóa `cost_id`, `job_id`, `provider`, `amount`, `currency`, `amount_basis`, `recorded_at`; `amount` là chuỗi số thập phân (không float), bằng `actual_cost` nếu có, không thì `estimated_cost`; `amount_basis` là `actual` hoặc `estimated`; `job_id` null khi không gắn job. (4) Không trả `operation_ref`, `batch_ref`, `source`.
    instrument: tạo bằng `PostgresCostLedger(connection).append(workspace_id, IncrementalCostRecord(...))`; bản ghi có `actual_cost`, bản ghi chỉ có `estimated_cost`, bản ghi không gắn job, số thập phân dài (ví dụ 0.000123) giữ nguyên chữ số, bản ghi của workspace khác; lọc `provider` và `job_id`.
    counterexample: `amount` là float làm mất chữ số; trộn actual và estimated mà không đánh dấu; lộ `operation_ref`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_11_cost.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/cost.py').read_text(encoding='utf-8').lower(); assert 'float(' not in t and 'operation_ref' not in t and 'batch_ref' not in t and 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'os.environ' not in t, 'RS-11'"`

### RS-12: Bộ ghép compose_read_screens

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/read_screens/compose.py`
  - `tests/integration/read_screens/test_rs_12_compose.py`
  - `docs/delivery-evidence/rs-12/report.md`
- dependsOn: `RS-2`, `RS-3`, `RS-4`, `RS-5`, `RS-6`, `RS-7`, `RS-8`, `RS-9`, `RS-10`, `RS-11`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `src/controlplane/api/wiring/production.py:310-318,385-398`; `src/controlplane/infrastructure/db/uow.py:93-97`; `src/controlplane/api/main.py:68-72`; `docs/parallel-delivery/ownership-and-locks.yaml:221-222`
- acceptance:
  - requirement: (1) `compose_read_screens(manager)` trả dict có đúng mười khóa `articles`, `events`, `media`, `artifacts`, `snapshots`, `story-angles`, `scripts`, `sessions`, `accounts`, `cost`; mỗi service dựng với `connection_scope=manager.borrow_connection`. (2) Mọi service có `fetch_page` và `fetch_one`; chỉ `media` có `apply_update` (ném `CapabilityUnavailableError`). (3) `compose.py` chỉ import từ các mô-đun anh em của `read_screens`; không import `production` (tránh vòng) và không import bất cứ gì từ `controlplane.api`; không mở kết nối khi dựng.
    instrument: test PostgreSQL với `temp_database`: dựng bộ ghép, gọi `fetch_page` của từng service trên CSDL rỗng nhận `Page` không có phần tử và `next_cursor` là `None`; `fetch_one` id lạ trả `None`; kiểm tập khóa đúng mười; `ast.parse` `compose.py` xác nhận danh sách import; dựng bộ ghép không gọi `borrow_connection` (đếm lời gọi).
    counterexample: thiếu hoặc thừa khóa; tên khóa lệch tên trong catalog (`story-angles` viết `story_angles`); import vòng với `production.py`; mở kết nối lúc dựng.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_12_compose.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/compose.py').read_text(encoding='utf-8').lower(); assert 'story-angles' in t and 'wiring.production' not in t and 'controlplane.api' not in t and 'from src.' not in t and 'os.environ' not in t, 'RS-12'"`

### RS-13: Kiểm đầu cuối trên ứng dụng production

- kind: work_package_slice
- ownedPaths:
  - `tests/integration/read_screens/test_rs_13_prod_e2e.py`
  - `docs/delivery-evidence/rs-13/report.md`
- dependsOn: `RS-12`, `CP-4-WIRING-FIX3`, `ADAPT-PROD-FIX3`
- resourceLocks: `LOCK-READ-SCREENS`
- bindingRefs: `tests/integration/adapt/prod/test_adapt_prod_app.py:49-135,285-305`; `src/controlplane/api/wiring/production.py:385-398`; `docs/implementation/read-screens/plan.md` mục 7 và 9
- acceptance:
  - requirement: (1) Dựng ứng dụng bằng `build_production_app` trên CSDL tạm (sao chép mẫu dựng `ProductionRuntime`, capability và phiên của `test_adapt_prod_app.py`, không import chéo giữa tệp test). (2) Với dữ liệu thật tạo bằng repository của phân hệ (như RS-2 đến RS-11), `GET /v1/<tài nguyên>?limit=1` trả 200 với `items` đúng dữ liệu và `next_cursor` không rỗng khi có hơn một dòng; trang tiếp theo qua `cursor` trả phần còn lại, cho đủ mười tài nguyên. (3) `GET /v1/<tài nguyên>/{id}` trả 200 cho id có thật và 404 `NOT_FOUND` cho id lạ và id của workspace khác. (4) `PATCH /v1/media/{id}` trả 503 `CAPABILITY_UNAVAILABLE`; `GET /v1/logs` vẫn 404; `GET /v1/sources` và `GET /v1/hooks` giữ nguyên trạng thái như `test_adapt_prod_app.py:296-305`. (5) Không phản hồi nào chứa canary hay trường cấm của mục 4 plan.md.
    instrument: test đầu cuối qua `TestClient` với header phiên như `test_adapt_prod_app.py:285-300`; hai workspace; canary cho từng tài nguyên; đếm hàng bảng nguồn trước và sau để chứng minh chỉ đọc.
    counterexample: route 503 vì quên gắn service; 404 vì thiếu mục catalog; lộ dữ liệu workspace khác; `logs` bị nối ngầm; `PATCH /v1/media` trả 500.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/read_screens/test_rs_13_prod_e2e.py -q -p no:cacheprovider`
  - `python -c "import pathlib; t = pathlib.Path('tests/integration/read_screens/test_rs_13_prod_e2e.py').read_text(encoding='utf-8'); assert '/v1/logs' in t and 'story-angles' in t and 'build_production_app' in t, 'RS-13'"`
