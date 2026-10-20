# Kế hoạch adapter PostgreSQL — IMPL-PLAN-PERSIST

- **Mã gói**: IMPL-PLAN-PERSIST (planning_package)
- **Ngày lập**: 20/10/2026
- **Cơ sở**: HEAD `bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc`; trong cây này `src/controlplane/infrastructure/db/migrations/` mới có `0001`..`0008`; migration `0009`..`0018` của CP-3 chưa có.
- **Nguồn quyền (D3)**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026. `PRODUCTION_ACTIVATION_BLOCKED` vẫn hiệu lực; không push, không merge, không chạm main hay backup.
- **Slice**: `docs/implementation/persist/slices.md` (chín slice `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J`). **Bằng chứng**: `docs/delivery-evidence/impl-plan-persist/report.md`.

## 1. Phạm vi và nguyên tắc

Kế hoạch này chuyển phần adapter PostgreSQL của các mục `CONV-A-01`, `REQ-B-CONV-01` và `REQ-B-CONV-02`, `CONV-C-01`, `CONV-D-01`, `CONV-E-01`, `CONV-F-01`, `YC-HT-G-01`, `YC-HT-I-01`, `YC-HT-J-01` thành chín slice do Control mở sau khi `CP-3-MIGRATIONS` đạt Auditor PASS (`docs/implementation/convergence/plan.md` mục 5.3 và 11.1). Phân hệ H không thêm bảng (migration `0018` chỉ thêm index) nên không có slice.

1. Chỉ cài port đã có trong `src/`; không đổi chữ ký port; không viết lại adapter đã nghiệm thu mà chỉ mở rộng (G, I, J).
2. Không tạo migration, không sửa `MigrationRunner`, composition root, `api/wiring`, lockfile, `tests/m2`, `ui/dist`, state machine, control API; việc nối vào ứng dụng là của `CP-4-WIRING`.
3. Không thêm thư viện: `psycopg[binary,pool]==3.3.5` và `psycopg-pool==3.3.1` đã khóa (convergence mục 3.1).
4. Mọi phép kiểm chạy trên PostgreSQL 18.6; không dùng kho tạm, SQLite, fake hay mock thay cho PostgreSQL. Adapter in-memory của A–F (`adapters/memory.py`) giữ nguyên, chỉ còn dùng cho test logic.
5. Import root là `src/`, không dùng tiền tố `src.`; adapter của phân hệ này không import adapter hay bảng của phân hệ khác, chỉ trao đổi qua port và tham chiếu chuỗi.
6. Tên bảng và cột của `0009`..`0018` trong tài liệu này lấy từ bảng 5.2 của kế hoạch hội tụ và các mục yêu cầu của kế hoạch phân hệ; chúng là **GIẢ ĐỊNH** tới khi CP-3 đạt Auditor PASS (mục 7, OI-PERSIST-01). Worker của slice mở tệp migration thật trước khi viết adapter, đối chiếu bằng `information_schema` trong test, và dừng `BLOCKED` kèm `blocked-manifest` (`DEPENDENCY_GAP`, `ownerTaskIds` là `CP-3-MIGRATIONS`) nếu thiếu bảng hay cột; không tự thêm migration.

## 2. Vị trí mã (D1, convergence mục 5.3)

Không dựng cây trùng (`src/storage`, `src/orchestration`, `src/ui`, `src/controlplane/infrastructure/db/completion`). Slice X chỉ sở hữu thư mục adapter của phân hệ X, tệp test `tests/integration/persistence/<x>/test_persist_<x>_postgres.py` (chữ thường) và bằng chứng `docs/delivery-evidence/persist-<x>/report.md`.

