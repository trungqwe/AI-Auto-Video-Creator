# Kế hoạch triển khai Phân hệ G — Điều phối công việc và quan sát vận hành

> Task: `IMPL-PLAN-G` (planning_package), trigger INITIAL. Base: `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4`.
> Nguồn quyền: D3 — user duyệt Phần B ngày 18/10/2026; M3–M7 theo ủy quyền AI_SETUP. Kích hoạt sản xuất vẫn `PRODUCTION_ACTIVATION_BLOCKED`.
> Đây là kế hoạch; mã nguồn do các slice trong `docs/implementation/g/slices.md` thực hiện.

## 1. Nguồn chuẩn

- `docs/modules/capability-g-orchestration.md` (có lỗi, xem 1.1)
- `docs/09-contracts/09-orchestration-contracts.md` (CT-ORC-001..012, mục 11), `03-workflow-and-execution.md` (CT-WF-001..009), `12-state-machines.md` (CT-STATE-008..011), `02-domain-events.md` (catalog G, CT-EVT-002..005), `00-common-contract.md` (CT-CMN-001..003, mục 14), `01-control-api-and-stream.md` (CT-API-005, CT-API-009), `11-configuration-security-contracts.md` (CT-CAP-002/003)
- `docs/11-roadmap.md` §8 (M2, năng lực G, AUD2-B01), §9–§12 (phần G của M3–M6), §13 (M7), §14, các mục ROADMAP-OPEN
- `docs/10-test-strategy.md` §14.2 (INV, dòng 526–545), §15 (E2E, dòng 549–603), TST-WF-VAR-001..004 (dòng 1184–1187), TEST-OPEN
- `docs/adr/0003-durable-workflow-engine.md`, `docs/adr/0004-commit-idempotency-and-fencing.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (G dòng 48–51; `PATH-SRC-ORCHESTRATION` dòng 167–177; `LOCK-SRC-ORCHESTRATION` dòng 427–432), `contract-registry.yaml` (CONTRACT-BATCHES-QUERY từ dòng 259), `schedule-policy.yaml`
- `docs/parallel-delivery/bindings/README.md`; binding `g-activity-execution.json`, `g-c-i-completion.json`, `domain-event-envelope.json`, `b-d-production-snapshot.json`; fixture `tests/fixtures/contracts/g-activity-execution/payloads.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m7-integration.md` (m3-a, m4-ci, m5-d, m6-ef cùng quy tắc)
- Mã hiện có (chỉ đọc): `src/controlplane/domain/orchestration/__init__.py`, `src/controlplane/application/orchestration/__init__.py`, `src/controlplane/application/orchestration/start_batch.py`, `src/controlplane/infrastructure/db/orchestration/`, `src/controlplane/domain/statemachine/__init__.py`, `src/controlplane/domain/events/contracts.py`, `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql`, `tests/m2/test_p6_orchestration_shell.py`
- Kế hoạch lân cận để đồng bộ: `docs/implementation/a/plan.md`, `c/plan.md`, `d/plan.md`, `i/plan.md`, `j/plan.md`

### 1.1. Đính chính tài liệu cũ (errata)

Khi mâu thuẫn, contract, catalog test, ADR và errata CP1 thắng `docs/modules/capability-g-orchestration.md`. Kế hoạch không chép lại các điểm sai dưới đây.

| Mã | Vị trí | Nội dung sai | Nguồn chuẩn và xử lý |
|---|---|---|---|
| ERR-G-01 | capability-g dòng 70–72 | Allowed path `src/controlplane/orchestration/**` | D1 và `PATH-SRC-ORCHESTRATION`: domain, application, infrastructure/db orchestration cùng tests/unit và tests/integration. Slice không sửa `docs/modules/capability-g-orchestration.md` (ngoài phong bì; YC-HT-G-09) |
| ERR-G-02 | dòng 29 | Lệnh batch qua `CT-API-001` và `CT-BAT-001`; pause/resume/cancel | CT-API-001 là quy tắc request; lệnh của G là CT-API-005. CT-BAT-001..004 chỉ có trong contract-registry.yaml và do H sở hữu. CT-API-005, CT-STATE-009, CT-STATE-010 không có pause/resume/cancel: không lập slice, xem PUC-G-03 |
| ERR-G-03 | dòng 34 | Completion unit of work là CT-ORC-002 | CT-ORC-008 và CT-ORC-009; CT-ORC-002 là AllocateVideoJob |
| ERR-G-04 | dòng 60–64 | INV-010 outbox, INV-016 một worker mỗi stage, INV-017 completion idempotent | Catalog: INV-010 completion lặp chỉ tăng ledger/count một lần; INV-016 result epoch cũ sau restore bị từ chối; INV-017 ledger và MediaUsage cùng commit/rollback; INV-018 hai allocator tranh suất cuối. Một worker mỗi stage là hệ quả của fencing (INV-003) |
| ERR-G-05 | dòng 7, 87–89 | `python -m unittest` với đường dẫn tệp; RED từ `pending` sang `succeeded` | Job không có `pending`/`succeeded` (CT-STATE-009: CREATED, SNAPSHOTTED, ACTIVE, WAITING, READY_FOR_COMPLETION, COMPLETED, FAILED_FINAL). Dùng pytest theo lệnh khoá; RED hợp lệ là `ACTIVE → COMPLETED` bỏ qua READY_FOR_COMPLETION gây `ForbiddenTransitionError` |
| ERR-G-06 | dòng 14–22 | Aggregate `Batch`; chuỗi stage Collection→Ingestion→Script→Voice→Render→Sync | Contract gọi `ProductionBatch` (bảng `cp_production_batches`); stage_type theo CT-ORC-003 |
| ERR-G-07 | dòng 54 | Ngưỡng admission nằm ở schedule-policy.yaml | Tệp là chính sách điều phối song song lúc phát triển (as_of 2026-10-02), không phải ngưỡng sản phẩm; ngưỡng đến từ cấu hình J (D8-G-07) |
| ERR-G-08 | dòng 53 | Lưu ArtifactLocation trong transaction completion | CT-ORC-008: I đã verify trước (`cloud_location_verification_ref`); G chỉ ghi ledger, job, reservation, bộ đếm, MediaUsage qua port của C, outbox và cleanup eligibility |

Áp dụng thêm errata m7-integration mục 1–6 (cây thư mục trùng, manifest điền sẵn, INV sai, test ID ngoài catalog, trạng thái tự đặt). Contract-registry.yaml CT-BAT-002 khai `jobs_summary` với `pending/succeeded` không khớp state machine job: việc ánh xạ thuộc H (YC-HT-G-08).

## 2. Năng lực và aggregate

Aggregate do G sở hữu (ownership-and-locks.yaml dòng 48–51): `Batch` (contract gọi `ProductionBatch`), `BatchCapacityReservation`, `VariantReservation`, `VariantRegistryRevision`, `VideoJob`, `StageRun`, `ExecutionGrant`, `CompletionLedger`. Shell P6/P7A đã ACCEPTED và đã có mã: dataclass `ExecutionGrant`, `VariantReservation`, `CapacityAllocation`, `CompletionLedger`, `ReservationState` ở `src/controlplane/domain/orchestration/__init__.py`; `ExecutionGrantService`, `VariantReservationService`, `BatchCapacityService`, `CompletionLedgerService` ở `src/controlplane/application/orchestration/__init__.py`; `PostgresOrchestrationRepository` ở `src/controlplane/infrastructure/db/orchestration/__init__.py`; bảng trong migration `0006_orchestration_shell.sql`. Kế hoạch này không dựng lại các aggregate đó: slice thêm module mới bên cạnh (value object, chính sách thuần, use case có port) và chỉ import.

Hiện trạng `commit_completion` của P6 chỉ chèn một dòng ledger: chưa chuyển job sang COMPLETED, chưa convert reservation, chưa tăng revision registry, chưa ghi MediaUsage, chưa phát outbox. Đủ CT-ORC-008 là việc của G-09/G-10 (logic với fake) và migration của hội tụ (YC-HT-G-01).

| # | Năng lực | Contract | Aggregate/thành phần | Slice |
|---|---|---|---|---|
| 1 | Validator payload activity và completion theo binding | CT-WF-003, CT-WF-006, CT-ORC-008, CT-ORC-009 | Value object | G-01, G-02 |
| 2 | Fencing generation/epoch, cấp grant đơn điệu | CT-WF-004, CT-WF-006, INV-003, INV-016 | ExecutionGrant | G-03, G-04 |
| 3 | Operation receipt, retry side effect an toàn | CT-WF-005, CT-STATE-011 | OperationReceipt (P4 đã có) | G-05 |
| 4 | StageRun, job waiting, R18, capability | CT-ORC-003, CT-ORC-007, CT-WF-007, CT-STATE-008/009 | StageRun, VideoJob | G-06 |
| 5 | Allocation theo target, 1–3 job mỗi lượt, capacity | CT-ORC-001, CT-ORC-002, INV-018 | Batch, BatchCapacityReservation | G-07 |
| 6 | Variant reservation và registry revision | CT-ORC-012, TST-WF-VAR-001..004 | VariantReservation, VariantRegistryRevision | G-08 |
| 7 | Cổng completion và unit of work | CT-ORC-008, CT-ORC-009, INV-010, INV-017 | CompletionLedger | G-09, G-10 |
| 8 | Retry, tạo biến thể, debug stage; retry/backoff | CT-ORC-004/005/006, CT-WF-007, CT-WF-008 | Command semantics | G-11 |
| 9 | Workflow catalog, task queue, versioning, resource admission | CT-WF-001/002/009, roadmap §13 mục 9 | Catalog, admission | G-12 |
| 10 | Event payload và audit nhất quán (no-silent-failure) | CT-EVT-002/003, roadmap §13 R5 | Event builder, audit | G-13 |
| 11 | Resume sau restart, lý do dừng batch, app session | CT-WF acceptance 1/7, CT-ORC-010, CT-ORC-011 | Recovery scan, Batch, AppSession | G-14 |

## 3. Vị trí mã theo D1

G mở rộng các gói đã có trong `src/controlplane`; không dựng `src/orchestration`, `src/controlplane/orchestration`, `src/storage`, `src/ui` hay cây trùng aggregate nào. Import root `src/`, dạng `controlplane.…`, không dùng tiền tố `src.`.

| Đường dẫn | Vai trò |
|---|---|
| `src/controlplane/domain/orchestration/` | Value object, validator binding, chính sách thuần (G-01..03, 05, 06, 07, 09, 11..14) |
| `src/controlplane/application/orchestration/` | Use case và port có fake trong test (G-04, 07, 08, 10, 13) |
| `src/controlplane/infrastructure/db/orchestration/` | Adapter PostgreSQL P6/P7A; chỉ mở rộng sau migration của hội tụ (YC-HT-G-01), chưa có slice |
| `tests/unit/orchestration/` | Test đơn vị tên `test_g_*.py` |
| `tests/integration/orchestration/` | Test tích hợp in-process với fake (G-10), tên `test_g_*.py` |

Quyết định D8-G-09: không sửa ba `__init__.py` của domain, application, db orchestration và `start_batch.py`, vì `tests/m2/test_p6_orchestration_shell.py`, test P7A và `tests/integration/collection/test_a18_worker_activity.py` import chúng (`ExecutionGrant`). Không thêm `__init__.py` vào thư mục test; tiền tố `test_g_` giữ tên tệp test duy nhất.

## 4. Contract dùng và cung cấp

### 4.1. G cung cấp

| Contract | Binding | Slice |
|---|---|---|
| CT-WF-003 `ActivityRequest`, CT-WF-006 `ActivityResult` | `docs/parallel-delivery/bindings/g-activity-execution.json` (BINDING-G-ACTIVITY-EXECUTION 1.0.0; consumer A, B, C, D, E, F, I, J); fixture `tests/fixtures/contracts/g-activity-execution/payloads.json` | G-01, G-03, G-04 |
| CT-ORC-008 `CommitVideoCompletionRequest`, CT-ORC-009 `CompletionLedgerEntry` | `docs/parallel-delivery/bindings/g-c-i-completion.json` (consumer C, I); fixture `tests/fixtures/contracts/g-c-i-completion/payloads.json` | G-02, G-09, G-10 |
| Event G (`BatchStarted`, `JobAllocated`, `StageStateChanged`, `JobWaiting`, `JobFailed`, `VideoCompleted`, `BatchTargetReached`, `BatchExhausted`) | `docs/parallel-delivery/bindings/domain-event-envelope.json` | G-13 |
| CT-ORC-012 (D ↔ G), CT-API-005 (H ↔ G), CT-CAP-002/003 (J → G) | Chưa có binding (bindings/README.md, mục seam chưa có binding) | Slice chỉ dùng port nội bộ G và fake; mở binding qua YC-HT-G-03 |

### 4.2. G dùng

| Binding hoặc mã | Trường G dùng | Slice |
|---|---|---|
| `b-d-production-snapshot.json` (G là consumer) | `snapshot_id` giữ làm `snapshot_ref` của job; G không đọc nội dung snapshot | G-07, G-11 |
| `i-artifact-version.json` (G là consumer) | `output_artifact_version_id`, hash | G-09 |
| `controlplane.domain.statemachine` | `transition_job`, `transition_batch`, `transition_stage_run`, `transition_operation` (chỉ import) | G-05, G-06, G-10, G-14 |
| `controlplane.domain.events.contracts` | `ensure_safe_event_payload` (chỉ import) | G-13 |
| `controlplane.domain.interfaces.uow.IUnitOfWork` | Hình dạng unit of work; fake cài trong test | G-10 |
| `j-provider-route.json` | Không dùng; routing là của J | — |

### 4.3. Kiểu và tên lệch cần giữ

- `recovery_epoch`: binding và CT-WF-004 là chuỗi opaque; `ExecutionGrant.recovery_epoch`, cột `cp_stage_runs.recovery_epoch` (BIGINT) và `DomainEvent.recovery_epoch` hiện là int (D8-G-03).
- `grant_id`: P6 `ExecutionGrant` không có trường này; test A-18 dùng `operation_id` làm `grant_id` (D8-G-04).
- `DomainEvent.schema_version` hiện là int, binding khai chuỗi.
- `CompletionLedgerEntry` (binding) yêu cầu `batch_ref`, `session_ref`, `preset_revision_ref`, `output_naming_metadata`, `cost_usage_summary`, `audit_actor`, `cleanup_policy_ref` mà `CommitVideoCompletionRequest` không có; G lấy từ ngữ cảnh qua port (D8-G-14); bảng `cp_completion_ledger` hiện thiếu các cột này (YC-HT-G-01).
- `ActivityRequest.execution_grant` là optional trong binding nhưng CT-WF-003 bắt buộc khi có side effect hoặc commit: G-01 kiểm điều kiện này bằng tham số `side_effect`.
- Khi mâu thuẫn, binding thắng; slice không sửa binding.

## 5. Exit gate roadmap và cách kiểm

G là năng lực xuyên suốt (roadmap §14: M2 core state/receipt, M3 collection workflow, M4 storage workflow, M5 creative workflow, M6 video workflow, M7 batch hoàn chỉnh). Mọi slice dùng fake nên chỉ chứng minh logic; không được trích làm bằng chứng đóng gate tài nguyên thật (roadmap §13 Điều cấm).

### 5.1. Gate G phục vụ

| Mã | Exit gate (nguồn) | Slice | Cách kiểm |
|---|---|---|---|
| EG-M2-G-1 | VariantReservation tách khỏi capacity; TST-WF-VAR-001..004 trước nghiệm thu completion (§8) | G-08, G-09, G-10 | `tests/unit/orchestration/test_g_variant_reservation_flow.py`, `test_g_completion_gate.py`, `tests/integration/orchestration/test_g_commit_completion.py` |
| EG-M3-G-1 | Desktop offline không dừng collection cloud; một nguồn lỗi không dừng cycle (§9) | G-06, G-12, G-14 | `test_g_job_waiting.py` (stage collection không bị R18 chặn), `test_g_workflow_catalog.py` (child cô lập), `test_g_batch_outcome.py` |
| EG-M3-G-2 | Scheduler cloud và lịch theo múi giờ (§9) | Không có slice | YC-HT-G-05; PUC-G-01 |
| EG-M4-G-1 | Completion chỉ khi có cloud verification; đồng bộ gián đoạn không đếm trùng (§10, TST-E2E-012) | G-05, G-09, G-10 | `test_g_operation_receipt.py`, `test_g_completion_gate.py`, `test_g_commit_completion.py` |
| EG-M5-G-1 | Provider lỗi không làm mất job/history và không tự thêm dịch vụ trả phí (§11) | G-06, G-11 | `test_g_job_waiting.py`, `test_g_retry_policy.py` |
| EG-M5-G-2 | Ba video cùng lượt khác góc; variant lượt sau không trùng (§11, INV-013) | G-07, G-08 | `test_g_allocation_policy.py`, `test_g_variant_reservation_flow.py` (phía G của TST-WF-VAR-004) |
| EG-M6-G-1 | Không output nào được đếm trước cloud verification; render, QC, upload, completion là bốn mốc riêng (§12) | G-06, G-09, G-10 | `test_g_stage_run_plan.py`, `test_g_completion_gate.py`, `test_g_commit_completion.py` (phần G của TST-E2E-INV-009) |
| EG-M6-G-2 | Không local output bị xóa khi sync/completion chưa đủ (§12) | G-10 | `test_g_commit_completion.py` (chỉ tạo cleanup eligibility sau commit, không phát lệnh xóa) |
| EG-M6-G-3 | Tạo `R4 Video Alpha` theo luồng giám sát (§12) | Không có slice | CP7-G-01; YC-HT-G-05 |
| EG-M7-G-1 | Năng lực 1: target, allocation 1–3 video/lượt, INV-018 (§13) | G-07, G-14 | `test_g_job_allocation.py`, `test_g_batch_outcome.py` (TST-E2E-005/006) |
| EG-M7-G-2 | Năng lực 2: child cô lập lỗi, waiting/resume (§13) | G-06, G-12, G-14 | `test_g_job_waiting.py`, `test_g_workflow_catalog.py`, `test_g_recovery_scan.py` (TST-E2E-007/008) |
| EG-M7-G-3 | Năng lực 3 và 5: retry khác variant; auto và debug cùng handler | G-11, G-12 | `test_g_command_semantics.py` (TST-E2E-010/014) |
| EG-M7-G-4 | Năng lực 4: desktop reconnect không chạy lại từ đầu; sẵn sàng trong 5 phút | G-14 (logic); CP7-G-02 (đo) | `test_g_recovery_scan.py`; thời gian chỉ đóng bằng đo thật |
| EG-M7-G-5 | Năng lực 7 và R5: không job biến mất không trạng thái/log | G-13 | `test_g_consistency_audit.py`, `test_g_event_payloads.py` |
| EG-M7-G-6 | Năng lực 9: resource admission | G-12 | `test_g_resource_admission.py` |
| EG-M7-G-7 | R5: resume, retry, reconcile và cleanup qua fault suite | G-05, G-10, G-14 (logic) | Fault suite thật: CP7-G-03 |
| EG-M7-G-8 | R6: 100 video/12 giờ (G02), 95% tự động, ngưỡng ACK/resume/scheduler | Không có slice | CP7-G-04; PUC-G-05 |

### 5.2. Test bắt buộc phần G (catalog docs/10-test-strategy.md)

- `TST-CTR-INV-001` (INV-001): lệnh lặp ra một receipt do P3/P4 đã có; G-11 kiểm retry không tạo job mới.
- `TST-WF-INV-003`: G-03, G-04. `TST-WF-INV-016`: G-03, G-14.
- `TST-WF-INV-010`: G-10. `TST-WF-INV-017`: G-10 với fake unit of work; bản PostgreSQL thật sau YC-HT-G-01 và CP7.
- `TST-WF-INV-018`: G-07 với fake có khóa luồng; ca PostgreSQL P6 đã có ở `tests/m2/test_p6_orchestration_shell.py`.
- `TST-WF-VAR-001..004`: G-08, G-09, G-10.
- `TST-E2E-005, 006, 007, 008, 010, 013, 014`: phần logic ở G-07, G-14, G-06, G-11; E2E đầy đủ do hội tụ.
- Không dùng test ID ngoài catalog; ID mới phải vào catalog trước (YC-HT-G-09).

## 6. Mục mở và quyết định mặc định (D8)

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-G-01 | Attempt và hàng StageRun không có cạnh thoát | Mỗi attempt là một StageRun mới (stage_run_id mới, attempt+1). Hàng ở `WAITING_DEPENDENCY`, `WAITING_CAPABILITY`, `FAILED_RETRYABLE` giữ nguyên và được đánh dấu superseded (cột của migration, YC-HT-G-01). Không thêm cạnh vào state machine | CT-STATE-008 nói rõ không có cạnh thoát từ các trạng thái đó và không tự suy diễn recovery edge; CT-STATE-001 mục 1: terminal không mở lại. Xác nhận ở PUC-G-02 |
| D8-G-02 | Disposition `waiting` khi stage đang RUNNING | Stage giữ nguyên; job chuyển `WAITING` kèm wait reason (CT-STATE-009 ACTIVE → WAITING); stage `RUNNING → STALE` khi grant bị thu hồi hoặc hết hạn; attempt mới chỉ tạo khi capability sẵn sàng | Không có cạnh RUNNING → WAITING_* trong CT-STATE-008. Xác nhận ở PUC-G-02 |
| D8-G-03 | Kiểu `recovery_epoch` | Chuỗi opaque ở tầng application; so sánh bằng `str()` với giá trị int hiện có | CT-WF-004, binding; cùng cách D8-I-04; đổi kiểu cột qua YC-HT-G-01 |
| D8-G-04 | `grant_id` | Value object `GrantClaims` riêng ở G-03; hàm ánh xạ từ `ExecutionGrant` P6 (`operation_id` đóng vai `grant_id` như test A-18); bảng grant riêng là YC-HT-G-01 | Không sửa `ExecutionGrant` đang được test bảo vệ |
| D8-G-05 | `stage_type` | Chuỗi snake_case; tập tối thiểu `collect`, `analyze`, `script`, `media_select`, `tts`, `align`, `process`, `render`, `qc`, `sync`, `complete`; dấu ba chấm của CT-ORC-003 nghĩa là tập mở, thêm qua workflow catalog G-12 | Bindings/README.md D8 mục 2 |
| D8-G-06 | Wait reason | Đúng 8 giá trị CT-ORC-007. CPU/GPU/RAM/mạng bão hòa là deferral (stage ở PENDING, không WAITING); thiếu đĩa là `insufficient_disk` | Bão hòa tài nguyên là backpressure, không phải trạng thái chờ có cấu trúc |
| D8-G-07 | Ngưỡng admission, timeout, heartbeat, retry | Tham số bắt buộc, không có giá trị mặc định cứng; nguồn là cấu hình J | CT-WF-007 ghi là CẤU HÌNH theo activity; TEST-OPEN-003; ERR-G-07 |
| D8-G-08 | Kiểm thử đồng thời | Fake in-memory có khóa luồng; bản PostgreSQL thật chỉ sau migration (YC-HT-G-01) và không dùng đóng gate | Locked runtime không có dịch vụ thật |
| D8-G-09 | Cách thêm mã | Module mới cạnh P6/P7A; không sửa ba `__init__.py` và `start_batch.py` | Giữ `tests/m2`, A-18 xanh |
| D8-G-10 | Event envelope | `schema_version` là chuỗi `1`, `sensitivity` là `internal`, `recovery_epoch` chuỗi (GIẢ ĐỊNH theo bindings/README.md D8) | Binding khai string; `test_driver.py` dùng `internal` |
| D8-G-11 | Pause/resume/cancel | Không lập slice | ERR-G-02; PUC-G-03 |
| D8-G-12 | Phạm vi khóa registry biến thể | Khóa theo workspace, giữ nguyên | CT-ORC-012, ADR-0004: không tối ưu scope khi chưa có bằng chứng |
| D8-G-13 | Workflow engine | Slice không import `temporalio`; logic thuần, wiring là hội tụ | ADR-0003 conditional |
| D8-G-14 | Trường ledger ngoài request | `batch_ref`, `session_ref`, `preset_revision_ref`, `output_naming_metadata`, `cost_usage_summary`, `audit_actor`, `cleanup_policy_ref` đến từ ngữ cảnh qua port có fake (GIẢ ĐỊNH); nguồn thật nối ở hội tụ | Binding hai thực thể lệch nhau |

Đối chiếu mục mở roadmap liên quan G: ROADMAP-OPEN-004 (múi giờ) → PUC-G-01; ROADMAP-OPEN-011 (scale workload) → PUC-G-05; ROADMAP-OPEN-012 (backup/restore) → PUC-G-06; TEST-OPEN-003 (timeout/retry/backoff) → D8-G-07, PUC-G-04; QUALITY-OPEN-002 (thời gian cycle) thuộc A, G chỉ nhận `deadline_at` từ cấu hình.

### 6.1. Danh sách chờ user (pendingUserCheckpoint)

Không mục nào dưới đây được coi là đã duyệt.

- PUC-G-01 — ROADMAP-OPEN-004/TEST-OPEN-009: múi giờ production cho scheduler. Hạn: trước khi bật lịch production.
- PUC-G-02 — Quyết định về khoảng trống CT-STATE-008 (thoát khỏi `WAITING_*`, `FAILED_RETRYABLE`; `waiting` khi RUNNING): giữ D8-G-01/02 hay mở cạnh mới (đổi state machine đã đóng băng là ARCHITECTURE_CHANGE). Hạn: trước G01 đầy đủ.
- PUC-G-03 — Pause/resume/cancel batch hoặc job: tài liệu module có, contract không có. Hạn: trước khi UI M7 có nút này.
- PUC-G-04 — TEST-OPEN-003: timeout, retry, backoff từng activity/provider sau benchmark. Hạn: trước fault oracle.
- PUC-G-05 — ROADMAP-OPEN-011 và ngưỡng ACK, resume 5 phút, scheduler cho R6. Hạn: trước claim performance.
- PUC-G-06 — ROADMAP-OPEN-012: phạm vi backup/restore (G05) và hành vi epoch. Hạn: trước khi bật writer/cleanup sau restore.
- PUC-G-07 — D5 cho CP7 và USER-CKPT-D9-D10 trước CP-2b.
- PUC-G-08 — User duyệt các mốc có phần G: A-B và R1 (M3), C-I và R2 (M4), D và R3 (M5), E-F, 5 preset và R4 (M6), R5/R6 (M7).

## 7. Thư viện (D10)

Các slice không cần thư viện mới: chỉ dùng stdlib (`dataclasses`, `enum`, `datetime`, `re`, `typing`, `threading`, `uuid`, `hashlib`, `json`) và `pytest==9.1.1` đã khoá. Không import `psycopg`, `temporalio` hay thư viện khác trong slice. Gói đã khai ở `pyproject.toml` gốc cho wiring và CP7 của hội tụ (không thêm mới): `temporalio==1.32.0` (ADR-0003, engine ưu tiên có điều kiện), `psycopg[binary]==3.3.5`, `psycopg-pool==3.3.1`. Kế hoạch không đề xuất gói mới. Nếu replay G01 cần test server của Temporal tải từ mạng thì phải trình USER-CKPT-D9-D10, không thêm âm thầm.

## 8. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5; dùng tài khoản thật chỉ qua secret broker của J; không mở, chép hay in bí mật.

- CP7-G-01 — Batch không giám sát trên workload đại diện với E-F thật và Drive thật (R5; EG-M6-G-3).
- CP7-G-02 — Đo desktop reconnect: sẵn sàng tiếp tục trong 5 phút, không chạy lại từ đầu (EG-M7-G-4; PUC-G-05).
- CP7-G-03 — Fault suite tại mọi ranh giới side effect (trước, trong, sau khi bên ngoài hoàn thành nhưng trước commit receipt), gồm ca PostgreSQL thật cho TST-WF-INV-010/016/017/018 và replay workflow (G01).
- CP7-G-04 — G02: 100 video hợp lệ trong 12 giờ, ít nhất 95% tự động; G03 chi phí tháng (R6).
- CP7-G-05 — G05 restore drill: epoch mới, result generation trùng epoch cũ bị quarantine, cấp lại grant (PUC-G-06).

## 9. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

Tài nguyên dùng chung chỉ gói hội tụ được sửa; slice G không chạm vào.

- YC-HT-G-01 — Migration: bảng grant (grant_id, stage_run_id, generation, recovery_epoch kiểu text, worker_lease_id, issued_at, expires_at, allowed_operation, input_fingerprint, trạng thái); cột `cp_stage_runs`: stage_type, input_refs, dependency_refs, wait_reason, problem, thời điểm, superseded_by; đổi `recovery_epoch` sang text opaque; cột `cp_video_jobs`: wait_reason, parent và prior variant refs; thêm vào `cp_completion_ledger` các trường CT-ORC-009 còn thiếu (D8-G-14); bảng receipt, cleanup eligibility, app session, lý do dừng batch; sau đó mở slice adapter PostgreSQL trong `src/controlplane/infrastructure/db/orchestration/`.
- YC-HT-G-02 — Composition root (`src/main.py`, `src/controlplane/api/main.py`): wiring service G, unit of work completion cùng port `MediaUsageRecorder` của C (CONV-C-02) và outbox.
- YC-HT-G-03 — Registry và binding: mở binding D ↔ G (CT-ORC-012), H ↔ G (CT-API-005), J → G (CT-CAP-002/003); bổ sung nguồn trường ledger ngoài request.
- YC-HT-G-04 — State machine (`LOCK-CONTRACT-STATE-MACHINES`): quyết định PUC-G-02 và PUC-G-03; giữ nguyên graph cho tới khi user quyết.
- YC-HT-G-05 — Workflow (Temporal): cài catalog G-12 thành workflow thật (Collection, Enrichment, ProductionBatch, VideoProduction child cô lập, DebugStage, Maintenance); đăng ký activity của A–F, I, J (CONV-A-06, CONV-C-08, CONV-D-05, YC-HT-I-06, YC-HT-J-06); scheduler cloud theo PUC-G-01.
- YC-HT-G-06 — Control API (H): route StartProductionBatch, RunDebugStage, RetryStage, CreateNewVariant, RegenerateFromStage theo G-11; trả receipt `accepted` khác trạng thái thực thi.
- YC-HT-G-07 — Outbox/event: đăng ký 8 event G và publisher dùng chung (G-13).
- YC-HT-G-08 — UI shell (H, `ui/dist`, `App.tsx`): màn hình batch, job, stage, session, log; ánh xạ `jobs_summary` của CT-BAT-002 sang state machine thật.
- YC-HT-G-09 — Tài liệu và catalog: sửa `docs/modules/capability-g-orchestration.md` theo ERR-G-01..08; đăng ký test ID mới vào `docs/10-test-strategy.md` nếu cần; chỉnh `PATH-SRC-ORCHESTRATION` nếu cần.
- YC-HT-G-10 — Tích hợp chéo: A-18 dùng `ExecutionGrant` P6; đổi sang `GrantClaims` (G-03) phải do hội tụ thực hiện.

## 10. DAG slice và song song

- Wave 1 (song song, chỉ phụ thuộc `CP1-CONTRACT-BINDING`, `CP2A-LAYOUT`): G-01, G-02, G-03, G-05, G-06, G-07, G-08, G-11, G-12, G-13, G-14.
- Wave 2: G-04 (sau G-03); G-09 (sau G-02, G-03).
- Wave 3: G-10 (sau G-09, G-13).

Mỗi slice sở hữu tệp riêng nên dùng lock `LOCK-G-<số>`; `LOCK-SRC-ORCHESTRATION` để dành cho việc sửa tệp P6/P7A chung do hội tụ thực hiện. Gốc của mọi slice là `CP1-CONTRACT-BINDING` và `CP2A-LAYOUT` (đã tích hợp).
