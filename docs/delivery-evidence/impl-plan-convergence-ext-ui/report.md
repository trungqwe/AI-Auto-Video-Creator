# Báo cáo IMPL-PLAN-CONVERGENCE-EXT-UI

- **Gói thực hiện**: IMPL-PLAN-CONVERGENCE-EXT-UI (planning_package)
- **Thời điểm**: 20/10/2026
- **Trạng thái**: Hoàn tất lập kế hoạch mở rộng hội tụ cho bốn mục BL-CV (BL-CV-02, BL-CV-12, BL-CV-05, BL-CV-07).

## Tệp đã tạo

1. docs/implementation/convergence-ext-ui/plan.md
2. docs/implementation/convergence-ext-ui/slices.md
3. docs/delivery-evidence/impl-plan-convergence-ext-ui/report.md

## Nguồn đã đọc

| Nguồn | SHA-256 | Vai trò / Nội dung đã đọc |
| --- | --- | --- |
| docs/implementation/convergence/plan.md | dc998d8cc60d7f8bd2141788f7ac83278b3d084be12912a1e5d920bffa1501d5 | Kế hoạch hội tụ cơ sở, mục 11, 11.1 và mục 12.1 về các mục BL-CV (BL-CV-02, 05, 07, 12, 13) |
| docs/implementation/convergence/slices.md | 0f18fbad94a959cb50668f3ff3202b79e12782fb4912c29750a644459228e322 | Kế hoạch slice hội tụ cơ sở |
| tests/unit/control_ui/test_h_stream_event_catalog.py | 3dbc1d2e6d27bc3b7c3d4480439f1460f471fafca6a0bce17b1467698032ee48 | Test ghim mười kind cơ sở, ba tiền tố, ba snapshot resource và danh mục client.ts |
| tests/unit/control_ui/test_h_stream_client_registry.py | 4bd727ff8239ee55af570390659d099aba2ad0d7d7f98d2924adb2e79274b67b | Test ghim 10 kind và resync table keys |
| tests/integration/control_ui/test_h_list_queries_sql.py | df48c57e5686f2a9a35c47f4719d6cce23923f9eb08767f3dcd39611c3cd43ab | Test ghim LIMIT 100 trong query SQL batches và jobs |
| tests/unit/control_ui/test_h_screen_registry.py | 908adbc1ad411f18e2c889df18083b421ce8b660ded67866bd26829bcd335565 | Test ghim bốn màn hình available và 14 pending_module |
| tests/unit/control_ui/test_h_ts_contract_types.py | c2a056d82fab8b8abc3893b49c6fd34bd5032498f2e2b0476b176d289de0a2fa | Test ghim OperationItem chưa có wait_reason |
| D:\AI_SETUP\project_controller\state\portfolio\lanes\lane-impl-plan-convergence-ext-ui\specs\IMPL-PLAN-CONVERGENCE-EXT-UI.md | f9989c368479e2d2eb1a55a170ed433162de653206a09ae26f1e6c89d22a6541 | Spec thực thi đầy đủ và lệnh làm việc của Orchestrator |

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả thật |
| --- | --- | --- |
| git diff --check (bước 18) | 0 | Không có lỗi khoảng trắng, không có khoảng trắng thừa cuối dòng, kết thúc tệp bằng đúng một dòng mới |
| Python acceptance probe (bước 19) | 0 | Kiểm tra cấu trúc đạt toàn bộ: đúng 4 slice (CP-4-EVENT-KINDS, CP-4-PAGINATION, CP-4-QUERIES, CP-4B-UI-SCREENS), đủ các trường bắt buộc (ownedPaths, dependsOn, indingRefs, 	estCommands, cceptance), mỗi khối slice không quá 7000 ký tự (các khối có độ dài: 3775, 3628, 3897, 5110 ký tự, tổng 16410 <= 38000), phụ thuộc đúng cổng GATE-PERSIST-*, CP-4-WIRING, CP-3-MIGRATIONS, CP-4B-UI-SHELL, USER-CKPT-D9-D10, có đủ 5 mã BL-CV (BL-CV-02, BL-CV-05, BL-CV-07, BL-CV-12, BL-CV-13), tiếng Việt đầy đủ dấu và không có ký tự thay thế U+FFFD |

## Ánh xạ

Bảng ánh xạ các hạng mục BL-CV từ mục 12.1 của kế hoạch hội tụ (docs/implementation/convergence/plan.md) sang bốn slice của kế hoạch mở rộng (nêu rõ BL-CV-13 vẫn BLOCKED):