| Slice | Thư mục adapter | Khóa tài nguyên | Cổng thả |
| --- | --- | --- | --- |
| `PERSIST-A` | `src/source_ingestion/persistence` (mới) | `LOCK-SRC-SOURCE-INGESTION` | `GATE-PERSIST-A` |
| `PERSIST-B` | `src/ingestion/persistence` (mới) | `LOCK-SRC-INGESTION` | `GATE-PERSIST-B` |
| `PERSIST-C` | `src/catalog/persistence` (mới) | `LOCK-SRC-CATALOG` | `GATE-PERSIST-C` |
| `PERSIST-D` | `src/creative/persistence` (mới) | `LOCK-SRC-CREATIVE` | `GATE-PERSIST-D` |
| `PERSIST-E` | `src/voice/persistence` (mới) | `LOCK-SRC-VOICE` | `GATE-PERSIST-E` |
| `PERSIST-F` | `src/render/persistence` (mới) | `LOCK-SRC-RENDER` | `GATE-PERSIST-F` |
| `PERSIST-G` | `src/controlplane/infrastructure/db/orchestration` (có sẵn, mở rộng) | `LOCK-SRC-ORCHESTRATION` | `GATE-PERSIST-G` |
| `PERSIST-I` | `src/controlplane/infrastructure/db/storage_meta` (có sẵn, mở rộng) | `LOCK-SRC-STORAGE` | `GATE-PERSIST-I` |
| `PERSIST-J` | `src/controlplane/infrastructure/db/config_security` (có sẵn, mở rộng) | `LOCK-SRC-CONFIG-SECURITY` | `GATE-PERSIST-J` |

Chín khóa khác nhau nên chín slice chạy song song. Gói `controlplane.infrastructure.db.orchestration`, `storage_meta` và `config_security` đã khai trong `src/controlplane/pyproject.toml`, nên slice G, I, J không tạo `__init__.py` mới và không sửa `pyproject.toml`; slice A–F chỉ thêm gói con `persistence` (có `__init__.py`) trong thư mục phân hệ của mình.

## 3. Mẫu chung: unit of work, outbox và ràng buộc

1. **Một giao dịch, một kết nối.** `TransactionManager` (`src/controlplane/infrastructure/db/uow.py`) sở hữu pool; `borrow_connection()` mượn đúng một kết nối cho một phạm vi giao dịch. Mỗi phân hệ A–F có lớp `Postgres<Phân hệ>UnitOfWork(manager)` cài `IUnitOfWork` (`begin`, `commit`, `rollback`, `__enter__`, `__exit__` của `src/controlplane/domain/interfaces/uow.py`) và giữ các thuộc tính kho cùng `outbox` mà Protocol UoW và bản in-memory của phân hệ đã có (ví dụ A: `sources`, `candidates`, `runs`, `packages`, `checkpoints`, `receipts`, `outbox`). Mọi kho trong cùng UoW dùng chung kết nối đó; kho không tự lấy kết nối từ pool. `__exit__` gọi `rollback()` khi chưa `commit()` (khác `SqlUnitOfWork` vốn commit khi thoát bình thường), để giữ đúng ngữ nghĩa của bản in-memory: ra khỏi `with` mà chưa `commit()` thì cả kho lẫn outbox bị hủy. G, I, J giữ mẫu hiện có: kho nhận `connection` do caller sở hữu.
2. **Outbox cùng giao dịch.** Event ghi vào `controlplane.cp_outbox_events` (migration `0003`) bằng kết nối của UoW. Port `IOutboxWriter.append_event(event_type, aggregate_id, payload, deduplication_id)` của A–F không có `workspace_id`, nên adapter nhận `workspace_id`, `correlation_id` và `actor` từ ngữ cảnh UoW, dựng `DomainEvent` rồi gọi `PostgresOutboxRepository.enqueue` có sẵn (không viết lại). `event_id` là `uuid5(NAMESPACE_URL, deduplication_id)`; nếu hàng cùng `event_id` đã có thì trả `event_id` cũ và không chèn lại (giống bản in-memory). Payload đi qua `ensure_safe_event_payload`: không secret, không byte thô.
3. **`recovery_epoch` là text.** Migration `0010` và `0011` đổi cột sang `text`. Mọi so sánh `recovery_epoch` trong adapter và test dùng `str(giá trị)` ở hai phía; không ép `int`, không so số. Cột `recovery_epoch` của `cp_outbox_events` vẫn là `BIGINT NULL` (migration `0003`, ngoài `0009`..`0018`): adapter ghi số khi chuỗi chỉ gồm chữ số thập phân, ngược lại ghi `NULL`, và không bao giờ để cột này làm commit thất bại (OI-PERSIST-03).

