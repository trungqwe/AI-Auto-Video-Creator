# Đóng Băng Hợp Đồng Giao Tiếp: M7-INTEGRATION (Contract Freeze Specification)

> **Mã gói (Package ID):** `M7-INTEGRATION` (Chuyển tiếp từ `M7-INTEGRATION-TEMPLATE`)
> **Milestone liên quan:** `M7` — Tự động hóa lô, hardening và baseline vận hành (`R5 Unattended Beta` & `R6 Operational Baseline`)
> **Trạng thái đóng băng:** `frozen_design_baseline`
> **Thẩm quyền quy định:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **Ràng buộc bất biến:** Bắt buộc khớp chính xác mã băm SHA-256 nguồn; sai mã băm hoặc sai nguồn định nghĩa phải fail-closed.

---

## 1. Nguyên Tắc Đóng Băng Hợp Đồng (Contract Freeze Principles)

1. **Khóa bất biến (Immutable Baseline):** Mọi công việc chuẩn bị, tích hợp toàn diện và kiểm định hệ thống của Milestone M7 (kết nối toàn bộ 10 phân hệ A..J với các phân hệ trụ cột G, H, I, J) bắt buộc phải dựa trên đúng các phiên bản hợp đồng đã được đóng băng dưới đây.
2. **Fail-Closed khi sai lệch:** Nếu phát hiện mã băm tệp nguồn thực tế khác với mã băm đã đóng băng, toàn bộ chu trình kiểm thử và tích hợp phải dừng ngay lập tức (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **Cấm sửa tệp nguồn hợp đồng:** Nghiêm cấm mọi sửa đổi đối với các tệp nguồn trong `docs/09-contracts/**` trong phạm vi của gói này (`LOCK-CONTRACT-SOURCE`). Mọi đề xuất thay đổi hợp đồng phải thông qua quy trình RFC / ADR kiến trúc cấp cao.
4. **Không suy diễn quyền thực thi mã nguồn:** Việc đóng băng tài liệu thiết kế không cấp quyền chỉnh sửa mã nguồn sản phẩm (`src/**`) hoặc migration cơ sở dữ liệu (`migrations/**`). Quyền thực thi chỉ được kích hoạt sau khi có User Checkpoint chính thức mở Milestone M7.

---

## 2. Bảng Đóng Băng Các Hợp Đồng Toàn Cục (Exact Frozen Contract Revisions)

| Mã Hợp Đồng (Contract ID) | Tệp Nguồn Định Nghĩa (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-CONTROL-API-STREAM` | `docs/09-contracts/01-control-api-and-stream.md` | `CT-API-*` | H | `ea16fe04759e6bdf3b7bdde3e27ad498d13a271bd45d412ba0e9068a9b918e12` |
| `CONTRACT-DOMAIN-EVENTS` | `docs/09-contracts/02-domain-events.md` | `CT-EVT-*` | G | `8114a208cecca67e553345ea5574d68752323c79cf833c8c8c9fa5e2f86e7540` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-SOURCE-CONTENT` | `docs/09-contracts/04-source-content-contracts.md` | `CT-SRC-*`, `CT-CNT-*` | A (Co-owner: B) | `61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31` |
| `CONTRACT-CONTENT-MEDIA` | `docs/09-contracts/05-content-media-contracts.md` | `CT-MED-*`, `CT-HOOK-*` | C (Co-owners: B, I) | `ea6a3723dece842d132f634d44c32eb301fbc98b43b61d24b5c32c907782e4cf` |
| `CONTRACT-CREATIVE-AI` | `docs/09-contracts/06-creative-ai-contracts.md` | `CT-AI-*` (loại trừ `CT-AI-ROUTE-*`) | D | `92b74489890f1eaf3915aef809af4cff0585659842f6930bbdf11d1236861b3a` |
| `CONTRACT-MEDIA-PROCESSING` | `docs/09-contracts/07-media-processing-contracts.md` | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*` | E (Co-owners: C, I) | `c5f7abaea422916165d59f8a5508817729d21035cffd663123a913c49365cf49` |
| `CONTRACT-RENDER-QUALITY` | `docs/09-contracts/08-render-quality-contracts.md` | `CT-RND-*`, `CT-QC-*` | F (Caller: G, Artifact owner: I) | `c3e35d032c0a8e721ed35bbecb5fb57f350788e8520d6e8df5ca78284199b493` |
| `CONTRACT-ORCHESTRATION` | `docs/09-contracts/09-orchestration-contracts.md` | `CT-ORC-*` | G | `402f499f2ac2613502684f1d89697cf72d0cc136b25f2fd08fae07a7c1baaf59` |
| `CONTRACT-STORAGE` | `docs/09-contracts/10-storage-contracts.md` | `CT-STO-*` | I | `6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-ACC-*`, `CT-AI-ROUTE-*`, `CT-CAP-*`, `CT-COST-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | G (Co-owners: C, D, I) | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |

---

## 3. Chi Tiết Giao Diện Điều Phối & Workflow Lô (Phân Hệ G)

### 3.1. Hợp đồng Workflow & Thực thi (CONTRACT-WORKFLOW-EXECUTION)
- **`CT-WF-001` (Các workflow logic):** Định nghĩa 6 workflow logic cốt lõi:
  1. `DailyCollectionWorkflow`: Thu thập tin định kỳ theo Tier và ngưỡng chủ đề, chạy độc lập trên Cloud khi desktop tắt.
  2. `ContentEnrichmentWorkflow`: Chuẩn hóa, khử trùng, gom cụm sự kiện và chuẩn bị media/index (Cloud + fallback local).
  3. `ProductionBatchWorkflow`: Điều phối sản xuất lô video tự động theo chỉ tiêu user đặt (Cloud control, child jobs chờ desktop).
  4. `VideoProductionWorkflow`: Child workflow sản xuất 1 video từ snapshot đến hoàn thành (cô lập độc lập, lỗi 1 video không làm hỏng batch).
  5. `DebugStageWorkflow`: Chạy một stage đơn lẻ có quan sát, `auto_advance=false`, phục vụ gỡ lỗi và kiểm thử.
  6. `MaintenanceWorkflow`: Đối soát artifact, dọn dẹp cache/staging, kiểm tra quota và diễn tập backup/restore.
- **`CT-WF-002` (Capability routing):** Định tuyến công việc theo hàng đợi năng lực logic (`control-workflows`, `cloud-io`, `cloud-ai`, `desktop-cpu`, `desktop-gpu`, `desktop-render`). Tên queue vật lý là cấu hình; capability và retry policy phân tách logic.
- **`CT-WF-003` (`ActivityRequest`):** Lệnh thực thi activity mang đầy đủ context: `workflow_id`, `workflow_run_id`, `video_job_id`, `stage_run_id`, `activity_name`, `activity_version`, `execution_grant` (bắt buộc với side effect/commit), `input_refs` (bất biến), `operation_key` (khóa idempotency), `deadline_at`, `capability_requirements`, `retry_policy_ref`. Payload không chứa blob hoặc secret.
- **`CT-WF-004` (`ExecutionGrant`):** Cấp quyền thực thi có fencing: `grant_id`, `stage_run_id`, `execution_generation`, `recovery_epoch`, `worker_lease_id`, `issued_at`, `expires_at`, `allowed_operation`, `input_fingerprint`. Kết quả từ worker generation cũ bị từ chối với `STALE_EXECUTION_GENERATION` (`INV-003`); kết quả từ epoch cũ trả `STALE_RECOVERY_EPOCH` (`INV-016`).
- **`CT-WF-005` (`OperationReceipt`):** Biên lai thực thi idempotency cho side effect: `operation_key`, `operation_type`, `input_fingerprint`, `recovery_epoch`, `state`, `external_operation_ref`, `output_refs`, `attempt`, `problem`. Trả lại output cũ nếu `succeeded`; reconcile trước nếu `outcome_unknown`; tạo attempt mới cùng key nếu `failed` & retryable.
- **`CT-WF-006` (`ActivityResult`):** Kết quả activity mang fencing identity (`stage_run_id`, `grant_id`, `execution_generation`, `recovery_epoch`), `disposition` (`succeeded`, `failed`, `waiting`, `outcome_unknown`, `stale`), `output_refs`, `metrics`, `warnings`, `problem`, `operation_receipt_ref`, `completed_at`. Workflow chỉ chuyển stage thành `SUCCEEDED` sau khi owner xác nhận commit output.
- **`CT-WF-007` (Quy tắc sống còn):** Heartbeat báo tiến độ và checkpoint kỹ thuật; timeout schedule-to-start phản ánh thiếu capability; khi desktop/provider offline, stage chuyển `WAITING_CAPABILITY`; tuân thủ R18: stage tạo script, production plan và voice chỉ bắt đầu khi desktop production capability đang hoạt động; desktop offline trong 5 phút không hủy workflow mà tự động tiếp tục khi reconnect; timeout start-to-close và heartbeat cấu hình riêng theo activity.
- **`CT-WF-008` (Ba ngữ nghĩa khác nhau):** Phân định nghiêm ngặt 3 hành động:
  1. `Retry kỹ thuật`: Giữ nguyên job, snapshot, intent, fingerprint; tạo attempt mới; không tính là video mới.
  2. `Tạo lại từ stage` (`RegenerateFromStage`): Giữ job, snapshot, intent; tạo revision downstream mới; vô hiệu hóa refs cũ.
  3. `Tạo biến thể mới` (`CreateNewVariant`): Tạo `video_job_id` mới; dùng cùng nguồn nhưng snapshot job mới; intent mới; tạo script/plan/output mới.
- **`CT-WF-009` (Tương thích khi triển khai):** Versioning workflow: Workflow đang chạy tiếp tục theo version logic đã ghi; activity result có version riêng; đảm bảo replay history compatibility qua các bản cập nhật mà không gây lỗi Non-Deterministic Error (`Gate G01`).

### 3.2. Hợp đồng Điều Phối Sản Xuất Lô & Biến Thể (CONTRACT-ORCHESTRATION)
- **`CT-ORC-001` (`StartProductionBatch`):** Tiếp nhận chỉ tiêu sản xuất (`target_completed_videos`), phạm vi chủ đề (topic scope), revision chính sách/cấu hình, chế độ thực thi (`auto` / `debug`), app session ref, cost/capacity constraints, và khóa idempotency duy nhất. Trả về batch ID/revision, accepted operation, effective policy refs.
- **`CT-ORC-002` (`AllocateVideoJob`):** Phân bổ video job từ bài viết/sự kiện candidate đủ điều kiện. Khóa batch và tạo `BatchCapacityReservation` trong cùng transaction. Chỉ cấp job khi `completed_count + active_capacity_reservations < target_completed_videos` (`INV-018`). Mỗi sự kiện/tin trong một lượt chỉ tạo 1-3 job và phải khác góc kể (`INV-013`).
- **`CT-ORC-003` (`StageRun`):** Quản lý lần chạy stage: `stage_run_id`, `stage_type`, `job_id`, `input_refs`, `state` (theo state machine), `attempt`, `execution_generation`, `dependency_refs`, `output_refs`, `wait_reason`, `problem`. G chỉ đánh dấu stage succeeded khi owner xác nhận commit output và grant hợp lệ.
- **`CT-ORC-004` (`RunDebugStage`):** Thực thi một module stage đơn lẻ có quan sát, bắt buộc `auto_advance=false`, dùng cùng schema/validation với auto pipeline. Không tự động đi tiếp stage sau và không tạo production completion trừ khi có lệnh riêng.
- **`CT-ORC-005` (`RetryStage`):** Thử lại kỹ thuật giữ nguyên `video_job_id`, snapshot, intent và input fingerprint; tăng attempt và execution generation; không tăng completed count.
- **`CT-ORC-006` (`CreateNewVariant`):** Tạo `video_job_id` mới với intent mới; D bắt buộc validate quy tắc khác biệt; chỉ sau completion mới ghi media usage và tính vào target lô.
- **`CT-ORC-007` (`SetJobWaiting`):** Thiết lập lý do chờ có cấu trúc: `desktop_offline`, `local_ai_unavailable`, `provider_unavailable`, `quota_wait`, `artifact_not_ready`, `insufficient_disk`, `dependency_wait`, `credential_unavailable`. Tuân thủ R18: không bắt đầu script/plan/voice khi desktop capability chưa hoạt động.
- **`CT-ORC-008` (`CommitVideoCompletion`):** Transaction nguyên tử 8 bước hoàn tất video: (1) kiểm tra job; (2) kiểm tra revision/hash/grant/epoch, khóa registry revision theo CT-ORC-012, kiểm tra validation; (3) tạo `CompletionLedger` duy nhất; (4) đánh job completed; (5) chuyển capacity reservation thành completion, chuyển `VariantReservation` thành `CONVERTED`, tăng registry revision và completed count đúng 1 lần; (6) gọi Unit of Work của C ghi `MediaUsage`; (7) phát outbox `VideoCompleted`; (8) tạo cleanup eligibility.
- **`CT-ORC-009` (`CompletionLedger`):** Sổ cái hoàn thành video duy nhất: completion ID, job/batch/session refs, video output artifact/hash/cloud location, QualityReport, variant validation, media usage manifest, completed time, output naming metadata, cost summary, cleanup policy ref (`INV-010`, `INV-017`).
- **`CT-ORC-010` (Lý do dừng lô):** Định nghĩa tường minh 4 lý do dừng: `COMPLETED_TARGET` (đạt chỉ tiêu target), `COMPLETED_EXHAUSTED` (hết candidate đủ điều kiện), `WAITING_CAPABILITY` (chờ năng lực thiếu), `FAILED_SYSTEM` (lỗi điều phối/hạ tầng nghiêm trọng). Video đơn lẻ lỗi không làm dừng toàn bộ batch.
- **`CT-ORC-011` (`AppSession`):** Phiên ứng dụng bật/tắt: session ID, start/end time, desktop identity, log scope, output folder `YY-MM-DD`, `YY-MM-DD (1)` khi có video hoàn thành hợp lệ. Restart app không reset batch/job checkpoint.
- **`CT-ORC-012` (`ReserveVariant` / `ReleaseVariant`):** Giữ chỗ nội dung biến thể độc lập với capacity reservation. Sổ đối soát biến thể do G quản lý với revision workspace compare-and-swap; D đối chiếu chữ ký thực tế của script/voice/media/timeline/output với active reservations và lịch sử; trạng thái `ACTIVE` giữ nguyên khi chờ/offline, chuyển `CONVERTED` khi completion hoặc `RELEASED` khi lỗi/hủy (`INV-014`).

---

## 4. Chi Tiết Giao Diện Điều Khiển, Sự Kiện & Lưu Trữ (Phân Hệ H & I)

### 4.1. Hợp đồng Điều Khiển & Luồng Cập Nhật (CONTRACT-CONTROL-API-STREAM & CONTRACT-BATCHES-QUERY)
- **`CT-API-001` (Quy tắc request HTTP):** Base path có version `/v1`; mutation bắt buộc mang `Idempotency-Key` (`INV-001`); metadata update bắt buộc `If-Match` hoặc `expected_revision`; mọi request authenticate và ràng buộc vào `workspace_id`; response mang `correlation_id`; lệnh async trả `202 Accepted`; xung đột trả `409 Conflict`; lỗi trả chuẩn RFC 7807 `ProblemDetail`.
- **`CT-API-002` (Danh mục query):** Danh mục query 13 tài nguyên logic: Sources, Articles, Events, Media, Hooks, Batches, Jobs, Stage runs, Sessions, Logs, Configuration, Capabilities, Operations. Query không tự động download thêm nguồn hay materialize nặng lên desktop.
- **`CT-API-003` (Quản lý nguồn):** Command `RegisterSource` (kiểm tra an toàn URL), `UpdateSourceMetadata` (Tier, topic/tag, toggle), `RemoveSource` (tombstone revision, ngừng thu thập, không tự thêm lại `INV-015`), `RestoreSource`, `TestSource`.
- **`CT-API-004` (Quản lý hook và media):** Command `ImportVisualHook` (video hook mờ), `ImportAudioHook`, `UpdateHookMetadata`, `UpdateMediaMetadata`. Không có command sửa byte bản gốc tại chỗ; bản xử lý là artifact version mới.
- **`CT-API-005` (Sản xuất và debug):** Command `StartProductionBatch` (user đặt target videos và cấu hình lô), `RunDebugStage` (chạy 1 module, `auto_advance=false`), `RetryStage` (cùng job/snapshot, attempt mới, giữ input logic), `CreateNewVariant` (job mới, intent mới, đạt quy tắc khác biệt), `RegenerateFromStage` (tạo revision đầu ra mới, giữ output cũ để audit).
- **`CT-API-006` (Cấu hình và tài khoản ngoài):** Command `PublishConfigurationRevision` (áp dụng cho job chưa bắt đầu tạo script), `UpdateSecret` (chỉ đi vào secret boundary, không trả lại secret), `TestExternalAccount` (kết quả đã redacted), `EnableExternalAccount`, `DisableExternalAccount`.
- **`CT-API-007` (`OperationView`):** Theo dõi command bất đồng bộ: `operation_id`, `command_ref`, `status` (`accepted`, `running`, `waiting`, `outcome_unknown`, `succeeded`, `failed`), `progress`, `resource_refs`, `wait_reason`, `problem`.
- **`CT-API-008` (`OperationStream`):** Endpoint SSE `GET /v1/operations/stream?cursor=...`. Mỗi item có `stream_event_id` duy nhất, `cursor` tăng dần, `event_kind`, `summary` an toàn, `correlation_id`. Client reconnect bằng cursor; deduplicate theo `stream_event_id`; query lại snapshot khi cursor hết hạn retention.
- **`CT-API-009` (Sửa khi lô đang chạy):** Metadata/config revision mới chỉ áp dụng cho video chưa bắt đầu tạo script; job đã snapshot giữ nguyên revision cũ; sửa đồng thời trả `REVISION_CONFLICT`.
- **`CT-API-010` (Bảo mật biên UI):** Local UI dùng HTTPS / loopback Origin (`localhost / 127.0.0.1`), chống CSRF, escape nội dung nguồn ngoài, secret đã lưu chỉ hiển thị metadata và không bao giờ rò rỉ secret ra UI, log có audit actor (`INV-012`).
- Kèm **`CONTRACT-BATCHES-QUERY`** (`CT-BAT-001..004`):
  - `CT-BAT-001` (`list_batches`): `GET /api/v1/batches` tra cứu danh sách batch kèm phân trang và lọc status.
  - `CT-BAT-002` (`batch_detail`): `GET /api/v1/batches/{batch_id}` chi tiết batch, tiến độ từng job và `capacity_reservation` ({total_slots, allocated_slots}).
  - `CT-BAT-003` (`filter_batches`): Bộ lọc nâng cao (date_range, status_in, priority_min, has_errors).
  - `CT-BAT-004` (`paginate_batches`): Quy chuẩn phân trang offset/limit (max_limit 100, default_limit 20).

### 4.2. Hợp đồng Sự Kiện Nghiệp Vụ (CONTRACT-DOMAIN-EVENTS)
- **`CT-EVT-001` (Delivery contract):** Chuyển phát at-least-once qua transactional outbox; ghi cùng transaction với thay đổi nghiệp vụ; thứ tự bảo đảm theo aggregate và `aggregate_revision`; consumer bắt buộc idempotent và lưu checkpoint outbox deduplication (`INV-002`).
- **`CT-EVT-002` (`DomainEvent`):** Envelope chuẩn gồm: `event_id` (duy nhất, bất biến), `event_name` (thì quá khứ), `aggregate_type`, `aggregate_id`, `aggregate_revision`, `producer`, `schema_version`, `recovery_epoch`, `payload`, `sensitivity`. Tuyệt đối không chứa blob, secret, raw OAuth token, long signed URL hay log stack trace (`INV-012`).
- **`CT-EVT-003` (Payload policy):** Mang ID và revision của đối tượng thay đổi; dùng `ResourceRef` / `ArtifactRef` cho dữ liệu lớn; field mới phải optional với consumer cũ; enum là open set; event đã phát không được sửa tại chỗ (sửa bằng event hiệu chỉnh mới).
- **`CT-EVT-004` (Subscription policy):** Event chỉ thông báo thay đổi đã diễn ra, không tự trao quyền sửa aggregate khác; consumer muốn thay đổi phải gửi command về owner; UI projection H rebuild từ dữ liệu owner và event checkpoint; mapping lỗi an toàn trước khi hiển thị.
- **`CT-EVT-005` (Recovery policy):** Xử lý gap bằng cách tạm dừng và query snapshot; event lặp deduplicate qua outbox checkpoint (`INV-002`); schema không hợp lệ đưa vào dead-letter/quarantine; replay kiểm tra receipt cũ; sau restore, event từ epoch cũ bị quarantine và không được mutation trực tiếp (`INV-016`).
- **Catalog sự kiện chuẩn 10 phân hệ A..J:**
  - Phân hệ A: `SourceRegistered`, `SourceMetadataUpdated`, `SourceRemoved`, `SourceRestored`, `SourceCandidateDiscovered`, `SourceCandidateResolved`, `CollectionRunStarted`, `CollectedDocumentAvailable`, `CollectionRunCompleted`, `CollectionRunFailed`.
  - Phân hệ B: `ArticleRevisionAccepted`, `DuplicateDocumentResolved`, `EventLinkResolved`, `EventUpdateAccepted`.
  - Phân hệ C: `MediaDiscovered`, `MediaCataloged`, `MediaAnalysisAccepted`, `MediaRenditionReady`, `MediaAvailabilityChanged`, `HookImported`, `HookMetadataUpdated`, `HookEnabled`, `HookDisabled`.
  - Phân hệ D: `ProductionSnapshotCommitted`, `StoryAnglesGenerated`, `ScriptVersionCreated`, `ProductionPlanCreated`, `VariantValidated`, `OutputMetadataCreated`.
  - Phân hệ E: `ImageSafetyAssessed`, `MediaProcessingCompleted`, `VoiceReady`, `WordTimingReady`.
  - Phân hệ F: `RenderCompleted`, `OutputQualityChecked`.
  - Phân hệ G: `BatchStarted`, `JobAllocated`, `StageStateChanged`, `JobWaiting`, `JobFailed`, `VideoCompleted`, `BatchTargetReached`, `BatchExhausted`.
  - Phân hệ I: `ArtifactLocationVerified`, `CleanupAuthorized`, `CleanupCompleted`, `StorageHealthChanged`.
  - Phân hệ J: `ConfigurationRevisionPublished`, `ProviderHealthChanged`, `QuotaObserved`, `CredentialChanged`.

### 4.3. Hợp đồng Lưu Trữ & Đồng Bộ Hybrid (CONTRACT-STORAGE)
- **`CT-STO-001` (`DeclareArtifactVersion`):** Khai báo artifact kind, content hash SHA-256, size, media type, lineage, retention class, storage class, idempotent version mapping. Cùng byte và policy quy về version hiện có; byte khác luôn tạo version mới, không ghi đè.
- **`CT-STO-002` (`RegisterArtifactLocation`):** Đăng ký vị trí vật lý trên cloud hoặc local staging/cache, provider object ID, logical path, observed hash/size, state, last verified time, lease. Không đưa raw credential vào location.
- **`CT-STO-003` (`PersistArtifactToCloud`):** Tải lên và xác minh cloud với operation receipt, retry idempotent; timeout chuyển `OUTCOME_UNKNOWN` để đối soát; bắt buộc verify object tồn tại và kiểm chứng checksum/integrity trước khi phát `ArtifactLocationVerified` (`Gate G04`).
- **`CT-STO-004` (`MaterializeArtifactSet`):** Tải artifact set xuống desktop staging; giới hạn working set tối đa cho 5 video làm việc gần nhất; chỉ render trên location đã verify hash; không dùng path ngoài staging root.
- **`CT-STO-005` (`LocalJournalEntry`):** Sổ nhật ký SQLite cục bộ ghi nhận device, session, job, stage, generation, lease, hash, recovery epoch; hỗ trợ phục hồi sau sự cố crash mà không vi phạm nguồn sự thật PostgreSQL/Cloud.
- **`CT-STO-006` (`PersistVideoOutput`):** Đồng bộ video đầu ra MP4 lên Google Drive bền vững, đối chiếu hash, metadata đặt tên file; G chỉ commit completion sau khi có xác nhận này.
- **`CT-STO-007` (`RequestCleanupEvaluation`):** Đánh giá điều kiện dọn dẹp local artifact (`eligible`, `deferred`, `forbidden`) dựa trên ledger, retention, active lease và recovery epoch.
- **`CT-STO-008` (`CleanupAuthorization`):** Cấp phép dọn dẹp bất biến với 5 điều kiện an toàn: thuộc staging/cache được phép xóa, không có lease/consumer hoạt động, đã verify trên cloud, cùng recovery epoch, resolved absolute path nằm trong staging root. Phát `CleanupCompleted` (`INV-011`).
- **`CT-STO-009` (`RecoveryEpoch`):** Tạo recovery epoch opaque mới sau mỗi lần restore/rebuild; cô lập toàn bộ command/result/event/cleanup từ epoch cũ; đối soát 6 chiều giữa DB, Cloud, Journal và Ledger (`INV-016`, `Gate G05`).
- **`CT-STO-010` (`StoragePlacementPolicy`):** Phân tầng lưu trữ Google Drive 4 tài khoản (20TB), định mức quota, phân vùng logic theo loại dữ liệu, fallback account, retention class.
- **`CT-STO-011` (`AllocateOutputPath`):** Chuẩn hóa tên file an toàn trên Windows và tạo thư mục xuất xưởng logic `YY-MM-DD`, `YY-MM-DD (1)` khi phiên `AppSession` có video hoàn thành hợp lệ.

---

## 5. Chi Tiết Quản Trị Cấu Hình, An Toàn & Chi Phí (Phân Hệ J)

### 5.1. Quản Trị Cấu Hình Có Phiên Bản (CONTRACT-CONFIG-SECURITY)
- **`CT-CFG-001` (`PublishConfigurationRevision`):** Xuất bản bản sửa đổi cấu hình bất biến theo scope (`workspace`, `module`, `provider`, `preset`, `policy`, `prompt`). Base revision là lineage bất biến trước đó. Job đã commit production snapshot giữ nguyên revision cũ (`INV-004`); job chưa bắt đầu tạo script có thể dùng revision mới.
- **`CT-CFG-002` (`ResolveConfigurationBundle`):** Hợp nhất cấu hình đã phân giải cho workflow/stage: exact revision refs, merged typed values, bundle fingerprint, provenance. Tuyệt đối không trả secret value trong bundle.

### 5.2. Bí Mật & Thông Số Xác Thực (CONTRACT-CONFIG-SECURITY)
- **`CT-SEC-001` (`UpdateSecret`):** Cập nhật secret qua kênh bảo vệ vào secret store; response chỉ gồm metadata/alias/fingerprint đã che giấu. Tuyệt đối không có API đọc lại secret value (`INV-012`).
- **`CT-SEC-002` (`IssueShortLivedCredential`):** Cấp phát credential ngắn hạn có phạm vi và thời hạn cho desktop/worker; không lưu Google Drive refresh token dài hạn trên desktop; không đưa credential vào Temporal history, event, trace, log, prompt hoặc error detail.
- **`CT-SEC-003` (Trust rules):** Ranh giới tin cậy: mọi caller được xác thực và ràng buộc workspace; URL ngoài qua SSRF validation; nội dung ngoài không đưa trực tiếp vào shell (`INV-020`); error/log redaction trước khi lưu trữ và stream; credential bị revoke có hiệu lực cao hơn snapshot cũ.
- **`CT-SEC-004` (`AuditRecord`):** Ghi nhật ký kiểm toán bất biến cho mọi thao tác nhạy cảm (cấu hình, secret, nguồn, debug/retry, cleanup/recovery); lưu actor, correlation, action, redacted reason; không chứa secret value.

### 5.3. Quản Trị Tài Khoản, Định Tuyến, Năng Lực & Chi Phí
- **`CT-ACC-001` (`ExternalAccountView`):** Quản lý metadata tài khoản provider bên ngoài: identity, provider, account_label, status, capabilities, quota_observation_ref, health (đã redacted credential).
- **`CT-ACC-002` (`TestExternalAccount`):** Kiểm thử tài khoản với request nhỏ nhất cần thiết và trả kết quả đã redacted; không tự bật account hay đổi routing.
- **`CT-AI-ROUTE-001` (`ResolveProviderRoute`):** Định tuyến provider/model/account theo vai trò AI, snapshot/config, độ nhạy cảm dữ liệu, ràng buộc chất lượng/chi phí và quota domain thực tế.
- **`CT-AI-ROUTE-002` (Fallback):** Xử lý chuyển đổi dự phòng: việc không cần AI vẫn chạy khi AI unavailable; stage AI chờ phục hồi hoặc fallback local; không tự ý thêm dịch vụ trả phí; fallback thay model phải ghi model/config revision.
- **`CT-CAP-001` (`ProviderCapacitySnapshot`):** Ghi nhận giới hạn quota quan sát được, usage, reset window, rate-limit state theo provider/model/account; không suy đoán quota đơn thuần từ số tài khoản.
- **`CT-CAP-002` (`ReserveProviderCapacity`):** Giữ chỗ năng lực dự kiến trước khi điều phối tác vụ; xử lý rate limit bằng waiting/backoff, không tạo retry storm.
- **`CT-CAP-003` (`CapabilityView`):** Hình chiếu sức khỏe năng lực hệ thống (cloud/desktop/provider, status, capacity indicators) phục vụ điều phối waiting/resume.
- **`CT-COST-001` (`RecordIncrementalCost`):** Ghi nhận chi phí phát sinh thực tế cho dự án (API trả thêm, nền, lưu trữ bổ sung) vào `CostLedger`; đối soát ngưỡng dự báo 80% ngân sách và trần chi phí gia tăng dưới 50 USD/tháng (`Gate G03`, `R24`).

---

## 6. Toàn Cảnh Ranh Giới Giao Tiếp Tích Hợp Đa Phân Hệ

Quy trình tích hợp toàn diện của Milestone M7 kết nối liền mạch 10 phân hệ theo một đường ống dữ liệu xác định:

```
[A: Thu Thập Nguồn]
       │
       ▼ (CT-SRC-001..006 / RawSourcePackage)
[B: Chuẩn Hóa & Sự Kiện]
       │
       ▼ (CT-CNT-001..004 / NormalizedContentSnapshot)
[D: Bộ Não AI & Kịch Bản] ◄── [C: Kho Media & Hook] (CT-MED-001..008)
       │
       ▼ (CT-AI-001..010 / ScriptAndProductionPlan)
[E: Media Processing & Voice]
       │ (CT-TTS-001, CT-SUB-001, CT-AUD-001 / AudioVoiceAndTiming)
       ▼
[F: Dựng Video & Kiểm Định QC] ◄── [LOCK-DESKTOP-GPU]
       │
       ▼ (CT-RND-001..006, CT-QC-001..002 / RenderOutput & QualityReport)
[I: Lưu Trữ Hybrid & Sync Drive]
       │
       ▼ (CT-STO-001..011 / CloudVerifiedArtifact)
[G: Điều Phối Lô & Workflow Temporal] ◄── [J: Config, Security, Cost & Quota]
       │                                     (CT-CFG-*, CT-SEC-*, CT-COST-*)
       ▼
[H: Control API, SSE Stream & UI Dashboard] (CT-API-001..010, CT-BAT-001..004, CT-EVT-001..005)
```

1. **Ranh giới A -> B:** B nhận dữ liệu nguồn thô từ A, khử trùng lặp và phân tích thực thể.
2. **Ranh giới B -> D:** D tiếp nhận nội dung chuẩn hóa, phối hợp thông tin media từ C để lên cấu trúc kịch bản.
3. **Ranh giới D -> E:** E tiếp nhận kịch bản tiếng Anh và thông số timing dự kiến từ D để tổng hợp giọng nói và căn chỉnh nhịp từ (`WordTiming`).
4. **Ranh giới E -> F:** F tiếp nhận giọng đọc, tệp phụ đề karaoke và nhạc nền từ E, kết hợp với các media asset từ C để đóng gói `RenderPackage`.
5. **Ranh giới F -> I:** F xuất xưởng video MP4 và thumbnail JPEG, chuyển giao cho I để đưa vào phân tầng lưu trữ và đồng bộ hóa lên Google Drive.
6. **Ranh giới I -> G:** I xác nhận chứng chỉ toàn vẹn đám mây (`cloud_verified`) cho G để G ghi nhận hoàn thành vào sổ cái nguyên tử.
7. **Ranh giới G -> H:** G cập nhật tiến độ lô và trạng thái job cho H để đẩy ra màn hình giám sát thời gian thực qua kênh SSE.
8. **Ranh giới Xuyên suốt J -> Toàn hệ thống:** J cung cấp cấu hình bất biến, cấp phát tài khoản provider, kiểm soát hạn mức chi phí và bảo đảm không rò rỉ secret tại mọi điểm tiếp xúc.

---

## 7. Danh Mục Bất Biến Cốt Lõi M7 (INV-001..INV-020) & Máy Trạng Thái Toàn Cục

### 7.1. Bảng phân bổ 20 Bất biến cốt lõi (Invariants Matrix)

| ID | Tên Bất Biến | Ranh Giới Kiểm Soát | Hành Động Bắt Buộc Khi Vi Phạm |
|---|---|---|---|
| `INV-001` | Command lặp không tạo hai aggregate logic | H -> G (API / Engine) | Trả về receipt cũ, không tạo bản ghi mới |
| `INV-002` | Event lặp không tạo side-effect lặp | G, H, I (Event Consumer) | Bỏ qua sự kiện trùng lặp nhờ outbox deduplication |
| `INV-003` | Result generation cũ không được commit | Worker -> G (Execution) | Từ chối kết quả nộp muộn (Stale Generation Guard) |
| `INV-004` | Job đã snapshot không đổi nguồn/config | G -> D, J (Job Init) | Khóa bất biến cấu hình và nguồn tại thời điểm tạo job |
| `INV-005` | Bài viết trùng không tạo script mới | B -> D (Ingestion) | Khử trùng bài viết dựa trên URL và độ tương đồng ngữ nghĩa |
| `INV-006` | Timeline narrative cần EventUpdateAccepted | B -> D (Storytelling) | Chỉ cập nhật diễn biến khi sự kiện được thẩm định |
| `INV-007` | Word timing khớp 100% script và voice hash | E -> F (Voice to Render) | Chặn render nếu phụ đề lệch từ hoặc lệch mã băm âm thanh |
| `INV-008` | Render package chỉ chứa artifact đã verify | I, D, E -> F (Render Package)| Từ chối dựng hình nếu bất kỳ artifact nào thiếu SHA-256 |
| `INV-009` | QC pass chưa đủ hoàn thành nếu chưa sync Drive | F, I -> G (Completion Gate) | Chặn ghi nhận completed nếu tệp chưa verify trên Cloud |
| `INV-010` | Completion tăng target đúng một lần | G -> H (Batch Accounting) | Ghi nhận hoàn thành nguyên tử vào `CompletionLedger` |
| `INV-011` | Cleanup cần ledger, verify, lease check và đúng epoch | I, G (Storage Cleanup) | Cấm xóa tệp nếu chưa đủ 5 điều kiện an toàn |
| `INV-012` | Secret tuyệt đối không rò rỉ vào log/event/history | J -> Toàn hệ thống | Bộ lọc `RedactionFilter` thanh lọc toàn diện |
| `INV-013` | Cùng một lượt, 1-3 video khác góc kể | D -> G (Batch Round) | Đa dạng hóa góc nhìn (Angle Diversity) trong cùng đợt |
| `INV-014` | Giữa các lượt, biến thể khác ít nhất một yếu tố thực tế | D -> G (Cross-Round) | Ngăn ngừa trùng lặp video qua sổ đối chiếu biến thể |
| `INV-015` | Nguồn đã tombstone không bị tự động thêm lại | A -> G, H (Source Discovery)| Bỏ qua nguồn tin đã bị người dùng vô hiệu hóa |
| `INV-016` | Message/grant/result từ epoch cũ không được mutation | G, J, I (Disaster Recovery) | Cô lập hoàn toàn trạng thái thuộc epoch phục hồi cũ |
| `INV-017` | Completion ledger và MediaUsage cùng commit/rollback | G <-> C (2PC / Saga) | Đồng bộ nguyên tử giữa đếm sản phẩm và đếm lượt dùng media |
| `INV-018` | Completed count + active capacity không vượt target | G (Capacity Control) | Chặn phân bổ slot công việc nếu chạm trần target lô |
| `INV-019` | Output hoàn thành có bằng chứng tiếng Anh toàn trình | D, E, F -> G (English QC) | Xác minh ngôn ngữ tiếng Anh trên script, voice và phụ đề |
| `INV-020` | Dữ liệu nguồn không tin cậy không đổi policy / gọi tool | A, C -> D, J (Security Sandbox)| Làm sạch nội dung, chống Prompt Injection và Path Traversal |

### 7.2. Máy Trạng Thái Cốt Lõi Lô & Tác Vụ (Bound State Machines)
Toàn bộ quy trình M7 vận hành dựa trên máy trạng thái chuẩn quy định tại `CONTRACT-STATE-MACHINES`:
- `ProductionBatchState`: `created` -> `running` -> `reconciling` -> `completed` / `stopped_no_work` / `failed_budget_exceeded`.
- `VideoJobState`: `snapshot_locked` -> `script_generated` -> `voice_ready` -> `rendered` -> `qc_passed` -> `cloud_verified` -> `completed` (hoặc `failed_terminal`).
- `StageRunState`: `pending` -> `assigned` -> `running` -> `succeeded` / `failed` / `timed_out`.
- `StorageArtifactState`: `staged_local` -> `uploading` -> `cloud_verified` -> `retained_local` / `pruned_safely`.

---

## 8. Kết Luận Khóa Bất Biến

1. Bản đặc tả này đóng băng toàn diện 13 hợp đồng giao tiếp của hệ thống, xác lập ranh giới vận hành hoàn chỉnh cho Milestone M7.
2. Mọi hoạt động kiểm thử trong `docs/parallel-delivery/M7-integration-test-plan.md` và gói triển khai trong `docs/parallel-delivery/M7-integration-execution-package.md` bắt buộc phải tuân thủ nghiêm ngặt các mã băm hợp đồng và bất biến đã khóa ở trên.
3. Bất kỳ sai lệch nào về chữ ký hợp đồng hoặc mã băm tệp nguồn đều dẫn đến kết luận thất bại tức thì (`FAIL_CLOSED_CONTRACT_DRIFT`).
