# Nhật ký kết quả lệnh kiểm M7 (revision 4) - TRẠNG THÁI: BLOCKED TẠI BƯỚC 6

Các lệnh kiểm bắt buộc chạy trên candidate `b8b46c6365c243088988581dbf6d18ba5c7b4e20` (HEAD lúc bắt đầu, tiêu đề `integrate(PW-E2E): lane lane-pw-e2e candidate 44e8965191b6`) bằng interpreter khoá `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/1ca840a7/venv/Scripts/python.exe`.

Tiến trình kiểm thử đã hoàn thành 53/53 đoạn lệnh của Chuỗi 1 đến Chuỗi 5 với exit code 0. Tại Chuỗi 6, sau khi build UI và 3 probe đầu đạt exit code 0, đoạn 5 (probe kiểm tra `screenRegistry.ts` từ gói `CP-4B-UI-SCREENS`) bị thất bại với exit code 1 (AssertionError). Tổng số đoạn lệnh đã chạy: 58 đoạn (57 đạt, 1 thất bại).

## Chuỗi 1

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | git diff --check | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 3 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 4 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 5 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 6 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 7 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 8 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 9 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 10 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 11 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 12 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 2

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib, re; r = pathlib.Path('docs/delivery-evidence/user-ckp | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 3 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 3

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 4

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -B -m pytest tests/unit/control_ui/test_h_problem_detail.py tests/unit/co | 0 | 163 passed, 1 warning in 0.74s |  |
| 2 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; asser | 0 | không có đầu ra |  |
| 3 | python -B -m pytest tests/unit/voice/test_e01_package_layout.py tests/unit/creat | 0 | 54 passed, 284 subtests passed in 0.70s |  |
| 4 | python -B -m pytest tests/unit -q -p no:cacheprovider | 0 | 7516 passed, 1 warning, 2561 subtests passed in 19.62s |  |
| 5 | python -B -m pytest tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider | 0 | 5 passed, 1 warning in 7.74s |  |
| 6 | python -B -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b | 0 | 179 passed, 1 deselected, 2 warnings in 205.45s (0:03:25) | --deselect test_h36_m1_regression hoãn sang CP7 theo quyết định của user 21/10/2026 |
| 7 | python -B -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:ca | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 8 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q | 0 | 8 passed in 1.34s |  |
| 9 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 4.34s |  |
| 10 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5229 passed, 1 warning, 2254 subtests passed in 18.42s |  |
| 11 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastru | 0 | không có đầu ra |  |
| 12 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py | 0 | 1 passed in 0.28s |  |

## Chuỗi 5

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/test_pg_dsn_harness.py -q -p no:cacheprovider | 0 | 8 passed in 0.21s |  |
| 2 | python -m pytest tests/integration/persistence -q -p no:cacheprovider | 0 | 174 passed in 60.98s (0:01:00) |  |
| 3 | python -c "import pathlib; t = pathlib.Path('tests/integration/conftest.py').rea | 0 | không có đầu ra |  |
| 4 | python -m pytest tests/unit/collection/test_a01_package_layout.py::PackageLayout | 0 | 1 passed in 0.08s |  |
| 5 | python -m pytest tests/unit/collection -q -p no:cacheprovider | 0 | 455 passed, 378 subtests passed in 0.59s |  |
| 6 | python -m pytest tests/integration/persistence/a -q -p no:cacheprovider | 0 | 22 passed in 9.35s |  |
| 7 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 1075 passed, 89 subtests passed in 2.82s |  |
| 8 | python -m pytest tests/unit/render -q -p no:cacheprovider | 0 | 1314 passed, 487 subtests passed in 8.21s |  |
| 9 | python -m pytest tests/unit/ingestion -q -p no:cacheprovider | 0 | 477 passed in 0.40s |  |
| 10 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cache | 0 | 137 passed, 28 skipped, 1 warning in 2.65s | 28 skipped: thiếu PostgreSQL, không phải bằng chứng tài nguyên thật |
| 11 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q - | 0 | 23 passed in 4.50s |  |
| 12 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p  | 0 | 40 passed in 3.48s |  |
| 13 | python -c "import pathlib; t = pathlib.Path('.gitattributes').read_text(encoding | 0 | không có đầu ra |  |
| 14 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/vite.config.ts' | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p  | 0 | 113 passed in 9.98s |  |
| 16 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p  | 0 | 21 passed, 1 warning in 0.80s |  |
| 17 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cachep | 0 | 83 passed, 1 warning in 0.52s |  |
| 18 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q | 0 | 1 passed, 1 warning in 0.66s |  |
| 19 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/c | 0 | không có đầu ra |  |
| 20 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py  | 0 | 9 passed in 2.08s |  |
| 21 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:ca | 0 | 28 passed, 1 warning in 19.94s |  |
| 22 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_ | 0 | 3 passed in 1.27s |  |
| 23 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 24 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |

## Chuỗi 6

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | npm --prefix src/controlplane/ui run build | 0 | ✓ built in 2.75s | Build thành công; dist khớp nguyên trạng |
| 2 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 675 passed, 1 warning in 1.25s |  |
| 3 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 4 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f. | 0 | không có đầu ra |  |
| 5 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 1 | AssertionError: {'operations': 'available', 'batches': 'available', 'jobs': 'available', 'configs': 'available', 'sources': 'available', 'articles': 'available', 'events': 'available', 'media': 'available', 'hooks': 'available', 'artifacts': 'available', 'snapshots': 'available', 'story-angles': 'available', 'scripts': 'available', 'stage-runs': 'available', 'sessions': 'available', 'logs': 'pending_module', 'accounts': 'available', 'cost': 'available'} |  |
