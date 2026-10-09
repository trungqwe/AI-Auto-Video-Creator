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
- **`CT-WF-001` (Workflow Catalog):** Định nghĩa 6 workflow logic cốt lõi:
  1. `DailyCollectionWorkflow`: Thu thập tin định kỳ theo Tier và ngưỡng chủ đề (chạy trên Cloud khi Desktop tắt).
  2. `ContentEnrichmentWorkflow`: Chuẩn hóa, khử trùng, gom cụm sự kiện và chuẩn bị media (Cloud + fallback local).
  3. `ProductionBatchWorkflow`: Điều phối sản xuất lô video tự động theo chỉ tiêu user đặt (Cloud control, child jobs chờ desktop).
  4. `VideoProductionWorkflow`: Child workflow sản xuất 1 video từ snapshot đến hoàn thành (độc lập, lỗi 1 video không hỏng batch).
  5. `DebugStageWorkflow`: Thực thi một stage đơn lẻ có quan sát, phục vụ gỡ lỗi và kiểm thử.
  6. `MaintenanceWorkflow`: Khôi phục đối soát artifact, dọn dẹp bộ nhớ đệm, kiểm tra quota và diễn tập backup/restore.
- **`CT-WF-002` (Task Queue & Capability Routing):** Định tuyến công việc theo khả năng máy trạm: `cloud-lightweight`, `desktop-heavy-render`, `desktop-probe-transcode`.
- **`CT-WF-003` (Retry & Timeout Policy):** Retry có exponential backoff và jitter; timeout riêng biệt cho từng activity; phân biệt rõ lỗi tạm thời (retryable) và lỗi vĩnh viễn (non-retryable).
- **`CT-WF-004` (Desktop Reconnection):** Desktop offline trong vòng 5 phút không làm hủy workflow; workflow chuyển sang trạng thái chờ capability (`waiting_capability`) và tiếp tục ngay khi desktop kết nối lại mà không chạy lại từ đầu.
- **`CT-WF-005` (Fencing Token & Generation Guard):** Mỗi activity grant mang `execution_generation`. Worker thế hệ cũ bị trễ nhịp sẽ bị từ chối commit kết quả (`INV-003`, `INV-016`).
- **`CT-WF-006` (Replay History Compatibility):** Đảm bảo tính tương thích lịch sử workflow qua các phiên bản mã nguồn cập nhật mà không gây lỗi Non-Deterministic Error (`G01`).

### 3.2. Hợp đồng Điều Phối Sản Xuất Lô & Biến Thể (CONTRACT-ORCHESTRATION)
- **`CT-ORC-001` (`StartProductionBatch`):** Tiếp nhận chỉ tiêu sản xuất (`target_completed_videos`), phạm vi chủ đề, cấu hình chính sách, chế độ thực thi (`auto` / `debug`), và khóa idempotency duy nhất.
- **`CT-ORC-002` (Batch Target & Allocation Rule):** Phân bổ video theo từng vòng; mỗi bài viết/sự kiện chỉ sản xuất từ 1 đến 3 video (`INV-013`).
- **`CT-ORC-003` (`ProductionBatchState`):** Quản lý vòng đời lô: `created` -> `running` -> (`paused` / `reconciling`) -> `completed` / `stopped_no_work` / `failed_budget_exceeded`.
- **`CT-ORC-004` (Batch Control Commands):** Điều khiển lô từ UI: `PauseBatch`, `ResumeBatch`, `CancelBatch`, `ForceReconcileBatch`.
- **`CT-ORC-005` (`VideoJob` Lifecycle):** Quản lý vòng đời từng job: `snapshot_locked` -> `script_generated` -> `voice_ready` -> `rendered` -> `qc_passed` -> `cloud_verified` -> `completed`.
- **`CT-ORC-006` (StageRun & Execution Grant):** Cấp quyền thực thi có thời hạn (`lease_expiry`), generation token và khóa tài nguyên (`resource_locks`).
- **`CT-ORC-007` (Command Receipt & Decoupled State):** Trả về biên lai ghi nhận lệnh ngay lập tức (`INV-001`); trạng thái thực thi thực tế được đọc bất đồng bộ từ PostgreSQL.
- **`CT-ORC-008` (Capacity Reservation Guard):** Tổng số video đã hoàn thành cộng với các slot công việc đang thực hiện không bao giờ vượt quá chỉ tiêu lô (`INV-018`).
- **`CT-ORC-009` (Atomic Completion Ledger):** Ghi nhận hoàn thành video vào sổ cái nguyên tử, tăng biến đếm hoàn thành đúng 1 lần (`INV-010`), đồng thời liên kết chặt chẽ với cập nhật tần suất sử dụng media của Phân hệ C (`INV-017`).
- **`CT-ORC-010` (Batch Stopping Reasons):** Định nghĩa tường minh lý do dừng lô: đạt chỉ tiêu (`target_reached`), cạn nguồn tin đủ điều kiện (`no_eligible_work`), hết ngân sách chi phí (`budget_limit_exceeded`), hoặc người dùng can thiệp (`user_cancelled`).
- **`CT-ORC-011` (Variant Reservation & Cross-Round Diversity):** Đảm bảo các biến thể giữa các đợt sản xuất khác nhau phải khác biệt ít nhất một yếu tố thực tế (góc tiếp cận, hook, phong cách dựng hoặc cấu trúc kịch bản) (`INV-014`).
- **`CT-ORC-012` (Disambiguation: Retry vs Variant):** Phân định rõ ràng: `Retry` là thử lại một công việc thất bại với cùng tham số; `Variant` là sinh một sản phẩm mới khác biệt từ cùng nguồn dữ liệu.
- **`CT-ORC-013` (Zero Work Discarded Without State):** Tuyệt đối không có công việc nào bị biến mất mà không có trạng thái cuối cùng hoặc nhật ký truy vết.

