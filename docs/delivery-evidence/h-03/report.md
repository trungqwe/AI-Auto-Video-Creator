# Báo cáo bằng chứng H-03

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `5c8e6691fb622d08054ca24cca359cf4f5f302b5` (5c8e669)
- Nguồn quyền: IMPL-PLAN-H Auditor PASS và slice H-03 trong `docs/implementation/h/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` (chạy với khung chưa có logic ở bước 6)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `60 failed, 2 passed in 0.37s`
- Chi tiết các dòng FAILED tiêu biểu:
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_pattern_constant_is_exact - AssertionError: assert '.+' == '[A-Za-z0-9_.-]+'`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_valid_kinds_are_accepted[job.created] - NotImplementedError: H-03 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_validator_uses_fullmatch_with_re_ascii - AssertionError: assert 'fullmatch' in set()`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_base_kinds_are_exactly_the_ten_expected - AssertionError: assert () == ('operation.accepted', ...)`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_default_registry_matches_base_set - NotImplementedError: H-03 RED skeleton`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_snapshot_resources_cover_exactly_the_base_prefixes - AssertionError: assert {} == {'job': ('jobs',), ...}`
  - `FAILED tests/unit/control_ui/test_h_stream_event_catalog.py::test_resync_targets_unknown_type_expands_to_all_without_duplicates - NotImplementedError: H-03 RED skeleton`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 2 test hợp lệ (`test_module_imports_only_stdlib`, `test_snapshot_resources_is_read_only`) đã PASS ngay từ đầu. Tất cả 60 test thất bại đều là `NotImplementedError` do khung skeleton chưa cài logic xử lý hoặc `AssertionError` khi kiểm tra hằng số / cấu trúc rỗng.

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` (chạy sau khi cài đặt logic ở bước 10)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `62 passed in 0.11s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/controlplane/application/sse/event_catalog.py`: Khai báo hằng số mẫu `EVENT_KIND_PATTERN = r"[A-Za-z0-9_.-]+"`, bộ 10 kind cơ sở `BASE_STREAM_EVENT_KINDS`, mapping tài nguyên snapshot chỉ đọc `SNAPSHOT_RESOURCES` và tuple tổng hợp `ALL_SNAPSHOT_RESOURCES`. Cài đặt hàm `is_valid_event_kind` sử dụng `re.fullmatch` với cờ `re.ASCII`, lớp `StreamKindRegistry` với phương thức `register(module_prefix, kinds)` đảm bảo tính hợp lệ, tính nguyên tử, kiểm tra quyền sở hữu prefix và `all_kinds()` sắp xếp ổn định, cùng các hàm tiện ích `default_registry()`, `snapshot_resources_for(resource_type)` và `resync_targets(resource_types)` hợp nhất không trùng lặp.
  - `tests/unit/control_ui/test_h_stream_event_catalog.py`: Bộ kiểm thử đơn vị toàn diện gồm 62 test cases bao gồm kiểm tra hằng số regex, chấp nhận kind hợp lệ, từ chối kind không hợp lệ (khoảng trắng, ký tự điều khiển, newline injection, non-ASCII Unicode), bắt buộc dùng `re.fullmatch` và `re.ASCII`, giới hạn import chỉ trong thư viện chuẩn stdlib, kiểm tra 10 kind cơ sở, đối chiếu client eventKinds là tập con của catalog, đăng ký module mới độc lập theo prefix, từ chối prefix sai hoặc kind sai prefix, từ chối đăng ký đè kind thuộc prefix khác, tính nguyên tử khi đăng ký lỗi, tính ổn định sắp xếp của `all_kinds()`, tính chỉ đọc của snapshot mapping, tra cứu snapshot resource cho loại đã biết và loại lạ/không hợp lệ, hợp nhất resync targets theo thứ tự xuất hiện không trùng lặp.
  - `docs/delivery-evidence/h-03/report.md`: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` | 0 | `62 passed in 0.11s` |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. `SNAPSHOT_RESOURCES` ánh xạ `resource_type` theo prefix kind: `operation` → `operations`, `production_batch` → `batches`, `job` → `jobs` (khớp trường `resource_type` trong `api/sse/stream.py`).
2. Thứ tự kiểm tra của `register`: kiểm tra tính hợp lệ (`is_valid_event_kind`) → kiểm tra đã thuộc prefix khác (`kind_owned_by_other_prefix`) → kiểm tra đúng prefix và có phần đuôi sau `<prefix>.` (`invalid_event_kind`).
3. Prefix không chứa dấu chấm và kind phải bắt đầu bằng `<prefix>.` kèm phần đuôi độ dài lớn hơn `len(prefix) + 1`.
4. `register` có tính nguyên tử: kiểm tra toàn bộ danh sách `kinds` trước khi ghi nhận vào registry; từ chối chuỗi trần (`str`, `bytes`) thay cho danh sách nhằm tránh lặp ký tự đơn lẻ.
5. `default_registry()` trả về instance mới độc lập mỗi lần gọi; `SNAPSHOT_RESOURCES` sử dụng `MappingProxyType` để đảm bảo bất biến chỉ đọc.
6. `resync_targets` khi nhận danh sách rỗng trả về tuple rỗng `()`; khi gặp `resource_type` lạ hoặc không phải `str` thì mở rộng an toàn thành toàn bộ `ALL_SNAPSHOT_RESOURCES` để đảm bảo không bỏ sót dữ liệu cần resync.

## Ánh xạ phản ví dụ

- Kind của phân hệ mới không có đường đăng ký nên bị bỏ rơi im lặng: Đã giải quyết và kiểm chứng qua `test_new_module_kind_under_its_own_prefix_is_accepted` (cho phép đăng ký module mới) và `test_kind_owned_by_other_prefix_is_rejected` (bảo vệ quyền sở hữu prefix giữa các phân hệ).
- Kind chứa ký tự xuống dòng chèn được frame SSE (CRLF injection): Đã giải quyết và kiểm chứng qua `test_invalid_kinds_are_rejected` (từ chối `\n`, `\r\n`, tab) và `test_invalid_kind_for_prefix_is_rejected`.
- Resource_type lạ không kích hoạt query lại: Đã giải quyết và kiểm chứng qua `test_unknown_resource_type_returns_all_resources` (trả về toàn bộ `ALL_SNAPSHOT_RESOURCES`) và `test_resync_targets_unknown_type_expands_to_all_without_duplicates` (mở rộng an toàn không trùng lặp).

## coveredIds

- `CT-API-008`
- `CT-EVT-002`

## Danh sách chờ user (pendingUserCheckpoint)

- `USER-CKPT-D9-D10`
- `CP7 tài nguyên thật (D5)`
- `YC-HT-H-03 nối catalog vào client.ts và wiring resync`

## Giới hạn

- Không sửa `src/controlplane/application/sse/stream.py`, `src/controlplane/api/sse/stream.py`, `src/controlplane/ui/src/api/client.ts`, `pyproject.toml`, `uv.lock`.
- Không chạy full suite, `tests/m1`, `tests/m2`.
- Chỉ sử dụng thư viện chuẩn stdlib.
- Không gọi dịch vụ thật.
