# CP2A-LAYOUT-PKGDIR-FIX — Báo cáo

## Thay đổi

Trong mục `[tool.setuptools.package-dir]` của tệp `src/controlplane/pyproject.toml`, đã thêm đúng hai dòng:

```toml
"controlplane.infrastructure.production_ports" = "infrastructure/production_ports"
"controlplane.infrastructure.read_screens" = "infrastructure/read_screens"
```

Hai dòng trên được đặt nằm giữa khoá `"controlplane.infrastructure.evidence"` và `"controlplane.infrastructure.security"`, cạnh các khoá `controlplane.infrastructure.*` hiện có.

Không đổi dòng nào khác của tệp:
- Không thay đổi danh sách `packages` trong `[tool.setuptools]`.
- Không thay đổi build-system, dependencies, phiên bản hay cấu hình build.
- Không sửa bất kỳ tệp lockfile nào (`uv.lock`, `requirements.lock`).
- Không sửa bất kỳ tệp nào ngoài owned paths.

## Lệnh kiểm đã chạy

| Bước | Lệnh | Mã thoát (exit code) | Kết quả |
|---|---|---|---|
| Bước 2 | `git diff --check` | 0 | Đạt (không có cảnh báo whitespace) |
| Bước 3 | `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"` | 0 | Đạt (mọi package có `__init__.py` dưới `src/controlplane` đều có trong `package-dir`, pytest pythonpath có src, không import tiền tố src.) |
| Bước 4 | `python -c "import pathlib, tomllib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']; assert d.get('controlplane.infrastructure.production_ports') == 'infrastructure/production_ports' and d.get('controlplane.infrastructure.read_screens') == 'infrastructure/read_screens', 'package-dir'"` | 0 | Đạt (khẳng định đúng hai giá trị package-dir mới) |
| Bước 5 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | Đạt (toàn bộ tests/unit pass) |

## Tổng kết tests/unit

Dòng tổng kết nguyên văn từ lệnh `python -m pytest tests/unit -q -p no:cacheprovider`:

```text
7477 passed, 1 warning, 2544 subtests passed in 12.59s
```

## Giới hạn

Gói này do Control lập nhằm khắc phục sự cố tích hợp seq 611 `INTEGRATION_HEAD_BROKEN` trên HEAD 98cd992 khi gộp `PW-CAT1`: hai gói `PP-1` và `RS-1` đã tạo package mới (`controlplane.infrastructure.production_ports` và `controlplane.infrastructure.read_screens`) trong phạm vi của chúng nhưng không thể khai báo trong `pyproject.toml` do `src/controlplane/pyproject.toml` là tài nguyên dành riêng (owned path riêng). Gói này chỉ khai đúng hai package bị thiếu nói trên theo seq 611 `INTEGRATION_HEAD_BROKEN`, không thay đổi bất kỳ logic sản phẩm, phụ thuộc hay cấu hình nào khác.
