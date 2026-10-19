# Báo cáo bằng chứng H-14

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `ddeec203cadc4982286cbfa02a4882905967b7d1`
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-14 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider`
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `10 failed, 4 passed in 0.12s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_client_kinds_equal_base_kinds_in_order - AssertionError: assert () == ('operation.accepted', ...)`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_client_kind_type_is_derived_from_const_tuple - AssertionError: assert 'export type StreamEventKind = (typeof STREAM_EVENT_KINDS)[number];' in ...`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_client_resource_table_equals_python_snapshot_resources - AssertionError: assert {} == {'job': ('jobs',), ...}`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_client_resource_table_keys_are_kind_prefixes - AssertionError: assert set() == {'batches', 'jobs', 'operations'}`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_client_fallback_equals_python_all_snapshot_resources - AssertionError: assert () == ('operations', 'batches', 'jobs')`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_snapshot_resources_for_signature_and_unknown_fallback - AssertionError: assert 'Object.prototype.hasOwnProperty.call(RESYNC_SNAPSHOT_RESOURCES, resourceType)' in ...`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_deduper_default_max_seen_is_5000 - AssertionError: assert None`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_deduper_factory_signature_and_interface - AssertionError: assert 'export function createBoundedEventDeduper(maxSeen: number = DEFAULT_MAX_SEEN): BoundedEventDeduper {' in ...`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_deduper_rejects_non_integer_or_non_positive_max_seen_before_allocating - AssertionError: assert 'if (!Number.isInteger(maxSeen) || maxSeen < 1) {' in ...`
  - `FAILED tests/unit/control_ui/test_h_stream_client_registry.py::test_deduper_evicts_oldest_id_in_insertion_order - AssertionError: assert None`
- Xác nhận: Hoàn toàn không có ImportError hay FileNotFoundError. Toàn bộ 10 test thất bại đều là AssertionError do khung RED chưa có nội dung thật; 4 test về tính thuần và encoding UTF-8 đã PASS ngay từ đầu.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `14 passed in 0.03s`

## Thay đổi

- 4 tệp thuộc owned paths:
  - `src/controlplane/ui/src/api/streamEventKinds.ts`: Khai báo bộ 10 kind STREAM_EVENT_KINDS as const, type StreamEventKind, mảng ALL_SNAPSHOT_RESOURCES, bảng RESYNC_SNAPSHOT_RESOURCES và hàm snapshotResourcesFor tra cứu snapshot an toàn bằng hasOwnProperty với fallback về toàn bộ tài nguyên.
  - `src/controlplane/ui/src/features/stream/boundedEventDeduper.ts`: Cung cấp hằng số DEFAULT_MAX_SEEN = 5000, interface BoundedEventDeduper và hàm khởi tạo createBoundedEventDeduper kiểm tra maxSeen bằng RangeError, thực hiện deduplicate và cơ chế eviction FIFO theo thứ tự chèn.
  - `tests/unit/control_ui/test_h_stream_client_registry.py`: Bộ kiểm thử tĩnh 12 hàm (14 test cases) đối chiếu danh mục kind và bảng snapshot phía TypeScript với server Python event_catalog.py, kiểm tra chữ ký, eviction và tính thuần (không I/O, không EventSource, không fetch, không any).
  - `docs/delivery-evidence/h-14/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider` | 0 | `14 passed in 0.03s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `snapshotResourcesFor` dùng `hasOwnProperty` để các khóa prototype như `'constructor'` hoặc `'toString'` không trả về thuộc tính prototype mà rơi về mảng fallback an toàn.
2. Eviction theo FIFO dựa trên thứ tự chèn của `Set`, id đã thấy lại không làm mới vị trí trong hàng đợi.
3. `maxSeen` không nguyên hoặc nhỏ hơn 1 ném `RangeError` trước khi cấp phát `Set`.
4. Test là kiểm tra tĩnh nội dung TypeScript vì repo chưa có test runner TS, `npm run build` thuộc hội tụ YC-HT-H-03.

## Ánh xạ phản ví dụ

- Danh sách kind lệch giữa server và client: Đã loại trừ qua `test_client_kinds_equal_base_kinds_in_order`.
- Set tăng vô hạn khi UI chạy 12 giờ: Đã loại trừ qua `test_deduper_evicts_oldest_id_in_insertion_order` và `test_deduper_default_max_seen_is_5000`.
- Resource_type lạ không kích hoạt tải lại: Đã loại trừ qua `test_snapshot_resources_for_signature_and_unknown_fallback` và `test_client_fallback_equals_python_all_snapshot_resources`.

## coveredIds

- `CT-API-008`

## Danh sách chờ user (pendingUserCheckpoint)

- `YC-HT-H-03 nối streamEventKinds.ts và boundedEventDeduper.ts vào client.ts và App.tsx, chạy npm run build`
- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`

## Giới hạn

- Không sửa `client.ts`, `App.tsx`, `event_catalog.py`, `pyproject.toml`, `lockfile`.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Không thêm thư viện.
- Không gọi dịch vụ thật.
