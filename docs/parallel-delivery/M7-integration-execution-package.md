# Gói Chuẩn Bị Thực Thi Kỹ Thuật: M7-INTEGRATION (Tự Động Hóa Lô, Hardening & Baseline Vận Hành)

> **Mã định danh gói (Package ID):** `M7-INTEGRATION` (Chuyển tiếp từ `M7-INTEGRATION-TEMPLATE`)
> **Milestone liên quan:** `M7` — Tự động hóa lô, hardening và baseline vận hành (`R5 Unattended Beta` & `R6 Operational Baseline`)
> **Trạng thái thẩm quyền (Authority State):** `planned` (Chuẩn bị kế hoạch thực thi kỹ thuật; cấm triển khai mã nguồn sản phẩm khi chưa có User Checkpoint phê duyệt mở Milestone M7)
> **Phân hệ sở hữu (Owners):** Toàn bộ Phân hệ A..J với các phân hệ trụ cột điều phối tích hợp: G (`CAP-G-ORCHESTRATION`), H (`CAP-H-CONTROL-API`), I (`CAP-I-STORAGE-SYNC`), J (`CAP-J-PROVIDERS`)
> **Thời điểm xác lập:** 09-10-2026 (Sau khi M6-EF hoàn tất kế hoạch và chốt baseline)
> **Tài liệu nguồn thẩm quyền:**
> - [docs/11-roadmap.md](../11-roadmap.md) (Mục 13 - M7, Mục 16, 19, 23, 27)
> - [docs/12-pre-code-checklist.md](../12-pre-code-checklist.md) (PCC-017, PCC-020, PCC-022, PCC-024)
> - [docs/modules/capability-g-orchestration.md](../modules/capability-g-orchestration.md)
> - [docs/modules/capability-j-providers.md](../modules/capability-j-providers.md)
> - [docs/modules/capability-c-storage.md](../modules/capability-c-storage.md)
> - [docs/06-system-map.md](../06-system-map.md) (Toàn bộ phân hệ A..J)
> - [docs/08-architecture.md](../08-architecture.md) (ARCH-001..ARCH-013)
> - [docs/adr/0003-durable-workflow-engine.md](../adr/0003-durable-workflow-engine.md)
> - [docs/adr/0006-drive-artifacts-and-local-journal.md](../adr/0006-drive-artifacts-and-local-journal.md)
> - [docs/adr/0007-runtime-and-admin-ui.md](../adr/0007-runtime-and-admin-ui.md)
> - [docs/adr/0011-observability-capacity-and-cost.md](../adr/0011-observability-capacity-and-cost.md)
> - [docs/adr/0013-wave-dag-development.md](../adr/0013-wave-dag-development.md)
> - [docs/parallel-delivery/operating-model.md](./operating-model.md)
> - [docs/parallel-delivery/ownership-and-locks.yaml](./ownership-and-locks.yaml)
> - [docs/parallel-delivery/task-dag.yaml](./task-dag.yaml)
> - [docs/parallel-delivery/acceptance-matrix.yaml](./acceptance-matrix.yaml) (R14..R24, Gates G01..G07)

---

## 1. Mục Đích & Giới Hạn Của Gói Chuẩn Bị M7-INTEGRATION

Gói chuẩn bị thực thi `M7-INTEGRATION` thiết lập toàn bộ cơ sở kỹ thuật machine-readable và human-readable để nối toàn bộ 10 phân hệ (A..J) thành một quy trình sản xuất video tự động có thể chịu lỗi, đạt đầy đủ các cổng chất lượng G01..G07 và thiết lập baseline vận hành vững chắc.

