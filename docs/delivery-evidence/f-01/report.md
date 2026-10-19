# Báo cáo bằng chứng F-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `6945c76b1b309084663e2e0a6b2b668bebad88fc`
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-01 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` (chạy trước khi tạo src/render)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `9 failed, 10 passed, 62 subtests passed in 0.15s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_importable_from_src_root`: `AssertionError: unexpectedly None : render is not importable from the src/ root`
  - `SUBFAILED(path='src/render/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/__init__.py`
  - `SUBFAILED(path='src/render/domain/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/domain/__init__.py`
  - `SUBFAILED(path='src/render/application/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/application/__init__.py`
  - `SUBFAILED(path='src/render/ports/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/ports/__init__.py`
  - `SUBFAILED(path='src/render/adapters/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/adapters/__init__.py`
  - `SUBFAILED(path='src/render/worker/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/worker/__init__.py`
  - `SUBFAILED(path='src/render/projections/__init__.py') tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/render/projections/__init__.py`
  - `FAILED tests/unit/render/test_f01_package_layout.py::PackageLayoutTests::test_package_modules_have_no_forbidden_constructs`: `AssertionError: [] is not true : src/render has no Python modules to scan`
- Xác nhận: Hoàn toàn không có ModuleNotFoundError, ImportError hay lỗi collection nào (RED là sai oracle vì find_spec trả None, thiếu __init__.py, không có module để quét).

## Thay đổi

- 7 tệp `__init__.py` mới (chỉ chứa docstring):
  - `src/render/__init__.py`
  - `src/render/domain/__init__.py`
  - `src/render/application/__init__.py`
  - `src/render/ports/__init__.py`
  - `src/render/adapters/__init__.py`
  - `src/render/worker/__init__.py`
  - `src/render/projections/__init__.py`
- Tệp kiểm thử mới:
  - `tests/unit/render/test_f01_package_layout.py`
  - `DetectorSelfTests` (5 test): kiểm tra tự thân bộ dò `find_forbidden_imports`, `find_forbidden_calls`, `find_forbidden_functions`, `find_forbidden_dirs` và `scan_package` trên cây tạm có tệp mới; bao phủ các phản ví dụ: `from src.` / `import src.`, các gói lân cận (`creative`, `voice`, `catalog`, `ingestion`, `source_ingestion`), `psycopg`, `temporalio`, `pydantic`, `socket`, `subprocess`, `os`, `shutil`, `tempfile`, `urllib.request`, `http.client`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`, `controlplane.config`, import động qua `import_module` / `__import__`, các lời gọi thuộc tính xoá/đổi tên (`unlink`, `rmdir`, `rmtree`, `remove`, `rename`, `truncate`), tên hàm bắt đầu bằng `delete_`, `cleanup_`, `remove_`, và thư mục trùng `storage`, `orchestration`, `ui`, `config` ở mọi cấp.
  - `PackageLayoutTests` (6 test): kiểm tra gói `render` import được từ root `src/`, tất cả các `__init__.py` chỉ chứa docstring, quét mọi `src/render/**/*.py` không có cấu trúc bị cấm, không có thư mục trùng ở mọi cấp, thư mục `tests/unit/render/` không chứa `__init__.py`, và tệp test khai báo dòng `coveredIds: không`.
- Xác nhận thư mục kiểm thử:
  - Thư mục `tests/unit/render/` chỉ chứa tệp `test_f01_package_layout.py`, hoàn toàn không có `__init__.py` (được kiểm tra và xác nhận bởi test `test_render_test_dir_has_no_init`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 75 subtests passed in 0.06s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Cấm theo ranh giới tên đầy đủ (`os` cấm, `osmosis` không; `subprocess` cấm, `subprocess_tools` không; `shutil` cấm, `shutil_tools` không; `tempfile` cấm, `tempfile_utils` không).
2. Phát hiện cả import động `import_module` / `__import__` với chuỗi hằng.
3. Lời gọi thuộc tính chỉ kiểm tra dạng `obj.attr(...)` đối với các thao tác huỷ/đổi tên file (`unlink`, `rmdir`, `rmtree`, `remove`, `rename`, `truncate`).
4. Gói `render` không nằm trong danh sách cấm vì là gói của chính slice.
5. Chỉ dùng Python stdlib (`ast`, `importlib`, `pathlib`, `tempfile`, `unittest`), không thêm thư viện ngoài.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật, không chạy FFmpeg.
