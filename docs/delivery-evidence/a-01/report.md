# Báo cáo bằng chứng A-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `bd037dc4c148a0a9d31cff9078bf4620b47fd815`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-01 trong docs/implementation/a/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` (chạy trước khi tạo src/source_ingestion)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `9 failed, 6 passed, 18 subtests passed in 0.08s`
- Chi tiết các test FAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_importable_from_src_root`: `AssertionError: unexpectedly None : source_ingestion is not importable from the src/ root`
  - `SUBFAILED(path='src/source_ingestion/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/domain/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/domain/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/application/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/application/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/ports/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/ports/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/adapters/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/adapters/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/worker/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/worker/__init__.py`
  - `SUBFAILED(path='src/source_ingestion/projections/__init__.py') tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/source_ingestion/projections/__init__.py`
  - `FAILED tests/unit/collection/test_a01_package_layout.py::PackageLayoutTests::test_package_modules_have_no_forbidden_imports`: `AssertionError: [] is not true : src/source_ingestion has no Python modules to scan`
- Xác nhận: Hoàn toàn không có ModuleNotFoundError, ImportError hay lỗi collection nào (RED là sai oracle vì find_spec trả None, thiếu tệp __init__.py, không có module để quét).

## Thay đổi

- 7 tệp `__init__.py` mới (chỉ chứa docstring):
  - `src/source_ingestion/__init__.py`
  - `src/source_ingestion/domain/__init__.py`
  - `src/source_ingestion/application/__init__.py`
  - `src/source_ingestion/ports/__init__.py`
  - `src/source_ingestion/adapters/__init__.py`
  - `src/source_ingestion/worker/__init__.py`
  - `src/source_ingestion/projections/__init__.py`
- Tệp kiểm thử mới:
  - `tests/unit/collection/test_a01_package_layout.py`
  - `DetectorSelfTests` (3 test): kiểm tra tự thân bộ dò `find_forbidden_imports` và `find_forbidden_dirs` bao phủ các phản ví dụ: `from src.` / `import src.`, các gói B–F (`ingestion`, `catalog`, `creative`, `voice`, `render`), `psycopg`, `temporalio`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api` kể cả `from controlplane import api`, import động qua `import_module` / `__import__`, và thư mục trùng `storage`, `orchestration`, `ui` ở mọi cấp.
  - `PackageLayoutTests` (5 test): kiểm tra gói `source_ingestion` import được từ root `src/`, tất cả các `__init__.py` chỉ chứa docstring, không có import bị cấm trong toàn bộ module của gói, không có thư mục trùng ở mọi cấp, và thư mục `tests/unit/collection/` không chứa `__init__.py`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 8 passed, 31 subtests passed in 0.03s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Liệt kê tests/unit/collection/

- Thư mục `tests/unit/collection/` chỉ có tệp `test_a01_package_layout.py`, hoàn toàn không có `__init__.py` (được kiểm tra và xác nhận bởi test `test_collection_test_dir_has_no_init`).

## Quyết định mặc định (D8)

1. Test gọi `importlib.util.find_spec` trước `import_module` để trạng thái RED là `AssertionError` rõ ràng, không rơi vào `ModuleNotFoundError`.
2. Cấm theo tiền tố đúng ranh giới tên (`ingestion` cấm, `ingestion_tools` không).
3. Quét thư mục cấm đệ quy mọi cấp dưới cây thư mục gói.
4. Chưa tạo gói `persistence` cho tới `CONV-A-01`.
5. Không thêm thư viện ngoài, chỉ dùng Python stdlib.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật.
