# Báo cáo CP-4-EVENT-KINDS

## 1. Phạm vi

Gói công việc CP-4-EVENT-KINDS chỉ thực hiện ĐĂNG KÝ TÊN KIND trong danh mục SSE phía máy chủ và phía giao diện người dùng theo plan.md mục 3.1. Gói này tuyệt đối không phát hành event ở các phân hệ, không sửa publisher hay outbox, không sửa client.ts và không sửa docs/09-contracts. Tệp client.ts hiện vẫn giữ `const eventKinds = [...]` riêng và chưa được nối vào `STREAM_EVENT_KINDS`.

Danh sách đúng sáu tệp thuộc quyền sở hữu (ownedPaths) đã sửa/tạo:
1. `src/controlplane/application/sse/event_catalog.py`
2. `src/controlplane/ui/src/api/streamEventKinds.ts`
3. `tests/unit/control_ui/test_h_stream_event_catalog.py`
4. `tests/unit/control_ui/test_h_stream_client_registry.py`
5. `tests/unit/control_ui/test_h_ts_contract_types.py`
6. `docs/delivery-evidence/cp-4-event-kinds/report.md`

## 2. RED

Trước khi chỉnh sửa `event_catalog.py` và `streamEventKinds.ts`, ba tệp test ghim của H đã được mở rộng để kiểm chứng thất bại theo nguyên tắc test-first. Lỗi ghi nhận hoàn toàn là AssertionError đúng oracle mong đợi (không có ImportError hay lỗi thu thập test nào). Tệp `test_h_ts_contract_types.py` không đỏ vì chuyển trường `wait_reason` thành kiểm tra có điều kiện nếu tồn tại.

Lệnh thực thi:
```
python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider
```

Exit code: 1

Nguyên văn ba dòng FAILED đầu tiên:
```
FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_stream_kinds_are_base_followed_by_38_module_kinds
FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_default_registry_matches_base_set
FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_default_registry_has_exactly_three_prefixes
```

Dòng tóm tắt thực tế:
```
16 failed, 76 passed in 0.25s
```

## 3. GREEN

Sau khi hoàn tất chỉnh sửa `event_catalog.py` và `streamEventKinds.ts`, toàn bộ các bài kiểm tra đều đạt chuẩn:

1. Ba tệp test ghim:
   - Lệnh: `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider`
   - Exit code: 0
   - Dòng tóm tắt thực tế: `92 passed in 0.11s`

2. Hồi quy toàn bộ bộ kiểm tra giao diện điều khiển và luồng SSE M2:
   - Lệnh: `python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider`
   - Exit code: 0
   - Dòng tóm tắt thực tế: `656 passed, 1 warning in 7.53s`

3. Probe đối chiếu danh mục kind giữa Python và TypeScript:
   - Lệnh: `python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pathlib.Path('src/controlplane/ui/src/api/streamEventKinds.ts').read_text(encoding='utf-8'); a = re.findall(chr(34) + '([a-z_]+[.][a-z_]+)' + chr(34) + ',', c.split('SNAPSHOT_RESOURCES')[0]); b = re.findall(chr(39) + '([a-z_]+[.][a-z_]+)' + chr(39) + ',', t.split('ALL_SNAPSHOT_RESOURCES')[0]); assert a == b and len(a) == 48 and len(set(a)) == 48, (len(a), len(b))"`
   - Exit code: 0 (không có output lỗi, danh sách khớp từng phần tử, đúng 48 kind, không trùng lặp)

4. Kiểm tra khoảng trắng thừa và ký tự xuống dòng:
   - Lệnh: `git diff --check`
   - Exit code: 0 (không có output lỗi)

## 4. Bảng kind

Tổng số event kind đã đăng ký là 48 kind (gồm 10 kind cơ sở ban đầu và 38 kind mới bổ sung từ các phân hệ):

