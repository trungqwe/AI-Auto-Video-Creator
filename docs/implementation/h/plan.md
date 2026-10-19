# Kế hoạch triển khai Phân hệ H — Giao diện quản trị

> Task: `IMPL-PLAN-H` (planning_package), trigger INITIAL. Base: `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4`.
> Nguồn quyền: D3 — user duyệt Phần B ngày 18/10/2026; M3–M7 theo ủy quyền AI_SETUP. Kích hoạt sản xuất vẫn `PRODUCTION_ACTIVATION_BLOCKED`.
> Đây là kế hoạch; mã nguồn do các slice trong `docs/implementation/h/slices.md` thực hiện.

## 1. Nguồn chuẩn

- `docs/09-contracts/01-control-api-and-stream.md` (CT-API-001..010, mục 9 acceptance; sha256 `ea16fe04759e6bdf3b7bdde3e27ad498d13a271bd45d412ba0e9068a9b918e12` theo `docs/delivery-evidence/cp1-contract-binding/report.md`) — nguồn chính của H
- `docs/09-contracts/02-domain-events.md` (CT-EVT-002/003), `docs/09-contracts/12-state-machines.md` (CT-STATE-008, CT-STATE-009, CT-STATE-010)
- `docs/milestones/m2-control-plane/spec.md` (mục 9 nền tảng Phân hệ H, dòng 27–29; bố cục `src/controlplane`, dòng 85–90)
- `docs/11-roadmap.md`: §8 (M2: năng lực H dòng 245, lát cắt dòng 247–259, exit gate dòng 271–278), §9 (M3, dòng 335–343), §10 (M4, dòng 409–416), §11 (M5, dòng 470–478), §12 (M6, dòng 515 và 526–535), §13 (M7, dòng 550–562 và 578–595), §14 (bản đồ phân hệ, dòng 616), danh sách ROADMAP-OPEN (dòng 765–778)
- `docs/10-test-strategy.md` §12.8 (H — Giao diện quản trị, dòng 420–434), §17.4 (UI và command latency, dòng 690–696), §26 (G07)
- `docs/03-quality-requirements.md` (QR-UX-001..008, QUALITY-OPEN-001/008/011/014)
- `docs/adr/0007-runtime-and-admin-ui.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (phân hệ H dòng 52–55; `PATH-SRC-CONTROL-UI` dòng 178–185; `LOCK-SRC-CONTROL-UI` dòng 433–438)
- `docs/parallel-delivery/bindings/README.md` (seam H ↔ G chưa có binding, dòng 63) và các binding: `domain-event-envelope.json` (BINDING-DOMAIN-EVENT-ENVELOPE 1.0.0), `b-d-production-snapshot.json`, `g-activity-execution.json`, `g-c-i-completion.json`, `i-artifact-version.json`
- `tests/fixtures/contracts/domain-event-envelope/payloads.json`, `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
- `docs/parallel-delivery/errata/m7-integration.md` (mục 1, 2, 5, 6); kế hoạch lân cận để đồng bộ: `docs/implementation/j/plan.md` (YC-HT-J-03, YC-HT-J-05), `docs/implementation/i/plan.md`
- Mã H đã có (chỉ đọc): `src/controlplane/ui/src/**`, `src/controlplane/ui/package.json`, `src/controlplane/api/routes/control.py`, `src/controlplane/api/sse/stream.py`, `src/controlplane/application/sse/stream.py`, `src/controlplane/application/projections/operation_view_mapper.py`, `src/controlplane/application/control_api/query_ports.py`, `src/controlplane/infrastructure/db/control_api_queries.py`, `src/controlplane/infrastructure/db/projections/postgres.py`
- Không có module spec riêng của H (`docs/modules/` không có `capability-h-*.md`); contract 01, ADR-0007 và roadmap là nguồn chuẩn.

### 1.1. Đính chính tài liệu cũ (errata)

Khi mâu thuẫn, contract, catalog test, ADR và errata CP1 thắng tài liệu kế hoạch cũ. Kế hoạch không chép lại các điểm sai dưới đây.