### 1.1. Phạm vi thực hiện
- **Tự động hóa lô không giám sát (Unattended Batch Automation):**
  - Tiếp nhận chỉ tiêu sản xuất do người dùng cấu hình qua UI (`target_completed_videos`), tự động phân bổ công việc theo vòng (1-3 video/tin/lượt) (`CT-ORC-001`, `CT-ORC-002`, `INV-013`).
  - Kiểm soát sức chứa lô nghiêm ngặt: Tổng số video hoàn thành cộng với các slot công việc đang thực hiện không bao giờ vượt quá chỉ tiêu lô (`INV-018`).
  - Đảm bảo tính đa dạng biến thể giữa các đợt sản xuất khác nhau (`INV-014`, `CT-ORC-011`).
- **Tích hợp toàn diện 10 phân hệ (End-to-End Cross-Module Pipeline):**
  - Kết nối đường ống dữ liệu hoàn chỉnh từ Thu thập (A) -> Chuẩn hóa & Sự kiện (B) -> Media (C) -> Trí tuệ kịch bản (D) -> Xử lý âm thanh & Timing (E) -> Dựng hình & QC (F) -> Lưu trữ & Sync Drive (I) -> Điều phối Temporal (G) -> UI/API Dashboard (H) -> Cấu hình & An toàn (J).
  - Đảm bảo tính tương thích hợp đồng tuyệt đối giữa các bước chuyển giao.
- **Chuỗi Hardening toàn diện (Comprehensive Hardening Suite):**
  - Chịu lỗi và cô lập lỗi: Lỗi tại một video, một nguồn tin hoặc một provider không làm dừng các công việc độc lập khác (`CT-WF-001`, `R16`).
  - Tái kết nối máy trạm: Desktop offline trong 5 phút không làm hỏng workflow, sẵn sàng tiếp tục khi online mà không chạy lại từ đầu (`CT-WF-004`).
  - Bảo vệ chống stale worker: Từ chối commit kết quả từ worker thế hệ cũ bằng generation token (`INV-003`, `INV-016`).
  - Không rò rỉ bí mật: Lọc sạch 100% secret/API key khỏi log, Temporal history, SSE stream và UI (`INV-012`, `CT-SEC-001`).
  - Sandbox dữ liệu ngoài: Chống indirect prompt injection, SSRF và path traversal từ dữ liệu RSS/web (`INV-020`, `CT-SEC-003`).
  - An toàn dọn dẹp và khôi phục: Cấm xóa bản sao cục bộ duy nhất nếu chưa xác minh trên Google Drive (`INV-009`, `INV-011`); cô lập hoàn toàn message epoch cũ khi khôi phục từ backup (`INV-016`, Gate G05).
- **Benchmark 12 Giờ & Kiểm chứng Ngưỡng Vận Hành:**
  - Đạt chỉ tiêu sản xuất tối thiểu 100 video hợp lệ hoàn tất trong 12 giờ chạy liên tục trên máy mục tiêu (`Gate G02`, `OBJ-003`).
  - Đạt tối thiểu 95% video đủ đầu vào hoàn thành không cần bất kỳ can thiệp thủ công nào sau khi bắt đầu lô (`Gate G02`, `OBJ-004`).
  - Kiểm soát chi phí gia tăng thực tế dưới 50 USD/tháng trên quy mô chuẩn, có cảnh báo khi chạm 80% ngân sách (`Gate G03`, `R24`).
- **Baseline Vận Hành & Runbook Xuất Xưởng:**
  - Đóng đầy đủ 7 cổng chất lượng hệ thống: G01 (Workflow), G02 (Throughput/Capacity), G03 (Cost), G04 (Drive/Security), G05 (Restore/Recovery), G06 (AI/Content Quality), G07 (Compatibility/QC).
  - Cung cấp runbook vận hành, quy trình xoay vòng credential, giám sát dung lượng, nâng cấp và rollback an toàn.

