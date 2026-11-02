# OPSTREAM-WIRE — báo cáo giao hàng

## 1. Nhóm lỗi OI-CP7-12-Q1
- Bối cảnh: Đo lường ngày 02/11/2026 (lô 74e795ef của CP7-11 trên launcher production) phát hiện bảng `controlplane.cp_operation_stream` có 0 dòng, khiến endpoint SSE `/v1/operations/stream` (`db/sse/postgres.py`) và màn hình thao tác không có dữ liệu thực tế.
- Nguyên nhân gốc: Kế hoạch M2-P3 đã duyệt cho consumer chiếu outbox vào luồng qua `PostgresEventProcessor` (checkpoint cùng giao dịch). Tuy nhiên trước đây chỉ có test `tests/m2` sử dụng consumer này; worker trong launcher production chỉ chạy `OutboxRelay` (chỉ xử lý `start_accepted`), `CollectionScheduler`, và `EnrichmentStarter`.
- Khắc phục: Bổ sung module `OperationStreamRelay` chạy nền trong tiến trình worker của `launcher.py` với chu kỳ `OPERATION_STREAM_INTERVAL_SECONDS = 2.0`, chiếu toàn bộ sự kiện outbox của workspace vào `cp_operation_stream` qua `PostgresEventProcessor`.

## 2. Các tệp đã thêm và sửa đổi
Ba tệp mã nguồn và kiểm thử được chép nguyên văn từ bản tham chiếu của Control tại D:/AIAVC_IMGPROTO/ref/opstream-wire/ (khớp sha256 chuẩn sau khi chuẩn hóa LF):
1. `tools/launcher/launcher.py` (sửa đổi): Khai báo hằng số `OPERATION_STREAM_INTERVAL_SECONDS = 2.0` cạnh `OUTBOX_RELAY_INTERVAL_SECONDS`, import `OperationStreamRelay`, khởi tạo `stream_relay = OperationStreamRelay(batch_connection, workspace_id)` và đăng ký `stream_relay.run_forever` vào danh sách `background` trong hàm `start_worker`.
   - SHA-256 (sau chuẩn hóa LF): `b49f26f3127847b259f6362b7b2d20e59d97febabce2fa2d68df504893f72c12`
2. `src/controlplane/infrastructure/db/projections/operation_stream_relay.py` (tệp mới): Cung cấp `OperationStreamRelay` và `AppliedRevisions`, sử dụng `PostgresEventProcessor` với consumer ID 'controlplane.operation_stream', xử lý outbox theo từng sự kiện trong từng giao dịch riêng biệt, quản lý checkpoint `APPLIED`, cách ly payload không an toàn với lý do `QUARANTINED_UNSAFE_PAYLOAD` với envelope chỉ tham chiếu không có payload.
   - SHA-256 (sau chuẩn hóa LF): `e8b168d8b84e857a46f7bed88920891aeb487fed250d8f5af63ba004bd395a5c`
3. `tests/integration/prod_wiring/test_opstream_wire_relay.py` (tệp mới): Bộ 9 ca kiểm thử giả lập bộ nhớ cho relay outbox (docstring có coveredIds: CT-API-008), không cần PostgreSQL, Temporal hay mạng ngoài, kiểm tra đúng workspace, con trỏ tăng đơn điệu, chống ghi trùng lặp, quy tắc thứ tự/gap P3, cách ly payload không an toàn theo tham chiếu, schema 2, rollback riêng từng sự kiện lỗi, từ chối autocommit, chạy nền và tích hợp start_worker của launcher.
   - SHA-256 (sau chuẩn hóa LF): `34abf31d91a8a9bc065eef6d2feecba1a2b169fdf4ab3d425536c15124cab894`
4. `docs/delivery-evidence/opstream-wire/report.md` (tệp mới): Báo cáo bằng chứng giao hàng bằng tiếng Việt đầy đủ dấu.