| Mã | Vị trí | Nội dung sai | Nguồn chuẩn và xử lý |
|---|---|---|---|
| ERR-H-01 | `docs/parallel-delivery/M7-integration-execution-package.md` dòng 102–120 | Cây thư mục trùng `src/ui/**`, `src/control_api`, `src/orchestration/**` | Errata m7 mục 1 và D1: H ở `src/controlplane/ui/**` cùng các gói `src/controlplane/...` ở mục 3; không dựng `src/ui`, `src/control_api`, `src/admin` |
| ERR-H-02 | `M7-integration-test-plan.md` dòng 27–74 | Test ID `TST-INT-SSE-*`, `TST-INT-CTL-*` nằm ngoài catalog | Errata m7 mục 6: slice H chỉ ghi mã CT-API, QR-UX và mục 12.8 của test strategy vào `coveredIds`; test ID mới (`TST-UX-*`) phải đăng ký vào `docs/10-test-strategy.md` trước (YC-HT-H-10) |
| ERR-H-03 | `M7-integration-test-plan.md` dòng 45 | Trạng thái job tự đặt `qc_passed`, `completed`, `cloud_verified` | Errata m7 mục 5: `READY_FOR_COMPLETION` → `COMPLETED` chỉ qua CT-ORC-008; H-05 chỉ hiển thị bốn mốc render, QC, upload verified, completion và cấm `completed` khi `upload_verified` sai |
| ERR-H-04 | `M7-integration-test-plan.md` dòng 132–180 | Manifest mẫu điền sẵn kết quả PASS, p95 và số video | Errata m7 mục 2: không phải bằng chứng; bằng chứng thật theo D4; gate tài nguyên thật thuộc CP7 |
| ERR-H-05 | `docs/parallel-delivery/ownership-and-locks.yaml` dòng 178–185 | `PATH-SRC-CONTROL-UI` chỉ liệt kê `src/controlplane/ui/**`, `tests/m2/e2e/**`, `src/controlplane/application/test_driver.py` | D1 giao thêm cho H các gói `application/projections`, `application/sse`, `api/sse`, `api/routes/modules`, `infrastructure/db/projections`, `tests/unit/control_ui`, `tests/integration/control_ui`; registry chưa có các mẫu này nên gửi YC-HT-H-01 |

### 1.2. Khoảng trống của mã H hiện có (GAP-H)

Đây là lỗi hoặc thiếu sót của mã đã có, không phải lỗi tài liệu. Slice chỉ thêm module mới bên cạnh; việc sửa tệp cũ là yêu cầu gửi hội tụ (mục 9).

| Mã | Vị trí | Hiện trạng | Xử lý |
|---|---|---|---|
| GAP-H-01 | `src/controlplane/ui/src/components/OperationsGrid.tsx` dòng 27–34 | Pill chỉ có bốn nhánh; `waiting` và `outcome_unknown` rơi về `pill-accepted` trong khi CT-API-007 có sáu trạng thái | H-01, H-10, H-11, H-12; thay vào lưới là YC-HT-H-03 |
| GAP-H-02 | `src/controlplane/ui/src/api/client.ts` dòng 179–196 | Danh sách `eventKinds` cố định; event có `event: <kind>` ngoài danh sách không tới handler (chỉ `onmessage` nhận event không tên), nên kind của phân hệ thêm sau bị bỏ rơi im lặng | H-03, H-14; wiring YC-HT-H-03 |
| GAP-H-03 | `client.ts` dòng 143 và `src/controlplane/ui/src/App.tsx` dòng 29 | `Set` ID đã thấy không có giới hạn; UI chạy nhiều giờ tăng bộ nhớ vô hạn | H-14 |
| GAP-H-04 | `src/controlplane/ui/src/types/api.ts` dòng 1–14 và 16–23 | `OperationItem` thiếu progress, wait_reason, started_at, updated_at, finished_at, problem; `JobItem` không có revision config hiệu lực (CT-API-009) | H-10, H-06; mở rộng `api.ts` là YC-HT-H-03 |
| GAP-H-05 | `src/controlplane/api/routes/control.py` dòng 23, 45, 81, 103 và `src/controlplane/infrastructure/db/control_api_queries.py` dòng 33, 92, 118, 148 | Luôn trả `next_cursor: None` và `LIMIT 100`; chưa phân trang, lọc, sắp xếp phía server như ADR-0007 | H-02, H-04, H-08; wiring YC-HT-H-04 |
| GAP-H-06 | `App.tsx` dòng 151–164 và `client.ts` dòng 67–95 | Nút kiểm thử XSS và đường `/test-driver/issue-capability` nằm trong mã UI; đường cấp phiên cho bản sản xuất chưa có | YC-HT-H-03, PUC-H-06, CP7-H-05 |
| GAP-H-07 | `src/controlplane/ui/package.json` | Không có test runner TypeScript; chỉ có `build` và `test:e2e` (Playwright cần PostgreSQL thật) | D8-H-01, H-16 |

## 2. Năng lực và aggregate

Aggregate do H sở hữu (ownership-and-locks.yaml dòng 52–55): `AdminReadModel` và `OperationStream`. H là lớp trình bày và read model: không sở hữu dữ liệu nghiệp vụ của A–G, I, J; H chỉ đọc qua port truy vấn do phân hệ đó cung cấp và gửi command qua service của chủ sở hữu.