### 1.2. Giới hạn nghiêm ngặt (Fail-Closed Boundaries)
- **Tuyệt đối không sửa đổi mã nguồn sản phẩm (Product Source):** Không tạo hoặc chỉnh sửa bất kỳ tệp nào trong `src/**`.
- **Tuyệt đối không sửa đổi database migration:** Không chạm vào `migrations/**` hoặc `src/**/migrations/**`.
- **Tuyệt đối không ghi đè evidence lịch sử:** Không chạm vào `docs/milestones/**/evidence/**` của M1 (P0..P6), M2 (P0..P9) và các gói chuẩn bị đã nghiệm thu.
- **Trạng thái thực thi:** Triển khai mã nguồn sản phẩm và migration vẫn tiếp tục bị **KHÓA CHẶT** (`NOT AUTHORIZED`) theo quy định tại `docs/12-pre-code-checklist.md` cho đến khi có User Checkpoint chính thức kích hoạt Milestone M7.

---

## 2. Tiền Đề Kỹ Thuật & Đồ Thị Phụ Thuộc (DAG Dependencies)

### 2.1. Điều kiện tiền đề kỹ thuật (Technical Preconditions)
1. **M6-EF Baseline:** Gói chuẩn bị thực thi Phân hệ E & F (`M6-EF`) đã hoàn tất đóng băng hợp đồng, kiểm định ma trận test plan và đạt Astra PASS.
2. **M5-D Baseline:** Gói chuẩn bị thực thi Phân hệ D (`M5-D`) đã hoàn tất đóng băng hợp đồng và đạt Astra PASS.
3. **M4-CI Baseline:** Gói chuẩn bị thực thi Phân hệ C & I (`M4-CI`) đã hoàn tất đóng băng hợp đồng và đạt Astra PASS.
4. **M3-A Baseline:** Gói chuẩn bị thực thi Phân hệ A & B (`M3-A`) đã hoàn tất đóng băng hợp đồng và đạt Astra PASS.
5. **M2 Foundation:** Nền tảng điều khiển, hợp đồng API, state machines và cơ chế logging/security đã được xác thực qua M2.
6. **Host Environment:** Máy mục tiêu Windows 11 đáp ứng tối thiểu CPU 8 cores, 32GB RAM, GPU NVIDIA RTX với VRAM >= 6GB, SSD NVMe >= 100GB trống, Python 3.11/3.13, FFmpeg 7.x, PostgreSQL 16 và Temporal Server R1.

### 2.2. Ràng buộc đồ thị DAG (DAG Graph Constraints)
Trong [task-dag.yaml](./task-dag.yaml), node `M7-INTEGRATION-TEMPLATE` được định vị tại vị trí đỉnh hội tụ của toàn bộ đồ thị:

```
[M3-A-TEMPLATE] ──► [M4-CI-TEMPLATE] ──► [M5-D-TEMPLATE] ──► [M6-EF-TEMPLATE]
                                                                     │
                                                                     ▼
                                                          [M7-INTEGRATION-TEMPLATE]
                                                          (Wave 3: Serialized Integration)
```

- **Điều kiện phụ thuộc:** `task: M6-EF-TEMPLATE`, `condition: accepted`.
- **Chính sách tiếp nhận (Admission):** `serialized_cross_owner_integration` (Tích hợp tuần tự liên phân hệ; cấm phân nhánh song song không kiểm soát tại tầng tích hợp lõi).
- **Quy tắc Single-Writer:** Tại thời điểm tích hợp M7, chỉ có một writer duy nhất được phép thay đổi composition root và luồng điều phối tích hợp.

---

## 3. Ranh Giới Sở Hữu Mã Nguồn (Single-Writer Ownership & Source Paths)

