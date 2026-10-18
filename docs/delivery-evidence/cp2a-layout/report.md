# Báo cáo bằng chứng CP2A-LAYOUT

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline gốc của slice: `e79ae82c349bd4492323d22a0070f77bbbe82337`
- Baseline lượt cấp lại (generation sau thu hồi): `b1ff0ed5566f61e3bba874f031d8ab708dc1490f`

## Phần giữ lại từ lượt trước (commit b1ff0ed)

- `pyproject.toml` gốc thêm `pythonpath = ["src"]`.
- `src/controlplane/pyproject.toml` thêm `controlplane.config`, `controlplane.security` vào `package-dir` và `packages`, giữ nguyên các pin build-system và dependencies.
- Bỏ tiền tố `src.` ở:
  - `src/controlplane/config/router.py` (3 dòng)
  - `src/controlplane/config/adapter.py` (1 dòng)
  - `tests/unit/security/test_provider_routing.py`
  - `tests/unit/security/test_dpapi_broker.py`
  - `tests/unit/security/test_capability_view.py`
  - `tests/unit/security/test_http_router_adapter.py`
  - `tests/unit/security/test_provider_capacity_accounting.py`

## RED

- (a) Kết quả bước 1 (instrument nghiệm thu tại baseline b1ff0ed):
  - Exit code: 1
  - Nguyên văn danh sách bad: `AssertionError: ['src\\controlplane\\security\\broker.py', 'src\\controlplane\\security\\sanitizer.py']`
- (b) Kết quả bước 3 (chạy `python -m pytest tests/unit/security/test_import_root.py -q -p no:cacheprovider` trước khi sửa mã nguồn):
  - Exit code: 1
  - Dòng tóm tắt 2 failed do AssertionError định danh: `FAILED tests/unit/security/test_import_root.py::ImportRootTests::test_broker_uses_canonical_dpapi_decrypt` (AssertionError: `<function dpapi_decrypt at ...> is not <function dpapi_decrypt at ...>`), `FAILED tests/unit/security/test_import_root.py::ImportRootTests::test_sanitizer_uses_canonical_secret_credential` (AssertionError: `<class 'src.controlplane.security.interfaces.SecretCredential'> is not <class 'controlplane.security.interfaces.SecretCredential'>`).

## Thay đổi lượt này

- `tests/unit/security/test_import_root.py`: tệp mới kiểm tra `sanitizer.SecretCredential is interfaces.SecretCredential` và `broker.dpapi_decrypt is dpapi.dpapi_decrypt`.
- `src/controlplane/security/sanitizer.py`: dòng 2 bỏ tiền tố `src.`, đổi `from src.controlplane.security.interfaces import SecretCredential` thành `from controlplane.security.interfaces import SecretCredential`.
- `src/controlplane/security/broker.py`: dòng 9 bỏ tiền tố `src.`, đổi `from src.controlplane.security.dpapi import dpapi_decrypt` thành `from controlplane.security.dpapi import dpapi_decrypt`.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/security/test_import_root.py -q -p no:cacheprovider` | 0 | 2 passed in 0.04s |
| 2 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | 57 passed, 398 subtests passed in 0.16s |
| 3 | `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"` | 0 | PASS (không output, package-dir đủ mọi gói con có __init__.py, pythonpath có src, không còn import tiền tố src.) |
| 4 | `git diff --check` | 0 | PASS (không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Khai hai gói con ở cả `package-dir` và `packages` để wheel đủ gói.
2. `pythonpath` chỉ gồm `"src"`, không thêm `"."`.
3. Không thêm `sys.path.insert` vào mã sản phẩm hay test mới.
4. Phân hệ A–F sau này là gói cấp cao trong `src/` (`source_ingestion`, `ingestion`, `catalog`, `creative`, `voice`, `render`), G–J mở rộng trong `controlplane` — slice này không tạo các gói đó.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy tests/m1, tests/m2.
- Không đổi uv.lock.
- Không thêm thư viện.
- Các `sys.path.insert` sẵn có trong tests/m1, tests/m2, src/m1proof nằm ngoài phạm vi slice và không bị sửa.