## 3. Bảng lệnh kiểm tra đã chạy và kết quả thực tế
Tất cả các lệnh kiểm tra đều được thực thi với môi trường `PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\OPSTREAM-WIRE-implement-r0-ac1b5c0961` và interpreter khóa `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

| Bước | Lệnh kiểm tra | Mã thoát | Dòng tổng kết / Kết quả nguyên văn |
| --- | --- | :---: | --- |
| Bước 3 | `python -m pytest tests/integration/prod_wiring/test_opstream_wire_relay.py -q -p no:cacheprovider` (RED khi launcher cũ) | 1 | `FAILED tests/integration/prod_wiring/test_opstream_wire_relay.py::test_start_worker_runs_the_stream_relay_beside_the_outbox_relay` — `1 failed, 8 passed in 9.38s` |
| Bước 5 | Probe sha256 launcher.py khớp bản tham chiếu Control | 0 | Thoát 0, khớp `b49f26f3127847b259f6362b7b2d20e59d97febabce2fa2d68df504893f72c12` |
| Bước 6 | `python -m pytest tests/integration/prod_wiring/test_opstream_wire_relay.py -q -p no:cacheprovider` (GREEN sau cập nhật launcher) | 0 | `9 passed in 1.68s` |
| Bước 7 | `python -m pytest tests/integration/adapt/launch -q -p no:cacheprovider` | 0 | `63 passed in 9.63s` |
| Bước 8 | `python -m pytest tests/m2/test_p3_outbox_and_projections.py -q -p no:cacheprovider` (nhóm PostgreSQL P3) | 0 | `11 passed in 2.97s` |
| Bước 9 | `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider` | 0 | `24 passed in 11.59s` |
| Bước 10 | Probe sha256 module relay và test khớp bản tham chiếu Control | 0 | Thoát 0, khớp đúng cả 2 tệp |
| Bước 11 | Probe cấu trúc relay (hai class, qua PostgresEventProcessor, không INSERT/UPDATE trực tiếp outbox, postgres.py không đổi) | 0 | Thoát 0 |
| Bước 12 | Probe start_worker và hằng OPERATION_STREAM_INTERVAL_SECONDS | 0 | Thoát 0 |
| Bước 13 | Probe tên test, docstring coveredIds CT-API-008 và không có byte CR | 0 | Thoát 0 |
| Bước 14 | Probe ADAPT-LAUNCH-FIX2 (ports và imports) | 0 | Thoát 0 |
| Bước 15 | Probe PW-W2-FIX5 (seed_production_render_config) | 0 | Thoát 0 |
| Bước 16 | Probe PW-W1-FIX1 (seed_media, import/generate) | 0 | Thoát 0 |
| Bước 17 | Probe ADAPT-PROD-FIX4 (install_activity_executor và capped_worker_factory) | 0 | Thoát 0 |
| Bước 18 | Probe PW-D3-FIX2 (resolve_documents và fallback_candidates) | 0 | Thoát 0 |
| Bước 19 | Probe IMGGEN-LAUNCH (Deps.start_imagegen và constants) | 0 | Thoát 0 |
| Bước 20 | Probe IMGGEN-LAUNCH (thứ tự cmd_serve, cmd_status, main) | 0 | Thoát 0 |
| Bước 21 | Probe IMGGEN-LAUNCH (tham số sidecar) | 0 | Thoát 0 |
| Bước 22 | Probe PW-W1 (OutboxRelay, build_grant_issuer, CapabilityReader) | 0 | Thoát 0 |
| Bước 23 | Probe IMGGEN-PIPE (assemble_dfe_handlers và start_worker) | 0 | Thoát 0 |
| Bước 24 | Probe bố cục CP2A-LAYOUT (package-dir, pythonpath, không import tiền tố src.) | 0 | Thoát 0 |
| Kiểm tra git | `git diff --check` | 0 | Thoát 0, không có lỗi khoảng trắng hay marker xung đột |

## 4. Số dòng outbox được chiếu và checkpoint của consumer controlplane.operation_stream trong test
Từ kết quả thực thi các ca kiểm thử trong `tests/integration/prod_wiring/test_opstream_wire_relay.py`:
- Trong ca 	est_outbox_events_become_operation_stream_rows_of_their_workspace:
  - Có 4 sự kiện outbox được nạp vào, trong đó 3 sự kiện thuộc workspace mục tiêu (`00000000-0000-0000-0000-00000000a001`) gồm `production_batch.start_accepted`, `video_job.state_changed`, và `render.output_inspected`; 1 sự kiện thuộc workspace khác (`OTHER_WS`).
  - Kết quả: Đúng 3 sự kiện của workspace mục tiêu được chiếu vào `cp_operation_stream` (stream_event_id: 1, 2, 3) với `summary == 'projection'`. Sự kiện của workspace khác không bị chiếu lọt vào.
  - Có đúng 3 checkpoint trạng thái `APPLIED` được ghi vào `cp_event_checkpoints` cho consumer `controlplane.operation_stream`.
  - Cột `published` của bảng outbox vẫn là `False`, không phát sinh câu lệnh `UPDATE` nào trên outbox.
- Trong ca 	est_running_again_appends_nothing_twice:
  - Đưa 3 sự kiện ban đầu vào outbox, lần chạy đầu tiên chiếu 3 dòng (`run_once() == 3`).
  - Lần chạy tiếp theo trả về 0 dòng (`run_once() == 0`).
  - Khởi tạo instance relay mới và chạy lại tiếp tục trả về 0 dòng (`make_relay(db).run_once() == 0`).
  - Tổng số dòng trong `db.stream` vẫn giữ nguyên là 3.
  - Khi bổ sung 1 sự kiện mới (`job-9`), lần chạy tiếp theo chỉ chiếu đúng 1 dòng mới (`run_once() == 1`), nâng tổng số dòng trong stream lên 4.
  - Không có sự kiện nào bị ghi lặp hai lần.
- Trong ca 	est_revisions_of_one_aggregate_follow_the_p3_order_rules:
  - 4 sự kiện cùng aggregate `job-1` được nạp (revision 1, 2, stale 1, gap 5).
  - Chiếu thành công đúng 2 sự kiện hợp lệ (rev 1, rev 2) vào stream (`run_once() == 2`).
  - Ghi nhận 4 checkpoint cho consumer `controlplane.operation_stream`: revision 1 -> `APPLIED`, revision 2 -> `APPLIED`, stale revision 1 -> `OUT_OF_ORDER`, gap revision 5 -> `GAP_BLOCKED`.
- Trong ca 	est_unsafe_payload_is_quarantined_by_reference_and_never_streamed:
  - 2 sự kiện outbox (1 sự kiện chứa payload nhạy cảm `token=abc123`, 1 sự kiện an toàn).
  - Chỉ có 1 sự kiện an toàn được chiếu vào stream (`run_once() == 1`) và ghi nhận checkpoint `APPLIED`.
  - Sự kiện có payload không an toàn bị chuyển vào bảng `cp_event_quarantine` với lý do `QUARANTINED_UNSAFE_PAYLOAD`, envelope cách ly chỉ mang tính tham chiếu và không chứa chuỗi nhạy cảm.
- Trong ca 	est_a_failed_event_rolls_back_alone_and_is_projected_on_the_next_cycle:
  - 3 sự kiện outbox, sự kiện thứ 2 bị inject lỗi.
  - Lượt đầu rollback riêng sự kiện lỗi, commit đúng 1 dòng stream cho sự kiện 1 cùng 1 checkpoint.
  - Lượt sau tiếp tục chiếu thành công 2 sự kiện còn lại vào stream.

## 5. Xác nhận kiểm thử PostgreSQL và cơ sở dữ liệu
- Phần SQL mới của `OperationStreamRelay` và `AppliedRevisions` được kiểm tra chặt chẽ thông qua bản giả lập `FakeP3Database` trong bộ nhớ (xác nhận đúng SQL của relay và các adapter P3, ngăn ngừa SQL ngoài mong muốn).
- Nhóm kiểm thử PostgreSQL M2-P3 (`tests/m2/test_p3_outbox_and_projections.py`) đã chạy thành công trên cơ sở dữ liệu PostgreSQL thực tế được cấp thông qua biến môi trường `M2_TEST_PG_DSN` với kết quả đạt toàn bộ 11/11 ca (`11 passed in 2.97s`, mã thoát 0). Không có ca kiểm thử nào bị lỗi hay hỏng do mã của gói.
- Các tệp kiểm thử `tests/m2/test_p7b_sse_stream.py` và `tests/integration/prod_wiring/test_pw_g6_outbox_relay.py` không nằm trong danh sách lệnh kiểm được giao của gói này và không được chạy trong lane.

## 6. Giới hạn đã biết (Limitations)
- Trường `operation_id` của các dòng trong `cp_operation_stream` là `NULL` do `PostgresEventProcessor` gọi `append(event=event)` không truyền `operation_id`, do đó `/v1/operations` chưa có `event_kind/summary` theo từng operation riêng biệt; `summary` là chuỗi cố định 'projection' theo đúng đặc tả thiết kế P3.
- Quy tắc aggregate revision của P3 được giữ nguyên: các sự kiện cùng aggregate trùng revision bị coi là `OUT_OF_ORDER`, nhảy cóc revision bị coi là `GAP_BLOCKED` và không được đưa vào luồng.
- Hai probe băm sha256 ghim `launcher.py` thuộc về `IMGGEN-LAUNCH` và `IMGGEN-PIPE` không còn khớp do launcher được bổ sung relay mới; điều này là mong muốn và đã được Control quyết định trong kế hoạch (không thuộc phạm vi gói này).
- Gói này không triển khai retention writer; watermark của bảng stream không thay đổi.