## 4. Cách kiểm trên PostgreSQL 18.6 (dùng một lần, cơ sở dữ liệu tạm)

Mỗi test của slice tự dựng cơ sở dữ liệu tạm riêng theo mẫu fixture `disposable_db` của `tests/m2/test_p3_outbox_and_projections.py`; chép mẫu vào tệp test của slice, không import từ `tests/m2`, không tạo `conftest.py` dùng chung:

1. Đọc DSN quản trị từ biến môi trường `M2_TEST_PG_DSN`; thiếu biến thì `pytest.fail('BLOCKED_EXTERNAL: ...')`, không skip, không có đường lùi sang kho tạm. Kiểm `SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user` là true (user có `CREATEDB`).
2. `CREATE DATABASE persist_<x>_<hex ngẫu nhiên>` (tên khớp `^persist_[a-j]_[0-9a-f]+` ), rồi tạo DSN mới bằng `make_conninfo(admin_dsn, dbname=tên)`.
3. Chạy `MigrationRunner(dsn, src/controlplane/infrastructure/db/migrations, is_test_env=True, expected_database_name=tên).migrate_up()` rồi khẳng định `SELECT version FROM controlplane.cp_schema_migrations ORDER BY version` bằng `[1..18]`; thiếu `0009`..`0018` thì test FAIL, không tự tạo bảng.
4. Kiểm bằng `information_schema` rằng mọi bảng và cột slice dùng có trong schema thật (chống chép sai tên bảng).
5. Kiểm round-trip từng kho (ghi rồi đọc lại bằng giá trị bằng nhau), từng ràng buộc unique (vi phạm cho đúng lỗi lĩnh vực của port, ví dụ `DuplicatePackageError`), từng bảng append-only (UPDATE và DELETE bị từ chối) và giao dịch với outbox: raise giữa chừng thì cả bảng phân hệ lẫn `cp_outbox_events` không đổi; `commit()` thì cả hai cùng có; gọi lặp cùng `deduplication_id` chỉ có một hàng outbox.
6. Teardown: đóng kết nối, `pg_terminate_backend`, `DROP DATABASE`, khẳng định không còn cơ sở dữ liệu mồ côi.

Slice PERSIST không giữ `LOCK-POSTGRES-TEST-DB`: mỗi test có cơ sở dữ liệu riêng (khóa advisory của `MigrationRunner` có phạm vi theo từng cơ sở dữ liệu) nên chín slice chạy song song không đụng nhau.

## 5. Chi tiết theo phân hệ

Mỗi mục nêu port cài, bảng (theo convergence mục 5.2, tên chính xác là GIẢ ĐỊNH tới khi có migration) và ràng buộc. Cách kiểm chi tiết nằm ở `slices.md`.

### 5.1. PERSIST-A — Nguồn thu thập (`0012_source_ingestion`, CONV-A-01)

- Port (`src/source_ingestion/ports/repositories.py`): `SourceRepository`, `SourceCandidateRepository`, `CollectionRunRepository`, `PackageRepository`, `CheckpointRepository`, `ReceiptStore`; UoW theo Protocol `SourceUnitOfWork`, `CandidateUnitOfWork`, `CollectionUnitOfWork` (`src/source_ingestion/application/`).
- Bảng: source, định danh locator và tombstone, source_candidate, collection_run, collection_attempt, collection_checkpoint, fetch_observation, collected_document_package.
- Ràng buộc: locator canonical duy nhất theo workspace, tombstone vẫn giữ (`DuplicateSourceIdentityError`); collection_run duy nhất `(workspace, source, business_date, PERIODIC)` và không chứa policy revision (A-RULE-004); package duy nhất `(source_id, canonical_locator, observation_fingerprint)` (`DuplicatePackageError`); receipt duy nhất `(workspace_id, idempotency_key)` (`DuplicateReceiptError`); `CheckpointRepository.advance` gọi `advance_checkpoint` của domain nên checkpoint chỉ tiến qua item đã bền vững. Mười event của A đi qua outbox cùng giao dịch.

