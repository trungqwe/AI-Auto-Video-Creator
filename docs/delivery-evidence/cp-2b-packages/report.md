# Báo cáo CP-2B-PACKAGES

## Tệp đã sửa
- src/controlplane/pyproject.toml: thêm hai gói controlplane.api.wiring = api/wiring và controlplane.application.orchestration.workflows = application/orchestration/workflows vào cả packages và package-dir (4 dòng thêm, 0 dòng xoá); controlplane.infrastructure.storage = infrastructure/storage đã được CP-2B-DEPS khai ở cả hai bảng nên không thêm lại; không tạo hay sửa __init__.py nào (hai __init__.py rỗng do CP-2B-RUNTIME-PATHS tạo, infrastructure/storage/__init__.py đã có); không đổi dependency hay lockfile.

## Lệnh đã chạy
- Bước 3: python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; n = ['controlplane.api.wiring', 'controlplane.application.orchestration.workflows', 'controlplane.infrastructure.storage']; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; assert all(k in s['packages'] and k in s['package-dir'] for k in n), n; assert all(pathlib.Path('src/controlplane', s['package-dir'][k], u).is_file() for k in n), n" -> exit code 0, kết quả: Đạt, không có assertion error.
- Bước 4: python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert x and all('==' in i for i in x), x" -> exit code 0, kết quả: Đạt, không có assertion error.
- Bước 5: python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider -> exit code 0, kết quả: 9 passed in 6.25s.
- Bước 8: git diff --check -> exit code 0, kết quả: Đạt, không có output.

## BL-CV-14
BL-CV-14: PENDING

Giải thích: cổng GATE-CP-2B-DEPS-PATHS do Control thả cùng CP-2B-RUNTIME-PATHS sau khi có Auditor PASS; slice này không tự thả cổng.

## OI-EXT-02
OI-EXT-02: PENDING

Giải thích: gói controlplane.api.routes.modules thuộc CP-2B-DEPS đã biên dịch, ngoài phong bì; slice này không thêm, không sửa và không làm phần này; ghi chú sự thật quan sát được là pyproject.toml tại HEAD fb7bca7 đã chứa khai báo controlplane.api.routes.modules do CP-2B-DEPS thêm trước đó (dòng package-dir và dòng packages), slice giữ nguyên, không xoá vì xoá sẽ hoàn tác việc của CP-2B-DEPS và vi phạm bảng ranh giới; đề nghị Control/Auditor xác nhận cách hiểu tiêu chí 'pyproject.toml không chứa controlplane.api.routes.modules' là 'slice này không thêm'.

## Phạm vi
Xác nhận chỉ chạm hai owned paths: src/controlplane/pyproject.toml và docs/delivery-evidence/cp-2b-packages/report.md. Không ghi secret.