| # | Năng lực | Contract | Aggregate hoặc thành phần | Slice |
|---|---|---|---|---|
| 1 | Hiển thị operation đủ sáu trạng thái, phân biệt đã nhận với đã hoàn thành | CT-API-007; CT-API mục 9 điều 3 | AdminReadModel | H-01, H-10, H-11, H-12 |
| 2 | Danh sách phân trang, lọc, sắp xếp phía server theo whitelist; workspace chỉ lấy từ identity | CT-API-001, CT-API-002, ADR-0007 | AdminReadModel | H-02, H-04, H-08 |
| 3 | Luồng SSE: dedupe theo `stream_event_id`, reconnect theo cursor, resync bằng query snapshot | CT-API-008 | OperationStream | H-03, H-14 |
| 4 | Lỗi an toàn: ProblemDetail, hover và focus, technical detail theo ref, không stack trace | CT-API-010, CT-API-008 điều 5, QR-UX-004 | — | H-07, H-13 |
| 5 | Sửa metadata theo allowlist với `If-Match` và `Idempotency-Key`; không sửa bài, script, event relation | CT-API-001, CT-API-003, CT-API-004, CT-API-009 | — | H-09, H-15 |
| 6 | Stage run, session, log, capability health và bốn mốc hoàn thành của job | CT-API-002, CT-STATE-008, CT-STATE-009 | AdminReadModel | H-05 |
| 7 | Metadata cấu hình và tài khoản không lộ secret; revision config hiệu lực của từng job | CT-API-006, CT-API-009, CT-API-010 | AdminReadModel | H-06 |
| 8 | Danh mục màn hình theo milestone M2–M7 và quy tắc trường được sửa | Roadmap §14 | — | H-15 |
| 9 | Guard nguồn UI: XSS sink, secret hằng, `fetch` ngoài `api/`, endpoint cấm | CT-API-010; CT-API mục 9 điều 5 và 6 | — | H-16 |

Không dựng aggregate trùng: `OperationStream` đã có repository `PostgresOperationStreamRepository` ở `src/controlplane/infrastructure/db/projections/postgres.py`; cursor và replay ở `SseStreamService` (`src/controlplane/application/sse/stream.py`); trình bày SSE ở `SseStreamPresenter` (`src/controlplane/api/sse/stream.py`); ánh xạ trạng thái ở `map_operation_view` (`src/controlplane/application/projections/operation_view_mapper.py`); port truy vấn ở `src/controlplane/application/control_api/query_ports.py`. Slice chỉ import chỉ đọc các lớp này và thêm module mới bên cạnh, vì `tests/m2/test_p7a_control_api_security.py` và `tests/m2/test_p7b_sse_stream.py` bảo vệ chúng (D8-H-07).

## 3. Vị trí mã theo D1

H mở rộng các gói đã có trong `src/controlplane`; không dựng `src/ui`, `src/control_api`, `src/admin`, `src/orchestration`, `src/storage` hay cây trùng aggregate nào. Một import root `src/`, dạng `controlplane.…`, không dùng tiền tố `src.`.

| Đường dẫn | Vai trò | Slice |
|---|---|---|
| `src/controlplane/ui/src/types/` | Kiểu TypeScript contract view mới: `operationView.ts`, `listPage.ts` | H-10 |
| `src/controlplane/ui/src/features/` | Logic UI thuần: `operations/statusPresentation.ts`, `stream/boundedEventDeduper.ts`, `screens/screenRegistry.ts` | H-11, H-14, H-15 |
| `src/controlplane/ui/src/components/` | Component mới: `StatusPill.tsx`, `ErrorHoverDetail.tsx` | H-12, H-13 |
| `src/controlplane/ui/src/api/` | `streamEventKinds.ts` | H-14 |
| `src/controlplane/application/projections/` | `operation_view_model.py`, `list_query.py`, `ops_read_models.py`, `config_account_views.py` | H-01, H-02, H-05, H-06 |
| `src/controlplane/application/sse/` | `event_catalog.py` | H-03 |
| `src/controlplane/api/sse/` | Không có slice; presenter hiện có giữ nguyên | — |
| `src/controlplane/api/routes/modules/` | `problem_detail.py`, `read_only_listing.py`, `metadata_update.py` (không có `__init__.py`, D8-H-07) | H-07, H-08, H-09 |
| `src/controlplane/infrastructure/db/projections/` | `list_queries.py` (dựng SQL tham số hóa, không kết nối thật) | H-04 |
| `tests/unit/control_ui/` | Test đơn vị `test_h_<chủ đề>.py` | tất cả trừ H-04 |
| `tests/integration/control_ui/` | `test_h_list_queries_sql.py` (connection giả, không PostgreSQL) | H-04 |

Không sửa tệp đã có trong các thư mục trên: `operation_view_mapper.py`, `application/sse/stream.py`, `api/sse/stream.py`, `infrastructure/db/projections/postgres.py`, `ui/src/api/client.ts`, `ui/src/types/api.ts`, các component hiện có. Không chạm `App.tsx`, `index.css`, `ui/dist`, `package.json`, `package-lock.json`, `src/controlplane/api/routes/control.py`, `src/controlplane/api/main.py`, migration, `tests/m2/**`: các tệp này là tài nguyên dùng chung của hội tụ (mục 9).

Pytest dùng `pythonpath = ["src"]` trong `pyproject.toml`. Không thêm `__init__.py` vào thư mục test mới; tiền tố `test_h_` giữ tên tệp test duy nhất trong repo.

## 4. Contract dùng và cung cấp

### 4.1. H cung cấp