### 5.2. PERSIST-B — Ingestion (`0013_ingestion`, REQ-B-CONV-01 và 02)

- Port (`src/ingestion/application/ports.py`): `ArticleRepository`, `ResolutionRepository`, `EventRepository`, `RecordRepository`, `OutboxWriter` và `UnitOfWork` (`articles`, `resolutions`, `events`, `records`, `outbox`; một giao dịch cho mỗi collected document, D8-B-11). `SourceTierLookup` không phải port PostgreSQL của B.
- Bảng: articles, article_revisions, collected_document_resolutions, dedup_evidence, events, event_link_candidates, event_updates, event_update_candidates.
- Ràng buộc: resolution duy nhất `(collected_document_id, dedup_policy_revision)`; tra article theo `identity_key` và `exact_fingerprint`; revision, dedup_evidence và event_update là append-only; `RecordRepository` ánh xạ bốn `kind` vào bốn bảng tương ứng; B tham chiếu `collected_document_package` của A bằng chuỗi, không join và không import A.

### 5.3. PERSIST-C — Catalog (`0014_catalog`, CONV-C-01)

- Port: `MediaAssetRepository` (`src/catalog/ports/repositories.py`), `MediaUsageRepository` (`src/catalog/ports/usage.py`); lịch sử hook qua `HookHistory` (`src/catalog/application/hooks.py`, `get(hook_id, revision)` và `append(HookRevision)`; OI-PERSIST-04).
- Bảng: media_assets, media_provenance, media_renditions, hooks, hook_revisions, media_usage (`usage_kind` là `production` hoặc `technical`), index FTS. Không có pgvector (D8-CV-02).
- Ràng buộc: tra theo fingerprint và `discovery_id`; rendition và hook_revisions bất biến; media_usage duy nhất `(completion_id, media_asset_id, role, usage_kind)`, chỉ dòng `production` được đếm. Kho `MediaUsage` nhận kết nối của caller để `MediaUsageRecorder.record_production_usage` chạy cùng giao dịch completion của `CP-5-COMPLETION`; adapter không mở kết nối thứ hai.

### 5.4. PERSIST-D — Creative (`0015_creative`, CONV-D-01)

- Port (`src/creative/ports/repositories.py`): `SnapshotRepository`, `AppendOnlyRepository` cùng sáu kho con (`AnalysisRepository`, `AngleSetRepository`, `ScriptRepository`, `PlanRepository`, `VariantValidationRepository`, `OutputMetadataRepository`), `InvocationRecordRepository` và `ReceiptStore`.
- Bảng: production_snapshot, content_analysis, story_angle_set, story_angle, script_version, production_plan, variant_validation, output_metadata, ai_invocation_record, receipt.
- Ràng buộc: `snapshot_id` duy nhất và bất biến (`DuplicateSnapshotError`); `append(key, revision, record)` chỉ nhận `revision = latest + 1`, sai thì `RevisionConflictError` của `controlplane.domain.concurrency`; id duy nhất theo `UNIQUE_ID_ATTRS` của file port (`DuplicateRecordError`); receipt duy nhất `(workspace_id, idempotency_key)`; mọi bảng lịch sử chặn UPDATE và DELETE.

### 5.5. PERSIST-E — Voice (`0016_voice`, CONV-E-01)

