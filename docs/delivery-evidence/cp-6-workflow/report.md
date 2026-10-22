# Báo cáo nghiệm thu CP-6-WORKFLOW

## 1. Thông tin chung

- Mã nhiệm vụ: `CP-6-WORKFLOW`
- Milestone: `M7`
- Commit HEAD gốc (Base SHA): `497a06b5f0f0783ea42200cb35f0f922f2cad09d`
- Trạng thái cổng: Cổng GATE-CP-6-WORKFLOW do Control thả khi có Auditor PASS; Worker không tự thả cổng.

## 2. Bảng lệnh kiểm thử và kết quả thực tế

| STT | Lệnh kiểm thử | Mã thoát (Exit Code) | Kết quả thực tế |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | Không có lỗi khoảng trắng hay định dạng dòng |
| 2 | `python -m pytest tests/integration/collection -q -p no:cacheprovider` (Bước 5) | 0 | 145 passed, 25 subtests passed in 0.65s |
| 3 | `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py -q -p no:cacheprovider` (Bước 18) | 0 | 9 passed in 0.12s |
| 4 | `python -m pytest tests/integration/convergence/test_cp6_workflow_catalog.py -q -p no:cacheprovider` (Bước 21) | 0 | 11 passed in 1.81s |
| 5 | `python -m pytest tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` (Bước 24) | 0 | 8 passed in 0.56s |
| 6 | `git diff --check` (Bước 26) | 0 | Không có lỗi khoảng trắng |
| 7 | `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` (Bước 27) | 0 | 28 passed in 0.80s |
| 8 | `python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voice tests/integration/render tests/unit/config tests/unit/catalog tests/unit/storage -q -p no:cacheprovider` (Bước 28) | 0 | 3379 passed, 1034 subtests passed in 6.41s |

## 3. Phạm vi đã triển khai

- **Sáu workflow Temporal theo catalog G-12**:
  - `DailyCollectionWorkflow`
  - `ContentEnrichmentWorkflow`
  - `ProductionBatchWorkflow`
  - `VideoProductionWorkflow`
  - `DebugStageWorkflow`
  - `MaintenanceWorkflow`
  Được định nghĩa tại `src/controlplane/application/orchestration/workflows/definitions.py` sử dụng thư viện `temporalio==1.32.0`.
- **Sáu task queue logic**:
  - `control-workflows`, `cloud-io`, `cloud-ai`, `desktop-cpu`, `desktop-gpu`, `desktop-render`.
  - Các stage `script`, `plan`, `tts` bắt buộc chỉ chạy ở queue desktop (`desktop-gpu`, `desktop-cpu`), không chạy ở queue cloud.
- **Bảng đăng ký activity (Activity Bindings)**:
  - Đăng ký đầy đủ 32 activity cho các phân hệ A, B, C, D, E, F, G, I, J tại `src/controlplane/application/orchestration/workflows/activities.py`.
  - Bộ điều phối `ActivityDispatcher` xác thực nghiêm ngặt; từ chối gọi handler của mọi activity có side effect nếu thiếu `execution_grant` (`MISSING_EXECUTION_GRANT`).
- **Bốn tín hiệu (Signals)**:
  - `VideoProductionWorkflow`: `RetryStage`, `RegenerateFromStage`.
  - `ProductionBatchWorkflow`: `CreateNewVariant`, `RunDebugStage`.
- **Điều phối khả năng thực thi (Capability View)**:
  - Khi thiếu capability desktop, luồng chuyển trạng thái sang `WAITING_CAPABILITY`, ghi nhận `waiting_stage` và `wait_reason`, sau đó resume mượt mà theo trạng thái cập nhật từ `CapabilityView`.
- **Ánh xạ sự kiện (Subscription)**:
  - Ánh xạ `CollectedDocumentAvailable` sang `ResolveCollectedDocument` của phân hệ B qua hàm `document_input_refs`.
- **Cấu hình động từ phân hệ J**:
  - Toàn bộ tham số timeout, retry, backoff được đọc trực tiếp từ cấu hình phân hệ J (`tools/launcher/prod/profile.json`) qua `WorkflowSettings`. Không có bất kỳ hằng số thời gian nào bị viết cứng trong mã nguồn workflow.