| Mã | Việc (mục 12.1 của kế hoạch hội tụ) | Slice | Cổng ở mục 12.1 (giữ nguyên) |
| --- | --- | --- | --- |
| BL-CV-02 | Đăng ký event kind: `event_catalog.py` (`BASE_STREAM_EVENT_KINDS`) và danh mục phía client | `CP-4-EVENT-KINDS` | Control mở rộng ownedPaths kèm khóa của owner đường dẫn hoặc mở slice riêng; gói này chính là slice riêng đó. PENDING tới khi Control xác nhận phong bì |
| BL-CV-12 | Bỏ `LIMIT 100` ở `control_api_queries.py` và `next_cursor: None` ở `control.py`, thay bằng phân trang keyset | `CP-4-PAGINATION` | Test PostgreSQL thật trên `PostgresControlQueries` và probe đọc tệp; cần index keyset của migration `0018` (CP-3). PENDING |
| BL-CV-05 | Query CT-API-002 còn thiếu: sources, articles, events, media, hooks, stage runs, sessions, logs, capabilities | `CP-4-QUERIES` | `PERSIST-A`..`PERSIST-G`, `PERSIST-I`, `PERSIST-J` đạt Auditor PASS (chín cổng `GATE-PERSIST-*`); route chỉ gọi service qua port. PENDING |
| BL-CV-07 | Màn hình module trên shell: `backendStatus` khỏi `pending_module`, dựng lại `ui/dist` | `CP-4B-UI-SCREENS` | `CP-4-WIRING` PASS, runtime Node sau `USER-CKPT-D9-D10`; màn hình chưa có route giữ `pending_module`. PENDING |
| BL-CV-13 | Gỡ hoặc khóa `handleTriggerTestError` và `/test-driver` | không có slice | BLOCKED theo quyết định, chờ PUC-H-06 và CP7-H-05; gói này không chạm `components/Header.tsx`, `/test-driver` hay năm spec M2 |

## Phần không làm

1. Phát hành event ở phân hệ (publisher, outbox, `append_event`): ngoài phong bì. BL-CV-02 chỉ đăng ký tên kind; tới khi phân hệ phát, danh mục có kind nhưng chưa có event nào mang kind đó. Không tuyên bố đã phát hành.
2. Lưu receipt cho lệnh CT-API-003..006 ở `src/controlplane/infrastructure/db/control_api_commands.py`: không sửa tệp này; lệnh vẫn thuộc `CP-4-WIRING` và phân hệ chủ sở hữu. Không tuyên bố đã làm lệnh CT-API-003..006.
3. Sáu màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost`: BL-CV-05 không có query tương ứng nên giữ `pending_module`, không route, không fetch.
4. `components/Header.tsx`, `handleTriggerTestError` và đường `/test-driver/issue-capability` (BL-CV-13, BLOCKED theo quyết định); năm spec M2 trong `tests/m2/e2e/` giữ nguyên byte; spec mới `tests/m2/e2e/cp4b-*.spec.ts` do Control.
5. Kế hoạch phân hệ A đến J, `docs/09-contracts/**`, migration, `api/wiring/**`, `config/adapter.py`, adapter `PERSIST-*`, lockfile, `docs/milestones/**/evidence/**`.
6. Route chi tiết `/v1/<tài nguyên>/{id}` cho chín query mới và mọi route ghi.
7. Event của C (chín kind media và hook) chưa đăng ký (OI-EXT-UI-01).

## Mục mở

Các mục mở OI-EXT-UI-01..06 theo plan.md mục 7; ghi rõ chưa mục nào được user duyệt, các mục cần user vẫn nằm ở danh sách chờ của kế hoạch hội tụ:

| Mã | Nội dung | Mặc định | Lý do |
| --- | --- | --- | --- |
| OI-EXT-UI-01 | Event của C (chín kind media, hook) không có trong mục 6 của kế hoạch hội tụ | Chưa đăng ký; màn hình media và hook nạp lại qua resync dự phòng | Không mở rộng phạm vi ngoài danh sách đã duyệt |
| OI-EXT-UI-02 | Tiền tố `ingestion`, `creative`, `voice`, `render`, `orchestration`, `storage`, `config` và tên snake_case là cách đặt tên của kế hoạch này (GIẢ ĐỊNH) | Dùng bảng ở mục 3.1; Control đối chiếu với `02-domain-events.md` khi nghiệm thu | Một tiền tố một phân hệ, dễ kiểm bằng `StreamKindRegistry` |
| OI-EXT-UI-03 | `cp_config_revisions` chưa có index keyset riêng (`0018` chỉ index receipts, batches, jobs) | Chấp nhận ở quy mô v1, ghi backlog; không thêm migration | Bảng nhỏ, không đổi `0018` |
| OI-EXT-UI-04 | Nguồn dữ liệu của `sessions`, `logs`, `capabilities` chưa xác nhận trong migration | Worker đọc `0009`..`0018` thật; thiếu bảng đủ cột thì tài nguyên BLOCKED (`DEPENDENCY_GAP`, `CP-3-MIGRATIONS`) và màn hình giữ `pending_module` | Không bịa bảng; không mở màn hình khi chưa có query |
| OI-EXT-UI-05 | Khoảng trống thứ tự: `CP-4B-UI-SHELL` bỏ danh sách `eventKinds` ở `client.ts` và mở rộng `OperationItem`, làm hỏng hai test H nêu ở mục 4 | Control dispatch `CP-4-EVENT-KINDS` trước `CP-4B-UI-SHELL`; không thêm cạnh vào kế hoạch hội tụ | Giữ nguyên cạnh của kế hoạch hội tụ |
| OI-EXT-UI-06 | `ownership-and-locks.yaml` chưa phủ `application/sse/**`, `application/control_api/**`, `api/routes/**`, `infrastructure/db/control_api_*.py`, `tests/unit/control_ui/**`, `tests/integration/convergence/**` (chỉ `api/main.py` và `ui/**` có owner) | Control xác nhận phong bì kèm khóa `LOCK-CONTROL-API`; gói này không sửa registry (thuộc `CP-2D-REGISTRY`) | Thiếu phủ thì slice BLOCKED, không đổi khóa |
