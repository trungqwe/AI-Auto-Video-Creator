# Báo cáo bằng chứng IMPL-PLAN-CONVERGENCE-EXT

- Task: `IMPL-PLAN-CONVERGENCE-EXT` (planning_package)
- Trigger: `REVIEW_FINDINGS` (vòng sửa F1; lần đầu là `INITIAL`)
- Cơ sở: HEAD `bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc`
- Tệp tạo mới:
  - `docs/implementation/convergence-ext/plan.md`
  - `docs/implementation/convergence-ext/slices.md` (sáu slice CP-2B-RUNTIME-PATHS, CP-2B-PACKAGES, CP-2D-REGISTRY, CP-3C-STATE-EDGES, CP-5-COMPLETION, CP-6-WORKFLOW)
  - `docs/delivery-evidence/impl-plan-convergence-ext/report.md`
- Không sửa `src/**`, `docs/09-contracts/**`, `docs/parallel-delivery/**`, kế hoạch phân hệ A đến J, `docs/milestones/**/evidence/**`.
- Nguồn đọc: `docs/implementation/convergence/plan.md`, `docs/implementation/convergence/slices.md`, `docs/09-contracts/12-state-machines.md`, `docs/parallel-delivery/contract-registry.yaml`, `src/controlplane/domain/config_security/status_graph.py`, `src/controlplane/application/storage_meta/__init__.py`, `src/controlplane/pyproject.toml`.

## Nguồn đọc và SHA-256

Danh sách các tệp nguồn đã đọc, kèm đường dẫn và SHA-256:

| Đường dẫn | SHA-256 | Ghi chú |
| --- | --- | --- |
| `docs/implementation/convergence/plan.md` | `dc998d8cc60d7f8bd2141788f7ac83278b3d084be12912a1e5d920bffa1501d5` | Kế hoạch hội tụ gốc, cơ sở DAG và các mục BL-CV |
| `docs/implementation/convergence/slices.md` | `0f18fbad94a959cb50668f3ff3202b79e12782fb4912c29750a644459228e322` | Slices gốc, nguồn cho CP-2D, CP-5, CP-6 |
| `docs/09-contracts/12-state-machines.md` | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` | Hợp đồng CT-STATE-012 và CT-STATE-013 |
| `docs/parallel-delivery/contract-registry.yaml` | `bffe38f354cbd327ee62330e93d99ae1be545de8fa9431edf25a8ad17da03c90` | Mục CONTRACT-STATE-MACHINES ghi revision và source_sha256 cũ |
| `src/controlplane/domain/config_security/status_graph.py` | `d4aece29c0261ad78ce02cbcbf80116f1c1e97008ff251879f2faec8c83406dd` | ACCOUNT_EDGES hiện có 5 cạnh, DEGRADED và INVALID chưa có cạnh thoát |
| `src/controlplane/application/storage_meta/__init__.py` | `34b0072b61ea5d0bd4823a0c1b771417e2155c6ac392d9b1208f8e1d15ebdd11` | ArtifactLocationStore và validate_transition hiện từ chối DELETED |
| `src/controlplane/pyproject.toml` | `9258c4a18f6d100654f883e629d8a50595f08cc11ee8ee89efc4a7af6ed44b1d` | Danh sách packages và tool.setuptools.package-dir |
| `IMPL-PLAN-CONVERGENCE-EXT.md` | `679e7207b81ad5a456be9f855fb65de4f30885eea1a9a5acce4317747b3136fb` | Spec và lệnh làm việc từ Orchestrator |

## Ánh xạ

Nhắc plan.md mục 2 (BL-CV-01, 06, 08, 09, 10, 11, 14, 15) và mục 5 (BL-CV-02, 05, 07, 12 ở IMPL-PLAN-CONVERGENCE-EXT-UI; BL-CV-03 đã đóng; BL-CV-04 ở ADAPT-D; BL-CV-13 BLOCKED), nêu rõ không có mục nào được ghi là đã làm.

### 1. Bảng ánh xạ BL-CV sang slice và cổng Portfolio (plan.md mục 2)

| Mã | Slice xử lý | Việc | Cổng thả | Trạng thái |
| --- | --- | --- | --- | --- |
| BL-CV-01 | CP-2D-REGISTRY | toàn bộ ownedPaths của CP-2D (docs/parallel-delivery/**, tests/fixtures/contracts/**, docs/10-test-strategy.md, docs/modules/capability-*.md, README.md, CHANGELOG.md, HANDOFF.md) | GATE-CP-2D-REGISTRY | PENDING |
| BL-CV-06 | CP-2D-REGISTRY | thêm mẫu src/controlplane/api/wiring/** vào PATH-COMPOSITION-ROOT (D8-CV-05) | GATE-CP-2D-REGISTRY | PENDING |
| BL-CV-08 | CP-5-COMPLETION | src/controlplane/api/wiring/completion.py nối completion vào composition root | GATE-CP-5-COMPLETION | PENDING |
| BL-CV-11 | CP-5-COMPLETION | src/controlplane/infrastructure/db/orchestration/postgres_completion.py và tests/integration/convergence/test_cp5_completion_uow.py | GATE-CP-5-COMPLETION | PENDING |
| BL-CV-09 | CP-6-WORKFLOW | A-18 sang GrantClaims (YC-HT-G-10) ở src/source_ingestion/worker/activity_handler.py và tests/integration/collection/test_a18_worker_activity.py | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-10 | CP-6-WORKFLOW | src/controlplane/api/wiring/workflow.py | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-15 | CP-6-WORKFLOW | toàn bộ ownedPaths của CP-6 | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-14 | CP-2B-RUNTIME-PATHS (tools/runtime/runtime.lock.json, hai __init__.py của api/wiring và application/orchestration/workflows) và CP-2B-PACKAGES (src/controlplane/pyproject.toml) | ghi ba pin D9; tạo hai __init__.py rỗng; khai ba gói api.wiring, orchestration.workflows, infrastructure.storage | GATE-CP-2B-DEPS-PATHS | PENDING |

### 2. Các BL-CV còn lại (plan.md mục 5)

| Mã | Trạng thái | Lý do | Nơi xử lý |
| --- | --- | --- | --- |
| BL-CV-02 | PENDING | đăng ký event kind ở src/controlplane/application/sse/event_catalog.py nằm ngoài phong bì của gói này; thuộc phần Control API | slice CP-4-EVENT-KINDS của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-05 | PENDING | query CT-API-002 còn thiếu cần kho PERSIST của từng phân hệ; thuộc Control API | slice CP-4-QUERIES của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-07 | PENDING | nối màn hình vào shell chỉ khi route CP-4 tương ứng tồn tại; thuộc giao diện | slice CP-4B-UI-SCREENS của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-12 | PENDING | bỏ LIMIT 100 và next_cursor None, phân trang keyset; thuộc Control API | slice CP-4-PAGINATION của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-03 | ĐÃ ĐÓNG | RoutedInvocationService (J-18) đã có ở src/controlplane/application/config_security/routed_invocation.py, nên CP-4 chỉ nối qua api/wiring | không còn việc; không có slice trong kế hoạch này |
| BL-CV-04 | PENDING | thay host mock-9router trong DEFAULT_APPROVED_ENDPOINTS làm hỏng tests/unit/security/test_http_router_adapter.py, tệp ngoài phong bì | slice ADAPT-D của IMPL-PLAN-ADAPT |
| BL-CV-13 | BLOCKED theo quyết định | nút kiểm thử (handleTriggerTestError, prop onOpenTestError ở components/Header.tsx), đường /test-driver và năm spec M2 đóng băng giữ nguyên byte; theo quyết định Control về phiên sản xuất, hồ sơ production tắt route test-driver ở phía máy chủ, UI và spec M2 giữ nguyên | không sửa ở kế hoạch này; không có slice trong kế hoạch này; giữ BLOCKED |

Không mục nào ở các bảng trên được ghi là đã làm.

## Pin D9

Ba giá trị chép từ ghi chú Control, không tự đo, không đoán, không bịa giá trị:

| Khóa pin | Vật phẩm đã đo | sha256 (hex 64 ký tự) | status |
| --- | --- | --- | --- |
| ffmpeg | C:\ffmpeg\bin\ffmpeg.exe, FFmpeg gyan.dev 2025-03-13-git-958c46800e-essentials_build (GPL v3; có libass, subtitles, h264_nvenc, libx264, loudnorm); ghim là sha256 của tệp ffmpeg.exe | f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480 | PINNED |
| postgresql_image | image postgres:18.6, digest sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280 (ghi phần hex sau sha256:) | 4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280 | PINNED |
| temporal_server_binary | image 	emporalio/server:1.31.2 (thay temporal-server.exe ở R7 của kế hoạch gốc), digest sha256:b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da | b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da | PINNED |

## Hai cạnh

PUC-J-03 và YC-HT-I-04 thuộc CP-3C-STATE-EDGES, PUC-G-02 giữ nguyên, chưa sửa contract hay registry ở gói này.

- **PUC-J-03**: ExternalAccount ở DEGRADED hoặc INVALID quay lại ENABLED khi lần kiểm CT-ACC-002 của chính tài khoản đạt; REVOKED vẫn là terminal; hàm thuần trong `external_account.py` và dịch vụ phục hồi `AccountRecoveryService` ở `src/controlplane/application/config_security/account_recovery.py`.
- **YC-HT-I-04**: ArtifactLocation CLEANUP_AUTHORIZED sang DELETED, chỉ qua đường ghi có bằng chứng cleanup `record_cleanup_deleted` ở `src/controlplane/application/storage_meta/__init__.py`; `transition` và `validate_transition` vẫn từ chối DELETED.
- **Nguồn quyền**: Quyết định (3) của user ngày 20/10/2026 (ARCHITECTURE_CHANGE đã duyệt); giữ nguyên PUC-G-02 và mọi cạnh khác của CT-STATE.
- **Contract và Registry**: Việc sửa `docs/09-contracts/12-state-machines.md` (CT-STATE-012, CT-STATE-013) và cập nhật `source_sha256`, `current_revision` của CONTRACT-STATE-MACHINES trong `docs/parallel-delivery/contract-registry.yaml` được thực hiện trong cùng slice `CP-3C-STATE-EDGES`, không thực hiện ở gói này.

## Lệnh kiểm

Interpreter khóa đã dùng: Python 3.13.12 (`C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe`).

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Đạt. Không có khoảng trắng cuối dòng hay xung đột marker. |
| Probe Bước 17 (Cấu trúc 6 slice, độ dài khối, cạnh GATE-PERSIST-*, tên cổng, NFC, tiếng Việt đủ dấu) | 0 | Đạt. Đúng 6 slice, mỗi khối <= 7000 ký tự (lớn nhất 6490), tổng khối = 23751 <= 38000 ký tự, cạnh GATE-PERSIST-* chuẩn xác, không có chr(65533). |
| Probe Bước 18 (Kiểm tra plan.md: 15 mã BL-CV, 3 pin hex, 4 mã cổng, tên module ngoài, tiếng Việt có dấu > 500) | 0 | Đạt. Đủ 15 mã BL-CV-01..15, đủ 3 pin hex, đủ 4 mã cổng, diacritics > 500, không mất dấu. |
| Probe Bước 19 (Kiểm tra slices.md: kind, locks, GATE-PERSIST-C, old hash trong CP-3C, cấm UI slice ids) - Lần 1 | 1 | Không đạt (`AssertionError: old hash recorded` do khối CP-3C ban đầu chưa ghép đủ phần acceptance 2). |
| Probe Bước 19 (Kiểm tra slices.md: kind, locks, GATE-PERSIST-C, old hash trong CP-3C, cấm UI slice ids) - Lần 2 | 0 | Đạt. Khối CP-3C chứa đầy đủ acceptance 1, acceptance 2 với old hash 64 ký tự, testCommands và notes; toàn bộ 6 khối đều đạt kiểm tra. |

## Vòng sửa REVIEW_FINDINGS (F1)

- F1 (MAJOR) đã xử lý: đưa ownedPaths về đúng phong bì acceptance. CP-3C-STATE-EDGES bỏ hai tệp test mới `tests/unit/config/test_j_account_recovery.py` và `tests/unit/storage/test_i_cleanup_deleted.py`; các test mới nằm trong `tests/unit/config/test_j_status_graph.py`. CP-2B-PACKAGES bỏ `api/routes/modules/__init__.py` và việc khai gói tương ứng (OI-EXT-02), chuyển hai `__init__.py` của `api/wiring` và `application/orchestration/workflows` sang CP-2B-RUNTIME-PATHS, thêm cạnh `CP-2B-RUNTIME-PATHS` vào dependsOn.
- F2, F3 (MINOR) không sửa trong vòng này theo kỷ luật hội tụ, đưa vào backlog.
- Lệnh kiểm vòng này (chạy bằng interpreter khóa của lane):

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Đạt. Không có lỗi khoảng trắng hay xung đột marker. |
| Probe bắt buộc của task (bước 6) | 0 | Đạt. Đúng 6 slice, mỗi khối <= 7000 ký tự, tổng khối <= 38000 ký tự, cạnh GATE-PERSIST-* chuẩn xác, không có chr(65533). |
| Probe đối chiếu F1 (bước 7) | 0 | Đạt. Hai init nằm ở runtime-paths, packages không sở hữu init và phụ thuộc runtime-paths, routes/modules không còn trong slices.md, không còn test_j_account_recovery và test_i_cleanup_deleted, test_j_status_graph.py vẫn được sở hữu. |

## Mục mở

## 7. Mục mở và danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10 (thư viện và cách dựng lại runtime; ba pin đã có theo Control, không thay cho checkpoint này)
- PUC-G-02 giữ nguyên, không mở cạnh nào
- OI-EXT-01 (mục 4)
- Điểm dừng user duy nhất của v1 trước nghiệm thu mẫu là OAuth Drive một lần
- Nghiệm thu cuối gồm checkpoint M2 và ngoại lệ CP-2C
- Không mục nào được ghi là đã duyệt.