| Contract | Binding | Ghi chú |
|---|---|---|
| CONTRACT-CONTROL-API-STREAM: CT-API-002 (query), CT-API-007 (`OperationView`), CT-API-008 (`OperationStream`) | Chưa có binding (`docs/parallel-delivery/bindings/README.md` dòng 63, seam H ↔ G); hiện được bảo vệ bởi `tests/m2` | H-01, H-03, H-10 khóa tên trường theo văn bản `docs/09-contracts/01-control-api-and-stream.md` bằng test đọc tệp; mở binding và fixture là YC-HT-H-07, fail-closed |
| CT-API-001, CT-API-003, CT-API-004 (command, `If-Match`, `Idempotency-Key`) | Chưa có binding | H-07, H-08, H-09 chỉ dựng lớp route mẫu với service giả; command thật do phân hệ chủ sở hữu cung cấp qua YC-HT-H-04 |
| CT-API-010 (bảo mật biên UI) | Không có binding; bảo vệ bởi `tests/m2/test_p7a_control_api_security.py` | H-16 thêm guard tĩnh phía UI, không thay test hiện có |

### 4.2. H dùng

| Binding hoặc mã | Trường H dùng | Slice |
|---|---|---|
| `domain-event-envelope.json` (BINDING-DOMAIN-EVENT-ENVELOPE 1.0.0) | `forbidden_fields` (`secret_value`, `raw_oauth_response`, `stack_trace`, `blob`) và `sensitivity`: payload hiển thị không chứa các khóa này | H-01, H-03, H-07 |
| `b-d-production-snapshot.json` | `configuration_revision_refs`, `configuration_bundle_fingerprint` cho revision config hiệu lực của job (CT-API-009) | H-06 |
| `g-activity-execution.json` | `capability_requirements` làm thuật ngữ cho capability health | H-05 |
| `g-c-i-completion.json` (CT-ORC-008) | `cloud_location_verification_ref`: completion chỉ sau khi location đã verify, nên H-05 cấm mốc completion khi upload chưa verified | H-05 |
| `i-artifact-version.json` | `artifact_id` và thuật ngữ version cho màn hình artifact (chỉ đọc) | H-15 |
| `controlplane.application.projections.operation_view_mapper.map_operation_view`, `controlplane.domain.statemachine.OperationState` | Ánh xạ trạng thái thực thi sang trạng thái view (chỉ import) | H-01 |

### 4.3. Tên và kiểu lệch cần giữ

- `OperationItem` hiện tại (`types/api.ts`) chỉ có `status` là chuỗi; view đầy đủ theo CT-API-007 là kiểu mới `OperationView`; slice không đổi `api.ts`.
- Giá trị `status` của view viết thường (`accepted`, `running`, `waiting`, `outcome_unknown`, `succeeded`, `failed`); trạng thái batch viết hoa (`CREATED`, `RUNNING`, `WAITING_CAPABILITY`, `COMPLETED_TARGET`, `COMPLETED_EXHAUSTED`, `FAILED_SYSTEM`) như trong `control_api_queries.py`; H không trộn hai namespace.
- Binding khai nhiều enum là `string` (bindings/README.md, D8 mục 2); thứ tự và danh sách giá trị là GIẢ ĐỊNH, khi mâu thuẫn binding thắng và slice không sửa binding.

## 5. Exit gate roadmap và cách kiểm

H là năng lực xuyên suốt (roadmap §14: M2 admin shell, M3 màn hình A-B, M4 C-I, M5 D, M6 E-F, M7 UI vận hành đầy đủ). Nguồn chính là §8 và §13, kèm các gate M3–M6 có phần UI.

### 5.1. Exit gate H phục vụ