---

## 4. Chi Tiết Giao Diện Điều Khiển, Sự Kiện & Lưu Trữ (Phân Hệ H & I)

### 4.1. Hợp đồng Điều Khiển & Quan Sát UI (CONTRACT-CONTROL-API-STREAM)
- **`CT-API-001` (Control API REST Endpoints):** Các điểm cuối quản trị: tạo/dừng lô, kích hoạt thu thập, xem danh sách bài viết/sự kiện/media, điều chỉnh cấu hình và tài khoản.
- **`CT-API-002` (Command Mutation Idempotency):** Mọi lệnh thay đổi trạng thái bắt buộc mang `idempotency_key` và trả về `CommandReceipt` có UUID xác định (`INV-001`).
- **`CT-API-003` (Server-Sent Events Stream):** Luồng sự kiện thời gian thực đẩy trạng thái lô, tiến độ job, cảnh báo chi phí và log hệ thống về giao diện Desktop UI.
- **`CT-API-004` (SSE Resync & Cursor Protocol):** Khi mất kết nối mạng, client gửi lại `Last-Event-ID`; server tự động bù đắp các sự kiện bị thiếu từ bảng `outbox` mà không bỏ sót bất kỳ thay đổi nào.
- **`CT-API-005` (Comprehensive Observability Screens):** Cung cấp dữ liệu đầy đủ cho các màn hình: Nguồn tin (`Source`), Nội dung (`Content`), Media & Hook, Jobs, Stages, Lô (`Batch`), Phiên làm việc (`Session`), Logs, Cấu hình (`Config`), Tài khoản (`Account`) và Chi phí (`Cost`).
- **`CT-API-006` (No-Silent-Failure Reconciliation):** UI phát hiện và hiển thị rõ ràng mọi sai lệch giữa cache cục bộ và cơ sở dữ liệu xác thực; không âm thầm giấu lỗi.
- **`CT-API-007` (Role-Based Admin Protection):** Chặn các thao tác nguy hiểm (xóa hàng loạt, xoay vòng khóa bí mật, khôi phục database) nếu thiếu quyền quản trị.
- **`CT-API-008` (Audit Log Stream):** Ghi nhận đầy đủ thông tin người thực hiện lệnh, thời điểm, tham số và kết quả phản hồi.

### 4.2. Hợp đồng Sự Kiện Nghiệp Vụ (CONTRACT-DOMAIN-EVENTS)
- **`CT-EVT-001` (Domain Event Standard Schema):** Cấu trúc chuẩn của mọi sự kiện: `event_id`, `event_type`, `aggregate_type`, `aggregate_id`, `occurred_at`, `payload`, `producer_service`.
- **`CT-EVT-002` (Transactional Outbox Pattern):** Mọi sự kiện miền bắt buộc được lưu đồng thời trong cùng transaction cơ sở dữ liệu với aggregate và được phân phối đáng tin cậy.
- **`CT-EVT-003` (Consumer Idempotency Guard):** Mọi consumer phải kiểm tra `event_id` trước khi thực hiện tác vụ; không sinh side-effect lặp (`INV-002`).
- **`CT-EVT-004` (Event Catalog):** Danh mục sự kiện đầy đủ: `SourceDiscovered`, `ArticleNormalized`, `ContentSnapshotCreated`, `ScriptGenerated`, `VoiceRendered`, `VideoRendered`, `QualityReportGenerated`, `ArtifactUploaded`, `ArtifactVerified`, `BatchProgressUpdated`, `BatchCompleted`.