### 3.1. Aggregates thuộc quyền sở hữu trong M7
Các Aggregate nghiệp vụ cốt lõi phục vụ tích hợp M7 được phân bổ rõ ràng cho các phân hệ chủ trì:
- **Phân hệ G (`CAP-G-ORCHESTRATION`):** `ProductionBatch`, `VideoJob`, `StageRun`, `CompletionLedger`, `ExecutionGrant`, `BatchCapacityReservation`, `VariantReservation`.
- **Phân hệ H (`CAP-H-CONTROL-API`):** `CommandReceipt`, `ClientSession`, `OutboxMessage`, `SSEStreamSubscription`, `UIProjection`.
- **Phân hệ I (`CAP-I-STORAGE-SYNC`):** `StorageArtifact`, `LocalJournal`, `DriveSyncMetadata`, `CleanupLedger`, `BackupEpoch`.
- **Phân hệ J (`CAP-J-PROVIDERS`):** `ConfigSnapshot`, `ProviderAccount`, `CredentialLease`, `CostLedger`, `ResourceQuota`.

### 3.2. Cấu trúc thư mục mã nguồn mục tiêu
Khi Milestone M7 được cấp quyền triển khai mã nguồn, cấu trúc thư mục mục tiêu được phân định như sau:

#### Cấu trúc Phân hệ G (`src/orchestration` và `tests/integration/orchestration`):
- `src/orchestration/batch_engine.py`: Điều phối vòng đời lô sản xuất và kiểm soát chỉ tiêu.
- `src/orchestration/allocation_policy.py`: Phân bổ bài viết/video theo vòng và giới hạn 1-3 video.
- `src/orchestration/workflows/`: Các workflow logic Temporal (`production_batch.py`, `video_production.py`, `daily_collection.py`, `maintenance.py`).
- `src/orchestration/activities/`: Các activity bọc giao tiếp sang các phân hệ thực thi A..F, I, J.
- `src/orchestration/completion_ledger.py`: Sổ cái nguyên tử ghi nhận hoàn thành video (`INV-010`, `INV-017`).
- `src/orchestration/variant_registry.py`: Sổ đối soát biến thể, chống lặp nội dung giữa các đợt (`INV-014`).

#### Cấu trúc Phân hệ H (`src/control_api`, `src/ui` và `tests/integration/control`):
- `src/control_api/endpoints/`: REST API điều khiển lô, job, config và quan sát trạng thái.
- `src/control_api/sse_stream.py`: Kênh SSE đẩy sự kiện thời gian thực kèm cơ chế resync con trỏ cursor.
- `src/control_api/idempotency.py`: Xử lý biên lai lệnh và bảo đảm tính lũy đọng (`INV-001`).
- `src/ui/`: Màn hình giao diện quản trị Desktop UI (Batch, Jobs, Media, Config, Logs, Cost).

#### Cấu trúc Phân hệ I (`src/storage` và `tests/integration/storage`):
- `src/storage/drive_sync.py`: Upload nối tiếp lên Google Drive, xác thực checksum và làm mới token OAuth.
- `src/storage/local_journal.py`: Sổ nhật ký tệp cục bộ đối soát hai chiều.
- `src/storage/cleanup_engine.py`: Động cơ dọn dẹp tệp tạm nguyên tử với 4 điều kiện kiểm tra (`INV-011`).
- `src/storage/backup_recovery.py`: Cơ chế sao lưu và khôi phục phân tách epoch (`INV-016`, Gate G05).

#### Cấu trúc Phân hệ J (`src/config`, `src/security`, `src/providers` và `tests/integration/providers`):
- `src/config/snapshot_manager.py`: Quản lý snapshot cấu hình bất biến cho từng job (`INV-004`).
- `src/security/redaction_filter.py`: Bộ lọc thanh lọc secret và credential trong mọi luồng dữ liệu (`INV-012`).
- `src/security/input_sanitizer.py`: Làm sạch dữ liệu nguồn ngoài, chống Prompt Injection và Path Traversal (`INV-020`).
- `src/providers/account_pool.py`: Bể tài khoản provider với luân chuyển và circuit breaker tự động.
- `src/providers/cost_guard.py`: Theo dõi chi phí tích lũy và phát cảnh báo dự báo 80% ngân sách (`Gate G03`).
- `src/providers/admission_control.py`: Kiểm soát cấp phát tài nguyên CPU/GPU/RAM/Disk.