| Mã | Exit gate (nguồn) | Slice | Cách kiểm |
|---|---|---|---|
| EG-M2-H-1 | UI không có đường sửa article, script, event relation (§8 dòng 275; CT-API mục 9 điều 5) | H-08, H-09, H-15, H-16 | `test_h_read_only_listing.py` (chỉ GET), `test_h_metadata_update.py` (allowlist và tập cấm), `test_h_screen_registry.py`, `test_h_ui_source_guard.py` |
| EG-M2-H-2 | Secret không xuất hiện trong UI (§8 dòng 276; CT-API mục 9 điều 6) | H-01, H-06, H-16 | `test_h_operation_view_model.py`, `test_h_config_account_views.py` (khóa secret bị từ chối), `test_h_ui_source_guard.py` (phần H của `TST-SEC-INV-012`) |
| EG-M2-H-3 | Mọi lỗi có trạng thái, correlation và technical detail ref (§8 dòng 277) | H-01, H-07, H-13 | `test_h_problem_detail.py`, `test_h_error_hover_detail.py` |
| EG-M2-H-4 | accepted khác running, succeeded, failed; SSE reconnect và resync (§8 dòng 253–257; CT-API mục 9 điều 3 và 4) | H-01, H-03, H-10, H-11, H-12, H-14 | `test_h_operation_view_model.py`, `test_h_stream_event_catalog.py`, `test_h_stream_client_registry.py`, `test_h_status_presentation.py`, `test_h_status_pill.py` |
| EG-M2-H-5 | User duyệt trải nghiệm nền và cách debug (§8 dòng 278) | Không có slice | PUC-H-04 |
| EG-M3-H-1 | User thêm nguồn và theo dõi từng lượt, stage, error trên UI (§9 dòng 337) | H-05, H-08, H-09, H-15 | Test view, route, registry; command `RegisterSource` do A và G cung cấp (YC-HT-H-04); E2E thật ở hội tụ và CP7-H-01 |
| EG-M3-H-2 | Article và Event truy ngược source, fetch evidence, revision (§9 dòng 338) | H-15 (cột provenance của màn hình articles và events) | `test_h_screen_registry.py`; dữ liệu do B cung cấp qua YC-HT-H-04 |
| EG-M4-H-1 | UI phân biệt original, processed, uncertain, failed, unavailable (§10 dòng 414) | H-11 | `test_h_status_presentation.py` (năm trạng thái artifact) |
| EG-M5-H-1 | Output D truy được snapshot, model, prompt, config (§11 dòng 472), phần UI: hiện revision hiệu lực của mỗi job, không có script editor | H-06, H-15 | `test_h_config_account_views.py`, `test_h_screen_registry.py` (`scripts` chỉ đọc) |
| EG-M6-H-1 | Render success, QC pass, upload success, completion là bốn mốc riêng (§12 dòng 526); chạy từng stage, retry, biến thể (dòng 515) | H-05, H-15 | `test_h_ops_read_models.py`; command `RunDebugStage`, `RetryStage`, `CreateNewVariant` thuộc G (YC-HT-H-04) |
| EG-M7-H-1 | UI hoàn chỉnh cho source, article/event, media/hook, job/stage/batch/session/log/config/account/cost (§13 dòng 557) | H-15 | `test_h_screen_registry.py` (đủ màn hình theo §14); màn hình thật là wiring của hội tụ |
| EG-M7-H-2 | SSE reconnect, resync, không im lặng bỏ sót (§13 dòng 558) | H-03, H-14 | Danh mục kind và deduper có giới hạn |
| EG-M7-H-3 | R5: không job biến mất không trạng thái hoặc log (§13 dòng 582) | H-05 | `test_h_ops_read_models.py`; fault suite ở hội tụ |
| EG-M7-H-4 | R6: UI p95 2 giây, ACK 1 giây trên workload khóa (§13 dòng 591; test strategy §17.4) | H-02, H-04 (trang bị chặn bởi `max_limit`) | Cơ chế bởi `test_h_list_query.py`, `test_h_list_queries_sql.py`; con số chỉ đóng bằng CP7-H-01 |
| EG-M7-H-5 | Không dùng mock để đóng gate (§13 dòng 602) | Không có slice | Fake và fixture của H chỉ chứng minh logic, không được trích làm bằng chứng gate |

### 5.2. Test bắt buộc phần H (roadmap §8, test strategy §12.8)

- Tiếng Việt và UTF-8 đúng, không ký tự thay thế: H-11, H-13, H-15, H-16.
- Không có thao tác sửa article body, script hoặc event relation: H-09, H-15, H-16.
- Hover và focus vào lỗi thấy thông tin cụ thể nhưng không lộ secret: H-13, H-07.
- accepted, running, waiting, outcome_unknown, succeeded, failed khác nhau rõ ràng: H-01, H-11, H-12.
- SSE reconnect, event lặp và resync không làm UI sai state: H-03, H-14 (phần logic; trình duyệt thật ở CP7-H-01).
- 1080p, trải nghiệm bảng, p95 2 giây, ACK 1 giây: không đo được bằng slice; CP7-H-01.
- Session, Host/Origin, CSRF: đã có `tests/m2/test_p7a_control_api_security.py`; H không thay đổi.
- Mỗi module chính có lệnh debug riêng: H-15 khai báo màn hình; command thuộc G (YC-HT-H-04).
- Không có test ID catalog riêng cho UI: `docs/10-test-strategy.md` dòng 135 chỉ khai tiền tố `TST-UX-*` chưa có ID; slice ghi mã CT-API và QR-UX vào `coveredIds`; test ID mới phải đăng ký trước (YC-HT-H-10).

## 6. Mục mở và quyết định mặc định (D8)

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-H-01 | Kiểm thử TypeScript | Test tĩnh bằng pytest đọc tệp `.ts` và `.tsx` (stdlib), không thêm test runner JS | Runtime khoá chỉ có Python; không thêm thư viện (D10); `package.json` chỉ có `build` và `test:e2e` cần PostgreSQL thật. Giới hạn: không thay `tsc`, Playwright hay duyệt thị giác; `npm run build` và E2E là việc của hội tụ và CP7 |
| D8-H-02 | Trạng thái lạ | Hiển thị `Không nhận diện được` (`pill-unknown`, cần chú ý), không rơi về accepted | GAP-H-01: nhầm với đã nhận làm user tưởng việc đang bình thường; fail-visible |
| D8-H-03 | Phân trang | Keyset với cursor đục (base64url của JSON `[giá trị sắp xếp, id]`); `default_limit` và `max_limit` là tham số bắt buộc, giá trị khởi đầu đề xuất 50 và 100 (GIẢ ĐỊNH, khớp `LIMIT 100` hiện có); sort và filter chỉ trong whitelist; không dùng offset | ADR-0007: phân trang, lọc, sắp xếp phía server; QUALITY-OPEN-001 và 011 chưa chốt quy mô nên không hard-code trần |
| D8-H-04 | Quy tắc view | `finished_at` bắt buộc khi terminal và cấm khi chưa terminal; `wait_reason` chỉ khi `waiting`; `problem` chỉ khi `failed` hoặc `outcome_unknown`; mức severity log (`debug`, `info`, `warning`, `error`) và trạng thái account chữ thường là GIẢ ĐỊNH | CT-API-007 liệt kê trường nhưng không nêu ràng buộc; enum chưa chốt trong contract là `string` (bindings/README.md, D8 mục 2); chờ Control hoặc PUC-H-03 xác nhận |
| D8-H-05 | Trường sửa được | Mỗi màn hình khai `editableFields`; tập cấm `article_body`, `body`, `script`, `script_text`, `event_relation`, `event_links`, `secret`, `secret_value` không bao giờ được cấp; `articles`, `events`, `snapshots`, `story-angles`, `scripts` chỉ đọc | CT-API mục 1 và mục 9 điều 5; roadmap §8 dòng 275. `editableFields` của `media` là GIẢ ĐỊNH (QUALITY-OPEN-008 còn một phần) |

