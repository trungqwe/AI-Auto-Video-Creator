# Báo cáo bằng chứng E-01

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `773af60b0f148d6212f261abeb57c71fb5bde4b7`
- Nguồn quyền: IMPL-PLAN-E Auditor PASS, slice E-01 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` (chạy trước khi tạo src/voice)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `9 failed, 7 passed, 36 subtests passed in 0.11s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn:
  - `FAILED tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_importable_from_src_root`: `AssertionError: unexpectedly None : voice is not importable from the src/ root`
  - `SUBFAILED(path='src/voice/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/__init__.py`
  - `SUBFAILED(path='src/voice/domain/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/domain/__init__.py`
  - `SUBFAILED(path='src/voice/application/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/application/__init__.py`
  - `SUBFAILED(path='src/voice/ports/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/ports/__init__.py`
  - `SUBFAILED(path='src/voice/adapters/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/adapters/__init__.py`
  - `SUBFAILED(path='src/voice/worker/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/worker/__init__.py`
  - `SUBFAILED(path='src/voice/projections/__init__.py') tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_inits_are_docstring_only`: `AssertionError: False is not true : missing src/voice/projections/__init__.py`
  - `FAILED tests/unit/voice/test_e01_package_layout.py::PackageLayoutTests::test_package_modules_have_no_forbidden_imports`: `AssertionError: [] is not true : src/voice has no Python modules to scan`
- Xác nhận: Hoàn toàn không có ModuleNotFoundError, ImportError hay lỗi collection nào (RED là sai oracle vì find_spec trả None, thiếu __init__.py, không có module để quét).

## Thay đổi

- 7 tệp `__init__.py` mới (chỉ chứa docstring):
  - `src/voice/__init__.py`
  - `src/voice/domain/__init__.py`
  - `src/voice/application/__init__.py`
  - `src/voice/ports/__init__.py`
  - `src/voice/adapters/__init__.py`
  - `src/voice/worker/__init__.py`
  - `src/voice/projections/__init__.py`
- Tệp kiểm thử mới:
  - `tests/unit/voice/test_e01_package_layout.py`
  - `DetectorSelfTests` (3 test): kiểm tra tự thân bộ dò `find_forbidden_imports` và `find_forbidden_dirs` bao phủ các phản ví dụ: `from src.` / `import src.`, các gói lân cận (`creative`, `render`, `catalog`, `ingestion`, `source_ingestion`), `psycopg`, `temporalio`, `pydantic`, `socket`, `subprocess`, `urllib.request`, `http.client`, `controlplane.infrastructure`, `controlplane.ui`, `controlplane.api`, `controlplane.config`, import động qua `import_module` / `__import__`, và thư mục trùng `storage`, `orchestration`, `ui`, `config` ở mọi cấp.
  - `PackageLayoutTests` (6 test): kiểm tra gói `voice` import được từ root `src/`, tất cả các `__init__.py` chỉ chứa docstring, không có import bị cấm trong toàn bộ module của gói, không có thư mục trùng ở mọi cấp, thư mục `tests/unit/voice/` không chứa `__init__.py`, và tệp test khai báo dòng `coveredIds: không`.
- Xác nhận thư mục kiểm thử:
  - Thư mục `tests/unit/voice/` chỉ chứa tệp `test_e01_package_layout.py`, hoàn toàn không có `__init__.py` (được kiểm tra và xác nhận bởi test `test_voice_test_dir_has_no_init`).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 9 passed, 49 subtests passed in 0.04s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Test gọi `importlib.util.find_spec` trước `import_module` để trạng thái RED là `AssertionError` rõ ràng, không rơi vào `ModuleNotFoundError`.
2. Cấm theo tiền tố đúng ranh giới tên (`ingestion` cấm, `ingestion_tools` không; `subprocess` cấm, `subprocess_tools` không).
3. Gói `voice` không nằm trong danh sách cấm vì là gói của chính slice.
4. Quét thư mục cấm đệ quy mọi cấp dưới cây thư mục gói.
5. `coveredIds: không` theo đúng quy định của `slices.md` cho slice E-01.
6. Không thêm thư viện ngoài, chỉ dùng Python stdlib.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi `pyproject.toml`, `uv.lock`.
- Không gọi dịch vụ thật, không chạy FFmpeg.
