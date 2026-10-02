# Đặc tả Kỹ thuật Capability G: Điều phối Quy trình & Quản lý Lô (Workflow Orchestration & Batch Management)

> **Mã Capability:** `CAP-G-ORCHESTRATION`
> **Chủ quản:** Module G
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-ORCHESTRATION`, `CONTRACT-WORKFLOW-EXECUTION`, `CONTRACT-DOMAIN-EVENTS`, `CONTRACT-STATE-MACHINES`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability G là tổng chỉ huy luồng vận hành của hệ thống, chịu trách nhiệm tiếp nhận các lô sản xuất (`Batch`), lập kế hoạch và phân bổ các công việc (`VideoJob`), quản lý hàng đợi và quyền thực thi từng công đoạn (`StageRun`, `ExecutionGrant`), theo dõi dung lượng tài nguyên và khóa biến thể (`VariantReservation`), đồng thời điều phối việc ghi nhận hoàn tất thông qua Unit of Work nguyên tử (`CompletionLedger`).

### Aggregates do Module G sở hữu độc quyền (Single-Writer):
- `Batch`: Quản lý tập hợp các job sản xuất được kích hoạt cùng đợt kèm chỉ tiêu và cấu hình chung.
- `BatchCapacityReservation`: Đặt trước định ngạch tài nguyên CPU, GPU, bộ nhớ cho toàn lô.
- `VariantReservation`: Đặt trước và khóa cấu trúc biến thể trong quá trình sinh kịch bản để chống va chạm.
- `VariantRegistryRevision`: Sổ cái phiên bản các biến thể đã từng xuất bản.
- `VideoJob`: Tiến trình vòng đời của một video từ lúc khởi tạo đến khi xuất xưởng hoàn chỉnh.
- `StageRun`: Nhật ký thực thi của từng công đoạn con (Collection -> Ingestion -> Script -> Voice -> Render -> Sync).
- `ExecutionGrant`: Token cấp quyền thực thi có thời hạn (fenced lease) cho worker thực hiện công đoạn.
- `CompletionLedger`: Sổ cái ghi nhận hoàn tất video nguyên tử, liên kết giữa Orchestration, Media Usage (Module C) và Artifact Sync (Module I).

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Lệnh từ Control API:** Tiếp nhận lệnh tạo batch, trigger job, pause/resume/cancel từ Module H qua `CONTRACT-CONTROL-API-STREAM` (`CT-API-001`, `CT-BAT-001`).
- **Port Lắng nghe Sự kiện Miền:** Nhận sự kiện hoàn tất công đoạn từ các worker qua `CONTRACT-DOMAIN-EVENTS` (`CT-EVT-001`).

### Outbound Ports:
- **Port Khởi tạo Workflow Activity:** Điều phối thực thi các activity qua `CONTRACT-WORKFLOW-EXECUTION` (`CT-WF-001`).
- **Port Atomic Completion Unit of Work:** Thực thi transaction liên module phối hợp Module C (MediaUsage) và Module I (Storage) qua `CONTRACT-ORCHESTRATION` (`CT-ORC-002`).

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
3. Nguyên tắc nguyên tử của Completion Unit of Work: Khi một video hoàn thành, việc tăng số đếm MediaUsage, cập nhật VideoJob sang `succeeded`, và lưu ArtifactLocation phải diễn ra trong đúng **MỘT** transaction PostgreSQL duy nhất.
4. Quản lý dung lượng (Admission Control): Từ chối nhận thêm job khi dung lượng hệ thống (CPU, GPU, RAM) vượt quá ngưỡng an toàn được quy định tại `schedule-policy.yaml`.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-001` (Decoupled Command Receipt vs Authoritative State):** Trả về `accepted` chỉ là biên lai ghi nhận lệnh; trạng thái thực thi thực tế phải được đọc từ state machine PostgreSQL.
- **`INV-003` (Monotonic Fencing Tokens):** Mỗi ExecutionGrant được cấp phát phải có fencing token tăng dần; kết quả trả về mang token cũ bị từ chối fail-closed.
- **`INV-010` (Transaction Atomicity & Outbox):** Mọi thay đổi trạng thái tiến trình và phát sinh sự kiện outbox phải cam kết nguyên tử.
- **`INV-016` (Single Active Worker per Job Stage):** Tại một thời điểm, chỉ có duy nhất một worker sở hữu lease thực thi trên một stage của job.
- **`INV-017` (Idempotent Job Completion):** Video hoàn tất không bao giờ bị xử lý trùng hoặc làm tăng bộ đếm 2 lần.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/controlplane/orchestration/**`
  - `tests/unit/orchestration/**`
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
- **Quan sát RED:** Kiểm thử fail rõ ràng khi cố tình chuyển trạng thái job từ `pending` thẳng sang `succeeded` mà không qua các stage bắt buộc.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/orchestration/test_job_lifecycle.py -k test_state_machine_and_fencing
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Khi phát sinh sự cố trong stage, chuyển trạng thái stage sang `failed`, ghi nhận nguyên nhân vào nhật ký, giải phóng toàn bộ resource leases và kích hoạt chính sách retry có giới hạn (exponential backoff). Nếu hủy bỏ batch, toàn bộ job chưa chạy được đánh dấu `cancelled` và hoàn trả capacity reservations.
