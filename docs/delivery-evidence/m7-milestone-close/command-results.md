# Nhật ký kết quả lệnh kiểm M7 (revision 4) - ĐẠT 467/467

Các lệnh kiểm bắt buộc chạy trên candidate `380f128bfe3c1e7e4b862ed2a8768b9344e43e91` (HEAD sau rebase, tích hợp trên base `f080601bae4ed341837157aaf87b3bcd85bd7424`) bằng interpreter khoá `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: 2026-10-29
- Biến môi trường: `PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\M7-MILESTONE-CLOSE-R4-implement`

Tiến trình kiểm thử đã hoàn thành 467/467 đoạn lệnh kiểm bắt buộc thuộc 23 chuỗi lệnh, toàn bộ đều đạt exit code 0.
Tổng số đoạn lệnh đã chạy: 467 đoạn (467 đạt, 0 thất bại).

## Chuỗi 1/23

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
| 13 | python -c "import pathlib, re; r = pathlib.Path('docs/delivery-evidence/user-ckp | 0 | không có đầu ra |  |
| 14 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 15 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 16 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 2/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 2 | python -B -m pytest tests/unit/control_ui/test_h_problem_detail.py tests/unit/co | 0 | 163 passed, 1 warning in 0.65s |  |
| 3 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; asser | 0 | không có đầu ra |  |
| 4 | python -B -m pytest tests/unit/voice/test_e01_package_layout.py tests/unit/creat | 0 | 54 passed, 284 subtests passed in 0.85s |  |
| 5 | python -B -m pytest tests/unit -q -p no:cacheprovider | 0 | 7516 passed, 1 warning, 2561 subtests passed in 17.25s |  |
| 6 | python -B -m pytest tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider | 0 | 5 passed, 1 warning in 7.15s |  |
| 7 | python -B -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b | 0 | 179 passed, 1 deselected, 2 warnings in 210.33s (0:03:30) | --deselect test_h36_m1_regression hoãn sang CP7 theo quyết định của user 21/10/2026 |
| 8 | python -B -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:ca | 0 | 13 passed, 62 subtests passed in 0.11s |  |
| 9 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q | 0 | 8 passed in 1.35s |  |
| 10 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 4.36s |  |
| 11 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5229 passed, 1 warning, 2254 subtests passed in 17.28s |  |
| 12 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastru | 0 | không có đầu ra |  |
| 13 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py | 0 | 1 passed in 0.28s |  |
| 14 | python -m pytest tests/integration/test_pg_dsn_harness.py -q -p no:cacheprovider | 0 | 8 passed in 0.16s |  |
| 15 | python -m pytest tests/integration/persistence -q -p no:cacheprovider | 0 | 174 passed in 65.32s (0:01:05) |  |
| 16 | python -c "import pathlib; t = pathlib.Path('tests/integration/conftest.py').rea | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/unit/collection/test_a01_package_layout.py::PackageLayout | 0 | 1 passed in 0.08s |  |
| 18 | python -m pytest tests/unit/collection -q -p no:cacheprovider | 0 | 455 passed, 378 subtests passed in 0.61s |  |
| 19 | python -m pytest tests/integration/persistence/a -q -p no:cacheprovider | 0 | 22 passed in 9.85s |  |
| 20 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 1075 passed, 89 subtests passed in 2.79s |  |
| 21 | python -m pytest tests/unit/render -q -p no:cacheprovider | 0 | 1314 passed, 487 subtests passed in 8.54s |  |
| 22 | python -m pytest tests/unit/ingestion -q -p no:cacheprovider | 0 | 477 passed in 0.40s |  |
| 23 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cache | 0 | 137 passed, 28 skipped, 1 warning in 2.54s | Số test skipped (nếu có) là do thiếu PostgreSQL fixture, không phải bằng chứng tài nguyên thật |
| 24 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q - | 0 | 23 passed in 4.84s |  |
| 25 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p  | 0 | 40 passed in 3.67s |  |
| 26 | python -c "import pathlib; t = pathlib.Path('.gitattributes').read_text(encoding | 0 | không có đầu ra |  |
| 27 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/vite.config.ts' | 0 | không có đầu ra |  |
| 28 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p  | 0 | 113 passed in 9.70s |  |
| 29 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p  | 0 | 21 passed, 1 warning in 0.83s |  |
| 30 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cachep | 0 | 83 passed, 1 warning in 0.49s |  |
| 31 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q | 0 | 1 passed, 1 warning in 0.82s |  |
| 32 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/c | 0 | không có đầu ra |  |
| 33 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py  | 0 | 9 passed in 2.15s |  |
| 34 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:ca | 0 | 28 passed, 1 warning in 19.43s |  |
| 35 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_ | 0 | 3 passed in 1.20s |  |
| 36 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 37 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |

## Chuỗi 3/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | npm --prefix src/controlplane/ui run build | 0 | ✓ 42 modules transformed. | npm run build không làm đổi dist |
| 2 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 675 passed, 1 warning in 1.04s |  |
| 3 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 4 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f. | 0 | không có đầu ra |  |
| 5 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider | 0 | 26 passed, 31 subtests passed in 0.05s |  |
| 7 | python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py  | 0 | 5 passed in 0.14s |  |
| 8 | python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q - | 0 | 15 passed in 5.05s |  |
| 9 | python -m pytest tests/unit/catalog -q -p no:cacheprovider | 0 | 202 passed, 463 subtests passed in 0.25s |  |
| 10 | python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' /  | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q | 0 | 9 passed in 2.05s |  |
| 12 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 13 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 14 | python -c "import pathlib; t = pathlib.Path('tests/integration/conftest.py').rea | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p n | 0 | 37 passed in 2.63s |  |
| 16 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml') | 0 | không có đầu ra |  |
| 17 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 18 | python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_t | 0 | không có đầu ra |  |
| 19 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 20 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml') | 0 | không có đầu ra |  |
| 21 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_screen | 0 | không có đầu ra |  |
| 22 | python -m pytest tests/integration/convergence/test_cp4_wiring_fix3.py -q -p no: | 0 | 34 passed, 1 warning in 1.21s |  |
| 23 | python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cachep | 0 | 45 passed in 0.06s |  |
| 24 | python -c "import ast, pathlib; m = ast.parse(pathlib.Path('src/controlplane/app | 0 | không có đầu ra |  |
| 25 | python -c "import pathlib; q = pathlib.Path('tests/integration/convergence/test_ | 0 | không có đầu ra |  |
| 26 | python -c "import pathlib; t = pathlib.Path('src/controlplane/api/wiring/product | 0 | không có đầu ra |  |
| 27 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 28 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d  | 0 | không có đầu ra |  |

## Chuỗi 4/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 2 | python -c "import pathlib, re; t = pathlib.Path('docs/implementation/prod-wiring | 0 | không có đầu ra |  |
| 3 | python -c "import pathlib, re; t = pathlib.Path('docs/implementation/prod-wiring | 0 | không có đầu ra |  |
| 4 | python -c "import pathlib, re, unicodedata; s = unicodedata.normalize('NFC', pat | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib, unicodedata; s = unicodedata.normalize('NFC', pathlib | 0 | không có đầu ra |  |
| 6 | python -c "import pathlib; r = pathlib.Path('docs/delivery-evidence/impl-plan-pr | 0 | không có đầu ra |  |
| 7 | python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); | 0 | không có đầu ra |  |
| 8 | python -c "import pathlib, tomllib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/unit -q -p no:cacheprovider | 0 | 7516 passed, 1 warning, 2561 subtests passed in 17.47s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/cp2a-layout- | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py -q -p no: | 0 | 20 passed in 11.41s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-a3-fix1/r | 0 | không có đầu ra |  |

## Chuỗi 5/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p  | 0 | 9 passed in 3.41s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e3-fix1/r | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py -q -p n | 0 | 14 passed in 5.89s |  |
| 4 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-i1-fix1/r | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p | 0 | 16 passed in 42.18s |  |
| 6 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f4-fix1/r | 0 | không có đầu ra |  |
| 7 | python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p | 0 | 11 passed in 6.85s |  |
| 8 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-a3-fix2/r | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no | 0 | 20 passed in 45.03s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-seed-f | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no | 0 | 18 passed in 9.94s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-d3-fix1/r | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py - | 0 | 16 passed in 7.81s |  |
| 14 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix1/r | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p  | 0 | 13 passed in 6.33s |  |
| 16 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix2/r | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py -q -p | 0 | 46 passed in 23.30s |  |
| 18 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix3/r | 0 | không có đầu ra |  |
| 19 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:c | 0 | 57 passed in 0.24s |  |
| 20 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f4-fix2/r | 0 | không có đầu ra |  |
| 21 | python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cach | 0 | 187 passed in 6.72s |  |
| 22 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/f-10-fix1/re | 0 | không có đầu ra |  |
| 23 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-i1-fix2/r | 0 | không có đầu ra |  |
| 24 | python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py -q | 0 | 44 passed in 10.18s |  |
| 25 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f1-fix1/r | 0 | không có đầu ra |  |
| 26 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/adapt-seed-f | 0 | không có đầu ra |  |
| 27 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-w2-fix4/r | 0 | không có đầu ra |  |
| 28 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/f-10-fix2/re | 0 | không có đầu ra |  |
| 29 | python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py te | 0 | 60 passed in 53.29s |  |
| 30 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f1-fix2/r | 0 | không có đầu ra |  |

## Chuỗi 6/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cache | 0 | 13 passed, 62 subtests passed in 0.11s |  |
| 2 | python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q | 0 | 27 passed, 99 subtests passed in 0.06s |  |
| 3 | python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cac | 0 | 17 passed, 50 subtests passed in 0.04s |  |
| 4 | python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cachepr | 0 | 74 passed in 0.08s |  |
| 5 | python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p n | 0 | 40 passed, 20 subtests passed in 0.05s |  |
| 6 | python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprov | 0 | 15 passed, 22 subtests passed in 0.04s |  |
| 7 | python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cac | 0 | 14 passed, 44 subtests passed in 0.03s |  |
| 8 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cachepr | 0 | 32 passed, 3 subtests passed in 0.08s |  |
| 9 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p  | 0 | 28 passed, 11 subtests passed in 0.10s |  |
| 10 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py | 0 | 23 passed, 14 subtests passed in 0.10s |  |
| 11 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p n | 0 | 18 passed in 0.10s |  |
| 12 | python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cachepr | 0 | 59 passed in 0.08s |  |
| 13 | python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cach | 0 | 49 passed in 0.09s |  |
| 14 | python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p | 0 | 19 passed in 0.10s |  |
| 15 | python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:c | 0 | 20 passed, 49 subtests passed in 0.05s |  |
| 16 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no: | 0 | 25 passed in 0.11s |  |
| 17 | python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cachepro | 0 | 33 passed, 29 subtests passed in 0.09s |  |
| 18 | python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p  | 0 | 32 passed in 0.11s |  |
| 19 | python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cachepr | 0 | 62 passed in 0.12s |  |

## Chuỗi 7/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.to | 0 | không có đầu ra |  |
| 2 | python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock' | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cac | 0 | 27 passed in 5.69s |  |
| 4 | python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t  | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/securit | 0 | 20 passed in 0.15s |  |
| 6 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 7 | python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no: | 0 | 34 passed in 0.57s |  |
| 8 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q  | 0 | 41 passed in 0.22s |  |
| 10 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cache | 0 | 54 passed in 3.52s |  |
| 12 | python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cachep | 0 | 22 passed in 13.87s |  |
| 14 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/sec | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cachep | 0 | 33 passed in 1.85s |  |
| 16 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/sto | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q  | 0 | 11 passed in 0.03s |  |
| 18 | python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [j | 0 | không có đầu ra |  |
| 19 | python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring') | 0 | không có đầu ra |  |
| 20 | python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_see | 0 | không có đầu ra |  |

## Chuỗi 8/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p | 0 | 39 passed in 0.07s |  |
| 2 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit | 0 | 30 passed in 0.05s |  |
| 3 | python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/ | 0 | 19 passed in 0.04s |  |
| 4 | python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:c | 0 | 64 passed in 0.06s |  |
| 5 | python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no: | 0 | 27 passed in 0.03s |  |
| 6 | python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p n | 0 | 31 passed in 0.07s |  |
| 7 | python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cach | 0 | 45 passed in 0.07s |  |
| 8 | python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:ca | 0 | 61 passed in 0.08s |  |
| 9 | python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cach | 0 | 39 passed in 0.06s |  |
| 10 | python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cachepr | 0 | 55 passed in 0.07s |  |
| 11 | python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p n | 0 | 67 passed in 0.11s |  |
| 12 | python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py  | 0 | 15 passed in 0.09s |  |
| 13 | python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovi | 0 | 20 passed, 37 subtests passed in 0.06s |  |
| 14 | python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovide | 0 | 20 passed, 45 subtests passed in 0.04s |  |
| 15 | python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprov | 0 | 11 passed, 11 subtests passed in 0.03s |  |
| 16 | python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cachepro | 0 | 20 passed, 33 subtests passed in 0.04s |  |
| 17 | python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cac | 0 | 27 passed, 19 subtests passed in 0.04s |  |
| 18 | python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cachepro | 0 | 31 passed, 189 subtests passed in 0.07s |  |
| 19 | python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cachepro | 0 | 20 passed, 87 subtests passed in 0.05s |  |
| 20 | python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider | 0 | 27 passed, 11 subtests passed in 0.05s |  |

## Chuỗi 9/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit | 0 | 94 passed in 0.11s |  |
| 2 | python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no: | 0 | 680 passed, 1 warning in 7.95s |  |
| 3 | python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/ss | 0 | không có đầu ra |  |
| 4 | python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py - | 0 | 16 passed in 6.92s |  |
| 5 | python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cac | 0 | 850 passed, 1 warning in 1.99s |  |

## Chuỗi 10/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_ha | 0 | 179 passed, 1 deselected, 2 warnings in 203.30s (0:03:23) | --deselect test_h36_m1_regression hoãn sang CP7 theo quyết định của user 21/10/2026 |

## Chuỗi 11/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 2 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/ | 0 | 30 passed, 1 warning in 4.58s |  |

## Chuỗi 12/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider | 0 | 4484 passed, 36 skipped, 1 warning, 25 subtests passed in 690.92s (0:11:30) |  |

## Chuỗi 13/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib; p = pathlib.Path('src/controlplane/application/contro | 0 | không có đầu ra |  |
| 2 | python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / | 0 | không có đầu ra |  |
| 3 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 4 | python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runt | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = p | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider | 0 | 9 passed in 9.01s |  |
| 7 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 8 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 293 passed in 0.38s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-an | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/unit/config tests/unit/storage tests/integration/converge | 0 | 1125 passed, 239 subtests passed in 0.94s |  |
| 12 | python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/con | 0 | 679 passed, 398 subtests passed in 1.76s |  |
| 13 | python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery | 0 | không có đầu ra |  |
| 14 | python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/orchestration tests/integration/storage tests | 0 | 2349 passed, 7 skipped, 1189 subtests passed in 16.54s |  |
| 16 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests | 0 | 30 passed in 1.70s |  |
| 18 | python -m pytest tests/unit/orchestration tests/integration/collection tests/uni | 0 | 3394 passed, 1034 subtests passed in 3.50s |  |
| 19 | python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/u | 0 | không có đầu ra |  |
| 20 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 21 | python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.p | 0 | không có đầu ra |  |
| 22 | python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests | 0 | 25 passed in 0.07s |  |
| 23 | python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_state | 0 | 666 passed, 841 subtests passed in 0.91s |  |

## Chuỗi 14/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect te | 0 | 3988 passed, 36 skipped, 1 deselected, 2 warnings, 25 subtests passed in 890.37s (0:14:50) | --deselect test_h36_m1_regression hoãn sang CP7 theo quyết định của user 21/10/2026 |

## Chuỗi 15/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5311 passed, 1 warning, 2015 subtests passed in 17.73s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='u | 0 | không có đầu ra |  |
| 3 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 4 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').r | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cachepr | 0 | 16 passed, 70 subtests passed in 0.14s |  |
| 6 | python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:ca | 0 | 68 passed in 0.09s |  |
| 7 | python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cac | 0 | 11 passed, 13 subtests passed in 0.04s |  |
| 8 | python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:ca | 0 | 87 passed in 0.11s |  |
| 9 | python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cache | 0 | 20 passed, 79 subtests passed in 0.06s |  |
| 10 | python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprov | 0 | 60 passed in 0.07s |  |
| 11 | python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no | 0 | 32 passed in 0.05s |  |
| 12 | python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cachepr | 0 | 62 passed in 0.10s |  |
| 13 | python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cachep | 0 | 110 passed in 0.16s |  |
| 14 | python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cachep | 0 | 94 passed in 0.14s |  |
| 15 | python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cac | 0 | 62 passed in 0.12s |  |
| 16 | python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cachep | 0 | 19 passed, 38 subtests passed in 0.04s |  |
| 17 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprov | 0 | 65 passed in 0.13s |  |
| 18 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p  | 0 | 18 passed in 0.14s |  |
| 19 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p n | 0 | 27 passed in 0.13s |  |
| 20 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no | 0 | 52 passed in 0.14s |  |
| 21 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cache | 0 | 22 passed in 0.10s |  |
| 22 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cache | 0 | 8 passed in 0.23s |  |

## Chuỗi 16/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovi | 0 | 16 passed, 89 subtests passed in 0.15s |  |
| 2 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cache | 0 | 65 passed in 0.07s |  |
| 3 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 144 passed in 0.12s |  |
| 4 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovi | 0 | 86 passed in 0.09s |  |
| 5 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovide | 0 | 50 passed in 0.06s |  |
| 6 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprov | 0 | 75 passed in 0.08s |  |
| 7 | python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprov | 0 | 106 passed in 0.12s |  |
| 8 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.08s |  |
| 9 | python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider | 0 | 114 passed in 0.11s |  |
| 10 | python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprov | 0 | 51 passed in 0.06s |  |
| 11 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovi | 0 | 21 passed in 0.05s |  |
| 12 | python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cachepr | 0 | 35 passed in 0.08s |  |
| 13 | python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider | 0 | 63 passed in 0.07s |  |
| 14 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cach | 0 | 79 passed in 0.13s |  |
| 15 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovide | 0 | 47 passed in 0.08s |  |
| 16 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p | 0 | 23 passed in 0.11s |  |
| 17 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py - | 0 | 45 passed in 0.13s |  |
| 18 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:ca | 0 | 44 passed in 0.17s |  |
| 19 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cachepro | 0 | 35 passed in 0.08s |  |
| 20 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cachepro | 0 | 25 passed in 1.84s |  |
| 21 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprov | 0 | 22 passed, 125 subtests passed in 0.46s |  |
| 22 | python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cachepro | 0 | 26 passed, 67 subtests passed in 0.11s |  |
| 23 | python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no: | 0 | 169 passed in 0.16s |  |
| 24 | python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cach | 0 | 58 passed in 0.11s |  |
| 25 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cachepro | 0 | 62 passed in 0.10s |  |
| 26 | python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q - | 0 | 104 passed in 0.11s |  |
| 27 | python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py  | 0 | 97 passed in 0.11s |  |
| 28 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cachepr | 0 | 55 passed in 0.12s |  |
| 29 | python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovid | 0 | 118 passed in 0.11s |  |
| 30 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprov | 0 | 97 passed in 0.12s |  |
| 31 | python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprov | 0 | 45 passed, 129 subtests passed in 0.11s |  |
| 32 | python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cachepro | 0 | 38 passed, 99 subtests passed in 0.07s |  |
| 33 | python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovi | 0 | 52 passed, 67 subtests passed in 0.09s |  |
| 34 | python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovid | 0 | 73 passed in 0.12s |  |
| 35 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cach | 0 | 39 passed in 0.10s |  |
| 36 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py  | 0 | 36 passed in 0.14s |  |
| 37 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q - | 0 | 28 passed in 0.14s |  |
| 38 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q | 0 | 35 passed in 0.20s |  |
| 39 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cachepr | 0 | 17 passed in 0.11s |  |
| 40 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cachepr | 0 | 55 passed in 0.12s |  |

## Chuỗi 17/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:ca | 0 | 43 passed in 0.05s |  |
| 2 | python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no: | 0 | 22 passed, 307 subtests passed in 0.06s |  |
| 3 | python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovid | 0 | 45 passed in 0.06s |  |
| 4 | python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cach | 0 | 45 passed in 0.06s |  |
| 5 | python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:c | 0 | 55 passed in 0.06s |  |
| 6 | python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/or | 0 | 147 passed in 0.14s |  |
| 7 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit | 0 | 88 passed in 0.22s |  |
| 8 | python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q  | 0 | 47 passed in 0.07s |  |
| 9 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cac | 0 | 86 passed in 0.08s |  |
| 10 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q  | 0 | 62 passed in 0.09s |  |
| 11 | python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit | 0 | 110 passed in 0.10s |  |
| 12 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/ | 0 | 85 passed in 0.10s |  |
| 13 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/or | 0 | 175 passed in 0.14s |  |
| 14 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orc | 0 | 157 passed in 0.16s |  |
| 15 | python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:c | 0 | 55 passed in 0.07s |  |
| 16 | python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovid | 0 | 115 passed in 0.09s |  |
| 17 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:c | 0 | 70 passed in 0.07s |  |
| 18 | python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p n | 0 | 175 passed, 1 warning in 1.26s |  |
| 19 | python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cachep | 0 | 31 passed in 0.05s |  |
| 20 | python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:c | 0 | 91 passed in 0.09s |  |
| 21 | python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cachepr | 0 | 37 passed in 0.30s |  |
| 22 | python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cach | 0 | 43 passed, 1 warning in 0.43s |  |
| 23 | python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cach | 0 | 10 passed in 0.03s |  |
| 24 | python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:ca | 0 | 9 passed in 0.03s |  |
| 25 | python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovi | 0 | 22 passed in 0.03s |  |
| 26 | python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cac | 0 | 24 passed in 0.04s |  |
| 27 | python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no | 0 | 14 passed in 0.03s |  |
| 28 | python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cachep | 0 | 26 passed in 0.06s |  |
| 29 | python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cachepr | 0 | 65 passed in 0.10s |  |
| 30 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cac | 0 | 24 passed in 0.05s |  |
| 31 | python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cachep | 0 | 11 passed, 85 subtests passed in 0.04s |  |
| 32 | python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cache | 0 | 22 passed, 21 subtests passed in 0.04s |  |
| 33 | python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p n | 0 | 21 passed in 6.04s |  |
| 34 | python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p n | 0 | 373 passed, 7 skipped in 0.97s |  |
| 35 | python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cac | 0 | 25 passed, 26 subtests passed in 0.05s |  |
| 36 | python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no: | 0 | 67 passed in 0.07s |  |
| 37 | python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q - | 0 | 21 passed in 0.13s |  |
| 38 | python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cach | 0 | 13 passed, 10 subtests passed in 0.05s |  |
| 39 | python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cache | 0 | 32 passed, 97 subtests passed in 0.06s |  |
| 40 | python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprov | 0 | 56 passed in 0.07s |  |
| 41 | python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cachep | 0 | 41 passed in 0.05s |  |

## Chuỗi 18/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovide | 0 | 50 passed in 0.05s |  |
| 2 | python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cachepr | 0 | 55 passed in 0.05s |  |
| 3 | python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider | 0 | 60 passed in 0.07s |  |
| 4 | python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider | 0 | 118 passed in 0.11s |  |
| 5 | python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cachepro | 0 | 49 passed in 0.07s |  |
| 6 | python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprov | 0 | 40 passed in 0.05s |  |
| 7 | python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cachepro | 0 | 104 passed in 0.08s |  |
| 8 | python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprov | 0 | 131 passed in 0.10s |  |
| 9 | python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovid | 0 | 104 passed in 0.09s |  |
| 10 | python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovi | 0 | 63 passed in 0.08s |  |
| 11 | python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cach | 0 | 51 passed in 0.07s |  |
| 12 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cache | 0 | 66 passed in 0.07s |  |
| 13 | python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovid | 0 | 50 passed in 0.08s |  |
| 14 | python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovi | 0 | 41 passed in 0.08s |  |
| 15 | python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovid | 0 | 47 passed in 0.07s |  |
| 16 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cachepro | 0 | 35 passed in 0.06s |  |
| 17 | python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no: | 0 | 35 passed in 0.46s |  |
| 18 | python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:c | 0 | 33 passed in 0.09s |  |
| 19 | python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q - | 0 | 22 passed in 9.92s |  |
| 20 | python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persiste | 0 | không có đầu ra |  |
| 21 | python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q - | 0 | 14 passed in 5.71s |  |
| 22 | python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').r | 0 | không có đầu ra |  |
| 23 | python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rgl | 0 | không có đầu ra |  |
| 24 | python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q - | 0 | 22 passed in 9.43s |  |
| 25 | python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rg | 0 | không có đầu ra |  |
| 26 | python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q - | 0 | 19 passed in 8.78s |  |
| 27 | python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob | 0 | không có đầu ra |  |
| 28 | python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q - | 0 | 20 passed in 8.62s |  |
| 29 | python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglo | 0 | không có đầu ra |  |
| 30 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 31 | python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q - | 0 | 16 passed in 5.95s |  |
| 32 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 33 | python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q - | 0 | 18 passed in 6.46s |  |
| 34 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |

## Chuỗi 19/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/prod_ports/test_pp_1_gpu_lease.py -q -p no:ca | 0 | 30 passed in 0.04s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/prod_ports/test_pp_2_credentials.py -q -p no: | 0 | 84 passed in 0.85s |  |
| 4 | python -c "import pathlib, json; d = pathlib.Path('src/controlplane/infrastructu | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/integration/prod_ports/test_pp_3_drive_token.py -q -p no: | 0 | 25 passed in 8.81s |  |
| 6 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 7 | python -m pytest tests/integration/prod_ports/test_pp_4_artifact_source.py -q -p | 0 | 55 passed, 1 skipped in 0.73s |  |
| 8 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/integration/prod_ports/test_pp_5_drive_placement.py -q -p | 0 | 55 passed in 28.94s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/prod_ports/test_pp_6_route_catalog.py -q -p n | 0 | 27 passed in 0.21s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/prod_ports/test_pp_7_vision_route.py -q -p no | 0 | 87 passed in 36.49s |  |
| 14 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/prod_ports/test_pp_8_assembly.py -q -p no:cac | 0 | 15 passed in 15.34s |  |
| 16 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/pro | 0 | không có đầu ra |  |

## Chuỗi 20/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/prod_wiring/test_pw_h0_harness.py -q -p no:ca | 0 | 34 passed in 2.92s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('tests/integration/prod_wiring/conft | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/prod_wiring/test_pw_schema_migration.py tests | 0 | 12 passed in 2.38s |  |
| 4 | python -c "import pathlib, re; ps = sorted(pathlib.Path('tests/integration/persi | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/integration/prod_wiring/test_pw_g1_app_session.py tests/i | 0 | 124 passed in 14.65s |  |
| 7 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 8 | python -m pytest tests/integration/prod_wiring/test_pw_g2_stage_runs.py tests/in | 0 | 96 passed in 21.04s |  |
| 9 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 10 | python -m pytest tests/integration/prod_wiring/test_pw_g3_grants.py tests/integr | 0 | 53 passed in 16.97s |  |
| 11 | python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orches | 0 | không có đầu ra |  |
| 12 | python -m pytest tests/integration/prod_wiring/test_pw_g4_job_states.py tests/in | 0 | 161 passed in 39.83s |  |
| 13 | python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orches | 0 | không có đầu ra |  |
| 14 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/integ | 0 | 84 passed in 1.22s |  |
| 15 | python -c "import re, pathlib; t = pathlib.Path('src/controlplane/domain/orchest | 0 | không có đầu ra |  |
| 16 | python -m pytest tests/integration/prod_wiring/test_pw_cat2_flow.py tests/integr | 0 | 39 passed in 3.78s |  |
| 17 | python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orches | 0 | không có đầu ra |  |
| 18 | python -m pytest tests/integration/prod_wiring/test_pw_g5_allocation.py tests/in | 0 | 36 passed in 9.44s |  |
| 19 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit | 0 | 111 passed in 5.04s |  |
| 20 | python -c "import pathlib; t = pathlib.Path('src/controlplane/application/orches | 0 | không có đầu ra |  |
| 21 | python -m pytest tests/integration/prod_wiring/test_pw_g6_outbox_relay.py tests/ | 0 | 77 passed in 15.99s |  |
| 22 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 23 | python -m pytest tests/integration/prod_wiring/test_pw_g7_completion.py -q -p no | 0 | 20 passed in 11.46s |  |
| 24 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 25 | python -m pytest tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p  | 0 | 8 passed in 29.42s |  |
| 26 | python -c "import pathlib; t = pathlib.Path('tests/integration/prod_wiring/pw_ve | 0 | không có đầu ra |  |
| 27 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests | 0 | 102 passed, 70 subtests passed in 3.78s |  |
| 28 | python -c "import pathlib; t = pathlib.Path('src/creative/application/roles.py') | 0 | không có đầu ra |  |
| 29 | python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py t | 0 | 102 passed, 70 subtests passed in 8.34s |  |
| 30 | python -c "import pathlib; t = pathlib.Path('src/creative/adapters/postgres_sele | 0 | không có đầu ra |  |
| 31 | python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py tests/un | 0 | 34 passed, 70 subtests passed in 10.91s |  |
| 32 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 33 | python -m pytest tests/integration/prod_wiring/test_pw_e1_persistence.py tests/i | 0 | 24 passed in 10.83s |  |
| 34 | python -c "import pathlib; t = pathlib.Path('src/voice/persistence/output_reposi | 0 | không có đầu ra |  |
| 35 | python -m pytest tests/integration/prod_wiring/test_pw_e2_voice_ports.py tests/i | 0 | 60 passed, 89 subtests passed in 2.02s |  |
| 36 | python -c "import pathlib; t = pathlib.Path('src/voice/application/voice_pipelin | 0 | không có đầu ra |  |
| 37 | python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py tests/ | 0 | 25 passed, 89 subtests passed in 3.60s |  |
| 38 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 39 | python -m pytest tests/integration/prod_wiring/test_pw_e4_audio_bed.py tests/uni | 0 | 39 passed, 89 subtests passed in 3.30s |  |
| 40 | python -c "import json, pathlib, re; j = json.loads(pathlib.Path('tools/launcher | 0 | không có đầu ra |  |
| 41 | python -m pytest tests/integration/prod_wiring/test_pw_f1_inspector_visual.py te | 0 | 66 passed, 125 subtests passed in 12.08s |  |
| 42 | python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_ins | 0 | không có đầu ra |  |

## Chuỗi 21/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/prod_wiring/test_pw_f2_inspector_audio.py tes | 0 | 94 passed, 125 subtests passed in 25.52s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('src/render/adapters/real_output_ins | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests | 0 | 68 passed, 125 subtests passed in 24.22s |  |
| 4 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py tests | 0 | 177 passed, 125 subtests passed in 46.61s |  |
| 6 | python -c "import pathlib; t = pathlib.Path('src/render/worker/activity_handler. | 0 | không có đầu ra |  |
| 7 | python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py tests/i | 0 | 30 passed in 11.82s |  |
| 8 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/integration/prod_wiring/test_pw_i2_persist_output.py -q - | 0 | 11 passed in 4.68s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('src/controlplane/application/storag | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/prod_wiring/test_pw_a1_plan_cycle.py tests/un | 0 | 28 passed, 62 subtests passed in 6.42s |  |
| 12 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/prod_wiring/test_pw_a2_collect_resolve.py tes | 0 | 66 passed, 62 subtests passed in 11.63s |  |
| 14 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/prod_wiring/test_pw_a3_scheduler.py tests/int | 0 | 104 passed in 18.87s |  |
| 16 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/integration/prod_wiring/test_pw_b1_candidate_selector.py  | 0 | 48 passed in 4.81s |  |
| 18 | python -c "import pathlib; t = pathlib.Path('src/ingestion/application/candidate | 0 | không có đầu ra |  |
| 19 | python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py tests | 0 | 189 passed, 1 warning in 33.34s |  |
| 20 | python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_t | 0 | không có đầu ra |  |
| 21 | python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/ | 0 | 191 passed, 1 warning in 31.88s |  |
| 22 | python -c "import ast, pathlib; t = pathlib.Path('src/controlplane/api/wiring/cr | 0 | không có đầu ra |  |
| 23 | python -c "import pathlib; t = pathlib.Path('src/controlplane/api/wiring/product | 0 | không có đầu ra |  |
| 24 | python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p  | 0 | 10 passed, 1 warning in 120.60s (0:02:00) |  |
| 25 | python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/repor | 0 | không có đầu ra |  |

## Chuỗi 22/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/read_screens/test_rs_1_common.py -q -p no:cac | 0 | 41 passed in 1.51s |  |
| 2 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/read_screens/test_rs_2_articles.py -q -p no:c | 0 | 30 passed in 0.71s |  |
| 4 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/integration/read_screens/test_rs_3_events.py -q -p no:cac | 0 | 31 passed in 0.71s |  |
| 6 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 7 | python -m pytest tests/integration/read_screens/test_rs_4_media.py -q -p no:cach | 0 | 60 passed in 0.79s |  |
| 8 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 9 | python -m pytest tests/integration/read_screens/test_rs_5_artifacts.py -q -p no: | 0 | 51 passed in 0.74s |  |
| 10 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 11 | python -m pytest tests/integration/read_screens/test_rs_6_snapshots.py -q -p no: | 0 | 41 passed in 0.80s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/read_screens/test_rs_7_story_angles.py -q -p  | 0 | 29 passed in 0.76s |  |
| 14 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/read_screens/test_rs_8_scripts.py -q -p no:ca | 0 | 33 passed in 1.07s |  |
| 16 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 17 | python -m pytest tests/integration/read_screens/test_rs_9_sessions.py -q -p no:c | 0 | 36 passed in 0.66s |  |
| 18 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 19 | python -m pytest tests/integration/read_screens/test_rs_10_accounts.py -q -p no: | 0 | 43 passed in 0.73s |  |
| 20 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 21 | python -m pytest tests/integration/read_screens/test_rs_11_cost.py -q -p no:cach | 0 | 42 passed in 0.75s |  |
| 22 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 23 | python -m pytest tests/integration/read_screens/test_rs_12_compose.py -q -p no:c | 0 | 34 passed in 0.58s |  |
| 24 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/rea | 0 | không có đầu ra |  |
| 25 | python -m pytest tests/integration/read_screens/test_rs_13_prod_e2e.py -q -p no: | 0 | 88 passed, 1 warning in 5.30s |  |
| 26 | python -c "import pathlib; t = pathlib.Path('tests/integration/read_screens/test | 0 | không có đầu ra |  |

## Chuỗi 23/23

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_vo | 0 | không có đầu ra |  |
| 2 | python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_me | 0 | không có đầu ra |  |
| 3 | python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_w | 0 | không có đầu ra |  |
| 4 | python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status | 0 | không có đầu ra |  |
| 6 | python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_a | 0 | 1 passed in 0.42s |  |

## Tổng kết kết quả kiểm thử

- Tổng số đoạn lệnh đã chạy: 467/467
- Đạt: 467 (exit code 0)
- Thất bại: 0 (exit code khác 0)
- Trạng thái kiểm thử: ĐẠT
