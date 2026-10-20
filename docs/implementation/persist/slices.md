# Slice adapter PostgreSQL — IMPL-PLAN-PERSIST

Nguồn: `docs/implementation/persist/plan.md`. Chín slice `work_package_slice` do Control biên dịch sau khi `CP-3-MIGRATIONS` đạt Auditor PASS; mỗi slice thả đúng một cổng `GATE-PERSIST-<mã>` cùng mã chữ cái (A, B, C, D, E, F, G, I, J; không có slice cho H).

## Quy tắc chung cho mọi slice

- Chỉ sửa đúng tệp trong `ownedPaths`; không sửa migration, composition root, `api/wiring`, lockfile, `tests/m2`, `ui/dist`, `App.tsx`, state machine hay control API; không thêm thư viện; không gọi dịch vụ thật; không đọc `Credentials/` hay bí mật.
- Trước khi viết adapter, đọc tệp migration thật; thiếu bảng hay cột thì BLOCKED kèm `blocked-manifest` (`DEPENDENCY_GAP`, `ownerTaskIds` là `CP-3-MIGRATIONS`); không tạo migration; không sửa adapter in-memory.
- Mọi phép kiểm chạy trên PostgreSQL 18.6 theo mẫu plan.md mục 4 (mỗi test một cơ sở dữ liệu tạm riêng, `MigrationRunner` tới 18); không dùng kho tạm, SQLite, fake hay mock thay PostgreSQL.
- Test-first: thấy RED do assertion đúng oracle (thiếu migration, ImportError hay thiếu binary không phải RED hợp lệ) rồi implement tới GREEN; `recovery_epoch` là text so bằng `str()`; import root `src/`, không tiền tố `src.`.
- Bằng chứng ở `docs/delivery-evidence/persist-<mã chữ thường>/report.md`; `testCommands` chạy bằng interpreter khoá của runtime D9.
- Mỗi mục slice theo thứ tự kind, ownedPaths, dependsOn, resourceLocks, bindingRefs, acceptance, testCommands và không quá 5000 ký tự.

