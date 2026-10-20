# Báo cáo CP-2B-DEPS

## Thư viện đã duyệt
- Chỉ thêm thư viện `temporalio==1.32.0` (nguồn: user duyệt Phần B ngày 18/10/2026 theo đề xuất; `docs/implementation/convergence/plan.md` mục 3.2 và D8-CV-07; giấy phép MIT).
- Ghi rõ: các thư viện `feedparser`, `trafilatura`, `faster-whisper`, và TTS thuộc dependency slice ADAPT-DEPS và KHÔNG thêm ở đây.

## Quyết định cryptography
- Theo `docs/implementation/convergence/plan.md` mục 3.3: `src/controlplane` giữ `cryptography==46.0.5`, `uv.lock` gốc giữ `50.0.1`.
- Giữ hai universe độc lập, không nâng phiên bản, không đổi M1-R1.

## Tệp đã đổi
- `src/controlplane/pyproject.toml`: thêm `temporalio==1.32.0`, khai gói `controlplane.api.routes.modules` và `controlplane.infrastructure.storage`.
- `src/controlplane/uv.lock`: chép nguyên văn bốn khối `temporalio`, `nexus-rpc`, `protobuf`, `types-protobuf` từ `uv.lock` gốc kèm hash; giữ `cryptography==46.0.5`.
- `src/controlplane/requirements.lock`: tái sinh kèm hash lấy từ `src/controlplane/uv.lock`, cập nhật via của `typing-extensions`.
- `src/controlplane/api/routes/modules/__init__.py`: tạo tệp rỗng hoàn toàn (0 byte).
- Ghi rõ: `pyproject.toml` gốc, `uv.lock` gốc, `src/controlplane/ui/package.json`, `src/controlplane/ui/package-lock.json` KHÔNG đổi vì không có thư viện UI nào cần thêm; mọi phiên bản trong `src/controlplane/ui/package.json` bắt đầu bằng chữ số.

## Phương pháp lockfile
- Lệnh uv/npm không nằm trong danh sách lệnh cho phép của lane nên `uv.lock` được cập nhật bằng cách chép nguyên bốn khối `temporalio`, `nexus-rpc`, `protobuf`, `types-protobuf` từ `uv.lock` gốc, `requirements.lock` được dựng từ hash trong `src/controlplane/uv.lock` và đối chiếu bằng probe bước 16.
- Đề nghị Control chạy lại `uv pip compile --generate-hashes` và `uv lock --check` ở bước R3 để xác nhận.

## Lệnh đã chạy
- Bước 8:
  - Lệnh: `python -c "import tomllib, pathlib; u = tomllib.loads(pathlib.Path('src/controlplane/uv.lock').read_text(encoding='utf-8')); r = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); pk = {p['name']: p for p in u['package']}; rk = {p['name']: p for p in r['package']}; c = pk['controlplane']; assert {'name': 'temporalio'} in c['dependencies'], c['dependencies']; assert {'name': 'temporalio', 'specifier': '==1.32.0'} in c['metadata']['requires-dist'], c['metadata']; ok = ['temporalio', 'nexus-rpc', 'protobuf', 'types-protobuf']; assert all(k in pk and pk[k] == rk[k] for k in ok), ok; assert pk['cryptography']['version'] == '46.0.5'; assert list(pk) == sorted(pk), list(pk)"`
  - exit code: 0
  - output: Không có lỗi, bốn gói khớp uv.lock gốc, cryptography giữ 46.0.5, thứ tự sorted.