### 4.3. Hợp đồng Lưu Trữ & Đồng Bộ Hybrid (CONTRACT-STORAGE)
- **`CT-STO-001` (Hybrid Storage Tiering):** Phân tầng dữ liệu rõ ràng giữa Local NVMe SSD (tệp tạm, xử lý render nhanh) và Google Drive Cloud Storage (kho lưu trữ lâu dài, bản phân phối cuối cùng).
- **`CT-STO-002` (Artifact Immutability & Content Addressing):** Mọi artifact được định danh bằng mã băm SHA-256; một khi đã tạo thì không thể sửa đổi nội dung.
- **`CT-STO-003` (Storage Intent Lifecycle):** Phân loại vòng đời: `ephemeral_scratch`, `reusable_rendition`, `production_output`, `cold_archive`.
- **`CT-STO-004` (Google Drive Resumable Upload):** Cơ chế tải lên đám mây hỗ trợ nối tiếp khi đứt kết nối mạng; tự động thử lại với lũy thừa thời gian chờ.
- **`CT-STO-005` (Cloud Verification Protocol):** Tệp sau khi upload lên Google Drive bắt buộc được tải về phần đầu hoặc kiểm tra MD5/SHA-256 checksum từ Google API; chỉ khi khớp hoàn toàn mới đánh dấu `cloud_verified` (`Gate G04`).
- **`CT-STO-006` (Zero Premature Deletion Rule):** Tuyệt đối cấm xóa bản sao cục bộ duy nhất nếu chưa có chứng nhận xác minh toàn vẹn trên đám mây (`INV-009`, `INV-011`).
- **`CT-STO-007` (Local Journal Reconciliation):** Sổ nhật ký tệp cục bộ (`LocalJournal`) đối soát hai chiều với database và Cloud Drive, phát hiện tệp rác mồ côi hoặc tệp bị thiếu.
- **`CT-STO-008` (Safe File Naming on Windows):** Chuẩn hóa tên tệp theo quy tắc Windows (loại bỏ ký tự đặc biệt, giới hạn 240 ký tự, cấu trúc `YYYY-MM-DD/HHMMSS_topic_hash.mp4`).
- **`CT-STO-009` (Atomic Cleanup Engine):** Dọn dẹp tệp tạm sau khi render hoàn tất; chỉ dọn khi đã qua kiểm tra 4 điều kiện: có trong sổ cái, đã verify trên cloud, đã hết hạn thuê (`lease expired`), và đúng epoch khôi phục (`INV-011`).
- **`CT-STO-010` (Backup Epoch & Isolated Restore):** Định kỳ sao lưu database và manifest; khi khôi phục sang epoch mới, toàn bộ message, grant và event từ epoch cũ bị cô lập hoàn toàn (`INV-016`, `Gate G05`).

---

## 5. Chi Tiết Quản Trị Cấu Hình, An Toàn & Chi Phí (Phân Hệ J)

### 5.1. Quản Trị Cấu Hình Đa Tầng (CONTRACT-CONFIG-SECURITY)
- **`CT-CFG-001` (Hierarchical Configuration Engine):** Nạp cấu hình theo thứ tự ưu tiên: Default Hệ Thống -> File Cấu Hình -> Biến Môi Trường -> Cấu Hình Lô Cụ Thể.
- **`CT-CFG-002` (Configuration Snapshot Immutability):** Mỗi công việc (`VideoJob`) khóa chặt một bản snapshot cấu hình tại thời điểm khởi tạo; việc thay đổi cấu hình toàn cục sau đó không làm ảnh hưởng đến các job đang chạy (`INV-004`).
- **`CT-CFG-003` (Dynamic Schema Validation):** Kiểm định tính hợp lệ của toàn bộ tham số cấu hình bằng Pydantic / JSON Schema nghiêm ngặt trước khi áp dụng.