| Tiền tố (prefix) | Số kind | Danh sách kind |
| --- | --- | --- |
| `operation` | 5 | `operation.accepted`, `operation.running`, `operation.succeeded`, `operation.failed`, `operation.changed` |
| `production_batch` | 1 | `production_batch.start_accepted` |
| `job` | 4 | `job.created`, `job.running`, `job.completed`, `job.failed` |
| `source` | 10 | `source.registered`, `source.metadata_updated`, `source.removed`, `source.restored`, `source.candidate_discovered`, `source.candidate_resolved`, `source.collection_run_started`, `source.collected_document_available`, `source.collection_run_completed`, `source.collection_run_failed` |
| `ingestion` | 4 | `ingestion.article_revision_accepted`, `ingestion.duplicate_document_resolved`, `ingestion.event_link_resolved`, `ingestion.event_update_accepted` |
| `creative` | 6 | `creative.production_snapshot_committed`, `creative.story_angles_generated`, `creative.script_version_created`, `creative.production_plan_created`, `creative.variant_validated`, `creative.output_metadata_created` |
| `voice` | 4 | `voice.image_safety_assessed`, `voice.media_processing_completed`, `voice.voice_ready`, `voice.word_timing_ready` |
| `render` | 2 | `render.render_completed`, `render.output_quality_checked` |
| `orchestration` | 8 | `orchestration.batch_started`, `orchestration.job_allocated`, `orchestration.stage_state_changed`, `orchestration.job_waiting`, `orchestration.job_failed`, `orchestration.video_completed`, `orchestration.batch_target_reached`, `orchestration.batch_exhausted` |
| `storage` | 2 | `storage.artifact_location_verified`, `storage.cleanup_completed` |
| `config` | 2 | `config.revision_published`, `config.credential_changed` |

Cấu hình tài nguyên snapshot:
- `SNAPSHOT_RESOURCES` gồm đúng 6 khóa:
  - `operation`: `("operations",)`
  - `production_batch`: `("batches",)`
  - `job`: `("jobs",)`
  - `source`: `("sources",)`
  - `ingestion`: `("articles", "events")`
  - `orchestration`: `("batches", "jobs", "stage-runs")`
- `ALL_SNAPSHOT_RESOURCES` gồm đúng 11 phần tử:
  `("operations", "batches", "jobs", "sources", "articles", "events", "media", "hooks", "stage-runs", "sessions", "logs")`

## 5. Chênh lệch so với kế hoạch

Trong `plan.md` mục 4 có nêu "hợp resource bằng ALL_SNAPSHOT_RESOURCES". Tuy nhiên, trên thực tế các tài nguyên `media`, `hooks`, `sessions`, `logs` hiện chưa có tiền tố phân hệ nào quản lý để ánh xạ trực tiếp trong bảng `SNAPSHOT_RESOURCES`. Do đó, hợp các tài nguyên trong bảng là một tập con thực sự của `ALL_SNAPSHOT_RESOURCES` và chênh lệch đúng 4 phần tử (`{'media', 'hooks', 'sessions', 'logs'}`). Bộ test ghim đã kiểm chứng và khóa chặt chính xác phần chênh lệch này để bảo đảm tính toàn vẹn.

## 6. Trạng thái BL

| Mã mục | Trạng thái | Chi tiết ghi nhận |
| --- | --- | --- |
| `BL-CV-02` | PENDING | Phong bì do Control mở bằng slice riêng CP-4-EVENT-KINDS (ownedPaths gồm `event_catalog.py` và `streamEventKinds.ts`, các khóa `LOCK-CONTROL-API`, `LOCK-SRC-CONTROL-UI`, `LOCK-CONVERGENCE` theo lệnh dispatch). Phần đăng ký tên kind đã hoàn tất trong candidate, đang chờ Reviewer và Auditor nghiệm thu, CHƯA tự tuyên bố đóng. Phần phát hành event ở phân hệ: chưa làm, nằm ngoài phong bì này. |
| `OI-EXT-UI-01` | Còn mở | Event của phân hệ C (gồm 9 kind liên quan đến media và hook) hiện chưa đăng ký theo quyết định thiết kế. |

## 7. Giới hạn

- Danh mục hiện tại đã đăng ký tên kind trên hệ thống SSE và client registry, nhưng chưa có bất kỳ event thực tế nào mang các kind này được phát hành từ các phân hệ nghiệp vụ.
- Báo cáo này tuyệt đối không tuyên bố rằng các event đã được phát hành hay tích hợp luồng phát tín hiệu.