| Mã | Chủ đề | Mặc định đã chọn | Lý do |
|---|---|---|---|
| D8-H-06 | Mã lỗi của route module | `VALIDATION_FAILED` 422, `FORBIDDEN_FIELD` 422, `REVISION_CONFLICT` 409, `NOT_FOUND` 404; thiếu `Idempotency-Key` hoặc `If-Match` là 422 kèm `field_errors` | CT-API-001 (409 cho revision conflict, 422 cho sai quy tắc) và CT-API-009 (mã `REVISION_CONFLICT`); khớp cách `src/controlplane/api/main.py` ánh xạ ngoại lệ là việc của YC-HT-H-02 |
| D8-H-07 | Package route module và cách thêm mã | `src/controlplane/api/routes/modules/` không có `__init__.py` trong slice; mọi mã mới là module mới cạnh mã cũ, không sửa tệp đã có | Kiểm tra layout CP2A (`docs/delivery-evidence/cp2a-layout/report.md`) yêu cầu mọi gói có `__init__.py` phải khai trong `src/controlplane/pyproject.toml` (tệp dùng chung); namespace package vẫn import được; `tests/m2` bảo vệ mã hiện có; thêm `__init__.py` và package-dir là YC-HT-H-09 |
| D8-H-08 | Màn hình chưa có backend | `backendStatus: 'pending_module'` cho mọi màn hình ngoài operations, batches, jobs, configs | Không tuyên bố tính năng khi `/v1/<resource>` chưa có trong `control.py` |
| D8-H-09 | Grid | Giữ AG Grid Community 32.3.9; không đổi sang TanStack | ADR-0007: chỉ đổi khi Community không đủ; chưa có bằng chứng |
| D8-H-10 | Múi giờ hiển thị | Giữ `toLocaleString('vi-VN')` theo trình duyệt (GIẢ ĐỊNH) | ROADMAP-OPEN-004 và QUALITY-OPEN-014 chưa chốt; PUC-H-01 |

Đối chiếu điểm mở của roadmap và quality:

| Điểm mở | Xử lý trong kế hoạch H |
|---|---|
| ROADMAP-OPEN-004, QUALITY-OPEN-014 (múi giờ) | D8-H-10; PUC-H-01 |
| QUALITY-OPEN-001, QUALITY-OPEN-011, TEST-OPEN-002 (quy mô bảng và dataset) | D8-H-03; PUC-H-02; CP7-H-01 |
| QUALITY-OPEN-008 và phần mở của QR-UX-008 (chi tiết sửa metadata, cột, lọc, nhóm, chọn nhiều) | D8-H-05; PUC-H-03 |
| ROADMAP-OPEN-003 (tài khoản test thật) | H không dùng tài khoản thật; CP7-H-04 |
| ROADMAP-OPEN-007 (output profile), ROADMAP-OPEN-009 (preset) | UI hiển thị theo giá trị F cung cấp; H không chốt giá trị; màn hình liên quan `pending_module` |
| QUALITY-OPEN-009 (retention log và audit) | Thuộc J (PUC-J-05 trong `docs/implementation/j/plan.md`); H không hard-code thời hạn |

### 6.1. Danh sách chờ user (pendingUserCheckpoint)

Không mục nào dưới đây được coi là đã duyệt.

- PUC-H-01 — ROADMAP-OPEN-004, QUALITY-OPEN-014: múi giờ hiển thị và log. Hạn: trước khi bật lịch production.
- PUC-H-02 — QUALITY-OPEN-001/011, TEST-OPEN-002: quy mô hàng/cột và dataset khóa để đo p95 2 giây và ACK 1 giây (G07). Hạn: trước CP7-H-01.
- PUC-H-03 — QUALITY-OPEN-008, QR-UX-008: chi tiết cột, lọc, nhóm, chọn nhiều và danh sách trường metadata sửa được của từng màn hình (nhất là `media`). Hạn: trước khi hội tụ nối màn hình tương ứng.
- PUC-H-04 — User checkpoint M2 (P8/P9) và duyệt trải nghiệm nền (§8 dòng 278); duyệt UI theo R1 đến R4 (§9–§12) và UI hoàn chỉnh trước R6.
- PUC-H-05 — USER-CKPT-D9-D10: có thêm test runner TypeScript (mục 7) hay giữ test tĩnh. Hạn: trước CP-2b.
- PUC-H-06 — Cơ chế cấp Launch Capability và phiên cho bản sản xuất thay cho `/test-driver/issue-capability` (`client.ts` dòng 67–95), đồng bộ với phân hệ J. Hạn: trước CP7-H-05.
- PUC-H-07 — D5 cho CP7 (trình duyệt thật, PostgreSQL thật, tài khoản thật).

