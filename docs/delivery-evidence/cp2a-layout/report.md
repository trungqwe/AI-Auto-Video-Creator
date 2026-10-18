# B?o c?o b?ng ch?ng CP2A-LAYOUT

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `e79ae82c349bd4492323d22a0070f77bbbe82337`

## RED

- K?t qu? b??c 1 (instrument nghi?m thu t?i baseline): Exit code 1, `AssertionError: ['controlplane.config', 'controlplane.security']` do `src/controlplane/pyproject.toml` ch?a khai b?o hai g?i con trong `package-dir`.
- Chi ti?t hi?n tr?ng baseline: C? 15 d?ng import d?ng ti?n t? `src.` g?m:
  - 4 d?ng trong `src/controlplane/config/`: `router.py` (3 d?ng: 4, 10, 11), `adapter.py` (1 d?ng: 16).
  - 2 d?ng trong `src/controlplane/security/`: `sanitizer.py` (d?ng 2), `broker.py` (d?ng 9).
  - 11 d?ng trong `tests/unit/security/`: `test_provider_routing.py` (4 d?ng: 2, 3, 4, 10), `test_dpapi_broker.py` (2 d?ng: 6, 11), `test_capability_view.py` (1 d?ng: 21), `test_http_router_adapter.py` (2 d?ng: 12, 17), `test_provider_capacity_accounting.py` (2 d?ng: 3, 1293).
  - `pyproject.toml` g?c ch?a khai b?o `pythonpath` trong `[tool.pytest.ini_options]`.

## Thay ??i

- `pyproject.toml`: Th?m `pythonpath = ["src"]` v?o `[tool.pytest.ini_options]` ?? `src/` l? import root duy nh?t cho pytest.
- `src/controlplane/pyproject.toml`: Khai b?o `"controlplane.config" = "config"` v? `"controlplane.security" = "security"` trong `[tool.setuptools.package-dir]`; th?m `"controlplane.config"` v? `"controlplane.security"` v?o `[tool.setuptools].packages`. Gi? nguy?n 100% pin build-system v? dependencies.
- `src/controlplane/config/router.py`: B? ti?n t? `src.` t?i 3 d?ng import (`from controlplane.config.models import ...`, `from controlplane.security.interfaces import ProviderProtocol`, `from controlplane.config.adapter import ...`).
- `src/controlplane/config/adapter.py`: B? ti?n t? `src.` t?i d?ng 16 (`from controlplane.config.models import ...`).
- `tests/unit/security/test_provider_routing.py`: B? ti?n t? `src.` t?i 4 d?ng import (d?ng 2, 3, 4, 10).
- `tests/unit/security/test_dpapi_broker.py`: B? ti?n t? `src.` t?i 2 d?ng import (d?ng 6, 11).
- `tests/unit/security/test_capability_view.py`: B? ti?n t? `src.` t?i d?ng 21.
- `tests/unit/security/test_http_router_adapter.py`: B? ti?n t? `src.` t?i 2 d?ng import (d?ng 12, 17).
- `tests/unit/security/test_provider_capacity_accounting.py`: B? ti?n t? `src.` t?i 2 d?ng import (d?ng 3, 1293).

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | Kh?ng c? trailing whitespace ho?c k? t? CR th?a; ??nh d?ng LF s?ch |
| 2 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | 55 passed, 398 subtests passed in 0.25s (100% test passed) |
| 3 | `python -c "import tomllib, pathlib; d = tomllib.loads(?); assert d['build-system']['requires'] == [?]; assert d['project']['dependencies'] == [?]; s = d['tool']['setuptools']; assert set(s['packages']) == set(s['package-dir'])"` | 0 | Pin build-system v? dependencies gi? nguy?n; packages kh?p ho?n to?n package-dir |
| 4 | `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); ?; assert not miss, miss; ?; assert 'src' in ini.get('pythonpath', []); ?; assert not bad, bad"` | 1 | miss r?ng (?? package-dir); pytest pythonpath c? 'src'; bad ch? c?n 2 t?p ngo?i ph?m vi: `['src\\controlplane\\security\\broker.py', 'src\\controlplane\\security\\sanitizer.py']` |

## Quy?t ??nh m?c ??nh (D8)

1. Khai `controlplane.config` v? `controlplane.security` ? c? `package-dir` l?n `packages` ?? wheel ch?a ??y ?? hai g?i con.
2. `pythonpath` ch? g?m `"src"`, kh?ng th?m `"."`.
3. Kh?ng th?m `sys.path.insert` ? m? s?n ph?m hay ki?m th?.

## Blocker ngo?i ph?m vi

- Instrument b??c 14 ph?t hi?n ??ng 2 d?ng import ti?n t? `src.` ngo?i owned paths:
  - `src/controlplane/security/sanitizer.py:2`: `from src.controlplane.security.interfaces import SecretCredential`
  - `src/controlplane/security/broker.py:9`: `from src.controlplane.security.dpapi import dpapi_decrypt`
- Hai t?p n?y n?m ngo?i `Owned paths` ???c giao c?a nhi?m v? CP2A-LAYOUT. Tu?n th? nguy?n t?c Single-Writer v? ph?n quy?n ??ng (fail-closed), Worker kh?ng t? ? s?a hai t?p n?y.
- ?? xu?t Control m? r?ng owned paths th?m `src/controlplane/security/sanitizer.py` v? `src/controlplane/security/broker.py` ?? Worker b? ti?n t? `src.` ? hai d?ng n?y, ho?n t?t instrument nghi?m thu v?i exit code 0.

## Danh s?ch ch? user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10 (th? vi?n v? c?ch d?ng l?i runtime)
- CP7 t?i nguy?n th?t (D5)

## Gi?i h?n

- Kh?ng ch?y tests/m2 (t?i nguy?n d?nh ri?ng).
- Kh?ng ??i uv.lock.
- Kh?ng th?m th? vi?n ngo?i.
- Kh?ng ghi PASS cho l?nh ch?a ch?y.