- **Lịch cloud (Schedule State)**:
  - Giữ trạng thái `NOT_READY` khi múi giờ chưa được người dùng phê duyệt theo điều kiện `PUC-G-01`.
- **Chuyển đổi A-18 sang `GrantClaims` (YC-HT-G-10)**:
  - Chuyển `workspace_id` sang `CollectActivityDeps` kèm xác thực khởi tạo `__post_init__`.
  - Thay thế `ActivityGrantPort` bằng `ClaimsCurrencyPort` ở phía handler.
  - Các phân hệ D, E, F giữ nguyên `ExecutionGrant` thông qua hàm chuyển đổi `to_execution_grant`.

## 4. Quyết định kỹ thuật mặc định (D8)

- Thời gian thăm dò chu kỳ khi ở trạng thái `WAITING_CAPABILITY` được lấy từ cấu hình `ai.quota_wait_poll_seconds` do cấu hình J chưa có khoá cấu hình thăm dò riêng cho workflow.
- Nhịp phát heartbeat định kỳ được lấy từ cấu hình `workflow.heartbeat_seconds`; không thiết lập `heartbeat_timeout` vì cấu hình J không có khoá này.
- `ReconcileStorage` được đặt tên theo activity cục bộ của phân hệ I.
- `RetryStage` và `RegenerateFromStage` là signal gắn trên `VideoProductionWorkflow`; `CreateNewVariant` và `RunDebugStage` là signal gắn trên `ProductionBatchWorkflow`.

## 5. Giới hạn và Hạng mục PENDING

- Activity của A (`PlanCollectionCycle`), C, I, J và 2 activity nội bộ chưa có mã service thực thi trong `src/`, nên handler mặc định hoạt động theo cơ chế fail-closed `unbound_handler` (trả lỗi `ACTIVITY_SERVICE_UNBOUND`). Chỉ các activity A (`CollectSource`), B, D, E, F có handler thực tế được nối qua composition root.
- Các stage `dedup`, `enrich_ai`, `media`, `index`, `allocate`, `run_videos`, `backup_check` chưa có activity đăng ký thực tế, được đánh dấu vào danh sách `unbound`.
- Cơ chế fan-out tự động của stage `collect` theo kết quả của `PlanCollectionCycle` chưa được kích hoạt ở slice này (tham số `item_refs` do caller cấp trực tiếp).
- Nghiệm thu luồng hoàn tất video trong kiểm thử đi qua use case `CommitVideoCompletion` thật của CP-5 với Unit of Work trong bộ nhớ; adapter PostgreSQL thực tế đã được kiểm chứng ở CP-5.
- Kiểm thử đăng ký workflow sử dụng API nội bộ `temporalio.workflow._Definition` để đối soát mà không cần máy chủ ngoài.

## 6. Tuyên bố an toàn bắt buộc

- **KHÔNG** có replay trên Temporal Server thật (nội dung replay máy chủ thật thuộc trách nhiệm gói `CP7-G-03`, không tuyên bố ở slice này).
- Tuyệt đối không gọi dịch vụ mạng thật, không đọc tệp bí mật hay thư mục `Credentials/`.
- Tệp `src/main.py` chưa gọi mô-đun `src/controlplane/api/wiring/workflow.py`.

## 7. Trạng thái Backlog

| Mã hạng mục | Trạng thái | Ghi chú |
| --- | --- | --- |
| `BL-CV-09` | PENDING | Đổi A-18 sang GrantClaims, cần khóa LOCK-SRC-SOURCE-INGESTION do Control xác nhận |
| `BL-CV-10` | PENDING | api/wiring/workflow.py chờ CP-2D-REGISTRY, CP-2B-PACKAGES, CP-5-COMPLETION PASS |
| `BL-CV-15` | PENDING | Không loại CP-6 khỏi kế hoạch; replay Temporal thật thuộc CP7-G-03 |
| `BL-CV-06` | PENDING | Tích hợp toàn diện |

> **Quy chuẩn chốt cổng:** Cổng GATE-CP-6-WORKFLOW do Control thả khi có Auditor PASS; Worker không tự thả cổng.