- Bước 16:
  - Lệnh: `python -c "import tomllib, pathlib, re; u = tomllib.loads(pathlib.Path('src/controlplane/uv.lock').read_text(encoding='utf-8')); t = pathlib.Path('src/controlplane/requirements.lock').read_text(encoding='utf-8'); exp = {p['name']: (p['version'], set([w['hash'] for w in p.get('wheels', [])] + ([p['sdist']['hash']] if 'sdist' in p else []))) for p in u['package'] if p['name'] != 'controlplane'}; bl = [b for b in re.split(r'
(?=[A-Za-z0-9])', t) if re.match(r'[A-Za-z0-9_.-]+==', b)]; got = {re.match(r'([A-Za-z0-9_.-]+)==(\S+)', b).group(1): (re.match(r'([A-Za-z0-9_.-]+)==(\S+)', b).group(2), set(re.findall(r'--hash=(sha256:[0-9a-f]{64})', b))) for b in bl}; assert len(bl) == len(got), 'duplicate'; assert got.keys() == exp.keys(), (set(got) ^ set(exp)); bad = [k for k in exp if got[k] != exp[k]]; assert not bad, bad; assert '--generate-hashes' in t and 'temporalio==1.32.0' in t and 'cryptography==46.0.5' in t"`
  - exit code: 0
  - output: Không có lỗi, 27 gói khớp phiên bản và tập hash từ uv.lock, có --generate-hashes, temporalio==1.32.0 và cryptography==46.0.5.

- Bước 17:
  - Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert x and all('==' in i for i in x), x"`
  - exit code: 0
  - output: Không có lỗi, mọi dependency có dấu ==.

- Bước 18:
  - Lệnh: `python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p['dependencies'].values()) + list(p['devDependencies'].values()); assert v and all(i[0].isdigit() for i in v), v"`
  - exit code: 0
  - output: Không có lỗi, mọi phiên bản trong package.json bắt đầu bằng chữ số.

- Bước 19:
  - Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; n = ['controlplane.api.routes.modules', 'controlplane.infrastructure.storage']; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; assert all(k in s['packages'] and k in s['package-dir'] for k in n), n; assert all(pathlib.Path('src/controlplane', s['package-dir'][k], u).is_file() for k in n), n"`
  - exit code: 0
  - output: Không có lỗi, hai gói mới có trong packages và package-dir, file __init__.py tồn tại.

- Bước 20:
  - Lệnh: `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert 'temporalio==1.32.0' in x and len(x) == 7, x; s = d['tool']['setuptools']; assert set(s['packages']) == set(s['package-dir']) and len(s['packages']) == len(set(s['packages'])) == 45, len(s['packages']); u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; assert pathlib.Path('src/controlplane/api/routes/modules', u).read_text(encoding='utf-8') == ''; assert not any(pathlib.Path(p).exists() for p in ['src/controlplane/api/wiring', 'src/controlplane/application/orchestration/workflows', 'src/controlplane/workflows', 'tools/runtime/runtime.lock.json']); assert 'controlplane.api.wiring' not in s['packages'] and 'controlplane.application.orchestration.workflows' not in s['packages']"`
  - exit code: 0
  - output: Không có lỗi, đúng 7 dependency gồm temporalio==1.32.0; 45 gói khớp packages và package-dir; modules/__init__.py rỗng; 4 đường dẫn BL-CV-14 chưa tạo và không bị khai.

- Bước 21:
  - Lệnh: `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider`
  - exit code: 0
  - output: 9 passed in 7.96s

## BL-CV-14
| Đường dẫn | Trạng thái | Mã | Ghi chú |
| --- | --- | --- | --- |
| `src/controlplane/api/wiring/__init__.py` | BLOCKED | BL-CV-14 | Ngoài phong bì của gói, thư mục chưa tồn tại; Worker không tạo và không khai gói controlplane.api.wiring ở pyproject. |
| `src/controlplane/application/orchestration/workflows/__init__.py` | BLOCKED | BL-CV-14 | Ngoài phong bì; Worker không tạo và không khai gói controlplane.application.orchestration.workflows ở pyproject, không tạo gói controlplane.workflows ở src/controlplane/workflows. |
| `tools/runtime/runtime.lock.json` | BLOCKED | BL-CV-14 | Ngoài phong bì; Worker không tạo tệp này, không bịa sha256 hay phiên bản; mọi gói hoặc giá trị phụ thuộc nó dừng tới khi Control mở rộng phong bì. |

## Quan sát ngoài phạm vi
- `src/controlplane/application/__init__.py` và `src/controlplane/application/control_api/__init__.py` chưa tồn tại dù hai gói đã khai ở `src/controlplane/pyproject.toml` (không sửa, ngoài owned paths).
- Không có secret, token hay thông tin nhạy cảm nào được ghi trong báo cáo.