### PERSIST-A: Adapter PostgreSQL của nguồn thu thập (A)

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/persistence/**`
  - `tests/integration/persistence/a/test_persist_a_*.py`
  - `docs/delivery-evidence/persist-a/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `A-08`
- resourceLocks: `LOCK-SRC-SOURCE-INGESTION`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Tạo gói `src/source_ingestion/persistence` (có `__init__.py`) cài sáu port của `src/source_ingestion/ports/repositories.py` (`SourceRepository`, `SourceCandidateRepository`, `CollectionRunRepository`, `PackageRepository`, `CheckpointRepository`, `ReceiptStore`) trên bảng của migration `0012_source_ingestion` (source, định danh locator và tombstone, source_candidate, collection_run, collection_attempt, collection_checkpoint, fetch_observation, collected_document_package), và `PostgresSourceIngestionUnitOfWork(manager)` với `sources`, `candidates`, `runs`, `packages`, `checkpoints`, `receipts`, `outbox`, mượn một kết nối từ `TransactionManager` và chung giao dịch với `cp_outbox_events`. Unique: locator canonical theo workspace kể cả tombstone (`DuplicateSourceIdentityError`); collection_run `(workspace, source, business_date, PERIODIC)` không có policy revision; package `(source_id, canonical_locator, observation_fingerprint)` (`DuplicatePackageError`); receipt `(workspace_id, idempotency_key)` (`DuplicateReceiptError`); `advance` chỉ tiến qua item bền vững.
    instrument: `test_persist_a_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip từng kho, từng unique, rollback và commit cùng `cp_outbox_events`, lặp `deduplication_id` chỉ một dòng outbox.
    counterexample: kho tạm hay fake thay PostgreSQL; chép tên bảng không có trong migration; tự thêm migration; kho tự lấy kết nối từ pool; tự commit khi thoát `with`; tombstone cho đăng ký lại cùng locator; tiền tố `src.`; cây trùng ngoài `src/source_ingestion/persistence`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter A'"`

### PERSIST-B: Adapter PostgreSQL của ingestion (B)

- kind: work_package_slice
- ownedPaths:
  - `src/ingestion/persistence/**`
  - `tests/integration/persistence/b/test_persist_b_*.py`
  - `docs/delivery-evidence/persist-b/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `B-3`
- resourceLocks: `LOCK-SRC-INGESTION`
- bindingRefs: `docs/parallel-delivery/bindings/a-b-collected-document.json`, `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- acceptance:
  - requirement: Tạo gói `src/ingestion/persistence` (có `__init__.py`) cài `ArticleRepository`, `ResolutionRepository`, `EventRepository`, `RecordRepository` của `src/ingestion/application/ports.py` trên bảng của migration `0013_ingestion` (articles, article_revisions, collected_document_resolutions, dedup_evidence, events, event_link_candidates, event_updates, event_update_candidates), và `PostgresIngestionUnitOfWork(manager)` thỏa Protocol `UnitOfWork` của file đó (`articles`, `resolutions`, `events`, `records`, `outbox`, `commit`, `rollback`): một giao dịch cho mỗi collected document, aggregate và outbox cùng commit hoặc cùng rollback (REQ-B-CONV-02, CT-EVT-001). Unique: resolution `(collected_document_id, dedup_policy_revision)`; tra article theo `identity_key` và `exact_fingerprint`; `article_revisions`, `dedup_evidence`, `event_updates` append-only; `RecordRepository` ánh xạ bốn `kind` (`dedup_evidence`, `event_link_candidate`, `event_update`, `event_update_candidate`) vào bốn bảng, `kind` lạ bị từ chối. B tham chiếu `collected_document_package` của A bằng chuỗi, không join, không import A.
    instrument: `test_persist_b_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip từng kho, unique của resolution, UPDATE vào bảng append-only bị từ chối, article cùng outbox cùng commit hoặc cùng rollback.
    counterexample: kho tạm thay PostgreSQL; hai resolution cùng khóa; UPDATE vào bảng append-only; `kind` lạ ghi vào bảng bất kỳ; join hay import bảng của A; aggregate commit mà outbox rollback.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter B'"`

### PERSIST-C: Adapter PostgreSQL của catalog (C)

- kind: work_package_slice
- ownedPaths:
  - `src/catalog/persistence/**`
  - `tests/integration/persistence/c/test_persist_c_*.py`
  - `docs/delivery-evidence/persist-c/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `C-09`
- resourceLocks: `LOCK-SRC-CATALOG`
- bindingRefs: `docs/parallel-delivery/bindings/c-d-media-candidates.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: Tạo gói `src/catalog/persistence` (có `__init__.py`) cài `MediaAssetRepository` (`src/catalog/ports/repositories.py`: `get`, `find_by_fingerprint`, `find_by_discovery_id`, `save`) và `MediaUsageRepository` (`src/catalog/ports/usage.py`: `exists`, `add`) trên bảng của migration `0014_catalog` (media_assets, media_provenance, media_renditions, hooks, hook_revisions, media_usage với `usage_kind` là `production` hoặc `technical`, index FTS; không pgvector), cùng lớp lịch sử hook có đúng phương thức `get(hook_id, revision)` và `append(HookRevision)` của `HookHistory` (`src/catalog/application/hooks.py`); nếu lớp đó không thay thế được thì BLOCKED, không sửa `src/catalog/application`. Mọi kho nhận kết nối của caller (hoặc UoW mượn từ `TransactionManager`) để `MediaUsageRecorder.record_production_usage` chạy cùng giao dịch completion của `CP-5-COMPLETION`; adapter không mở kết nối thứ hai. Unique: media_usage `(completion_id, media_asset_id, role, usage_kind)`, ghi lặp không nhân đôi; rendition và hook_revisions bất biến; chỉ dòng `production` được đếm.
    instrument: `test_persist_c_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip tài sản và hook revision, unique của media_usage, lỗi sau `add` thì rollback giữ nguyên số dòng, truy vấn FTS trả đúng tài sản.
    counterexample: kho tạm thay PostgreSQL; pgvector trong schema; hai dòng production cùng khóa; kho tự mở kết nối thứ hai; sửa rendition hoặc hook_revisions; sửa `src/catalog/application`.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter C'"`

### PERSIST-D: Adapter PostgreSQL của creative (D)

- kind: work_package_slice
- ownedPaths:
  - `src/creative/persistence/**`
  - `tests/integration/persistence/d/test_persist_d_*.py`
  - `docs/delivery-evidence/persist-d/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `D-13`
- resourceLocks: `LOCK-SRC-CREATIVE`
- bindingRefs: `docs/parallel-delivery/bindings/b-d-production-snapshot.json`, `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: Tạo gói `src/creative/persistence` (có `__init__.py`) cài `SnapshotRepository`, `AppendOnlyRepository` cùng các kho con (`AnalysisRepository`, `AngleSetRepository`, `ScriptRepository`, `PlanRepository`, `VariantValidationRepository`, `OutputMetadataRepository`, `InvocationRecordRepository`) và `ReceiptStore` của `src/creative/ports/repositories.py` trên bảng của migration `0015_creative` (production_snapshot, content_analysis, story_angle_set, story_angle, script_version, production_plan, variant_validation, output_metadata, ai_invocation_record, receipt), và `PostgresCreativeUnitOfWork(manager)` (`snapshots`, `analyses`, `angle_sets`, `scripts`, `plans`, `variant_validations`, `output_metadata`, `invocations`, `receipts`, `outbox`) chung giao dịch với `cp_outbox_events`. Ràng buộc: `snapshot_id` duy nhất và bất biến (`DuplicateSnapshotError`); `append(key, revision, record)` chỉ nhận `latest + 1`, sai thì `RevisionConflictError` của `controlplane.domain.concurrency`; id duy nhất theo `UNIQUE_ID_ATTRS` (`DuplicateRecordError`); receipt `(workspace_id, idempotency_key)` (`DuplicateReceiptError`); bảng lịch sử chặn UPDATE và DELETE.
    instrument: `test_persist_d_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, record đọc lại bằng record đã ghi, revision sai bị từ chối, UPDATE và DELETE bị từ chối, record cùng outbox cùng commit hoặc cùng rollback.
    counterexample: kho tạm thay PostgreSQL; ghi revision nhảy cóc; sửa snapshot đã ghi; hai receipt cùng khóa; record mất trường sau round-trip; tự thêm migration.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter D'"`

### PERSIST-E: Adapter PostgreSQL của voice (E)

- kind: work_package_slice
- ownedPaths:
  - `src/voice/persistence/**`
  - `tests/integration/persistence/e/test_persist_e_*.py`
  - `docs/delivery-evidence/persist-e/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `E-15`
- resourceLocks: `LOCK-SRC-VOICE`
- bindingRefs: `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`
- acceptance:
  - requirement: Tạo gói `src/voice/persistence` (có `__init__.py`) cài `OutputRepository` (`append`, `latest`, `revisions`) của `src/voice/ports/repositories.py` cho các `kind` mà file port khai (`KIND_VOICE`, `KIND_WORD_TIMING`; không thêm `kind` mới) trên bảng của migration `0016_voice` (processed_media, image_safety_assessment, voice_track, word_timing, timing_validation_report, tts_invocation_record, language_evidence, audio_bed_result, probe_report, analysis_result, receipt), và `PostgresVoiceUnitOfWork(manager)` (`outputs`, `outbox`) thỏa `VoiceUnitOfWork` (`src/voice/application/voice_pipeline.py`) và `MediaUnitOfWork` (`src/voice/application/media_pipeline.py`), chung giao dịch với `cp_outbox_events`. Ràng buộc: `voice_hash` duy nhất và `timing_artifact_ref` duy nhất (`DuplicateOutputError`); revision tăng đúng một (`RevisionConflictError`); bảng lịch sử append-only.
    instrument: `test_persist_e_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip `VoiceTrack` và `WordTimingRecord`, hai unique, UPDATE và DELETE bị từ chối, output cùng outbox cùng commit hoặc cùng rollback.
    counterexample: kho tạm thay PostgreSQL; hai voice cùng `voice_hash`; hai timing cùng `timing_artifact_ref`; thêm `kind` ngoài file port; revision nhảy cóc; tự thêm migration.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter E'"`

### PERSIST-F: Adapter PostgreSQL của render (F)

- kind: work_package_slice
- ownedPaths:
  - `src/render/persistence/**`
  - `tests/integration/persistence/f/test_persist_f_*.py`
  - `docs/delivery-evidence/persist-f/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `F-16`
- resourceLocks: `LOCK-SRC-RENDER`
- bindingRefs: `docs/parallel-delivery/bindings/f-render-package.json`, `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- acceptance:
  - requirement: Tạo gói `src/render/persistence` (có `__init__.py`) cài `RenderRepository` (`append`, `latest`, `revisions`) của `src/render/ports/repositories.py` cho `KIND_PACKAGE`, `KIND_ATTEMPT`, `KIND_QUALITY_REPORT` theo `RECORD_TYPES`, trên bảng của migration `0017_render` (render_preset_revision, render_package, package_validation_report, render_attempt, quality_report, quality_gate_result, video_output, operation_receipt), và `PostgresRenderUnitOfWork(manager)` (`renders`, `outbox`, `reports`, `receipts`, `traces`, `attempt_index`) thỏa `PackageUnitOfWork` (`src/render/application/package_pipeline.py`) và `RenderUnitOfWork` (`src/render/application/render_video.py`), chung giao dịch với `cp_outbox_events`. Ràng buộc: `package_fingerprint` duy nhất và bất biến giữa các revision; `render_attempt_id` duy nhất; `output_artifact_ref` duy nhất giữa các attempt và bất biến trong một attempt (`DuplicateRecordError`, `ImmutableFieldError`); khóa package bằng `render_package_id`, khóa attempt bằng `render_attempt_id`; bảng lịch sử append-only.
    instrument: `test_persist_f_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip package, attempt và quality report, ba unique, hai lỗi bất biến, record cùng outbox cùng commit hoặc cùng rollback.
    counterexample: kho tạm thay PostgreSQL; đổi `package_fingerprint` giữa revision; hai attempt cùng `output_artifact_ref`; khóa package khác `render_package_id`; UPDATE vào bảng append-only; tự thêm migration.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); assert fs and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and 'from src.' not in t, 'adapter F'"`

### PERSIST-G: Adapter PostgreSQL của orchestration (G)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/orchestration/**`
  - `tests/integration/persistence/g/test_persist_g_*.py`
  - `docs/delivery-evidence/persist-g/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `G-10`
- resourceLocks: `LOCK-SRC-ORCHESTRATION`
- bindingRefs: `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: Mở rộng, không viết lại, `PostgresOrchestrationRepository` (`src/controlplane/infrastructure/db/orchestration/__init__.py`) và `start_batch.py`; thêm kho PostgreSQL nhận `connection` của caller cho `GrantStorePort` và `RecoveryEpochPort` (`src/controlplane/application/orchestration/grant_issuance.py`), `AllocationStorePort` (`job_allocation.py`), `VariantRegistryPort` (`variant_reservation_flow.py`) trên bảng và cột của migration `0011_orchestration_extensions` (bảng grant; cột mới của `cp_stage_runs` và `cp_video_jobs`; trường CT-ORC-009 của `cp_completion_ledger`; receipt, cleanup eligibility, app session, lý do dừng batch). Ràng buộc: grant đơn điệu và duy nhất `(stage_run_id, generation)`, một lease hoạt động mỗi stage; `lock_batch` dùng `SELECT ... FOR UPDATE` trên dòng batch, hai kết nối song song cùng batch không vượt target; `recovery_epoch` là text, so bằng `str()` ở hai phía. Không tạo `postgres_completion.py` và không cài `CompletionStorePort` (thuộc `CP-5-COMPLETION`, BL-CV-11); không đổi chữ ký trong `commit_completion.py`.
    instrument: `test_persist_g_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip grant, hai kết nối song song vào `lock_batch`, `recovery_epoch` int và str cho cùng kết quả, rollback cùng outbox.
    counterexample: kho tạm thay PostgreSQL; hai grant cùng generation; vượt target khi hai kết nối song song; so `recovery_epoch` bằng số; tạo `postgres_completion.py`; viết lại adapter đã nghiệm thu.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'CREATE TABLE' not in t and 'ALTER TABLE' not in t and not (d / 'postgres_completion.py').exists(), 'adapter G'"`

### PERSIST-I: Adapter PostgreSQL của storage metadata (I)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/storage_meta/**`
  - `tests/integration/persistence/i/test_persist_i_*.py`
  - `docs/delivery-evidence/persist-i/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `I-04`
- resourceLocks: `LOCK-SRC-STORAGE`
- bindingRefs: `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`
- acceptance:
  - requirement: Mở rộng, không viết lại, `PostgresStorageMetaRepository` (`src/controlplane/infrastructure/db/storage_meta/__init__.py`) để cài đủ `StorageMetaRepository` (`src/controlplane/application/storage_meta/__init__.py`), `UploadReceiptPort` (`cloud_persist.py`: `get(operation_key)`, `save(receipt)`) và `ArtifactVersionCatalogPort` (`declare_version.py`) trên bảng và cột của migration `0010_storage_meta_extensions` (`cp_artifact_versions` thêm `intended_storage_class`, `producer_operation_ref`, `lineage_refs`; upload receipt có `OUTCOME_UNKNOWN`; lease materialization; revision placement và working set policy; trường CT-STO-002 của `cp_artifact_locations`; `cp_cleanup_authorizations.recovery_epoch` là text). Ràng buộc: giữ trigger bất biến của `cp_artifact_versions` và `cp_cleanup_authorizations` (migration `0005`); khai báo lặp cùng `(workspace_id, artifact_id, sha256_hash)` trả bản cũ; upload receipt duy nhất theo `operation_key`; `recovery_epoch` so bằng `str()`. `CloudObjectPort` không có adapter PostgreSQL.
    instrument: `test_persist_i_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip version, location và upload receipt `OUTCOME_UNKNOWN`, UPDATE và DELETE trên version và authorization bị từ chối, `recovery_epoch` kiểu text, rollback cùng outbox.
    counterexample: kho tạm thay PostgreSQL; sửa được `cp_artifact_versions` sau khi ghi; hai upload receipt cùng `operation_key`; `recovery_epoch` còn là số; viết lại adapter đã nghiệm thu; tự thêm migration.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'CREATE TABLE' not in t and 'ALTER TABLE' not in t, 'adapter I'"`

### PERSIST-J: Adapter PostgreSQL của config và security (J)

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/config_security/**`
  - `tests/integration/persistence/j/test_persist_j_*.py`
  - `docs/delivery-evidence/persist-j/report.md`
- dependsOn: `CP-3-MIGRATIONS`, `J-09`, `J-18`
- resourceLocks: `LOCK-SRC-CONFIG-SECURITY`
- bindingRefs: `docs/parallel-delivery/bindings/j-provider-route.json`, `docs/parallel-delivery/bindings/domain-event-envelope.json`
- acceptance:
  - requirement: Mở rộng, không viết lại, `PostgresConfigSecurityRepository` và `PostgresConfigEventSink` (`src/controlplane/infrastructure/db/config_security/__init__.py`) để cài `ReservationStorePort` (`capacity_reservation.py`), `CostLedgerPort` (`routed_invocation.py`), `ReceiptStorePort` (`account_test.py`) và `AuditSinkPort` (`src/controlplane/domain/config_security/audit_record.py`) trên bảng và cột của migration `0009_config_security_extensions` (`cp_external_accounts`, `cp_provider_capacity_snapshots`, `cp_capacity_reservations` có expiry, `cp_cost_records`, `cp_audit_records` append-only, credential version và revocation version của `cp_secret_handles`, CHECK `scope_kind`). F1 của IMPL-PLAN-J: thêm phương thức đọc chọn cột `effective_at` (đã có từ `0004`) và dựng `EffectiveConfigRevision(revision, effective_at)` (`src/controlplane/application/config_security/bundle_resolution.py`) với `revision` là `ConfigRevision` chín trường không đổi và `effective_at` là `datetime` có múi giờ hoặc `None`; danh sách đó đưa thẳng vào `resolve_bundle`. Không có adapter PostgreSQL cho `SecretStorePort`; PostgreSQL không bao giờ giữ giá trị bí mật.
    instrument: `test_persist_j_postgres.py` theo mẫu plan.md mục 4 (PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test, `MigrationRunner` tới 18): đối chiếu bảng bằng `information_schema`, round-trip reservation, cost record, audit record và account test receipt, UPDATE và DELETE trên `cp_audit_records` bị từ chối, gọi `resolve_bundle` với danh sách đọc từ PostgreSQL và so kết quả với `effective_at` đã ghi.
    counterexample: kho tạm thay PostgreSQL; truyền `ConfigRevision` thẳng vào `resolve_bundle`; bỏ `effective_at`; `effective_at` ngây thơ; sửa được `cp_audit_records`; lưu giá trị bí mật vào cơ sở dữ liệu; tự thêm migration.
- testCommands:
  - `git diff --check`
  - `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider`
  - `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf-8') for f in d.rglob('*.py')); assert 'EffectiveConfigRevision' in t and 'CREATE TABLE' not in t and 'ALTER TABLE' not in t, 'adapter J'"`