- Port (`src/voice/ports/repositories.py`): `OutputRepository` (`append(kind, key, revision, record)`, `latest`, `revisions`) với `KIND_VOICE` và `KIND_WORD_TIMING`; UoW theo Protocol `VoiceUnitOfWork` (`src/voice/application/voice_pipeline.py`) và `MediaUnitOfWork` (`src/voice/application/media_pipeline.py`), cùng thuộc tính `outputs` và `outbox`.
- Bảng: processed_media, image_safety_assessment, voice_track, word_timing, timing_validation_report, tts_invocation_record, language_evidence, audio_bed_result, probe_report, analysis_result, receipt.
- Ràng buộc: `voice_hash` duy nhất và `timing_artifact_ref` duy nhất (`DuplicateOutputError`); revision tăng đúng một; bảng lịch sử append-only. Chỉ cài các `kind` mà file port khai; không thêm `kind` mới.

### 5.6. PERSIST-F — Render (`0017_render`, CONV-F-01)

- Port (`src/render/ports/repositories.py`): `RenderRepository` với `KIND_PACKAGE`, `KIND_ATTEMPT`, `KIND_QUALITY_REPORT` và `RECORD_TYPES`; UoW theo `PackageUnitOfWork` (`src/render/application/package_pipeline.py`: `renders`, `outbox`, `reports`, `receipts`, `traces`) và `RenderUnitOfWork` (`src/render/application/render_video.py`: thêm `attempt_index`).
- Bảng: render_preset_revision, render_package, package_validation_report, render_attempt, quality_report, quality_gate_result, video_output, operation_receipt.
- Ràng buộc: `package_fingerprint` duy nhất và bất biến giữa các revision; `render_attempt_id` duy nhất; `output_artifact_ref` duy nhất giữa các attempt khác nhau và bất biến trong một attempt (`DuplicateRecordError`, `ImmutableFieldError`); khóa package phải bằng `render_package_id`, khóa attempt bằng `render_attempt_id`; bảng lịch sử append-only.

### 5.7. PERSIST-G — Orchestration (`0011_orchestration_extensions`, YC-HT-G-01)

- Mở rộng `PostgresOrchestrationRepository` (`src/controlplane/infrastructure/db/orchestration/__init__.py`) và `start_batch.py`; port: `GrantStorePort` và `RecoveryEpochPort` (`src/controlplane/application/orchestration/grant_issuance.py`), `AllocationStorePort` (`job_allocation.py`), `VariantRegistryPort` (`variant_reservation_flow.py`), `StartBatchRepositoryPort` (`start_batch.py`).
- Bảng: grant (mới); cột mới của `cp_stage_runs` (`stage_type`, `input_refs`, `dependency_refs`, `wait_reason`, `problem`, mốc thời gian, `superseded_by`) và `cp_video_jobs` (`wait_reason`, tham chiếu variant cha và trước); trường CT-ORC-009 của `cp_completion_ledger`; receipt, cleanup eligibility, app session, lý do dừng batch.
- Ràng buộc: grant đơn điệu theo `stage_run_id` và duy nhất `(stage_run_id, generation)`; một lease hoạt động cho mỗi stage; `lock_batch` dùng `SELECT ... FOR UPDATE` trên dòng batch; `recovery_epoch` text so bằng `str()`. `CompletionStorePort` và `postgres_completion.py` thuộc `CP-5-COMPLETION` (BL-CV-11), slice này không tạo.

### 5.8. PERSIST-I — Storage metadata (`0010_storage_meta_extensions`, YC-HT-I-01)

- Mở rộng `PostgresStorageMetaRepository` (`src/controlplane/infrastructure/db/storage_meta/__init__.py`); port: `StorageMetaRepository` (`src/controlplane/application/storage_meta/__init__.py`), `UploadReceiptPort` (`cloud_persist.py`), `ArtifactVersionCatalogPort` (`declare_version.py`). `CloudObjectPort` không phải port PostgreSQL.
- Bảng: `cp_artifact_versions` (thêm `intended_storage_class`, `producer_operation_ref`, `lineage_refs`), upload receipt (có `OUTCOME_UNKNOWN`), lease materialization, revision placement và working set policy, `cp_artifact_locations` (trường CT-STO-002 còn thiếu), `cp_cleanup_authorizations` (`recovery_epoch` sang text).
- Ràng buộc: giữ trigger bất biến của `cp_artifact_versions` và `cp_cleanup_authorizations` (migration `0005`); khai báo lặp cùng `(workspace_id, artifact_id, sha256_hash)` trả bản cũ; upload receipt duy nhất theo `operation_key`; `recovery_epoch` so bằng `str()`.

