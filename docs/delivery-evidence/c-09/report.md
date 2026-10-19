# Báo cáo bằng chứng C-09

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4f956426cf8a28182acd5cba47ceebe368f9908f`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-09 trong `docs/implementation/c/slices.md`, binding `docs/parallel-delivery/bindings/g-c-i-completion.json`, fixture `tests/fixtures/contracts/g-c-i-completion/payloads.json`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` (chạy với stub ở bước 2)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `22 failed, 12 passed, 4 subtests passed in 0.21s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/catalog/test_catalog_usage.py::UnitOfWorkTests::test_recorder_never_calls_commit_or_rollback`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::UnitOfWorkTests::test_repository_comes_from_factory_with_same_uow`: `AssertionError: 0 != 2`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::UnitOfWorkTests::test_usage_is_invisible_before_commit`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::UnitOfWorkTests::test_usage_is_visible_after_commit`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ReplayTests::test_duplicate_element_inside_manifest_counts_once`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ReplayTests::test_new_completion_id_counts_again`: `AssertionError: 0 != 2`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ReplayTests::test_replay_after_commit_does_not_increase_count`: `AssertionError: Tuples differ: (0, 0) != (1, 0)`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ReplayTests::test_replay_inside_same_uow_before_commit_adds_nothing`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ReplayTests::test_valid_fixture_payload_writes_every_manifest_element`: `AssertionError: 0 != 2`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_empty_video_job_id_is_invalid_value`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_asset_id') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_manifest_element_missing_asset_or_role_stages_nothing`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='role') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_manifest_element_missing_asset_or_role_stages_nothing`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='video_job_id') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_missing_required_top_level_fields`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_usage_manifest') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_missing_required_top_level_fields`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='video_job_id') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_wrong_types_are_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_usage_manifest') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_wrong_types_are_rejected`: `AssertionError: ValueError not raised`
  - `SUBFAILED(field='media_usage_manifest[0]') tests/unit/catalog/test_catalog_usage.py::ValidationTests::test_wrong_types_are_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::TechnicalUsageTests::test_non_record_is_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::TechnicalUsageTests::test_production_kind_is_rejected`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::TechnicalUsageTests::test_technical_and_production_are_separate_kinds`: `AssertionError: 0 != 1`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::TechnicalUsageTests::test_technical_replay_adds_nothing`: `AssertionError: False is not true`
  - `FAILED tests/unit/catalog/test_catalog_usage.py::TechnicalUsageTests::test_technical_usage_does_not_count_as_production`: `AssertionError: False is not true`
- Xác nhận: Toàn bộ lỗi FAILED/SUBFAILED đều là AssertionError từ stub; hoàn toàn không có ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay lỗi collection (các test RecordTests và BoundaryTests đã PASS).

## Thay đổi

- `src/catalog/ports/usage.py`: Khai báo enum `UsageKind` (production, technical), frozen slots dataclass `MediaUsageRecord` với runtime validation các trường chuỗi bắt buộc không rỗng và kiểu `UsageKind`, protocol `MediaUsageRepository` với method `exists` và `add`. Không import bất kỳ thứ gì từ `controlplane`.
- `src/catalog/application/usage.py`: Khai báo ngoại lệ hợp đồng `UsageContractError(ValueError)` mang mã lỗi `code` và tên trường `field`. Triển khai `MediaUsageRecorder` với factory `repository_factory(uow)`. Method `record_production_usage` validate toàn bộ request/manifest trước khi ghi, bảo đảm idempotency qua `exists`, và stage các bản ghi production vào repository. Method `record_technical_usage` kiểm tra kiểu `MediaUsageRecord` và `UsageKind.technical`, ghi độc lập không tính vào production. Module tuyệt đối không gọi `uow.begin()`, `uow.commit()` hay `uow.rollback()`.
- `tests/unit/catalog/test_catalog_usage.py`: Bộ kiểm thử đơn vị toàn diện gồm 7 nhóm: `FakeStore`, `FakeUnitOfWork` (staging fake, hàng chỉ vào store khi commit, rollback xoá staging), `FakeUsageRepository`, `RecordingFactory`, `UnitOfWorkTests` (chứng minh usage chỉ thấy sau commit, rollback không để lại production usage, recorder không gọi commit/rollback, repository lấy qua factory với cùng uow), `ReplayTests` (idempotency, replay sau commit/trong uow/từ uow mới không tăng count, completion_id mới ghi nhận, payload fixture hợp lệ ghi đủ phần tử, deduplication trong manifest, manifest rỗng trả 0), `ValidationTests` (kiểm tra thiếu trường bắt buộc, sai kiểu, rỗng), `TechnicalUsageTests` (technical usage không tăng production, replay technical, từ chối production kind hoặc non-record), `RecordTests` (frozen record, từ chối chuỗi rỗng/sai kiểu), và `BoundaryTests` (AST audit không gọi begin/commit/rollback, kiểm tra ranh giới import).
- `docs/delivery-evidence/c-09/report.md`: Báo cáo bằng chứng thực thi C-09 ghi lại môi trường, kết quả RED/GREEN thật, phân tích diff và các quyết định kỹ thuật.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` | 0 | 27 passed, 11 subtests passed in 0.06s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |
| 3 | `python -c "import pathlib; fs=['src/catalog/ports/usage.py','src/catalog/application/usage.py','tests/unit/catalog/test_catalog_usage.py']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('\n'),1) if l.rstrip('\r')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'\n') and not d.startswith(b'\xef\xbb\xbf') for d in data.values()); print('OK')"` | 0 | OK (UTF-8 không BOM, không trailing whitespace, kết thúc LF) |

## Quyết định mặc định (D8)

1. GIẢ ĐỊNH: `UsageKind` dùng tên thành viên chữ thường theo slice (`production`, `technical`).
2. GIẢ ĐỊNH: `record_technical_usage` trả `bool` (`True` = ghi mới, `False` = đã tồn tại).
3. GIẢ ĐỊNH: `UsageContractError(ValueError)` mang `code` và `field`, dùng `missing_required`/`wrong_type`/`invalid_value` như binding.
4. GIẢ ĐỊNH: `media_usage_manifest` rỗng là hợp lệ và trả `0`, thiếu khoá thì báo `missing_required`.
5. GIẢ ĐỊNH: Validate toàn bộ `media_usage_manifest` trước khi gọi `repository_factory(uow)` để bảo đảm tính nguyên tử và fail-fast.
6. GIẢ ĐỊNH: Khoá xác định trùng lặp (idempotency key) cho repository là `(completion_id, media_asset_id, role, usage_kind)`.
7. GIẢ ĐỊNH: Việc wiring `MediaUsageRecorder` vào unit of work thực tế của G và adapter PostgreSQL sẽ được triển khai ở `CONV-C-01`, `CONV-C-02` và `CP7`.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- GIẢ ĐỊNH D8-C-09
(Không mục nào được coi là đã duyệt.)

## Giới hạn

- Không chạy full suite; không chạy tests/m1, tests/m2.
- Không sửa fixture, state machine, migration, pyproject.toml, lockfile.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib và pytest đã khoá.
- Không gọi dịch vụ thật.
- Không tạo conftest.py hay __init__.py trong tests/.
- `MediaUsageRecorder` không tự gọi `uow.begin()`, `uow.commit()` hay `uow.rollback()`.
- Không commit secret, đường dẫn Credentials/ hay dữ liệu cá nhân.