## 7. Thư viện (D10)

Các slice H không cần thư viện mới: Python chỉ dùng stdlib và gói đã có trong runtime khoá (`fastapi`, `starlette`, `httpx` cho `TestClient`, `pytest`); TypeScript không import thư viện mới.

Đã khoá, giữ nguyên, không slice nào sửa: trong `src/controlplane/ui/package.json` có `react==18.3.1`, `react-dom==18.3.1`, `ag-grid-community==32.3.9`, `ag-grid-react==32.3.9`, `vite==6.2.0`, `typescript==5.7.3`, `@playwright/test==1.50.1`, `@vitejs/plugin-react==4.3.4`, `@types/react==18.3.18`, `@types/react-dom==18.3.5`, Node `>=22.17.0 <23.0.0`, npm `10.9.2`; trong `src/controlplane/requirements.lock` có `fastapi==0.141.1`, `starlette==1.6.0`, `httpx==0.28.1`.

Đề xuất cho bước sau (không slice nào import; chờ USER-CKPT-D9-D10 và PUC-H-05): một test runner TypeScript cùng thư viện render component chạy trên jsdom để kiểm component React thật thay cho test tĩnh. Kế hoạch này không ghi số phiên bản vì chưa xác minh được trên registry trong phiên lập kế hoạch (không suy đoán, D10); Control xác minh tên và phiên bản cố định (dạng `tên==phiên bản`) tại thời điểm duyệt và đổi `package-lock.json` bằng slice phụ thuộc riêng (`dependency_slice`). Không đề xuất đổi AG Grid (D8-H-09).

## 8. Việc cần tài nguyên thật (CP7)

Chỉ chạy sau khi user duyệt D5. Không mở, chép hay in bí mật; tài khoản thật chỉ dùng qua secret broker của phân hệ J.

- CP7-H-01 — Browser E2E thật (Playwright trên Chromium) trên máy mục tiêu 1080p trở lên: Browser → Control API → PostgreSQL → Outbox → Projection → SSE → DOM; đo p95 thao tác 2 giây và ACK lệnh 1 giây, cold và warm riêng (test strategy §17.4), trên dataset khóa ở PUC-H-02; đóng phần UI của G07 (EG-M7-H-4).
- CP7-H-02 — SSE reconnect, resync khi cursor hết retention, desktop offline rồi online (TST-E2E-008) trên PostgreSQL thật.
- CP7-H-03 — User nghiệm thu UX và tiếng Việt từng milestone (R1 Content Alpha, R2 Media Alpha, R3 Creative Alpha, R4 Video Alpha) và baseline R6.
- CP7-H-04 — Quét secret canary trong DOM, HAR, log và response của UI khi chạy với tài khoản thật (phần H của `TST-SEC-INV-012`).
- CP7-H-05 — Luồng cấp phiên sản xuất thật (không dùng `/test-driver`) và kiểm Host/Origin/CSRF/TLS loopback trên máy người dùng.

## 9. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

Tài nguyên dùng chung chỉ gói hội tụ được sửa; slice H không chạm vào.