#### Thư mục kiểm thử đầu-cuối (`tests/e2e`):
- `tests/e2e/test_e2e_001_to_014.py`: Bộ 14 kịch bản kiểm thử toàn trình từ thu thập đến xuất xưởng.
- `tests/e2e/test_benchmark_12h.py`: Kịch bản đo lường hiệu năng 100 video/12 giờ và 95% tự động.
- `tests/e2e/test_fault_injection.py`: Kịch bản tiêm lỗi toàn diện (mất mạng, crash worker, API 429, disk full).

### 3.3. Ranh giới cấm ghi chéo (Strictly Forbidden Cross-Owner Paths)
- Worker thực thi phân hệ G tuyệt đối không ghi trực tiếp vào bảng nội dung của B, catalog của C hay tệp của I ngoài API/contract.
- Worker phân hệ H tuyệt đối không can thiệp logic dựng hình của F hay tính toán kịch bản của D.
- Tuyệt đối cấm mọi thao tác bypass hợp đồng hoặc chèn logic tắt (shortcut) không thông qua Temporal workflow.

---

## 4. Quản Lý Khóa Tài Nguyên & Fencing (Resource Locks & Leases)

Trong môi trường tích hợp M7, các tài nguyên dùng chung được quản trị bằng hệ thống khóa xác định tại [ownership-and-locks.yaml](./ownership-and-locks.yaml):

1. **`LOCK-TEMPORAL-WORKFLOW`:** Khóa điều phối Temporal; chỉ có phân hệ G được phép tạo và quản lý workflow execution.
2. **`LOCK-DESKTOP-GPU`:** Khóa tài nguyên GPU trên Desktop; cấp slot độc quyền cho các tác vụ nặng (FFmpeg render, probe, transcode) nhằm ngăn chặn tràn VRAM.
3. **`LOCK-DRIVE-SYNC`:** Khóa phân luồng đồng bộ đám mây; giới hạn số luồng upload đồng thời lên Google Drive nhằm tránh vi phạm quota rate-limit của Google API.
4. **`LOCK-DB-SCHEMA`:** Khóa di chuyển cấu trúc dữ liệu; chỉ duy nhất một tiến trình migration được cấp phép chạy tại một thời điểm.
5. **`LOCK-COST-QUOTA`:** Khóa định mức chi phí; kiểm soát ngưỡng chi tiêu API để ngăn chặn cạn kiệt ngân sách bất ngờ.
6. **`LOCK-CONTRACT-SOURCE`:** Khóa bất biến tệp nguồn hợp đồng (`docs/09-contracts/**`); cấm mọi hành vi sửa đổi.
7. **Generation Fencing Token:** Mỗi tác vụ được cấp một token `execution_generation`. Worker thế hệ cũ gửi kết quả muộn sau sự cố mạng hoặc failover sẽ bị hệ thống từ chối commit ngay lập tức (`INV-003`, `INV-016`).

---

## 5. Phân Kỳ Gói Công Việc Nhỏ (Work Packages INT-0..INT-8)

Gói tích hợp M7 được chia thành 9 gói công việc con (Work Packages) có ranh giới rõ ràng, thực thi tuần tự và kiểm chứng nghiêm ngặt:

```
INT-0 (Composition Root & Contract Glue)
  │
  ├──► INT-1 (Unattended Batch Engine & Allocation)
  │      │
  │      └──► INT-2 (Resilience, Child Isolation & Circuit Breaker)
  │
  ├──► INT-3 (Security, Sandboxing & Zero-Leakage Hardening)
  │
  ├──► INT-4 (Control Plane, SSE Stream & UI Hardening)
  │
  ├──► INT-5 (Hybrid Storage Reconcile, Cleanup & Isolated Restore)
  │
  └──► INT-6 (Provider Routing, Quota & Cost Guard)
         │
         ▼
       INT-7 (12-Hour Benchmark & Performance Hardening)
         │
         ▼
       INT-8 (Baseline Verification & Operational Runbook Release)
```

