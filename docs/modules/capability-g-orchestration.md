# Đặc tả Kỹ thuật Capability G: Điều phối Quy trình & Quản lý Lô (Workflow Orchestration & Batch Management)

> **Mã Capability:** `CAP-G-ORCHESTRATION`
> **Chủ quản:** Module G
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-ORCHESTRATION`, `CONTRACT-WORKFLOW-EXECUTION`, `CONTRACT-DOMAIN-EVENTS`, `CONTRACT-STATE-MACHINES`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability G là tổng chỉ huy luồng vận hành của hệ thống, chịu trách nhiệm tiếp nhận các lô sản xuất (`Batch`), lập kế hoạch và phân bổ các công việc (`VideoJob`), quản lý hàng đợi và quyền thực thi từng công đoạn (`StageRun`, `ExecutionGrant`), theo dõi dung lượng tài nguyên và khóa biến thể (`VariantReservation`), đồng thời điều phối việc ghi nhận hoàn tất thông qua Unit of Work nguyên tử (`CompletionLedger`).

### Aggregates do Module G sở hữu độc quyền (Single-Writer):
- `Batch` (contract gọi `ProductionBatch`, bảng `cp_production_batches`): Quản lý tập hợp các job sản xuất được kích hoạt cùng đợt kèm chỉ tiêu và cấu hình chung.
- `BatchCapacityReservation`: Đặt trước định ngạch tài nguyên CPU, GPU, bộ nhớ cho toàn lô.
- `VariantReservation`: Đặt trước và khóa cấu trúc biến thể trong quá trình sinh kịch bản để chống va chạm.
- `VariantRegistryRevision`: Sổ cái phiên bản các biến thể đã từng xuất bản.
- `VideoJob`: Tiến trình vòng đời của một video từ lúc khởi tạo đến khi xuất xưởng hoàn chỉnh.
- `StageRun`: Nhật ký thực thi của từng công đoạn con (stage_type theo `CT-ORC-003`).
- `ExecutionGrant`: Token cấp quyền thực thi có thời hạn (fenced lease) cho worker thực hiện công đoạn.
- `CompletionLedger`: Sổ cái ghi nhận hoàn tất video nguyên tử, liên kết giữa Orchestration, Media Usage (Module C) và Artifact Sync (Module I).

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Lệnh từ Control API:** Tiếp nhận lệnh sản xuất của G từ Module H qua `CONTRACT-CONTROL-API-STREAM` (`CT-API-005`: `StartProductionBatch`, `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`; `CT-API-001` là quy tắc request). `CT-BAT-001..004` do Module H sở hữu trong `contract-registry.yaml`. Contract hiện không có lệnh pause, resume hoặc cancel (PUC-G-03).
- **Port Lắng nghe Sự kiện Miền:** Nhận sự kiện hoàn tất công đoạn từ các worker qua `CONTRACT-DOMAIN-EVENTS` (`CT-EVT-001`).

### Outbound Ports:
- **Port Khởi tạo Workflow Activity:** Điều phối thực thi các activity qua `CONTRACT-WORKFLOW-EXECUTION` (`CT-WF-001`).
- **Port Atomic Completion Unit of Work:** Thực thi transaction liên module phối hợp Module C (MediaUsage) và Module I (Storage) qua `CONTRACT-ORCHESTRATION` (`CT-ORC-008`, `CT-ORC-009`; `CT-ORC-002` là `AllocateVideoJob`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability G phải thỏa mãn:
1. `CONTRACT-ORCHESTRATION`, `CONTRACT-WORKFLOW-EXECUTION` và `CONTRACT-STATE-MACHINES` đã được đóng băng phiên bản (`frozen revision`).
2. Tách biệt rõ ràng giữa Command Receipt (`status: "accepted"`) và Authoritative Execution State (`running`, `succeeded`, `failed`, `cancelled`).
3. Database namespace `db:orchestration` và bảng trạng thái máy (state machines) đã được chuẩn hóa.
4. Cơ chế cấp phát fencing token đơn điệu đã được cài đặt và kiểm chứng tính an toàn trước tấn công replay/stale lease.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability G chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. 100% unit tests, state machine tests và mock workflow integration tests đạt `PASS`.
2. Kiểm chứng tính lũy kế và bất biến của State Machine: Chuyển đổi trạng thái job và stage phải tuân thủ nghiêm ngặt đồ thị hợp lệ; tuyệt đối cấm tua ngược hoặc bỏ qua bước kiểm tra.
3. Nguyên tắc nguyên tử của Completion Unit of Work (`CT-ORC-008`): ledger, chuyển VideoJob sang `COMPLETED`, MediaUsage qua port của Module C và outbox cùng một transaction PostgreSQL; ArtifactLocation do Module I verify trước (`cloud_location_verification_ref`) và không được ghi trong transaction này.
4. Quản lý dung lượng (Admission Control): Từ chối nhận thêm job khi tài nguyên vượt ngưỡng lấy từ cấu hình của Module J (D8-G-07); `schedule-policy.yaml` chỉ là chính sách điều phối song song lúc phát triển, không phải ngưỡng sản phẩm.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-001` (Decoupled Command Receipt vs Authoritative State):** Trả về `accepted` chỉ là biên lai ghi nhận lệnh; trạng thái thực thi thực tế phải được đọc từ state machine PostgreSQL.
- **`INV-003` (Monotonic Fencing Tokens):** Mỗi ExecutionGrant được cấp phát phải có fencing token tăng dần; kết quả trả về mang token cũ bị từ chối fail-closed.
- **`INV-010`** (`TST-WF-INV-010`): completion lặp chỉ tăng ledger và bộ đếm một lần; **`INV-017`** (`TST-WF-INV-017`): ledger và `MediaUsage` cùng commit hoặc rollback.
- **`INV-016`** (`TST-WF-INV-016`): result mang epoch cũ sau restore bị từ chối; **`INV-018`** (`TST-WF-INV-018`): hai allocator tranh suất cuối.
- Một worker mỗi stage là hệ quả của fencing (`INV-003`), không phải một INV riêng.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/controlplane/domain/orchestration/**`, `src/controlplane/application/orchestration/**`, `src/controlplane/infrastructure/db/orchestration/**`
  - `tests/unit/orchestration/**`, `tests/integration/orchestration/**`
  - `docs/modules/capability-g-orchestration.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/voice/**`
  - `src/render/**`
  - `src/storage/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử State Machine & Fencing:** Kiểm tra việc từ chối các kết quả muộn (late worker results) mang fencing token cũ, và xác minh giao dịch nguyên tử khi job hoàn tất.
- **Quan sát RED:** Chuyển job `ACTIVE → COMPLETED` bỏ qua `READY_FOR_COMPLETION` phải gây `ForbiddenTransitionError` (CT-STATE-009: CREATED, SNAPSHOTTED, ACTIVE, WAITING, READY_FOR_COMPLETION, COMPLETED, FAILED_FINAL; job không có `pending` hay `succeeded`).
- **Targeted Test Command:**
  ```bash
  python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Khi phát sinh sự cố trong stage, chuyển trạng thái stage sang `failed`, ghi nhận nguyên nhân vào nhật ký, giải phóng toàn bộ resource leases và kích hoạt chính sách retry có giới hạn (exponential backoff). Nếu hủy bỏ batch, toàn bộ job chưa chạy được đánh dấu `cancelled` và hoàn trả capacity reservations.