### 5.9. PERSIST-J — Config và security (`0009_config_security_extensions`, YC-HT-J-01)

- Mở rộng `PostgresConfigSecurityRepository` và `PostgresConfigEventSink` (`src/controlplane/infrastructure/db/config_security/__init__.py`); port: `ConfigSecurityRepositoryPort`, `ConfigEventSinkPort` (`src/controlplane/application/config_security/__init__.py`), `ReservationStorePort` (`capacity_reservation.py`), `CostLedgerPort` (`routed_invocation.py`), `ReceiptStorePort` (`account_test.py`), `AuditSinkPort` (`src/controlplane/domain/config_security/audit_record.py`). `SecretStorePort` không có adapter PostgreSQL: giá trị bí mật chỉ ở broker DPAPI (J-17), PostgreSQL chỉ giữ metadata handle (OI-PERSIST-06).
- Bảng: `cp_external_accounts`, `cp_provider_capacity_snapshots`, `cp_capacity_reservations` (có expiry), `cp_cost_records`, `cp_audit_records` (append-only), `cp_secret_handles` (thêm credential version và revocation version), CHECK `scope_kind` của `cp_config_revisions`.
- **F1 của IMPL-PLAN-J**: cột `effective_at` của `cp_config_revisions` đã có từ `0004` (không cần migration). Thêm một phương thức đọc vào `PostgresConfigSecurityRepository` chọn thêm cột `effective_at` rồi dựng `EffectiveConfigRevision(revision, effective_at)` với `revision` là `ConfigRevision` chín trường và `effective_at` là `datetime` có múi giờ hoặc `None`; danh sách đó là đầu vào của `resolve_bundle(revisions, request)` (`src/controlplane/application/config_security/bundle_resolution.py`). `ConfigRevision` không mang `effective_at`; không đổi `_revision()` và không đổi dataclass. `effective_at` ngây thơ (naive) làm `EffectiveConfigRevision` ném `naive_effective_at`, nên cột phải được đọc dạng `timestamptz`.

## 6. Cổng GATE-PERSIST và quan hệ với CP-4, CP-5

- Slice `PERSIST-X` thả đúng một cổng `GATE-PERSIST-X` cùng mã chữ cái khi Auditor PASS: `GATE-PERSIST-A`, `GATE-PERSIST-B`, `GATE-PERSIST-C`, `GATE-PERSIST-D`, `GATE-PERSIST-E`, `GATE-PERSIST-F`, `GATE-PERSIST-G`, `GATE-PERSIST-I`, `GATE-PERSIST-J`. Phân hệ H không có slice và không có cổng. Cổng chờ đúng chín mã này nên tiêu đề trong `slices.md` khớp từng ký tự dạng `PERSIST-<mã>: <tên>` ở cấp ba.
- `CP-4-WIRING` chờ cả chín cổng (convergence mục 11.1): route và wiring cần kho PostgreSQL thật của từng phân hệ; không bỏ cạnh nào.
- `CP-5-COMPLETION` chờ `GATE-PERSIST-C`, `GATE-PERSIST-G`, `GATE-PERSIST-I`: ledger, `MediaUsage` và outbox chỉ chứng minh cùng giao dịch trên kho PostgreSQL thật. `PERSIST-C` cung cấp kho `MediaUsage` nhận kết nối caller, `PERSIST-G` cung cấp bảng và kho của `0011`, `PERSIST-I` cung cấp kho storage meta; `PostgresCompletionUnitOfWork` là việc của CP-5.
- Mỗi slice phụ thuộc `CP-3-MIGRATIONS` và slice của phân hệ đã tạo port: A-08, B-3, C-09, D-13, E-15, F-16, G-10, I-04, J-09 (J thêm J-18 vì `CostLedgerPort`). Các mã này đã có trong danh sách phụ thuộc của `CP-3-MIGRATIONS` và `CP-4-WIRING` nên có sẵn trong Portfolio.
- Không slice nào được chạy trước khi CP-3 đạt Auditor PASS.