### 5.2. An Toàn Thông Tin & Không Rò Rỉ Bí Mật (CONTRACT-CONFIG-SECURITY)
- **`CT-SEC-001` (Zero Secret Leakage Principle):** Tuyệt đối không xuất hiện API key, token OAuth, private key hoặc mật khẩu trong log hệ thống, Temporal workflow history, SSE stream, database audit, hay màn hình UI (`INV-012`).
- **`CT-SEC-002` (Secret Storage & In-Memory Redaction):** Bí mật được lưu trữ trong keyring bảo mật của hệ điều hành hoặc tệp mã hóa AES-GCM; trong bộ nhớ chỉ giải mã khi cần gọi API và tự động che giấu bằng bộ lọc `RedactionFilter` trước khi xuất log.
- **`CT-SEC-003` (Untrusted Source Isolation & Sandboxing):** Dữ liệu thu thập từ Internet và RSS ngoài được đối xử như dữ liệu không tin cậy; cấm sử dụng trực tiếp để thay đổi chính sách, gọi công cụ hệ điều hành hoặc tạo đường dẫn tệp chưa kiểm định (`INV-020`).
- **`CT-SEC-004` (Prompt Injection Defense):** Bộ lọc làm sạch đầu vào nội dung nguồn trước khi truyền vào prompt mô hình AI, ngăn chặn kỹ thuật chèn prompt gián tiếp (Indirect Prompt Injection).
- **`CT-SEC-005` (Local HTTPS & Secure Origin):** Giao tiếp giữa Control UI và Backend trên Desktop bắt buộc dùng TLS cục bộ hoặc ràng buộc nghiêm ngặt với loopback origin (`localhost / 127.0.0.1`), phòng chống tấn công CSRF / DNS rebinding.

### 5.3. Quản Trị Tài Khoản, Định Mức Tài Nguyên & Ngân Sách Chi Phí
- **`CT-ACC-001` (Provider Account Pool Management):** Quản lý luân chuyển nhiều tài khoản provider (OpenAI, Gemini, Anthropic, ElevenLabs, Google Drive); tự động chuyển đổi khi chạm giới hạn tốc độ (Rate Limit / HTTP 429).
- **`CT-ACC-002` (Health Check & Circuit Breaker):** Giám sát trạng thái hoạt động của từng tài khoản nhà cung cấp; tự động mở mạch ngắt (Circuit Breaker) khi phát hiện lỗi xác thực liên tiếp hoặc số dư tài khoản cạn kiệt.
- **`CT-CAP-001` (System Resource Admission Control):** Kiểm soát cấp phát tài nguyên phần cứng trước khi nhận tác vụ mới:
  - CPU usage < 85%;
  - RAM khả dụng tối thiểu > 4 GB;
  - Disk NVMe khả dụng tối thiểu > 20 GB;
  - GPU VRAM khả dụng tối thiểu > 2 GB;
  - Slot GPU độc quyền (`LOCK-DESKTOP-GPU`) được cấp phát tuần tự qua mutex.
- **`CT-COST-001` (Real-Time Cost Tracking):** Tích lũy chi phí gọi API theo từng token, từng giây âm thanh TTS, và từng tác vụ phân tích; lưu vết chi tiết trong `CostLedger`.
- **`CT-COST-002` (80% Budget Forecast Warning):** Tự động dự báo xu hướng chi phí của lô sản xuất; phát cảnh báo khẩn cấp lên UI và dừng nhận job mới nếu chi phí dự kiến vượt ngưỡng 80% ngân sách tháng (`Gate G03`).
- **`CT-COST-003` (Monthly Incremental Cost Boundary):** Đảm bảo chi phí phát sinh thực tế dưới 50 USD/tháng trên quy mô vận hành chuẩn (`R24`, `Gate G03`).

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
       ▼ (CT-STO-001..012 / CloudVerifiedArtifact)
[G: Điều Phối Lô & Workflow Temporal] ◄── [J: Config, Security, Cost & Quota]
       │                                     (CT-CFG-*, CT-SEC-*, CT-COST-*)
       ▼
[H: Control API, SSE Stream & UI Dashboard] (CT-API-001..008, CT-EVT-001..008)
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
| `INV-011` | Cleanup cần ledger, verify, lease check và đúng epoch | I, G (Storage Cleanup) | Cấm xóa tệp nếu chưa đủ 4 điều kiện an toàn |
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
