# Kế hoạch hội tụ mở rộng — IMPL-PLAN-CONVERGENCE-EXT

- **Mã gói**: IMPL-PLAN-CONVERGENCE-EXT (planning_package)
- **Ngày lập**: 20/10/2026
- **Cơ sở**: HEAD bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc, mở rộng docs/implementation/convergence/plan.md, giữ nguyên mọi cạnh phụ thuộc của kế hoạch đó (mục 11.1 của kế hoạch gốc)
- **Nguồn quyền**: ủy quyền AI_SETUP, chỉ thị user duyệt Phần B ngày 18/10/2026, quyết định (3) của user ngày 20/10/2026 về hai cạnh state machine (ARCHITECTURE_CHANGE đã duyệt) và ghi chú Control về ba pin D9
- **Trạng thái**: kế hoạch, PRODUCTION_ACTIVATION_BLOCKED vẫn hiệu lực, không push, không merge, không chạm main hay backup
- **Slice**: docs/implementation/convergence-ext/slices.md
- **Bằng chứng**: docs/delivery-evidence/impl-plan-convergence-ext/report.md

## 1. Phạm vi và nguyên tắc

1. Kế hoạch nhận phần việc nằm ngoài phong bì của IMPL-PLAN-CONVERGENCE: BL-CV-01, 06, 08, 09, 10, 11, 14, 15, ba pin D9 và hai cạnh state machine PUC-J-03, YC-HT-I-04; Control API và giao diện của BL-CV-02, 05, 07, 12 thuộc IMPL-PLAN-CONVERGENCE-EXT-UI.
2. Đúng sáu slice: CP-2B-RUNTIME-PATHS, CP-2B-PACKAGES, CP-2D-REGISTRY, CP-3C-STATE-EDGES, CP-5-COMPLETION, CP-6-WORKFLOW; ba mã CP-2D-REGISTRY, CP-5-COMPLETION, CP-6-WORKFLOW khớp từng ký tự với ba cổng GATE-CP-2D-REGISTRY, GATE-CP-5-COMPLETION, GATE-CP-6-WORKFLOW; bản của ba slice này thay bản cùng mã trong kế hoạch gốc (Control không biên dịch hai bản); không dùng mã slice của IMPL-PLAN-CONVERGENCE hay của IMPL-PLAN-CONVERGENCE-EXT-UI.
3. Mỗi slice chỉ sửa trong ownedPaths, giữ khóa tài nguyên và LOCK-CONVERGENCE nên chạy tuần tự.
4. Không sửa kế hoạch phân hệ A đến J; không sửa docs/milestones/**/evidence/** (LOCK-ACCEPTED-EVIDENCE).
5. Không thêm thư viện, không bịa giá trị pin; mục chưa được user duyệt ghi pendingUserCheckpoint.
6. Fixture và fake chỉ chứng minh logic; việc cần Drive/OAuth, GPU, AI trả phí hoặc chạy 12 giờ thuộc CP7.

## 2. Bảng ánh xạ BL-CV sang slice và cổng Portfolio

Mỗi mã BL-CV dưới đây là việc nằm ngoài phong bì của IMPL-PLAN-CONVERGENCE; trạng thái PENDING nghĩa là đã có slice nhưng chưa làm, chỉ xong khi slice có Auditor PASS và cổng được thả.

| Mã | Slice xử lý | Việc | Cổng thả | Trạng thái |
| --- | --- | --- | --- | --- |
| BL-CV-01 | CP-2D-REGISTRY | toàn bộ ownedPaths của CP-2D (docs/parallel-delivery/**, tests/fixtures/contracts/**, docs/10-test-strategy.md, docs/modules/capability-*.md, README.md, CHANGELOG.md, HANDOFF.md) | GATE-CP-2D-REGISTRY | PENDING |
| BL-CV-06 | CP-2D-REGISTRY | thêm mẫu src/controlplane/api/wiring/** vào PATH-COMPOSITION-ROOT (D8-CV-05) | GATE-CP-2D-REGISTRY | PENDING |
| BL-CV-08 | CP-5-COMPLETION | src/controlplane/api/wiring/completion.py nối completion vào composition root | GATE-CP-5-COMPLETION | PENDING |
| BL-CV-11 | CP-5-COMPLETION | src/controlplane/infrastructure/db/orchestration/postgres_completion.py và tests/integration/convergence/test_cp5_completion_uow.py | GATE-CP-5-COMPLETION | PENDING |
| BL-CV-09 | CP-6-WORKFLOW | A-18 sang GrantClaims (YC-HT-G-10) ở src/source_ingestion/worker/activity_handler.py và tests/integration/collection/test_a18_worker_activity.py | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-10 | CP-6-WORKFLOW | src/controlplane/api/wiring/workflow.py | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-15 | CP-6-WORKFLOW | toàn bộ ownedPaths của CP-6 | GATE-CP-6-WORKFLOW | PENDING |
| BL-CV-14 | CP-2B-RUNTIME-PATHS (tools/runtime/runtime.lock.json) và CP-2B-PACKAGES (ba __init__.py, src/controlplane/pyproject.toml) | ghi ba pin D9; khai bốn gói và tạo ba __init__.py rỗng | GATE-CP-2B-DEPS-PATHS | PENDING |

Hai cạnh state machine PUC-J-03 và YC-HT-I-04 do CP-3C-STATE-EDGES xử lý; slice này không thả cổng Portfolio nào và chạy sau CP-3B-STATE-MACHINE và CP-2D-REGISTRY (mục 4).

**GIẢ ĐỊNH**: GATE-CP-2B-DEPS-PATHS chỉ được thả khi cả CP-2B-RUNTIME-PATHS và CP-2B-PACKAGES đạt Auditor PASS; Control đối chiếu với Portfolio khi biên dịch. Các slice đang chờ CP-2B-DEPS (CP-4-WIRING, CP-6-WORKFLOW) giữ cạnh đó và chờ thêm cổng này; không bỏ cạnh nào.

## 3. Ba pin D9 trong tools/runtime/runtime.lock.json (CP-2B-RUNTIME-PATHS)

Ba giá trị chép nguyên văn từ ghi chú Control trong policy ngày 20/10/2026 (D9 ghim theo vật phẩm đã đo); kế hoạch và Worker không đo lại, không đoán, không bịa.

| Khóa pin | Vật phẩm đã đo | sha256 (hex 64 ký tự) | status |
| --- | --- | --- | --- |
| ffmpeg | C:\ffmpeg\bin\ffmpeg.exe, FFmpeg gyan.dev 2025-03-13-git-958c46800e-essentials_build (GPL v3; có libass, subtitles, h264_nvenc, libx264, loudnorm); ghim là sha256 của tệp ffmpeg.exe | f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480 | PINNED |
| postgresql_image | image postgres:18.6, digest sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280 (ghi phần hex sau sha256:) | 4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280 | PINNED |
| temporal_server_binary | image 	emporalio/server:1.31.2 (thay temporal-server.exe ở R7 của kế hoạch gốc), digest sha256:b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da | b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da | PINNED |

- Cấu trúc tệp theo mục 4 của kế hoạch gốc:
ersions đúng sáu khóa python 3.13.15, uv 0.12.13, node 22.17.0, npm 10.9.2, postgresql 18.6, temporal_server 1.31.2; pins đúng ba khóa trên, mỗi khóa có sha256 và status = PINNED; riêng ffmpeg thêm rchive_name = 2025-03-13-git-958c46800e-essentials_build (nhãn build theo ghi chú Control, không phải tên tệp archive) và measured_artifact =
fmpeg.exe.
- Khóa 	emporal_server_binary giữ tên của CP-2B-DEPS nhưng giá trị là digest image 	emporalio/server:1.31.2; sha256 của ffmpeg là của ffmpeg.exe, không phải của archive.
- Không có giá trị
ull hay BLOCKED trong tệp vì cả ba đã đo.
- Tệp thuộc ownedPaths của CP-2B-RUNTIME-PATHS; CP-2B-DEPS đã biên dịch không chứa tệp này, nếu Control mở phong bì cho CP-2B-DEPS thì phần ghi tệp vẫn chỉ có một owner.
- Định dạng đầu ra 1080x1920, 30 fps, H.264 (NVENC, libx264 dự phòng), AAC, MP4 là quyết định Control, không ghi vào tệp pin.

## 4. Hai cạnh state machine đã duyệt (CP-3C-STATE-EDGES)

1. Nguồn quyền: quyết định (3) của user ngày 20/10/2026, ARCHITECTURE_CHANGE đã duyệt, mở đúng hai cạnh thoát; giữ nguyên PUC-G-02 (khoảng trống CT-STATE-008) và mọi cạnh khác của CT-STATE; không mở thêm cạnh nào. Đây là ngoại lệ có chủ đích của quy tắc cấm sửa docs/09-contracts/** của kế hoạch gốc, chỉ cho CT-STATE-012, CT-STATE-013 và chỉ trong CP-3C-STATE-EDGES.
2. Bảng chi tiết hai cạnh state machine:

| Mã | Cạnh | Hiện hành | Thay đổi | Nơi sửa |
| --- | --- | --- | --- | --- |
| PUC-J-03 | ExternalAccount DEGRADED hoặc INVALID → ENABLED khi lần kiểm của chính tài khoản đạt | ACCOUNT_EDGES ở src/controlplane/domain/config_security/status_graph.py có 5 cạnh, DEGRADED và INVALID không có cạnh thoát | thêm đúng (DEGRADED, ENABLED) và (INVALID, ENABLED), tổng 7 cạnh; REVOKED vẫn chỉ kích hoạt lại bằng credential version mới; hàm thuần trong external_account.py; dịch vụ phục hồi AccountRecoveryService nhận AccountTestReceipt của ExternalAccountTester, chỉ phục hồi khi ok đúng và khớp tài khoản, không tự probe | status_graph.py, external_account.py, src/controlplane/application/config_security/account_recovery.py (mới) |
| YC-HT-I-04 | artifact location CLEANUP_AUTHORIZED → DELETED, chỉ qua đường ghi có bằng chứng cleanup | đồ thị miền statemachine đã có cạnh nhưng ArtifactLocationStore.validate_transition luôn từ chối DELETED | thêm ArtifactLocationStore.record_cleanup_deleted là đường ghi duy nhất sang DELETED, đòi CleanupAuthorization khớp location, artifact version và hash, cleanup_deleted đúng (kết quả CleanupResult.deleted của LocalCleanupExecutor) và cleanup_receipt_ref không rỗng; 	ransition và
alidate_transition vẫn từ chối DELETED | src/controlplane/application/storage_meta/__init__.py |

3. Contract và registry trong cùng slice: sửa CT-STATE-013 và CT-STATE-012 trong docs/09-contracts/12-state-machines.md; cập nhật source_sha256 và current_revision của CONTRACT-STATE-MACHINES trong docs/parallel-delivery/contract-registry.yaml (hiện cùng là 2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28) bằng sha256 byte tệp contract sau khi sửa, tính bằng probe, không gõ tay.
4. Thứ tự: sau CP-3B-STATE-MACHINE và CP-2D-REGISTRY (cùng sửa registry và giữ LOCK-CONTRACT-STATE-MACHINES). Test hiện có phải sửa: tests/unit/config/test_j_status_graph.py (đang khẳng định 5 cạnh và DEGRADED, INVALID không có cạnh thoát). Test M2 giữ nguyên byte; Control chạy tests/m2 trên PostgreSQL 18.6 sau slice.
5. Mục mở OI-EXT-01: nơi lưu cleanup_receipt_ref ngoài receipt của cleanup executor; gói này không thêm cột hay migration, mặc định đơn giản là chỉ kiểm bằng chứng khi ghi.

## 5. Các BL-CV còn lại (không tuyên bố đã làm)

| Mã | Trạng thái | Lý do | Nơi xử lý |
| --- | --- | --- | --- |
| BL-CV-02 | PENDING | đăng ký event kind ở src/controlplane/application/sse/event_catalog.py nằm ngoài phong bì của gói này; thuộc phần Control API | slice CP-4-EVENT-KINDS của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-05 | PENDING | query CT-API-002 còn thiếu cần kho PERSIST của từng phân hệ; thuộc Control API | slice CP-4-QUERIES của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-07 | PENDING | nối màn hình vào shell chỉ khi route CP-4 tương ứng tồn tại; thuộc giao diện | slice CP-4B-UI-SCREENS của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-12 | PENDING | bỏ LIMIT 100 và next_cursor None, phân trang keyset; thuộc Control API | slice CP-4-PAGINATION của IMPL-PLAN-CONVERGENCE-EXT-UI |
| BL-CV-03 | ĐÃ ĐÓNG | RoutedInvocationService (J-18) đã có ở src/controlplane/application/config_security/routed_invocation.py, nên CP-4 chỉ nối qua api/wiring | không còn việc; không có slice trong kế hoạch này |
| BL-CV-04 | PENDING | thay host mock-9router trong DEFAULT_APPROVED_ENDPOINTS làm hỏng tests/unit/security/test_http_router_adapter.py, tệp ngoài phong bì | slice ADAPT-D của IMPL-PLAN-ADAPT |
| BL-CV-13 | BLOCKED theo quyết định | nút kiểm thử (handleTriggerTestError, prop onOpenTestError ở components/Header.tsx), đường /test-driver và năm spec M2 đóng băng giữ nguyên byte; theo quyết định Control về phiên sản xuất, hồ sơ production tắt route test-driver ở phía máy chủ, UI và spec M2 giữ nguyên | không sửa ở kế hoạch này; không có slice trong kế hoạch này; giữ BLOCKED |

Không mục nào ở bảng này được ghi là đã làm; các slice CP-4-EVENT-KINDS, CP-4-QUERIES, CP-4B-UI-SCREENS, CP-4-PAGINATION không nằm trong slices.md của kế hoạch này.

## 6. Thứ tự, khóa và DAG

| Slice | dependsOn chính | Khóa tài nguyên | Cổng thả |
| --- | --- | --- | --- |
| CP-2B-RUNTIME-PATHS | IMPL-PLAN-CONVERGENCE, IMPL-PLAN-CONVERGENCE-EXT | LOCK-DEPENDENCY-UNIVERSE, LOCK-CONVERGENCE | GATE-CP-2B-DEPS-PATHS (cùng CP-2B-PACKAGES) |
| CP-2B-PACKAGES | IMPL-PLAN-CONVERGENCE, IMPL-PLAN-CONVERGENCE-EXT | LOCK-DEPENDENCY-UNIVERSE, LOCK-CONVERGENCE | GATE-CP-2B-DEPS-PATHS |
| CP-2D-REGISTRY | CP1-CONTRACT-BINDING, CP2A-LAYOUT, IMPL-PLAN-CONVERGENCE, IMPL-PLAN-CONVERGENCE-EXT | LOCK-PARALLEL-REGISTRY, LOCK-DOC-AUTHORITY, LOCK-DOC-INDEX, LOCK-CONVERGENCE | GATE-CP-2D-REGISTRY |
| CP-3C-STATE-EDGES | CP-3B-STATE-MACHINE, CP-2D-REGISTRY, IMPL-PLAN-CONVERGENCE-EXT | LOCK-CONTRACT-STATE-MACHINES, LOCK-CONTRACT-SOURCE, LOCK-PARALLEL-REGISTRY, LOCK-SRC-STORAGE, LOCK-SRC-CONFIG-SECURITY, LOCK-CONVERGENCE | không thả cổng Portfolio |
| CP-5-COMPLETION | CP-3-MIGRATIONS, CP-4-WIRING, GATE-PERSIST-C, GATE-PERSIST-G, GATE-PERSIST-I, CP-2D-REGISTRY, CP-2B-PACKAGES | LOCK-SRC-ORCHESTRATION, LOCK-COMPOSITION-ROOT, LOCK-POSTGRES-TEST-DB, LOCK-CONVERGENCE | GATE-CP-5-COMPLETION |
| CP-6-WORKFLOW | USER-CKPT-D9-D10, CP-2B-DEPS, CP-5-COMPLETION, CP-2D-REGISTRY, CP-2B-PACKAGES | LOCK-SRC-ORCHESTRATION, LOCK-SRC-SOURCE-INGESTION, LOCK-COMPOSITION-ROOT, LOCK-CONVERGENCE | GATE-CP-6-WORKFLOW |

Cạnh gốc giữ nguyên: CP-3B-STATE-MACHINE chờ CP-2D-REGISTRY; CP-4-WIRING và CP-4B-UI-SHELL chờ CP-2D-REGISTRY; CP-5-COMPLETION chờ GATE-PERSIST-C, GATE-PERSIST-G, GATE-PERSIST-I; CP-6-WORKFLOW chờ CP-5-COMPLETION. Cạnh tới adapter PostgreSQL luôn viết GATE-PERSIST-<X> trong slices.md. Slice giữ LOCK-CONVERGENCE nên chạy tuần tự.

## 7. Mục mở và danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10 (thư viện và cách dựng lại runtime; ba pin đã có theo Control, không thay cho checkpoint này)
- PUC-G-02 giữ nguyên, không mở cạnh nào
- OI-EXT-01 (mục 4)
- Điểm dừng user duy nhất của v1 trước nghiệm thu mẫu là OAuth Drive một lần
- Nghiệm thu cuối gồm checkpoint M2 và ngoại lệ CP-2C
- Không mục nào được ghi là đã duyệt.

## 8. Ngoài phạm vi

Mã nguồn src/**, migration, sửa kế hoạch phân hệ A đến J, sửa docs/milestones/**/evidence/**, Control API và giao diện của BL-CV-02, 05, 07, 12, tài nguyên thật (CP7), kích hoạt sản xuất, push, merge.