## 7. Mục mở và mặc định đã chọn (D8)

Không mục nào là đã duyệt; mục cần user vẫn nằm trong `pendingUserCheckpoint` của kế hoạch hội tụ.

| Mã | Nội dung | Mặc định | Lý do |
| --- | --- | --- | --- |
| OI-PERSIST-01 | Tên bảng và cột của `0009`..`0018` chưa có trong cây | Dùng tên ở convergence mục 5.2; test đối chiếu `information_schema`; thiếu thì `BLOCKED` (`DEPENDENCY_GAP`, owner `CP-3-MIGRATIONS`) | Không chép tên bảng không có thật; slice không tự thêm migration |
| OI-PERSIST-02 | `ownership-and-locks.yaml` chưa phủ `src/controlplane/infrastructure/db/config_security/**` (khóa J), `tests/integration/persistence/**` và `docs/delivery-evidence/persist-*/**` | Control mở rộng phong bì khi biên dịch kèm khóa của phân hệ; không sửa registry trong gói này | Registry thuộc `CP-2D-REGISTRY`; thiếu phủ thì slice BLOCKED, không đổi khóa |
| OI-PERSIST-03 | Outbox `0003` có `recovery_epoch BIGINT`, event A–F mang chuỗi | Ghi số khi chuỗi toàn chữ số, ngược lại `NULL` | Không cần migration; so sánh nghiệp vụ vẫn bằng `str()` ở cột text |
| OI-PERSIST-04 | `HookHistory` là lớp cụ thể, chưa có Protocol | Adapter cùng phương thức `get(hook_id, revision)` và `append(HookRevision)`; không thay thế được thì BLOCKED, không sửa `src/catalog/application` | Slice C chỉ sở hữu `src/catalog/persistence` |
| OI-PERSIST-05 | pgvector (ADR-0002) | Hoãn; C dùng FTS (D8-CV-02) | Embedding chưa chốt; thêm bằng migration `0019` ở slice hội tụ mới |
| OI-PERSIST-06 | Nơi lưu secret (PUC-J-07) | Broker DPAPI-file (J-17); PostgreSQL chỉ lưu metadata handle | Quyết định của Control ngày 20/10/2026; không bí mật nào vào cơ sở dữ liệu |
| OI-PERSIST-07 | Cạnh state machine PUC-J-03 và YC-HT-I-04 (user duyệt 20/10/2026); PUC-G-02 giữ nguyên | Adapter chỉ lưu trạng thái hiện có, không mã hóa cạnh mới | Đồ thị thuộc `CP-3B-STATE-MACHINE` |

## 8. Thư viện và ngoài phạm vi

- Không thêm thư viện: chỉ `psycopg[binary,pool]==3.3.5`, `psycopg-pool==3.3.1` (đã khóa) và `pytest==9.1.1` đã có. Không dùng ORM.
- Ngoài phạm vi: migration, `MigrationRunner`, composition root, `api/wiring`, route, UI, state machine, workflow, `postgres_completion.py` (CP-5), dịch vụ thật (CP7), kích hoạt sản xuất, push và merge.
- Kích thước biên dịch: `slices.md` có chín mục, mỗi mục không quá 5000 ký tự và tổng không quá 38000 ký tự để gói biên dịch của kế hoạch dưới 60000 ký tự (`PLAN_REVIEW_INPUT_TOO_LARGE` nếu vượt).