### 5.1. INT-0: Composition Root & Contract Glue
- **Mục tiêu:** Xây dựng dependency injection container và liên kết hợp đồng giữa 10 phân hệ theo đúng các interface đã đóng băng.
- **Ràng buộc:** Không thay đổi hợp đồng nguồn; kiểm tra tính toàn vẹn chữ ký hàm và schema dữ liệu (`CT-CMN-*`).

### 5.2. INT-1: Unattended Batch Engine & Allocation
- **Mục tiêu:** Hoàn thiện động cơ quản lý lô sản xuất tự động: tiếp nhận chỉ tiêu từ người dùng, thuật toán phân bổ vòng (1-3 video/tin), kiểm soát capacity reservation (`INV-010`, `INV-013`, `INV-018`, `CT-ORC-001..010`).

### 5.3. INT-2: Resilience, Child Isolation & Circuit Breaker
- **Mục tiêu:** Thiết lập cơ chế chịu lỗi của hệ thống: bọc `VideoProductionWorkflow` thành child workflow cô lập lỗi; kiểm thử kịch bản Desktop offline và tự động phục hồi trong 5 phút; cơ chế stale worker rejection (`INV-003`, `CT-WF-001..006`, `R16`).

### 5.4. INT-3: Security, Sandboxing & Zero-Leakage Hardening
- **Mục tiêu:** Triển khai bộ lọc `RedactionFilter` trên toàn bộ luồng log/history/SSE/UI; cơ chế khử độc dữ liệu nguồn ngoài chống prompt injection, SSRF và path traversal (`INV-012`, `INV-020`, `CT-SEC-001..005`).

### 5.5. INT-4: Control Plane, SSE Stream & UI Hardening
- **Mục tiêu:** Hoàn thiện giao diện điều khiển và kênh đẩy sự kiện thời gian thực: SSE resync với cursor offset; không âm thầm giấu lỗi; màn hình Dashboard quan sát đầy đủ 10 phân hệ (`CT-API-001..008`, `CT-EVT-001..004`, `R19`, `R20`).

### 5.6. INT-5: Hybrid Storage Reconcile, Cleanup & Isolated Restore
- **Mục tiêu:** Hoàn thiện cơ chế đồng bộ Google Drive với xác thực SHA-256; sổ đối soát hai chiều `LocalJournal`; động cơ dọn dẹp tệp tạm nguyên tử với 4 điều kiện kiểm tra; cơ chế phục hồi cơ sở dữ liệu phân tách epoch (`INV-009`, `INV-011`, `INV-016`, `INV-017`, `CT-STO-001..010`, `Gate G04`, `Gate G05`).

### 5.7. INT-6: Provider Routing, Quota & Cost Guard
- **Mục tiêu:** Quản trị bể tài khoản provider với luân chuyển và circuit breaker; kiểm soát cấp phát tài nguyên phần cứng (CPU/GPU/RAM/Disk); theo dõi chi phí tích lũy và phát cảnh báo dự báo 80% ngân sách (`Gate G03`, `CT-ACC-001..002`, `CT-CAP-001`, `CT-COST-001..003`, `R23`, `R24`).

### 5.8. INT-7: 12-Hour Benchmark & Performance Hardening
- **Mục tiêu:** Chạy thử nghiệm tải liên tục trong 12 giờ trên máy mục tiêu: sản xuất tối thiểu 100 video hợp lệ hoàn tất, đạt tối thiểu 95% video tự động hoàn toàn không cần can thiệp (`Gate G02`, `OBJ-003`, `OBJ-004`).