- YC-HT-H-01 — Registry và ownership: thêm vào `PATH-SRC-CONTROL-UI` (`ownership-and-locks.yaml` dòng 178–185) các mẫu `src/controlplane/application/projections/**`, `src/controlplane/application/sse/**`, `src/controlplane/api/sse/**`, `src/controlplane/api/routes/modules/**`, `src/controlplane/infrastructure/db/projections/**`, `tests/unit/control_ui/**`, `tests/integration/control_ui/**`; đăng ký lock `LOCK-H-01` đến `LOCK-H-16` hoặc quy ước thay thế.
- YC-HT-H-02 — Composition root (`src/controlplane/api/main.py`, `src/main.py`): mount router từ `api/routes/modules/` (`build_listing_router`, `build_metadata_router`), wiring service theo từng module vào `app.state`; thống nhất ánh xạ ngoại lệ sang ProblemDetail với mã ở D8-H-06.
- YC-HT-H-03 — UI shell: sửa `App.tsx`, `index.css`, `api/client.ts`, `OperationsGrid.tsx`, `BatchesGrid.tsx`, `JobsGrid.tsx`, `types/api.ts`, rồi build lại `ui/dist` bằng `npm run build`. Nối `StatusPill`, `ErrorHoverDetail`, `screenRegistry`, `streamEventKinds`, `boundedEventDeduper` vào shell; thay logic pill ở `OperationsGrid.tsx` dòng 27–34, danh sách `eventKinds` ở `client.ts` dòng 179–196, `Set` ở `client.ts` dòng 143 và `App.tsx` dòng 29; thêm CSS cho `pill-waiting`, `pill-outcome-unknown`, `pill-unknown`; mở rộng `OperationItem` và `JobItem` (GAP-H-04); gỡ hoặc khóa nút kiểm thử `handleTriggerTestError` (`App.tsx` dòng 151–164) và đường `/test-driver` khỏi bản sản xuất (GAP-H-06).
- YC-HT-H-04 — Control API (`src/controlplane/api/routes/control.py`, `application/control_api/**`, `infrastructure/db/control_api_queries.py`, `control_api_commands.py`): dùng `ListQuery` để phân trang thay `next_cursor: None` và `LIMIT 100`; trả `OperationView` đầy đủ (progress, wait_reason, mốc thời gian, problem); thêm query CT-API-002 còn thiếu (sources, articles, events, media, hooks, stage runs, sessions, logs, capabilities) và command CT-API-003..006 (`RegisterSource`, `UpdateSourceMetadata`, `RemoveSource`, `RestoreSource`, `TestSource`, `ImportVisualHook`, `ImportAudioHook`, `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`, `PublishConfigurationRevision`, `UpdateSecret` chỉ ghi, `TestExternalAccount`, `EnableExternalAccount`, `DisableExternalAccount`); service do phân hệ chủ sở hữu cung cấp, H chỉ trình bày.
- YC-HT-H-05 — Migration: index cho keyset (ví dụ `(workspace_id, created_at DESC, id DESC)` của `cp_production_batches` và `cp_video_jobs`, `(workspace_id, accepted_at DESC, receipt_id DESC)` của `cp_command_receipts`; migration `0008_operation_stream_workspace_cursor_index.sql` hiện chỉ có index cursor của stream); nguồn dữ liệu cho `progress`, `wait_reason`, `started_at`, `updated_at`, `finished_at` của operation; kiểm bằng `EXPLAIN` trên PostgreSQL thật (CP7-H-01). H không thêm bảng.
- YC-HT-H-06 — State machine: giữ `OperationState` và `map_operation_view`; nếu G đổi trạng thái stage, job hoặc batch (CT-STATE-008..010) thì cập nhật H-05 và H-11 trong cùng một lượt; không đăng ký trạng thái view vào `controlplane.domain.statemachine`.
- YC-HT-H-07 — Binding và registry: mở binding H ↔ G (`CONTRACT-CONTROL-API-STREAM`; CT-API-002, 005, 007, 008) và H ↔ J (CT-ACC-001, CT-SEC-001 chỉ ghi; đồng bộ YC-HT-J-03 và YC-HT-J-05) kèm fixture `tests/fixtures/contracts/<seam>/payloads.json` (hiện chưa có fixture cho Control API); cập nhật `contract-registry.yaml`.
- YC-HT-H-08 — Workflow G: signal và activity cho `RunDebugStage`, `RetryStage`, `CreateNewVariant`, `RegenerateFromStage`; mỗi phân hệ đăng ký event kind mới vào danh mục `STREAM_EVENT_KINDS` (H-03, H-14) khi thêm event.
- YC-HT-H-09 — Packaging: thêm `src/controlplane/api/routes/modules/__init__.py` và khai `controlplane.api.routes.modules` trong `src/controlplane/pyproject.toml` (package-dir, packages); không đổi lockfile.
- YC-HT-H-10 — Catalog test và tài liệu: đăng ký test ID `TST-UX-*` vào `docs/10-test-strategy.md` nếu muốn dùng làm oracle; Playwright E2E cho màn hình mới trong `tests/m2/e2e/**`; đồng bộ `HANDOFF.md`, `README.md`, `CHANGELOG.md`.

## 10. DAG slice và song song

Có 16 slice H-01..H-16 trong `docs/implementation/h/slices.md`. Gốc của mọi slice là `CP1-CONTRACT-BINDING` và `CP2A-LAYOUT` (đã tích hợp).

- Wave 1 (song song, không phụ thuộc slice H khác): H-01, H-02, H-03, H-06, H-07, H-16.
- Wave 2: H-04 (sau H-02); H-05 (sau H-01); H-08 (sau H-02, H-07); H-09 (sau H-07); H-10 (sau H-01, H-02).
- Wave 3: H-11, H-13, H-15 (sau H-10); H-14 (sau H-03).
- Wave 4: H-12 (sau H-11).

Mỗi slice có lock riêng `LOCK-H-<số>` vì chỉ sửa tệp mới đặt cạnh mã cũ; `LOCK-SRC-CONTROL-UI` dành cho việc sửa tệp dùng chung của H (shell, client, grid, `tests/m2/e2e`), do hội tụ thực hiện.

Rủi ro đã biết: (1) test tĩnh TypeScript không thay `tsc` và trình duyệt, nên H-10..H-16 có thể qua test mà chưa biên dịch; hội tụ phải chạy `npm run build` (YC-HT-H-03); (2) route module dùng service giả, không chứng minh gate (EG-M7-H-5); (3) mọi mục ghi `GIẢ ĐỊNH` ở mục 6 cần Control hoặc user xác nhận trước khi dùng làm cơ sở nghiệm thu.