### 5.9. INT-8: Baseline Verification & Operational Runbook Release
- **Mục tiêu:** Rà soát nghiệm thu toàn diện 7 cổng chất lượng G01..G07; xuất bản runbook vận hành, quy trình xử lý sự cố, và hồ sơ nghiệm thu kỹ thuật bàn giao cho người dùng.

---

## 6. Chiến Lược Rollback & Bảo Toàn Dữ Liệu (Rollback Strategy)

Trong quá trình tích hợp hoặc chạy thử nghiệm M7, nếu phát hiện sự cố nghiêm trọng, chiến lược rollback được thực thi theo các nguyên tắc:
1. **Bảo toàn dữ liệu đã xác thực:** Toàn bộ video đã xuất xưởng đạt chuẩn và đã được xác thực trên Google Drive (`cloud_verified`) cùng các bản ghi sổ cái tương ứng (`CompletionLedger`) tuyệt đối không bị xóa hoặc rollback.
2. **Hủy an toàn các công việc dở dang:** Các child workflow đang chạy dở dang tại thời điểm phát sinh sự cố sẽ được Temporal gửi tín hiệu hủy an toàn (`Graceful Cancellation`); toàn bộ tệp tạm được dọn dẹp sạch sẽ.
3. **Phục hồi trạng thái cơ sở dữ liệu:** Nếu cần rollback schema cơ sở dữ liệu, sử dụng tệp sao lưu trước đợt chạy lô và chuyển sang một epoch mới (`BackupEpoch`), cô lập toàn bộ message cũ để ngăn chặn zombie mutation (`INV-016`).

---

## 7. Danh Mục Open Items & Hạn Quyết Định (Open Decision Gates)

Các quyết định mở liên quan đến Milestone M7 được ghi nhận rõ ràng, kèm điều kiện kích hoạt:
- **`ROADMAP-OPEN-006` (Sampling Plan & Holdout Corpus):** Phương pháp lấy mẫu kiểm định chất lượng AI/Content (`Gate G06`) phải được người dùng phê duyệt trước khi khóa holdout set cho đợt kiểm thử cuối.
- **`ROADMAP-OPEN-010` (Retention & Storage Placement):** Chính sách thời hạn lưu trữ tệp cục bộ và quy tắc dọn dẹp tự động phải được chốt trước khi kích hoạt tính năng dọn dẹp không giám sát.
- **`ROADMAP-OPEN-011` (Scale Workload Definition):** Bộ tham số tải đại diện cho bài kiểm tra 12 giờ (tỷ lệ chủ đề, cấu hình preset, tần suất tin mới) phải được khóa trước khi chạy benchmark chính thức.
- **`ROADMAP-OPEN-012` (Backup & Restore Scope):** Phạm vi các bảng và tệp cần sao lưu phục vụ diễn tập thảm họa (`Gate G05`) phải được chốt trước khi tuyên bố tính năng restore sẵn sàng.
- **`USER-CKPT-M7` (User Approval Checkpoint):** Người dùng nghiệm thu toàn diện kết quả chuẩn bị kỹ thuật và phê duyệt cấp quyền triển khai mã nguồn sản phẩm cho Milestone M7.

---

## 8. Kết Luận & Định Hướng Tiếp Theo

1. Gói chuẩn bị thực thi kỹ thuật `M7-INTEGRATION` đã hoàn tất thiết lập lộ trình tích hợp, ranh giới phân quyền, cơ chế quản lý khóa và kế hoạch phân kỳ 9 gói công việc nhỏ cho toàn bộ 10 phân hệ của hệ thống.
2. Tài liệu này đóng vai trò là kim chỉ nam kỹ thuật ràng buộc cho bản kế hoạch kiểm thử đi kèm (`docs/parallel-delivery/M7-integration-test-plan.md`).
3. Mọi công việc tiếp theo tuân thủ triệt để nguyên tắc Fail-Closed và sẵn sàng đón nhận thẩm tra kỹ thuật độc lập (Sol-Lead) và thẩm định kiến trúc tối cao (Astra-Lead).
